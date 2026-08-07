from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionRequest:

    title: str

    priority: float

    summary: str

    metadata: dict[str, Any] = field(default_factory=dict)