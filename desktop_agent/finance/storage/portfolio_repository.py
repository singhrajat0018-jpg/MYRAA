"""
Portfolio Repository

Persistence layer for portfolio data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..portfolio.models.portfolio import Portfolio


class PortfolioRepository(ABC):

    @abstractmethod
    def load(self) -> Portfolio:
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        portfolio: Portfolio,
    ) -> None:
        raise NotImplementedError