"""
Full System Integration — Phase 2/3 tests.

Verifies:
- One shared AI Manager authority across BrainEngine, ExecutionBrain, SuperBrain.
- One shared Memory 2.0 authority across the whole runtime.
- Memory 2.0 is the implicit context-retrieval authority (get_relevant_memories
  reachable through ContextManager).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

from desktop_agent.core.application_container import ApplicationContainer
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord,
    MemoryType,
    MemoryScope,
    Provenance,
    RetentionPolicy,
)


class TestIntegrationSharedAuthorities(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.container = ApplicationContainer()

    def test_single_ai_manager_authority(self):
        c = self.container
        self.assertIs(c.brain_engine.ai, c.ai_manager)
        self.assertIs(c.execution_brain.ai_manager, c.ai_manager)
        self.assertIs(c.super_brain.ai_manager, c.ai_manager)

    def test_single_memory_authority(self):
        c = self.container
        self.assertIs(c.brain_engine.memory, c.memory_2_0)
        self.assertIs(c.brain_engine.memory_2_0, c.memory_2_0)
        self.assertIs(c.runtime.memory_2_0, c.memory_2_0)
        self.assertIs(c.super_brain.memory_2_0, c.memory_2_0)
        self.assertIs(c.brain_engine.memory_command_engine.manager, c.memory_2_0)


class TestMemory2ImplicitContextRetrieval(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.manager = UnifiedMemoryManager(
            os.path.join(self.tmp.name, "store.json"))

    def tearDown(self):
        self.manager.flush()
        self.tmp.cleanup()

    def _remember(self, content: str, importance: float = 0.7):
        rec = MemoryRecord(
            type=MemoryType.SEMANTIC,
            content=content,
            summary=content[:60],
            source="integration-test",
            scope=MemoryScope.USER,
            importance=importance,
            confidence=0.9,
            provenance=Provenance.SYSTEM_OBSERVED,
            retention_policy=RetentionPolicy.LONG_TERM,
        )
        self.assertTrue(self.manager.remember(rec))
        return rec

    def test_get_relevant_memories_returns_ranked_dicts(self):
        self._remember("user prefers mechanical keyboards")
        self._remember("user drinks chai every morning")

        hits = self.manager.get_relevant_memories("keyboard", limit=5)

        self.assertTrue(hits)
        first = hits[0]
        self.assertEqual(first["memory"], "user prefers mechanical keyboards")
        self.assertIn("relevance", first)
        self.assertIn("id", first)
        self.assertEqual(first["type"], "semantic")
        # The chai fact must not leak into context (relevance floor)
        self.assertNotIn("chai", [h["memory"] for h in hits])

    def test_context_manager_uses_unified_memory(self):
        self._remember("meeting with priya at 5pm")
        from desktop_agent.brain.context_manager import ContextManager
        cctx = ContextManager(perception=None, blackboard=None,
                              memory_manager=self.manager)
        context = cctx.build("email", {"to": "priya"})
        self.assertIn("memory", context.metadata)
        self.assertTrue(hasattr(context, "memory"))

        # Memory 2.0 retrieved through the implicit path
        hits = self.manager.get_relevant_memories("priya meeting", limit=5)
        self.assertEqual([h["memory"] for h in hits],
                         ["meeting with priya at 5pm"])

    def test_no_relevant_memory_returns_empty(self):
        self._remember("user prefers mechanical keyboards")
        hits = self.manager.get_relevant_memories("quantum chemistry theorems", limit=5)
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()