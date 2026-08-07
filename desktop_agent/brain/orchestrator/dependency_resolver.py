"""
MYRAA Cognitive Engine
Dependency Resolver
"""

from __future__ import annotations

from ..planner.execution.execution_plan import ExecutionPlan
from ..planner.models.plan_step import PlanStep


class DependencyResolver:
    """
    Validates whether a plan step is ready to execute.
    """

    # -----------------------------------------------------

    def can_execute(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
    ) -> bool:

        if not step.depends_on:

            return True

        completed = {

            s.id

            for s in plan.steps

            if s.completed

        }

        return all(

            dependency in completed

            for dependency in step.depends_on

        )

    # -----------------------------------------------------

    def pending_dependencies(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
    ) -> list[int]:

        completed = {

            s.id

            for s in plan.steps

            if s.completed

        }

        return [

            dependency

            for dependency in step.depends_on

            if dependency not in completed

        ]