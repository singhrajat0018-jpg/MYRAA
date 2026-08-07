"""
MYRAA Cognitive Engine

Execution History

Stores execution records for
debugging, analytics and learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .execution_result import ExecutionResult

from ..models.plan_step import PlanStep



# ==========================================================
# History Entry
# ==========================================================

@dataclass(slots=True)
class HistoryEntry:
    """
    Single execution history record.
    """

    step_id: int

    action: str

    success: bool

    verified: bool

    duration: float

    retry_count: int = 0

    error: str | None = None

    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )



# ==========================================================
# Execution History
# ==========================================================

class ExecutionHistory:
    """
    Stores execution history.
    """

    def __init__(
        self,
    ) -> None:

        self._records: list[
            HistoryEntry
        ] = []



    # =====================================================
    # Record Result
    # =====================================================

    def record(
        self,
        step: PlanStep,
        result: ExecutionResult,
    ) -> HistoryEntry:
        """
        Store execution result.
        """

        entry = HistoryEntry(

            step_id=step.id,

            action=step.action.value,

            success=result.success,

            verified=result.verified,

            duration=result.duration,

            retry_count=result.retry_count,

            error=result.error_message,

            metadata=result.metadata,

        )


        self._records.append(
            entry
        )


        return entry



    # =====================================================
    # Success Record
    # =====================================================

    def record_success(
        self,
        step: PlanStep,
        result: ExecutionResult,
    ) -> HistoryEntry:

        return self.record(
            step,
            result,
        )



    # =====================================================
    # Failure Record
    # =====================================================

    def record_failure(
        self,
        step: PlanStep,
        result: ExecutionResult,
    ) -> HistoryEntry:

        return self.record(
            step,
            result,
        )



    # =====================================================
    # Latest
    # =====================================================

    @property
    def last_result(
        self,
    ) -> HistoryEntry | None:

        if not self._records:

            return None


        return self._records[-1]



    # =====================================================
    # All Records
    # =====================================================

    def all(
        self,
    ) -> list[HistoryEntry]:

        return list(
            self._records
        )



    # =====================================================
    # Clear
    # =====================================================

    def clear(
        self,
    ) -> None:

        self._records.clear()



    # =====================================================
    # Stats
    # =====================================================

    def count(
        self,
    ) -> int:

        return len(
            self._records
        )


    def successful_count(
        self,
    ) -> int:

        return sum(

            1

            for record in self._records

            if record.success

        )


    def failed_count(
        self,
    ) -> int:

        return sum(

            1

            for record in self._records

            if not record.success

        )