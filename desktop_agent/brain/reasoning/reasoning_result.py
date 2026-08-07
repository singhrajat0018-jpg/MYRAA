from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ReasoningResult:

    success: bool = True

    should_plan: bool = False

    should_notify: bool = False

    confidence: float = 0.0

    summary: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)