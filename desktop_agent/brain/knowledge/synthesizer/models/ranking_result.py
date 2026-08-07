"""
Ranking Result

Represents the final ranking score for a provider response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...provider_response import ProviderResponse


@dataclass(slots=True)
class RankingResult:
    """
    Final ranking information.
    """

    response: ProviderResponse

    provider: str

    score: float

    freshness: float

    confidence: float

    provider_priority: float

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.response.success

    @property
    def source_count(self) -> int:
        return len(self.response.sources)

    def to_dict(self) -> dict[str, Any]:

        return {
            "provider": self.provider,
            "score": self.score,
            "freshness": self.freshness,
            "confidence": self.confidence,
            "provider_priority": self.provider_priority,
            "success": self.success,
            "source_count": self.source_count,
            "metadata": self.metadata,
        }