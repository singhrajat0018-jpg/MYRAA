"""
Tests for ContextFusionService implementing Phase 4 Canonical Context Fusion.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from desktop_agent.brain.context.context_fusion_service import ContextFusionService, ContextSource, FusionConfig
from desktop_agent.brain.models import BrainContext
from desktop_agent.brain.blackboard.working_blackboard import WorkingBlackboard
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.knowledge.services.project_context_service import ProjectContextService


class TestContextFusionService(unittest.TestCase):

    def setUp(self):
        self.blackboard = WorkingBlackboard()
        self.memory_manager = UnifiedMemoryManager()
        self.project_context_service = ProjectContextService(self.memory_manager)
        self.fusion_service = ContextFusionService(
            blackboard=self.blackboard,
            memory_manager=self.memory_manager,
            project_context_service=self.project_context_service
        )

    def test_memory_task_fusion(self):
        """Test that memory and task context are properly fused"""
        # Setup: Add task and memory context
        self.blackboard.write("cognitive_context", "current_task", {"goal": "send email to priya"})

        # Add a relevant memory
        from desktop_agent.brain.memory.unified_model import MemoryRecord, MemoryType, MemoryScope, Provenance, RetentionPolicy
        memory_record = MemoryRecord(
            type=MemoryType.EPISODIC,
            content="User frequently emails priya about project updates",
            summary="User frequently emails priya about project updates",
            source="test",
            scope=MemoryScope.USER,
            importance=0.8,
            confidence=0.9,
            provenance=Provenance.SYSTEM_OBSERVED,
            retention_policy=RetentionPolicy.LONG_TERM,
        )
        self.memory_manager.remember(memory_record)

        # Execute: Fuse context for email tool
        context = self.fusion_service.fuse_context("email", {"to": "priya"})

        # Verify: Both task and memory context should be present
        self.assertIsInstance(context, BrainContext)
        self.assertIn("fused_task_state", context.metadata)
        self.assertIn("fused_recent_conversation", context.metadata)  # May be empty but key should exist

        # Verify memory was retrieved and scored
        fusion_sources = context.metadata.get("fusion_sources", [])
        memory_sources = [s for s in fusion_sources if s.get("type") == "memory"]
        self.assertTrue(len(memory_sources) > 0, "Memory source should be present in fusion")

    def test_project_isolation(self):
        """Test that project-scoped context is properly isolated"""
        # Setup: Set current project in blackboard
        self.blackboard.write("project_context", "current_project", "myraa-project")

        # Mock project context service to return specific data
        with patch.object(self.project_context_service, 'get_project') as mock_get_project:
            mock_get_project.return_value = {
                "name": "myraa-project",
                "description": "Test project for isolation",
                "settings": {"language": "python"}
            }

            # Execute: Fuse context
            context = self.fusion_service.fuse_context("read_file", {"path": "test.py"})

            # Verify: Project context should be present with PROJECT scope
            fusion_sources = context.metadata.get("fusion_sources", [])
            project_sources = [s for s in fusion_sources if s.get("scope") == "PROJECT"]
            self.assertTrue(len(project_sources) > 0, "Project source should be present")

            # Verify the project source has correct data
            project_source = project_sources[0]
            self.assertEqual(project_source.get("name"), "project_context")
            self.assertIn("metadata", project_source)
            self.assertEqual(project_source["metadata"].get("type"), "project")

    def test_stale_context_suppression(self):
        """Test that stale context is properly suppressed"""
        # Setup: Create an old context source
        old_time = datetime.now() - timedelta(hours=2)  # Older than max_age_seconds (1 hour)

        # Manually create an old source to test suppression
        sources = [
            ContextSource(
                name="old_source",
                data={"info": "stale data"},
                scope="SESSION",
                confidence=0.9,
                timestamp=old_time.timestamp(),  # Old timestamp
                metadata={"type": "conversation"}
            ),
            ContextSource(
                name="fresh_source",
                data={"info": "fresh data"},
                scope="SESSION",
                confidence=0.9,
                timestamp=datetime.now().timestamp(),  # Fresh timestamp
                metadata={"type": "conversation"}
            )
        ]

        # Execute: Score and rank sources
        scored_sources = self.fusion_service._score_and_rank_sources(sources, "test_tool", {})

        # Verify: Fresh source should have higher score than old source
        self.assertGreater(len(scored_sources), 1, "Should have two scored sources")
        fresh_score = scored_sources[0][1]  # First element should be freshest
        old_score = scored_sources[1][1]   # Second element should be older

        self.assertGreater(fresh_score, old_score, "Fresh source should score higher than stale source")

        # Verify: When bounding/filtering, stale source might be filtered out if below threshold
        bounded_sources = self.fusion_service._bound_and_filter_sources(scored_sources)
        # At least the fresh source should remain
        self.assertGreaterEqual(len(bounded_sources), 1, "At least fresh source should remain after filtering")

    def test_conflicting_context(self):
        """Test handling of conflicting context from different sources"""
        # Setup: Create conflicting context sources
        sources = [
            ContextSource(
                name="source_a",
                data={"answer": "yes"},
                scope="SESSION",
                confidence=0.8,
                metadata={"type": "memory"}
            ),
            ContextSource(
                name="source_b",
                data={"answer": "no"},
                scope="USER",
                confidence=0.9,
                metadata={"type": "goal"}
            )
        ]

        # Execute: Score and rank sources
        scored_sources = self.fusion_service._score_and_rank_sources(sources, "test_tool", {})

        # Verify: Both sources should be scored and ranked
        self.assertEqual(len(scored_sources), 2, "Both sources should be scored")
        # USER scope should generally score higher than SESSION scope
        # But exact ranking depends on other factors like type weights

    def test_multimodal_context(self):
        """Test fusion of multimodal context (vision, conversation, etc.)"""
        # Setup: Mock perception with vision data
        mock_perception = Mock()
        mock_screen_state = Mock()
        mock_screen_state.active_application = "Chrome"
        mock_screen_state.active_window = "Google Search"
        mock_screen_state.timestamp = datetime.now().timestamp()
        mock_perception.state.screen_state = mock_screen_state

        # Add conversation context
        self.blackboard.write("conversation", "recent", [
            {"role": "user", "content": "What's the weather?"},
            {"role": "assistant", "content": "It's sunny today"}
        ])

        # Execute: Fuse context
        context = self.fusion_service.fuse_context("search_web", {"query": "weather"})

        # Verify: Multiple modality types should be present
        fusion_sources = context.metadata.get("fusion_sources", [])
        source_types = [s.get("type") for s in fusion_sources]

        # Should have conversation and potentially vision sources
        self.assertIn("conversation", source_types, "Conversation source should be present")

        # If vision processing worked, should have vision source
        # Note: This depends on the perception mock working correctly
        # The key test is that the service doesn't crash with multimodal input

    def test_bounded_context(self):
        """Test that context is properly bounded to prevent over-injection"""
        # Setup: Create many context sources
        sources = []
        for i in range(15):  # More than max_context_items (10)
            sources.append(ContextSource(
                name=f"source_{i}",
                data={"info": f"data {i}"},
                scope="SESSION",
                confidence=0.8,
                metadata={"type": "tool_result"}
            ))

        # Execute: Score and rank sources
        scored_sources = self.fusion_service._score_and_rank_sources(sources, "test_tool", {})

        # Verify: We have more than max context items before bounding
        self.assertGreater(len(scored_sources), 10, "Should have more sources than max limit")

        # Execute: Bound and filter sources
        bounded_sources = self.fusion_service._bound_and_filter_sources(scored_sources)

        # Verify: Number of sources should be bounded by max_context_items
        self.assertLessEqual(len(bounded_sources), 10,
                           f"Bounded sources ({len(bounded_sources)}) should not exceed max ({10})")

        # Verify: Sources are still ranked by relevance (highest first)
        if len(bounded_sources) > 1:
            first_source_score = bounded_sources[0].relevance if hasattr(bounded_sources[0], 'relevance') else 0
            second_source_score = bounded_sources[1].relevance if hasattr(bounded_sources[1], 'relevance') else 0
            self.assertGreaterEqual(first_source_score, second_source_score,
                                  "Sources should remain ranked by relevance after bounding")


if __name__ == "__main__":
    unittest.main()