"""
MYRAA Cognitive Engine

Execution Queue

Manages execution order of PlanSteps.
"""

from __future__ import annotations

from collections import deque

from ..models.plan_step import PlanStep

from .execution_plan import ExecutionPlan

from .dependency_resolver import DependencyResolver



class ExecutionQueue:
    """
    Queue manager for execution steps.
    """

    def __init__(
        self,
        dependency_resolver: DependencyResolver,
    ) -> None:

        self.resolver = dependency_resolver

        self._queue: deque[PlanStep] = deque()

        self._completed: set[int] = set()



    # =====================================================
    # Load Plan
    # =====================================================

    def load(
        self,
        plan: ExecutionPlan,
    ) -> None:
        """
        Load execution plan into queue.
        """

        self.clear()

        ready_steps = self.resolver.get_ready_steps(
            plan
        )

        for step in ready_steps:

            self._queue.append(step)



    # =====================================================
    # Add Step
    # =====================================================

    def add(
        self,
        step: PlanStep,
    ) -> None:
        """
        Add new step.
        """

        self._queue.append(step)



    # =====================================================
    # Next Step
    # =====================================================

    def next(
        self,
    ) -> PlanStep | None:
        """
        Get next executable step.
        """

        if not self._queue:

            return None


        return self._queue.popleft()



    # =====================================================
    # Refresh Queue
    # =====================================================

    def refresh(
        self,
        plan: ExecutionPlan,
    ) -> None:
        """
        Recalculate available steps.
        """

        ready_steps = self.resolver.get_ready_steps(
            plan
        )


        for step in ready_steps:

            if step.id not in self._completed:

                if step not in self._queue:

                    self._queue.append(step)



    # =====================================================
    # Mark Complete
    # =====================================================

    def mark_completed(
        self,
        step: PlanStep,
    ) -> None:
        """
        Mark step completed.
        """

        self._completed.add(
            step.id
        )



    # =====================================================
    # Status
    # =====================================================

    def has_next(
        self,
    ) -> bool:

        return len(
            self._queue
        ) > 0



    def size(
        self,
    ) -> int:

        return len(
            self._queue
        )



    # =====================================================
    # Clear
    # =====================================================

    def clear(
        self,
    ) -> None:

        self._queue.clear()

        self._completed.clear()



    # =====================================================
    # Pending Steps
    # =====================================================

    def pending_ids(
        self,
    ) -> list[int]:

        return [

            step.id

            for step in self._queue

        ]