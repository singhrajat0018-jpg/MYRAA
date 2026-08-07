"""
MYRAA Cognitive Engine

Goal Parser
"""

from __future__ import annotations

import re

from ..models.models import PlannerGoal


class GoalParser:
    """
    Parses raw user goals into a normalized PlannerGoal.
    """

    def parse(
        self,
        goal: str,
    ) -> PlannerGoal:
        """
        Convert a raw user request into a PlannerGoal.
        """

        normalized = self._normalize(goal)

        return PlannerGoal(
            text=normalized,
            confidence=1.0,
        )

    def _normalize(
        self,
        text: str,
    ) -> str:
        """
        Normalize user input.
        """

        text = text.strip()

        text = re.sub(r"\s+", " ", text)

        return text.lower()