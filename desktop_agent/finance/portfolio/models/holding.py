"""
Holding Model

Represents a single investment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Holding:

    symbol: str

    company_name: str

    quantity: float

    average_price: float

    exchange: str = "NSE"

    currency: str = "INR"

    created_at: datetime = field(default_factory=datetime.utcnow)

    current_price: float = 0.0

    previous_close: float = 0.0

    last_updated: datetime | None = None

    # -----------------------------------------

    @property
    def invested_amount(self) -> float:

        return self.quantity * self.average_price

    # -----------------------------------------

    @property
    def current_value(self) -> float:

        return self.quantity * self.current_price

    # -----------------------------------------

    @property
    def profit_loss(self) -> float:

        return self.current_value - self.invested_amount

    # -----------------------------------------

    @property
    def profit_percent(self) -> float:

        invested = self.invested_amount

        if invested == 0:
            return 0.0

        return (self.profit_loss / invested) * 100

    # -----------------------------------------

    @property
    def day_change_percent(self) -> float:

        if self.previous_close == 0:
            return 0.0

        return (
            (self.current_price - self.previous_close)
            / self.previous_close
        ) * 100