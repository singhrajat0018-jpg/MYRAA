from dataclasses import dataclass

from ..semantic_models import SemanticTask


@dataclass(slots=True)
class ParserResponse:

    task: SemanticTask

    raw_response: str

    provider: str

    latency_ms: float