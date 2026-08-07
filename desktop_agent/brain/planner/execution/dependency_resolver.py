"""
MYRAA Cognitive Engine

Dependency Resolver

Manages execution dependencies between PlanSteps.
"""

from __future__ import annotations

from ..models.plan_step import PlanStep
from .execution_plan import ExecutionPlan

from .exceptions import DependencyError



class DependencyResolver:
    """
    Resolves and validates step dependencies.
    """



    # =====================================================
    # Validate Dependencies
    # =====================================================

    def validate(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
    ) -> None:
        """
        Validate that all dependencies
        are completed before execution.
        """

        for dependency_id in step.depends_on:

            dependency = self._find_step(
                dependency_id,
                plan,
            )


            if dependency is None:

                raise DependencyError(
                    f"Missing dependency step: {dependency_id}"
                )


            if not dependency.completed:

                raise DependencyError(

                    f"Step {step.id} waiting for "
                    f"Step {dependency_id}"

                )



    # =====================================================
    # Check Status
    # =====================================================

    def dependencies_satisfied(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
    ) -> bool:
        """
        Returns True if all dependencies
        are completed.
        """

        try:

            self.validate(
                step,
                plan,
            )

            return True


        except DependencyError:

            return False



    # =====================================================
    # Find Step
    # =====================================================

    def _find_step(
        self,
        step_id: int,
        plan: ExecutionPlan,
    ) -> PlanStep | None:
        """
        Find step by ID.
        """

        for step in plan.steps:

            if step.id == step_id:

                return step


        return None



    # =====================================================
    # Circular Dependency Check
    # =====================================================

    def has_cycle(
        self,
        plan: ExecutionPlan,
    ) -> bool:
        """
        Detect circular dependencies.
        """

        visited = set()

        stack = set()


        def visit(step_id: int) -> bool:

            if step_id in stack:

                return True


            if step_id in visited:

                return False


            visited.add(step_id)

            stack.add(step_id)


            step = self._find_step(
                step_id,
                plan,
            )


            if step:

                for dependency in step.depends_on:

                    if visit(dependency):

                        return True


            stack.remove(step_id)

            return False



        for step in plan.steps:

            if visit(step.id):

                return True


        return False



    # =====================================================
    # Ready Steps
    # =====================================================

    def get_ready_steps(
        self,
        plan: ExecutionPlan,
    ) -> list[PlanStep]:
        """
        Returns steps which are ready
        for execution.
        """

        ready = []


        for step in plan.steps:

            if step.is_finished:

                continue


            if self.dependencies_satisfied(
                step,
                plan,
            ):

                ready.append(step)


        return ready