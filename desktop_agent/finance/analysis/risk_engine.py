"""
Risk Engine
"""

from __future__ import annotations

from dataclasses import dataclass

from .stock_analyzer import StockAnalysis


@dataclass(slots=True)
class RiskResult:

    level: str

    score: float

    reason: str


class RiskEngine:

    def evaluate(

        self,

        analysis: StockAnalysis,

    ) -> RiskResult:

        if abs(analysis.day_change) >= 10:

            return RiskResult(

                level="HIGH",

                score=0.90,

                reason="Very high daily volatility",

            )

        if abs(analysis.day_change) >= 5:

            return RiskResult(

                level="MEDIUM",

                score=0.60,

                reason="Moderate daily volatility",

            )

        return RiskResult(

            level="LOW",

            score=0.20,

            reason="Normal market movement",

        )