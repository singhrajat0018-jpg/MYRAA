"""
Stock Analyzer

Analyzes market quotes and holdings.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..market.market_provider import MarketQuote
from ..portfolio.models.holding import Holding


@dataclass(slots=True)
class StockAnalysis:

    symbol: str

    current_price: float

    invested_value: float

    current_value: float

    profit_loss: float

    profit_percent: float

    day_change: float

    recommendation: str

    confidence: float


class StockAnalyzer:

    def analyze(

        self,

        holding: Holding,

        quote: MarketQuote,

    ) -> StockAnalysis:

        holding.current_price = quote.current_price

        holding.previous_close = quote.previous_close

        recommendation = "HOLD"

        confidence = 0.75

        if holding.day_change_percent >= 8:

            recommendation = "STRONG_UP"

            confidence = 0.95

        elif holding.day_change_percent <= -8:

            recommendation = "STRONG_DOWN"

            confidence = 0.95

        return StockAnalysis(

            symbol=holding.symbol,

            current_price=quote.current_price,

            invested_value=holding.invested_amount,

            current_value=holding.current_value,

            profit_loss=holding.profit_loss,

            profit_percent=holding.profit_percent,

            day_change=holding.day_change_percent,

            recommendation=recommendation,

            confidence=confidence,

        )