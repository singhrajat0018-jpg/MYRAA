"""
Abstract Market Provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarketQuote:

    symbol: str

    current_price: float

    previous_close: float

    open_price: float = 0.0

    high_price: float = 0.0

    low_price: float = 0.0

    volume: int = 0

    @property
    def day_change(self) -> float:
        return self.current_price - self.previous_close

    @property
    def day_change_percent(self) -> float:
        if self.previous_close == 0:
            return 0.0

        return (
            (self.current_price - self.previous_close)
            / self.previous_close
        ) * 100


class MarketProvider(ABC):

    @abstractmethod
    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        raise NotImplementedError

    @abstractmethod
    def get_quotes(
        self,
        symbols: list[str],
    ) -> dict[str, MarketQuote]:
        raise NotImplementedError