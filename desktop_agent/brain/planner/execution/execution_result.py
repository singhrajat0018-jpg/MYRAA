"""
MYRAA Cognitive Engine

Execution Result Model

Represents result of execution
from ExecutorBridge pipeline.
"""

from __future__ import annotations


from dataclasses import dataclass, field

from datetime import datetime

from typing import Any



@dataclass(slots=True)
class ExecutionResult:
    """
    Result produced after execution.

    Used by:
    - Dispatcher
    - ExecutorBridge
    - Verification
    - History
    - Metrics
    """


    # ==================================================
    # Status
    # ==================================================

    success: bool = False


    verified: bool = False



    # ==================================================
    # Step Statistics
    # ==================================================

    completed_steps: int = 0


    failed_steps: int = 0



    # ==================================================
    # Timing
    # ==================================================

    execution_time: float = 0.0


    duration: float = 0.0


    started_at: datetime | None = None


    finished_at: datetime | None = None



    # ==================================================
    # Retry
    # ==================================================

    retry_count: int = 0


    max_retries: int = 0



    # ==================================================
    # Error Handling
    # ==================================================

    error_message: str | None = None


    exception: Exception | None = None



    # ==================================================
    # Output Data
    # ==================================================

    value: Any = None


    metadata: dict[str, Any] = field(
        default_factory=dict
    )



    # ==================================================
    # Compatibility Aliases
    # ==================================================

    @property
    def error(self) -> str | None:
        """
        Backward compatibility.
        """

        return self.error_message



    # ==================================================
    # Status Helpers
    # ==================================================

    @property
    def failed(self) -> bool:
        """
        Returns True when execution failed.
        """

        return not self.success



    @property
    def has_exception(self) -> bool:
        """
        Check exception existence.
        """

        return self.exception is not None



    @property
    def is_verified(self) -> bool:
        """
        Verification status.
        """

        return self.verified



    # ==================================================
    # Factory Helpers
    # ==================================================

    @classmethod
    def success_result(
        cls,
        value: Any = None,
        **kwargs,
    ) -> "ExecutionResult":

        return cls(

            success=True,

            value=value,

            verified=True,

            **kwargs,

        )



    @classmethod
    def failure_result(
        cls,
        error: str,
        exception: Exception | None = None,
        **kwargs,
    ) -> "ExecutionResult":

        return cls(

            success=False,

            error_message=error,

            exception=exception,

            **kwargs,

        )



    # ==================================================
    # Representation
    # ==================================================

    def summary(self) -> dict[str, Any]:

        return {

            "success": self.success,

            "verified": self.verified,

            "completed_steps":
                self.completed_steps,

            "failed_steps":
                self.failed_steps,

            "duration":
                self.duration,

            "error":
                self.error_message,

        }