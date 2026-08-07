"""
MYRAA Execution Report

Stores the complete outcome of a task execution.
This report is later consumed by:
- Reflection Engine
- Working Memory
- Analytics
- Retry Manager
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class StepReport:
    """
    Result of one execution step.
    """

    step_id: int
    tool: str

    status: str = "pending"

    started_at: datetime | None = None
    finished_at: datetime | None = None

    duration: float = 0.0

    verified: bool = False

    retries: int = 0

    success: bool = False

    message: str = ""

    error: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    """
    Final execution report produced after an execution completes.
    """

    task_id: str

    task: str

    status: str = "pending"

    created_at: datetime = field(default_factory=datetime.utcnow)

    started_at: datetime | None = None

    finished_at: datetime | None = None

    total_duration: float = 0.0

    success: bool = False

    verified: bool = False

    retry_count: int = 0

    recovery_used: bool = False

    recovery_strategy: str = ""

    error: str = ""

    summary: str = ""

    steps: list[StepReport] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    # ----------------------------------------------------------

    def add_step(self, report: StepReport) -> None:
        self.steps.append(report)

    # ----------------------------------------------------------

    @property
    def completed_steps(self) -> int:
        return sum(step.success for step in self.steps)

    # ----------------------------------------------------------

    @property
    def failed_steps(self) -> int:
        return len(self.steps) - self.completed_steps

    # ----------------------------------------------------------

    def mark_started(self) -> None:
        self.started_at = datetime.utcnow()
        self.status = "running"

    # ----------------------------------------------------------

    def mark_completed(self) -> None:
        self.finished_at = datetime.utcnow()

        if self.started_at:
            self.total_duration = (
                self.finished_at - self.started_at
            ).total_seconds()

        self.status = "completed"
        self.success = True

    # ----------------------------------------------------------

    def mark_failed(self, reason: str) -> None:

        self.finished_at = datetime.utcnow()

        if self.started_at:
            self.total_duration = (
                self.finished_at - self.started_at
            ).total_seconds()

        self.status = "failed"
        self.success = False
        self.error = reason

    # ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:

        return {
            "task_id": self.task_id,
            "task": self.task,
            "status": self.status,
            "success": self.success,
            "verified": self.verified,
            "retry_count": self.retry_count,
            "recovery_used": self.recovery_used,
            "recovery_strategy": self.recovery_strategy,
            "error": self.error,
            "summary": self.summary,
            "duration": self.total_duration,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "metadata": self.metadata,
            "steps": [
                {
                    "step_id": s.step_id,
                    "tool": s.tool,
                    "status": s.status,
                    "duration": s.duration,
                    "verified": s.verified,
                    "retries": s.retries,
                    "success": s.success,
                    "message": s.message,
                    "error": s.error,
                    "metadata": s.metadata,
                }
                for s in self.steps
            ],
        }

    # ----------------------------------------------------------

    def __str__(self) -> str:

        return (
            f"<ExecutionReport "
            f"task='{self.task}' "
            f"status='{self.status}' "
            f"success={self.success} "
            f"verified={self.verified}>"
        )       