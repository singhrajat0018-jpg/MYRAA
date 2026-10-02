"""
Tests for the MYRAA Unified Memory Model
"""

import unittest
import time
from unified_model import (
    MemoryRecord, MemoryType, MemoryScope, MemoryStatus, Sensitivity,
    RetentionPolicy, Provenance, validate_memory_record, is_valid_memory,
    create_working_memory, create_episodic_memory, create_semantic_memory,
    create_preference_memory, create_procedural_memory, create_experience_memory,
    memories_are_equivalent, calculate_memory_similarity
)


class TestUnifiedMemoryModel(unittest.TestCase):
    """Test cases for the Unified Memory Model."""

    def test_basic_creation(self):
        """Test basic memory record creation."""
        mem = MemoryRecord(
            content="Test memory content",
            source="test",
            importance=0.8,
            confidence=0.9
        )

        self.assertIsInstance(mem.id, str)
        self.assertEqual(mem.content, "Test memory content")
        self.assertEqual(mem.source, "test")
        self.assertEqual(mem.importance, 0.8)
        self.assertEqual(mem.confidence, 0.9)
        self.assertEqual(mem.type, MemoryType.SEMANTIC)  # Default
        self.assertEqual(mem.scope, MemoryScope.GLOBAL)  # Default
        self.assertEqual(mem.status, MemoryStatus.ACTIVE)  # Default
        self.assertEqual(mem.sensitivity, Sensitivity.PUBLIC)  # Default
        self.assertEqual(mem.retention_policy, RetentionPolicy.MEDIUM_TERM)  # Default
        self.assertEqual(mem.provenance, Provenance.SYSTEM_OBSERVED)  # Default

        # Check timestamps are set
        self.assertGreater(mem.created_at, 0)
        self.assertGreater(mem.updated_at, 0)
        self.assertGreater(mem.last_accessed_at, 0)

        # Check fingerprint is computed
        self.assertIsInstance(mem.fingerprint, str)
        self.assertGreater(len(mem.fingerprint), 0)

    def test_validation(self):
        """Test memory validation."""
        # Valid memory
        valid_mem = MemoryRecord(
            content="Valid memory",
            source="test",
            importance=0.5,
            confidence=0.5
        )
        self.assertTrue(is_valid_memory(valid_mem))
        self.assertEqual(len(validate_memory_record(valid_mem)), 0)

        # Invalid importance
        invalid_mem = MemoryRecord(
            content="Invalid memory",
            source="test",
            importance=1.5,  # Too high
            confidence=0.5
        )
        self.assertFalse(is_valid_memory(invalid_mem))
        errors = validate_memory_record(invalid_mem)
        self.assertTrue(any("Importance must be between 0.0 and 1.0" in err for err in errors))

        # Invalid confidence
        invalid_mem2 = MemoryRecord(
            content="Invalid memory",
            source="test",
            importance=0.5,
            confidence=-0.1  # Too low
        )
        self.assertFalse(is_valid_memory(invalid_mem2))
        errors = validate_memory_record(invalid_mem2)
        self.assertTrue(any("Confidence must be between 0.0 and 1.0" in err for err in errors))

        # Missing content
        empty_mem = MemoryRecord(
            content="",  # Empty content
            source="test",
            importance=0.5,
            confidence=0.5
        )
        self.assertFalse(is_valid_memory(empty_mem))
        errors = validate_memory_record(empty_mem)
        self.assertTrue(any("Memory content is required" in err for err in errors))

    def test_timestamps(self):
        """Test timestamp behavior."""
        mem = MemoryRecord(content="Test", source="test")
        creation_time = mem.created_at
        update_time = mem.updated_at
        access_time = mem.last_accessed_at

        # Wait a tiny bit
        time.sleep(0.01)

        # Access the memory
        mem.access()

        # Check that access time updated
        self.assertGreaterEqual(mem.last_accessed_at, access_time)
        self.assertEqual(mem.access_count, 1)

        # Check that recency was updated
        self.assertGreaterEqual(mem.recency, 0.0)
        self.assertLessEqual(mem.recency, 1.0)

    def test_importance_confidence_updates(self):
        """Test updating importance and confidence."""
        mem = MemoryRecord(
            content="Test memory",
            source="test",
            importance=0.5,
            confidence=0.5
        )

        # Test importance update
        mem.update_importance(0.9)
        self.assertEqual(mem.importance, 0.9)
        self.assertGreater(mem.updated_at, mem.created_at)

        # Test bounds
        mem.update_importance(1.5)  # Should clamp to 1.0
        self.assertEqual(mem.importance, 1.0)

        mem.update_importance(-0.5)  # Should clamp to 0.0
        self.assertEqual(mem.importance, 0.0)

        # Test confidence update
        mem.update_confidence(0.8)
        self.assertEqual(mem.confidence, 0.8)

        # Test bounds
        mem.update_confidence(1.5)  # Should clamp to 1.0
        self.assertEqual(mem.confidence, 1.0)

        mem.update_confidence(-0.5)  # Should clamp to 0.0
        self.assertEqual(mem.confidence, 0.0)

    def test_supersede_mechanism(self):
        """Test the supersede mechanism for versioning."""
        mem1 = MemoryRecord(
            content="Original memory",
            source="test",
            importance=0.7
        )

        mem2 = MemoryRecord(
            content="Updated memory",
            source="test",
            importance=0.8
        )

        # Initially, neither supersedes the other
        self.assertIsNone(mem1.superseded_by)
        self.assertIsNone(mem2.supersedes)
        self.assertEqual(mem1.status, MemoryStatus.ACTIVE)
        self.assertEqual(mem2.status, MemoryStatus.ACTIVE)

        # Make mem1 supersede mem2
        mem1.supersede_by(mem2.id)

        self.assertEqual(mem1.status, MemoryStatus.SUPERSEDED)
        self.assertEqual(mem1.superseded_by, mem2.id)
        self.assertIsNone(mem1.supersedes)  # mem1 doesn't supersede anything
        self.assertGreater(mem1.updated_at, mem1.created_at)

        # mem2 should still be active unless explicitly marked
        self.assertEqual(mem2.status, MemoryStatus.ACTIVE)
        self.assertIsNone(mem2.superseded_by)

    def test_expiration(self):
        """Test memory expiration logic."""
        # Test permanent memory (should never expire)
        perm_mem = MemoryRecord(
            content="Permanent memory",
            source="test",
            retention_policy=RetentionPolicy.PERMANENT
        )
        self.assertFalse(perm_mem.is_expired())

        # Test with explicit max age - memory created just now
        mem = MemoryRecord(
            content="Test memory",
            source="test"
        )
        # Should not expire with large future max age
        self.assertFalse(mem.is_expired(max_age_seconds=1000))  # Far in future
        # Should expire with past max age (memory is newer than allowed age)
        self.assertTrue(mem.is_expired(max_age_seconds=-1))  # Already expired

        # Test ephemeral memory logic by manipulating time
        # Create a memory that appears old
        old_time = time.time() - (10 * 60)  # 10 minutes ago
        eph_mem = MemoryRecord(
            content="Ephemeral memory",
            source="test",
            retention_policy=RetentionPolicy.EPHEMERAL
        )
        # Manually set the creation time to simulate age
        eph_mem.created_at = old_time
        eph_mem.updated_at = old_time
        eph_mem.last_accessed_at = old_time

        # Should expire because it's older than EPHEMERAL limit (5 minutes)
        self.assertTrue(eph_mem.is_expired())

        # Test that a recent ephemeral memory doesn't expire
        recent_mem = MemoryRecord(
            content="Recent memory",
            source="test",
            retention_policy=RetentionPolicy.EPHEMERAL
        )
        # Should not expire immediately (just created)
        self.assertFalse(recent_mem.is_expired())

    def test_serialization_deserialization(self):
        """Test JSON serialization and deserialization."""
        original = MemoryRecord(
            content="Test memory for serialization",
            source="test_serialization",
            importance=0.8,
            confidence=0.9,
            scope=MemoryScope.USER,
            type=MemoryType.PREFERENCE,
            tags={"test", "serialization"},
            entities={"entity1", "entity2"}
        )

        # Serialize to JSON
        json_str = original.to_json()
        self.assertIsInstance(json_str, str)
        self.assertGreater(len(json_str), 0)

        # Deserialize from JSON
        restored = MemoryRecord.from_json(json_str)

        # Check key fields match
        self.assertEqual(original.content, restored.content)
        self.assertEqual(original.source, restored.source)
        self.assertEqual(original.importance, restored.importance)
        self.assertEqual(original.confidence, restored.confidence)
        self.assertEqual(original.scope, restored.scope)
        self.assertEqual(original.type, restored.type)
        self.assertEqual(original.status, restored.status)
        self.assertEqual(original.sensitivity, restored.sensitivity)
        self.assertEqual(original.retention_policy, restored.retention_policy)
        self.assertEqual(original.provenance, restored.provenance)
        self.assertEqual(original.tags, restored.tags)
        self.assertEqual(original.entities, restored.entities)

        # Fingerprint should match
        self.assertEqual(original.fingerprint, restored.fingerprint)

        # ID should match
        self.assertEqual(original.id, restored.id)

    def test_factory_functions(self):
        """Test the memory factory functions."""
        # Working memory
        working = create_working_memory(
            content="Working memory test",
            source="test_factory"
        )
        self.assertEqual(working.type, MemoryType.WORKING)
        self.assertEqual(working.scope, MemoryScope.SESSION)
        self.assertIn(working.retention_policy, [RetentionPolicy.EPHEMERAL, RetentionPolicy.SHORT_TERM])

        # Episodic memory
        episodic = create_episodic_memory(
            title="Test Event",
            description="This is a test event",
            category="test",
            importance=0.7
        )
        self.assertEqual(episodic.type, MemoryType.EPISODIC)
        self.assertEqual(episodic.scope, MemoryScope.USER)
        self.assertIn("test", episodic.tags)
        self.assertEqual(episodic.summary, "Test Event")

        # Semantic memory
        semantic = create_semantic_memory(
            key="test_key",
            value="test_value",
            confidence=0.95,
            source="test_factory"
        )
        self.assertEqual(semantic.type, MemoryType.SEMANTIC)
        self.assertEqual(semantic.scope, MemoryScope.GLOBAL)
        self.assertEqual(semantic.confidence, 0.95)
        self.assertIn("test_key", semantic.tags)

        # Preference memory
        preference = create_preference_memory(
            preference="theme",
            value="dark",
            source="user_explicit",
            importance=0.9
        )
        self.assertEqual(preference.type, MemoryType.PREFERENCE)
        self.assertEqual(preference.scope, MemoryScope.USER)
        self.assertEqual(preference.retention_policy, RetentionPolicy.PERMANENT)
        self.assertEqual(preference.importance, 0.9)
        self.assertIn("theme", preference.tags)
        self.assertIn("preference", preference.tags)

        # Procedural memory
        procedural = create_procedural_memory(
            name="test_procedure",
            description="A test procedure",
            steps=["step1", "step2", "step3"],
            success_rate=0.9,
            source="observed"
        )
        self.assertEqual(procedural.type, MemoryType.PROCEDURAL)
        self.assertEqual(procedural.scope, MemoryScope.PROJECT)
        self.assertEqual(procedural.importance, 0.7 + (0.9 * 0.3))  # 0.97
        self.assertIn("test_procedure", procedural.tags)
        self.assertIn("procedure", procedural.tags)
        self.assertEqual(procedural.relations.get("steps"), ["step1", "step2", "step3"])

        # Experience memory
        experience = create_experience_memory(
            goal="Test goal",
            plan="Test plan",
            outcome="Test outcome",
            success=True,
            user_feedback="Great job!",
            source="test_factory"
        )
        self.assertEqual(experience.type, MemoryType.EXPERIENCE)
        self.assertEqual(experience.scope, MemoryScope.USER)
        self.assertIn("experience", experience.tags)
        self.assertIn("success", experience.tags)
        self.assertGreater(experience.importance, 0.7)  # Successful experiences are important

    def test_memory_equivalence(self):
        """Test memory equivalence checking."""
        # Identical memories
        mem1 = MemoryRecord(
            content="Same content",
            source="test",
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        mem2 = MemoryRecord(
            content="Same content",
            source="test",
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        # Different IDs but same content should be equivalent
        self.assertTrue(memories_are_equivalent(mem1, mem2))

        # Different content
        mem3 = MemoryRecord(
            content="Different content",
            source="test",
            scope=MemoryScope.USER,
            type=MemoryType.SEMANTIC
        )

        self.assertFalse(memories_are_equivalent(mem1, mem3))

        # Different scope
        mem4 = MemoryRecord(
            content="Same content",
            source="test",
            scope=MemoryScope.GLOBAL,  # Different scope
            type=MemoryType.SEMANTIC
        )

        self.assertFalse(memories_are_equivalent(mem1, mem4))

        # Similarity calculation
        sim = calculate_memory_similarity(mem1, mem2)
        self.assertEqual(sim, 1.0)  # Identical

        sim2 = calculate_memory_similarity(mem1, mem3)
        self.assertLess(sim2, 1.0)  # Different

        sim3 = calculate_memory_similarity(mem1, mem4)
        self.assertLess(sim3, 1.0)  # Different scope

    def test_access_tracking(self):
        """Test memory access tracking."""
        mem = MemoryRecord(content="Test memory", source="test")

        initial_access = mem.access_count
        initial_time = mem.last_accessed_at

        # Access multiple times
        mem.access()
        mem.access()
        mem.access()

        self.assertEqual(mem.access_count, initial_access + 3)
        self.assertGreaterEqual(mem.last_accessed_at, initial_time)

        # Test that we can convert to dict
        mem_dict = mem.to_dict()
        self.assertIsInstance(mem_dict, dict)
        self.assertIn('content', mem_dict)
        self.assertIn('importance', mem_dict)
        self.assertIn('access_count', mem_dict)


if __name__ == '__main__':
    unittest.main()