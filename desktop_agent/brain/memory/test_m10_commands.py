"""
MYRAA Memory 2.0 — M10: Explicit Memory Command System tests.

Covers English + Hinglish parsing, execution against UnifiedMemoryManager,
ambiguity handling, sensitivity rejection, scope clearing, and request-flow
integration through MemoryCommandEngine.handle().
"""

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from desktop_agent.brain.memory.memory_commands import (
    MemoryCommandEngine,
    MemoryCommandParser,
    MemoryCommandResult,
)
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


def make_ctx(project_id="p1", task_id=None, conversation_id="c1"):
    return SimpleNamespace(
        project_id=project_id,
        task_id=task_id,
        conversation_id=conversation_id,
    )


def make_record(content, mtype=MemoryType.SEMANTIC, scope=MemoryScope.USER,
                project_id=None, task_id=None, conversation_id=None):
    return MemoryRecord(
        type=mtype,
        content=content,
        summary=content[:120],
        source="test",
        scope=scope,
        project_id=project_id,
        task_id=task_id,
        conversation_id=conversation_id,
        provenance=Provenance.USER_EXPLICIT,
        retention_policy=RetentionPolicy.USER_DEFINED,
        importance=0.8,
        confidence=0.9,
    )


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = MemoryCommandParser()

    def test_remember_english(self):
        cmd = self.parser.parse("remember that I prefer Hinglish")
        self.assertTrue(cmd.is_command)
        self.assertEqual(cmd.operation, "REMEMBER")
        self.assertEqual(cmd.content, "I prefer Hinglish")
        self.assertEqual(cmd.memory_type, "PREFERENCE")

    def test_remember_english_preference_direct(self):
        cmd = self.parser.parse("remember my favourite color is blue")
        self.assertEqual(cmd.operation, "REMEMBER")
        self.assertEqual(cmd.content, "my favourite color is blue")
        self.assertEqual(cmd.memory_type, "SEMANTIC")

    def test_remember_hinglish(self):
        cmd = self.parser.parse("yaad rakh ki server us-east hai")
        self.assertEqual(cmd.operation, "REMEMBER")
        self.assertEqual(cmd.content, "server us-east hai")

    def test_remember_hinglish_variant(self):
        cmd = self.parser.parse("dhyaan rakh NIFTY 24000 par hai")
        self.assertEqual(cmd.operation, "REMEMBER")
        self.assertEqual(cmd.content, "NIFTY 24000 par hai")

    def test_remember_note(self):
        cmd = self.parser.parse("note that the build command is npm run build")
        self.assertEqual(cmd.operation, "REMEMBER")
        self.assertEqual(cmd.content, "the build command is npm run build")

    def test_remember_naked_requires_clarification(self):
        cmd = self.parser.parse("remember this")
        self.assertTrue(cmd.is_command)
        self.assertEqual(cmd.operation, "REMEMBER")
        self.assertTrue(cmd.needs_clarification)
        self.assertEqual(cmd.reason, "no_content")

    def test_recall_english(self):
        cmd = self.parser.parse("what do you remember about NIFTY?")
        self.assertEqual(cmd.operation, "RECALL")
        self.assertEqual(cmd.subject, "NIFTY")

    def test_recall_hinglish(self):
        cmd = self.parser.parse("NIFTY ke baare mein kya yaad hai?")
        self.assertEqual(cmd.operation, "RECALL")
        self.assertEqual(cmd.subject, "NIFTY")

    def test_recall_hinglish_variant(self):
        cmd = self.parser.parse("kya yaad hai TCS ke baare mein")
        self.assertEqual(cmd.operation, "RECALL")
        self.assertEqual(cmd.subject, "TCS")

    def test_recall_no_subject(self):
        cmd = self.parser.parse("what do you remember?")
        self.assertEqual(cmd.operation, "RECALL")
        self.assertEqual(cmd.subject, "")

    def test_update_english(self):
        cmd = self.parser.parse("update the memory about favourite color to green")
        self.assertEqual(cmd.operation, "UPDATE")
        self.assertEqual(cmd.subject, "favourite color")
        self.assertEqual(cmd.content, "green")

    def test_update_change(self):
        cmd = self.parser.parse("change what you remember about coffee to tea")
        self.assertEqual(cmd.operation, "UPDATE")
        self.assertEqual(cmd.subject, "coffee")
        self.assertEqual(cmd.content, "tea")

    def test_update_that(self):
        cmd = self.parser.parse("update that I like cold coffee")
        self.assertEqual(cmd.operation, "UPDATE")
        self.assertEqual(cmd.content, "I like cold coffee")

    def test_forget_english(self):
        cmd = self.parser.parse("forget my nickname")
        self.assertEqual(cmd.operation, "FORGET")
        self.assertEqual(cmd.subject, "my nickname")

    def test_forget_hinglish(self):
        cmd = self.parser.parse("bhool jao TCS ke baare mein")
        self.assertEqual(cmd.operation, "FORGET")
        self.assertEqual(cmd.subject, "TCS ke baare mein")

    def test_forget_naked_requires_clarification(self):
        cmd = self.parser.parse("forget")
        self.assertTrue(cmd.is_command)
        self.assertEqual(cmd.operation, "FORGET")
        self.assertTrue(cmd.needs_clarification)
        self.assertEqual(cmd.reason, "no_subject")

    def test_list_with_subject(self):
        cmd = self.parser.parse("show my memories about NIFTY")
        self.assertEqual(cmd.operation, "LIST")
        self.assertEqual(cmd.subject, "NIFTY")

    def test_list_all(self):
        cmd = self.parser.parse("show all memories")
        self.assertEqual(cmd.operation, "LIST")
        self.assertEqual(cmd.subject, "")

    def test_list_hinglish(self):
        cmd = self.parser.parse("memories dikhao NIFTY")
        self.assertEqual(cmd.operation, "LIST")
        self.assertEqual(cmd.subject, "NIFTY")

    def test_clear_project(self):
        cmd = self.parser.parse("forget this project's memories", make_ctx())
        self.assertEqual(cmd.operation, "CLEAR_SCOPE")
        self.assertEqual(cmd.scope, "PROJECT")
        self.assertEqual(cmd.project_id, "p1")

    def test_clear_project_missing_context(self):
        cmd = self.parser.parse("forget this project's memories", SimpleNamespace())
        self.assertTrue(cmd.is_command)
        self.assertEqual(cmd.operation, "CLEAR_SCOPE")
        self.assertTrue(cmd.needs_clarification)

    def test_clear_task(self):
        cmd = self.parser.parse("clear task memory", make_ctx(task_id="t1"))
        self.assertEqual(cmd.operation, "CLEAR_SCOPE")
        self.assertEqual(cmd.scope, "TASK")
        self.assertEqual(cmd.task_id, "t1")

    def test_non_command_unchanged(self):
        cmd = self.parser.parse("hello Myraa how are you?")
        self.assertFalse(cmd.is_command)
        self.assertEqual(cmd.operation, "NONE")

    def test_no_false_positive_remember(self):
        cmd = self.parser.parse("I remember you from yesterday")
        self.assertFalse(cmd.is_command)

    def test_no_false_positive_forget(self):
        cmd = self.parser.parse("don't forget me!")
        self.assertFalse(cmd.is_command)


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.manager = make_manager()
        self.engine = MemoryCommandEngine(self.manager)
        self.ctx = make_ctx()

    def _store(self, *records):
        for r in records:
            self.assertTrue(self.manager.remember(r), f"store failed: {r.content}")

    # ---- REMEMBER -----------------------------------------------------

    def test_remember_stores_preference(self):
        result = self.engine.handle("remember that I prefer Hinglish")
        self.assertIsInstance(result, MemoryCommandResult)
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "REMEMBER")
        active = self.manager.get_all_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].type, MemoryType.PREFERENCE)
        self.assertEqual(active[0].provenance, Provenance.USER_EXPLICIT)
        self.assertEqual(active[0].retention_policy, RetentionPolicy.USER_DEFINED)
        self.assertEqual(active[0].content, "I prefer Hinglish")

    def test_remember_hinglish(self):
        result = self.engine.handle("yaad rakh ki server us-east hai")
        self.assertTrue(result.success)
        active = self.manager.get_all_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].content, "server us-east hai")
        self.assertEqual(active[0].type, MemoryType.SEMANTIC)

    def test_remember_contextual_scope(self):
        result = self.engine.handle(
            "remember that this project uses FastAPI", make_ctx(project_id="p1"))
        self.assertTrue(result.success)
        active = self.manager.get_all_active()
        self.assertEqual(active[0].scope, MemoryScope.PROJECT)
        self.assertEqual(active[0].project_id, "p1")

    def test_remember_naked_asks_clarification(self):
        result = self.engine.handle("remember this")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.operation, "REMEMBER")
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_remember_sensitive_rejected(self):
        result = self.engine.handle("remember that my password is hunter2")
        self.assertFalse(result.success)
        self.assertIn("secret", result.message.lower())
        self.assertEqual(self.manager.get_active_count(), 0)

    # ---- RECALL -------------------------------------------------------

    def test_recall_returns_matching(self):
        self._store(make_record("NIFTY is trading around 24000"))
        result = self.engine.handle("what do you remember about NIFTY?")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "RECALL")
        self.assertTrue(result.records)
        self.assertEqual(result.records[0].content, "NIFTY is trading around 24000")

    def test_recall_hinglish(self):
        self._store(make_record("TCS share price around 3800"))
        result = self.engine.handle("TCS ke baare mein kya yaad hai?")
        self.assertTrue(result.success)
        self.assertTrue(any("TCS" in r.content for r in result.records))

    def test_recall_nonexistent(self):
        result = self.engine.handle("what do you remember about Quantum Physics?")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "RECALL")
        self.assertFalse(result.records)
        self.assertIn("don't remember anything", result.message)

    # ---- UPDATE -------------------------------------------------------

    def test_update_changes_existing(self):
        self._store(make_record("my favourite color is blue"))
        result = self.engine.handle("update the memory about favourite color to green")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "UPDATE")
        active = self.manager.get_all_active()
        self.assertEqual(len(active), 1)
        self.assertIn("green", active[0].content)

    def test_update_increments_version(self):
        self._store(make_record("my favourite color is blue"))
        before = self.manager.get_all_active()[0].version
        self.engine.handle("update the memory about favourite color to green")
        after = self.manager.get_all_active()[0].version
        self.assertEqual(after, before + 1)

    def test_update_without_existing_stores_new(self):
        result = self.engine.handle("update the memory about coffee to tea")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "UPDATE")
        self.assertEqual(self.manager.get_active_count(), 1)
        self.assertEqual(self.manager.get_all_active()[0].content, "tea")

    # ---- FORGET -------------------------------------------------------

    def test_forget_marks_deleted(self):
        rec = make_record("my nickname is Sparrow")
        self._store(rec)
        result = self.engine.handle("forget my nickname")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "FORGET")
        self.assertEqual(self.manager.get_active_count(), 0)
        stored = self.manager.recall(rec.id)
        self.assertIsNone(stored)  # DELETED is not returned by recall

    def test_forget_hinglish(self):
        rec = make_record("meeting at 3pm today")
        self._store(rec)
        result = self.engine.handle("bhool jao meeting ke baare mein")
        self.assertTrue(result.success)
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_forget_nonexistent_is_noop(self):
        result = self.engine.handle("forget the secret recipe")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "FORGET")
        self.assertEqual(self.manager.get_active_count(), 0)
        self.assertIn("nothing", result.message.lower())

    def test_forget_naked_asks_clarification(self):
        self._store(make_record("anything at all"))
        result = self.engine.handle("forget")
        self.assertTrue(result.needs_clarification)
        self.assertEqual(self.manager.get_active_count(), 1)  # nothing deleted

    # ---- LIST ---------------------------------------------------------

    def test_list_with_subject(self):
        self._store(make_record("NIFTY around 24000"))
        self._store(make_record("TCS around 3800"))
        result = self.engine.handle("show my memories about NIFTY")
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "LIST")
        self.assertTrue(any("NIFTY" in r.content for r in result.records))

    def test_list_all(self):
        self._store(make_record("fact one"))
        self._store(make_record("fact two"))
        result = self.engine.handle("show all memories")
        self.assertTrue(result.success)
        self.assertEqual(len(result.records), 2)

    # ---- CLEAR_SCOPE --------------------------------------------------

    def test_clear_project_scope(self):
        self._store(make_record("project alpha note", scope=MemoryScope.PROJECT,
                                project_id="p1"))
        self._store(make_record("user level fact", scope=MemoryScope.USER))
        result = self.engine.handle("forget this project's memories", make_ctx(project_id="p1"))
        self.assertTrue(result.success)
        self.assertEqual(result.operation, "CLEAR_SCOPE")
        # Project memories gone, user memory intact
        remaining = self.manager.get_all_active()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].content, "user level fact")

    def test_clear_task_scope(self):
        self._store(make_record("task-specific plan", scope=MemoryScope.TASK, task_id="t1"))
        self._store(make_record("global fact", scope=MemoryScope.GLOBAL))
        result = self.engine.handle("clear task memory", make_ctx(task_id="t1"))
        self.assertTrue(result.success)
        remaining = self.manager.get_all_active()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].content, "global fact")

    # ---- handle() integration ------------------------------------------

    def test_handle_returns_none_for_non_command(self):
        result = self.engine.handle("hello Myraa, how is the weather?")
        self.assertIsNone(result)

    def test_handle_pipeline_end_to_end(self):
        self.engine.handle("remember that I prefer dark mode")
        self.engine.handle("remember that my screen timeout is 5 minutes")
        rec = self.engine.handle("what do you remember about dark mode?")
        self.assertTrue(rec.success)
        self.assertTrue(any("dark mode" in r.content for r in rec.records))

    def test_engine_rejects_wrong_manager_type(self):
        with self.assertRaises(TypeError):
            MemoryCommandEngine(object())


