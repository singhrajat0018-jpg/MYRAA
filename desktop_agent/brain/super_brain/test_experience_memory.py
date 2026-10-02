"""
Tests for MYRAA Memory 2.0 M8: ExperienceEngine writes MemoryRecords.

Verifies that recorded Super-Brain experiences are mirrored into the unified
memory store (Memory 2.0) as long-term EXPERIENCE records, that the write is
best-effort (never breaks execution), and that existing hint-layer behavior is
preserved.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from desktop_agent.brain.super_brain.experience import Experience, ExperienceEngine
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import MemoryType, MemoryStatus


class TestExperienceMemory(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = UnifiedMemoryManager(self.temp_file.name)
        self.engine = ExperienceEngine(memory_2_0=self.manager)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def _experience(self, success=True, verified=True, capability="OPEN_APPLICATION",
                    tools=None, lesson="", request_id="req-1"):
        return Experience(
            request_id=request_id,
            goal_text="Open the editor",
            capability=capability,
            route_decision="BRAIN",
            success=success,
            tool_sequence=tools or ["openApplication", "activateWindow"],
            outcome_message="Editor opened" if success else "Editor not found",
            verification_method="window_title",
            verified=verified,
            recovery="" if success else "retry",
            replan_count=0 if success else 1,
            duration_ms=123.4,
            lesson=lesson,
        )

    # ------------------------------------------------------------------

    def test_verified_success_writes_experience_record(self):
        self.engine.record(self._experience(success=True, verified=True))

        records = self.manager.recall_by_type(MemoryType.EXPERIENCE)
        self.assertEqual(len(records), 1)

        rec = records[0]
        self.assertIn("Open the editor", rec.content)
        self.assertIn("success", rec.tags)
        self.assertIn("OPEN_APPLICATION", rec.tags)
        self.assertTrue(rec.metadata["verified"])
        self.assertEqual(rec.metadata["request_id"], "req-1")
        self.assertEqual(rec.status, MemoryStatus.ACTIVE)
        self.assertGreaterEqual(rec.confidence, 0.6)

    def test_failure_writes_lower_importance_record(self):
        self.engine.record(self._experience(success=False, verified=False))

        records = self.manager.recall_by_type(MemoryType.EXPERIENCE)
        self.assertEqual(len(records), 1)
        self.assertIn("failure", records[0].tags)
        self.assertLess(records[0].importance, 0.8)
        self.assertLess(records[0].confidence, 0.9)

    def test_no_store_keeps_recording_working(self):
        engine = ExperienceEngine()
        engine.record(self._experience())
        self.assertEqual(engine.count(), 1)
        self.assertEqual(len(engine.history()), 1)
        self.assertEqual(engine.success_rate("OPEN_APPLICATION"), 1.0)

    def test_broken_store_never_breaks_execution(self):
        class BrokenStore:
            def remember(self, record):
                raise RuntimeError("store down")

        engine = ExperienceEngine(memory_2_0=BrokenStore())
        engine.record(self._experience())  # must not raise
        self.assertEqual(engine.count(), 1)

    def test_hint_layer_preserved(self):
        engine = ExperienceEngine(memory_2_0=self.manager)
        engine.record(self._experience(tools=["openApplication"]))
        engine.record(self._experience(tools=["openApplication"]))
        self.assertEqual(engine.hint_for("OPEN_APPLICATION"),
                         ["openApplication"])
        self.assertEqual(engine.hint_for("UNKNOWN_CAP"), [])

    def test_lessons_available(self):
        engine = ExperienceEngine(memory_2_0=self.manager)
        engine.record(self._experience(lesson="Verify window title after open"))
        self.assertIn("Verify window title after open", engine.lessons())


if __name__ == "__main__":
    unittest.main()