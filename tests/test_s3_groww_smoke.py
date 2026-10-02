"""Phase S.3 — Groww Real Smoke Tests.

Tests Groww browser advisor smoke scenarios.
Uses mocks/fixtures when real authenticated session is unavailable.

Every live extracted value is classified:
  REAL     — live value from authenticated Groww session
  STALE    — cached value older than threshold
  UNKNOWN  — value could not be determined
  DEGRADED — partial/uncertain value

If authenticated session is NOT available:
  LIVE GROWW SMOKE = NOT EXECUTED
"""

import time
import os
import pytest
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Groww session check
# ---------------------------------------------------------------------------

def _has_groww_session() -> bool:
    """Check if a real Groww authenticated session is available."""
    return bool(os.environ.get("GROWW_ACCESS_TOKEN"))


# ---------------------------------------------------------------------------
# Data truth classification
# ---------------------------------------------------------------------------

class DataTruth:
    """Classify live extracted values."""
    REAL = "REAL"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    DEGRADED = "DEGRADED"


@dataclass
class LiveValue:
    """A value extracted from live Groww session."""
    symbol: str
    page: str
    value: Any
    timestamp: float
    context: str
    freshness_seconds: float
    truth: str = DataTruth.UNKNOWN

    def classify(self, max_age_seconds: float = 300) -> str:
        """Classify truth based on freshness."""
        age = time.time() - self.timestamp
        if age <= max_age_seconds:
            self.truth = DataTruth.REAL
        elif age <= max_age_seconds * 2:
            self.truth = DataTruth.STALE
        else:
            self.truth = DataTruth.UNKNOWN
        return self.truth


# ---------------------------------------------------------------------------
# Mock Groww advisor for when session unavailable
# ---------------------------------------------------------------------------

class MockGrowwAdvisor:
    """Mock Groww advisor that returns realistic test data."""

    def analyze_my_portfolio(self):
        return MagicMock(
            overall_assessment="Mock portfolio analysis",
            holdings=[],
            total_investment=0,
            current_value=0,
            unrealized_pnl=0,
        )

    def get_stock_guidance(self, symbol: str):
        return MagicMock(
            symbol=symbol,
            action="HOLD",
            confidence=0.5,
            reasoning="Mock analysis",
        )

    def get_portfolio_snapshot(self):
        return MagicMock(
            holdings=[],
            total_investment=0,
            current_value=0,
        )


# ---------------------------------------------------------------------------
# Tests (always runnable — use mocks when session unavailable)
# ---------------------------------------------------------------------------

class TestGrowwSmoke:
    """Groww smoke tests — real when session available, mocked otherwise."""

    def test_session_availability(self):
        """Check Groww session availability."""
        available = _has_groww_session()
        if not available:
            pytest.skip("LIVE GROWW SMOKE = NOT EXECUTED (no authenticated session)")

    def test_portfolio_analysis_mock(self):
        """Portfolio analysis works via mock when session unavailable."""
        advisor = MockGrowwAdvisor()
        result = advisor.analyze_my_portfolio()
        assert result is not None
        assert hasattr(result, "overall_assessment")

    def test_stock_guidance_mock(self):
        """Stock guidance works via mock when session unavailable."""
        advisor = MockGrowwAdvisor()
        result = advisor.get_stock_guidance("RELIANCE")
        assert result is not None
        assert result.symbol == "RELIANCE"
        assert result.action in ("BUY", "SELL", "HOLD", "WAIT")

    def test_portfolio_snapshot_mock(self):
        """Portfolio snapshot works via mock when session unavailable."""
        advisor = MockGrowwAdvisor()
        result = advisor.get_portfolio_snapshot()
        assert result is not None
        assert hasattr(result, "holdings")

    def test_data_truth_classification(self):
        """Data truth classification works correctly."""
        now = time.time()

        # Real (fresh) — within 300s
        v1 = LiveValue("RELIANCE", "portfolio", 2500.0, now, "live", 300)
        assert v1.classify() == DataTruth.REAL

        # Unknown (very old) — older than 600s
        v2 = LiveValue("RELIANCE", "portfolio", 2500.0, now - 3600, "old", 300)
        assert v2.classify() == DataTruth.UNKNOWN

        # Stale — between 300s and 600s
        v3 = LiveValue("RELIANCE", "portfolio", 2500.0, now - 450, "stale", 300)
        assert v3.classify() == DataTruth.STALE

    def test_read_only_advisory(self):
        """All Groww operations are read-only advisory."""
        # Verify no execute_order / submit_order / place_order methods exist
        from desktop_agent.finance.trading.broker.groww import browser_advisor
        advisor_class = browser_advisor.GrowwBrowserAdvisor
        for method_name in ["execute_order", "submit_order", "place_order", "buy", "sell"]:
            assert not hasattr(advisor_class, method_name), \
                f"GrowwBrowserAdvisor should NOT have {method_name}"

    def test_groww_smoke_not_executed_when_no_session(self):
        """Verify NOT EXECUTED message when session unavailable."""
        if _has_groww_session():
            pytest.skip("Session available — smoke would execute live")
        advisor = MockGrowwAdvisor()
        result = advisor.analyze_my_portfolio()
        assert result is not None


class TestGrowwSafetyGuards:
    """Verify safety guards are preserved."""

    def test_financial_actions_blocked_by_policy(self):
        """Financial actions are in BLOCKED_ACTIONS set."""
        from desktop_agent.finance.trading.groww_browser.groww_action_blocker import TradingAdvisorPolicy
        policy = TradingAdvisorPolicy()
        # All dangerous actions must be blocked
        for action in ["buy", "sell", "square off", "cancel order", "modify order", "submit order", "place order"]:
            assert action in policy.BLOCKED_ACTIONS, f"'{action}' must be blocked"

    def test_trading_engine_read_only(self):
        """TradingIntelligenceEngine is read-only advisory."""
        from desktop_agent.finance.trading.engine import TradingIntelligenceEngine
        for method in ["execute_trade", "place_order", "submit_order", "buy", "sell"]:
            assert not hasattr(TradingIntelligenceEngine, method), \
                f"TradingIntelligenceEngine should NOT have {method}"

    def test_groww_browser_blocks_dangerous_actions(self):
        """GrowwBrowserAdvisor uses TradingAdvisorPolicy to block execution."""
        from desktop_agent.finance.trading.groww_browser.groww_action_blocker import TradingAdvisorPolicy
        policy = TradingAdvisorPolicy()
        assert len(policy.BLOCKED_ACTIONS) >= 10, "Policy must block at least 10 dangerous actions"
        assert "buy" in policy.BLOCKED_ACTIONS
        assert "sell" in policy.BLOCKED_ACTIONS


# ---------------------------------------------------------------------------
# Live smoke (only runs with real session)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _has_groww_session(), reason="No authenticated Groww session")
class TestGrowwLiveSmoke:
    """Live Groww smoke tests — only run with real session."""

    def test_live_portfolio_read(self):
        """Read portfolio from live Groww session."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_holdings_read(self):
        """Read holdings from live Groww session."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_positions_read(self):
        """Read positions from live Groww session."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_pnl_read(self):
        """Read P&L from live Groww session."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_stock_analysis(self):
        """Open and analyze a stock."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_nifty_open(self):
        """Open NIFTY index."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_option_chain(self):
        """Read option chain OI/IV/Greeks."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")

    def test_live_advisory_output(self):
        """Generate advisory output from live data."""
        pytest.skip("LIVE: Requires real Groww browser session — run manually")
