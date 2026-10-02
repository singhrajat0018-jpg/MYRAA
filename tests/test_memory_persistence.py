"""Tests for the Python Brain memory persistence (F1 hardening)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from desktop_agent.brain.memory.manager import MemoryManager
from desktop_agent.brain.memory import persistence


def _tmp_file() -> str:
    tmp = Path(tempfile.mkdtemp(prefix="myraa_mem_test_"))
    return str(tmp / "brain_memory.json")


def test_round_trip_survives_restart():
    path = _tmp_file()
    m1 = MemoryManager(store_path=path)
    m1.remember_fact("user_name", "Rahul")
    m1.remember_event("user asked about NIFTY")
    m1.remember_reflection("user prefers Hinglish explanations")

    # Fresh manager = new session after restart.
    m2 = MemoryManager(store_path=path)
    assert len(m2.semantic._knowledge) == 1
    assert m2.semantic._knowledge["user_name"].value == "Rahul"
    assert len(m2.episodic._events) == 2


def test_clear_persists_empty():
    path = _tmp_file()
    m1 = MemoryManager(store_path=path)
    m1.remember_fact("k", "v")
    m1.clear()

    m2 = MemoryManager(store_path=path)
    assert len(m2.semantic._knowledge) == 0
    assert len(m2.episodic._events) == 0


def test_corrupt_store_recovers_from_backup():
    path = _tmp_file()
    m1 = MemoryManager(store_path=path)
    m1.remember_fact("user_name", "Rahul")
    m1.remember_event("a useful event")
    m1.remember_event("a second event")  # .bak lags one write behind the live file

    # Corrupt the live store.
    raw = Path(path).read_text(encoding="utf-8")
    Path(path).write_text(raw + "GARBAGE!!", encoding="utf-8")

    m2 = MemoryManager(store_path=path)  # must not raise
    assert len(m2.semantic._knowledge) == 1
    assert len(m2.episodic._events) >= 1

    # Corrupt file was quarantined, not deleted.
    quarantined = [p for p in os.listdir(os.path.dirname(path)) if ".corrupt." in p]
    assert len(quarantined) >= 1


def test_missing_store_starts_empty():
    path = _tmp_file()
    m = MemoryManager(store_path=path)
    assert len(m.semantic._knowledge) == 0
    assert len(m.episodic._events) == 0


def test_write_is_atomic_leaves_valid_json():
    path = _tmp_file()
    m1 = MemoryManager(store_path=path)
    m1.remember_fact("a", 1)
    m1.remember_fact("b", 2)

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert set(payload["semantic"]["facts"].keys()) == {"a", "b"}
    assert payload["version"] == 1


def test_process_reflection_safe_without_blackboard():
    m = MemoryManager(store_path=_tmp_file())
    m.process_reflection()  # must not raise (blackboard is None)


def test_remember_fact_signature():
    m = MemoryManager(store_path=_tmp_file())
    m.remember_fact("key", {"nested": [1, 2, 3]})
    m.remember_fact("empty_value", None)
    assert m.semantic._knowledge["key"].value == {"nested": [1, 2, 3]}


def test_sensitive_fact_rejected_never_stored():
    path = _tmp_file()
    m = MemoryManager(store_path=path)
    assert m.remember_fact("user_name", "Rahul") is True
    assert m.remember_fact("gemini_api_key", "AIzaSyFakeKey000000000000000000000") is False
    assert m.remember_fact("credentials", "my password is hunter2") is False
    assert m.remember_fact("safe_note", {"value": "lasagna", "count": 3}) is True
    assert len(m.semantic._knowledge) == 2


def test_sensitive_event_rejected_never_stored():
    path = _tmp_file()
    m = MemoryManager(store_path=path)
    assert m.remember_event("user talked about NIFTY strategy") is True
    assert m.remember_event("user shared sk-abcdefghijklmnopqrstuvwxyz") is False
    assert len(m.episodic._events) == 1


def test_sensitive_reflection_rejected():
    path = _tmp_file()
    m = MemoryManager(store_path=path)
    assert m.remember_reflection("user prefers Hinglish") is True
    assert m.remember_reflection("api key: AIzaSyABC12345678901234567890") is False


def test_secrets_scrubbed_on_restore():
    path = _tmp_file()
    m = MemoryManager(store_path=path)
    m.remember_fact("user_name", "Rahul")
    # Simulate a legacy store containing a secret.
    m.semantic.store("leak", "client_secret=superS3cretValue")
    m._persist()

    m2 = MemoryManager(store_path=path)
    keys = set(m2.semantic._knowledge.keys())
    assert "user_name" in keys
    assert "leak" not in keys


def test_is_sensitive_text_recursive():
    assert persistence.is_sensitive_text("password: hunter2") is True
    assert persistence.is_sensitive_text({"nested": {"otp": "123456"}}) is True
    assert persistence.is_sensitive_text(["ok", "AIzaSyFake0000000000000000"]) is True
    assert persistence.is_sensitive_text("normal conversation about food") is False
    assert persistence.is_sensitive_text({"nested": [1, 2, {"x": "y"}]}) is False