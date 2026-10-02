"""
Tests for MYRAA Memory 2.0 M9: UnifiedMemoryManager is authoritative.

Verifies the swap: BrainEngine's live cognitive memory is the unified store,
the legacy-shaped sub-manager views (.working/.episodic/.semantic), context()
gathering, compat entry points, and the observer-event write path all route to
the SAME authoritative store.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryType, MemoryScope, MemoryStatus,
)
from desktop_agent.brain.memory import persistence
from desktop_agent.brain.super_brain.context import ContextFusionEngine


class TestMemory9Authoritative(unittest.TestCase):

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = UnifiedMemoryManager(self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def _brain(self):
        from desktop_agent.brain.brain_engine import BrainEngine
        orchestrator = SimpleNamespace(
            execution_coordinator=SimpleNamespace(reflection=None),
        )
        return BrainEngine(
            orchestrator=orchestrator,
            memory_manager=self.manager,
        )

    # ------------------------------------------------------------------

    def test_default_brain_memory_is_unified(self):
        from desktop_agent.brain.brain_engine import BrainEngine
        orchestrator = SimpleNamespace(
            execution_coordinator=SimpleNamespace(reflection=None),
        )
        brain = BrainEngine(orchestrator=orchestrator)
        self.assertIsInstance(brain.memory, UnifiedMemoryManager)
        self.assertIs(brain.memory_2_0, brain.memory)

    def test_injected_memory_is_shared_instance(self):
        brain = self._brain()
        self.assertIs(brain.memory, self.manager)
        self.assertIs(brain.memory_2_0, self.manager)

    # ------------------------------------------------------------------

    def test_working_view_lifecycle(self):
        brain = self._brain()
        brain.memory.working.add(value="step A", category="step", importance=0.7)
        brain.memory.working.add(value="plan X", category="execution_plan",
                                 importance=0.8)

        snap = brain.memory.working.snapshot()
        self.assertEqual(len(snap), 2)
        self.assertEqual(snap[-1].value, "plan X")
        self.assertEqual(snap[-1].category, "execution_plan")

        self.assertEqual(len(brain.memory.working.recent(limit=1)), 1)
        latest = brain.memory.working.latest(category="step")
        self.assertEqual(latest.value, "step A")
        self.assertEqual(len(brain.memory.working.search("execution_plan")), 1)

        brain.memory.working.clear()
        self.assertEqual(len(brain.memory.working.snapshot()), 0)

    def test_episodic_view_lifecycle(self):
        brain = self._brain()
        brain.memory.episodic.record(title="Step done", category="completed_step",
                                     description="did x", importance=0.7,
                                     metadata={"source": "orchestrator"})

        recent = brain.memory.episodic.recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].title, "Step done")
        self.assertEqual(recent[0].category, "completed_step")

        self.assertEqual(len(brain.memory.episodic.by_category("completed_step")), 1)
        self.assertEqual(len(brain.memory.episodic.important(threshold=0.6)), 1)
        self.assertEqual(len(brain.memory.episodic.search("did x")), 1)
        self.assertEqual(brain.memory.episodic.latest().title, "Step done")

    def test_semantic_view_lifecycle(self):
        brain = self._brain()
        brain.memory.semantic.store("user_role", "developer", source="brain")

        self.assertEqual(brain.memory.semantic.get("user_role"), "developer")
        self.assertTrue(brain.memory.semantic.exists("user_role"))
        self.assertEqual(len(brain.memory.semantic.search("role")), 1)

        snap = brain.memory.semantic.snapshot()
        self.assertIn("user_role", snap)
        self.assertEqual(snap["user_role"].value, "developer")

    def test_context_shape(self):
        brain = self._brain()
        brain.memory.working.add(value="w1", category="event")
        brain.memory.episodic.record(title="e1", category="general")
        brain.memory.semantic.store("k1", "v1")

        ctx = brain.memory.context()
        self.assertEqual(set(ctx.keys()), {"working", "episodic", "semantic"})
        self.assertEqual(len(ctx["working"]), 1)
        self.assertEqual(len(ctx["episodic"]), 1)
        self.assertEqual(list(ctx["semantic"].keys()), ["k1"])

    def test_compat_entry_points(self):
        brain = self._brain()
        self.assertTrue(brain.memory.remember_fact("theme", "dark"))
        self.assertTrue(brain.memory.remember_event(SimpleNamespace(
            title="event", message="msg", source="obs", severity="info",
            payload={})))
        self.assertTrue(brain.memory.remember_reflection("reflection text"))
        self.assertTrue(brain.memory.learn("obs", ["e"], {"p": 1}))
        self.assertGreaterEqual(
            brain.memory.recall_by_type(MemoryType.SEMANTIC).__len__(), 1)
        self.assertGreaterEqual(
            brain.memory.recall_by_type(MemoryType.WORKING).__len__(), 1)
        self.assertGreaterEqual(
            brain.memory.recall_by_type(MemoryType.EPISODIC).__len__(), 2)

    def test_retrieve_alias(self):
        brain = self._brain()
        brain.memory.semantic.store("project_stack", "react")
        hits = brain.memory.retrieve("react")
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(any("react" in h.content for h in hits))

    def test_process_event_writes_unified_working(self):
        brain = self._brain()
        event = SimpleNamespace(
            title="App opened", message="Chrome launched", source="observer",
            severity="info", payload={"app": "chrome"},
        )
        brain.process_event(event)

        working = brain.memory.recall_by_type(MemoryType.WORKING)
        self.assertEqual(len(working), 1)
        self.assertEqual(working[0].content, "Chrome launched")
        self.assertEqual(working[0].status, MemoryStatus.ACTIVE)

    def test_context_fusion_engine_gathers_from_unified(self):
        self.manager.working.add(value="recent working item", category="event")
        self.manager.semantic.store("user_name", "Aarav")

        fusion = ContextFusionEngine(
            memory_manager=self.manager,
            world_model=None,
            memory_retrieval=None,
        )
        fused = fusion.fuse(request="continue", goal=None)
        self.assertIsNotNone(fused.memory)
        self.assertIn("working_recent", fused.memory)
        self.assertIn("episodic_recent", fused.memory)
        self.assertIn("semantic_keys", fused.memory)
        self.assertEqual(fused.memory["semantic_keys"], ["user_name"])

    def test_persistence_migration_utility_exists(self):
        self.assertTrue(hasattr(persistence, "migrate_memory_file_legacy_to_unified"))
        self.assertTrue(hasattr(persistence, "_migrate_legacy_to_unified"))


if __name__ == "__main__":
    unittest.main()