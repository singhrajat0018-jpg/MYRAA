"""
MYRAA Groww Trading Advisor — Browser-First Implementation

Professional trading companion that uses Groww web interface via browser automation
instead of Groww API. Advises only — never executes trades.

Architecture:
Groww Web → Default Browser (vision/OCR via UniversalController) →
Trading Models → Guidance Engine → Trading Intelligence Engine → Advice

This advisor implements the same interface as the API-based GrowwAdvisor
but uses vision-based browser data extraction underneath (MYRAA owns no
browser engine: the user's Windows default browser is observed on screen).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.broker.groww.guidance import (
    PersonalizedGuidanceEngine,
    PortfolioAdvice,
    StockGuidance,
)
from desktop_agent.finance.trading.models import (
    OptionChain,
    PortfolioSnapshot,
    TechnicalAnalysis,
)
from desktop_agent.finance.trading.groww_browser import (
    GrowwBrowserBridge,
    GrowwDataExtractor,
    TradingAdvisorPolicy,
)

logger = logging.getLogger(__name__)


@dataclass
class GrowwBrowserAdvisorState:
    """State tracking for the browser-based Groww advisor."""
    connected: bool = False
    holdings_count: int = 0
    positions_count: int = 0
    last_sync: Optional[str] = None
    last_guidance: Optional[str] = None
    guidance_count: int = 0
    error: str = ""
    session_state: str = "unknown"
    auth_method: str = "browser_based"


class GrowwBrowserAdvisor:
    """
    Professional trading companion backed by real Groww portfolio data via browser automation.
    Advises only — never executes trades.

    This is the browser-first implementation that reads the Groww web interface
    through the user's Windows default browser (observed via vision/OCR through
    UniversalController) instead of the Groww API.

    Usage:
        advisor = GrowwBrowserAdvisor()
        advice = advisor.analyze_my_portfolio()
        print(advice.overall_assessment)
    """

    def __init__(
        self,
        trading_engine=None,
        action_blocker: Optional[TradingAdvisorPolicy] = None,
        session_manager: Optional[Any] = None,  # GrowwSessionManager
        data_extractor: Optional[Any] = None,   # GrowwDataExtractor
        browser_bridge: Optional[Any] = None,   # GrowwBrowserBridge
        universal_controller: Optional[Any] = None,  # UniversalController
    ):
        # Use singleton instances if not provided
        self._browser_bridge = browser_bridge or GrowwBrowserBridge(
            action_blocker=action_blocker,
            session_manager=session_manager,
            data_extractor=data_extractor,
        )
        self._universal_controller = universal_controller
        self._data_extractor = data_extractor or GrowwDataExtractor()
        self._action_blocker = action_blocker or TradingAdvisorPolicy()
        self._guidance = PersonalizedGuidanceEngine()
        self._trading_engine = trading_engine
        self._state = GrowwBrowserAdvisorState()
        self._snapshot: Optional[PortfolioSnapshot] = None
        self._technical_cache: Dict[str, TechnicalAnalysis] = {}
        self._market_context: str = ""
        self._lock = threading.Lock()

        # Initialize browser bridge if needed
        try:
            # Try to get current session state
            session_check = self._browser_bridge.check_session()
            self._state.session_state = session_check.get("session_state", "unknown")
            self._state.connected = session_check.get("is_logged_in", False)
        except Exception as exc:
            logger.warning("Failed to initialize browser bridge session check: %s", exc)
            self._state.error = str(exc)

    @property
    def connected(self) -> bool:
        """Check if connected to Groww via browser session."""
        try:
            session_check = self._browser_bridge.check_session()
            connected = session_check.get("is_logged_in", False)
            self._state.connected = connected
            self._state.session_state = session_check.get("session_state", "unknown")
            return connected
        except Exception as exc:
            logger.debug("Browser session check failed: %s", exc)
            self._state.error = str(exc)
            self._state.connected = False
            return False

    @property
    def state(self) -> Dict[str, Any]:
        """Return current advisor state."""
        return {
            "connected": self.connected,
            "holdings_count": self._state.holdings_count,
            "positions_count": self._state.positions_count,
            "last_sync": self._state.last_sync,
            "last_guidance": self._state.last_guidance,
            "guidance_count": self._state.guidance_count,
            "error": self._state.error,
            "session_state": self._state.session_state,
            "auth_method": self._state.auth_method,
        }

    # ─── Core Portfolio Operations ──────────────────────────────────────

    def sync_portfolio(self) -> PortfolioSnapshot:
        """
        Pull latest holdings + positions from Groww web and build snapshot.

        Uses browser automation to navigate to Groww portfolio/positions pages
        and extracts data via DOM parsing.
        """
        try:
            # Navigate to portfolio page and extract data
            portfolio_result = self._browser_bridge.read_portfolio()

            if portfolio_result.get("status") != "ok":
                error_msg = portfolio_result.get("error", "Unknown error")
                logger.warning("Failed to read portfolio from Groww web: %s", error_msg)
                self._state.error = error_msg
                return PortfolioSnapshot(
                    positions=[],
                    cash=0.0,
                    timestamp=datetime.utcnow()
                )

            # Extract holdings and summary from browser data
            holdings_data = portfolio_result.get("data", {}).get("holdings", [])
            summary_data = portfolio_result.get("data", {}).get("summary", {})

            # Convert extracted holdings to PortfolioPosition objects
            positions = []
            for holding_dict in holdings_data:
                try:
                    position = PortfolioPosition(
                        symbol=holding_dict.get("symbol", ""),
                        quantity=float(holding_dict.get("quantity", 0)),
                        average_price=float(holding_dict.get("average_price", 0)),
                        current_price=float(holding_dict.get("current_price", 0)),
                        previous_close=float(holding_dict.get("previous_close", 0)),
                        exchange=holding_dict.get("exchange", "NSE"),
                        sector=holding_dict.get("sector", ""),
                        instrument_type=holding_dict.get("instrument_type", "EQUITY"),
                        notes=holding_dict.get("notes", ""),
                    )
                    positions.append(position)
                except (ValueError, TypeError) as exc:
                    logger.debug("Skipping invalid holding %s: %s",
                                 holding_dict.get("symbol", "unknown"), exc)
                    continue

            # Build portfolio snapshot
            self._snapshot = PortfolioSnapshot(
                positions=positions,
                cash=float(summary_data.get("cash", 0) or summary_data.get("total_invested", 0) -
                          sum(p.invested_value for p in positions)),
                timestamp=datetime.utcnow()
            )

            # Update state
            self._state.holdings_count = len(self._snapshot.positions)
            self._state.positions_count = self._snapshot.position_count
            self._state.last_sync = datetime.utcnow().isoformat()
            self._state.error = ""

            logger.info("Successfully synced portfolio via browser: %d positions",
                       len(self._snapshot.positions))

            return self._snapshot

        except Exception as exc:
            logger.error("Portfolio sync failed: %s", exc)
            self._state.error = str(exc)
            return PortfolioSnapshot(
                positions=[],
                cash=0.0,
                timestamp=datetime.utcnow()
            )

    def get_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Return the last synced portfolio snapshot."""
        return self._snapshot

    # ─── Personalized Guidance ────────────────────────────────────────

    def analyze_my_portfolio(self, market_context: str = "") -> PortfolioAdvice:
        """
        'Mere portfolio ko analyze karo' — the main guidance entry point.

        Syncs portfolio data from Groww web and provides personalized advice.
        """
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
        """
        'RELIANCE ke baare mein kya sochte ho?' — single stock guidance.
        """
        pos = None
        if self._snapshot:
            for p in self._snapshot.positions:
                if p.symbol.upper() == symbol.upper():
                    pos = p
                    break
        ta = self._technical_cache.get(symbol.upper())
        return self._guidance.get_stock_guidance(symbol, pos, ta)

    # ─── Market Data (via Groww Web) ────────────────────────────────

    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        """Get live quote from Groww web via browser automation."""
        try:
            # Navigate to stock detail page and extract quote
            stock_result = self._browser_bridge.read_stock_detail(symbol)

            if stock_result.get("status") != "ok":
                error_msg = stock_result.get("error", "Unknown error")
                logger.warning("Failed to get live quote for %s: %s", symbol, error_msg)
                return {
                    "error": error_msg,
                    "symbol": symbol,
                    "source": "groww_web"
                }

            quote_data = stock_result.get("data", {}).get("quote", {})
            if not quote_data:
                # Try to construct quote from other available data
                quote_data = {
                    "symbol": symbol.upper(),
                    "current_price": 0.0,
                    "previous_close": 0.0,
                    "open_price": 0.0,
                    "high_price": 0.0,
                    "low_price": 0.0,
                    "volume": 0,
                    "source": "groww_web"
                }

            # Ensure we have required fields
            result = {
                "symbol": quote_data.get("symbol", symbol.upper()),
                "current_price": float(quote_data.get("current_price", 0)),
                "previous_close": float(quote_data.get("previous_close", 0)),
                "open_price": float(quote_data.get("open_price", 0)),
                "high_price": float(quote_data.get("high_price", 0)),
                "low_price": float(quote_data.get("low_price", 0)),
                "volume": int(quote_data.get("volume", 0)),
                "source": "groww_web",
                "timestamp": datetime.utcnow().isoformat(),
                "data_quality": "LIVE" if self.connected else "UNAVAILABLE",
            }

            # Calculate derived fields
            if result["previous_close"] > 0:
                result["change"] = result["current_price"] - result["previous_close"]
                result["change_percent"] = (result["change"] / result["previous_close"]) * 100
            else:
                result["change"] = 0.0
                result["change_percent"] = 0.0

            if result["high_price"] > 0 and result["low_price"] > 0:
                result["spread"] = result["high_price"] - result["low_price"]
                if result["current_price"] > 0:
                    result["spread_percent"] = (result["spread"] / result["current_price"]) * 100
                else:
                    result["spread_percent"] = 0.0
            else:
                result["spread"] = 0.0
                result["spread_percent"] = 0.0

            return result

        except Exception as exc:
            logger.error("Failed to get live quote for %s: %s", symbol, exc)
            return {
                "error": str(exc),
                "symbol": symbol,
                "source": "groww_web"
            }

    def get_option_chain(self, underlying: str, expiry: str) -> Optional[OptionChain]:
        """Get option chain from Groww web and normalize into Phase D model."""
        try:
            # Navigate to option chain page and extract data
            option_result = self._browser_bridge.read_option_chain(underlying, expiry)

            if option_result.get("status") != "ok":
                error_msg = option_result.get("error", "Unknown error")
                logger.warning("Failed to get option chain for %s %s: %s",
                              underlying, expiry, error_msg)
                return None

            option_data = option_result.get("data", {})
            if not option_data:
                return None

            # Get underlying quote for price
            quote_result = self.get_live_quote(underlying)
            underlying_price = 0.0
            if quote_result and "error" not in quote_result:
                underlying_price = quote_result.get("current_price", 0)

            # Convert to OptionChain model
            return self._data_extractor.to_option_chain_model(
                option_data, underlying, underlying_price, expiry
            )

        except Exception as exc:
            logger.error("Failed to get option chain for %s %s: %s",
                        underlying, expiry, exc)
            return None

    # ─── Trading Engine Integration ────────────────────────────────

    def analyze_stock(self, symbol: str) -> Dict[str, Any]:
        """Run full Phase D analysis on a stock using Groww web quote."""
        quote_raw = self.get_live_quote(symbol)
        if not quote_raw or quote_raw.get("error"):
            return {"error": quote_raw.get("error", "Quote unavailable"), "symbol": symbol}

        if self._trading_engine is None:
            return {"error": "Trading engine not connected", "symbol": symbol}

        try:
            result = self._trading_engine.analyze_stock(symbol)
            result["groww_quote"] = {
                "symbol": quote_raw.get("symbol", symbol),
                "price": quote_raw.get("current_price", 0),
                "change": quote_raw.get("change_percent", 0),
                "volume": quote_raw.get("volume", 0),
                "source": "groww_web"
            }
            return result
        except Exception as exc:
            return {"error": str(exc), "symbol": symbol}

    # ─── Health ────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Return health information."""
        bridge_health = self._browser_bridge.get_health()
        return {
            "groww_connected": self.connected,
            "portfolio_positions": self._state.holdings_count,
            "last_sync": self._state.last_sync,
            "guidance_count": self._state.guidance_count,
            "session_state": self._state.session_state,
            "bridge_health": bridge_health,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ─── Additional Browser-Specific Methods ────────────────────────

    def check_session(self) -> Dict[str, Any]:
        """Check the current Groww web session state."""
        return self._browser_bridge.check_session()

    def open_groww(self, page_type: str = "portfolio") -> Dict[str, Any]:
        """Navigate to a specific Groww page."""
        from desktop_agent.finance.trading.groww_browser import GrowwPageType
        try:
            page_enum = GrowwPageType(page_type.lower())
            return self._browser_bridge.open_groww(page_enum)
        except ValueError:
            return self._browser_bridge._error_response(
                f"Invalid page type: {page_type}", ""
            )