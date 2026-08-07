"""
Portfolio Manager
"""

from __future__ import annotations

from .models.holding import Holding
from .models.portfolio import Portfolio

from ..storage.portfolio_store import PortfolioStore


class PortfolioManager:

    def __init__(
        self,
        store: PortfolioStore | None = None,
    ):

        self.store = store or PortfolioStore()

        self.portfolio = self.store.load()

    # -----------------------------------------

    def buy(

        self,

        symbol: str,

        company_name: str,

        quantity: float,

        average_price: float,

        exchange: str = "NSE",

    ) -> Holding:

        existing = self.portfolio.get(symbol)

        if existing:

            total_qty = existing.quantity + quantity

            total_cost = (

                existing.quantity * existing.average_price

                + quantity * average_price

            )

            existing.average_price = total_cost / total_qty

            existing.quantity = total_qty

            self.store.save(self.portfolio)

            return existing

        holding = Holding(

            symbol=symbol.upper(),

            company_name=company_name,

            quantity=quantity,

            average_price=average_price,

            exchange=exchange,

        )

        self.portfolio.add(holding)

        self.store.save(self.portfolio)

        return holding

    # -----------------------------------------

    def sell(

        self,

        symbol: str,

        quantity: float,

    ) -> bool:

        holding = self.portfolio.get(symbol)

        if holding is None:

            return False

        if quantity >= holding.quantity:

            self.portfolio.remove(symbol)

            self.store.save(self.portfolio)

            return True

        holding.quantity -= quantity

        self.store.save(self.portfolio)

        return True

    # -----------------------------------------from desktop_agent.finance.portfolio.portfolio_manager import PortfolioManager

    def get_portfolio(self) -> Portfolio:

        return self.portfolio

    # -----------------------------------------

    def save(self) -> None:

        self.store.save(self.portfolio)

    # -----------------------------------------

    def reload(self) -> None:

        self.portfolio = self.store.load()