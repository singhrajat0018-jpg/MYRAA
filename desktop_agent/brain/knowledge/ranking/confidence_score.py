"""
Confidence Score

Calculates provider confidence.
"""

from __future__ import annotations

from ..provider_response import ProviderResponse


class ConfidenceScore:
    """
    Calculates confidence score.
    """

    PROVIDER_WEIGHTS = {

        "tavily": 1.00,

        "wikipedia": 0.95,

        "duckduckgo": 0.85,

    }

    def calculate(

        self,

        response: ProviderResponse,

    ) -> float:

        confidence = response.confidence

        if confidence <= 0:

            confidence = 0.50

        provider_weight = self.PROVIDER_WEIGHTS.get(

            response.provider.lower(),

            0.75,

        )

        source_bonus = min(

            len(response.sources) * 0.02,

            0.10,

        )

        final = (

            confidence * 0.75

            + provider_weight * 0.20

            + source_bonus

        )

        return min(final, 1.0)