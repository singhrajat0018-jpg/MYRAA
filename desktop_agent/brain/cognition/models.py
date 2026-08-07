from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CognitiveDecision:
    """
    Result of evaluating a background event.
    """

    store_memory: bool = True

    notify_user: bool = False

    trigger_reasoning: bool = False

    trigger_planner: bool = False

    priority: float = 0.0

    reason: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)