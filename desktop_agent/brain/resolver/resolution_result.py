from dataclasses import dataclass, field


@dataclass(slots=True)
class ResolutionResult:

    resolved: bool = False

    confidence: float = 0.0

    project: str | None = None

    path: str | None = None

    metadata: dict = field(default_factory=dict)