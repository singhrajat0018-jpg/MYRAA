"""
MYRAA Cognitive Engine

Plan Optimizer
"""

from __future__ import annotations

from ..execution.execution_plan import ExecutionPlan
from ..models.action_types import ActionType
from ..models.plan_step import PlanStep


class PlanOptimizer:
    """
    Optimizes execution plans before execution.
    """

    def optimize(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionPlan:

        plan.steps = self._remove_duplicate_waits(plan.steps)

        plan.steps = self._remove_empty_type_steps(plan.steps)

        plan.steps = self._renumber_steps(plan.steps)

        plan.estimated_steps = len(plan.steps)

        return plan

    # =====================================================
    # Duplicate Wait Removal
    # =====================================================

    def _remove_duplicate_waits(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:

        optimized: list[PlanStep] = []

        previous_wait = False

        for step in steps:

            if step.action == ActionType.WAIT:

                if previous_wait:
                    continue

                previous_wait = True

            else:

                previous_wait = False

            optimized.append(step)

        return optimized

    # =====================================================
    # Empty Typing Removal
    # =====================================================

    def _remove_empty_type_steps(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:

        optimized: list[PlanStep] = []

        for step in steps:

            if step.action == ActionType.TYPE_TEXT:

                text = step.parameters.get("text", "")

                if not str(text).strip():
                    continue

            optimized.append(step)

        return optimized

    # =====================================================
    # Renumber IDs
    # =====================================================

    def _renumber_steps(
        self,
        steps: list[PlanStep],
    ) -> list[PlanStep]:

        for index, step in enumerate(steps, start=1):

            step.id = index

        return steps