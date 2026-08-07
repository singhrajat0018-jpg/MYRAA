"""
MYRAA Cognitive Engine

Rollback Manager

Handles recovery actions after
execution failures.
"""

from __future__ import annotations

from typing import Any

from .execution_plan import ExecutionPlan

from .execution_result import ExecutionResult

from .exceptions import RollbackError

from ..models.plan_step import PlanStep



class RollbackManager:
    """
    Manages rollback of completed execution steps.
    """

    def __init__(
        self,
    ) -> None:

        self.rollback_history: list[
            PlanStep
        ] = []



    # =====================================================
    # Register Completed Step
    # =====================================================

    def register(
        self,
        step: PlanStep,
    ) -> None:
        """
        Store completed step for rollback.
        """

        if step.rollback_action:

            self.rollback_history.append(
                step
            )



    # =====================================================
    # Rollback Plan
    # =====================================================

    async def rollback(
        self,
        plan: ExecutionPlan,
    ) -> None:
        """
        Execute rollback operations.
        """

        failed_steps = list(
            reversed(
                self.rollback_history
            )
        )


        for step in failed_steps:

            try:

                await self._rollback_step(
                    step
                )


            except Exception as exc:

                raise RollbackError(
                    f"Rollback failed for step "
                    f"{step.id}: {exc}"
                )



    # =====================================================
    # Single Step Rollback
    # =====================================================

    async def _rollback_step(
        self,
        step: PlanStep,
    ) -> Any:
        """
        Execute rollback action.

        Actual dispatcher integration
        will be connected later.
        """

        if not step.rollback_action:

            return None


        # Placeholder hook:
        #
        # ExecutorBridge will connect
        # rollback_action with Dispatcher.
        #

        return True



    # =====================================================
    # Clear
    # =====================================================

    def clear(
        self,
    ) -> None:

        self.rollback_history.clear()



    # =====================================================
    # Status
    # =====================================================

    def has_actions(
        self,
    ) -> bool:

        return len(
            self.rollback_history
        ) > 0



    def count(
        self,
    ) -> int:

        return len(
            self.rollback_history
        )