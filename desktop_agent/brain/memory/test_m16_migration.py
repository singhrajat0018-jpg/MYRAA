"""
M16: legacy memory migration + backward compatibility tests.

Covers the DETECT -> BACKUP -> NORMALIZE -> VALIDATE -> MIGRATE -> DEDUP
-> CONFLICT CHECK -> VERIFY -> ACTIVATE pipeline, including the safety
contract (never destroys originals, idempotent, scrubs secrets).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest

from desktop_agent.brain.memory import persistence
from desktop_agent.brain.memory.migrate_legacy import migrate_legacy_to_unified


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        import json
        json.dump(data, fh, indent=2)


def _legacy_store() -> dict:
    now = 1000.0
    return {
        "version": 1,
        "episodic": {
            "events": [
                {
                    "title": "Morning briefing",
                    "description": "Reviewed NIFTY levels",
                    "timestamp": now,
                    "importance": 0.7,
                    "category": "meeting",
                    "metadata": {"channel": "voice"},
                },
                {
                    "title": "Coding session",
                    "description": "Implemented memory commands",
                    "timestamp": now + 1,
                    "importance": 0.8,
                    "category": "work",
                    "metadata": {},
                },
                {
                    "title": "Coding session",
                    "description": "Implemented memory commands",
                    "timestamp": now + 2,
                    "importance": 0.8,
                    "category": "work",
                    "metadata": {},
                },
            ]
        },
        "semantic": {
            "facts": {
                "user_language": {
                    "value": "Hinglish",
                    "confidence": 0.9,
                    "source": "conversation",
                    "created_at": now,
                    "updated_at": now,
                    "metadata": {},
                },
                "secret_fact": {
                    "value": "api key is sk-abcd1234efgh5678ijkl9012",
                    "confidence": 0.9,
                    "source": "conversation",
                    "created_at": now,
                    "updated_at": now,
                    "metadata": {},
                },
                "broken_importance": {
                    "value": "out of range",
                    "confidence": 5.0,
                    "source": "test",
                    "created_at": now,
                    "updated_at": now,
                    "metadata": {},
                },
            }
        },
    }


class TestMigrateLegacy(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.legacy_path = os.path.join(self.tmp.name, "legacy_memory.json")
        self.unified_path = os.path.join(self.tmp.name, "unified_memory.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrate_basic_success_and_original_preserved(self):
        _write_json(self.legacy_path, _legacy_store())
        before = hashlib.sha256(open(self.legacy_path, "rb").read()).hexdigest()

        report = migrate_legacy_to_unified(self.legacy_path, self.unified_path)

        self.assertTrue(report.detected)
        self.assertTrue(report.backup_written)
        self.assertTrue(os.path.exists(report.source_backup))
        self.assertTrue(report.verified)
        self.assertTrue(report.activated)
        self.assertEqual(report.errors, [])

        # Never destroy the original
        after = hashlib.sha256(open(self.legacy_path, "rb").read()).hexdigest()
        self.assertEqual(before, after)

        # Sensitive fact scrubbed, invalid fact dropped, dup collapsed
        records = persistence.load_unified_memory_records(self.unified_path)
        contents = [r.content for r in records]
        self.assertEqual(len(records), 3)  # 2 episodic (1 dup) + user_language
        self.assertIn("Morning briefing: Reviewed NIFTY levels", contents)
        self.assertIn("Coding session: Implemented memory commands", contents)
        self.assertIn("user_language: Hinglish", contents)
        self.assertFalse(any("sk-" in c for c in contents))
        self.assertFalse(any("out of range" in c for c in contents))

    def test_migrate_scrubs_sensitive_fact(self):
        store = _legacy_store()
        store["semantic"]["facts"]["gmail_token"] = {
            "value": "AIzaSyTestKeyOnlyForUnitTests123456", "confidence": 0.8,
            "source": "x", "created_at": 1, "updated_at": 1, "metadata": {},
        }
        _write_json(self.legacy_path, store)
        report = migrate_legacy_to_unified(self.legacy_path, self.unified_path)
        records = persistence.load_unified_memory_records(self.unified_path)
        self.assertFalse(any("AIza" in r.content for r in records))
        self.assertFalse(any("gmail_token" in r.content for r in records))

    def test_migrate_idempotent_when_already_unified(self):
        _write_json(self.legacy_path, _legacy_store())
        first = migrate_legacy_to_unified(self.legacy_path, self.unified_path)
        self.assertTrue(first.activated)

        second = migrate_legacy_to_unified(self.unified_path, self.unified_path)
        self.assertTrue(second.already_unified)
        self.assertTrue(second.verified)
        self.assertEqual(second.errors, [])

    def test_migrate_merges_into_existing_target(self):
        _write_json(self.legacy_path, _legacy_store())
        existing = {
            "version": 2,
            "records": [{
                "id": "pre-existing-0001", "type": "preference",
                "content": "User prefers dark mode", "summary": "dark mode",
                "source": "brain", "scope": "user", "importance": 0.6,
                "confidence": 0.8, "relevance": 0.5, "salience": 0.5,
                "recency": 0.5, "access_count": 0, "version": 1,
                "status": "active", "tags": [], "entities": [], "relations": {},
                "sensitivity": "public", "retention_policy": "long_term",
                "metadata": {}, "provenance": "system_observed",
                "created_at": 1.0, "updated_at": 1.0, "last_accessed_at": 1.0,
            }],
        }
        _write_json(self.unified_path, existing)

        report = migrate_legacy_to_unified(self.legacy_path, self.unified_path)
        records = persistence.load_unified_memory_records(self.unified_path)
        self.assertEqual(report.records_migrated, 3)  # incoming new records
        self.assertEqual(len(records), 4)  # 1 pre-existing + 3 migrated
        self.assertTrue(report.verified)

    def test_migrate_rejects_unknown_format(self):
        _write_json(self.legacy_path, {"random": "data"})
        report = migrate_legacy_to_unified(self.legacy_path, self.unified_path)
        self.assertFalse(report.detected)
        self.assertFalse(report.activated)
        self.assertTrue(any("not recognized" in e for e in report.errors))

    def test_migrate_missing_source(self):
        report = migrate_legacy_to_unified(
            os.path.join(self.tmp.name, "nope.json"), self.unified_path)
        self.assertFalse(report.detected)
        self.assertTrue(any("not found" in e for e in report.errors))


if __name__ == "__main__":
    unittest.main()