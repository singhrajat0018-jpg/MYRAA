from dataclasses import dataclass, field
from typing import Any
from .knowledge_source import KnowledgeSource

@dataclass(slots=True)
class KnowledgeResult:
    """
    Final synthesized knowledge returned to the Brain.
    """

    success: bool

    answer: str = ""

    confidence: float = 0.0

    sources: list[KnowledgeSource] = field(default_factory=list)

    provider: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)