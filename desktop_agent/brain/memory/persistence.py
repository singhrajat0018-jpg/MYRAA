"""
MYRAA Brain memory persistence (F1 hardening).

Safe disk persistence for memory stores. Supports both legacy format
(EpisodicMemory + SemanticMemory) and unified memory model (MemoryRecord).

Properties
----------
- Atomic writes: temp file + os.replace (rename). A crash mid-write cannot
  corrupt the live store.
- Backup/rollback: the previous good copy is kept at ``<file>.bak``.
- Corruption recovery: a corrupt store is quarantined (``<file>.corrupt.<ts>``)
  and the last good backup is loaded; if none exists the store starts empty.
- Concurrency: a process-level lock serializes readers/writers.
- Version-aware migration: can migrate between legacy and unified formats.
- Bounded growth: underlying stores cap their in-memory size; persistence
  mirrors whatever is in memory and never grows unbounded.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict

from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryType,
    MemoryScope,
    MemoryStatus,
    RetentionPolicy,
    Provenance,
)

log = logging.getLogger(__name__)

# Serializes all reads/writes of the brain-memory store in this process.
_LOCK = threading.RLock()

# ---------------------------------------------------------------------------
# Sensitive-data filtering (F1)
#
# Secrets (API keys, passwords, tokens, OTPs, private keys, credit-card shapes)
# must NEVER be persisted as ordinary memories. The same contract as the Node
# memory backend (server_memory.ts). Checked on every remember() and on every
# restore so a pre-existing store that somehow contains a secret is scrubbed.
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS = [
    r"\b(api[ _-]?key|apikey)\b[\s:=]+[A-Za-z0-9_\-]{12,}",
    r"\b(api[ _-]?key|apikey)\b[^\n]{0,10}(?:is|=|:)\s*[A-Za-z0-9_\-]{12,}",
    r"\b(password|passwd|pwd)\b[\s:=]+[^\s]{6,}",
    r"\b(secret|client[_-]?secret)\b[\s:=]+[^\s]{6,}",
    r"\b(access[ _-]?token|auth[ _-]?token|bearer)\b[\s:=]+[^\s]{10,}",
    r"\b(ssh[_-]?key|private[_-]?key|BEGIN [A-Z ]*PRIVATE KEY)\b",
    r"\b(sk-|rk-|ghp_|github_pat_|tvly-|hf_|n8n_|rk_live_)\w{12,}",
    r"\bAIza[A-Za-z0-9_\-]{20,}\b",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bASIA[0-9A-Z]{16}\b",
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    r"(authorization\s*:\s*(bearer|basic)\s+\S+)\b",
    r"\b(session|auth|user)?cookie\b[\s:=]+[A-Za-z0-9_=;.-]{8,}",
    r"\b(session|auth|user)?cookie\b[^\n]{0,8}(?:is|=|:)\s*[A-Za-z0-9_=;.-]{8,}",
    r"\b(?:password|passwd|pwd)\d{2,}\b",
    r"\b\w+\s*:\s*\w+\d{2,}\b",
    r"\b[0-9]{4}[ -][0-9]{4}[ -][0-9]{4}[ -][0-9]{4}\b",
    r"(?<![\d.])[0-9]{15,16}\b",
    r"\b(password|passwd|pwd|secret|client[_-]?secret)\b[^\n]{0,6}is\s+\S*\d\S*",
    r"\b(otp|one[- ]?time[- ]?pin|pin)\b[\s:=]+[0-9]{4,8}",
    r"\b(otp|one[- ]?time[- ]?pin|pin)\b[^\n]{0,6}(?:is|=|:)\s*[0-9]{4,8}",
]

SENSITIVE_KEY_HINTS = ("api_key", "apikey", "password", "passwd", "secret",
                       "token", "otp", "private_key", "client_secret",
                       "cookie", "authorization", "auth_header",
                       "bearer", "credential", "session_key", "secret_key")


def is_sensitive_text(value: Any) -> bool:
    """Recursively scan a value (str/dict/list) for secret-like content."""
    if isinstance(value, str):
        return any(re.search(pattern, value, re.IGNORECASE) for pattern in _SENSITIVE_PATTERNS)
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.lower().strip() in SENSITIVE_KEY_HINTS:
                return True
            if is_sensitive_text(k) or is_sensitive_text(v):
                return True
    if isinstance(value, (list, tuple, set)):
        return any(is_sensitive_text(item) for item in value)
    return False


def default_memory_file() -> str:
    """Where the Python Brain memory store lives.

    ONE authoritative path, shared by MemoryManager, UnifiedMemoryManager,
    repair and migration code.

    Resolution order:
    1. ``MYRAA_MEMORY_FILE`` env (explicit override)
    2. ``MYRAA_DATA_DIR`` env (data dir; filename appended)
    3. Canonical runtime dir: ``<project_root>/runtime/memory/``

    Runtime-generated state must NEVER live inside the frontend source tree:
    Vite watches the project root and a changing JSON file there triggers
    endless HMR/page reloads. The canonical fallback is therefore outside
    any watched source directory.
    """
    env = os.getenv("MYRAA_MEMORY_FILE")
    if env:
        return env
    filename = "myraa_brain_memory.json"
    data_dir = os.getenv("MYRAA_DATA_DIR")
    if data_dir:
        return os.path.join(data_dir, filename)
    path = os.path.join(_runtime_memory_dir(), filename)
    _migrate_legacy_store_if_needed(path)
    return path


def _project_root() -> str:
    # desktop_agent/brain/memory/persistence.py -> project root is 3 up.
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def _runtime_memory_dir() -> str:
    return os.path.join(_project_root(), "runtime", "memory")


_migrated_legacy_store = False


def _migrate_legacy_store_if_needed(new_path: str) -> None:
    """One-time move of a pre-fix store that lived in the project root.

    The old default was ``<cwd>/myraa_brain_memory.json`` which sat inside
    Vite's watch scope and caused reload loops. Move it (plus .bak) to the
    canonical runtime location once; never overwrite newer runtime data.
    """
    global _migrated_legacy_store
    if _migrated_legacy_store:
        return
    _migrated_legacy_store = True
    try:
        legacy = os.path.join(os.getcwd(), "myraa_brain_memory.json")
        if not os.path.isfile(legacy) or os.path.islink(new_path):
            return
        if os.path.abspath(legacy) == os.path.abspath(new_path):
            return
        if os.path.exists(new_path):
            return  # runtime data already authoritative; leave legacy alone
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(legacy, new_path)
        legacy_bak = legacy + ".bak"
        if os.path.isfile(legacy_bak):
            shutil.move(legacy_bak, new_path + ".bak")
        log.info("Migrated brain-memory store %s -> %s", legacy, new_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("Legacy memory-store migration failed (%s); continuing.", exc)


def _serialize_default(value: Any) -> str:
    return repr(value)


# ---------------------------------------------------------------------------
# Persistence health (Windows / OneDrive safety)
#
# A final persist failure must never crash MYRAA: the in-memory store stays
# authoritative, the failure is recorded (telemetry + status) and persistence
# is reported DEGRADED until the next successful write.
# ---------------------------------------------------------------------------

_persist_status = {"ok": True, "last_error": None, "last_failure_ts": 0.0,
                   "last_success_ts": 0.0, "consecutive_failures": 0,
                   "next_attempt_after": 0.0, "_last_log_ts": 0.0}

# Cooldown is tracked PER STORE PATH.
#
# The previous design kept a single process-global cooldown. That had two
# real defects:
#   1. A lock on ONE store silently blocked writes to EVERY other store in
#      the process (they shared one `next_attempt_after`).
#   2. `atomic_write_json()` returned early on cooldown without signalling,
#      so callers could not tell "written" from "skipped" and marked pending
#      changes as persisted.
_cooldowns: Dict[str, float] = {}


def _cooldown_key(path: str) -> str:
    try:
        return os.path.abspath(str(path))
    except Exception:  # noqa: BLE001
        return str(path)


def is_on_cooldown(path: str) -> bool:
    """True when ``path`` is inside its own post-failure backoff window."""
    key = _cooldown_key(path)
    with _LOCK:
        return time.time() < _cooldowns.get(key, 0.0)


def cooldown_remaining_s(path: str) -> float:
    """Seconds left in ``path``'s backoff window (0.0 when not cooling)."""
    key = _cooldown_key(path)
    with _LOCK:
        return max(0.0, round(_cooldowns.get(key, 0.0) - time.time(), 1))


