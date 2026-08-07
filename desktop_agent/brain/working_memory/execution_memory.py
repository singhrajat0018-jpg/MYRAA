from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExecutionRecord:

    title: str

    success: bool

    execution_time: float


@dataclass(slots=True)
class ExecutionMemory:

    last_execution: ExecutionRecord | None = None

    recent_executions: list[ExecutionRecord] = field(
        default_factory=list
    )

    success_count: int = 0

    failure_count: int = 0