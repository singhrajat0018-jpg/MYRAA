"""
MYRAA Cognitive Engine

Retry Manager
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetryDecision:
    retry: bool
    reason: str
    delay_ms: int = 0


class RetryManager:

    def __init__(
        self,
        max_attempts: int = 2,
    ) -> None:

        self.max_attempts = max_attempts

    def evaluate(
        self,
        *,
        success: bool,
        attempt: int,
        error: str | None = None,
    ) -> RetryDecision:

        if success:
            return RetryDecision(
                retry=False,
                reason="Execution successful.",
            )

        if attempt >= self.max_attempts:
            return RetryDecision(
                retry=False,
                reason="Maximum retry attempts reached.",
            )

        return RetryDecision(
            retry=True,
            reason="Retry permitted.",
            delay_ms=500,
        )