class TestBrainEngineIntegration(unittest.TestCase):
    """M10: commands integrate into BrainEngine.process() request flow."""

    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.temp_path = path
        self.manager = UnifiedMemoryManager(path)
        self.manager.clear()
        self.brain = self._brain()

    def tearDown(self):
        if os.path.exists(self.temp_path):
            os.unlink(self.temp_path)

    def _brain(self):
        from desktop_agent.brain.brain_engine import BrainEngine
        orchestrator = SimpleNamespace(
            execution_coordinator=SimpleNamespace(reflection=None),
        )
        return BrainEngine(orchestrator=orchestrator, memory_manager=self.manager)

    def test_command_engine_shares_store(self):
        self.assertIs(self.brain.memory_command_engine.manager, self.manager)
        self.assertIs(self.brain.memory_2_0, self.manager)

    def test_process_remember_short_circuits(self):
        result = self.brain.process("remember that I prefer Hinglish")
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["route"], "MEMORY_COMMAND")
        self.assertEqual(result.metadata["command_operation"], "REMEMBER")
        active = self.manager.get_all_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].content, "I prefer Hinglish")

    def test_process_recall(self):
        self.brain.process("remember that the server region is us-east")
        result = self.brain.process("what do you remember about server region?")
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["route"], "MEMORY_COMMAND")
        self.assertIn("us-east", result.message)

    def test_process_forget(self):
        self.brain.process("remember that my nickname is Sparrow")
        self.assertEqual(self.manager.get_active_count(), 1)
        result = self.brain.process("forget my nickname")
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_operation"], "FORGET")
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_process_clarification_surfaces_question(self):
        result = self.brain.process("forget")
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_operation"], "FORGET")
        self.assertIn("?", result.message)


if __name__ == "__main__":
    unittest.main()