def reset_persistence_status() -> None:
    """Clear global persistence health AND every per-path cooldown.

    Diagnostics/tests use this to start a scenario from a known-clean slate.
    It never hides a failure: it only drops sticky backoff state.
    """
    with _LOCK:
        _persist_status.update({
            "ok": True, "last_error": None, "last_failure_ts": 0.0,
            "last_success_ts": 0.0, "consecutive_failures": 0,
            "next_attempt_after": 0.0, "_last_log_ts": 0.0,
        })
        _cooldowns.clear()


def persistence_status() -> Dict[str, Any]:
    """Health of the memory-persistence layer for /health and telemetry."""
    with _LOCK:
        now = time.time()
        on_cooldown = now < _persist_status["next_attempt_after"]
        return {
            "status": "HEALTHY" if _persist_status["ok"] and not on_cooldown else "DEGRADED",
            "last_error": _persist_status["last_error"],
            "consecutive_failures": _persist_status["consecutive_failures"],
            "on_cooldown": on_cooldown,
            "cooldown_remaining_s": max(0, round(_persist_status["next_attempt_after"] - now, 1)),
            "seconds_since_success": (
                round(now - _persist_status["last_success_ts"], 1)
                if _persist_status["last_success_ts"] else None
            ),
        }


def _record_persist_success(path: str | None = None) -> None:
    """Record a durable write.

    ``path=None`` is the explicit reset hook used by diagnostics/tests and
    clears *every* cooldown. Passing a path clears only that store's cooldown,
    so a healthy store can never unblock a different store whose file is
    still locked (which is what made the old global cooldown a storm risk).
    """
    with _LOCK:
        _persist_status["ok"] = True
        _persist_status["last_error"] = None
        _persist_status["last_success_ts"] = time.time()
        _persist_status["consecutive_failures"] = 0
        _persist_status["next_attempt_after"] = 0.0
        if path is None:
            _cooldowns.clear()
        else:
            _cooldowns.pop(_cooldown_key(path), None)


