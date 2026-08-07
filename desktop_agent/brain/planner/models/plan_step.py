"""
MYRAA Cognitive Engine
Plan Step
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from .action_types import ActionType


class StepStatus(str,Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class PlanStep:
    """
    Represents one executable step.
    """

    # =====================================================
    # Identity
    # =====================================================

    id: int

    name: str

    action: ActionType

    description: str = ""

    # =====================================================
    # Parameters
    # =====================================================

    parameters: dict[str, Any] = field(default_factory=dict)

    # =====================================================
    # Dependencies
    # =====================================================

    depends_on: list[int] = field(default_factory=list)

    optional: bool = False

    # =====================================================
    # Execution
    # =====================================================
    status: StepStatus = StepStatus.PENDING

    @property
    def completed(self) -> bool:
        return self.status == StepStatus.COMPLETED

    @property
    def failed(self) -> bool:
        return self.status == StepStatus.FAILED

    @property
    def running(self) -> bool:
        return self.status == StepStatus.RUNNING

    @property
    def skipped(self) -> bool:
        return self.status == StepStatus.SKIPPED


    # =====================================================
    # Verification
    # =====================================================

    requires_verification: bool = True

    verified: bool = False

    expected_result: str = ""

    actual_result: str = ""

    # =====================================================
    # Scheduling
    # =====================================================

    priority: int = 100


    # =====================================================
    # Retry
    # =====================================================

    retries: int = 0

    max_retries: int = 3

    # =====================================================
    # Timing
    # =====================================================

    timeout: float = 30.0

    started_at: float | None = None

    finished_at: float | None = None

    execution_time: float = 0.0

    # =====================================================
    # Rollback
    # =====================================================

    rollback_action: ActionType | None = None

    rollback_parameters: dict[str, Any] = field(default_factory=dict)

    # =====================================================
    # Parallel
    # =====================================================

    parallel_group: int | None = None

    # =====================================================
    # Metadata
    # =====================================================

    metadata: dict[str, Any] = field(default_factory=dict)

    error: str | None = None

    # =====================================================
    # Lifecycle
    # =====================================================

    def start(self) -> None:
        self.status = StepStatus.RUNNING
        self.started_at = time.perf_counter()  

         
    def complete(self) -> None:
        self.status = StepStatus.COMPLETED
        self.finished_at = time.perf_counter()

        if self.started_at is not None:
            self.execution_time = self.finished_at - self.started_at

    def fail(self, message: str) -> None:
        self.status = StepStatus.FAILED
        self.error = message
        self.finished_at = time.perf_counter()

        if self.started_at is not None:
            self.execution_time = self.finished_at - self.started_at

    def retry(self) -> None:
        self.retries += 1
        self.status = StepStatus.PENDING
        self.error = None
        self.started_at = None
        self.finished_at = None
        self.execution_time = 0.0

    def skip(self) -> None:
        self.status = StepStatus.SKIPPED

    @property
    def can_retry(self) -> bool:

        return self.retries < self.max_retries

    @property
    def is_finished(self) -> bool:

        return (
            self.completed
            or self.failed
            or self.skipped
        )

    @property
    def duration(self) -> float:

        return self.execution_time

    def reset(self) -> None:
        self.status = StepStatus.PENDING
        self.retries = 0
        self.error = None
        self.started_at = None
        self.finished_at = None
        self.execution_time = 0.0   