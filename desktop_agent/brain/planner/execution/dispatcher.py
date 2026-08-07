"""
MYRAA Cognitive Engine

Action Dispatcher

Routes PlanStep execution to
registered action handlers.
"""

from __future__ import annotations

import time

from typing import Any

from .action_registry import ActionRegistry
from .execution_result import ExecutionResult

from ..models.plan_step import PlanStep



class Dispatcher:
    """
    Executes actions through ActionRegistry.
    """

    def __init__(
        self,
        registry: ActionRegistry,
    ) -> None:

        self.registry = registry



    # =====================================================
    # Dispatch
    # =====================================================

    async def dispatch(
        self,
        step: PlanStep,
    ) -> ExecutionResult:
        """
        Execute a PlanStep.
        """

        started = time.perf_counter()


        try:

            handler = self.registry.resolve(
                step.action
            )


            result = await self._execute_handler(
                handler,
                step.parameters,
            )


            duration = (
                time.perf_counter()
                -
                started
            )


            return ExecutionResult(

                success=True,

                value=result,

                duration=duration,

                metadata={

                    "action": step.action.value,

                    "step_id": step.id,

                },

            )


        except Exception as exc:


            duration = (
                time.perf_counter()
                -
                started
            )


            return ExecutionResult(

                success=False,

                duration=duration,

                exception=exc,

                error_message=str(exc),

                metadata={

                    "action": step.action.value,

                    "step_id": step.id,

                },

            )



    # =====================================================
    # Handler Execution
    # =====================================================

    async def _execute_handler(
        self,
        handler,
        parameters: dict[str, Any],
    ):
        """
        Supports async and sync handlers.
        """

        result = handler(
            **parameters
        )


        if hasattr(
            result,
            "__await__"
        ):

            return await result


        return result



    # =====================================================
    # Validation
    # =====================================================

    def can_execute(
        self,
        step: PlanStep,
    ) -> bool:
        """
        Check action availability.
        """

        return self.registry.exists(
            step.action
        )