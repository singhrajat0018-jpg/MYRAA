"""
MYRAA Cognitive Engine
Progress Tracker
"""

from __future__ import annotations

from ..planner.execution.execution_plan import ExecutionPlan


class ProgressTracker:
    """
    Tracks execution progress.
    """

    def progress(
        self,
        plan: ExecutionPlan,
    ) -> float:

        total = len(plan.steps)

        if total == 0:
            return 0.0

        completed = sum(
            1
            for step in plan.steps
            if step.completed
        )

        return (completed / total) * 100.0

    # ---------------------------------------------------

    def completed_steps(
        self,
        plan: ExecutionPlan,
    ) -> int:

        return sum(
            1
            for step in plan.steps
            if step.completed
        )

    # ---------------------------------------------------

    def failed_steps(
        self,
        plan: ExecutionPlan,
    ) -> int:

        return sum(
            1
            for step in plan.steps
            if step.failed
        )

    # ---------------------------------------------------

    def remaining_steps(
        self,
        plan: ExecutionPlan,
    ) -> int:

        return sum(
            1
            for step in plan.steps
            if not step.completed
            and not step.failed
        )
    