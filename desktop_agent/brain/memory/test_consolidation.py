"""
Tests for MYRAA Memory 2.0 M7: Authoritative Consolidation.

Verifies the WORKING -> EPISODIC -> SEMANTIC pipeline, duplicate/merge
behavior, contradiction detection with confidence updating, scope isolation,
idempotency, and the runtime consolidation loop.
"""

import os
import tempfile
import threading
import time
import unittest

from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord, MemoryType, MemoryScope, MemoryStatus,
    RetentionPolicy, Provenance,
)


class TestConsolidation(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = UnifiedMemoryManager(self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _working(self, content, source="observer", conversation_id=None,
                 scope=MemoryScope.SESSION):
        return MemoryRecord(
            type=MemoryType.WORKING,
            content=content,
            source=source,
            importance=0.5,
            confidence=0.6,
            retention_policy=RetentionPolicy.SHORT_TERM,
            scope=scope,
            conversation_id=conversation_id,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.SYSTEM_OBSERVED,
        )

    def _episodic(self, content, source="test", scope=MemoryScope.USER):
        return MemoryRecord(
            type=MemoryType.EPISODIC,
            content=content,
            source=source,
            importance=0.7,
            confidence=0.6,
            retention_policy=RetentionPolicy.MEDIUM_TERM,
            scope=scope,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.SYSTEM_OBSERVED,
        )

    def _semantic(self, content, source="test", scope=MemoryScope.USER):
        return MemoryRecord(
            type=MemoryType.SEMANTIC,
            content=content,
            source=source,
            importance=0.7,
            confidence=0.6,
            retention_policy=RetentionPolicy.LONG_TERM,
            scope=scope,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.SYSTEM_OBSERVED,
        )

    # ------------------------------------------------------------------
    # WORKING -> EPISODIC
    # ------------------------------------------------------------------

    def test_working_to_episodic_promotion(self):
        wm = self._working("Observed: user opened the editor")
        self.assertTrue(self.manager.remember(wm))

        episodic = self.manager.consolidate_working_to_episodic()
        self.assertEqual(len(episodic), 1)
        self.assertEqual(episodic[0].type, MemoryType.EPISODIC)
        self.assertEqual(episodic[0].content, "Observed: user opened the editor")
        self.assertEqual(episodic[0].status, MemoryStatus.ACTIVE)

        with self.manager._lock:
            stored = self.manager._records.get(wm.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, MemoryStatus.ARCHIVED)
        self.assertTrue(stored.metadata.get("consolidated_at"))

        episodic_again = self.manager.consolidate_working_to_episodic()
        self.assertEqual(len(episodic_again), 0)

    def test_working_to_episodic_merge_duplicates(self):
        self.assertTrue(self.manager.remember(self._working("Same event happened")))
        self.assertTrue(self.manager.remember(self._working("Same event happened")))

        self.manager.consolidate_working_to_episodic()
        active_episodic = self.manager.recall_by_type(MemoryType.EPISODIC)
        self.assertEqual(len(active_episodic), 1)
        self.assertEqual(active_episodic[0].content, "Same event happened")

    def test_conversation_scoped_consolidation(self):
        wm = self._working(
            "Message: user asked for the weather",
            conversation_id="conv-123",
            scope=MemoryScope.CONVERSATION,
        )
        self.assertTrue(self.manager.remember(wm))

        episodic = self.manager.consolidate_working_to_episodic()
        self.assertEqual(len(episodic), 1)
        self.assertEqual(episodic[0].conversation_id, "conv-123")
        self.assertEqual(episodic[0].scope, MemoryScope.CONVERSATION)

    def test_remember_working_event(self):
        class FakeEvent:
            title = "App opened"
            message = "Chrome was launched"
            source = "observer"
            severity = "info"
            payload = {"app": "chrome"}

        ok = self.manager.remember_working_event(FakeEvent())
        self.assertTrue(ok)

        working = self.manager.recall_by_type(MemoryType.WORKING)
        self.assertEqual(len(working), 1)
        self.assertEqual(working[0].summary, "App opened")
        self.assertEqual(working[0].content, "Chrome was launched")

    # ------------------------------------------------------------------
    # EPISODIC -> SEMANTIC
    # ------------------------------------------------------------------

    def test_episodic_to_semantic_fact_extraction(self):
        em = self._episodic("Team size: 5")
        self.assertTrue(self.manager.remember(em))

        semantic = self.manager.consolidate_episodic_to_semantic()
        self.assertEqual(len(semantic), 1)
        self.assertEqual(semantic[0].type, MemoryType.SEMANTIC)
        self.assertEqual(semantic[0].content, "Team size: 5")
        self.assertIn("Team size", semantic[0].tags)

        with self.manager._lock:
            stored = self.manager._records.get(em.id)
        self.assertEqual(stored.status, MemoryStatus.ARCHIVED)
        self.assertTrue(stored.metadata.get("consolidated_at"))

    def test_episodic_narrative_without_fact_is_consumed(self):
        em = self._episodic("User chatted about the weather in a long conversation")
        self.assertTrue(self.manager.remember(em))

        semantic = self.manager.consolidate_episodic_to_semantic()
        self.assertEqual(len(semantic), 0)
        with self.manager._lock:
            stored = self.manager._records.get(em.id)
        self.assertEqual(stored.status, MemoryStatus.ARCHIVED)

    def test_semantic_contradiction_detection(self):
        em1 = self._episodic("Team size: 5", source="source_a")
        self.assertTrue(self.manager.remember(em1))
        self.manager.consolidate_episodic_to_semantic()

        em2 = self._episodic("Team size: 8", source="source_b")
        self.assertTrue(self.manager.remember(em2))
        self.manager.consolidate_episodic_to_semantic()

        active = self.manager.recall_by_type(MemoryType.SEMANTIC)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].content, "Team size: 8")

        superseded = [m for m in self.manager._records.values()
                      if m.status == MemoryStatus.SUPERSEDED]
        self.assertEqual(len(superseded), 1)
        self.assertEqual(superseded[0].content, "Team size: 5")
        self.assertGreaterEqual(superseded[0].metadata.get("contradictions", 0), 1)
        self.assertLess(superseded[0].confidence, active[0].confidence)

    def test_repeated_observation_reinforces_confidence(self):
        em1 = self._episodic("Server region: us-east")
        self.assertTrue(self.manager.remember(em1))
        self.manager.consolidate_episodic_to_semantic()

        em2 = self._episodic("Server region: us-east")
        self.assertTrue(self.manager.remember(em2))
        self.manager.consolidate_episodic_to_semantic()

        active = self.manager.recall_by_type(MemoryType.SEMANTIC)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].content, "Server region: us-east")
        self.assertGreaterEqual(active[0].metadata.get("observation_count", 0), 2)
        self.assertGreater(active[0].confidence, 0.6)

    # ------------------------------------------------------------------
    # Orchestration / pipeline
    # ------------------------------------------------------------------

    def test_consolidate_orchestrator_full_pipeline(self):
        self.assertTrue(self.manager.remember(
            self._working("Observed: project status meeting started")))
        self.assertTrue(self.manager.remember(
            self._episodic("Budget approved: 100K", source="team")))

        stats = self.manager.consolidate()
        self.assertEqual(stats["working_to_episodic"], 1)
        self.assertGreaterEqual(stats["episodic_to_semantic"], 1)
        self.assertIn("timestamp", stats)

        semantic = self.manager.recall_by_type(MemoryType.SEMANTIC)
        self.assertGreaterEqual(len(semantic), 1)

    def test_consolidation_is_idempotent(self):
        self.assertTrue(self.manager.remember(
            self._episodic("Approved: launch date set to Monday")))

        first = self.manager.consolidate()
        self.assertGreaterEqual(first["episodic_to_semantic"], 1)

        count_after_first = self.manager.get_active_count()

        second = self.manager.consolidate()
        self.assertEqual(second["working_to_episodic"], 0)
        self.assertEqual(second["episodic_to_semantic"], 0)
        self.assertEqual(self.manager.get_active_count(), count_after_first)

    def test_consolidation_respects_scope_isolation(self):
        self.assertTrue(self.manager.remember(
            self._working("Prefers dark mode: true", scope=MemoryScope.USER)))
        self.assertTrue(self.manager.remember(
            self._working("Global default: light theme", scope=MemoryScope.GLOBAL)))

        self.manager.consolidate()

        user_semantic = self.manager.recall_by_scope(MemoryScope.USER)
        self.assertEqual(len(user_semantic), 1)
        self.assertEqual(user_semantic[0].content, "Prefers dark mode: true")

        global_semantic = self.manager.recall_by_scope(MemoryScope.GLOBAL)
        self.assertEqual(len(global_semantic), 1)
        self.assertEqual(global_semantic[0].content, "Global default: light theme")

    # ------------------------------------------------------------------
    # Runtime wiring
    # ------------------------------------------------------------------

    def test_runtime_consolidation_loop(self):
        from desktop_agent.runtime.runtime_manager import RuntimeManager

        class StubBrain:
            class _Autonomy:
                def start(self):
                    pass
            blackboard = None
            autonomy = _Autonomy()

        class StubVision:
            def add_state_listener(self, cb):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            @property
            def is_running(self):
                return False

        self.assertTrue(self.manager.remember(
            self._episodic("Runtime fact: pipeline healthy", source="health")))

        runtime = RuntimeManager(
            brain=StubBrain(),
            vision=StubVision(),
            memory_2_0=self.manager,
            consolidation_interval=0.05,
        )

        # Synchronous pass works immediately.
        stats = runtime.consolidate_now()
        self.assertGreaterEqual(stats["episodic_to_semantic"], 1)
        count_after_first = self.manager.get_active_count()

        # Background loop actually runs (thread alive) and stays idempotent
        # (no further consolidation growth across repeated passes).
        runtime._start_consolidation()
        try:
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if runtime._consolidation_thread and runtime._consolidation_thread.is_alive():
                    break
                time.sleep(0.1)
            self.assertTrue(
                runtime._consolidation_thread is not None and
                runtime._consolidation_thread.is_alive(),
                "consolidation thread should be running",
            )
            time.sleep(0.4)  # let the loop make several passes
        finally:
            runtime._stop_consolidation()

        self.assertFalse(runtime._consolidation_running)
        self.assertEqual(self.manager.get_active_count(), count_after_first)


if __name__ == "__main__":
    unittest.main()