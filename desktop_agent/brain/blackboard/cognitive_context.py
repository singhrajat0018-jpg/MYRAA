"""
MYRAA Cognitive Context

Shared cognitive state used by the Blackboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CognitiveContext:
    """
    Shared runtime context.
    """

    timestamp: datetime = field(
        default_factory=datetime.utcnow,
    )

    current_goal: str = ""

    current_activity: str = ""

    current_application: str = ""

    current_user_query: str = ""

    emotional_state: str = "neutral"

    attention_target: str = ""

    reasoning_state: str = ""

    planner_state: str = ""

    execution_state: str = ""

    vision_state: str = ""

    knowledge_state: str = ""

    memory_state: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    # --------------------------------------------------

    def touch(self):

        self.timestamp = datetime.utcnow()

    # --------------------------------------------------

    def update(

        self,

        **kwargs,

    ):

        for key, value in kwargs.items():

            if hasattr(self, key):

                setattr(

                    self,

                    key,

                    value,

                )

        self.touch()

    # --------------------------------------------------

    def to_dict(self):

        return {

            "timestamp": self.timestamp,

            "current_goal": self.current_goal,

            "current_activity": self.current_activity,

            "current_application": self.current_application,

            "current_user_query": self.current_user_query,

            "emotional_state": self.emotional_state,

            "attention_target": self.attention_target,

            "reasoning_state": self.reasoning_state,

            "planner_state": self.planner_state,

            "execution_state": self.execution_state,

            "vision_state": self.vision_state,

            "knowledge_state": self.knowledge_state,

            "memory_state": self.memory_state,

            "metadata": self.metadata,

        }