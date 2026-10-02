"""
MYRAA Memory 2.0 — M11: Lifecycle Management tests.

Covers status-transition integrity (validity map, idempotency, terminal
states), temporal decay, explicit lifecycle commands (ARCHIVE/BURY/RETRACT/
EXPIRE/RESTORE) through the M10 command engine, and decay wired into
consolidate().
"""

import os
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from desktop_agent.brain.memory.memory_commands import MemoryCommandEngine
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryScope,
    MemoryStatus,
    MemoryType,
    Provenance,
    RetentionPolicy,
)


def make_manager():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    manager = UnifiedMemoryManager(path)
    manager.clear()
    return manager


def make_record(content, mtype=MemoryType.SEMANTIC, scope=MemoryScope.USER,
                retention=RetentionPolicy.MEDIUM_TERM, importance=0.7,
                created_at=None):
    return MemoryRecord(
        type=mtype,
        content=content,
        summary=content[:120],
        source="test",
        scope=scope,
        retention_policy=retention,
        importance=importance,
        confidence=0.9,
        provenance=Provenance.USER_EXPLICIT,
        created_at=created_at if created_at is not None else time.time(),
    )


def store_fresh(manager, content, **kw):
    """Store a record while fresh (write-governance rejects already-expired
    candidates), then return the stored record so callers can age it."""
    rec = make_record(content, **kw)
    assert manager.remember(rec), f"store failed: {content}"
    for r in manager.get_all():
        if r.id == rec.id:
            return r
    return rec


def age(record, seconds):
    record.created_at = time.time() - seconds


class TestLifecycleTransitions(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()

    def _rec(self, memory_id):
        for r in self.manager.get_all():
            if r.id == memory_id:
                return r
        return None

    def _store(self):
        rec = make_record("a testable fact")
        self.assertTrue(self.manager.remember(rec))
        return rec

    def test_active_to_archived(self):
        rec = self._store()
        self.assertTrue(self.manager.archive(rec.id))
        self.assertEqual(self._rec(rec.id).status, MemoryStatus.ARCHIVED)
        self.assertIn("archived_at", self._rec(rec.id).metadata)

    def test_active_to_retracted(self):
        rec = self._store()
        self.assertTrue(self.manager.retract(rec.id))
        self.assertEqual(self._rec(rec.id).status, MemoryStatus.RETRACTED)

    def test_active_to_expired(self):
        rec = self._store()
        self.assertTrue(self.manager.expire(rec.id))
        self.assertEqual(self._rec(rec.id).status, MemoryStatus.EXPIRED)

    def test_active_to_conflicted(self):
        rec = self._store()
        self.assertTrue(self.manager.mark_conflict(rec.id, conflicts_with=["x"]))
        stored = self._rec(rec.id)
        self.assertEqual(stored.status, MemoryStatus.CONFLICTED)
        self.assertEqual(stored.metadata["conflicts_with"], ["x"])

    def test_bury_is_archive(self):
        rec = self._store()
        self.assertTrue(self.manager.bury(rec.id))
        stored = self._rec(rec.id)
        self.assertEqual(stored.status, MemoryStatus.ARCHIVED)
        self.assertTrue(stored.metadata.get("buried"))

    def test_restore_archived(self):
        rec = self._store()
        self.manager.archive(rec.id)
        self.assertTrue(self.manager.restore(rec.id))
        self.assertEqual(self._rec(rec.id).status, MemoryStatus.ACTIVE)

    def test_restore_expired_and_conflicted(self):
        rec = self._store()
        self.manager.expire(rec.id)
        self.assertTrue(self.manager.restore(rec.id))
        rec2 = make_record("a distinct fact")
        self.assertTrue(self.manager.remember(rec2))
        self.manager.mark_conflict(rec2.id)
        self.assertTrue(self.manager.restore(rec2.id))
        self.assertEqual(self._rec(rec2.id).status, MemoryStatus.ACTIVE)

    def test_restore_rejected_from_superseded(self):
        rec = self._store()
        rec2 = make_record("a testable fact 2")
        self.assertTrue(self.manager.remember(rec2))
        rec.supersede_by(rec2.id)
        rec.status = MemoryStatus.SUPERSEDED
        self.assertFalse(self.manager.restore(rec.id))

    def test_restore_rejected_from_deleted(self):
        rec = self._store()
        self.manager.forget(rec.id)
        self.assertFalse(self.manager.restore(rec.id))

    def test_transition_idempotent_noop(self):
        rec = self._store()
        self.assertTrue(self.manager.archive(rec.id))
        self.assertTrue(self.manager.archive(rec.id))  # safe no-op
        stored = self._rec(rec.id)
        self.assertEqual(stored.status, MemoryStatus.ARCHIVED)
        self.assertIn("noop_transitions", stored.metadata["lifecycle"])

    def test_invalid_transition_rejected(self):
        rec = self._store()
        # DELETED is terminal: nothing may revive it via the validity map.
        self.manager.forget(rec.id)
        self.assertFalse(self.manager.transition_status(rec.id, MemoryStatus.ACTIVE))

    def test_illegal_direct_jump_rejected(self):
        rec = self._store()
        # SUPERSEDED may only go to ARCHIVED/DELETED.
        rec2 = make_record("another fact")
        self.assertTrue(self.manager.remember(rec2))
        rec.supersede_by(rec2.id)
        rec.status = MemoryStatus.SUPERSEDED
        self.assertFalse(self.manager.transition_status(rec.id, MemoryStatus.RETRACTED))
        self.assertTrue(self.manager.transition_status(rec.id, MemoryStatus.ARCHIVED))

    def test_lifecycle_audit_trail(self):
        rec = self._store()
        self.manager.archive(rec.id, reason="user requested")
        stored = self._rec(rec.id)
        transitions = stored.metadata["lifecycle"]["transitions"]
        self.assertEqual(transitions[-1]["from"], "active")
        self.assertEqual(transitions[-1]["to"], "archived")
        self.assertEqual(transitions[-1]["reason"], "user requested")
        self.assertEqual(stored.metadata["last_lifecycle_reason"], "user requested")

    def test_get_by_status(self):
        rec = self._store()
        self.manager.archive(rec.id)
        self.assertEqual(len(self.manager.get_by_status(MemoryStatus.ARCHIVED)), 1)
        self.assertEqual(len(self.manager.get_by_status(MemoryStatus.ACTIVE)), 0)

    def test_lifecycle_stats(self):
        rec = self._store()
        self.manager.archive(rec.id)
        stats = self.manager.lifecycle_stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["active"], 0)
        self.assertEqual(stats["by_status"]["archived"], 1)


