from dataclasses import dataclass, field

from ..intelligence.knowledge_source import KnowledgeSource


@dataclass(slots=True)
class ProviderResponse:
    """
    Raw response returned by any provider
    before synthesis.
    """

    provider: str

    success: bool

    answer: str = ""

    sources: list[KnowledgeSource] = field(
        default_factory=list
    )

    latency: float = 0.0

    tokens_used: int = 0

    credits_used: int = 0

    metadata: dict = field(
        default_factory=dict
    )