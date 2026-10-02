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
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    UNVERIFIED = "unverified"


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

    # Priority levels: lower numbers = higher priority
    PRIORITY_HIGH = -10
    PRIORITY_NORMAL = 0
    PRIORITY_LOW = 10

    priority: int = PRIORITY_NORMAL

    def _get_priority_for_action(self) -> int:
        """Get appropriate priority level for this action type."""
        # High priority actions (safety, user interaction, critical system)
        high_priority_actions = {
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.RIGHT_CLICK,
            ActionType.TYPE_TEXT,
            ActionType.PRESS_KEY,
            ActionType.HOTKEY,
            ActionType.OPEN_APPLICATION,
            ActionType.CLOSE_APPLICATION,
            ActionType.ACTIVATE_WINDOW,
            ActionType.MINIMIZE_WINDOW,
            ActionType.MAXIMIZE_WINDOW,
            ActionType.RESTORE_WINDOW,
            ActionType.SWITCH_WINDOW,
            ActionType.OPEN_URL,
            ActionType.NEW_TAB,
            ActionType.CLOSE_TAB,
            ActionType.SWITCH_TAB,
            ActionType.REFRESH_PAGE,
            ActionType.OPEN_FILE,
            ActionType.READ_FILE,
            ActionType.WRITE_FILE,
            ActionType.DELETE_FILE,
            ActionType.MOVE_FILE,
            ActionType.COPY_FILE,
            ActionType.RENAME_FILE,
        }

        # Low priority actions (background, maintenance, non-urgent)
        low_priority_actions = {
            ActionType.LIST_FILES,
            ActionType.FILE_EXISTS,
            ActionType.COPY,
            ActionType.CUT,
            ActionType.PASTE,
            ActionType.UNDO,
            ActionType.REDO,
            ActionType.SELECT_ALL,
            ActionType.DELETE,
            ActionType.WAIT,
            ActionType.WAIT_FOR_ELEMENT,
            ActionType.WAIT_FOR_WINDOW,
            ActionType.WAIT_FOR_SCREEN_CHANGE,
            ActionType.FIND_ELEMENT,
            ActionType.VERIFY_ELEMENT,
            ActionType.VERIFY_SCREEN,
            ActionType.CAPTURE_SCREEN,
            ActionType.OCR_SCREEN,
        }

        if self.action in high_priority_actions:
            return self.PRIORITY_HIGH
        elif self.action in low_priority_actions:
            return self.PRIORITY_LOW
        else:
            return self.PRIORITY_NORMAL


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