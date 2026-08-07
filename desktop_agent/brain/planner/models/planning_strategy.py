"""
MYRAA Cognitive Engine
Planner Strategy
"""

from __future__ import annotations

from enum import Enum


class PlanningStrategy(str, Enum):
    """
    Strategy used by the Planner to generate an execution plan.
    """

    # Single executable action
    DIRECT = "direct"

    # Break into multiple sequential steps
    SEQUENTIAL = "sequential"

    # Multiple independent steps
    PARALLEL = "parallel"

    # Automation workflow
    AUTOMATION = "automation"

    # Requires AI reasoning before execution
    REASONING = "reasoning"

    # User confirmation required
    CONFIRMATION = "confirmation"

    # Cannot create a valid plan
    REJECT = "reject"

    @property
    def is_multi_step(self) -> bool:
        return self in (
            PlanningStrategy.SEQUENTIAL,
            PlanningStrategy.PARALLEL,
            PlanningStrategy.AUTOMATION,
        )

    @property
    def requires_reasoning(self) -> bool:
        return self == PlanningStrategy.REASONING

    @property
    def requires_confirmation(self) -> bool:
        return self == PlanningStrategy.CONFIRMATION


    @property
    def is_terminal(self) -> bool:
        return self == PlanningStrategy.REJECT