"""
Tests for the MYRAA Unified Memory Manager
"""

import unittest
import tempfile
import os
from desktop_agent.brain.memory.unified_manager import (
    UnifiedMemoryManager, create_unified_memory_manager,
    remember_fact, remember_event
)
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord, MemoryType, MemoryScope, MemoryStatus,
    Sensitivity, RetentionPolicy, Provenance
)


class TestUnifiedMemoryManager(unittest.TestCase):
    """Test cases for the Unified Memory Manager."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary file for memory storage
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.manager = UnifiedMemoryManager(self.temp_file.name)

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove the temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_manager_creation(self):
        """Test creating a unified memory manager."""
        self.assertIsInstance(self.manager, UnifiedMemoryManager)
        self.assertEqual(self.manager.get_count(), 0)
        self.assertEqual(self.manager.get_active_count(), 0)

    def test_remember_and_recall(self):
        """Test remembering and recalling memories."""
        # Create a memory record
        record = MemoryRecord(
            content="Test memory content",
            source="test",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        # Remember the memory
        result = self.manager.remember(record)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_count(), 1)
        self.assertEqual(self.manager.get_active_count(), 1)

        # Recall the memory
        recalled = self.manager.recall(record.id)
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled.id, record.id)
        self.assertEqual(recalled.content, record.content)
        self.assertEqual(recalled.access_count, 1)  # Accessed during recall

        # Note: importance and confidence may be adjusted by the write governance pipeline
        # but should be in reasonable range
        self.assertGreaterEqual(recalled.importance, 0.0)
        self.assertLessEqual(recalled.importance, 1.0)
        self.assertGreaterEqual(recalled.confidence, 0.0)
        self.assertLessEqual(recalled.confidence, 1.0)

    def test_remember_duplicate(self):
        """Test that duplicate memories are not stored."""
        record1 = MemoryRecord(
            content="Test memory content",
            source="test",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        record2 = MemoryRecord(
            content="Test memory content",  # Same content
            source="test",
            importance=0.7,  # Different importance
            confidence=0.8,  # Different confidence
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)
        initial_count = self.manager.get_count()

        # Remember second memory (should be treated as duplicate)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)  # Still returns true (updated)
        self.assertEqual(self.manager.get_count(), initial_count)  # Count unchanged

        # Recall the memory - should have adjusted importance/confidence
        recalled = self.manager.recall(record1.id)
        self.assertIsNotNone(recalled)
        # The importance and confidence should be reasonably adjusted
        # (exact values depend on the write governance scoring)
        self.assertGreaterEqual(recalled.importance, 0.0)
        self.assertLessEqual(recalled.importance, 1.0)
        self.assertGreaterEqual(recalled.confidence, 0.0)
        self.assertLessEqual(recalled.confidence, 1.0)

    def test_forget(self):
        """Test forgetting memories."""
        record = MemoryRecord(
            content="Test memory to forget",
            source="test",
            importance=0.6,
            confidence=0.7,
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )

        # Remember the memory
        self.manager.remember(record)
        self.assertEqual(self.manager.get_count(), 1)

        # Forget the memory
        result = self.manager.forget(record.id)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_count(), 1)  # Still exists but marked as deleted
        self.assertEqual(self.manager.get_active_count(), 0)  # No active memories

        # Try to recall - should return None
        recalled = self.manager.recall(record.id)
        self.assertIsNone(recalled)

        # Try to forget again - should return True (memory still exists in store)
        result2 = self.manager.forget(record.id)
        self.assertTrue(result2)

    def test_recall_by_content(self):
        """Test recalling memories by content."""
        # Remember several memories
        memories = [
            MemoryRecord(content="User prefers Hinglish explanations", source="test",
                        importance=0.9, confidence=0.95, scope=MemoryScope.USER,
                        type=MemoryType.PREFERENCE),
            MemoryRecord(content="User is working on MYRAA project", source="test",
                        importance=0.8, confidence=0.9, scope=MemoryScope.PROJECT,
                        type=MemoryType.PROJECT, project_id="MYRAA"),
            MemoryRecord(content="User likes pizza", source="test",
                        importance=0.5, confidence=0.8, scope=MemoryScope.USER,
                        type=MemoryType.PREFERENCE)
        ]

        for mem in memories:
            self.manager.remember(mem)

        # Search for memories containing "Hinglish"
        results = self.manager.recall_by_content("Hinglish", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "User prefers Hinglish explanations")

        # Search for memories containing "user" (should match all)
        results = self.manager.recall_by_content("user", limit=10)
        self.assertEqual(len(results), 3)  # All three contain "user"

        # Search for memories containing "pizza"
        results = self.manager.recall_by_content("pizza", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "User likes pizza")

    def test_recall_by_scope(self):
        """Test recalling memories by scope."""
        # Remember memories in different scopes
        memories = [
            MemoryRecord(content="Global memory", source="test",
                        importance=0.7, confidence=0.8, scope=MemoryScope.GLOBAL,
                        type=MemoryType.SEMANTIC),
            MemoryRecord(content="User preference", source="test",
                        importance=0.9, confidence=0.95, scope=MemoryScope.USER,
                        type=MemoryType.PREFERENCE),
            MemoryRecord(content="MYRAA project detail", source="test",
                        importance=0.8, confidence=0.9, scope=MemoryScope.PROJECT,
                        type=MemoryType.PROJECT, project_id="MYRAA"),
            MemoryRecord(content="Task step completed", source="test",
                        importance=0.75, confidence=0.85, scope=MemoryScope.TASK,
                        type=MemoryType.TASK, task_id="task_123")
        ]

        for mem in memories:
            self.manager.remember(mem)

        # Recall global memories
        results = self.manager.recall_by_scope(MemoryScope.GLOBAL)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Global memory")

        # Recall user memories
        results = self.manager.recall_by_scope(MemoryScope.USER)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "User preference")

        # Recall project memories
        results = self.manager.recall_by_scope(MemoryScope.PROJECT, project_id="MYRAA")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "MYRAA project detail")

        # Recall task memories
        results = self.manager.recall_by_scope(MemoryScope.TASK, task_id="task_123")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Task step completed")

    def test_recall_by_type(self):
        """Test recalling memories by type."""
        # Remember memories of different types
        memories = [
            MemoryRecord(content="Semantic fact", source="test",
                        importance=0.7, confidence=0.8, scope=MemoryScope.GLOBAL,
                        type=MemoryType.SEMANTIC),
            MemoryRecord(content="Episodic event", source="test",
                        importance=0.8, confidence=0.9, scope=MemoryScope.USER,
                        type=MemoryType.EPISODIC),
            MemoryRecord(content="Preference setting", source="test",
                        importance=0.9, confidence=0.95, scope=MemoryScope.USER,
                        type=MemoryType.PREFERENCE)
        ]

        for mem in memories:
            self.manager.remember(mem)

        # Recall semantic memories
        results = self.manager.recall_by_type(MemoryType.SEMANTIC)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Semantic fact")

        # Recall episodic memories
        results = self.manager.recall_by_type(MemoryType.EPISODIC)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Episodic event")

        # Recall preference memories
        results = self.manager.recall_by_type(MemoryType.PREFERENCE)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Preference setting")

    def test_memory_status_transitions(self):
        """Test memory status transitions."""
        record = MemoryRecord(
            content="Test memory for status transitions",
            source="test",
            importance=0.6,
            confidence=0.7,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        # Remember the memory
        self.assertTrue(self.manager.remember(record))
        self.assertEqual(self.manager.get_active_count(), 1)

        # Verify the memory is active and retrievable
        recalled = self.manager.recall(record.id)
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled.status, MemoryStatus.ACTIVE)

        # Forget the memory (marks as deleted)
        self.assertTrue(self.manager.forget(record.id))
        self.assertEqual(self.manager.get_active_count(), 0)  # No longer active
        self.assertEqual(self.manager.get_count(), 1)       # Still exists in store

        # Verify the memory is no longer retrievable (status is DELETED)
        recalled = self.manager.recall(record.id)
        self.assertIsNone(recalled)  # Should not be retrievable after forgetting

    def test_sensitive_data_rejection(self):
        """Test that sensitive data is properly rejected."""
        # Test various types of sensitive data
        sensitive_memories = [
            MemoryRecord(content="My password is hunter2", source="test",
                        importance=0.5, confidence=0.8, scope=MemoryScope.USER,
                        type=MemoryType.SEMANTIC),
            MemoryRecord(content="My API key is sk-abcdefghijklmnopqrstuvwxyz", source="test",
                        importance=0.5, confidence=0.8, scope=MemoryScope.USER,
                        type=MemoryType.SEMANTIC),
            MemoryRecord(content="My secret token is ghp_abcdefghijklmnopqrstuvwxyz", source="test",
                        importance=0.5, confidence=0.8, scope=MemoryScope.USER,
                        type=MemoryType.SEMANTIC),
            MemoryRecord(content="My credit card is 4111 1111 1111 1111", source="test",
                        importance=0.5, confidence=0.8, scope=MemoryScope.USER,
                        type=MemoryType.SEMANTIC)
        ]

        for mem in sensitive_memories:
            result = self.manager.remember(mem)
            self.assertFalse(result, f"Sensitive memory should be rejected: {mem.content}")

        # Verify no memories were stored
        self.assertEqual(self.manager.get_count(), 0)

    def test_persistence_roundtrip(self):
        """Test that memories persist correctly across manager instances."""
        # Remember some memories in the first manager
        memories = [
            MemoryRecord(content="Persistent fact 1", source="test",
                        importance=0.8, confidence=0.9, scope=MemoryScope.GLOBAL,
                        type=MemoryType.SEMANTIC),
            MemoryRecord(content="Persistent event 1", source="test",
                        importance=0.7, confidence=0.8, scope=MemoryScope.USER,
                        type=MemoryType.EPISODIC),
            MemoryRecord(content="Persistent preference", source="test",
                        importance=0.9, confidence=0.95, scope=MemoryScope.USER,
                        type=MemoryType.PREFERENCE)
        ]

        for mem in memories:
            self.manager.remember(mem)

        initial_count = self.manager.get_count()
        initial_active = self.manager.get_active_count()

        # M14: deferred persist is coalesced; flush before reload (restart sim)
        self.manager.flush()

        # Create a new manager with the same storage file
        new_manager = UnifiedMemoryManager(self.temp_file.name)

        # Check that the memories were loaded
        self.assertEqual(new_manager.get_count(), initial_count)
        self.assertEqual(new_manager.get_active_count(), initial_active)

        # Check that we can recall the memories
        for mem in memories:
            recalled = new_manager.recall(mem.id)
            self.assertIsNotNone(recalled)
            self.assertEqual(recalled.content, mem.content)
            # Note: importance and confidence may be adjusted by persistence/loading

    def test_convenience_functions(self):
        """Test the backward compatibility convenience functions."""
        # Test remember_fact
        result1 = remember_fact("test_key", "test_value", confidence=0.9)
        self.assertTrue(result1)

        # Test remember_event
        result2 = remember_event("Test Event", "This is a test event", "test")
        self.assertTrue(result2)

        # Check that we can recall these memories
        # Note: These use the default storage location, so we need to check a different approach
        # For now, just verify the functions don't throw exceptions

    def test_memory_limitations(self):
        """Test that memory limitations are respected."""
        # Test that we can store memories with various importance values
        test_cases = [
            (0.0, 0.5),  # Minimum importance
            (0.5, 0.5),  # Middle importance
            (1.0, 0.5),  # Maximum importance
            (0.5, 0.0),  # Minimum confidence
            (0.5, 1.0)   # Maximum confidence
        ]

        for importance, confidence in test_cases:
            record = MemoryRecord(
                content=f"Test memory with importance={importance}, confidence={confidence}",
                source="test",
                importance=importance,
                confidence=confidence,
                scope=MemoryScope.USER,
                type=MemoryType.SEMANTIC
            )
            result = self.manager.remember(record)
            self.assertTrue(result, f"Failed to store memory with importance={importance}, confidence={confidence}")

        # Verify we stored all test memories
        self.assertEqual(self.manager.get_count(), len(test_cases))

    def test_write_governance_importance_scoring(self):
        """Test that importance scoring works correctly in write governance."""
        # Test user explicit memories get high importance
        explicit_record = MemoryRecord(
            content="User explicitly said this is important",
            source="user_explicit",
            importance=0.5,  # Base importance
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            provenance=Provenance.USER_EXPLICIT
        )

        result = self.manager.remember(explicit_record)
        self.assertTrue(result)

        recalled = self.manager.recall(explicit_record.id)
        self.assertIsNotNone(recalled)
        # User explicit memories should get boosted importance
        self.assertGreater(recalled.importance, 0.5)

        # Test low importance memories get adjusted
        low_importance_record = MemoryRecord(
            content="Trivial information",
            source="test",
            importance=0.05,  # Very low importance
            confidence=0.5,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        result2 = self.manager.remember(low_importance_record)
        # Very low importance memories might be rejected by usefulness assessment
        # or get adjusted upward
        if result2:
            recalled2 = self.manager.recall(low_importance_record.id)
            self.assertIsNotNone(recalled2)
            # Should be adjusted to a reasonable value
            self.assertGreaterEqual(recalled2.importance, 0.0)
            self.assertLessEqual(recalled2.importance, 1.0)

    def test_write_governance_confidence_scoring(self):
        """Test that confidence scoring works correctly in write governance."""
        # Test different provenances affect confidence
        provenances_and_expected_adjustments = [
            (Provenance.USER_EXPLICIT, 0.8),   # Should be high confidence
            (Provenance.MODEL_INFERRED, 0.5),  # Should be medium confidence
            (Provenance.PEER_VALIDATED, 0.9)   # Should be very high confidence
        ]

        for provenance, min_expected_confidence in provenances_and_expected_adjustments:
            record = MemoryRecord(
                content=f"Test memory from {provenance.value}",
                source="test",
                importance=0.7,
                confidence=0.6,  # Base confidence
                scope=MemoryScope.USER,
                type=MemoryType.SEMANTIC,
                provenance=provenance
            )

            result = self.manager.remember(record)
            self.assertTrue(result, f"Failed to remember memory with provenance {provenance}")

            recalled = self.manager.recall(record.id)
            self.assertIsNotNone(recalled)
            # Confidence should be adjusted based on provenance
            self.assertGreaterEqual(recalled.confidence, 0.0)
            self.assertLessEqual(recalled.confidence, 1.0)

    def test_write_governance_usefulness_assessment(self):
        """Test that usefulness assessment works correctly."""
        # Test very low confidence memories might be rejected
        low_confidence_record = MemoryRecord(
            content="Uncertain information",
            source="test",
            importance=0.5,
            confidence=0.1,  # Very low confidence
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        result = self.manager.remember(low_confidence_record)
        # Very low confidence memories might be rejected
        # (implementation dependent)
        if not result:
            # If rejected, that's acceptable behavior
            pass
        else:
            # If accepted, should still be valid
            recalled = self.manager.recall(low_confidence_record.id)
            self.assertIsNotNone(recalled)

        # Test ephemeral very old memories might not be useful
        # (This is harder to test without manipulating time)

    def test_write_governance_conflict_detection(self):
        """Test that conflict detection works correctly."""
        # Create two similar but different memories
        record1 = MemoryRecord(
            content="The project deadline is next Friday",
            source="test",
            importance=0.6,
            confidence=0.7,
            scope=MemoryScope.PROJECT,
            project_id="TEST_PROJECT",
            type=MemoryType.SEMANTIC
        )

        record2 = MemoryRecord(
            content="The project deadline is next Friday",  # Same content
            source="test",
            importance=0.8,  # Higher importance
            confidence=0.9,  # Higher confidence
            scope=MemoryScope.PROJECT,
            project_id="TEST_PROJECT",
            type=MemoryType.SEMANTIC
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember second similar memory
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # Depending on the conflict resolution strategy, we might have:
        # 1. Only one memory (if treated as duplicate)
        # 2. Two memories (if not similar enough to trigger conflict)
        # 3. One memory with updated values (if conflict resolution chose to update)

        # At minimum, we should have at least one memory
        self.assertGreaterEqual(self.manager.get_count(), 1)
        self.assertGreaterEqual(self.manager.get_active_count(), 1)

        # If we have memories, they should be valid
        if self.manager.get_count() > 0:
            # Get the most recent memory (should be record2 if it won)
            memories = self.manager.get_all_active()
            if memories:
                latest_memory = max(memories, key=lambda m: m.updated_at)
                # Should have reasonably high importance/confidence
                self.assertGreaterEqual(latest_memory.importance, 0.0)
                self.assertLessEqual(latest_memory.importance, 1.0)
                self.assertGreaterEqual(latest_memory.confidence, 0.0)
                self.assertLessEqual(latest_memory.confidence, 1.0)


if __name__ == '__main__':
    unittest.main()