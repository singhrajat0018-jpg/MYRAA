"""
MYRAA Cognitive Engine
Planner Rules
"""

from __future__ import annotations

from dataclasses import dataclass

from ..decision.execution_strategy import ExecutionStrategy
from .planning.strategy import PlanningStrategy


@dataclass(slots=True)
class PlannerRule:
    """
    Maps a Decision Engine strategy to a Planner strategy.
    """

    execution_strategy: ExecutionStrategy

    planning_strategy: PlanningStrategy


class PlannerRules:
    """
    Centralized planning strategy rules.
    """

    RULES = {

        ExecutionStrategy.DIRECT:
            PlanningStrategy.DIRECT,

        ExecutionStrategy.PLAN:
            PlanningStrategy.SEQUENTIAL,

        ExecutionStrategy.REASON:
            PlanningStrategy.REASONING,

        ExecutionStrategy.AUTOMATION:
            PlanningStrategy.AUTOMATION,

        ExecutionStrategy.CONFIRM:
            PlanningStrategy.CONFIRMATION,

        ExecutionStrategy.REJECT:
            PlanningStrategy.REJECT,

        ExecutionStrategy.UNKNOWN:
            PlanningStrategy.REJECT,
    }

    @classmethod
    def resolve(
        cls,
        strategy: ExecutionStrategy,
    ) -> PlanningStrategy:

        return cls.RULES.get(
            strategy,
            PlanningStrategy.REJECT,
        )