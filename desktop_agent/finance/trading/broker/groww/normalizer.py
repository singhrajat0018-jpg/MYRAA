"""
MYRAA Groww Trading Advisor — Data Normalizer

Converts raw Groww API responses into Phase D trading models.
All Groww data is normalized at the integration boundary.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.models import (
    Exchange,
    InstrumentType,
    MarketQuote,
    OHLCV,
    OptionChain,
    OptionContract,
    PortfolioPosition,
    PortfolioSnapshot,
)


def _normalize_price(value: Any) -> float:
    if value is None:
        return 0.0
    v = float(value)
    if v > 50000:
        v = v / 100.0
    return round(v, 2)


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_exchange(raw: str) -> Exchange:
    mapping = {
        "NSE": Exchange.NSE,
        "BSE": Exchange.BSE,
        "NIFTY": Exchange.NIFTY,
        "BANKNIFTY": Exchange.BANKNIFTY,
    }
    return mapping.get(str(raw).upper(), Exchange.UNKNOWN)


def _parse_instrument_type(raw: str) -> InstrumentType:
    mapping = {
        "EQUITY": InstrumentType.EQUITY,
        "INDEX": InstrumentType.INDEX,
        "FUTURES": InstrumentType.FUTURES,
        "OPTIONS": InstrumentType.OPTIONS,
        "ETF": InstrumentType.ETF,
        "MUTUAL_FUND": InstrumentType.MUTUAL_FUND,
    }
    return mapping.get(str(raw).upper(), InstrumentType.EQUITY)


def normalize_groww_quote(raw: Dict[str, Any], symbol: str = "") -> MarketQuote:
    """Convert Groww live quote to Phase D MarketQuote."""
    sym = raw.get("trading_symbol", raw.get("symbol", symbol))
    return MarketQuote(
        symbol=sym,
        current_price=_normalize_price(raw.get("ltp", raw.get("last_traded_price", 0))),
        previous_close=_normalize_price(raw.get("previous_close", raw.get("prev_close", 0))),
        open_price=_normalize_price(raw.get("open", raw.get("open_price", 0))),
        high_price=_normalize_price(raw.get("high", raw.get("day_high", 0))),
        low_price=_normalize_price(raw.get("low", raw.get("day_low", 0))),
        volume=_safe_int(raw.get("volume", raw.get("total_traded_volume", 0))),
        bid_price=_normalize_price(raw.get("best_bid_price", raw.get("bid", 0))),
        ask_price=_normalize_price(raw.get("best_ask_price", raw.get("ask", 0))),
        bid_size=_safe_int(raw.get("best_bid_quantity", 0)),
        ask_size=_safe_int(raw.get("best_ask_quantity", 0)),
        exchange=_parse_exchange(raw.get("exchange", "NSE")),
        currency="INR",
        market_status=raw.get("market_status", "UNKNOWN"),
        timestamp=datetime.utcnow().isoformat(),
        source="groww",
        data_quality="LIVE",
        freshness_seconds=0,
    )


def normalize_groww_ohlcv(raw: Dict[str, Any], symbol: str = "",
                          timeframe: str = "1day") -> Optional[OHLCV]:
    """Convert Groww candle data to Phase D OHLCV."""
    try:
        ts = raw.get("timestamp", raw.get("date", datetime.utcnow().isoformat()))
        if isinstance(ts, str):
            ts_str = ts
        else:
            ts_str = datetime.utcfromtimestamp(ts / 1000).isoformat() if ts else datetime.utcnow().isoformat()
        return OHLCV(
            timestamp=ts_str,
            open=_normalize_price(raw.get("open", 0)),
            high=_normalize_price(raw.get("high", 0)),
            low=_normalize_price(raw.get("low", 0)),
            close=_normalize_price(raw.get("close", 0)),
            volume=_safe_int(raw.get("volume", 0)),
            timeframe=timeframe,
            source="groww",
            confidence=1.0,
        )
    except Exception:
        return None


def normalize_groww_holdings(raw_holdings: List[Dict[str, Any]]) -> List[PortfolioPosition]:
    """Convert Groww holdings list to Phase D PortfolioPosition list."""
    positions = []
    for h in raw_holdings:
        try:
            symbol = h.get("trading_symbol", h.get("symbol", ""))
            if not symbol:
                continue
            quantity = _safe_int(h.get("quantity", h.get("available_quantity", 0)))
            if quantity <= 0:
                continue
            positions.append(PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                average_price=_normalize_price(h.get("average_price", h.get("avg_price", 0))),
                current_price=_normalize_price(h.get("ltp", h.get("last_traded_price", 0))),
                previous_close=_normalize_price(h.get("previous_close", 0)),
                exchange=_parse_exchange(h.get("exchange", "NSE")),
                sector="",
                instrument_type=InstrumentType.EQUITY,
                entry_date=h.get("created_at", ""),
                notes="",
            ))
        except Exception:
            continue
    return positions


def normalize_groww_positions(raw_positions: List[Dict[str, Any]],
                              existing_symbols: set) -> List[PortfolioPosition]:
    """Convert Groww intraday positions, skipping symbols already in holdings."""
    positions = []
    for p in raw_positions:
        try:
            symbol = p.get("trading_symbol", p.get("symbol", ""))
            if not symbol or symbol in existing_symbols:
                continue
            quantity = _safe_int(p.get("quantity", 0))
            if quantity == 0:
                continue
            positions.append(PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                average_price=_normalize_price(p.get("average_price", p.get("avg_price", 0))),
                current_price=_normalize_price(p.get("ltp", p.get("last_traded_price", 0))),
                previous_close=_normalize_price(p.get("previous_close", 0)),
                exchange=_parse_exchange(p.get("exchange", "NSE")),
                sector="",
                instrument_type=InstrumentType.EQUITY,
                entry_date=p.get("created_at", ""),
                notes="intraday",
            ))
            existing_symbols.add(symbol)
        except Exception:
            continue
    return positions


def normalize_groww_portfolio(holdings_raw: List[Dict], positions_raw: List[Dict],
                               cash: float = 0.0) -> PortfolioSnapshot:
    """Build a full PortfolioSnapshot from Groww data."""
    holdings = normalize_groww_holdings(holdings_raw)
    existing = {h.symbol for h in holdings}
    positions = normalize_groww_positions(positions_raw, existing)
    all_positions = holdings + positions
    return PortfolioSnapshot(
        positions=all_positions,
        cash=cash,
        timestamp=datetime.utcnow().isoformat(),
    )


def normalize_groww_option_chain(raw_chain: List[Dict], underlying: str,
                                  underlying_price: float = 0.0,
                                  expiry: str = "") -> OptionChain:
    """Convert Groww option chain to Phase D OptionChain."""
    contracts = []
    for item in raw_chain:
        try:
            oc = OptionContract(
                symbol=item.get("trading_symbol", item.get("symbol", "")),
                strike=_safe_float(item.get("strike_price", 0)),
                expiry=item.get("expiry_date", expiry),
                option_type="CE" if "CE" in item.get("trading_symbol", "").upper() else "PE",
                ltp=_normalize_price(item.get("ltp", 0)),
                bid=_normalize_price(item.get("best_bid_price", 0)),
                ask=_normalize_price(item.get("best_ask_price", 0)),
                volume=_safe_int(item.get("volume", 0)),
                open_interest=_safe_int(item.get("open_interest", 0)),
                change_in_oi=_safe_int(item.get("change_in_oi", 0)),
                implied_volatility=_safe_float(item.get("implied_volatility", 0)),
                delta=_safe_float(item.get("delta", 0)),
                gamma=_safe_float(item.get("gamma", 0)),
                theta=_safe_float(item.get("theta", 0)),
                vega=_safe_float(item.get("vega", 0)),
                in_the_money=item.get("in_the_money", False),
                margin_required=_safe_float(item.get("margin_required", 0)),
                lot_size=_safe_int(item.get("lot_size", 1)),
            )
            contracts.append(oc)
        except Exception:
            continue
    return OptionChain(
        symbol=underlying,
        underlying_price=underlying_price,
        expiry=expiry,
        contracts=contracts,
    )


def normalize_groww_trades(raw_trades: List[Dict]) -> List[Dict[str, Any]]:
    """Normalize Groww trade history into a clean list."""
    trades = []
    for t in raw_trades:
        try:
            trades.append({
                "trade_id": t.get("trade_id", t.get("groww_trade_id", "")),
                "order_id": t.get("order_id", t.get("groww_order_id", "")),
                "symbol": t.get("trading_symbol", t.get("symbol", "")),
                "side": t.get("side", t.get("transaction_type", "")),
                "quantity": _safe_int(t.get("quantity", 0)),
                "price": _normalize_price(t.get("trade_price", t.get("price", 0))),
                "timestamp": t.get("timestamp", t.get("created_at", "")),
                "status": t.get("status", "COMPLETE"),
            })
        except Exception:
            continue
    return trades
