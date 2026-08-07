"""
MYRAA Cognitive Engine

Execution Events

Event models used by the Execution Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any



# ==========================================================
# Base Event
# ==========================================================

@dataclass(slots=True)
class ExecutionEvent:
    """
    Base execution event.
    """

    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )



# ==========================================================
# Execution Lifecycle Events
# ==========================================================

@dataclass(slots=True)
class ExecutionStarted(ExecutionEvent):
    """
    Fired when execution begins.
    """

    execution_id: str = ""

    plan_id: str = ""



@dataclass(slots=True)
class ExecutionCompleted(ExecutionEvent):
    """
    Fired when complete execution finishes.
    """

    execution_id: str = ""

    success: bool = True



@dataclass(slots=True)
class ExecutionFailed(ExecutionEvent):
    """
    Fired when execution fails.
    """

    execution_id: str = ""

    error: str = ""



@dataclass(slots=True)
class ExecutionCancelled(ExecutionEvent):
    """
    Fired when user cancels execution.
    """

    execution_id: str = ""



# ==========================================================
# Step Events
# ==========================================================

@dataclass(slots=True)
class StepStarted(ExecutionEvent):
    """
    Fired when a step starts.
    """

    step_id: int = 0

    step_name: str = ""

    action: str = ""



@dataclass(slots=True)
class StepCompleted(ExecutionEvent):
    """
    Fired when a step completes.
    """

    step_id: int = 0

    success: bool = True

    duration: float = 0.0



@dataclass(slots=True)
class StepFailed(ExecutionEvent):
    """
    Fired when a step fails.
    """

    step_id: int = 0

    error: str = ""



# ==========================================================
# Retry Events
# ==========================================================

@dataclass(slots=True)
class RetryStarted(ExecutionEvent):
    """
    Fired before retry attempt.
    """

    step_id: int = 0

    attempt: int = 0



@dataclass(slots=True)
class RetryCompleted(ExecutionEvent):
    """
    Fired after retry.
    """

    step_id: int = 0

    success: bool = False

    attempt: int = 0



# ==========================================================
# Verification Events
# ==========================================================

@dataclass(slots=True)
class VerificationStarted(ExecutionEvent):
    """
    Verification started.
    """

    step_id: int = 0



@dataclass(slots=True)
class VerificationCompleted(ExecutionEvent):
    """
    Verification completed.
    """

    step_id: int = 0

    verified: bool = False

    message: str = ""



# ==========================================================
# Progress Event
# ==========================================================

@dataclass(slots=True)
class ProgressUpdated(ExecutionEvent):
    """
    Execution progress changed.
    """

    current: int = 0

    total: int = 0

    percentage: float = 0.0