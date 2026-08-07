"""
Finance Service

Central finance orchestration layer.

Responsibilities
----------------
- Refresh portfolio prices
- Analyze holdings
- Evaluate risk
- Generate finance events

The Brain and Observers should only talk to this service.
"""

from __future__ import annotations

import logging

from desktop_agent.brain.observer.event import ObserverEvent

from .portfolio.portfolio_manager import PortfolioManager
from .market.provider_manager import ProviderManager
from .analysis.stock_analyzer import StockAnalyzer
from .analysis.risk_engine import RiskEngine
from .alerts.finance_alert_engine import FinanceAlertEngine

logger = logging.getLogger(__name__)


class FinanceService:

    def __init__(
        self,
        portfolio: PortfolioManager,
        provider: ProviderManager,
    ):

        self.portfolio = portfolio
        self.provider = provider

        self.analyzer = StockAnalyzer()
        self.risk_engine = RiskEngine()
        self.alert_engine = FinanceAlertEngine()

    # ----------------------------------------------------------

    def process(self) -> list[ObserverEvent]:

        events: list[ObserverEvent] = []

        portfolio = self.portfolio.get_portfolio()

        if not portfolio.holdings:
            return events

        quotes = self.provider.get_quotes(
            [h.symbol for h in portfolio.holdings]
        )

        for holding in portfolio.holdings:

            quote = quotes.get(holding.symbol)

            if quote is None:
                continue

            try:

                analysis = self.analyzer.analyze(
                    holding,
                    quote,
                )

                risk = self.risk_engine.evaluate(
                    analysis,
                )

                event = self.alert_engine.to_event(
                    analysis,
                    risk,
                )

                if event:
                    events.append(event)

            except Exception:

                logger.exception(
                    "Finance processing failed for %s",
                    holding.symbol,
                )

        return events