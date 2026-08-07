"""
MYRAA Cognitive Engine

Execution Feedback
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ExecutionFeedback:
    """
    Result returned after executing a plan step.
    """

    success: bool

    tool: str

    message: str

    duration_ms: float = 0.0

    result: Any = None

    error: str | None = None

    timestamp: datetime = field(default_factory=datetime.now)