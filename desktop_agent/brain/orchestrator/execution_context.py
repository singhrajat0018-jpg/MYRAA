"""
MYRAA Cognitive Engine
Execution Context
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .execution_state import ExecutionState
from ..planner.execution.execution_plan import ExecutionPlan


@dataclass(slots=True)
class ExecutionContext:
    """
    Shared runtime context used by the Orchestrator.
    """

    plan: ExecutionPlan

    state: ExecutionState = ExecutionState.PENDING

    current_step: int = 0

    variables: dict[str, Any] = field(default_factory=dict)

    shared_memory: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------

    @property
    def total_steps(self) -> int:

        return len(self.plan.steps)

    # --------------------------------------------------

    @property
    def has_next_step(self) -> bool:

        return self.current_step < self.total_steps

    # --------------------------------------------------

    def next_step(self):

        if self.has_next_step:

            step = self.plan.steps[self.current_step]

            self.current_step += 1

            return step

        return None

    # --------------------------------------------------

    def reset(self):

        self.current_step = 0

        self.state = ExecutionState.PENDING

        self.variables.clear()

        self.shared_memory.clear()