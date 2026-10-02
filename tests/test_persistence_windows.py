"""Deterministic Windows failure-injection tests for Python memory persistence.

Simulates WinError 5 (Access denied) / EPERM during os.replace and verifies:
bounded retry, no process crash, previous valid data preserved, recovery.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from desktop_agent.brain.memory import persistence
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord, MemoryType, MemoryScope, MemoryStatus,
    RetentionPolicy, Provenance,
)

# New persistence-failure test: references the store filename only via the
# authoritative persistence module (see test_runtime_memory_path allowlist).
_STORE_FILENAME = "myraa_brain_memory.json"


def _tmp_file() -> str:
    tmp = Path(tempfile.mkdtemp(prefix="myraa_win_py_"))
    return str(tmp / _STORE_FILENAME)


def _record(content: str, tag: str = "win-test") -> MemoryRecord:
    return MemoryRecord(
        type=MemoryType.SEMANTIC, content=content, summary=content[:50],
        source="test", importance=0.9, confidence=0.9,
        retention_policy=RetentionPolicy.LONG_TERM, scope=MemoryScope.USER,
        status=MemoryStatus.ACTIVE, provenance=Provenance.USER_EXPLICIT,
        tags={tag, content}, metadata={},
    )


def test_winerror5_retry_then_success():
    path = _tmp_file()
    mgr = UnifiedMemoryManager(store_path=path)
    mgr.remember(_record("the user owns a blue bicycle in Berlin", tag="cycling-berlin"))
    mgr.flush()
    assert Path(path).exists()

    calls = {"n": 0}
    real_replace = os.replace

    def flaky(src, dst):
        if str(dst) == path and calls["n"] < 2:
            calls["n"] += 1
            exc = PermissionError(13, "Access is denied", dst)
            exc.winerror = 5  # real WinError 5 shape on Windows
            raise exc
        return real_replace(src, dst)

    with patch("os.replace", side_effect=flaky):
        # Deferred _persist() schedules a 50ms background flush; wait for it
        # INSIDE the patched window so retries hit the injected failure.
        assert mgr.remember(_record("quantum entanglement enables instant spice trading on Mars", tag="quantum-mars")) is True
        import time as _time
        _time.sleep(0.6)
        mgr.flush()

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(payload.get("records", [])) == 2
    assert persistence.persistence_status()["status"] == "HEALTHY"


def test_winerror5_permanent_failure_preserves_previous():
    path = _tmp_file()
    mgr = UnifiedMemoryManager(store_path=path)
    mgr.remember(_record("the user owns a blue bicycle in Berlin", tag="cycling-berlin"))
    mgr.flush()
    good = Path(path).read_text(encoding="utf-8")

    def always_locked(src, dst):
        exc = PermissionError(13, "Access is denied", dst)
        exc.winerror = 5
        raise exc

    with patch("os.replace", side_effect=always_locked):
        mgr.remember(_record("quantum entanglement enables instant spice trading on Mars", tag="quantum-mars"))
        import time as _time
        _time.sleep(0.6)  # let the deferred background flush run inside patch
        mgr.flush()  # must not raise, must not storm

    # Previous valid file preserved byte-for-byte.
    assert Path(path).read_text(encoding="utf-8") == good
    status = persistence.persistence_status()
    assert status["status"] == "DEGRADED"

    # Recovery on next flush after the lock clears. _write_snapshot is a
    # no-op when the store is clean, so touch dirty state via a new record
    # (both records must survive) before flushing.
    mgr.remember(_record("the user adopted a senior rescue dog named Biscuit", tag="dog-biscuit"))
    mgr.flush()
    assert persistence.persistence_status()["status"] == "HEALTHY"
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(payload.get("records", [])) == 3


_SUBJECTS = [
    ("bicycle", "the user owns a blue bicycle in Berlin"),
    ("guitar", "the user practices acoustic guitar every evening"),
    ("marathon", "the user is training for the autumn marathon"),
    ("sourdough", "the user bakes sourdough bread on weekends"),
    ("telescope", "the user bought a telescope for stargazing"),
    ("kayak", "the user kayaks on the lake in summer"),
    ("chess", "the user plays competitive chess online"),
    ("garden", "the user grows tomatoes in a rooftop garden"),
    ("piano", "the user takes jazz piano lessons"),
    ("hiking", "the user hikes alpine trails each spring"),
    ("sailing", "the user sails a small dinghy on Sundays"),
    ("photography", "the user shoots film photography downtown"),
    ("beekeeping", "the user keeps two beehives upstate"),
    ("pottery", "the user throws pottery at a studio"),
    ("cycling", "the user commutes by cycling year round"),
    ("skiing", "the user skis black diamond runs"),
    ("surfing", "the user surfs at dawn in Portugal"),
    ("climbing", "the user climbs indoor bouldering walls"),
    ("birding", "the user spots migratory birds in wetlands"),
    ("fermentation", "the user ferments kimchi at home"),
]


def test_rapid_writes_serialized_no_crash():
    path = _tmp_file()
    mgr = UnifiedMemoryManager(store_path=path)
    for i, (tag, content) in enumerate(_SUBJECTS):
        assert mgr.remember(_record(content, tag=f"hobby-{tag}-{i}")) is True
    mgr.flush()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(payload.get("records", [])) == 20


# ---------------------------------------------------------------------------
# Cooldown contract (regression for the silent-skip / data-loss defect)
#
# Defect: a single process-global cooldown meant a lock on ONE store blocked
# every other store, and atomic_write_json() returned early without signalling
# so callers cleared their pending/dirty flag even though nothing was written.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_persistence_status():
    persistence.reset_persistence_status()
    yield
    persistence.reset_persistence_status()


def test_cooldown_is_scoped_per_store():
    """A failure on store A must not put store B into cooldown."""
    path_a = _tmp_file()
    path_b = _tmp_file()

    persistence._record_persist_failure(OSError(5, "locked", None, 5), path_a)

    assert persistence.is_on_cooldown(path_a) is True
    assert persistence.is_on_cooldown(path_b) is False, \
        "a lock on one store must not block a different store"

    # Store B still writes successfully while A cools down.
    assert persistence.atomic_write_json(path_b, {"ok": True}) is True
    assert Path(path_b).exists()
    assert persistence.is_on_cooldown(path_a) is True


def test_skipped_write_is_not_reported_as_persisted():
    """A cooldown-skipped write must keep the store dirty (no silent success)."""
    path = _tmp_file()
    mgr = UnifiedMemoryManager(store_path=path)
    mgr.remember(_record("the user owns a blue bicycle in Berlin", tag="cycling-berlin"))

    # Put this exact store on cooldown, as a failed Windows replace would.
    persistence._record_persist_failure(OSError(5, "locked", None, 5), path)

    # Background write path respects the cooldown -> must skip, not "succeed".
    mgr._write_snapshot()
    assert mgr._dirty is True, "skipped write must not clear the dirty flag"

    # An explicit durability point bypasses the cooldown and really writes.
    mgr.flush()
    assert mgr._dirty is False
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(payload["records"]) == 1


def test_explicit_flush_bypasses_cooldown_and_recovers():
    """flush() must never be silently swallowed by a background cooldown."""
    path = _tmp_file()
    mgr = UnifiedMemoryManager(store_path=path)
    mgr.remember(_record("the user practices acoustic guitar every evening", tag="guitar"))
    mgr.flush()
    assert persistence.persistence_status()["status"] == "HEALTHY"

    def always_locked(src, dst):
        raise OSError(5, "Access is denied", None, 5)

    with patch("os.replace", side_effect=always_locked):
        mgr.remember(_record("the user kayaks on the lake in summer", tag="kayak"))
        mgr.flush()  # locked: must not raise, must not record success
        assert persistence.persistence_status()["status"] == "DEGRADED"

    assert persistence.is_on_cooldown(path) is True

    # Lock cleared: a forced flush must recover immediately (no 5s wait).
    mgr.flush()
    assert persistence.persistence_status()["status"] == "HEALTHY"
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(payload["records"]) == 2


def test_exhausted_write_reports_false_and_preserves_previous():
    """atomic_write_json must report failure (False) without corrupting state."""
    path = _tmp_file()
    persistence.atomic_write_json(path, {"good": True})
    good = Path(path).read_text(encoding="utf-8")

    def always_locked(src, dst):
        raise OSError(5, "Access is denied", None, 5)

    with patch("os.replace", side_effect=always_locked), \
         patch.object(persistence.time, "sleep", lambda s: None):
        assert persistence.atomic_write_json(path, {"bad": True}) is False

    assert Path(path).read_text(encoding="utf-8") == good, \
        "a failed write must leave the previous good store untouched"
    assert not [f for f in os.listdir(os.path.dirname(path)) if f.endswith(".tmp")]
