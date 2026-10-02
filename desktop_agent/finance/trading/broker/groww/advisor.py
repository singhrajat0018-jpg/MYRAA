"""
MYRAA Groww Trading Advisor — Main Orchestrator

Ties together: GrowwAdapter + GuidanceEngine + TradingIntelligenceEngine
to deliver personalized portfolio-aware trading advice.

This is MYRAA's professional trading companion — it advises, never executes.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.broker.groww.groww_adapter import GrowwAdapter
from desktop_agent.finance.trading.broker.groww.groww_auth import GrowwAuthConfig
from desktop_agent.finance.trading.broker.groww.guidance import (
    PersonalizedGuidanceEngine,
    PortfolioAdvice,
    StockGuidance,
)
from desktop_agent.finance.trading.broker.groww.normalizer import (
    normalize_groww_holdings,
    normalize_groww_option_chain,
    normalize_groww_portfolio,
    normalize_groww_quote,
)
from desktop_agent.finance.trading.models import (
    DailyMarketCloseReport,
    OptionChain,
    PortfolioSnapshot,
    TechnicalAnalysis,
)

logger = logging.getLogger(__name__)


@dataclass
class GrowwAdvisorState:
    connected: bool = False
    holdings_count: int = 0
    positions_count: int = 0
    last_sync: Optional[str] = None
    last_guidance: Optional[str] = None
    guidance_count: int = 0
    error: str = ""


class GrowwAdvisor:
    """
    Professional trading companion backed by real Groww portfolio data.
    Advises only — never executes trades.

    Usage:
        advisor = GrowwAdvisor()
        advice = advisor.analyze_my_portfolio()
        print(advice.overall_assessment)
    """

    def __init__(self, config: Optional[GrowwAuthConfig] = None,
                 trading_engine=None):
        self._adapter = GrowwAdapter(config)
        self._guidance = PersonalizedGuidanceEngine()
        self._trading_engine = trading_engine
        self._state = GrowwAdvisorState()
        self._snapshot: Optional[PortfolioSnapshot] = None
        self._technical_cache: Dict[str, TechnicalAnalysis] = {}
        self._market_context: str = ""
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._adapter.is_connected()

    @property
    def state(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "holdings_count": self._state.holdings_count,
            "positions_count": self._state.positions_count,
            "last_sync": self._state.last_sync,
            "last_guidance": self._state.last_guidance,
            "guidance_count": self._state.guidance_count,
            "error": self._state.error,
            "auth_state": self._adapter.auth_state,
        }

    # ─── Core Portfolio Operations ──────────────────────────────────────

    def sync_portfolio(self) -> PortfolioSnapshot:
        """Pull latest holdings + positions from Groww and build snapshot."""
        try:
            raw_sync = self._adapter.sync_portfolio()
            if raw_sync.get("error"):
                self._state.error = raw_sync["error"]
                return PortfolioSnapshot(positions=[], cash=0, timestamp=datetime.utcnow().isoformat())

            self._snapshot = normalize_groww_portfolio(
                raw_holdings=self._adapter.get_holdings(),
                positions_raw=self._adapter.get_positions(),
                cash=raw_sync.get("cash", 0),
            )
            self._state.holdings_count = len(self._snapshot.positions)
            self._state.positions_count = self._snapshot.position_count
            self._state.last_sync = datetime.utcnow().isoformat()
            self._state.error = ""
            return self._snapshot
        except Exception as exc:
            logger.debug("Groww sync failed: %s", type(exc).__name__)
            self._state.error = str(exc)
            return PortfolioSnapshot(positions=[], cash=0, timestamp=datetime.utcnow().isoformat())

    def get_snapshot(self) -> Optional[PortfolioSnapshot]:
        return self._snapshot

    # ─── Personalized Guidance ──────────────────────────────────────────

    def analyze_my_portfolio(self, market_context: str = "") -> PortfolioAdvice:
        """'Mere portfolio ko analyze karo' — the main guidance entry point."""
        if self._snapshot is None:
            self.sync_portfolio()
        if self._snapshot is None or not self._snapshot.positions:
            return PortfolioAdvice(
                overall_assessment="Portfolio khaali hai ya Groww se connect nahi ho paya.",
                portfolio_health="CRITICAL",
                total_invested=0, total_value=0, total_pnl=0, total_pnl_pct=0,
                day_pnl=0, cash_available=0, position_advices=[],
                sector_exposure={}, concentration_warnings=[],
                risk_warnings=["Portfolio data unavailable"],
                next_actions=["Groww connect karo ya positions add karo"],
                market_context=market_context,
                timestamp=datetime.utcnow().isoformat(),
            )

        ctx = market_context or self._market_context
        advice = self._guidance.analyze_portfolio(
            self._snapshot, self._technical_cache, ctx
        )
        self._state.last_guidance = datetime.utcnow().isoformat()
        self._state.guidance_count += 1
        return advice

    def get_stock_advice(self, symbol: str) -> StockGuidance:
        """'RELIANCE ke baare mein kya sochte ho?' — single stock guidance."""
        pos = None
        if self._snapshot:
            for p in self._snapshot.positions:
                if p.symbol.upper() == symbol.upper():
                    pos = p
                    break
        ta = self._technical_cache.get(symbol.upper())
        return self._guidance.get_stock_guidance(symbol, pos, ta)

    # ─── Market Data (via Groww) ────────────────────────────────────────

    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        """Get live quote from Groww."""
        return self._adapter.get_quote(symbol)

    def get_option_chain(self, underlying: str, expiry: str) -> Optional[OptionChain]:
        """Get option chain from Groww and normalize into Phase D model."""
        raw = self._adapter.get_option_chain(underlying, expiry)
        if not raw:
            return None
        quote = self._adapter.get_quote(underlying)
        price = quote.get("ltp", 0) if isinstance(quote, dict) else 0
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0.0
        return normalize_groww_option_chain(raw, underlying, price, expiry)

    # ─── Trading Engine Integration ─────────────────────────────────────

    def analyze_stock(self, symbol: str) -> Dict[str, Any]:
        """Run full Phase D analysis on a stock using Groww quote."""
        quote_raw = self._adapter.get_quote(symbol)
        if not quote_raw or quote_raw.get("error"):
            return {"error": quote_raw.get("error", "Quote unavailable"), "symbol": symbol}
        quote = normalize_groww_quote(quote_raw, symbol)
        if self._trading_engine is None:
            return {"error": "Trading engine not connected", "symbol": symbol}
        try:
            result = self._trading_engine.analyze_stock(symbol)
            result["groww_quote"] = {
                "symbol": quote.symbol,
                "price": quote.current_price,
                "change": quote.day_change_percent,
                "volume": quote.volume,
            }
            return result
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

    # ─── Health ─────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        return {
            "groww_connected": self.connected,
            "portfolio_positions": self._state.holdings_count,
            "last_sync": self._state.last_sync,
            "guidance_count": self._state.guidance_count,
            "auth": self._adapter.auth_state,
        }
