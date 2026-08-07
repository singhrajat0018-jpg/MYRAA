"""
Brain Context

Immutable cognitive snapshot shared across
the entire Brain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from desktop_agent.brain.perception import PerceptionSnapshot
from desktop_agent.brain.world_model import WorldState
from desktop_agent.brain.reasoning_engine import ReasoningResult

@dataclass(slots=True, frozen=False)
class BrainContext:

    perception: PerceptionSnapshot

    world: WorldState

    reasoning: Optional[ReasoningResult]

    intent: Optional[Any]

    working_memory: Optional[Any]

    episodic_memory: Optional[Any]

    semantic_memory: Optional[Any]

    execution_history: tuple[Any, ...] = ()

    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------
    # Compatibility Properties
    # ------------------------------------------------------

    @property
    def active_app(self):

        state = self.perception.state

        if state is None:
            return None

        return state.active_application

    @property
    def active_window(self):

        state = self.perception.state

        if state is None:
            return None

        return state.active_window

    @property
    def clipboard(self):

        if self.metadata is None:

            return None

        return self.metadata.get("clipboard")