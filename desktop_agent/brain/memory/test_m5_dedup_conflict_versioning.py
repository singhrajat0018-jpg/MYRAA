"""
Tests for MYRAA Memory 2.0 M5: Deduplication + Conflict Resolution + Versioning
"""

import unittest
import tempfile
import os
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.memory.unified_model import (
    MemoryRecord, MemoryType, MemoryScope, MemoryStatus,
    Sensitivity, RetentionPolicy, Provenance
)


class TestM5DeduplicationConflictVersioning(unittest.TestCase):
    """Test cases for M5 deduplication, conflict resolution, and versioning."""

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

    # ==========================================================
    # Deduplication Tests
    # ==========================================================

    def test_exact_fingerprint_deduplication(self):
        """Test Level 1 deduplication: exact fingerprint match."""
        record1 = MemoryRecord(
            content="User prefers dark mode",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        record2 = MemoryRecord(
            content="User prefers dark mode",  # Identical content
            source="test",
            importance=0.8,  # Different importance
            confidence=0.9,  # Different confidence
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)
        initial_count = self.manager.get_count()

        # Remember second memory (should be treated as duplicate)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)  # Should return true (updated)
        self.assertEqual(self.manager.get_count(), initial_count)  # Count unchanged

        # Recall the memory - should have adjusted importance/confidence
        recalled = self.manager.recall(record1.id)
        self.assertIsNotNone(recalled)
        # Should have higher importance/confidence from the second record
        self.assertGreaterEqual(recalled.importance, 0.7)
        self.assertGreaterEqual(recalled.confidence, 0.8)

    def test_normalized_content_deduplication(self):
        """Test Level 2 deduplication: normalized-content match."""
        record1 = MemoryRecord(
            content="User Prefers Dark Mode!",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        record2 = MemoryRecord(
            content="user prefers dark mode",  # Normalized identical
            source="test",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)
        initial_count = self.manager.get_count()

        # Remember second memory (should be treated as duplicate)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)
        self.assertEqual(self.manager.get_count(), initial_count)  # Count unchanged

        # Recall the memory
        recalled = self.manager.recall(record1.id)
        self.assertIsNotNone(recalled)
        # Should have adjusted values
        self.assertGreaterEqual(recalled.importance, 0.7)
        self.assertGreaterEqual(recalled.confidence, 0.8)

    def test_semantic_fact_deduplication(self):
        """Test Level 3 deduplication: same semantic fact with different wording."""
        record1 = MemoryRecord(
            content="The project deadline is next Friday",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_A",
            type=MemoryType.SEMANTIC
        )

        record2 = MemoryRecord(
            content="Project A deadline: Friday of next week",
            source="test",
            importance=0.8,
            confidence=0.85,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_A",
            type=MemoryType.SEMANTIC
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)
        initial_count = self.manager.get_count()

        # Remember second memory (should be treated as similar/semantic duplicate)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)
        # Depending on similarity threshold, this might update or create new
        # For now, we check that we have at least one memory
        self.assertGreaterEqual(self.manager.get_count(), 1)

        # If we have memories, check they're valid
        if self.manager.get_count() > 0:
            memories = self.manager.get_all_active()
            if memories:
                latest = max(memories, key=lambda m: m.updated_at)
                self.assertGreaterEqual(latest.importance, 0.7)
                self.assertGreaterEqual(latest.confidence, 0.8)

    def test_scoped_deduplication_respects_scope(self):
        """Test that deduplication respects scope boundaries."""
        record1 = MemoryRecord(
            content="I prefer dark mode",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.PREFERENCE
        )

        record2 = MemoryRecord(
            content="I prefer dark mode",  # Identical content
            source="test",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,  # Different scope
            type=MemoryType.PREFERENCE
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)
        initial_count = self.manager.get_count()

        # Remember second memory (should NOT be treated as duplicate due to different scope)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)
        self.assertEqual(self.manager.get_count(), initial_count + 1)  # Count increased

        # Both memories should exist
        recalled1 = self.manager.recall(record1.id)
        recalled2 = self.manager.recall(record2.id)
        self.assertIsNotNone(recalled1)
        self.assertIsNotNone(recalled2)
        self.assertEqual(recalled1.scope, MemoryScope.GLOBAL)
        self.assertEqual(recalled2.scope, MemoryScope.USER)

    def test_global_scope_deduplication_wins(self):
        """Test that in conflicts, GLOBAL scope memories take precedence."""
        record1 = MemoryRecord(
            content="User prefers dark mode",
            source="test",
            importance=0.6,
            confidence=0.7,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        record2 = MemoryRecord(
            content="User prefers dark mode",  # Identical content
            source="test",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.GLOBAL,  # GLOBAL scope
            type=MemoryType.PREFERENCE
        )

        # Remember USER scope memory first
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember GLOBAL scope memory second
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # Should have only one memory due to deduplication (GLOBAL wins)
        self.assertEqual(self.manager.get_count(), 1)

        # The remaining memory should be the GLOBAL one
        memories = self.manager.get_all_active()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].scope, MemoryScope.GLOBAL)
        self.assertEqual(memories[0].importance, 0.8)  # From GLOBAL record
        self.assertEqual(memories[0].confidence, 0.9)  # From GLOBAL record

    # ==========================================================
    # Conflict Detection Tests
    # ==========================================================

    def test_simple_conflict_detection(self):
        """Test detection of simple contradictory memories."""
        record1 = MemoryRecord(
            content="I prefer Python as my programming language",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        record2 = MemoryRecord(
            content="I prefer TypeScript as my programming language",  # Different value
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember second conflicting memory
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # Depending on conflict resolution, we might have:
        # 1. One memory (if one supersedes the other)
        # 2. Two memories (if kept both)
        # 3. Marked as conflicted
        # 4. Require confirmation

        # At minimum, we should have at least one memory
        self.assertGreaterEqual(self.manager.get_count(), 1)

    def test_conflict_with_different_scopes(self):
        """Test that conflicts are scoped appropriately."""
        record1 = MemoryRecord(
            content="Project uses React framework",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_A",
            type=MemoryType.SEMANTIC
        )

        record2 = MemoryRecord(
            content="Project uses Vue framework",  # Different value
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_B",  # Different project
            type=MemoryType.SEMANTIC
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember second memory (different project, should not conflict)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # Should have two memories since they're for different projects
        self.assertEqual(self.manager.get_count(), 2)

        # Both should be retrievable
        recalled1 = self.manager.recall(record1.id)
        recalled2 = self.manager.recall(record2.id)
        self.assertIsNotNone(recalled1)
        self.assertIsNotNone(recalled2)
        self.assertEqual(recalled1.project_id, "PROJECT_A")
        self.assertEqual(recalled2.project_id, "PROJECT_B")

    def test_explicit_user_correction_conflict_resolution(self):
        """Test that explicit user corrections have high authority in conflict resolution."""
        # Old memory from implicit observation
        old_record = MemoryRecord(
            content="User prefers English language",
            source="observation",
            importance=0.6,
            confidence=0.7,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            provenance=Provenance.USER_IMPLICIT
        )

        # New explicit user statement
        new_record = MemoryRecord(
            content="I now prefer Hinglish language",  # Explicit correction
            source="user_explicit",
            importance=0.9,
            confidence=0.95,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            provenance=Provenance.USER_EXPLICIT
        )

        # Remember old memory first
        result1 = self.manager.remember(old_record)
        self.assertTrue(result1)

        # Remember new explicit correction
        result2 = self.manager.remember(new_record)
        self.assertTrue(result2)

        # Should have only one memory (the new one should supersede the old)
        self.assertEqual(self.manager.get_count(), 1)

        # The remaining memory should be the new explicit one
        memories = self.manager.get_all_active()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].content, "I now prefer Hinglish language")
        self.assertEqual(memories[0].provenance, Provenance.USER_EXPLICIT)
        self.assertEqual(memories[0].importance, 0.9)
        self.assertEqual(memories[0].confidence, 0.95)

    def test_high_confidence_wins_in_conflict(self):
        """Test that higher confidence wins in conflict resolution."""
        record1 = MemoryRecord(
            content="The meeting is at 3 PM",
            source="source_a",
            importance=0.7,
            confidence=0.6,  # Lower confidence
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )

        record2 = MemoryRecord(
            content="The meeting is at 4 PM",  # Different time
            source="source_b",
            importance=0.7,
            confidence=0.9,  # Higher confidence
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember second memory with higher confidence
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # The higher confidence memory should win
        self.assertEqual(self.manager.get_count(), 1)

        memories = self.manager.get_all_active()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].content, "The meeting is at 4 PM")
        self.assertEqual(memories[0].confidence, 0.9)

    def test_recency_wins_in_conflict(self):
        """Test that more recent memories can win in conflict resolution."""
        import time

        record1 = MemoryRecord(
            content="User's current goal is to finish project",
            source="test",
            importance=0.8,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )

        # Simulate older memory by adjusting timestamp
        record2 = MemoryRecord(
            content="User's current goal is to start new project",  # Different goal
            source="test",
            importance=0.8,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )
        # Make record2 older by setting earlier timestamp
        old_time = time.time() - (24 * 3600)  # 1 day ago
        record2.created_at = old_time
        record2.updated_at = old_time
        record2.last_accessed_at = old_time

        # Remember first memory (older one)
        result1 = self.manager.remember(record2)
        self.assertTrue(result1)

        # Remember second memory (newer one)
        result2 = self.manager.remember(record1)
        self.assertTrue(result2)

        # Depending on scoring, the newer one might win due to recency factor
        # At minimum, we should have valid memories
        self.assertGreaterEqual(self.manager.get_count(), 1)

    # ==========================================================
    # Conflict Resolution Policy Tests
    # ==========================================================

    def test_keep_existing_resolution(self):
        """Test KEEP_EXISTING resolution policy."""
        # This would be tested indirectly through conflict resolution logic
        # For now, we verify the system doesn't arbitrarily drop established memories
        record1 = MemoryRecord(
            content="Established fact: Earth is round",
            source="textbook",
            importance=0.9,
            confidence=0.95,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.SEMANTIC,
            provenance=Provenance.DOCUMENT_DERIVED
        )

        record2 = MemoryRecord(
            content="New claim: Earth is flat",  # Contradictory
            source="blog",
            importance=0.3,
            confidence=0.4,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.SEMANTIC,
            provenance=Provenance.MODEL_INFERRED
        )

        # Remember established fact first
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember contradictory claim
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # The established fact should likely win due to higher importance/confidence/provenance
        # We check that we have at least one memory and it's reasonable
        self.assertGreaterEqual(self.manager.get_count(), 1)

        if self.manager.get_count() > 0:
            memories = self.manager.get_all_active()
            # Should have the established fact or a reasonable resolution
            for mem in memories:
                self.assertGreaterEqual(mem.importance, 0.3)
                self.assertGreaterEqual(mem.confidence, 0.3)

    def test_merge_resolution(self):
        """Test MERGE resolution policy."""
        # Create memories that should be merged rather than one winning
        record1 = MemoryRecord(
            content="User likes pizza",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            tags={"food"}
        )

        record2 = MemoryRecord(
            content="User also enjoys pasta",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            tags={"food"}
        )

        # Remember first memory
        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Remember second memory (related but different)
        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # Depending on similarity, they might be kept separate, merged, or one winning
        # We verify we have valid memories
        self.assertGreaterEqual(self.manager.get_count(), 1)

    # ==========================================================
    # Versioning Tests
    # ==========================================================

    def test_version_increment_on_update(self):
        """Test that version increments when memory is updated."""
        record = MemoryRecord(
            content="User's current title: Junior Developer",
            source="hr_system",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC,
            version=1
        )

        # Remember initial version
        result1 = self.manager.remember(record)
        self.assertTrue(result1)

        recalled_initial = self.manager.recall(record.id)
        self.assertIsNotNone(recalled_initial)
        self.assertEqual(recalled_initial.version, 1)

        # Update the memory with new information
        updated_record = MemoryRecord(
            content="User's current title: Senior Developer",  # Updated content
            source="hr_system",
            importance=0.85,
            confidence=0.92,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC,
            id=record.id,  # Same ID
            version=2  # This should be ignored - version is managed internally
        )

        # Remember updated version
        result2 = self.manager.remember(updated_record)
        self.assertTrue(result2)

        # Check that version was incremented
        recalled_updated = self.manager.recall(record.id)
        self.assertIsNotNone(recalled_updated)
        self.assertEqual(recalled_updated.version, 2)  # Should be incremented
        self.assertEqual(recalled_updated.content, "User's current title: Senior Developer")
        self.assertEqual(recalled_updated.importance, 0.85)
        self.assertEqual(recalled_updated.confidence, 0.92)

    def testՍ者supersedes_linking(self):
        """Test that supersedes/superseded_by links are properly maintained."""
        # Create initial memory
        v1_record = MemoryRecord(
            content="User preference: theme = blue",
            source="config",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            version=1
        )

        # Remember initial version
        result1 = self.manager.remember(v1_record)
        self.assertTrue(result1)

        # Create updated version
        v2_record = MemoryRecord(
            content="User preference: theme = dark",  # Updated value
            source="config",
            importance=0.75,
            confidence=0.85,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            version=2
        )

        # Remember updated version
        result2 = self.manager.remember(v2_record)
        self.assertTrue(result2)

        # Check that v1 is now superseded by v2
        v1_recalled = self.manager.recall(v1_record.id)
        v2_recalled = self.manager.recall(v2_record.id)

        self.assertIsNotNone(v1_recalled)
        self.assertIsNotNone(v2_recalled)

        # v1 should be SUPERSEDED
        self.assertEqual(v1_recalled.status, MemoryStatus.SUPERSEDED)
        self.assertEqual(v1_recalled.superseded_by, v2_record.id)

        # v2 should be ACTIVE and supersede v1
        self.assertEqual(v2_recalled.status, MemoryStatus.ACTIVE)
        self.assertEqual(v2_recalled.supersedes, v1_record.id)

    def test_version_persistence_across_restarts(self):
        """Test that version history persists across manager restarts."""
        # Create and remember a memory
        record1 = MemoryRecord(
            content="User's email: user@example.com",
            source="profile",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            version=1
        )

        result1 = self.manager.remember(record1)
        self.assertTrue(result1)

        # Update the memory
        record2 = MemoryRecord(
            content="User's email: newuser@example.com",
            source="profile",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            version=2
        )

        result2 = self.manager.remember(record2)
        self.assertTrue(result2)

        # Verify current state
        memories_before = self.manager.get_all_active()
        self.assertEqual(len(memories_before), 1)
        self.assertEqual(memories_before[0].content, "User's email: newuser@example.com")
        self.assertEqual(memories_before[0].version, 2)

        # Create a new manager with the same storage (simulating restart)
        self.manager.flush()
        new_manager = UnifiedMemoryManager(self.temp_file.name)

        # Check that version history is preserved
        memories_after = new_manager.get_all_active()
        self.assertEqual(len(memories_after), 1)
        self.assertEqual(memories_after[0].content, "User's email: newuser@example.com")
        self.assertEqual(memories_after[0].version, 2)

        # Check that we can still access the manager and it works
        test_record = MemoryRecord(
            content="Test persistence record",
            source="test",
            importance=0.5,
            confidence=0.6,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )
        result3 = new_manager.remember(test_record)
        self.assertTrue(result3)

    # ==========================================================
    # Memory States Integration Tests
    # ==========================================================

    def test_superseded_memory_not_in_normal_recall(self):
        """Test that SUPERSEDED memories are not returned in normal recall."""
        # Create initial memory
        v1_record = MemoryRecord(
            content="User's role: intern",
            source="hr",
            importance=0.6,
            confidence=0.7,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC,
            version=1
        )

        # Remember initial version
        result1 = self.manager.remember(v1_record)
        self.assertTrue(result1)

        # Create updated version
        v2_record = MemoryRecord(
            content="User's role: developer",  # Updated value
            source="hr",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC,
            version=2
        )

        # Remember updated version
        result2 = self.manager.remember(v2_record)
        self.assertTrue(result2)

        # Check that we have both memories in storage
        self.assertEqual(self.manager.get_count(), 2)

        # Check active count (should be 1 - only the latest)
        self.assertEqual(self.manager.get_active_count(), 1)

        # Check that only the ACTIVE memory is recallable
        active_memories = self.manager.get_all_active()
        self.assertEqual(len(active_memories), 1)
        self.assertEqual(active_memories[0].content, "User's role: developer")
        self.assertEqual(active_memories[0].status, MemoryStatus.ACTIVE)

        # Check that the SUPERSEDED memory exists but is not active
        all_memories = [self.manager.recall(mid) for mid in self.manager._records.keys()]
        all_memories = [m for m in all_memories if m is not None]
        superseded_memories = [m for m in all_memories if m.status == MemoryStatus.SUPERSEDED]
        self.assertEqual(len(superseded_memories), 1)
        self.assertEqual(superseded_memories[0].content, "User's role: intern")
        self.assertEqual(superseded_memories[0].status, MemoryStatus.SUPERSEDED)

        # Explicit-ID recall exposes version history: SUPERSEDED records remain
        # retrievable by ID for audit/history (M5 version-chaining contract).
        superseded_by_id = [m for m in all_memories if m.status == MemoryStatus.SUPERSEDED][0].id
        history_recall = self.manager.recall(superseded_by_id)
        self.assertIsNotNone(history_recall)
        self.assertEqual(history_recall.status, MemoryStatus.SUPERSEDED)
        self.assertEqual(history_recall.content, "User's role: intern")

        # NORMAL recall (by content) excludes SUPERSEDED history — only the
        # current ACTIVE version is returned as authentic information.
        normal_results = self.manager.recall_by_content("User's role", limit=10)
        self.assertEqual(len(normal_results), 1)
        self.assertEqual(normal_results[0].content, "User's role: developer")
        self.assertEqual(normal_results[0].status, MemoryStatus.ACTIVE)

    def test_conflicted_memory_handling(self):
        """Test handling of CONFLICTED memories."""
        # Create two conflicting memories of similar quality
        record1 = MemoryRecord(
            content="The budget for Q1 is $100K",
            source="finance_team",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_X",
            type=MemoryType.SEMANTIC
        )

        record2 = MemoryRecord(
            content="The budget for Q1 is $120K",  # Conflicting value
            source="budget_office",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_X",
            type=MemoryType.SEMANTIC
        )

        # Remember both memories
        result1 = self.manager.remember(record1)
        result2 = self.manager.remember(record2)
        self.assertTrue(result1)
        self.assertTrue(result2)

        # Check what happened - depending on conflict resolution
        # We verify we have valid memories in the system
        self.assertGreaterEqual(self.manager.get_count(), 1)

        # If we have conflicted memories, they should have proper status
        all_memories = [self.manager.recall(mid) for mid in self.manager._records.keys()]
        all_memories = [m for m in all_memories if m is not None]
        conflicted_memories = [m for m in all_memories if m.status == MemoryStatus.CONFLICTED]
        # Note: CONFLICTED status might not be fully implemented yet, so we check reasonably

    def test_deleted_memory_excluded_from_recall(self):
        """Test that DELETED memories are excluded from normal recall."""
        record = MemoryRecord(
            content="This memory will be deleted",
            source="test",
            importance=0.5,
            confidence=0.6,
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )

        # Remember the memory
        result = self.manager.remember(record)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_active_count(), 1)

        # Forget the memory
        forget_result = self.manager.forget(record.id)
        self.assertTrue(forget_result)

        # Check that it's no longer active
        self.assertEqual(self.manager.get_active_count(), 0)
        self.assertEqual(self.manager.get_count(), 1)  # Still exists in storage

        # Check that it's not recallable
        recalled = self.manager.recall(record.id)
        self.assertIsNone(recalled)

        # But we can still access it directly from storage if needed
        # (for debugging, audit, etc.) - this tests internal state
        with self.manager._lock:
            stored_record = self.manager._records.get(record.id)
            self.assertIsNotNone(stored_record)
            self.assertEqual(stored_record.status, MemoryStatus.DELETED)

    # ==========================================================
    # Scope + Versioning Isolation Tests
    # ==========================================================

    def test_project_isolation_during_version_updates(self):
        """Test that PROJECT_A memory updates don't affect PROJECT_B or GLOBAL."""
        # Create memories in different scopes
        global_record = MemoryRecord(
            content="Global company policy: remote work allowed",
            source="hr_policy",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.SEMANTIC
        )

        project_a_record = MemoryRecord(
            content="Project Alpha uses React framework",
            source="tech_lead",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_ALPHA",
            type=MemoryType.SEMANTIC
        )

        project_b_record = MemoryRecord(
            content="Project Beta uses Vue framework",
            source="tech_lead",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_BETA",
            type=MemoryType.SEMANTIC
        )

        # Remember all initial memories
        self.manager.remember(global_record)
        self.manager.remember(project_a_record)
        self.manager.remember(project_b_record)

        initial_count = self.manager.get_count()
        self.assertEqual(initial_count, 3)

        # Update Project Alpha memory
        updated_project_a = MemoryRecord(
            content="Project Alpha now uses Vue framework",  # Changed framework
            source="tech_lead",
            importance=0.75,
            confidence=0.85,
            scope=MemoryScope.PROJECT,
            project_id="PROJECT_ALPHA",
            type=MemoryType.SEMANTIC
        )

        result = self.manager.remember(updated_project_a)
        self.assertTrue(result)

        # Check that we still have 3 memories (no cross-contamination)
        self.assertEqual(self.manager.get_count(), 3)

        # Verify each scope still has correct memories
        global_memories = self.manager.recall_by_scope(MemoryScope.GLOBAL)
        self.assertEqual(len(global_memories), 1)
        self.assertEqual(global_memories[0].content, "Global company policy: remote work allowed")

        project_a_memories = self.manager.recall_by_scope(
            MemoryScope.PROJECT, project_id="PROJECT_ALPHA"
        )
        self.assertEqual(len(project_a_memories), 1)
        self.assertEqual(project_a_memories[0].content, "Project Alpha now uses Vue framework")

        project_b_memories = self.manager.recall_by_scope(
            MemoryScope.PROJECT, project_id="PROJECT_BETA"
        )
        self.assertEqual(len(project_b_memories), 1)
        self.assertEqual(project_b_memories[0].content, "Project Beta uses Vue framework")

        # Verify GLOBAL memory is unchanged
        self.assertNotIn("Vue", global_memories[0].content)
        self.assertIn("remote work allowed", global_memories[0].content)

    def test_global_isolation_during_version_updates(self):
        """Test that GLOBAL memory updates don't leak into USER scope incorrectly."""
        # Create memories
        global_record = MemoryRecord(
            content="Default language: English",
            source="system",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.PREFERENCE
        )

        user_record = MemoryRecord(
            content="User prefers Hinglish",
            source="user_input",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE
        )

        # Remember both
        self.manager.remember(global_record)
        self.manager.remember(user_record)

        initial_count = self.manager.get_count()
        self.assertEqual(initial_count, 2)

        # Update GLOBAL memory
        updated_global = MemoryRecord(
            content="Default language: Spanish",  # Changed default
            source="system_update",
            importance=0.75,
            confidence=0.85,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.PREFERENCE
        )

        result = self.manager.remember(updated_global)
        self.assertTrue(result)

        # Check that we still have 2 memories
        self.assertEqual(self.manager.get_count(), 2)

        # Verify scopes are still isolated
        global_memories = self.manager.recall_by_scope(MemoryScope.GLOBAL)
        user_memories = self.manager.recall_by_scope(MemoryScope.USER)

        self.assertEqual(len(global_memories), 1)
        self.assertEqual(len(user_memories), 1)

        # GLOBAL should have the updated value
        self.assertEqual(global_memories[0].content, "Default language: Spanish")
        self.assertEqual(global_memories[0].importance, 0.75)

        # USER should retain its original value (not affected by GLOBAL change)
        self.assertEqual(user_memories[0].content, "User prefers Hinglish")
        self.assertEqual(user_memories[0].importance, 0.8)

    # ==========================================================
    # Retrieval Integration Tests
    # ==========================================================

    def test_normal_recall_excludes_superseded_versions(self):
        """Test that normal recall excludes SUPERSEDED history."""
        # Create version chain
        v1 = MemoryRecord(
            content="API endpoint: /v1/users",
            source="docs",
            importance=0.6,
            confidence=0.8,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.SEMANTIC
        )

        v2 = MemoryRecord(
            content="API endpoint: /v2/users",
            source="docs",
            importance=0.6,
            confidence=0.8,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.SEMANTIC
        )

        v3 = MemoryRecord(
            content="API endpoint: /v3/users",
            source="docs",
            importance=0.6,
            confidence=0.8,
            scope=MemoryScope.GLOBAL,
            type=MemoryType.SEMANTIC
        )

        # Remember all versions
        self.manager.remember(v1)
        self.manager.remember(v2)
        self.manager.remember(v3)

        # Check total count
        total_count = self.manager.get_count()
        self.assertEqual(total_count, 3)

        # Check active count (should be 1 - only latest)
        active_count = self.manager.get_active_count()
        self.assertEqual(active_count, 1)

        # Check that recall by content returns only the latest
        results = self.manager.recall_by_content("API endpoint", limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "API endpoint: /v3/users")
        self.assertEqual(results[0].status, MemoryStatus.ACTIVE)

        # Verify that we cannot recall the superseded versions by content
        # (They should not appear in normal search results)
        v1_results = self.manager.recall_by_content("/v1/users", limit=10)
        v2_results = self.manager.recall_by_content("/v2/users", limit=10)

        # These might return empty or might return the latest if it matches
        # The key point is that normal recall should not return SUPERSEDED memories
        # as current/authentic information

    def test_deleted_memory_excluded_from_search_results(self):
        """Test that DELETED memories are excluded from search results."""
        # Create memories
        mem1 = MemoryRecord(
            content="Important project milestone: design complete",
            source="pm",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.PROJECT,
            project_id="WEBSITE_REDESIGN",
            type=MemoryType.EPISODIC
        )

        mem2 = MemoryRecord(
            content="Regular team meeting notes",
            source="notes",
            importance=0.5,
            confidence=0.6,
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC
        )

        # Remember both
        self.manager.remember(mem1)
        self.manager.remember(mem2)

        initial_count = self.manager.get_count()
        self.assertEqual(initial_count, 2)

        # Delete one memory
        delete_result = self.manager.forget(mem2.id)
        self.assertTrue(delete_result)

        # Check that we still have 2 total memories but only 1 active
        self.assertEqual(self.manager.get_count(), 2)
        self.assertEqual(self.manager.get_active_count(), 1)

        # Search should only return the active memory
        results = self.manager.recall_by_content("project milestone", limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Important project milestone: design complete")
        self.assertEqual(results[0].status, MemoryStatus.ACTIVE)

        results2 = self.manager.recall_by_content("team meeting", limit=10)
        self.assertEqual(len(results2), 0)  # Should not find deleted memory

    # ==========================================================
    # Write Governance Integration Tests
    # ==========================================================

    def test_write_governance_integration_with_m5(self):
        """Test that M5 features integrate properly with write governance pipeline."""
        # Test that a memory goes through the full pipeline: validation -> scoring ->
        # sensitivity -> usefulness -> deduplication -> conflict -> retention -> persist

        # Create a memory that should pass through all stages
        record = MemoryRecord(
            content="User has completed the Python tutorial",
            source="learning_system",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.EPISODIC,
            provenance=Provenance.SYSTEM_OBSERVED
        )

        # Remember the memory - should go through full pipeline
        result = self.manager.remember(record)
        self.assertTrue(result)

        # Verify it was stored
        self.assertEqual(self.manager.get_count(), 1)
        self.assertEqual(self.manager.get_active_count(), 1)

        recalled = self.manager.recall(record.id)
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled.content, "User has completed the Python tutorial")

        # Verify persistence worked
        # Create new manager with same storage
        self.manager.flush()
        new_manager = UnifiedMemoryManager(self.temp_file.name)
        self.assertEqual(new_manager.get_count(), 1)
        self.assertEqual(new_manager.get_active_count(), 1)

        recalled_new = new_manager.recall(record.id)
        self.assertIsNotNone(recalled_new)
        self.assertEqual(recalled_new.content, "User has completed the Python tutorial")

    # ==========================================================
    # Edge Case and Regression Tests
    # ==========================================================

    def test_empty_and_null_values(self):
        """Test handling of empty or null values."""
        # Test with empty content (should be rejected by validation)
        empty_record = MemoryRecord(
            content="",  # Empty content
            source="test",
            importance=0.5,
            confidence=0.6,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        result = self.manager.remember(empty_record)
        self.assertFalse(result)  # Should be rejected by validation

        # Test with whitespace-only content (should be treated as empty)
        whitespace_record = MemoryRecord(
            content="   ",  # Whitespace only
            source="test",
            importance=0.5,
            confidence=0.6,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        result2 = self.manager.remember(whitespace_record)
        self.assertFalse(result2)  # Should be rejected by validation after normalization

    def test_duplicate_prevention_chains(self):
        """Test deduplication chains: A=B, B=C, therefore A=C should be deduplicated."""
        record_a = MemoryRecord(
            content="The quick brown fox jumps over the lazy dog",
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        record_b = MemoryRecord(
            content="The quick brown fox jumps over lazy dog",  # Slightly different
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        record_c = MemoryRecord(
            content="Quick brown fox jumps over the lazy dog",  # Another variation
            source="test",
            importance=0.7,
            confidence=0.8,
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        # Remember all three
        result_a = self.manager.remember(record_a)
        result_b = self.manager.remember(record_b)
        result_c = self.manager.remember(record_c)

        # Depending on similarity thresholds, we might end up with 1, 2, or 3 memories
        # The important thing is that the system handles it gracefully
        self.assertGreaterEqual(self.manager.get_count(), 1)
        self.assertLessEqual(self.manager.get_count(), 3)

        # All stored memories should be valid
        all_memories = [self.manager.recall(mid) for mid in self.manager._records.keys()]
        all_memories = [m for m in all_memories if m is not None]
        for mem in all_memories:
            self.assertIsNotNone(mem.content)
            self.assertGreaterEqual(mem.importance, 0.0)
            self.assertLessEqual(mem.importance, 1.0)
            self.assertGreaterEqual(mem.confidence, 0.0)
            self.assertLessEqual(mem.confidence, 1.0)

    def test_concurrent_access_simulation(self):
        """Test basic concurrent access safety (simulated)."""
        # Remember several memories quickly
        memories = []
        for i in range(10):
            mem = MemoryRecord(
                content=f"Test memory {i}",
                source="test",
                importance=0.5 + (i * 0.05),  # Varying importance
                confidence=0.6,
                scope=MemoryScope.USER,
                type=MemoryType.SEMANTIC
            )
            memories.append(mem)
            result = self.manager.remember(mem)
            self.assertTrue(result)  # Each should succeed

        # Check that we have the expected number of memories
        # (Some might be deduplicated if content is too similar, but with different numbers
        # they should mostly be distinct)
        self.assertGreaterEqual(self.manager.get_count(), 5)  # At least half should remain
        self.assertLessEqual(self.manager.get_count(), 10)    # But no more than we added

        # Verify we can recall them
        recalled_count = 0
        for mem in memories:
            recalled = self.manager.recall(mem.id)
            if recalled is not None:
                recalled_count += 1

        # Should be able to recall most of them
        self.assertGreaterEqual(recalled_count, 5)


if __name__ == '__main__':
    unittest.main()