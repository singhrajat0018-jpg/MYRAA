"""
Market Cache
"""

from __future__ import annotations

import time

from .market_provider import MarketQuote


class MarketCache:

    def __init__(

        self,

        ttl: int = 30,

    ):

        self.ttl = ttl

        self._cache: dict[str, tuple[float, MarketQuote]] = {}

    # -------------------------------------

    def get(

        self,

        symbol: str,

    ) -> MarketQuote | None:

        item = self._cache.get(symbol)

        if item is None:

            return None

        ts, quote = item

        if time.time() - ts > self.ttl:

            del self._cache[symbol]

            return None

        return quote

    # -------------------------------------

    def set(

        self,

        quote: MarketQuote,

    ) -> None:

        self._cache[quote.symbol] = (

            time.time(),

            quote,

        )

    # -------------------------------------

    def clear(self):

        self._cache.clear()