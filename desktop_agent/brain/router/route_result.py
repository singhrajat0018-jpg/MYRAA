from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RouteResult:
    handled: bool = False
    action: str | None = None
    parameters: dict = field(default_factory=dict)
    confidence: float = 1.0