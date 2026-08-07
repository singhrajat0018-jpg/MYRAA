"""
MYRAA Cognitive Engine
Execution State
"""

from __future__ import annotations

from enum import Enum


class ExecutionState(str, Enum):
    """
    Current execution state.
    """

    PENDING = "pending"

    RUNNING = "running"

    COMPLETED = "completed"

    FAILED = "failed"

    SKIPPED = "skipped"

    WAITING = "waiting"

    CANCELLED = "cancelled"

    @property
    def is_finished(self) -> bool:
        return self in (
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.SKIPPED,
            ExecutionState.CANCELLED,
        )

    @property
    def is_active(self) -> bool:
        return self == ExecutionState.RUNNING