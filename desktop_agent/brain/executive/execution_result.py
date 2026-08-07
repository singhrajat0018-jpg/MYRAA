from __future__ import annotations

from dataclasses import dataclass


from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionResult:

    success: bool

    plan_title: str

    completed_steps: int

    total_steps: int

    failed_step: int | None = None

    reason: str = ""

    execution_time: float = 0.0