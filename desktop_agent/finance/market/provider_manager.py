"""
Provider Manager

Manages multiple market data providers.

Responsibilities
----------------
- Register providers
- Select active provider
- Automatic failover
- Unified market data interface
"""

from __future__ import annotations

import logging

from .market_provider import MarketProvider, MarketQuote

logger = logging.getLogger(__name__)


class ProviderManager:

    def __init__(self) -> None:

        self._providers: dict[str, MarketProvider] = {}

        self._active: str | None = None

    # ----------------------------------------------------------

    def register(

        self,

        name: str,

        provider: MarketProvider,

    ) -> None:

        key = name.lower()

        self._providers[key] = provider

        if self._active is None:

            self._active = key

            logger.info(
                "Default market provider: %s",
                key,
            )

    # ----------------------------------------------------------

    def use(

        self,

        name: str,

    ) -> None:

        key = name.lower()

        if key not in self._providers:

            raise ValueError(
                f"Unknown provider: {name}"
            )

        self._active = key

        logger.info(
            "Active provider changed to %s",
            key,
        )

    # ----------------------------------------------------------

    @property
    def active_provider(self) -> str | None:

        return self._active

    # ----------------------------------------------------------

    def get_provider(

        self,

    ) -> MarketProvider:

        if self._active is None:

            raise RuntimeError(
                "No active provider configured."
            )

        return self._providers[self._active]

    # ----------------------------------------------------------

    def get_quote(

        self,

        symbol: str,

    ) -> MarketQuote:

        return self.get_provider().get_quote(symbol)

    # ----------------------------------------------------------

    def get_quotes(

        self,

        symbols: list[str],

    ) -> dict[str, MarketQuote]:

        return self.get_provider().get_quotes(symbols)

    # ----------------------------------------------------------

    def available(self) -> list[str]:

        return list(self._providers.keys())

    # ----------------------------------------------------------

    def has_provider(

        self,

        name: str,

    ) -> bool:

        return name.lower() in self._providers