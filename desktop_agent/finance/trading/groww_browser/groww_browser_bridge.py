"""Browser-First Groww Bridge — main integration point for browser-based data.

Connects browser tools to Groww analysis. This is a DATA LAYER, not an
analysis layer: it reads data from Groww web pages via the data extractor
and delegates analysis to the Trading Intelligence Engine.

Every navigation/click is gated through the TradingAdvisorPolicy blocker.
Every extraction is quality-checked for freshness and completeness.

Thread-safe singleton.
"""
from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Optional

from .groww_action_blocker import TradingAdvisorPolicy
from .groww_session import GrowwSessionManager, SessionState
from .groww_data_extractor import (
    GrowwDataExtractor,
    ExtractedHolding,
    GrowwPageState,
)

logger = logging.getLogger(__name__)


class GrowwPageType(Enum):
    """Known Groww page types for navigation and extraction routing."""

    HOME = "home"
    PORTFOLIO = "portfolio"
    HOLDINGS = "holdings"
    POSITIONS = "positions"
    ORDERS = "orders"
    WATCHLIST = "watchlist"
    CHARTS = "charts"
    OPTION_CHAIN = "option_chain"
    NIFTY = "nifty"
    BANKNIFTY = "banknifty"
    STOCK_DETAIL = "stock_detail"
    LOGIN = "login"
    UNKNOWN = "unknown"


