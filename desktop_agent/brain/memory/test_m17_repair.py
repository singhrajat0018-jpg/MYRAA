"""
M17: store repair tooling tests.

Covers safe/idempotent/observable/non-destructive/reversible repair:
quarantine of invalid + sensitive records, fingerprint rebuild, dedup,
reversibility via restore_quarantine.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from desktop_agent.brain.memory import persistence
from desktop_agent.brain.memory.repair import (
    repair_store,
    list_quarantine,
    restore_quarantine,
)
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryType,
    MemoryScope,
    MemoryStatus,
    Provenance,
    RetentionPolicy,
)


def _record(content: str, importance: float = 0.5, **kw) -> MemoryRecord:
    rec = MemoryRecord(
        type=MemoryType.SEMANTIC,
        content=content,
        summary=content[:40],
        source="repair-test",
        scope=MemoryScope.USER,
        importance=importance,
        confidence=0.8,
        provenance=Provenance.SYSTEM_OBSERVED,
        retention_policy=RetentionPolicy.MEDIUM_TERM,
        **kw,
    )
    rec.status = MemoryStatus.ACTIVE
    return rec


class TestRepairStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "store.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, records):
        persistence.save_unified_memory_records(records, self.path)

    def test_repair_clean_store_is_idempotent(self):
        self._write([_record("clean fact one"), _record("clean fact two")])
        report1 = repair_store(self.path)
        self.assertFalse(report1.repaired)
        self.assertEqual(report1.scanned, 2)
        self.assertEqual(report1.active_after, 2)
        self.assertEqual(report1.errors, [])

        # Re-running is a no-op
        report2 = repair_store(self.path)
        self.assertFalse(report2.repaired)

    def test_repair_quarantines_invalid_records(self):
        invalid = _record("bad importance", importance=5.0)
        valid = _record("good fact")
        self._write([invalid, valid])

        report = repair_store(self.path)

        self.assertTrue(report.repaired)
        self.assertEqual(report.invalid, 1)
        self.assertEqual(report.active_before, 2)
        self.assertEqual(report.active_after, 1)
        self.assertTrue(os.path.exists(report.quarantine_file))
        self.assertIn(invalid.id, report.quarantined_ids)

        remaining = persistence.load_unified_memory_records(self.path)
        self.assertEqual([r.content for r in remaining], ["good fact"])

        # Non-destructive: quarantined record is recoverable
        q = list_quarantine(report.quarantine_file)
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0].content, "bad importance")

    def test_repair_quarantines_sensitive_records(self):
        sensitive = _record("api key is sk-abcd1234efgh5678ijkl9012")
        self._write([sensitive, _record("clean fact")])

        report = repair_store(self.path)

        self.assertTrue(report.repaired)
        self.assertEqual(report.sensitive, 1)
        self.assertIn(sensitive.id, report.quarantined_ids)
        remaining = persistence.load_unified_memory_records(self.path)
        self.assertFalse(any("sk-" in r.content for r in remaining))

    def test_repair_rebuilds_fingerprints(self):
        rec = _record("fact before")
        rec.fingerprint = "stale-fingerprint"
        self._write([rec])

        report = repair_store(self.path)

        self.assertEqual(report.rebuilt_fingerprints, 1)
        remaining = persistence.load_unified_memory_records(self.path)
        self.assertNotEqual(remaining[0].fingerprint, "stale-fingerprint")
        self.assertTrue(remaining[0].fingerprint)

    def test_repair_dedup_equivalents(self):
        dup = _record("same content")
        dup2 = _record("same content")
        self._write([dup, dup2])

        report = repair_store(self.path)

        self.assertTrue(report.repaired)
        self.assertEqual(report.duplicates_removed, 1)
        remaining = persistence.load_unified_memory_records(self.path)
        self.assertEqual(len(remaining), 1)

    def test_restore_quarantine_is_reversible(self):
        invalid = _record("bad", importance=5.0)
        valid = _record("good")
        self._write([invalid, valid])
        report = repair_store(self.path)

        restored = restore_quarantine(report.quarantine_file, self.path)

        self.assertTrue(restored.repaired)
        self.assertEqual(restored.active_after, 2)
        self.assertEqual(restored.active_before, 1)
        all_records = persistence.load_unified_memory_records(self.path)
        contents = [r.content for r in all_records]
        self.assertIn("bad", contents)
        self.assertIn("good", contents)

    def test_repair_missing_store(self):
        report = repair_store(os.path.join(self.tmp.name, "missing.json"))
        self.assertTrue(any("not found" in e for e in report.errors))

    def test_restore_quarantine_skips_existing_ids(self):
        rec = _record("fact")
        self._write([rec])
        # Fake a quarantine containing the same id already present
        persistence.save_unified_memory_records([rec], self.path + ".q.json")
        restored = restore_quarantine(self.path + ".q.json", self.path)
        self.assertFalse(restored.repaired)
        self.assertEqual(restored.active_after, 1)


if __name__ == "__main__":
    unittest.main()