def _record_persist_failure(exc: Exception, path: str | None = None) -> None:
    with _LOCK:
        _persist_status["ok"] = False
        _persist_status["last_error"] = str(exc)
        _persist_status["last_failure_ts"] = time.time()
        _persist_status["consecutive_failures"] += 1
        # Exponential backoff cooldown: 5s, 10s, 20s, 40s, 80s, max 120s.
        # Prevents the 60s consolidation loop from triggering a new storm
        # while the underlying lock (OneDrive/AV) is still held.
        n = _persist_status["consecutive_failures"]
        cooldown = min(5.0 * (2 ** min(n - 1, 4)), 120.0)
        _persist_status["next_attempt_after"] = time.time() + cooldown
        if path is not None:
            _cooldowns[_cooldown_key(path)] = time.time() + cooldown
    try:
        from desktop_agent.brain.metrics import telemetry

        telemetry.record(
            component="memory_persistence",
            route="atomic_write_json",
            status="error",
            error=str(exc),
        )
    except Exception:  # noqa: BLE001
        pass


def cleanup_stale_tmp_files(path: str, max_age_s: float = 300.0) -> int:
    """Remove orphaned temp files from crashed writes (older than max_age)."""
    p = Path(path)
    removed = 0
    try:
        parent = p.parent
        prefix = p.name + "."
        now = time.time()
        for entry in parent.glob(prefix + "*.tmp"):
            try:
                if now - entry.stat().st_mtime > max_age_s:
                    entry.unlink()
                    removed += 1
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    return removed


