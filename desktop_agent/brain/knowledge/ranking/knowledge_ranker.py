"""
Knowledge Ranker

Ranks provider responses using freshness,
confidence and provider priority.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .confidence_score import ConfidenceScore
from .freshness_score import FreshnessScore
from .ranking_policy import RankingPolicy
from .score_calculator import ScoreCalculator

from .models.ranking_result import RankingResult

from ..providers.provider_response import ProviderResponse
from ..intelligence.query_type import QueryType


class KnowledgeRanker:
    """
    Ranks provider responses.

    Pipeline

        ProviderResponse
              │
              ▼
        FreshnessScore
              │
              ▼
        ConfidenceScore
              │
              ▼
        RankingPolicy
              │
              ▼
        ScoreCalculator
              │
              ▼
        RankingResult
    """

    def __init__(self) -> None:

        self.freshness = FreshnessScore()

        self.confidence = ConfidenceScore()

        self.policy = RankingPolicy()

        self.calculator = ScoreCalculator()

    # ---------------------------------------------------------

    def rank(
        self,
        responses: Iterable[ProviderResponse],
        *,
        query_type: QueryType | None = None,
    ) -> list[RankingResult]:

        ranked: list[RankingResult] = []

        for response in responses:

            if response is None:
                continue

            if not response.success:
                continue

            freshness_score = self._freshness_score(
                response,
            )

            confidence_score = self.confidence.calculate(
                response,
            )

            provider_priority = self.policy.priority(
                response.provider,
                query_type,
            )

            final_score = self.calculator.calculate(
                freshness=freshness_score,
                confidence=confidence_score,
                provider_priority=provider_priority,
            )

            ranked.append(

                RankingResult(

                    response=response,

                    provider=response.provider,

                    score=final_score,

                    freshness=freshness_score,

                    confidence=confidence_score,

                    provider_priority=provider_priority,

                    metadata=response.metadata,
                )

            )

        ranked.sort(

            key=lambda item: item.score,

            reverse=True,

        )

        return ranked

    # ---------------------------------------------------------

    def best(
        self,
        responses: Iterable[ProviderResponse],
        *,
        query_type: QueryType | None = None,
    ) -> ProviderResponse | None:

        ranked = self.rank(

            responses,

            query_type=query_type,

        )

        if not ranked:

            return None

        return ranked[0].response

    # ---------------------------------------------------------

    def top(
        self,
        responses: Iterable[ProviderResponse],
        limit: int = 3,
        *,
        query_type: QueryType | None = None,
    ) -> list[ProviderResponse]:

        ranked = self.rank(

            responses,

            query_type=query_type,

        )

        return [

            item.response

            for item in ranked[:limit]

        ]

    # ---------------------------------------------------------

    def _freshness_score(
        self,
        response: ProviderResponse,
    ) -> float:

        metadata = response.metadata or {}

        published = (

            metadata.get("published")

            or metadata.get("published_at")

            or metadata.get("date")

            or metadata.get("updated")

        )

        if isinstance(
            published,
            datetime,
        ):

            return self.freshness.calculate(
                published,
            )

        return 0.50