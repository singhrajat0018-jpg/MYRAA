"""
Goal Priority Engine
"""

from __future__ import annotations

from .goal import Goal


class GoalPriority:

    """
    Calculates runtime goal priority.
    """

    def calculate(

        self,

        goal: Goal,

    ) -> float:

        score = goal.priority

        score += goal.confidence * 0.20

        score += goal.progress * 0.10

        if goal.deadline:

            score += 0.20

        return min(score, 1.0)