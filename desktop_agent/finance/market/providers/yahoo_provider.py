"""
Yahoo Finance Provider
"""

from __future__ import annotations

from datetime import datetime

import yfinance as yf

from ..market_provider import (

    MarketProvider,

    MarketQuote,

)


class YahooProvider(MarketProvider):

    # -------------------------------------

    def _normalize(

        self,

        symbol: str,

    ) -> str:

        symbol = symbol.upper()

        if "." not in symbol:

            symbol += ".NS"

        return symbol

    # -------------------------------------

    def get_quote(

        self,

        symbol: str,

    ) -> MarketQuote:

        ticker = yf.Ticker(

            self._normalize(symbol)

        )

        info = ticker.fast_info

        history = ticker.history(period="2d")

        previous_close = 0.0

        if len(history) >= 2:

            previous_close = float(

                history.iloc[-2]["Close"]

            )

        return MarketQuote(

            symbol=symbol.upper(),

            company_name=ticker.info.get(

                "longName",

                symbol,

            ),

            current_price=float(

                info["lastPrice"]

            ),

            previous_close=previous_close,

            open_price=float(

                info["open"]

            ),

            high=float(

                info["dayHigh"]

            ),

            low=float(

                info["dayLow"]

            ),

            volume=int(

                info["lastVolume"]

            ),

            exchange="NSE",

            currency="INR",

            market_time=datetime.utcnow(),

        )

    # -------------------------------------

    def get_quotes(

        self,

        symbols: list[str],

    ) -> dict[str, MarketQuote]:

        result = {}

        for symbol in symbols:

            try:

                result[symbol] = self.get_quote(symbol)

            except Exception:

                continue

        return result