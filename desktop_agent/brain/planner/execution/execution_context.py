"""
MYRAA Cognitive Engine

Execution Context
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ExecutionContext:
    """
    Runtime context shared during execution.
    """

    plan: ExecutionPlan | None = None

    total_steps: int = 0

    current_step: int = 0

    execution_id: str = ""

    current_step: int = 0

    total_steps: int = 0

    active_window: str = ""

    active_application: str = ""

    cancelled: bool = False

    started_at: datetime = field(default_factory=datetime.utcnow)

    variables: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    # ----------------------------------------------------

    @property
    def progress(self) -> float:

        if self.total_steps == 0:

            return 0.0

        return self.current_step / self.total_steps

    # ----------------------------------------------------

    def set_variable(

        self,

        name: str,

        value: Any,

    ) -> None:

        self.variables[name] = value

    # ----------------------------------------------------

    def get_variable(

        self,

        name: str,

        default: Any = None,

    ) -> Any:

        return self.variables.get(name, default)