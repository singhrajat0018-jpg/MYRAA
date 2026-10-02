"""
MYRAA Context Fusion Service

Implements authoritative context fusion for Phase 4 of Full System Integration.
Combines multiple context sources with relevance scoring, bounding, and filtering.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from desktop_agent.brain.models import BrainContext
from desktop_agent.brain.blackboard.working_blackboard import WorkingBlackboard
from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
from desktop_agent.brain.knowledge.services.project_context_service import ProjectContextService


@dataclass
class ContextSource:
    """Represents a context source with metadata for fusion."""
    name: str
    data: Any
    relevance: float = 0.0
    scope: str = "USER"  # USER, GLOBAL, PROJECT, SESSION
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionConfig:
    """Configuration for context fusion."""
    max_context_items: int = 10
    max_memory_items: int = 5
    min_relevance_threshold: float = 0.1
    max_age_seconds: float = 3600.0  # 1 hour
    scope_weights: Dict[str, float] = field(default_factory=lambda: {
        "USER": 1.0,
        "PROJECT": 0.8,
        "SESSION": 0.6,
        "GLOBAL": 0.4
    })
    type_weights: Dict[str, float] = field(default_factory=lambda: {
        "goal": 1.0,
        "task": 0.9,
        "memory": 0.8,
        "conversation": 0.7,
        "application": 0.6,
        "vision": 0.6,
        "tool_result": 0.5,
        "preference": 0.4
    })


class ContextFusionService:
    """
    Authoritative context fusion service.

    Implements Phase 4: Canonical Context Fusion
    Combines multiple context sources with relevance-aware, scope-aware,
    confidence-aware, and freshness-aware fusion.
    """

    def __init__(
        self,
        blackboard: Optional[WorkingBlackboard] = None,
        memory_manager: Optional[UnifiedMemoryManager] = None,
        project_context_service: Optional[ProjectContextService] = None,
        config: Optional[FusionConfig] = None
    ):
        self.blackboard = blackboard or WorkingBlackboard()
        self.memory_manager = memory_manager or UnifiedMemoryManager()
        self.project_context_service = project_context_service or ProjectContextService(
            UnifiedMemoryManager()  # This would normally be injected properly
        )
        self.config = config or FusionConfig()

    def fuse_context(
        self,
        tool: str,
        args: Dict[str, Any],
        perception=None,
    ) -> BrainContext:
        """
        Fuse context from all available sources.

        Flow:
        REQUEST → retrieve relevant memory → retrieve current world/application context
                  → fuse → rank → bound → provide to planner

        Args:
            tool: The tool being executed
            args: The arguments passed to the tool
            perception: Optional perception component for vision/screen context

        Returns:
            BrainContext with fused and bounded context
        """
        # Collect all context sources
        sources = self._collect_context_sources(tool, args, perception)

        # Score and rank sources
        scored_sources = self._score_and_rank_sources(sources, tool, args)

        # Bound and filter context
        bounded_sources = self._bound_and_filter_sources(scored_sources)

        # Build final BrainContext
        return self._build_brain_context(bounded_sources, tool, args)

    def _collect_context_sources(
        self,
        tool: str,
        args: Dict[str, Any],
        perception=None,
    ) -> List[ContextSource]:
        """Collect context from all available sources."""
        sources = []

        # 1. Current request (highest priority)
        sources.append(ContextSource(
            name="current_request",
            data={"tool": tool, "args": args},
            scope="SESSION",
            confidence=1.0,
            metadata={"type": "request"}
        ))

        # 2. Current conversation from blackboard
        try:
            recent_conversation = self.blackboard.read(
                "conversation", "recent", default=[]
            )
            if recent_conversation:
                sources.append(ContextSource(
                    name="recent_conversation",
                    data=recent_conversation,
                    scope="SESSION",
                    confidence=0.9,
                    metadata={"type": "conversation", "count": len(recent_conversation)}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'conversation' failed: %s", e)

        # 3. Active goal from blackboard
        try:
            current_goal = self.blackboard.read(
                "cognitive_context", "current_goal", default=""
            )
            if current_goal:
                sources.append(ContextSource(
                    name="current_goal",
                    data=current_goal,
                    scope="SESSION",
                    confidence=0.95,
                    metadata={"type": "goal"}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'current_goal' failed: %s", e)

        # 4. Current task state from blackboard
        try:
            current_task = self.blackboard.read(
                "cognitive_context", "current_task", default={}
            )
            if current_task:
                sources.append(ContextSource(
                    name="current_task",
                    data=current_task,
                    scope="SESSION",
                    confidence=0.9,
                    metadata={"type": "task"}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'current_task' failed: %s", e)

        # 5. Active application/window from cognitive context
        try:
            current_app = self.blackboard.read(
                "cognitive_context", "current_application", default=""
            )
            current_window = self.blackboard.read(
                "cognitive_context", "current_window", default=""
            )
            if current_app or current_window:
                sources.append(ContextSource(
                    name="application_state",
                    data={
                        "application": current_app,
                        "window": current_window
                    },
                    scope="SESSION",
                    confidence=0.8,
                    metadata={"type": "application"}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'application_state' failed: %s", e)

        # 6. Screen/vision context from perception
        if perception is not None:
            try:
                screen_state = getattr(perception.state, 'screen_state', None)
                if screen_state is not None:
                    vision_context = {
                        'active_application': getattr(screen_state, 'active_application', None),
                        'active_window': getattr(screen_state, 'active_window', None),
                        'timestamp': getattr(screen_state, 'timestamp', None),
                    }
                    sources.append(ContextSource(
                        name="vision_context",
                        data=vision_context,
                        scope="SESSION",
                        confidence=0.85,
                        metadata={"type": "vision"}
                    ))
            except Exception as e:
                import logging
                logging.getLogger(__name__).debug("Context source 'vision_context' failed: %s", e)

        # 7. Relevant memories from Memory 2.0
        try:
            # Create a query from tool and args for memory retrieval
            # Extract string values from args for better matching
            args_str = ' '.join(str(v) for v in args.values() if isinstance(v, str) and v.strip())
            query = f"{tool} {args_str}".strip()
            relevant_memories = self.memory_manager.get_relevant_memories(query, limit=10, min_relevance=0.05)
            if relevant_memories:
                sources.append(ContextSource(
                    name="relevant_memories",
                    data=relevant_memories,
                    scope="USER",  # Memories are typically user-scoped
                    confidence=0.9,
                    metadata={"type": "memory", "count": len(relevant_memories)}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'relevant_memories' failed: %s", e)

        # 8. Project context
        try:
            # Get current project from blackboard or derive from context
            current_project = self.blackboard.read(
                "project_context", "current_project", default=None
            )
            if current_project:
                project_info = self.project_context_service.get_project(current_project)
                if project_info:
                    sources.append(ContextSource(
                        name="project_context",
                        data=project_info,
                        scope="PROJECT",
                        confidence=0.8,
                        metadata={"type": "project"}
                    ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'project_context' failed: %s", e)

        # 9. User preferences (from blackboard or memory)
        try:
            user_prefs = self.blackboard.read(
                "user_preferences", "all", default={}
            )
            if user_prefs:
                sources.append(ContextSource(
                    name="user_preferences",
                    data=user_prefs,
                    scope="USER",
                    confidence=0.7,
                    metadata={"type": "preference"}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'user_preferences' failed: %s", e)

        # 10. Recent tool results
        try:
            recent_tool_results = self.blackboard.read(
                "execution_history", "recent", default=[]
            )
            if recent_tool_results:
                sources.append(ContextSource(
                    name="recent_tool_results",
                    data=recent_tool_results[-5:],  # Last 5 results
                    scope="SESSION",
                    confidence=0.6,
                    metadata={"type": "tool_result", "count": len(recent_tool_results)}
                ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("Context source 'recent_tool_results' failed: %s", e)

        return sources

    def _score_and_rank_sources(
        self,
        sources: List[ContextSource],
        tool: str,
        args: Dict[str, Any],
    ) -> List[Tuple[ContextSource, float]]:
        """Score and rank context sources by relevance."""
        scored_sources = []

        for source in sources:
            # Start with base confidence
            score = source.confidence

            # Apply scope weighting
            scope_weight = self.config.scope_weights.get(source.scope, 0.5)
            score *= scope_weight

            # Apply type weighting if available
            source_type = source.metadata.get("type", "unknown")
            type_weight = self.config.type_weights.get(source_type, 0.5)
            score *= type_weight

            # Apply freshness decay
            age = time.time() - source.timestamp
            if age < self.config.max_age_seconds:
                freshness_factor = 1.0 - (age / self.config.max_age_seconds)
                score *= (0.5 + 0.5 * freshness_factor)  # 0.5 to 1.0 range
            else:
                score *= 0.1  # Heavily penalize old content

            # Apply content-based relevance boosting
            content_boost = self._calculate_content_relevance(source, tool, args)
            score *= (1.0 + content_boost)

            # Update source with calculated relevance
            source.relevance = score
            scored_sources.append((source, score))

        # Sort by score descending
        scored_sources.sort(key=lambda x: x[1], reverse=True)
        return scored_sources

    def _calculate_content_relevance(
        self,
        source: ContextSource,
        tool: str,
        args: Dict[str, Any],
    ) -> float:
        """Calculate content-based relevance boost."""
        boost = 0.0
        source_data = str(source.data).lower()
        query = f"{tool} {str(args)}".lower()

        # Exact phrase matching boost
        if query in source_data:
            boost += 0.5

        # Keyword matching
        query_words = set(query.split())
        source_words = set(source_data.split())
        if query_words and source_words:
            overlap = len(query_words.intersection(source_words))
            if len(query_words) > 0:
                boost += 0.3 * (overlap / len(query_words))

        # Special boosting for certain source types
        source_type = source.metadata.get("type", "")
        if source_type == "goal" and any(word in source_data for word in query_words):
            boost += 0.4
        elif source_type == "task" and any(word in source_data for word in query_words):
            boost += 0.3
        elif source_type == "memory" and any(word in source_data for word in query_words):
            boost += 0.2

        return min(boost, 1.0)  # Cap the boost

    def _bound_and_filter_sources(
        self,
        scored_sources: List[Tuple[ContextSource, float]],
    ) -> List[ContextSource]:
        """Bound and filter context sources to prevent over-injection."""
        bounded_sources = []
        memory_count = 0

        for source, score in scored_sources:
            # Skip if below minimum relevance threshold
            if score < self.config.min_relevance_threshold:
                continue

            # Limit memory items to prevent context pollution
            if source.metadata.get("type") == "memory":
                if memory_count >= self.config.max_memory_items:
                    continue
                memory_count += 1

            # Stop if we've reached max context items
            if len(bounded_sources) >= self.config.max_context_items:
                break

            bounded_sources.append(source)

        return bounded_sources

    def _build_brain_context(
        self,
        sources: List[ContextSource],
        tool: str,
        args: Dict[str, Any],
    ) -> BrainContext:
        """Build the final BrainContext from fused sources."""
        context = BrainContext()
        context.timestamp = datetime.now()
        context.metadata["tool"] = tool
        context.metadata["args"] = args
        context.metadata["fusion_sources"] = [
            {
                "name": s.name,
                "type": s.metadata.get("type", "unknown"),
                "scope": s.scope,
                "relevance": s.relevance,
                "confidence": s.confidence,
                "metadata": s.metadata
            }
            for s in sources
        ]

        # Initialize expected context fields to ensure they exist even when empty
        context.metadata["fused_goal"] = ""
        context.metadata["fused_task_state"] = {}
        context.metadata["fused_recent_conversation"] = []
        context.metadata["fused_application_state"] = {}
        context.metadata["fused_project_context"] = {}
        context.metadata["fused_user_preferences"] = {}
        context.metadata["fused_recent_tool_results"] = []
        context.metadata['memory'] = []

        # Extract and assign standard context fields from sources
        for source in sources:
            source_type = source.metadata.get("type", "")
            source_data = source.data

            if source_type == "request":
                # Request data is already in metadata
                pass
            elif source_type == "goal":
                context.metadata["fused_goal"] = source_data
            elif source_type == "task":
                context.metadata["fused_task_state"] = source_data
            elif source_type == "conversation":
                context.metadata["fused_recent_conversation"] = source_data
            elif source_type == "application":
                context.metadata["fused_application_state"] = source_data
                if isinstance(source_data, dict):
                    context.active_app = source_data.get("application")
                    # Note: active_window would be set similarly if available
            elif source_type == "vision":
                context.vision_context = source_data
                if isinstance(source_data, dict):
                    context.active_app = source_data.get("active_application")
                    context.active_window = source_data.get("active_window")
            elif source_type == "memory":
                # Store memories in the expected location for tests
                context.metadata['memory'] = source_data
            elif source_type == "project":
                context.metadata["fused_project_context"] = source_data
            elif source_type == "preference":
                context.metadata["fused_user_preferences"] = source_data
            elif source_type == "tool_result":
                context.metadata["fused_recent_tool_results"] = source_data

        return context


# Global instance for easy access
_context_fusion_service: Optional[ContextFusionService] = None


def get_context_fusion_service() -> ContextFusionService:
    """Get or create the global context fusion service instance."""
    global _context_fusion_service
    if _context_fusion_service is None:
        _context_fusion_service = ContextFusionService()
    return _context_fusion_service


def fuse_context(
    tool: str,
    args: Dict[str, Any],
    perception=None,
) -> BrainContext:
    """
    Convenience function to fuse context using the global service.

    Args:
        tool: The tool being executed
        args: The arguments passed to the tool
        perception: Optional perception component

    Returns:
        BrainContext with fused context
    """
    return get_context_fusion_service().fuse_context(tool, args, perception)