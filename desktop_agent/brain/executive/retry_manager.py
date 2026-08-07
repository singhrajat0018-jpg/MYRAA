"""
MYRAA Retry Manager

Automatically retries failed executions.

Responsibilities
----------------
• Retry failed tasks
• Limit retry attempts
• Progressive delay
• Maintain retry history
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================
# Retry Record
# ============================================================

@dataclass(slots=True)
class RetryRecord:

    attempts: int = 0

    last_attempt: datetime | None = None

    last_error: str = ""

    successful: bool = False

    history: list[str] = field(default_factory=list)


# ============================================================
# Retry Manager
# ============================================================

class RetryManager:

    """
    Controls automatic retries after a failed execution.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):

        self.max_retries = max_retries

        self.base_delay = base_delay

        self.records: dict[str, RetryRecord] = {}

    # --------------------------------------------------------

    def get_record(self, task_id: str) -> RetryRecord:

        if task_id not in self.records:

            self.records[task_id] = RetryRecord()

        return self.records[task_id]

    # --------------------------------------------------------

    def can_retry(self, task_id: str) -> bool:

        record = self.get_record(task_id)

        return record.attempts < self.max_retries

    # --------------------------------------------------------

    def next_delay(self, task_id: str) -> float:

        record = self.get_record(task_id)

        # Exponential Backoff
        return self.base_delay * (2 ** record.attempts)

    # --------------------------------------------------------

    def register_failure(
        self,
        task_id: str,
        error: str,
    ):

        record = self.get_record(task_id)

        record.attempts += 1

        record.last_attempt = datetime.utcnow()

        record.last_error = error

        record.history.append(error)

    # --------------------------------------------------------

    def register_success(self, task_id: str):

        record = self.get_record(task_id)

        record.successful = True

        record.last_attempt = datetime.utcnow()

    # --------------------------------------------------------

    def wait_before_retry(self, task_id: str):

        delay = self.next_delay(task_id)

        time.sleep(delay)

    # --------------------------------------------------------

    def reset(self, task_id: str):

        self.records.pop(task_id, None)

    # --------------------------------------------------------

    def summary(self, task_id: str):

        record = self.get_record(task_id)

        return {
            "attempts": record.attempts,
            "successful": record.successful,
            "last_error": record.last_error,
            "history": record.history,
        }

    # --------------------------------------------------------

    def execute_with_retry(
        self,
        task_id: str,
        callback,
        *args,
        **kwargs,
    ):
        """
        Executes callback until success
        or retry limit reached.
        """

        while True:

            try:

                result = callback(*args, **kwargs)

                self.register_success(task_id)

                return result

            except Exception as e:

                self.register_failure(
                    task_id,
                    str(e),
                )

                if not self.can_retry(task_id):

                    raise

                self.wait_before_retry(task_id)