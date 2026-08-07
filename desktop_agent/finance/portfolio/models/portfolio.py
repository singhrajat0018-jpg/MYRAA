"""
Portfolio Model
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .holding import Holding


@dataclass(slots=True)
class Portfolio:

    owner: str = "User"

    holdings: list[Holding] = field(default_factory=list)

    # -----------------------------------------

    def add(self, holding: Holding) -> None:

        self.holdings.append(holding)

    # -----------------------------------------

    def remove(self, symbol: str) -> None:

        symbol = symbol.upper()

        self.holdings = [

            h

            for h in self.holdings

            if h.symbol.upper() != symbol

        ]

    # -----------------------------------------

    def get(self, symbol: str) -> Holding | None:

        symbol = symbol.upper()

        for holding in self.holdings:

            if holding.symbol.upper() == symbol:

                return holding

        return None

    # -----------------------------------------

    @property
    def invested_amount(self) -> float:

        return sum(

            h.invested_amount

            for h in self.holdings

        )

    # -----------------------------------------

    @property
    def current_value(self) -> float:

        return sum(

            h.current_value

            for h in self.holdings

        )

    # -----------------------------------------

    @property
    def total_profit(self) -> float:

        return self.current_value - self.invested_amount

    # -----------------------------------------

    @property
    def total_profit_percent(self) -> float:

        invested = self.invested_amount

        if invested == 0:
            return 0.0

        return (self.total_profit / invested) * 100