"""
Score Calculator

Combines all ranking scores into one final score.
"""

from __future__ import annotations


class ScoreCalculator:
    """
    Calculates the final ranking score.
    """

    def __init__(
        self,
        freshness_weight: float = 0.30,
        confidence_weight: float = 0.45,
        provider_weight: float = 0.25,
    ) -> None:

        self.freshness_weight = freshness_weight
        self.confidence_weight = confidence_weight
        self.provider_weight = provider_weight

    # -----------------------------------------------------

    def calculate(

        self,

        freshness: float,

        confidence: float,

        provider_priority: float,

    ) -> float:

        score = (

            freshness * self.freshness_weight

            + confidence * self.confidence_weight

            + provider_priority * self.provider_weight

        )

        return round(
            min(score, 1.0),
            4,
        )