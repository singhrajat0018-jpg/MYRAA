"""
MYRAA Execution Monitor

Tracks every running task inside the Brain.

Responsibilities
----------------
• Register execution
• Track live state
• Update progress
• Finish execution
• Fail execution
• Cancel execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, Optional

from .execution_report import ExecutionReport


# ============================================================
# Execution States
# ============================================================

PENDING = "pending"
RUNNING = "running"
VERIFYING = "verifying"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"
RETRYING = "retrying"


# ============================================================
# Runtime Execution
# ============================================================

@dataclass(slots=True)
class ExecutionState:

    report: ExecutionReport

    progress: float = 0.0

    current_step: int = 0

    total_steps: int = 0

    state: str = PENDING

    created_at: datetime = field(default_factory=datetime.utcnow)

    updated_at: datetime = field(default_factory=datetime.utcnow)

    def touch(self):

        self.updated_at = datetime.utcnow()


# ============================================================
# Execution Monitor
# ============================================================

class ExecutionMonitor:

    """
    Tracks every execution currently known to MYRAA.
    """

    def __init__(self):

        self._executions: Dict[str, ExecutionState] = {}

        self._lock = Lock()

    # --------------------------------------------------------

    def register(self, report: ExecutionReport):

        state = ExecutionState(report=report)

        with self._lock:
            self._executions[report.task_id] = state

        return state

    # --------------------------------------------------------

    def get(self, task_id: str) -> Optional[ExecutionState]:

        return self._executions.get(task_id)

    # --------------------------------------------------------

    def exists(self, task_id: str) -> bool:

        return task_id in self._executions

    # --------------------------------------------------------

    def start(self, task_id: str):

        state = self.get(task_id)

        if state is None:
            return

        state.state = RUNNING

        state.report.mark_started()

        state.touch()

    # --------------------------------------------------------

    def set_total_steps(self, task_id: str, total_steps: int):

        state = self.get(task_id)

        if state is None:
            return

        state.total_steps = max(1, total_steps)

        state.touch()

    # --------------------------------------------------------

    def update_step(self, task_id: str, step_number: int):

        state = self.get(task_id)

        if state is None:
            return

        state.current_step = step_number

        if state.total_steps:

            state.progress = (
                step_number / state.total_steps
            ) * 100

        state.touch()

    # --------------------------------------------------------

    def verifying(self, task_id: str):

        state = self.get(task_id)

        if state is None:
            return

        state.state = VERIFYING

        state.touch()

    # --------------------------------------------------------

    def retrying(self, task_id: str):

        state = self.get(task_id)

        if state is None:
            return

        state.state = RETRYING

        state.report.retry_count += 1

        state.touch()

    # --------------------------------------------------------

    def complete(self, task_id: str):

        state = self.get(task_id)

        if state is None:
            return

        state.state = COMPLETED

        state.progress = 100

        state.report.mark_completed()

        state.touch()

    # --------------------------------------------------------

    def fail(self, task_id: str, reason: str):

        state = self.get(task_id)

        if state is None:
            return

        state.state = FAILED

        state.report.mark_failed(reason)

        state.touch()

    # --------------------------------------------------------

    def cancel(self, task_id: str):

        state = self.get(task_id)

        if state is None:
            return

        state.state = CANCELLED

        state.report.status = CANCELLED

        state.touch()

    # --------------------------------------------------------

    def remove(self, task_id: str):

        with self._lock:

            self._executions.pop(task_id, None)

    # --------------------------------------------------------

    def active(self):

        return list(self._executions.values())

    # --------------------------------------------------------

    def snapshot(self):

        return {
            task_id: {
                "state": state.state,
                "progress": state.progress,
                "current_step": state.current_step,
                "total_steps": state.total_steps,
            }
            for task_id, state in self._executions.items()
        }

    # --------------------------------------------------------

    def clear_finished(self):

        remove = []

        for task_id, state in self._executions.items():

            if state.state in (
                COMPLETED,
                FAILED,
                CANCELLED,
            ):
                remove.append(task_id)

        for task_id in remove:
            self.remove(task_id)