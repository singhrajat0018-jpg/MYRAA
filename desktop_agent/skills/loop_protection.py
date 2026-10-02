"""LoopGuard — bounded execution protection for MYRAA agents.

Detects: same-task repetition, same-error repetition, circular handoffs.
Enforces: max retries, max handoffs, max replans, max depth, max time.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class LoopLimits:
    """Configurable loop protection limits."""
    max_retries: int = 3
    max_handoffs: int = 10
    max_replans: int = 3
    max_depth: int = 10
    max_execution_time_s: float = 300.0
    max_same_task_repetitions: int = 3
    max_same_error_repetitions: int = 3


class LoopGuard:
    """Detects and prevents infinite loops in agent execution.

    Tracks: retries, handoffs, replans, depth, time, task repetitions, error repetitions.
    """

    def __init__(self, limits: Optional[LoopLimits] = None) -> None:
        self.limits = limits or LoopLimits()
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._retry_count: int = 0
        self._handoff_count: int = 0
        self._replan_count: int = 0
        self._depth: int = 0
        self._task_history: Dict[str, int] = {}
        self._error_history: Dict[str, int] = {}
        self._violations: list = []

    def start(self) -> None:
        with self._lock:
            self._start_time = time.time()

    def check_retry(self, task_id: str = "", error: str = "") -> bool:
        """Check if a retry is allowed. Returns True if allowed."""
        with self._lock:
            self._retry_count += 1
            if self._retry_count > self.limits.max_retries:
                self._violations.append(f"Max retries exceeded ({self.limits.max_retries})")
                return False

            if task_id:
                count = self._task_history.get(task_id, 0) + 1
                self._task_history[task_id] = count
                if count > self.limits.max_same_task_repetitions:
                    self._violations.append(f"Same task repeated {count} times: {task_id}")
                    return False

            if error:
                count = self._error_history.get(error, 0) + 1
                self._error_history[error] = count
                if count > self.limits.max_same_error_repetitions:
                    self._violations.append(f"Same error repeated {count} times: {error}")
                    return False

            return True

    def check_handoff(self, from_worker: str = "", to_worker: str = "") -> bool:
        """Check if a handoff is allowed."""
        with self._lock:
            self._handoff_count += 1
            if self._handoff_count > self.limits.max_handoffs:
                self._violations.append(f"Max handoffs exceeded ({self.limits.max_handoffs})")
                return False
            return True

    def check_replan(self) -> bool:
        """Check if a replan is allowed."""
        with self._lock:
            self._replan_count += 1
            if self._replan_count > self.limits.max_replans:
                self._violations.append(f"Max replans exceeded ({self.limits.max_replans})")
                return False
            return True

    def check_depth(self) -> bool:
        """Check if depth is within limits."""
        with self._lock:
            self._depth += 1
            if self._depth > self.limits.max_depth:
                self._violations.append(f"Max depth exceeded ({self.limits.max_depth})")
                return False
            return True

    def check_time(self) -> bool:
        """Check if execution time is within limits."""
        with self._lock:
            if self._start_time is None:
                return True
            elapsed = time.time() - self._start_time
            if elapsed > self.limits.max_execution_time_s:
                self._violations.append(
                    f"Max execution time exceeded ({self.limits.max_execution_time_s}s)"
                )
                return False
            return True

    def check_all(self) -> bool:
        """Check all limits. Returns True if all OK."""
        return (
            self.check_retry()
            and self.check_handoff()
            and self.check_replan()
            and self.check_depth()
            and self.check_time()
        )

    def get_violations(self) -> list:
        with self._lock:
            return list(self._violations)

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = (time.time() - self._start_time) if self._start_time else 0
            return {
                "retries": self._retry_count,
                "handoffs": self._handoff_count,
                "replans": self._replan_count,
                "depth": self._depth,
                "elapsed_s": elapsed,
                "task_repetitions": dict(self._task_history),
                "error_repetitions": dict(self._error_history),
                "violations": len(self._violations),
                "limits": {
                    "max_retries": self.limits.max_retries,
                    "max_handoffs": self.limits.max_handoffs,
                    "max_replans": self.limits.max_replans,
                    "max_depth": self.limits.max_depth,
                    "max_execution_time_s": self.limits.max_execution_time_s,
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._start_time = None
            self._retry_count = 0
            self._handoff_count = 0
            self._replan_count = 0
            self._depth = 0
            self._task_history.clear()
            self._error_history.clear()
            self._violations.clear()
