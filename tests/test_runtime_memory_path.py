"""
Runtime-data vs frontend-source separation (Vite reload-loop fix).

Proves:
1.  brain memory persists
2.  memory reloads after restart (fresh manager/load cycle)
3.  the canonical memory file lives OUTSIDE Vite's watch scope
    (runtime/memory/, never the project root or src/)
4.  a memory write cannot trigger a Vite page reload
    (all generated paths match vite.config.ts watch.ignored globs)
5.  HMR still works for real frontend sources (globs do NOT match src/**)
6.  the frontend consumes memories through API/WS only (/api/memories,
    memory_sync) - never by watching the storage file
7.  exactly ONE authoritative store definition exists in the backend
8.  agent startup remains healthy (app imports, /health/live = 200)
9.  legacy project-root stores migrate once into runtime/memory/
10. atomic write survives OneDrive-style sharing violations (bounded retry)
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import sys
import tempfile

import pytest

from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from desktop_agent.brain.memory import persistence  # noqa: E402


@pytest.fixture()
def tmp_dir():
    """Self-managed temp dir (pytest tmp_path root is access-denied here)."""
    d = tempfile.mkdtemp(prefix="myraa_mem_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# chokidar/picomatch-style glob matching (subset sufficient for our patterns)
# ---------------------------------------------------------------------------

def matches_ignored(path: str, patterns: list[str]) -> bool:
    norm = path.replace("\\", "/")
    for pat in patterns:
        rx = re.escape(pat).replace(r"\*\*/", "(?:.*/)?").replace(r"\*", "[^/]*")
        if re.fullmatch(rx, norm) or re.fullmatch(rx, os.path.basename(norm)):
            return True
        # '**/runtime/**' must also match 'runtime/x' directly under root
        if pat.endswith("/**") and pat.startswith("**/"):
            seg = pat[len("**/"): -len("/**")]
            if f"/{seg}/" in f"/{norm}":
                return True
    return False


def vite_ignored_globs() -> list[str]:
    with open(os.path.join(PROJECT_ROOT, "vite.config.ts"), "r", encoding="utf-8") as f:
        cfg = f.read()
    m = re.search(r"ignored:\s*\[(.*?)\]", cfg, re.DOTALL)
    assert m, "vite.config.ts must define server.watch.ignored"
    return re.findall(r"'([^']+)'", m.group(1))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("MYRAA_MEMORY_FILE", raising=False)
    monkeypatch.delenv("MYRAA_DATA_DIR", raising=False)


# ---------------------------------------------------------------------------
# 1+2. Persistence round-trip
# ---------------------------------------------------------------------------

def _sample_record():
    from desktop_agent.brain.memory.unified_model import (
        MemoryRecord, MemoryType, MemoryScope, MemoryStatus, RetentionPolicy,
    )
    return MemoryRecord(
        type=MemoryType.SEMANTIC,
        content="test: runtime path fix",
        summary="runtime path fix",
        source="pytest",
        confidence=1.0,
        retention_policy=RetentionPolicy.LONG_TERM,
        scope=MemoryScope.GLOBAL,
        status=MemoryStatus.ACTIVE,
        tags={"test"},
    )


def test_memory_persists(tmp_dir):
    path = os.path.join(tmp_dir, "store.json")
    persistence.save_unified_memory_records([_sample_record()], path)
    assert os.path.isfile(path)
    loaded = persistence.load_unified_memory_records(path)
    assert len(loaded) == 1
    assert loaded[0].content == "test: runtime path fix"


def test_memory_reloads_after_restart(tmp_dir):
    """Simulates restart: save, then load into a fresh UnifiedMemoryManager."""
    from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager

    path = os.path.join(tmp_dir, "store.json")
    persistence.save_unified_memory_records([_sample_record()], path)

    # "Restart": brand-new manager over the same store.
    mgr2 = UnifiedMemoryManager(store_path=path)
    mgr2._load_memories()
    records = list(getattr(mgr2, "_records", {}).values())
    assert records, "fresh manager loaded nothing"
    assert any(getattr(r, "content", "") == "test: runtime path fix"
               for r in records), "memory lost across restart"


# ---------------------------------------------------------------------------
# 3+4. Canonical path outside watch scope; writes can't reload the page
# ---------------------------------------------------------------------------

def test_default_store_is_outside_frontend_watch_scope():
    persistence._migrated_legacy_store = False  # allow fresh resolution
    path = persistence.default_memory_file()
    rel = os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")
    assert rel.startswith("runtime/memory/"), \
        f"canonical store must be runtime/memory/, got {rel}"
    assert "/src/" not in f"/{rel}"
    assert os.path.isabs(path)


def test_memory_writes_cannot_trigger_vite_reload():
    globs = vite_ignored_globs()
    store = persistence.default_memory_file().replace("\\", "/")
    candidates = [store, store + ".tmp", store + ".bak",
                  f"{store}.corrupt.20260823_000000"]
    for c in candidates:
        assert matches_ignored(c, globs), f"{c} would trigger a Vite reload"


# ---------------------------------------------------------------------------
# 5. HMR still works for actual frontend sources
# ---------------------------------------------------------------------------

def test_hmr_sources_not_ignored():
    globs = vite_ignored_globs()
    keep = [
        "src/App.tsx",
        "src/lib/audio.ts",
        "src/components/SettingsPanel.tsx",
        "server.ts",
        "vite.config.ts",
    ]
    for f in keep:
        assert not matches_ignored(f, globs), f"{f} wrongly ignored - HMR broken"


# ---------------------------------------------------------------------------
# 6. Frontend consumes memory via API/event path only
# ---------------------------------------------------------------------------

def test_frontend_uses_api_not_file_watch():
    # App.tsx only mounts the shell; the frontend API consumer lives in
    # src/core/api.ts (memoriesApi). Assert the API path there, preserving
    # the original intent: frontend consumes memories via HTTP API only.
    api_ts = open(os.path.join(PROJECT_ROOT, "src", "core", "api.ts"),
                  encoding="utf-8").read()
    assert "/api/memories" in api_ts
    audio_ts = open(os.path.join(PROJECT_ROOT, "src", "lib", "audio.ts"),
                    encoding="utf-8").read()
    assert "memory_sync" in audio_ts
    # No frontend source may read/watch the storage file directly.
    for rel in ("src/App.tsx", "src/lib/audio.ts", "src/core/api.ts"):
        src = open(os.path.join(PROJECT_ROOT, *rel.split("/")),
                   encoding="utf-8").read()
        assert "myraa_brain_memory" not in src


# ---------------------------------------------------------------------------
# 7. Exactly one authoritative store definition
# ---------------------------------------------------------------------------

def test_no_duplicate_memory_stores():
    allowed = {
        os.path.join(PROJECT_ROOT, "desktop_agent", "brain", "memory",
                     "persistence.py"),  # THE authoritative definition
        os.path.join(PROJECT_ROOT, "vite.config.ts"),  # watch-ignore glob
        os.path.abspath(__file__),  # this test
        os.path.join(PROJECT_ROOT, "tests", "soak_test.py"),  # known reference
        os.path.join(PROJECT_ROOT, "tests", "test_persistence_windows.py"),  # failure-injection test
    }
    hits = []
    for base, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in (
            "node_modules", ".git", "dist", "__pycache__", ".pytest_cache")]
        for fn in files:
            if not fn.endswith((".py", ".ts")):
                continue
            fp = os.path.abspath(os.path.join(base, fn))
            if fp in allowed:
                continue
            try:
                src = open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if "myraa_brain_memory.json" in src:
                hits.append(fp.replace("\\", "/"))
    assert not hits, (
        "store filename referenced outside the authoritative module: "
        f"{hits}"
    )


# ---------------------------------------------------------------------------
# 8. Startup healthy
# ---------------------------------------------------------------------------

def test_startup_healthy():
    from desktop_agent.main import app
    client = TestClient(app)
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# 9. Legacy store migration
# ---------------------------------------------------------------------------

def test_legacy_store_migrates_once(tmp_dir, monkeypatch):
    # Redirect ONLY the canonical dir into tmp; never touch repo data.
    fake_runtime = os.path.join(tmp_dir, "runtime", "memory")
    monkeypatch.setattr(persistence, "_runtime_memory_dir",
                        lambda: fake_runtime)
    monkeypatch.setattr(persistence, "_migrated_legacy_store", False)
    monkeypatch.chdir(tmp_dir)  # legacy store lived in the old default (=cwd)

    legacy = os.path.join(tmp_dir, "myraa_brain_memory.json")
    with open(legacy, "w", encoding="utf-8") as fh:
        json.dump({"version": 2, "records": []}, fh)

    resolved = persistence.default_memory_file()

    assert resolved == os.path.join(fake_runtime, "myraa_brain_memory.json")
    assert not os.path.exists(legacy), "legacy store left behind in watched root"
    assert os.path.isfile(resolved), "legacy store not moved to runtime/memory"


# ---------------------------------------------------------------------------
# 10. Atomic write bounded retry (OneDrive sharing violations)
# ---------------------------------------------------------------------------

def test_atomic_write_retries_on_windows_lock(tmp_dir, monkeypatch):
    target = os.path.join(tmp_dir, "store.json")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("{}")
    calls = {"n": 0}
    real_replace = os.replace
    flaky_locks = {0, 1}  # fail twice, succeed on third attempt

    def flaky_replace(src, dst):
        if calls["n"] in flaky_locks:
            calls["n"] += 1
            # 4-arg form sets .winerror like a real Windows sharing violation
            raise OSError(32, "The process cannot access the file", None, 32)
        calls["n"] += 1
        return real_replace(src, dst)

    monkeypatch.setattr(persistence.os, "replace", flaky_replace)
    monkeypatch.setattr(persistence.time, "sleep", lambda s: None)
    persistence.atomic_write_json(target, {"ok": True})
    with open(target, encoding="utf-8") as fh:
        assert json.load(fh) == {"ok": True}
    assert calls["n"] == 3


# ---------------------------------------------------------------------------
# Windows persistence hardening (WinError 5/32 contract)
# ---------------------------------------------------------------------------

def _winerror(exc_no: int):
    return OSError(exc_no, "locked", None, exc_no)


def test_transient_winerror5_then_success_recovers(tmp_dir, monkeypatch):
    target = os.path.join(tmp_dir, "store.json")
    real_replace = os.replace
    state = {"n": 0}

    def flaky(src, dst):
        if state["n"] < 2:
            state["n"] += 1
            raise _winerror(5)
        return real_replace(src, dst)

    monkeypatch.setattr(persistence.os, "replace", flaky)
    monkeypatch.setattr(persistence.time, "sleep", lambda s: None)
    persistence._record_persist_success()
    persistence.atomic_write_json(target, {"attempt": "final"})
    assert json.loads(open(target, encoding="utf-8").read()) == {"attempt": "final"}
    assert persistence.persistence_status()["status"] == "HEALTHY"


def test_persist_degraded_not_raising_after_exhausted_budget(tmp_dir, monkeypatch):
    target = os.path.join(tmp_dir, "store.json")

    def always_locked(src, dst):
        raise _winerror(5)

    monkeypatch.setattr(persistence.os, "replace", always_locked)
    monkeypatch.setattr(persistence.time, "sleep", lambda s: None)
    persistence._record_persist_success()

    # Must NOT raise even when every attempt is locked.
    persistence.atomic_write_json(target, {"doomed": True})

    status = persistence.persistence_status()
    assert status["status"] == "DEGRADED"
    assert status["last_error"]
    # No tmp litter left behind.
    leftovers = [f for f in os.listdir(tmp_dir) if f.endswith(".tmp")]
    assert leftovers == []
    persistence._record_persist_success()  # reset for other tests


def test_unique_temp_file_per_attempt(tmp_dir, monkeypatch):
    target = os.path.join(tmp_dir, "store.json")
    seen_srcs = []
    real_replace = os.replace

    def spy(src, dst):
        if src.endswith(".tmp"):
            seen_srcs.append(os.path.basename(src))
        if len(seen_srcs) < 3:
            raise _winerror(32)
        return real_replace(src, dst)

    monkeypatch.setattr(persistence.os, "replace", spy)
    monkeypatch.setattr(persistence.time, "sleep", lambda s: None)
    persistence.atomic_write_json(target, {"x": 1})
    assert len(seen_srcs) == 3
    assert len(set(seen_srcs)) == 3, "temp filenames must be unique per attempt"


def test_concurrent_saves_all_land(tmp_dir):
    import threading

    path = os.path.join(tmp_dir, "store.json")
    errors = []

    def writer(i):
        try:
            for j in range(5):
                persistence.atomic_write_json(path, {"writer": i, "iter": j})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writes raised: {errors}"
    data = json.loads(open(path, encoding="utf-8").read())
    assert "writer" in data
    assert not [f for f in os.listdir(tmp_dir) if f.endswith(".tmp")]


def test_repeated_saves_stable(tmp_dir):
    path = os.path.join(tmp_dir, "store.json")
    for i in range(10):
        persistence.save_unified_memory_records([_sample_record()], path)
    loaded = persistence.load_unified_memory_records(path)
    assert len(loaded) >= 1


def test_corrupted_store_recovers_from_backup(tmp_dir):
    path = os.path.join(tmp_dir, "store.json")
    # Two writes so the first good state lands in the .bak.
    persistence.save_unified_memory_records([_sample_record()], path)
    persistence.save_unified_memory_records([_sample_record()], path)
    # .bak now holds a valid copy; corrupt the live store.
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{ this is not json !!!")
    records = persistence.load_unified_memory_records(path)
    assert any(r.content == "test: runtime path fix" for r in records), \
        "backup recovery failed"


def test_stale_tmp_cleanup_on_load(tmp_dir, monkeypatch):
    path = os.path.join(tmp_dir, "store.json")
    persistence.save_unified_memory_records([_sample_record()], path)
    stale = path + ".999.123.0.tmp"
    old = __import__("time").time() - 400
    with open(stale, "w", encoding="utf-8") as fh:
        fh.write("junk")
    os.utime(stale, (old, old))

    persistence.load_unified_memory_records(path)

    assert not os.path.exists(stale), "stale temp file was not cleaned up"