class TestDecay(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()

    def _rec(self, memory_id):
        for r in self.manager.get_all():
            if r.id == memory_id:
                return r
        return None

    def test_ephemeral_expires(self):
        rec = store_fresh(self.manager, "transient note",
                          retention=RetentionPolicy.EPHEMERAL)
        age(rec, 600)
        stats = self.manager.run_decay()
        self.assertEqual(stats["expired"], 1)
        self.assertEqual(self._rec(rec.id).status, MemoryStatus.EXPIRED)

    def test_low_importance_old_memory_archives(self):
        rec = store_fresh(self.manager, "old mediocre fact",
                          retention=RetentionPolicy.SHORT_TERM, importance=0.8)
        age(rec, 3 * 24 * 3600)
        stats = self.manager.run_decay()
        self.assertEqual(stats["archived"], 1)
        self.assertEqual(self._rec(rec.id).status, MemoryStatus.ARCHIVED)

    def test_fresh_memory_not_decayed(self):
        rec = make_record("recent fact", retention=RetentionPolicy.SHORT_TERM)
        self.manager.remember(rec)
        stats = self.manager.run_decay()
        self.assertEqual(stats["transitioned"], 0)
        self.assertEqual(self.manager.recall(rec.id).status, MemoryStatus.ACTIVE)

    def test_user_defined_and_permanent_never_decay(self):
        rec1 = store_fresh(self.manager, "user pin",
                           retention=RetentionPolicy.USER_DEFINED)
        rec2 = store_fresh(self.manager, "identity fact",
                           retention=RetentionPolicy.PERMANENT)
        age(rec1, 10 * 24 * 3600)
        age(rec2, 10 * 24 * 3600)
        stats = self.manager.run_decay()
        self.assertEqual(stats["transitioned"], 0)
        self.assertEqual(self.manager.get_active_count(), 2)

    def test_decay_in_consolidate(self):
        rec = store_fresh(self.manager, "old ephemeral",
                          retention=RetentionPolicy.EPHEMERAL)
        age(rec, 600)
        stats = self.manager.consolidate()
        self.assertEqual(stats["decay"]["expired"], 1)

    def test_decay_is_idempotent(self):
        rec = store_fresh(self.manager, "old ephemeral 2",
                          retention=RetentionPolicy.EPHEMERAL)
        age(rec, 600)
        self.manager.run_decay()
        second = self.manager.run_decay()
        self.assertEqual(second["transitioned"], 0)

    def test_expired_low_importance_expires_not_archives(self):
        rec = store_fresh(self.manager, "stale weak",
                          retention=RetentionPolicy.SHORT_TERM, importance=0.2)
        age(rec, 3 * 24 * 3600)
        rec.importance = 0.1  # scoring may raise it; force genuinely low value
        stats = self.manager.run_decay()
        self.assertEqual(stats["expired"], 1)
        self.assertEqual(stats["archived"], 0)


class TestLifecycleCommands(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()
        self.engine = MemoryCommandEngine(self.manager)

    def _store(self, content, **kw):
        rec = make_record(content, **kw)
        self.assertTrue(self.manager.remember(rec))
        return rec

    def test_archive_command(self):
        self._store("the build script is run")
        result = self.engine.handle("archive the memory about build script")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "ARCHIVE")
        self.assertEqual(self.manager.get_active_count(), 0)
        archived = self.manager.get_by_status(MemoryStatus.ARCHIVED)
        self.assertEqual(len(archived), 1)

    def test_bury_command(self):
        self._store("old deployment detail")
        result = self.engine.handle("bury the memory about deployment detail")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "BURY")
        buried = self.manager.get_by_status(MemoryStatus.ARCHIVED)
        self.assertTrue(buried[0].metadata.get("buried"))

    def test_retract_command(self):
        rec = self._store("the previous plan")
        result = self.engine.handle("retract the memory about previous plan")
        self.assertTrue(result.success)
        self.assertEqual(self.manager.get_by_status(MemoryStatus.RETRACTED)[0].id, rec.id)

    def test_expire_command(self):
        rec = self._store("outdated pricing note")
        result = self.engine.handle("expire the memory about outdated pricing")
        self.assertTrue(result.success)
        self.assertEqual(self.manager.get_by_status(MemoryStatus.EXPIRED)[0].id, rec.id)

    def test_restore_command(self):
        rec = self._store("the api endpoint")
        self.manager.archive(rec.id)
        result = self.engine.handle("restore the memory about api endpoint")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "RESTORE")
        self.assertEqual(self.manager.recall(rec.id).status, MemoryStatus.ACTIVE)

    def test_archive_command_no_match_is_noop(self):
        self._store("unrelated thing")
        result = self.engine.handle("archive the memory about quantum")
        self.assertTrue(result.success)
        self.assertEqual(self.manager.get_active_count(), 1)
        self.assertIn("nothing changed", result.message)

    def test_restore_command_no_match(self):
        result = self.engine.handle("restore the memory about nonexistent topic")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "RESTORE")
        self.assertIn("No archived", result.message)

    def test_lifecycle_command_idempotent(self):
        rec = self._store("the config value")
        self.engine.handle("archive the memory about config value")
        result = self.engine.handle("archive the memory about config value")
        self.assertTrue(result.success)
        self.assertEqual(self.manager.get_by_status(MemoryStatus.ARCHIVED)[0].id, rec.id)

    def test_restore_then_recall_works(self):
        rec = self._store("the meeting time")
        self.engine.handle("archive the memory about meeting time")
        self.engine.handle("restore the memory about meeting time")
        result = self.engine.handle("what do you remember about meeting time?")
        self.assertTrue(any("meeting time" in r.content for r in result.records))


if __name__ == "__main__":
    unittest.main()