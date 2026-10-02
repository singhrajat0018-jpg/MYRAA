"""
Browser-based Groww Data Extraction — DOM parsing and data normalization.

Parses raw HTML/DOM content from Groww web pages into structured data
classes (holdings, positions, orders, option chains, NIFTY data). Handles
Indian number formatting, missing data, staleness detection, and confidence
scoring.

Thread-safe singleton — all extraction state is shared.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtractedHolding:
    """A single equity holding extracted from Groww portfolio page."""

    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    market_value: float
    invested_value: float
    pnl: float
    pnl_percent: float
    day_change: float
    source: str = "GROWW_WEB"
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.9
    is_stale: bool = False


@dataclass
class ExtractedPosition:
    """A derivative position extracted from Groww positions page."""

    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    pnl: float
    pnl_percent: float
    position_type: str
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None
    source: str = "GROWW_WEB"
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.9


@dataclass
class ExtractedOrder:
    """An order extracted from Groww order history."""

    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    status: str
    order_type: str
    timestamp: float = field(default_factory=time.time)
    exchange_timestamp: Optional[float] = None


@dataclass
class GrowwPageState:
    """Metadata about the state of the extracted page."""

    url: str
    page_type: str
    is_loaded: bool
    has_data: bool
    element_count: int
    timestamp: float = field(default_factory=time.time)
    extraction_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Regex helpers for DOM parsing
# ---------------------------------------------------------------------------

_TABLE_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_TABLE_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
_DIV_CONTENT_RE = re.compile(r"<div[^>]*class=\"[^\"]*\"[^>]*>(.*?)</div>", re.DOTALL | re.IGNORECASE)
_SPAN_TEXT_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.DOTALL | re.IGNORECASE)
_STRIP_HTML_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# Indian number patterns: ₹1,23,456.78 or 1,23,456.78
_INDIAN_NUMBER_RE = re.compile(
    r"₹?\s*(-?[\d,]+(?:\.\d+)?)"
)


# ---------------------------------------------------------------------------
# Data extractor
# ---------------------------------------------------------------------------

class GrowwDataExtractor:
    """Parses Groww web page content into structured financial data.

    Thread-safe singleton. Bounded extraction stats (max 500).
    """

    _instance: Optional["GrowwDataExtractor"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "GrowwDataExtractor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._stats_lock = threading.Lock()
                    inst._total_extractions: int = 0
                    inst._successful_extractions: int = 0
                    inst._confidence_sum: float = 0.0
                    inst._recent_extractions: list[dict] = []
                    cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Public extraction methods
    # ------------------------------------------------------------------

    def extract_portfolio(self, page_content: str, url: str) -> dict:
        """Extract holdings and page state from a Groww portfolio page.

        Returns:
            dict with keys ``holdings`` (list[ExtractedHolding]) and
            ``page_state`` (GrowwPageState).
        """
        page_state = self._build_page_state(url, "portfolio", page_content)
        holdings = self.extract_holdings_from_dom(page_content)
        summary = self.extract_portfolio_summary(page_content)

        is_stale = self._detect_data_freshness(page_content)
        for h in holdings:
            h.is_stale = is_stale

        with self._stats_lock:
            self._total_extractions += 1
            if holdings:
                self._successful_extractions += 1
            self._confidence_sum += page_state.extraction_confidence
            self._record_extraction("portfolio", url, len(holdings))

        return {
            "holdings": holdings,
            "summary": summary,
            "page_state": page_state,
        }

    def extract_holdings_from_dom(self, page_content: str) -> list[ExtractedHolding]:
        """Parse individual holding rows from Groww portfolio HTML.

        Attempts to locate tabular or card-based holding data and returns
        one ``ExtractedHolding`` per detected row.
        """
        holdings: list[ExtractedHolding] = []
        content_lower = page_content.lower()

        # Identify table rows in the DOM
        rows = _TABLE_ROW_RE.findall(page_content)
        for row_html in rows:
            cells = _TABLE_CELL_RE.findall(row_html)
            if len(cells) < 5:
                continue
            cleaned = [self._strip_html(c).strip() for c in cells]
            holding = self._try_parse_holding_row(cleaned)
            if holding is not None:
                holdings.append(holding)

        # Fallback: card / div-based layouts
        if not holdings:
            holdings = self._parse_holdings_from_divs(page_content)

        # Fallback: detect plain-text portfolio lists (pre-render / SSR)
        if not holdings:
            holdings = self._parse_holdings_from_text(content_lower)

        logger.debug("Extracted %d holdings from DOM", len(holdings))
        return holdings

    def extract_holdings_from_ui_targets(self, ui_targets: List[Dict[str, Any]]) -> List[ExtractedHolding]:
        """Extract holdings from a list of UI targets (from ContinuousVisionController).

        Groups UI targets into rows based on vertical position, then attempts
        to parse each row as a holding.
        """
        if not ui_targets:
            return []

        # Group UI targets into rows
        rows = self._group_ui_targets_into_rows(ui_targets)
        holdings: List[ExtractedHolding] = []

        for row in rows:
            # Extract text from each UI target in the row, sorted by x (left to right)
            cells = [target.get("text", "").strip() for target in sorted(row, key=lambda t: t.get("x", 0))]
            if len(cells) < 4:
                continue
            holding = self._try_parse_holding_row(cells)
            if holding is not None:
                holdings.append(holding)

        logger.debug("Extracted %d holdings from UI targets", len(holdings))
        return holdings

    def extract_positions_from_dom(self, page_content: str) -> list[ExtractedPosition]:
        """Parse position rows from Groww positions page HTML."""
        positions: list[ExtractedPosition] = []

        rows = _TABLE_ROW_RE.findall(page_content)
        for row_html in rows:
            cells = _TABLE_CELL_RE.findall(row_html)
            if len(cells) < 4:
                continue
            cleaned = [self._strip_html(c).strip() for c in cells]
            pos = self._try_parse_position_row(cleaned)
            if pos is not None:
                positions.append(pos)

        if not positions:
            positions = self._parse_positions_from_divs(page_content)

        logger.debug("Extracted %d positions from DOM", len(positions))
        return positions

    def extract_positions_from_ui_targets(self, ui_targets: List[Dict[str, Any]]) -> List[ExtractedPosition]:
        """Extract positions from a list of UI targets (from ContinuousVisionController)."""
        if not ui_targets:
            return []

        rows = self._group_ui_targets_into_rows(ui_targets)
        positions: List[ExtractedPosition] = []

        for row in rows:
            cells = [target.get("text", "").strip() for target in sorted(row, key=lambda t: t.get("x", 0))]
            if len(cells) < 3:
                continue
            pos = self._try_parse_position_row(cells)
            if pos is not None:
                positions.append(pos)

        logger.debug("Extracted %d positions from UI targets", len(positions))
        return positions

    def extract_orders_from_dom(self, page_content: str) -> list[ExtractedOrder]:
        """Parse order rows from Groww orders page HTML."""
        orders: list[ExtractedOrder] = []

        rows = _TABLE_ROW_RE.findall(page_content)
        for row_html in rows:
            cells = _TABLE_CELL_RE.findall(row_html)
            if len(cells) < 5:
                continue
            cleaned = [self._strip_html(c).strip() for c in cells]
            order = self._try_parse_order_row(cleaned)
            if order is not None:
                orders.append(order)

        logger.debug("Extracted %d orders from DOM", len(orders))
        return orders

    def extract_orders_from_ui_targets(self, ui_targets: List[Dict[str, Any]]) -> List[ExtractedOrder]:
        """Extract orders from a list of UI targets (from ContinuousVisionController)."""
        if not ui_targets:
            return []

        rows = self._group_ui_targets_into_rows(ui_targets)
        orders: List[ExtractedOrder] = []

        for row in rows:
            cells = [target.get("text", "").strip() for target in sorted(row, key=lambda t: t.get("x", 0))]
            if len(cells) < 5:
                continue
            order = self._try_parse_order_row(cells)
            if order is not None:
                orders.append(order)

        logger.debug("Extracted %d orders from UI targets", len(orders))
        return orders

    def extract_portfolio_summary(self, page_content: str) -> dict:
        """Extract portfolio summary values (total value, day P&L, total P&L).

        Returns:
            dict with keys ``total_invested``, ``total_current_value``,
            ``total_pnl``, ``total_pnl_percent``, ``day_pnl``,
            ``day_pnl_percent``.
        """
        summary: dict[str, Any] = {
            "total_invested": 0.0,
            "total_current_value": 0.0,
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0,
            "day_pnl": 0.0,
            "day_pnl_percent": 0.0,
        }
        content_lower = page_content.lower()

        summary["total_invested"] = self._extract_value_near_label(
            content_lower,
            ["invested", "total investment", "total invested", "amount invested"],
        )
        summary["total_current_value"] = self._extract_value_near_label(
            content_lower,
            ["current value", "current amount", "portfolio value", "total value"],
        )
        summary["total_pnl"] = self._extract_value_near_label(
            content_lower,
            ["total pnl", "total profit", "overall pnl", "profit & loss", "profit and loss"],
        )
        summary["day_pnl"] = self._extract_value_near_label(
            content_lower,
            ["day pnl", "today pnl", "daily pnl", "day change"],
        )

        # Calculate derived values
        if summary["total_invested"] > 0 and summary["total_current_value"] > 0:
            if summary["total_pnl"] == 0.0:
                summary["total_pnl"] = summary["total_current_value"] - summary["total_invested"]
            summary["total_pnl_percent"] = (
                (summary["total_pnl"] / summary["total_invested"]) * 100
            )

        return summary

    def extract_portfolio_summary_from_ui_targets(self, ui_targets: List[Dict[str, Any]]) -> dict:
        """Extract portfolio summary from a list of UI targets."""
        summary: dict[str, Any] = {
            "total_invested": 0.0,
            "total_current_value": 0.0,
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0,
            "day_pnl": 0.0,
            "day_pnl_percent": 0.0,
        }

        # We'll search for labels in the text of UI targets and look for nearby numbers
        # For simplicity, we'll concatenate all text and search (less accurate but works)
        all_text = " ".join([target.get("text", "").lower() for target in ui_targets])

        summary["total_invested"] = self._extract_value_near_label(
            all_text,
            ["invested", "total investment", "total invested", "amount invested"],
        )
        summary["total_current_value"] = self._extract_value_near_label(
            all_text,
            ["current value", "current amount", "portfolio value", "total value"],
        )
        summary["total_pnl"] = self._extract_value_near_label(
            all_text,
            ["total pnl", "total profit", "overall pnl", "profit & loss", "profit and loss"],
        )
        summary["day_pnl"] = self._extract_value_near_label(
            all_text,
            ["day pnl", "today pnl", "daily pnl", "day change"],
        )

        # Calculate derived values
        if summary["total_invested"] > 0 and summary["total_current_value"] > 0:
            if summary["total_pnl"] == 0.0:
                summary["total_pnl"] = summary["total_current_value"] - summary["total_invested"]
            summary["total_pnl_percent"] = (
                (summary["total_pnl"] / summary["total_invested"]) * 100
            )

        return summary

    def extract_nifty_data(self, page_content: str) -> dict:
        """Extract NIFTY 50 index data from Groww page content.

        Returns:
            dict with ``value``, ``change``, ``change_percent``.
        """
        data: dict[str, Any] = {
            "value": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "is_available": False,
        }
        content_lower = page_content.lower()

        # Look for NIFTY heading
        nifty_patterns = [
            r"nifty\s*50[^0-9]*?([\d,]+(?:\.\d+)?)",
            r"nifty\s*[^0-9]*?([\d,]+(?:\.\d+)?)",
            r"nift50[^0-9]*?([\d,]+(?:\.\d+)?)",
        ]
        for pattern in nifty_patterns:
            match = re.search(pattern, content_lower)
            if match:
                val = self._parse_number(match.group(1))
                if val > 1000:  # sanity — NIFTY is always > 1000
                    data["value"] = val
                    data["is_available"] = True
                    break

        # Change value
        change_patterns = [
            r"nifty[^0-9]*?[\d,.]+[^-+]*?([-+][\d,.]+)",
            r"change[^0-9]*?([-+]?[\d,.]+)",
            r"day change[^0-9]*?([-+]?[\d,.]+)",
        ]
        for pattern in change_patterns:
            match = re.search(pattern, content_lower)
            if match:
                change_val = self._parse_number(match.group(1))
                if abs(change_val) < 5000:  # sanity for NIFTY daily change
                    data["change"] = change_val
                    break

        # Percentage change
        pct_patterns = [
            r"([\d.]+)\s*%\s*(?:change|up|down)",
            r"(?:up|down|change)\s*([\d.]+)\s*%",
            r"([-+]?\d+\.?\d*)\s*%",
        ]
        for pattern in pct_patterns:
            match = re.search(pattern, content_lower)
            if match:
                pct = self._parse_number(match.group(1))
                if abs(pct) < 20:  # sanity for NIFTY daily %
                    data["change_percent"] = pct
                    break

        return data

    def extract_nifty_data_from_ui_targets(self, ui_targets: List[Dict[str, Any]]) -> dict:
        """Extract NIFTY data from a list of UI targets."""
        data: dict[str, Any] = {
            "value": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "is_available": False,
        }

        all_text = " ".join([target.get("text", "").lower() for target in ui_targets])

        # Look for NIFTY heading
        nifty_patterns = [
            r"nifty\s*50[^0-9]*?([\d,]+(?:\.\d+)?)",
            r"nifty\s*[^0-9]*?([\d,]+(?:\.\d+)?)",
            r"nift50[^0-9]*?([\d,]+(?:\.\d+)?)",
        ]
        for pattern in nifty_patterns:
            match = re.search(pattern, all_text)
            if match:
                val = self._parse_number(match.group(1))
                if val > 1000:  # sanity — NIFTY is always > 1000
                    data["value"] = val
                    data["is_available"] = True
                    break

        # Change value
        change_patterns = [
            r"nifty[^0-9]*?[\d,.]+[^-+]*?([-+][\d,.]+)",
            r"change[^0-9]*?([-+]?[\d,.]+)",
            r"day change[^0-9]*?([-+]?[\d,.]+)",
        ]
        for pattern in change_patterns:
            match = re.search(pattern, all_text)
            if match:
                change_val = self._parse_number(match.group(1))
                if abs(change_val) < 5000:  # sanity for NIFTY daily change
                    data["change"] = change_val
                    break

        # Percentage change
        pct_patterns = [
            r"([\d.]+)\s*%\s*(?:change|up|down)",
            r"(?:up|down|change)\s*([\d.]+)\s*%",
            r"([-+]?\d+\.?\d*)\s*%",
        ]
        for pattern in pct_patterns:
            match = re.search(pattern, all_text)
            if match:
                pct = self._parse_number(match.group(1))
                if abs(pct) < 20:  # sanity for NIFTY daily %
                    data["change_percent"] = pct
                    break

        return data

    def extract_option_chain(self, page_content: str) -> dict:
        """Extract option chain data from Groww options page.

        Returns:
            dict with ``calls`` (list[dict]), ``puts`` (list[dict]),
            ``strikes`` (list[float]).
        """
        result: dict[str, Any] = {
            "calls": [],
            "puts": [],
            "strikes": [],
            "is_available": False,
        }
        content_lower = page_content.lower()

        # Locate option chain table
        rows = _TABLE_ROW_RE.findall(page_content)
        strikes_seen: set[float] = set()

        for row_html in rows:
            cells = _TABLE_CELL_RE.findall(row_html)
            cleaned = [self._strip_html(c).strip() for c in cells]
            contract = self._try_parse_option_row(cleaned)
            if contract is not None:
                strike = contract.get("strike", 0.0)
                if strike > 0:
                    strikes_seen.add(strike)
                if contract.get("option_type") == "CE":
                    result["calls"].append(contract)
                elif contract.get("option_type") == "PE":
                    result["puts"].append(contract)
                result["is_available"] = True

        result["strikes"] = sorted(strikes_seen)
        return result

    def extract_option_chain_from_ui_targets(self, ui_targets: List[Dict[str, Any]]) -> dict:
        """Extract option chain from a list of UI targets."""
        result: dict[str, Any] = {
            "calls": [],
            "puts": [],
            "strikes": [],
            "is_available": False,
        }

        # We'll try to group UI targets into rows and parse each row as an option contract
        rows = self._group_ui_targets_into_rows(ui_targets)
        strikes_seen: set[float] = set()

        for row in rows:
            cells = [target.get("text", "").strip() for target in sorted(row, key=lambda t: t.get("x", 0))]
            contract = self._try_parse_option_row(cells)
            if contract is not None:
                strike = contract.get("strike", 0.0)
                if strike > 0:
                    strikes_seen.add(strike)
                if contract.get("option_type") == "CE":
                    result["calls"].append(contract)
                elif contract.get("option_type") == "PE":
                    result["puts"].append(contract)
                result["is_available"] = True

        result["strikes"] = sorted(strikes_seen)
        return result

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_market_quote(self, holding: ExtractedHolding) -> dict:
        """Convert an ExtractedHolding to a MarketQuote-compatible dict.

        Uses ``finance.market.market_provider.MarketQuote`` field names.
        """
        prev_close = holding.current_price - holding.day_change if holding.day_change else 0.0
        return {
            "symbol": holding.symbol,
            "current_price": holding.current_price,
            "previous_close": prev_close,
            "open_price": 0.0,
            "high_price": 0.0,
            "low_price": 0.0,
            "volume": 0,
            "source": holding.source,
        }

    def to_portfolio_position(self, holding: ExtractedHolding) -> dict:
        """Convert an ExtractedHolding to a PortfolioPosition-compatible dict.

        Uses ``finance.trading.models.PortfolioPosition`` field names.
        """
        return {
            "symbol": holding.symbol,
            "quantity": float(holding.quantity),
            "average_price": holding.avg_price,
            "current_price": holding.current_price,
            "previous_close": holding.current_price - holding.day_change,
            "exchange": "NSE",
            "sector": "",
            "instrument_type": "EQUITY",
            "notes": "",
        }

    def to_portfolio_snapshot(
        self,
        holdings: list[ExtractedHolding],
        summary: dict,
    ) -> dict:
        """Convert holdings + summary to a PortfolioSnapshot-compatible dict.

        Uses ``finance.trading.models.PortfolioSnapshot`` field names.
        """
        positions = [self.to_portfolio_position(h) for h in holdings]
        return {
            "positions": positions,
            "cash": 0.0,
            "total_invested": summary.get("total_invested", 0.0),
            "total_market_value": summary.get("total_current_value", 0.0),
            "total_pnl": summary.get("total_pnl", 0.0),
            "total_pnl_percent": summary.get("total_pnl_percent", 0.0),
            "day_pnl": summary.get("day_pnl", 0.0),
            "position_count": len(positions),
        }

    def get_extraction_stats(self) -> dict:
        """Return cumulative extraction statistics.

        Returns:
            dict with ``total_extractions``, ``successful_extractions``,
            ``success_rate``, ``avg_confidence``, ``recent_count``.
        """
        with self._stats_lock:
            total = self._total_extractions
            success = self._successful_extractions
            avg_conf = (
                self._confidence_sum / total if total > 0 else 0.0
            )
            return {
                "total_extractions": total,
                "successful_extractions": success,
                "success_rate": success / total if total > 0 else 0.0,
                "avg_confidence": avg_conf,
                "recent_count": len(self._recent_extractions),
            }

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Intended for testing only."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Internal parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags and collapse whitespace."""
        clean = _STRIP_HTML_RE.sub("", text)
        return _WHITESPACE_RE.sub(" ", clean).strip()

    @staticmethod
    def _parse_number(text: str) -> float:
        """Parse a number string, handling Indian formatting (commas, ₹).

        Handles: ``₹1,23,456.78``, ``-12.5%``, ``1,234``, ``12.5``.
        Returns ``0.0`` on failure or NaN.
        """
        if not text or not text.strip():
            return 0.0
        cleaned = text.strip()
        # Remove currency symbols, percentage signs, whitespace
        for prefix in ("₹", "INR", "inr", "Rs.", "Rs", "rs.", "rs"):
            cleaned = cleaned.replace(prefix, "")
        cleaned = cleaned.replace("%", "").replace(",", "").strip()
        # Handle plus sign
        cleaned = cleaned.lstrip("+")
        if not cleaned:
            return 0.0
        try:
            value = float(cleaned)
            if math.isnan(value) or math.isinf(value):
                return 0.0
            return value
        except (ValueError, OverflowError):
            return 0.0

    @staticmethod
    def _parse_quantity(text: str) -> int:
        """Parse a quantity string to int, stripping commas and whitespace."""
        cleaned = text.strip().replace(",", "").replace("₹", "").strip()
        try:
            return int(float(cleaned))
        except (ValueError, OverflowError):
            return 0

    def _detect_data_freshness(self, page_content: str) -> bool:
        """Detect whether the page content appears stale or still loading.

        Returns ``True`` if stale indicators are found.
        """
        content_lower = page_content.lower()
        stale_indicators = [
            "loading",
            "please wait",
            "spinner",
            "fetching data",
            "refreshing",
            "data not available",
            "no data",
            "market closed",
            "after market",
            "previous close",
            "last updated",
        ]
        return any(indicator in content_lower for indicator in stale_indicators)

    @staticmethod
    def _calculate_confidence(extracted_count: int, expected_count: int) -> float:
        """Calculate extraction confidence based on coverage.

        Returns a float between 0.0 and 1.0.
        """
        if expected_count <= 0:
            return 0.5
        ratio = min(extracted_count / expected_count, 1.0)
        return round(0.5 + (ratio * 0.5), 2)

    def _build_page_state(
        self, url: str, page_type: str, content: str
    ) -> GrowwPageState:
        """Build a GrowwPageState from raw page content."""
        content_lower = content.lower()
        has_data = not self._detect_data_freshness(content)
        # Count DOM elements as a rough signal of page load completeness
        element_count = len(_TABLE_ROW_RE.findall(content)) + len(
            _DIV_CONTENT_RE.findall(content)
        )
        confidence = self._calculate_confidence(
            1 if has_data else 0, 1
        )
        return GrowwPageState(
            url=url,
            page_type=page_type,
            is_loaded=element_count > 0,
            has_data=has_data,
            element_count=element_count,
            extraction_confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Row parsers
    # ------------------------------------------------------------------

    def _try_parse_holding_row(self, cells: List[str]) -> Optional[ExtractedHolding]:
        """Attempt to parse a table row into an ExtractedHolding.

        Groww holding rows typically have columns like:
        Symbol | Qty | Avg Price | Current Price | P&L | Day Change
        The parser is lenient about column order.
        """
        if len(cells) < 4:
            return None

        # Find symbol: first cell that looks like a ticker (all upper, 2-10 chars)
        symbol = ""
        for cell in cells:
            stripped = cell.strip()
            if re.match(r"^[A-Z]{2,10}$", stripped):
                symbol = stripped
                break
        if not symbol:
            # Fallback: use first non-numeric cell
            for cell in cells:
                stripped = cell.strip()
                if stripped and not self._is_numeric_only(stripped):
                    symbol = re.sub(r"[^A-Z0-9]", "", stripped.upper())
                    if len(symbol) >= 2:
                        break
        if not symbol:
            return None

        # Extract numeric values
        numbers = [self._parse_number(c) for c in cells if self._is_numeric_only(c)]

        if len(numbers) < 2:
            return None

        # Heuristic assignment based on value magnitudes
        avg_price = 0.0
        current_price = 0.0
        quantity = 0
        pnl = 0.0
        pnl_percent = 0.0
        day_change = 0.0

        # Sort numbers descending to help assignment
        sorted_nums = sorted(numbers, reverse=True)

        # The largest integer-like value is likely quantity
        for n in numbers:
            if n > 0 and n == int(n) and n < 100000:
                quantity = int(n)
                break

        # Prices are typically the largest decimal values
        price_candidates = [n for n in numbers if n > 0 and n != quantity and n < 10000000]
        if len(price_candidates) >= 2:
            avg_price = price_candidates[0]
            current_price = price_candidates[1]
        elif len(price_candidates) == 1:
            current_price = price_candidates[0]

        # P&L and percentage are often the last 1-2 numbers
        remaining = [n for n in numbers if n not in (quantity, avg_price, current_price)]
        if remaining:
            pnl = remaining[0]
        if len(remaining) > 1:
            pnl_percent = remaining[1]
        if len(remaining) > 2:
            day_change = remaining[2]

        # Derive values if missing
        if avg_price == 0 and current_price > 0 and quantity > 0:
            avg_price = current_price  # fallback
        if current_price == 0 and avg_price > 0:
            current_price = avg_price
        market_value = quantity * current_price if quantity > 0 and current_price > 0 else 0.0
        invested_value = quantity * avg_price if quantity > 0 and avg_price > 0 else 0.0
        if pnl == 0 and market_value > 0 and invested_value > 0:
            pnl = market_value - invested_value
        if pnl_percent == 0 and invested_value > 0:
            pnl_percent = (pnl / invested_value) * 100

        return ExtractedHolding(
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            market_value=market_value,
            invested_value=invested_value,
            pnl=pnl,
            pnl_percent=pnl_percent,
            day_change=day_change,
        )

    def _try_parse_position_row(self, cells: List[str]) -> Optional[ExtractedPosition]:
        """Attempt to parse a table row into an ExtractedPosition."""
        if len(cells) < 3:
            return None

        symbol = ""
        for cell in cells:
            stripped = cell.strip()
            if re.match(r"^[A-Z]{2,10}$", stripped):
                symbol = stripped
                break
        if not symbol:
            for cell in cells:
                stripped = cell.strip()
                if stripped and not self._is_numeric_only(stripped):
                    symbol = re.sub(r"[^A-Z0-9]", "", stripped.upper())
                    if len(symbol) >= 2:
                        break
        if not symbol:
            return None

        numbers = [self._parse_number(c) for c in cells if self._is_numeric_only(c)]

        quantity = 0
        avg_price = 0.0
        current_price = 0.0
        pnl = 0.0
        pnl_percent = 0.0

        for n in numbers:
            if n > 0 and n == int(n) and n < 100000:
                quantity = int(n)
                break

        price_candidates = [n for n in numbers if n > 0 and n != quantity and n < 10000000]
        if len(price_candidates) >= 2:
            avg_price = price_candidates[0]
            current_price = price_candidates[1]
        elif len(price_candidates) == 1:
            current_price = price_candidates[0]

        remaining = [n for n in numbers if n not in (quantity, avg_price, current_price)]
        if remaining:
            pnl = remaining[0]
        if len(remaining) > 1:
            pnl_percent = remaining[1]

        if avg_price == 0 and current_price > 0 and quantity > 0:
            avg_price = current_price
        if current_price == 0 and avg_price > 0:
            current_price = avg_price

        # Detect derivatives from symbol pattern
        position_type = "EQUITY"
        expiry: Optional[str] = None
        strike: Optional[float] = None
        option_type: Optional[str] = None

        opt_match = re.match(
            r"([A-Z]+)\s*(\d{1,2}[A-Z]{3}\d{0,4})?\s*(\d+(?:\.\d+)?)\s*(CE|PE)?$",
            symbol,
        )
        if opt_match:
            base = opt_match.group(1)
            exp = opt_match.group(2)
            strk = opt_match.group(3)
            otype = opt_match.group(4)
            if otype:
                position_type = "OPTIONS"
                expiry = exp
                strike = self._parse_number(strk) if strk else None
                option_type = otype
            elif exp and strk:
                position_type = "FUTURES"
                expiry = exp

        return ExtractedPosition(
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            pnl=pnl,
            pnl_percent=pnl_percent,
            position_type=position_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )

    def _try_parse_order_row(self, cells: List[str]) -> Optional[ExtractedOrder]:
        """Attempt to parse a table row into an ExtractedOrder."""
        if len(cells) < 5:
            return None

        # Identify order ID (usually alphanumeric)
        order_id = ""
        symbol = ""
        side = ""
        quantity = 0
        price = 0.0
        status = ""
        order_type = ""

        for cell in cells:
            stripped = cell.strip()
            if re.match(r"^[A-Z0-9]{6,20}$", stripped) and not order_id:
                order_id = stripped
            elif re.match(r"^[A-Z]{2,10}$", stripped) and not symbol:
                symbol = stripped
            elif stripped.lower() in ("buy", "sell") and not side:
                side = stripped.upper()
            elif stripped.lower() in ("completed", "pending", "cancelled", "rejected", "open", "executed") and not status:
                status = stripped.upper()
            elif stripped.lower() in ("market", "limit", "sl", "sl-m") and not order_type:
                order_type = stripped.upper()

        if not symbol:
            return None

        numbers = [self._parse_number(c) for c in cells if self._is_numeric_only(c)]
        for n in numbers:
            if n > 0 and n == int(n) and n < 1000000:
                if quantity == 0:
                    quantity = int(n)
                elif price == 0.0:
                    price = n
            elif n > 0 and price == 0.0:
                price = n

        if not order_id:
            order_id = f"GROWW_{symbol}_{int(time.time())}"

        return ExtractedOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status=status,
            order_type=order_type,
        )

    def _parse_holdings_from_divs(self, page_content: str) -> List[ExtractedHolding]:
        """Fallback: parse holdings from div/card-based layouts."""
        holdings: List[ExtractedHolding] = []
        # Look for repeated card patterns
        card_pattern = re.compile(
            r"<div[^>]*class=\"[^\"]*(?:holding|stock|card)[^\"]*\"[^>]*>(.*?)</div>\s*</div>",
            re.DOTALL | re.IGNORECASE,
        )
        cards = card_pattern.findall(page_content)
        for card_html in cards:
            text = self._strip_html(card_html)
            parts = [p.strip() for p in text.split("\n") if p.strip()]
            if len(parts) >= 3:
                symbol = re.sub(r"[^A-Z0-9]", "", parts[0].upper())
                if 2 <= len(symbol) <= 10:
                    numbers = [self._parse_number(p) for p in parts[1:] if self._is_numeric_only(p)]
                    if numbers:
                        holdings.append(ExtractedHolding(
                            symbol=symbol,
                            quantity=int(numbers[0]) if numbers else 0,
                            avg_price=numbers[1] if len(numbers) > 1 else 0.0,
                            current_price=numbers[2] if len(numbers) > 2 else 0.0,
                            market_value=0.0,
                            invested_value=0.0,
                            pnl=0.0,
                            pnl_percent=0.0,
                            day_change=0.0,
                        ))
        return holdings

    def _parse_holdings_from_text(self, content_lower: str) -> List[ExtractedHolding]:
        """Fallback: parse holdings from plain-text / pre-rendered content."""
        holdings: List[ExtractedHolding] = []
        # Pattern: "SYMBOL ... ₹1,234.56 ... +₹12.34 (1.0%)"
        line_pattern = re.compile(
            r"([A-Z]{2,10})\s+.*?(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)",
            re.IGNORECASE,
        )
        for match in line_pattern.finditer(content_lower):
            symbol = match.group(1).upper()
            price = self._parse_number(match.group(2))
            if price > 0:
                holdings.append(ExtractedHolding(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0.0,
                    current_price=price,
                    market_value=0.0,
                    invested_value=0.0,
                    pnl=0.0,
                    pnl_percent=0.0,
                    day_change=0.0,
                    confidence=0.6,
                ))
        return holdings

    def _parse_positions_from_divs(self, page_content: str) -> List[ExtractedPosition]:
        """Fallback: parse positions from div/card layouts."""
        positions: List[ExtractedPosition] = []
        card_pattern = re.compile(
            r"<div[^>]*class=\"[^\"]*(?:position|trade|card)[^\"]*\"[^>]*>(.*?)</div>\s*</div>",
            re.DOTALL | re.IGNORECASE,
        )
        cards = card_pattern.findall(page_content)
        for card_html in cards:
            text = self._strip_html(card_html)
            parts = [p.strip() for p in text.split("\n") if p.strip()]
            if len(parts) >= 2:
                symbol = re.sub(r"[^A-Z0-9]", "", parts[0].upper())
                if 2 <= len(symbol) <= 10:
                    numbers = [self._parse_number(p) for p in parts[1:] if self._is_numeric_only(p)]
                    positions.append(ExtractedPosition(
                        symbol=symbol,
                        quantity=int(numbers[0]) if numbers else 0,
                        avg_price=numbers[1] if len(numbers) > 1 else 0.0,
                        current_price=numbers[2] if len(numbers) > 2 else 0.0,
                        pnl=0.0,
                        pnl_percent=0.0,
                        position_type="EQUITY",
                    ))
        return positions

    def _try_parse_option_row(self, cells: List[str]) -> Optional[dict]:
        """Attempt to parse a table row into an option contract dict."""
        if len(cells) < 3:
            return None

        strike = 0.0
        option_type = ""
        ltp = 0.0
        oi = 0
        volume = 0

        for cell in cells:
            stripped = cell.strip()
            if stripped.upper() in ("CE", "PE", "CALL", "PUT"):
                option_type = "CE" if stripped.upper() in ("CE", "CALL") else "PE"
            num = self._parse_number(stripped)
            if num > 100 and strike == 0.0:  # likely strike price
                strike = num
            elif num > 0 and ltp == 0.0 and strike > 0:
                ltp = num
            elif num > 0 and num == int(num):
                if volume == 0:
                    volume = int(num)
                else:
                    oi = int(num)

        if strike == 0.0 or not option_type:
            return None

        return {
            "strike": strike,
            "option_type": option_type,
            "ltp": ltp,
            "volume": volume,
            "open_interest": oi,
        }

    def _extract_value_near_label(
        self, content_lower: str, labels: List[str]
    ) -> float:
        """Extract the first numeric value appearing near a text label."""
        for label in labels:
            idx = content_lower.find(label)
            if idx == -1:
                continue
            # Search in a window after the label
            window = content_lower[idx : idx + 200]
            match = _INDIAN_NUMBER_RE.search(window)
            if match:
                return self._parse_number(match.group(1))
        return 0.0

    @staticmethod
    def _is_numeric_only(text: str) -> bool:
        """Check if a string contains at least one digit and no letters."""
        stripped = text.strip().replace(",", "").replace("₹", "").replace("%", "").replace("+", "").replace("-", "").replace(".", "")
        return len(stripped) > 0 and stripped.isdigit()

    def _record_extraction(self, page_type: str, url: str, count: int) -> None:
        """Record an extraction in the bounded recent-history buffer."""
        self._recent_extractions.append({
            "page_type": page_type,
            "url": url,
            "extracted_count": count,
            "timestamp": time.time(),
        })
        if len(self._recent_extractions) > 500:
            self._recent_extractions = self._recent_extractions[-500:]

    # ------------------------------------------------------------------
    # UI Targets helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_ui_targets_into_rows(ui_targets: List[Dict[str, Any]], y_tolerance: int = 10) -> List[List[Dict[str, Any]]]:
        """Group UI targets into rows based on vertical proximity.

        Targets are sorted by y (top to bottom), then grouped if their y
        coordinates are within y_tolerance pixels.
        """
        if not ui_targets:
            return []

        # Sort by y (top to bottom)
        sorted_targets = sorted(ui_targets, key=lambda t: t.get("y", 0))

        rows: List[List[Dict[str, Any]]] = []
        current_row: List[Dict[str, Any]] = [sorted_targets[0]]

        for target in sorted_targets[1:]:
            if abs(target.get("y", 0) - current_row[-1].get("y", 0)) <= y_tolerance:
                current_row.append(target)
            else:
                rows.append(current_row)
                current_row = [target]

        if current_row:
            rows.append(current_row)

        return rows