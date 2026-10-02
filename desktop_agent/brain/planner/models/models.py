"""
MYRAA Cognitive Engine

Shared Planner Models
"""

from __future__ import annotations

import time
from typing import Optional

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..execution.execution_plan import ExecutionPlan


# ==========================================================
# Planner Goal
# ==========================================================

@dataclass(slots=True)
class PlannerGoal:
    """
    High-level goal received by the planner.
    """

    text: str

    confidence: float = 1.0


    parameters: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Planner Context
# ==========================================================

@dataclass(slots=True)
class PlannerContext:
    """
    Runtime information used during planning.
    """

    active_application: str = ""

    active_window: str = ""

    screen_summary: str = ""

    screen_resolution: tuple[int, int] | None = None

    cursor_position: tuple[int, int] | None = None

    selected_text: str = ""

    clipboard: str = ""
    task_deadline: Optional[float] = None  # Absolute deadline timestamp (time.time())
    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Planner Result Status
# ==========================================================

class PlannerResultStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


# ==========================================================
# Planner Result
# ==========================================================

@dataclass(slots=True)
class PlannerResult:
    """
    Result produced by the planner.
    """

    status: PlannerResultStatus

    plan: ExecutionPlan | None = None

    message: str = ""

    confidence: float = 1.0

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Execution Result
# ==========================================================

@dataclass(slots=True)
class ExecutionResult:
    """
    Result returned after executing a plan.
    """

    success: bool

    completed_steps: int = 0

    failed_steps: int = 0

    execution_time: float = 0.0

    error: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Planner Statistics
# ==========================================================

@dataclass(slots=True)
class PlannerStatistics:
    """
    Planner performance metrics.
    """

    total_plans: int = 0

    successful_plans: int = 0

    failed_plans: int = 0

    total_execution_time: float = 0.0

    average_execution_time: float = 0.0

    last_execution: float = field(default_factory=time.time)

    metadata: dict[str, Any] = field(default_factory=dict)