class GrowwBrowserBridge:
    """Main integration point connecting browser tools to Groww analysis.

    Reads data from Groww web pages and provides structured results. All
    navigation is gated through the read-only TradingAdvisorPolicy. All
    extraction is quality-verified.

    Thread-safe singleton — all callers share the same session state.
    """

    _instance: Optional["GrowwBrowserBridge"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(
        cls,
        action_blocker: Optional[TradingAdvisorPolicy] = None,
        session_manager: Optional[GrowwSessionManager] = None,
        data_extractor: Optional[GrowwDataExtractor] = None,
    ) -> "GrowwBrowserBridge":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._action_blocker = action_blocker or TradingAdvisorPolicy()
                    inst._session_manager = session_manager or GrowwSessionManager()
                    inst._data_extractor = data_extractor or GrowwDataExtractor()
                    inst._state_lock = threading.Lock()
                    inst._last_session_state: SessionState = SessionState.UNKNOWN
                    inst._last_check_time: float = 0.0
                    inst._navigation_count: int = 0
                    inst._extraction_count: int = 0
                    inst._error_count: int = 0
                    cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Navigation / session
    # ------------------------------------------------------------------

    def open_groww(self, page_type: GrowwPageType = GrowwPageType.HOME) -> dict:
        """Navigate to a Groww page.

        Returns:
            dict with ``status``, ``page_type``, ``url``, ``session_state``,
            ``source``, ``timestamp``.
        """
        url = self._session_manager.build_url(page_type.value)
        return self._safe_navigate(url)

    def check_session(self) -> dict:
        """Detect the current Groww session state.

        Returns:
            dict with ``status``, ``session_state``, ``is_logged_in``,
            ``source``, ``timestamp``.
        """
        now = time.time()
        # Throttle checks to at most once per 30 seconds
        with self._state_lock:
            if now - self._last_check_time < 30 and self._last_session_state != SessionState.UNKNOWN:
                return {
                    "status": "ok",
                    "session_state": self._last_session_state.value,
                    "is_logged_in": self._last_session_state == SessionState.LOGGED_IN,
                    "source": "groww_session_cache",
                    "timestamp": now,
                }

        # To actually detect state we need page content — use a lightweight
        # read of the home page. If no content is available, return unknown.
        try:
            page_content = self._fetch_page_content("https://groww.in")
            state = self._session_manager.detect_session_state(page_content, "https://groww.in")
        except Exception as exc:
            logger.warning("Session check failed: %s", exc)
            state = SessionState.ERROR

        with self._state_lock:
            self._last_session_state = state
            self._last_check_time = time.time()

        return {
            "status": "ok",
            "session_state": state.value,
            "is_logged_in": state == SessionState.LOGGED_IN,
            "source": "groww_session",
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Data reading
    # ------------------------------------------------------------------

    def read_portfolio(self) -> dict:
        """Extract holdings and summary from Groww portfolio page.

        Returns:
            dict with ``status``, ``data`` (holdings + summary),
            ``page_state``, ``source``, ``timestamp``, ``confidence``.
        """
        url = self._session_manager.build_url("portfolio")
        nav_result = self._safe_navigate(url)
        if nav_result.get("status") != "ok":
            return self._error_response(f"Navigation failed: {nav_result.get('error', 'unknown')}", url)

        page_content = self._fetch_page_content(url)
        if not page_content:
            return self._error_response("Could not fetch page content", url)

        holdings, page_state = self._extract_and_verify(page_content, "portfolio")
        summary = self._data_extractor.extract_portfolio_summary(page_content)

        return {
            "status": "ok",
            "data": {
                "holdings": holdings,
                "summary": summary,
            },
            "page_state": {
                "url": page_state.url,
                "page_type": page_state.page_type,
                "is_loaded": page_state.is_loaded,
                "has_data": page_state.has_data,
                "element_count": page_state.element_count,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": page_state.extraction_confidence,
        }

    def read_positions(self) -> dict:
        """Extract positions from Groww positions page.

        Returns:
            dict with ``status``, ``data`` (positions list), ``page_state``,
            ``source``, ``timestamp``, ``confidence``.
        """
        url = self._session_manager.build_url("positions")
        nav_result = self._safe_navigate(url)
        if nav_result.get("status") != "ok":
            return self._error_response(f"Navigation failed: {nav_result.get('error', 'unknown')}", url)

        page_content = self._fetch_page_content(url)
        if not page_content:
            return self._error_response("Could not fetch page content", url)

        positions = self._data_extractor.extract_positions_from_dom(page_content)
        page_state = self._build_page_state(page_content, url, "positions", len(positions))

        return {
            "status": "ok",
            "data": {
                "positions": positions,
                "count": len(positions),
            },
            "page_state": {
                "url": page_state.url,
                "page_type": page_state.page_type,
                "is_loaded": page_state.is_loaded,
                "has_data": page_state.has_data,
                "element_count": page_state.element_count,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": page_state.extraction_confidence,
        }

    def read_orders(self) -> dict:
        """Extract orders from Groww orders page.

        Returns:
            dict with ``status``, ``data`` (orders list), ``page_state``,
            ``source``, ``timestamp``, ``confidence``.
        """
        url = self._session_manager.build_url("orders")
        nav_result = self._safe_navigate(url)
        if nav_result.get("status") != "ok":
            return self._error_response(f"Navigation failed: {nav_result.get('error', 'unknown')}", url)

        page_content = self._fetch_page_content(url)
        if not page_content:
            return self._error_response("Could not fetch page content", url)

        orders = self._data_extractor.extract_orders_from_dom(page_content)
        page_state = self._build_page_state(page_content, url, "orders", len(orders))

        return {
            "status": "ok",
            "data": {
                "orders": orders,
                "count": len(orders),
            },
            "page_state": {
                "url": page_state.url,
                "page_type": page_state.page_type,
                "is_loaded": page_state.is_loaded,
                "has_data": page_state.has_data,
                "element_count": page_state.element_count,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": page_state.extraction_confidence,
        }

    def read_stock_detail(self, symbol: str) -> dict:
        """Navigate to a stock detail page and extract quote data.

        Args:
            symbol: Stock symbol (e.g. ``RELIANCE``, ``TCS``).

        Returns:
            dict with ``status``, ``data`` (quote dict), ``page_state``,
            ``source``, ``timestamp``, ``confidence``.
        """
        if not symbol or not symbol.strip():
            return self._error_response("Symbol is required", "")

        normalised = symbol.strip().upper()
        url = self._session_manager.build_url("charts", normalised)
        nav_result = self._safe_navigate(url)
        if nav_result.get("status") != "ok":
            return self._error_response(
                f"Navigation failed for {normalised}: {nav_result.get('error', 'unknown')}",
                url,
            )

        page_content = self._fetch_page_content(url)
        if not page_content:
            return self._error_response(f"Could not fetch page content for {normalised}", url)

        # Extract whatever data is available from the stock page
        nifty_data = self._data_extractor.extract_nifty_data(page_content)
        page_state = self._build_page_state(page_content, url, "stock_detail", 1)

        # Build a minimal quote from whatever the page contains
        quote = {
            "symbol": normalised,
            "current_price": 0.0,
            "previous_close": 0.0,
            "open_price": 0.0,
            "high_price": 0.0,
            "low_price": 0.0,
            "volume": 0,
            "source": "GROWW_WEB",
        }
        # Attempt to extract price from page content
        import re
        price_match = re.search(
            r"₹\s*([\d,]+(?:\.\d+)?)",
            page_content,
        )
        if price_match:
            quote["current_price"] = self._data_extractor._parse_number(price_match.group(1))

        return {
            "status": "ok",
            "data": {
                "quote": quote,
                "nifty_context": nifty_data,
            },
            "page_state": {
                "url": page_state.url,
                "page_type": page_state.page_type,
                "is_loaded": page_state.is_loaded,
                "has_data": page_state.has_data,
                "element_count": page_state.element_count,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": page_state.extraction_confidence,
        }

    def read_nifty(self) -> dict:
        """Read NIFTY 50 index data from Groww.

        Returns:
            dict with ``status``, ``data`` (NIFTY value, change, pct),
            ``page_state``, ``source``, ``timestamp``, ``confidence``.
        """
        url = self._session_manager.build_url("nifty")
        nav_result = self._safe_navigate(url)
        if nav_result.get("status") != "ok":
            return self._error_response(f"Navigation failed: {nav_result.get('error', 'unknown')}", url)

        page_content = self._fetch_page_content(url)
        if not page_content:
            return self._error_response("Could not fetch page content", url)

        nifty_data = self._data_extractor.extract_nifty_data(page_content)
        page_state = self._build_page_state(page_content, url, "nifty", 1 if nifty_data.get("is_available") else 0)

        return {
            "status": "ok",
            "data": nifty_data,
            "page_state": {
                "url": page_state.url,
                "page_type": page_state.page_type,
                "is_loaded": page_state.is_loaded,
                "has_data": page_state.has_data,
                "element_count": page_state.element_count,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": page_state.extraction_confidence,
        }

    def read_option_chain(self, symbol: str) -> dict:
        """Read option chain data from Groww.

        Args:
            symbol: Underlying symbol (e.g. ``NIFTY``, ``BANKNIFTY``, ``RELIANCE``).

        Returns:
            dict with ``status``, ``data`` (calls, puts, strikes),
            ``page_state``, ``source``, ``timestamp``, ``confidence``.
        """
        if not symbol or not symbol.strip():
            return self._error_response("Symbol is required", "")

        normalised = symbol.strip().upper()
        url = self._session_manager.build_url("option_chain", normalised)
        nav_result = self._safe_navigate(url)
        if nav_result.get("status") != "ok":
            return self._error_response(
                f"Navigation failed for {normalised} options: {nav_result.get('error', 'unknown')}",
                url,
            )

        page_content = self._fetch_page_content(url)
        if not page_content:
            return self._error_response(f"Could not fetch option chain for {normalised}", url)

        option_data = self._data_extractor.extract_option_chain(page_content)
        page_state = self._build_page_state(
            page_content, url, "option_chain",
            len(option_data.get("calls", [])) + len(option_data.get("puts", [])),
        )

        return {
            "status": "ok",
            "data": option_data,
            "page_state": {
                "url": page_state.url,
                "page_type": page_state.page_type,
                "is_loaded": page_state.is_loaded,
                "has_data": page_state.has_data,
                "element_count": page_state.element_count,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": page_state.extraction_confidence,
        }

    # ------------------------------------------------------------------
    # Analysis (read + delegate)
    # ------------------------------------------------------------------

    def analyze_portfolio(self) -> dict:
        """Read portfolio and prepare analysis context.

        This bridge does NOT perform analysis — it reads data and prepares
        a context dict suitable for the Trading Intelligence Engine.

        Returns:
            dict with ``status``, ``data`` (readings), ``source``,
            ``timestamp``, ``confidence``.
        """
        readings = self.read_portfolio()
        if readings.get("status") != "ok":
            return readings

        context = self._build_analysis_context(readings)
        return {
            "status": "ok",
            "data": {
                "readings": readings.get("data"),
                "analysis_context": context,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": readings.get("confidence", 0.0),
            "note": "Data layer only — delegate to Trading Intelligence Engine for analysis",
        }

    def analyze_stock(self, symbol: str) -> dict:
        """Read stock detail and prepare analysis context.

        Returns:
            dict with ``status``, ``data`` (readings + context), ``source``,
            ``timestamp``, ``confidence``.
        """
        if not symbol or not symbol.strip():
            return self._error_response("Symbol is required", "")

        readings = self.read_stock_detail(symbol)
        if readings.get("status") != "ok":
            return readings

        context = self._build_analysis_context(readings)
        return {
            "status": "ok",
            "data": {
                "readings": readings.get("data"),
                "analysis_context": context,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": readings.get("confidence", 0.0),
            "note": "Data layer only — delegate to Trading Intelligence Engine for analysis",
        }

    def analyze_nifty(self) -> dict:
        """Read NIFTY data and prepare analysis context.

        Returns:
            dict with ``status``, ``data`` (readings + context), ``source``,
            ``timestamp``, ``confidence``.
        """
        readings = self.read_nifty()
        if readings.get("status") != "ok":
            return readings

        context = self._build_analysis_context(readings)
        return {
            "status": "ok",
            "data": {
                "readings": readings.get("data"),
                "analysis_context": context,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": readings.get("confidence", 0.0),
            "note": "Data layer only — delegate to Trading Intelligence Engine for analysis",
        }

    def analyze_options(self, symbol: str) -> dict:
        """Read option chain and prepare analysis context.

        Returns:
            dict with ``status``, ``data`` (readings + context), ``source``,
            ``timestamp``, ``confidence``.
        """
        if not symbol or not symbol.strip():
            return self._error_response("Symbol is required", "")

        readings = self.read_option_chain(symbol)
        if readings.get("status") != "ok":
            return readings

        context = self._build_analysis_context(readings)
        return {
            "status": "ok",
            "data": {
                "readings": readings.get("data"),
                "analysis_context": context,
            },
            "source": "groww_web",
            "timestamp": time.time(),
            "confidence": readings.get("confidence", 0.0),
            "note": "Data layer only — delegate to Trading Intelligence Engine for analysis",
        }

    # ------------------------------------------------------------------
    # Health / stats
    # ------------------------------------------------------------------

    def get_health(self) -> dict:
        """Return health information about the bridge.

        Returns:
            dict with ``status``, ``session_state``, ``extraction_stats``,
            ``blocker_stats``, ``navigation_count``, ``error_count``,
            ``timestamp``.
        """
        session_info = self._session_manager.get_session_info()
        extraction_stats = self._data_extractor.get_extraction_stats()
        blocked_history = self._action_blocker.get_blocked_history()

        return {
            "status": "ok",
            "session_state": session_info.get("state", "unknown"),
            "last_check_time": session_info.get("last_check_time", 0.0),
            "extraction_stats": extraction_stats,
            "blocker_stats": {
                "total_blocked": len(blocked_history),
                "recent_blocks": [
                    {
                        "action": b.action_type,
                        "element": b.element_text,
                        "reason": b.blocked_reason,
                    }
                    for b in blocked_history[-5:]
                ],
            },
            "navigation_count": self._navigation_count,
            "extraction_count": self._extraction_count,
            "error_count": self._error_count,
            "timestamp": time.time(),
        }

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Intended for testing only."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_navigate(self, url: str) -> dict:
        """Check the action blocker before navigating, then perform navigation.

        Returns:
            dict with ``status`` (``ok`` or ``blocked``/``error``),
            ``url``, ``source``, ``timestamp``, and optionally ``error``.
        """
        # Gate through the read-only policy
        allowed, reason = self._action_blocker.checkNavigation(url)
        if not allowed:
            logger.warning("Navigation BLOCKED: %s — %s", url, reason)
            return {
                "status": "blocked",
                "url": url,
                "reason": reason,
                "source": "action_blocker",
                "timestamp": time.time(),
            }

        # Perform the navigation (delegates to browser tools externally)
        # For now we record the attempt and return success — the actual
        # browser page content is fetched separately via _fetch_page_content.
        with self._state_lock:
            self._navigation_count += 1

        logger.debug("Navigating to %s", url)
        return {
            "status": "ok",
            "url": url,
            "source": "groww_browser",
            "timestamp": time.time(),
        }

    def _extract_and_verify(
        self, page_content: str, page_type: str
    ) -> tuple[list[ExtractedHolding], GrowwPageState]:
        """Extract holdings and verify data quality.

        Returns:
            Tuple of (holdings list, page state).
        """
        holdings = self._data_extractor.extract_holdings_from_dom(page_content)
        is_stale = self._data_extractor._detect_data_freshness(page_content)

        page_state = GrowwPageState(
            url="",
            page_type=page_type,
            is_loaded=len(page_content) > 100,
            has_data=len(holdings) > 0 and not is_stale,
            element_count=len(holdings),
            extraction_confidence=self._data_extractor._calculate_confidence(
                len(holdings), 1
            ),
        )

        if is_stale:
            logger.warning("Detected stale/loading indicators on %s page", page_type)
            for h in holdings:
                h.is_stale = True

        with self._state_lock:
            self._extraction_count += 1

        return holdings, page_state

    def _build_analysis_context(self, readings: dict) -> dict:
        """Combine reading results into a context dict for analysis.

        This does NOT perform analysis — it structures the raw data so
        the Trading Intelligence Engine can consume it.
        """
        return {
            "source": "groww_web",
            "timestamp": time.time(),
            "data_freshness": "live" if not readings.get("page_state", {}).get("has_data") is False else "unknown",
            "readings": readings.get("data", {}),
            "confidence": readings.get("confidence", 0.0),
        }

    def _build_page_state(
        self,
        page_content: str,
        url: str,
        page_type: str,
        data_count: int,
    ) -> GrowwPageState:
        """Build a GrowwPageState from page content and extraction results."""
        is_stale = self._data_extractor._detect_data_freshness(page_content)
        has_data = data_count > 0 and not is_stale
        confidence = self._data_extractor._calculate_confidence(
            1 if has_data else 0, 1
        )
        return GrowwPageState(
            url=url,
            page_type=page_type,
            is_loaded=len(page_content) > 100,
            has_data=has_data,
            element_count=data_count,
            extraction_confidence=confidence,
        )

    def _fetch_page_content(self, url: str) -> str:
        """Fetch page content from a URL.

        This is a synchronous placeholder to be replaced by vision-based
        extraction (screenshot + OCR through the default browser, via
        UniversalController). Returns empty string on failure.
        """
        try:
            # In production this calls the browser tool to get DOM content.
            # For now, return empty — the real bridge is wired externally.
            logger.debug("Fetching page content for %s (stub)", url)
            return ""
        except Exception as exc:
            logger.error("Failed to fetch page content for %s: %s", url, exc)
            with self._state_lock:
                self._error_count += 1
            return ""

    @staticmethod
    def _error_response(message: str, url: str) -> dict:
        """Build a standardised error response dict."""
        return {
            "status": "error",
            "error": message,
            "url": url,
            "source": "groww_browser_bridge",
            "timestamp": time.time(),
        }
