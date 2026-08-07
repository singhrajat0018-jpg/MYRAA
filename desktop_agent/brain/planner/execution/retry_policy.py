"""
MYRAA Cognitive Engine

Retry Policy
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


# ==========================================================
# Retry Strategy
# ==========================================================

class RetryStrategy(str, Enum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


# ==========================================================
# Retry Result
# ==========================================================

@dataclass(slots=True)
class RetryResult:

    success: bool

    attempts: int

    exception: Exception | None = None

    value: Any = None


# ==========================================================
# Retry Policy
# ==========================================================

@dataclass(slots=True)
class RetryPolicy:

    max_attempts: int = 3

    initial_delay: float = 0.25

    backoff_factor: float = 2.0

    max_delay: float = 5.0

    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL

    retry_on: tuple[type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )

    # ------------------------------------------------------

    async def execute(

        self,

        operation: Callable[..., Awaitable[Any]],

        *args,

        **kwargs,

    ) -> RetryResult:

        delay = self.initial_delay

        last_exception: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):

            try:

                value = await operation(*args, **kwargs)

                return RetryResult(

                    success=True,

                    attempts=attempt,

                    value=value,

                )

            except self.retry_on as exc:

                last_exception = exc

                if attempt >= self.max_attempts:

                    break

                await asyncio.sleep(delay)

                delay = self._next_delay(delay)

        return RetryResult(

            success=False,

            attempts=self.max_attempts,

            exception=last_exception,

        )

    # ------------------------------------------------------

    def _next_delay(

        self,

        current_delay: float,

    ) -> float:

        if self.strategy == RetryStrategy.NONE:

            return 0.0

        if self.strategy == RetryStrategy.FIXED:

            return self.initial_delay

        delay = current_delay * self.backoff_factor

        return min(delay, self.max_delay)



    def should_retry(
        self,
        attempt,
        error: Exception | None = None,
    ) -> bool:
        """
        Decide whether execution should retry.

        Supports PlanStep input from ExecutorBridge.
        """

        # ExecutorBridge passes PlanStep
        if hasattr(attempt, "retries"):

            return attempt.retries < self.max_attempts


        # Normal integer attempt
        return attempt < self.max_attempts