"""
MYRAA Cognitive Engine
Execution Result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .execution_state import ExecutionState


@dataclass(slots=True)
class ExecutionResult:
    """
    Final result returned by the Orchestrator.
    """

    success: bool = True

    state: ExecutionState = ExecutionState.COMPLETED

    completed_steps: int = 0

    failed_step: int | None = None

    total_steps: int = 0

    elapsed_time: float = 0.0

    errors: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------
    # Execution Details
    # ---------------------------------------------

    last_action: str = ""

    last_tool: str = ""

    last_message: str = ""

    # The actual tool-handler output (dict / text / structured data), when the
    # dispatcher produced one. Preserved so /execute callers and the Node bridge
    # can report exactly what happened, not just that a step completed.
    result: Any = None
    # ---------------------------------------------

    @property
    def progress(self) -> float:

        if self.total_steps == 0:
            return 0.0

        return (
            self.completed_steps
            / self.total_steps
        ) * 100.0

    # ---------------------------------------------

    def add_error(
        self,
        message: str,
    ) -> None:

        self.errors.append(message)

        self.success = False

        self.state = ExecutionState.FAILED