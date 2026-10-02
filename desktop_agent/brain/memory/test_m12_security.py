"""
MYRAA Memory 2.0 — M12: Security & Privacy tests.

Verifies the F1 secret-scrubbing contract:
  - every secret family is detected by is_sensitive_text
  - sensitive records are never stored (write governance)
  - metadata / tags / entities / summary are also scanned
  - backups/exports are sanitized and cannot leak secrets
  - API keys are never stored in memory or echoed back
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from desktop_agent.brain.memory.memory_commands import MemoryCommandEngine
from desktop_agent.brain.memory.persistence import is_sensitive_text
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryScope,
    MemoryStatus,
    MemoryType,
    Provenance,
    RetentionPolicy,
)

SECRET_SAMPLES = [
    "my api_key is AbCdEfGhIjKlMnOp1234",
    "password: hunter2secret",
    "the secret is s3cr3t-value1",
    "access token: aBcDeFgHiJkLmNoPqRsTuV",
    "bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "sk-abc123def456ghi789jkl012",
    "rk-abc123def456ghi789jkl012",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXabcdefghij",
    "tvly-ABCDEFGHIJKLMNOPQRSTUVabcdefghijk",
    "hf_abcdefghijklmnopqrstuvwxyz",
    "AIzaSyD3x9u_y0abcdefghijklmnopqrstuvwxyz",
    "AKIAIOSFODNN7EXAMPLE",
    "xoxb-123456789012-abcdefghijklmnop",
    "private key: -----BEGIN RSA PRIVATE KEY-----",
    "otp: 482913",
    "one time pin is 4731",
    "card 4111 1111 1111 1111",
    "Authorization: Bearer aGVsbG8td29ybGQtdG9rZW4tMDEyMzQ1",
    "session cookie: abcdefgh12345678",
    "credential: admin:password123",
]

CLEAN_SAMPLES = [
    "My favourite color is blue",
    "The server region is us-east",
    "NIFTY is trading around 24000",
    "remember to water the plants on Sunday",
    "The meeting is at 3pm",
    "I prefer Hinglish responses",
]


def make_manager():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    manager = UnifiedMemoryManager(path)
    manager.clear()
    return manager


def make_record(content, metadata=None):
    return MemoryRecord(
        type=MemoryType.SEMANTIC,
        content=content,
        summary=content[:120],
        source="test",
        scope=MemoryScope.USER,
        importance=0.8,
        confidence=0.9,
        provenance=Provenance.USER_EXPLICIT,
        retention_policy=RetentionPolicy.USER_DEFINED,
        metadata=metadata or {},
    )


class TestSensitiveDetection(unittest.TestCase):
    def test_detects_all_secret_families(self):
        for sample in SECRET_SAMPLES:
            with self.subTest(sample=sample):
                self.assertTrue(is_sensitive_text(sample),
                                f"not detected: {sample}")

    def test_clean_text_not_flagged(self):
        for sample in CLEAN_SAMPLES:
            with self.subTest(sample=sample):
                self.assertFalse(is_sensitive_text(sample),
                                 f"false positive: {sample}")

    def test_sensitive_key_hint_in_dict(self):
        self.assertTrue(is_sensitive_text({"api_key": "some-value"}))
        self.assertTrue(is_sensitive_text({"password": "anything"}))
        self.assertTrue(is_sensitive_text({"authorization": "Bearer xyz"}))
        self.assertTrue(is_sensitive_text({"cookie": "session=abc"}))
        self.assertTrue(is_sensitive_text({"credential": "user:pass"}))

    def test_sensitive_nested_in_list(self):
        self.assertTrue(is_sensitive_text(["ok", "secret: abcdef123456"]))

    def test_metadata_key_hint_detected(self):
        record = make_record("innocent fact", metadata={"api_key": "value"})
        self.assertTrue(is_sensitive_text(record.metadata))

    def test_summary_and_tags_entities_scanned(self):
        rec = make_record("clean body", metadata={})
        rec.summary = "password: hunter2"
        self.assertTrue(is_sensitive_text(rec.summary))
        rec2 = make_record("clean body")
        rec2.tags = {"secret: abcdef123456"}
        self.assertTrue(is_sensitive_text(list(rec2.tags)))


class TestStoreRejectsSecrets(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()

    def test_each_secret_rejected_at_remember(self):
        for sample in SECRET_SAMPLES:
            with self.subTest(sample=sample):
                ok = self.manager.remember(make_record(sample))
                self.assertFalse(ok, f"stored secret: {sample}")
                self.assertEqual(self.manager.get_active_count(), 0)

    def test_clean_records_stored(self):
        for sample in CLEAN_SAMPLES:
            with self.subTest(sample=sample):
                self.assertTrue(self.manager.remember(make_record(sample)))
        self.assertEqual(self.manager.get_active_count(), len(CLEAN_SAMPLES))

    def test_gemini_key_never_stored(self):
        rec = make_record("Gemini API key AIzaSyD3x9u_y0abcdefghijklmnopqrstuvwxyz")
        self.assertFalse(self.manager.remember(rec))

    def test_legacy_sensitive_records_scrubbed_on_load(self):
        # Persist a store that contains a secret record, then reload: the
        # scrubbing path in persistence must drop it.
        path = self.manager._store_path
        dirty = make_record("clean-ish")
        dirty.metadata = {"password": "hunter2"}
        from desktop_agent.brain.memory import persistence
        persistence.save_unified_memory_records([dirty], path)
        new_manager = UnifiedMemoryManager(path)
        self.assertEqual(new_manager.get_active_count(), 0)

    def test_metadata_secret_rejected(self):
        rec = make_record("clean body", metadata={"token": "abcdefgh12345678"})
        self.assertFalse(self.manager.remember(rec))


class TestBackupAndExportSecurity(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()

    def test_backup_contains_no_secrets(self):
        self.manager.remember(make_record("a normal fact"))
        fd, backup_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(backup_path)
        ok = self.manager.backup(backup_path)
        self.assertTrue(ok)
        with open(backup_path, "r", encoding="utf-8") as f:
            raw = f.read()
        self.assertIn("a normal fact", raw)
        for secret in SECRET_SAMPLES:
            self.assertNotIn(secret, raw)
        os.unlink(backup_path)

    def test_backup_excludes_sensitive_records(self):
        # Inject a dirty record directly into the store bypassing governance.
        dirty = make_record("normal text")
        dirty.metadata = {"password": "hunter2"}
        with self.manager._lock:
            self.manager._records[dirty.id] = dirty
        clean = make_record("clean memory")
        self.manager.remember(clean)
        fd, backup_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(backup_path)
        self.assertTrue(self.manager.backup(backup_path))
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        contents = [r["content"] for r in data["records"]]
        self.assertIn("clean memory", contents)
        self.assertNotIn("normal text", contents)
        os.unlink(backup_path)

    def test_serialized_records_have_no_secrets(self):
        self.manager.remember(make_record("clean memory"))
        for rec in self.manager.get_all_active():
            blob = json.dumps(rec.to_dict())
            self.assertFalse(is_sensitive_text(blob))


class TestCommandSecurity(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()
        self.engine = MemoryCommandEngine(self.manager)

    def test_remember_command_rejects_secrets(self):
        result = self.engine.handle("remember that my API key is sk-abc123def456ghi789")
        self.assertFalse(result.success)
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_remember_command_rejects_credential(self):
        result = self.engine.handle("remember that my password is hunter2secret")
        self.assertFalse(result.success)
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_remember_command_rejects_otp(self):
        result = self.engine.handle("remember that the OTP is 482913")
        self.assertFalse(result.success)
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_update_command_rejects_secret(self):
        self.manager.remember(make_record("my phone number"))
        result = self.engine.handle(
            "update the memory about phone number to my api key AbCdEfGhIjKlMnOp1234")
        self.assertFalse(result.success)
        self.assertEqual(self.manager.get_active_count(), 1)

    def test_recall_never_echoes_secret_shapes(self):
        self.manager.remember(make_record("normal memory"))
        result = self.engine.handle("what do you remember about normal memory?")
        self.assertFalse(is_sensitive_text(result.message))

    def test_engine_rejects_sensitive_metadata_command(self):
        self.manager.remember(make_record("the config value"))
        result = self.engine.handle("remember that the cookie is abcdefgh12345678")
        self.assertFalse(result.success)
        self.assertEqual(self.manager.get_active_count(), 1)


if __name__ == "__main__":
    unittest.main()