from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeSource:

    provider: str

    title: str

    url: str

    snippet: str

    confidence: float