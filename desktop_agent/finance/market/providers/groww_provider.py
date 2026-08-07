"""
Groww Provider

Future adapter for Groww integration.

Current status:
- No official public portfolio API.
- Placeholder interface for future connector support.
"""

from __future__ import annotations

from ..market_provider import MarketProvider, MarketQuote


class GrowwProvider(MarketProvider):

    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:

        raise NotImplementedError(
            "Groww market provider is not implemented. "
            "Use YahooProvider for market data."
        )

    def get_quotes(
        self,
        symbols: list[str],
    ) -> dict[str, MarketQuote]:

        raise NotImplementedError(
            "Groww market provider is not implemented."
        )