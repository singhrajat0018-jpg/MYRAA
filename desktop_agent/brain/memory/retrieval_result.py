from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RetrievalResult:

    handled: bool = False

    response: str = ""

    source: str = ""

    confidence: float = 0.0

    metadata: dict[str, Any] | None = None