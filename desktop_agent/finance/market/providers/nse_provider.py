"""
NSE Provider

Future market data provider.
"""

from __future__ import annotations

from ..market_provider import MarketProvider, MarketQuote


class NSEProvider(MarketProvider):

    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:

        raise NotImplementedError(
            "NSE provider not implemented yet."
        )

    def get_quotes(
        self,
        symbols: list[str],
    ) -> dict[str, MarketQuote]:

        raise NotImplementedError(
            "NSE provider not implemented yet."
        )