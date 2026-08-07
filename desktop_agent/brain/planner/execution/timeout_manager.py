"""
MYRAA Cognitive Engine

Timeout Manager

Controls execution time limits
for PlanSteps.
"""

from __future__ import annotations

import asyncio

from typing import Any, Awaitable, Callable

from .exceptions import ExecutionTimeoutError

from ..models.plan_step import PlanStep



class TimeoutManager:
    """
    Handles timeout control for executions.
    """

    def __init__(
        self,
        default_timeout: float = 30.0,
    ) -> None:

        self.default_timeout = default_timeout



    # =====================================================
    # Get Timeout
    # =====================================================

    def get_timeout(
        self,
        step: PlanStep,
    ) -> float:
        """
        Returns timeout value for a step.
        """

        if step.timeout:

            return step.timeout


        return self.default_timeout



    # =====================================================
    # Execute With Timeout
    # =====================================================

    async def run(
        self,
        timeout: float,
        operation: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute async operation with timeout.
        """

        try:

            return await asyncio.wait_for(

                operation(
                    *args,
                    **kwargs,
                ),

                timeout=timeout,

            )


        except asyncio.TimeoutError:

            raise ExecutionTimeoutError(
                timeout
            )



    # =====================================================
    # Step Execution Wrapper
    # =====================================================

    async def execute_step(
        self,
        step: PlanStep,
        operation: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute a step using its timeout.
        """

        timeout = self.get_timeout(
            step
        )


        return await self.run(

            timeout,

            operation,

            *args,

            **kwargs,

        )



    # =====================================================
    # Validation
    # =====================================================

    def is_valid_timeout(
        self,
        timeout: float,
    ) -> bool:
        """
        Validate timeout value.
        """

        return timeout > 0