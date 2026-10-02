"""
MYRAA Brain
Context Manager

Manages context assembly for the BrainEngine with Phase 4 Context Fusion.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Optional

from desktop_agent.brain.models import BrainContext
from desktop_agent.brain.context.context_fusion_service import fuse_context, ContextFusionService


class ContextManager:
    """
    Assembles context for the BrainEngine based on priority ordering with Phase 4 fusion:
    1. Current user request
    2. Current task state
    3. Active ScreenState summary
    4. Relevant recent conversation
    5. Relevant tool results
    6. Relevant memory
    7. Older context only when necessary
    """

    # Budget for context metadata string length (characters)
    _CONTEXT_BUDGET_CHAR_LIMIT = 2000

    def __init__(
        self,
        perception: Optional[Any] = None,
        blackboard: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
    ):
        self.perception = perception
        self.blackboard = blackboard
        self.memory_manager = memory_manager

        # Note: For Phase 4, we use the ContextFusionService for authoritative context fusion
        # but retain perception/blackboard/memory_manager for backward compatibility

    def build(self, tool: str, args: dict) -> BrainContext:
        """
        Build a BrainContext for the given tool and arguments using Phase 4 Context Fusion.

        Args:
            tool: The tool name being executed.
            args: The arguments passed to the tool.

        Returns:
            A BrainContext instance containing assembled context.
        """
        # Use Phase 4 Context Fusion Service for authoritative context fusion
        # This implements: REQUEST → retrieve relevant memory → retrieve current world/application context
        # → fuse → rank → bound → provide to planner
        fusion_service = ContextFusionService(
            blackboard=self.blackboard,
            memory_manager=self.memory_manager
        )
        context = fusion_service.fuse_context(tool, args, self.perception)
        # Debug: Print context metadata to help debug test issues
        # print(f"DEBUG ContextManager.build: context.metadata = {context.metadata}")
        return context

    def build_from_state(self) -> BrainContext:
        """
        Build a BrainContext from the current state of perception, blackboard, and memory.
        This is used for general brain processes (thinking, decision, etc.) where there is
        no specific tool being executed.

        Assembles context based on priority ordering:
        1. Current user request (if available, otherwise skipped)
        2. Current task state
        3. Active ScreenState summary
        4. Relevant recent conversation
        5. Relevant tool results (skipped in this method)
        6. Relevant memory
        7. Older context only when necessary
        """
        # For build_from_state, we don't have a specific tool/args,
        # so we use placeholder values and focus on state-based context
        # but still apply Phase 4 fusion principles
        return self.build("brain_process", {})