def atomic_write_json(path: str, data: Dict[str, Any],
                      *, respect_cooldown: bool = True) -> bool:
    """Write ``data`` to ``path`` atomically, keeping a .bak of the old copy.

    Windows/OneDrive-safe sequence:
      writer-lock -> UNIQUE temp file per attempt -> flush+fsync -> close ->
      bounded retry of os.replace -> atomic replacement.

    Transient WinError 5 (access denied) / 32 (sharing violation) happen while
    OneDrive or AV holds the target; retried with exponential backoff. After
    the bounded budget the write is abandoned WITHOUT raising: in-memory state
    stays authoritative, persistence is marked DEGRADED and telemetry records
    the failure.

    Cooldown: after consecutive failures the *background* write path skips
    further attempts for a bounded, exponentially growing window (5s-120s), so
    the consolidation loop cannot hammer a locked file. Explicit durability
    points (``respect_cooldown=False``) bypass the window so a user-driven
    flush always attempts a real write.

    Returns
    -------
    bool
        True when the payload was durably replaced. False when the write was
        skipped (cooldown) or the bounded retry budget was exhausted. Hard
        (non-transient) OS errors still raise.
    """
    key_path = str(path)
    # Cooldown gate (per store path): if this store recently failed, hold off.
    if respect_cooldown and is_on_cooldown(key_path):
        return False  # skipped; caller must NOT treat state as persisted
    payload = json.dumps(data, indent=2, ensure_ascii=False, default=_serialize_default)
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass
    # Keep a backup of the current good state before overwriting it.
    try:
        if p.exists():
            shutil.copy2(str(p), str(p) + ".bak")
    except Exception:  # noqa: BLE001
        pass

    last_exc: Exception | None = None
    max_attempts = 6
    delay = 0.25
    tmp: str | None = None

    def _discard_tmp() -> None:
        """Remove this attempt's temp file (best-effort)."""
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:  # noqa: BLE001
                pass

    for attempt in range(max_attempts):
        # Unique temp file per attempt: concurrent/crashed writers can never
        # collide on one fixed myraa_brain_memory.json.tmp.
        tmp = f"{p}.{os.getpid()}.{threading.get_ident()}.{attempt}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            last_exc = exc
            if getattr(exc, "winerror", None) not in (5, 32):
                _record_persist_failure(exc, key_path)
                raise
            _discard_tmp()
            time.sleep(delay)
            delay *= 1.5
            continue

        try:
            os.replace(tmp, str(p))
            _record_persist_success(key_path)
            return True
        except OSError as exc:
            # 5 = access denied, 32 = sharing violation (OneDrive / AV lock)
            if getattr(exc, "winerror", None) not in (5, 32):
                _record_persist_failure(exc, key_path)
                raise
            last_exc = exc
            _discard_tmp()
            time.sleep(delay)
            delay *= 1.5

    # Bounded budget exhausted: give up gracefully, keep state in memory.
    _discard_tmp()
    if last_exc is not None:
        # Rate-limit: log at most once per 30s to avoid storm noise.
        now = time.time()
        with _LOCK:
            if now - _persist_status["_last_log_ts"] > 30.0:
                log.warning(
                    "Memory persist failed after %d attempts (%s); "
                    "persistence DEGRADED, state kept in memory.",
                    max_attempts, last_exc,
                )
                _persist_status["_last_log_ts"] = now
        _record_persist_failure(last_exc, key_path)
    return False


