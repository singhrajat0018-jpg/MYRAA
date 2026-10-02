"""
Yahoo Finance Provider

Fixed to match MarketQuote dataclass contract.
yfinance is optional — gracefully degrades if not installed.
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..market_provider import MarketProvider, MarketQuote

logger = logging.getLogger(__name__)

_yf = None


def _get_yf():
    global _yf
    if _yf is None:
        try:
            import yfinance
            _yf = yfinance
        except ImportError:
            logger.warning("yfinance not installed. YahooProvider will not work.")
            return None
    return _yf


class YahooProvider(MarketProvider):

    def _normalize(self, symbol: str) -> str:
        symbol = symbol.upper()
        if "." not in symbol:
            symbol += ".NS"
        return symbol

    def get_quote(self, symbol: str) -> MarketQuote:
        yf = _get_yf()
        if yf is None:
            raise RuntimeError("yfinance not installed")

        ticker = yf.Ticker(self._normalize(symbol))
        info = ticker.fast_info
        history = ticker.history(period="2d")

        previous_close = 0.0
        if len(history) >= 2:
            previous_close = float(history.iloc[-2]["Close"])

        return MarketQuote(
            symbol=symbol.upper(),
            current_price=float(info["lastPrice"]),
            previous_close=previous_close,
            open_price=float(info.get("open", 0.0)),
            high_price=float(info.get("dayHigh", 0.0)),
            low_price=float(info.get("dayLow", 0.0)),
            volume=int(info.get("lastVolume", 0)),
        )

    def get_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        result = {}
        for symbol in symbols:
            try:
                result[symbol] = self.get_quote(symbol)
            except Exception as exc:
                logger.debug("Yahoo quote failed for %s: %s", symbol, exc)
                continue
        return result
