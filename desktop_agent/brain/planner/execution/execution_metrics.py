"""
MYRAA Cognitive Engine

Execution Metrics
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionMetrics:
    """
    Collects execution statistics.
    """

    total_steps: int = 0

    retry_count: int = 0

    rollback_count: int = 0

    verification_success: int = 0

    verification_failure: int = 0

    completed_steps: int = 0

    failed_steps: int = 0

    verified_steps: int = 0

    retried_steps: int = 0

    total_execution_time: float = 0.0

    total_retry_time: float = 0.0

    started_at: float | None = None

    finished_at: float | None = None

    # ----------------------------------------------------
    def start(self) -> None:
        """
        Start execution metrics timer.
        """

        import time

        self.started_at = time.perf_counter()


    @property
    def success_rate(self) -> float:

        if self.total_steps == 0:

            return 0.0

        return self.completed_steps / self.total_steps

    # ----------------------------------------------------

    @property
    def failure_rate(self) -> float:

        if self.total_steps == 0:

            return 0.0

        return self.failed_steps / self.total_steps

    # ----------------------------------------------------

    @property
    def average_step_time(self) -> float:

        if self.completed_steps == 0:

            return 0.0

        return self.total_execution_time / self.completed_steps


    def record_rollback(
        self,
    ):
        """
        Record rollback event.
        """

        self.rollback_count = (
            getattr(
                self,
                "rollback_count",
                0
            )
            + 1
        )


    def reset(
        self,
    ) -> None:
        """
        Reset execution metrics.
        """

        self.total_steps = 0

        self.completed_steps = 0

        self.failed_steps = 0

        self.retry_count = 0

        self.rollback_count = 0

        self.verification_success = 0

        self.verification_failure = 0

        self.total_execution_time = 0.0


    def finish(self) -> None:
        """
        Mark execution finished.
        """

        import time

        self.finished_at = time.perf_counter()


        if self.started_at is not None:

            self.total_execution_time = (
                self.finished_at
                -
                self.started_at
            )


    def record_retry(
        self,
        step=None,
    ) -> None:

        self.retry_count += 1


    def record_success(
        self,
        step=None,
        result=None,
    ) -> None:

        self.completed_steps += 1


    def record_failure(
        self,
        step=None,
        error=None,
    ) -> None:

        self.failed_steps += 1


    def record_rollback(self) -> None:

        self.rollback_count += 1


    def record_verification_success(
        self,
    ) -> None:
        """
        Record successful verification.
        """

        self.verification_success += 1



    def record_verification_failure(
        self,
    ) -> None:
        """
        Record failed verification.
        """

        self.verification_failure += 1