def load_json_safe(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """Load JSON with corruption recovery and backup rollback."""
    p = Path(path)
    # Startup-safe: clear orphaned temp files left by crashed writes.
    try:
        cleanup_stale_tmp_files(path)
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except Exception as exc:  # noqa: BLE001
        log.warning("Brain-memory store corrupt (%s); attempting recovery.", exc)
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            os.replace(str(p), f"{p}.corrupt.{ts}")
        except Exception:  # noqa: BLE001
            pass
        try:
            with open(str(p) + ".bak", "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:  # noqa: BLE001
            return default


def save_memory_manager(manager: Any, path: str) -> bool:
    """Serialize EpisodicMemory + SemanticMemory of a MemoryManager to disk.

    Returns True only when the snapshot was durably written.
    """
    episodic = getattr(manager, "episodic", None)
    semantic = getattr(manager, "semantic", None)
    data: Dict[str, Any] = {
        "version": 1,
        "saved_at": time.time(),
        "episodic": _snapshot_episodic(episodic),
        "semantic": _snapshot_semantic(semantic),
    }
    with _LOCK:
        return atomic_write_json(path, data)


def load_memory_manager(manager: Any, path: str) -> bool:
    """Restore EpisodicMemory + SemanticMemory into ``manager``.

    Returns True when a store was actually restored, False otherwise.
    Never raises; a corrupt/missing store simply leaves memory empty.
    """
    try:
        data = load_json_safe(path, {})
        if not isinstance(data, dict):
            return False
        restored = False
        episodic = getattr(manager, "episodic", None)
        semantic = getattr(manager, "semantic", None)
        with _LOCK:
            if episodic is not None:
                restored = _restore_episodic(episodic, data.get("episodic")) or restored
            if semantic is not None:
                restored = _restore_semantic(semantic, data.get("semantic")) or restored
        if restored:
            log.info("Brain memory restored from %s", path)
        return restored
    except Exception as exc:  # noqa: BLE001
        log.warning("Brain memory restore failed (%s); starting empty.", exc)
        return False


# ---------------------------------------------------------------------------
# Episodic memory serialization
# ---------------------------------------------------------------------------

def _snapshot_episodic(store: Any) -> Dict[str, Any]:
    if store is None:
        return {"next_id": 0, "events": []}
    events = store._events if hasattr(store, "_events") else []
    next_id = getattr(store, "_next_id", len(events))
    out = []
    for ev in events:
        item = {
            "id": getattr(ev, "id", 0),
            "timestamp": getattr(ev, "timestamp", time.time()),
            "category": getattr(ev, "category", ""),
            "title": getattr(ev, "title", ""),
            "description": getattr(ev, "description", ""),
            "importance": getattr(ev, "importance", 0.5),
            "metadata": getattr(ev, "metadata", {}) or {},
        }
        out.append(item)
    return {"next_id": next_id, "events": out}


def _restore_episodic(store: Any, data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    events_raw = data.get("events")
    if not isinstance(events_raw, list):
        return False
    try:
        from .episodic_memory import Episode

        events = []
        for item in events_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))
            description = str(item.get("description", ""))
            # Scrub secrets already present in a legacy store.
            if is_sensitive_text(title) or is_sensitive_text(description) \
                    or is_sensitive_text(item.get("metadata", {}) or {}):
                continue
            events.append(
                Episode(
                    id=int(item.get("id", 0)),
                    timestamp=float(item.get("timestamp", time.time())),
                    category=str(item.get("category", "event")),
                    title=title,
                    description=description,
                    importance=float(item.get("importance", 0.5)),
                    metadata=item.get("metadata", {}) or {},
                )
            )
        with store._lock:
            store._events = events
            next_id = int(data.get("next_id", len(events)))
            store._next_id = max(next_id, len(events))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Episodic memory restore failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Semantic memory serialization
# ---------------------------------------------------------------------------

def _snapshot_semantic(store: Any) -> Dict[str, Any]:
    if store is None:
        return {"facts": {}}
    knowledge = getattr(store, "_knowledge", {}) or {}
    facts = {}
    for key, fact in knowledge.items():
        facts[str(key)] = {
            "key": getattr(fact, "key", key),
            "value": getattr(fact, "value", None),
            "confidence": getattr(fact, "confidence", 1.0),
            "source": getattr(fact, "source", "brain"),
            "created_at": getattr(fact, "created_at", time.time()),
            "updated_at": getattr(fact, "updated_at", time.time()),
            "metadata": getattr(fact, "metadata", {}) or {},
        }
    return {"facts": facts}


def _restore_semantic(store: Any, data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    facts_raw = data.get("facts")
    if not isinstance(facts_raw, dict):
        return False
    try:
        from .semantic_memory import Knowledge

        with store._lock:
            store._knowledge = {}
            for key, item in facts_raw.items():
                if not isinstance(item, dict):
                    continue
                fact_value = item.get("value")
                # Scrub secrets already present in a legacy store.
                if is_sensitive_text(str(key)) or is_sensitive_text(fact_value) \
                        or is_sensitive_text(item.get("metadata", {}) or {}):
                    continue
                store._knowledge[str(key)] = Knowledge(
                    key=str(item.get("key", key)),
                    value=item.get("value"),
                    confidence=float(item.get("confidence", 1.0)),
                    source=str(item.get("source", "brain")),
                    created_at=float(item.get("created_at", time.time())),
                    updated_at=float(item.get("updated_at", time.time())),
                    metadata=item.get("metadata", {}) or {},
                )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Semantic memory restore failed: %s", exc)
        return False


# ==========================================================
# Unified Memory Persistence Functions
# ==========================================================

def save_unified_memory_records(records: List[MemoryRecord], path: str,
                               *, respect_cooldown: bool = True) -> bool:
    """
    Save a list of MemoryRecord objects to disk atomically.

    Args:
        records: List of MemoryRecord objects to save
        path: File path to save to
        respect_cooldown: background writes honour the per-store backoff
            window; explicit durability points pass False.

    Returns:
        True when the store was durably replaced, False when the write was
        skipped or abandoned (in-memory state stays authoritative).
    """
    with _LOCK:
        # Convert MemoryRecord objects to dictionaries for JSON serialization
        data = {
            "version": 2,  # Version 2 for unified memory format
            "saved_at": time.time(),
            "records": [record.to_dict() for record in records]
        }
        return atomic_write_json(path, data, respect_cooldown=respect_cooldown)


def load_unified_memory_records(path: str) -> List[MemoryRecord]:
    """
    Load MemoryRecord objects from disk with corruption recovery.

    Args:
        path: File path to load from

    Returns:
        List of MemoryRecord objects (empty list if failed or empty file)
    """
    try:
        data = load_json_safe(path, {})
        if not isinstance(data, dict):
            return []

        # Handle version differences
        version = data.get("version", 1)
        if version == 2:
            # Unified memory format
            records_raw = data.get("records", [])
            if not isinstance(records_raw, list):
                return []

            records = []
            for item in records_raw:
                if not isinstance(item, dict):
                    continue
                # Scrub secrets already present in a legacy store
                if _contains_sensitive_data(item):
                    log.warning("[Memory] Skipping record with sensitive data during load")
                    continue
                try:
                    record = MemoryRecord.from_dict(item)
                    records.append(record)
                except Exception as exc:
                    log.warning(f"[Memory] Failed to load memory record: {exc}")
                    continue
            return records
        elif version == 1:
            # Legacy format - convert to unified format
            return _migrate_legacy_to_unified(data)
        else:
            # Unknown version
            log.warning(f"[Memory] Unknown memory format version: {version}")
            return []
    except Exception as exc:  # noqa: BLE001
        log.warning("Unified memory records load failed (%s); returning empty list.", exc)
        return []


def _contains_sensitive_data(data: Dict[str, Any]) -> bool:
    """
    Check if a memory record dictionary contains sensitive data.

    Args:
        data: Dictionary representation of a memory record

    Returns:
        True if sensitive data detected, False otherwise
    """
    # Check content and summary for sensitive patterns
    content = str(data.get("content", ""))
    summary = str(data.get("summary", ""))

    if is_sensitive_text(content) or is_sensitive_text(summary):
        return True

    # Check metadata if present
    metadata = data.get("metadata", {})
    if isinstance(metadata, dict):
        # Recursive dict scan flags secret-like KEY NAMES too.
        if is_sensitive_text(metadata):
            return True
        for key, value in metadata.items():
            if is_sensitive_text(str(key)) or is_sensitive_text(str(value)):
                return True

    # Check tags and entities
    tags = data.get("tags", [])
    entities = data.get("entities", [])
    if isinstance(tags, list):
        for tag in tags:
            if is_sensitive_text(str(tag)):
                return True
    if isinstance(entities, list):
        for entity in entities:
            if is_sensitive_text(str(entity)):
                return True

    return False


def _migrate_legacy_to_unified(legacy_data: Dict[str, Any]) -> List[MemoryRecord]:
    """
    Migrate legacy memory format to unified memory format.

    Args:
        legacy_data: Dictionary in legacy format

    Returns:
        List of MemoryRecord objects
    """
    records = []

    # Migrate episodic memory
    episodic_data = legacy_data.get("episodic")
    if isinstance(episodic_data, dict):
        events_raw = episodic_data.get("events", [])
        if isinstance(events_raw, list):
            for item in events_raw:
                if not isinstance(item, dict):
                    continue
                # Scrub secrets
                if _contains_sensitive_data_in_legacy_event(item):
                    log.warning("[Memory] Skipping episodic event with sensitive data during migration")
                    continue
                try:
                    record = MemoryRecord(
                        type=MemoryType.EPISODIC,
                        content=f"{item.get('title', '')}: {item.get('description', '')}".strip(),
                        summary=item.get("title", ""),
                        source="legacy_episodic",
                        importance=float(item.get("importance", 0.5)),
                        retention_policy=RetentionPolicy.MEDIUM_TERM,
                        scope=MemoryScope.USER,
                        status=MemoryStatus.ACTIVE,
                        event_time=float(item.get("timestamp", time.time())),
                        tags={str(item.get("category", "event"))},
                        metadata=item.get("metadata", {}) or {}
                    )
                    # Override the timestamps to match the original
                    record.created_at = record.updated_at = record.last_accessed_at = float(item.get("timestamp", time.time()))
                    records.append(record)
                except Exception as exc:
                    log.warning(f"[Memory] Failed to migrate episodic memory item: {exc}")

    # Migrate semantic memory
    semantic_data = legacy_data.get("semantic")
    if isinstance(semantic_data, dict):
        facts_raw = semantic_data.get("facts", {})
        if isinstance(facts_raw, dict):
            for key, item in facts_raw.items():
                if not isinstance(item, dict):
                    continue
                # Scrub secrets
                fact_value = item.get("value")
                if is_sensitive_text(str(key)) or is_sensitive_text(str(fact_value)) \
                        or is_sensitive_text(item.get("metadata", {}) or {}):
                    log.warning(f"[Memory] Skipping semantic fact '{key}' with sensitive data during migration")
                    continue
                try:
                    record = MemoryRecord(
                        type=MemoryType.SEMANTIC,
                        content=f"{key}: {str(fact_value)}",
                        summary=f"{key} = {str(fact_value)[:100]}",
                        source=str(item.get("source", "brain")),
                        confidence=float(item.get("confidence", 1.0)),
                        retention_policy=RetentionPolicy.LONG_TERM,
                        scope=MemoryScope.GLOBAL,
                        status=MemoryStatus.ACTIVE,
                        tags={key},
                        metadata=item.get("metadata", {}) or {}
                    )
                    # Override the timestamps to match the original
                    record.created_at = float(item.get("created_at", time.time()))
                    record.updated_at = float(item.get("updated_at", time.time()))
                    records.append(record)
                except Exception as exc:
                    log.warning(f"[Memory] Failed to migrate semantic memory item '{key}': {exc}")

    return records


def _contains_sensitive_data_in_legacy_event(event_data: Dict[str, Any]) -> bool:
    """
    Check if a legacy episodic event contains sensitive data.

    Args:
        event_data: Dictionary representing a legacy episodic event

    Returns:
        True if sensitive data detected, False otherwise
    """
    title = str(event_data.get("title", ""))
    description = str(event_data.get("description", ""))
    metadata = event_data.get("metadata", {})

    if is_sensitive_text(title) or is_sensitive_text(description):
        return True

    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if is_sensitive_text(str(key)) or is_sensitive_text(str(value)):
                return True

    return False


def merge_memory_relations(existing: Dict[str, List[str]],
                          new: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Merge two relations dictionaries, combining lists for same keys.

    Args:
        existing: Existing relations
        new: New relations to merge

    Returns:
        Merged relations dictionary
    """
    result = existing.copy()

    for key, values in new.items():
        if key in result:
            # Combine lists, removing duplicates
            combined = list(set(result[key]).union(set(values)))
            result[key] = combined
        else:
            result[key] = values.copy()

    return result


def migrate_memory_file_legacy_to_unified(legacy_path: str, unified_path: str) -> bool:
    """
    Migrate a legacy memory file to unified format.

    Args:
        legacy_path: Path to legacy memory file
        unified_path: Path to save unified memory file

    Returns:
        True if migration successful, False otherwise
    """
    try:
        # Load legacy data
        legacy_data = load_json_safe(legacy_path, {})
        if not isinstance(legacy_data, dict):
            log.error("[Memory] Invalid legacy memory file format")
            return False

        # Convert to unified format
        unified_records = _migrate_legacy_to_unified(legacy_data)

        # Save in unified format
        save_unified_memory_records(unified_records, unified_path)

        log.info(f"[Memory] Successfully migrated {len(unified_records)} memories from legacy to unified format")
        return True
    except Exception as exc:
        log.error(f"[Memory] Failed to migrate memory file: {exc}")
        return False