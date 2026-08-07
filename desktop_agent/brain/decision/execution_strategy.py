"""
MYRAA Cognitive Engine
Execution Strategy
"""

from __future__ import annotations

from enum import Enum


class ExecutionStrategy(str, Enum):
    """
    Defines how the Decision Engine should execute a task.
    """

    # Execute immediately
    DIRECT = "direct"

    # Ask user for confirmation
    CONFIRM = "confirm"

    # Multi-step planning required
    PLAN = "plan"

    # AI reasoning required
    REASON = "reason"

    # Execute via workflow/automation
    AUTOMATION = "automation"

    # Human intervention required
    ESCALATE = "escalate"

    # Reject execution
    REJECT = "reject"

    # Unknown
    UNKNOWN = "unknown"

    @property
    def requires_confirmation(self) -> bool:
        return self is ExecutionStrategy.CONFIRM

    @property
    def requires_planning(self) -> bool:
        return self is ExecutionStrategy.PLAN

    @property
    def requires_reasoning(self) -> bool:
        return self is ExecutionStrategy.REASON

    @property
    def is_terminal(self) -> bool:
        return self in (
            ExecutionStrategy.REJECT,
            ExecutionStrategy.UNKNOWN,
        )