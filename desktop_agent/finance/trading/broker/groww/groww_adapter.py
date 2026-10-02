"""
MYRAA Groww Trading Advisor — API Client

Read-only Groww API client. Translates Groww responses into Phase D models.
No order execution — execution methods raise NotImplementedError.

CRITICAL: Credentials never enter Memory 2.0, logs, telemetry, or error messages.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
from desktop_agent.finance.trading.broker.groww.groww_auth import (
    GROWW_BASE_URL,
    GrowwAuthConfig,
    GrowwAuthenticator,
)

logger = logging.getLogger(__name__)

# Groww segment constants
SEGMENT_CASH = "CASH"
SEGMENT_FNO = "FNO"
EXCHANGE_NSE = "NSE"
EXCHANGE_BSE = "BSE"

# Price normalization: Groww sometimes returns prices in paise
PAISE_THRESHOLD = 1000  # If price > this, likely in paise


def _normalize_price(value: Any) -> float:
    """Normalize price from Groww API (may be in paise)."""
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


class GrowwClient:
    """Low-level Groww API HTTP client."""

    def __init__(self, authenticator: GrowwAuthenticator):
        self._auth = authenticator
        self._base_url = GROWW_BASE_URL

    def _request(self, method: str, path: str, params: Optional[Dict] = None,
                 body: Optional[Dict] = None, timeout: int = 10) -> Dict[str, Any]:
        if not self._auth.is_authenticated():
            self._auth.refresh_if_needed()
        headers = self._auth.get_headers()
        if not headers:
            return {"error": "not_authenticated", "message": "No valid credentials"}
        url = f"{self._base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if qs:
                url += f"?{qs}"
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw)
        except HTTPError as exc:
            try:
                err_body = exc.read()
                err_data = json.loads(err_body)
                return {"error": f"http_{exc.code}", "message": err_data.get("message", str(exc))}
            except Exception:
                return {"error": f"http_{exc.code}", "message": str(exc)}
        except URLError as exc:
            return {"error": "network_error", "message": str(exc.reason)}
        except Exception as exc:
            return {"error": "unknown", "message": str(exc)}

    def get(self, path: str, params: Optional[Dict] = None, timeout: int = 10) -> Dict[str, Any]:
        return self._request("GET", path, params=params, timeout=timeout)

    def post(self, path: str, body: Optional[Dict] = None, timeout: int = 10) -> Dict[str, Any]:
        return self._request("POST", path, body=body, timeout=timeout)


class GrowwAdapter(BrokerAdapter):
    """
    Read-only Groww broker adapter.
    Translates Groww API responses into Phase D trading models.
    Execution methods raise NotImplementedError (MYRAA never places orders).
    """

    def __init__(self, config: Optional[GrowwAuthConfig] = None):
        super().__init__()
        self._auth_config = config or GrowwAuthConfig.from_env()
        self._authenticator = GrowwAuthenticator(self._auth_config)
        self._client = GrowwClient(self._authenticator)
        self._connected = self._authenticator.is_authenticated()
        self._account_cache: Optional[Dict[str, Any]] = None
        self._holdings_cache: Optional[List[Dict]] = None
        self._positions_cache: Optional[List[Dict]] = None

    @property
    def authenticated(self) -> bool:
        return self._authenticator.is_authenticated()

    @property
    def auth_state(self) -> Dict[str, Any]:
        return self._authenticator.get_state()

    def is_connected(self) -> bool:
        return self._connected and self._authenticator.is_authenticated()

    def _ensure_connected(self) -> bool:
        if not self._authenticator.is_authenticated():
            self._authenticator.refresh_if_needed()
        self._connected = self._authenticator.is_authenticated()
        return self._connected

    # ─── Portfolio ──────────────────────────────────────────────────────

    def get_account(self) -> Dict[str, Any]:
        if not self._ensure_connected():
            return {"error": "not_connected", "balance": 0, "margin_used": 0,
                    "margin_available": 0, "realized_pnl": 0, "unrealized_pnl": 0}
        try:
            resp = self._client.get("/margins/user")
            if "error" in resp:
                return {"error": resp["error"], "balance": 0, "margin_used": 0,
                        "margin_available": 0, "realized_pnl": 0, "unrealized_pnl": 0}
            data = resp.get("data", resp)
            return {
                "balance": _safe_float(data.get("available_margin", data.get("balance", 0))),
                "margin_used": _safe_float(data.get("margin_used", 0)),
                "margin_available": _safe_float(data.get("available_margin", 0)),
                "realized_pnl": _safe_float(data.get("realized_pnl", 0)),
                "unrealized_pnl": _safe_float(data.get("unrealized_pnl", 0)),
                "collateral": _safe_float(data.get("collateral", 0)),
                "error": None,
            }
        except Exception as exc:
            logger.debug("Groww get_account failed: %s", type(exc).__name__)
            return {"error": "fetch_failed", "balance": 0, "margin_used": 0,
                    "margin_available": 0, "realized_pnl": 0, "unrealized_pnl": 0}

    def get_holdings(self) -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return []
        try:
            resp = self._client.get("/holdings/user")
            if "error" in resp:
                return []
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("holdings", [])
        except Exception as exc:
            logger.debug("Groww get_holdings failed: %s", type(exc).__name__)
            return []

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return []
        try:
            resp = self._client.get("/positions/user", params={"segment": SEGMENT_CASH})
            if "error" in resp:
                return []
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("positions", [])
        except Exception as exc:
            logger.debug("Groww get_positions failed: %s", type(exc).__name__)
            return []

    def get_orders(self, page: int = 0, page_size: int = 100) -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return []
        try:
            resp = self._client.get("/order/list", params={
                "segment": SEGMENT_CASH, "page": str(page), "page_size": str(page_size)
            })
            if "error" in resp:
                return []
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("orders", [])
        except Exception as exc:
            logger.debug("Groww get_orders failed: %s", type(exc).__name__)
            return []

    def get_order_trades(self, order_id: str) -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return []
        try:
            resp = self._client.get(f"/order/trades/{order_id}", params={
                "segment": SEGMENT_CASH, "page": "0", "page_size": "50"
            })
            if "error" in resp:
                return []
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("trades", [])
        except Exception as exc:
            logger.debug("Groww get_order_trades failed: %s", type(exc).__name__)
            return []

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if not self._ensure_connected():
            return {"status": "UNKNOWN", "error": "not_connected"}
        try:
            resp = self._client.get(f"/order/detail/{order_id}", params={"segment": SEGMENT_CASH})
            if "error" in resp:
                return {"status": "NOT_FOUND", "error": resp["error"]}
            return resp.get("data", resp)
        except Exception as exc:
            return {"status": "ERROR", "error": "fetch_failed"}

    # ─── Market Data ────────────────────────────────────────────────────

    def get_quote(self, symbol: str, exchange: str = EXCHANGE_NSE) -> Dict[str, Any]:
        if not self._ensure_connected():
            return {"error": "not_connected", "symbol": symbol}
        try:
            resp = self._client.get("/live-data/quote", params={
                "exchange": exchange, "segment": SEGMENT_CASH,
                "trading_symbol": symbol,
            })
            if "error" in resp:
                return {"error": resp["error"], "symbol": symbol}
            return resp.get("data", resp)
        except Exception as exc:
            return {"error": "fetch_failed", "symbol": symbol}

    def get_quotes_batch(self, symbols: List[str], exchange: str = EXCHANGE_NSE) -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return [{"error": "not_connected", "symbol": s} for s in symbols]
        try:
            exchange_symbols = ",".join(f"{exchange}_{s}" for s in symbols)
            resp = self._client.get("/live-data/ltp", params={
                "segment": SEGMENT_CASH, "exchange_symbols": exchange_symbols,
            })
            if "error" in resp:
                return [{"error": resp["error"], "symbol": s} for s in symbols]
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("ltp_data", [data]) if isinstance(data, dict) else []
        except Exception:
            return [{"error": "fetch_failed", "symbol": s} for s in symbols]

    def get_ohlc(self, symbol: str, exchange: str = EXCHANGE_NSE) -> Dict[str, Any]:
        if not self._ensure_connected():
            return {"error": "not_connected", "symbol": symbol}
        try:
            resp = self._client.get("/live-data/ohlc", params={
                "segment": SEGMENT_CASH, "exchange_symbols": f"{exchange}_{symbol}",
            })
            if "error" in resp:
                return {"error": resp["error"], "symbol": symbol}
            return resp.get("data", resp)
        except Exception as exc:
            return {"error": "fetch_failed", "symbol": symbol}

    def get_historical_candles(self, symbol: str, exchange: str = EXCHANGE_NSE,
                               interval: str = "1day", start_time: str = "",
                               end_time: str = "") -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return []
        try:
            params = {
                "exchange": exchange, "segment": SEGMENT_CASH,
                "trading_symbol": symbol, "interval": interval,
            }
            if start_time:
                params["start_time"] = start_time
            if end_time:
                params["end_time"] = end_time
            resp = self._client.get("/historical/candle/range", params=params)
            if "error" in resp:
                return []
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("candles", [])
        except Exception:
            return []

    def get_option_chain(self, underlying: str, expiry_date: str,
                         exchange: str = EXCHANGE_NSE) -> List[Dict[str, Any]]:
        if not self._ensure_connected():
            return []
        try:
            resp = self._client.get(
                f"/option-chain/exchange/{exchange}/underlying/{underlying}",
                params={"expiry_date": expiry_date},
            )
            if "error" in resp:
                return []
            data = resp.get("data", resp)
            if isinstance(data, list):
                return data
            return data.get("option_chain", [])
        except Exception:
            return []

    def get_greeks(self, exchange: str, underlying: str, symbol: str,
                   expiry: str) -> Dict[str, Any]:
        if not self._ensure_connected():
            return {}
        try:
            resp = self._client.get(
                f"/live-data/greeks/exchange/{exchange}/underlying/{underlying}"
                f"/trading_symbol/{symbol}/expiry/{expiry}",
            )
            if "error" in resp:
                return {}
            return resp.get("data", resp)
        except Exception:
            return {}

    # ─── User Profile ───────────────────────────────────────────────────

    def get_user_profile(self) -> Dict[str, Any]:
        if not self._ensure_connected():
            return {"error": "not_connected"}
        try:
            resp = self._client.get("/user/profile")
            if "error" in resp:
                return resp
            return resp.get("data", resp)
        except Exception:
            return {"error": "fetch_failed"}

    # ─── Portfolio Sync ─────────────────────────────────────────────────

    def sync_portfolio(self) -> Dict[str, Any]:
        """
        Build PortfolioSnapshot from Groww holdings + positions.
        Returns dict with positions, cash, and metadata.
        """
        if not self._ensure_connected():
            return {"positions": [], "cash": 0, "broker": "groww", "connected": False}

        holdings = self.get_holdings()
        positions = self.get_positions()
        account = self.get_account()

        normalized = []

        # Holdings → PortfolioPosition-like dicts
        for h in holdings:
            try:
                symbol = h.get("trading_symbol", h.get("symbol", ""))
                quantity = _safe_int(h.get("quantity", h.get("available_quantity", 0)))
                avg_price = _normalize_price(h.get("average_price", h.get("avg_price", 0)))
                current_price = _normalize_price(h.get("ltp", h.get("last_traded_price", 0)))
                previous_close = _normalize_price(h.get("previous_close", 0))
                if not symbol or quantity <= 0:
                    continue
                normalized.append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "average_price": avg_price,
                    "current_price": current_price,
                    "previous_close": previous_close,
                    "source": "groww_holding",
                    "exchange": h.get("exchange", EXCHANGE_NSE),
                    "instrument_type": "EQUITY",
                })
            except Exception:
                continue

        # Intraday positions (non-holding)
        seen_symbols = {p["symbol"] for p in normalized}
        for p in positions:
            try:
                symbol = p.get("trading_symbol", p.get("symbol", ""))
                if not symbol or symbol in seen_symbols:
                    continue
                quantity = _safe_int(p.get("quantity", 0))
                if quantity == 0:
                    continue
                avg_price = _normalize_price(p.get("average_price", p.get("avg_price", 0)))
                current_price = _normalize_price(p.get("ltp", p.get("last_traded_price", 0)))
                normalized.append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "average_price": avg_price,
                    "current_price": current_price,
                    "previous_close": _normalize_price(p.get("previous_close", 0)),
                    "source": "groww_position",
                    "exchange": p.get("exchange", EXCHANGE_NSE),
                    "instrument_type": "EQUITY",
                })
                seen_symbols.add(symbol)
            except Exception:
                continue

        return {
            "positions": normalized,
            "cash": account.get("balance", 0),
            "margin_used": account.get("margin_used", 0),
            "unrealized_pnl": account.get("unrealized_pnl", 0),
            "realized_pnl": account.get("realized_pnl", 0),
            "broker": "groww",
            "connected": True,
            "position_count": len(normalized),
            "timestamp": datetime.utcnow().isoformat(),
        }
