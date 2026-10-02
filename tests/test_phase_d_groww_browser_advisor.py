from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from desktop_agent.finance.trading.groww_browser import (
    GrowwBrowserBridge,
    GrowwDataExtractor,
    ExtractedHolding,
    ExtractedPosition,
    ExtractedOrder,
    GrowwPageState,
    TradingAdvisorPolicy,
    BlockedAction,
    GrowwSessionManager,
    SessionState,
)


# ---------------------------------------------------------------------------
# Inline HTML fixtures
# ---------------------------------------------------------------------------

SAMPLE_PORTFOLIO_HTML = """
<table>
  <tr>
    <td>RELIANCE</td>
    <td>10</td>
    <td>2500.00</td>
    <td>2600.00</td>
    <td>1000.00</td>
    <td>4.00</td>
    <td>50.00</td>
  </tr>
  <tr>
    <td>TCS</td>
    <td>5</td>
    <td>3200.00</td>
    <td>3350.00</td>
    <td>750.00</td>
    <td>2.34</td>
    <td>30.00</td>
  </tr>
</table>
"""

STALE_HTML = '<div>Loading, please wait...</div>'

FRESH_HTML = """
<table>
  <tr>
    <td>HDFCBANK</td>
    <td>20</td>
    <td>1600.00</td>
    <td>1650.00</td>
    <td>1000.00</td>
    <td>3.13</td>
    <td>25.00</td>
  </tr>
</table>
"""


# ===================================================================
# TestActionBlocking  (8 tests)
# ===================================================================

class TestActionBlocking:
    def setup_method(self):
        GrowwBrowserBridge.reset_instance()
        GrowwDataExtractor.reset_instance()
        TradingAdvisorPolicy.reset_instance()
        GrowwSessionManager.reset_instance()

    def test_blocked_actions_list(self):
        policy = TradingAdvisorPolicy()
        required = {
            "buy", "sell", "square off", "square-off", "cancel order",
            "cancel", "modify order", "modify", "submit order",
            "place order", "confirm order", "confirm", "pay", "pay now",
        }
        assert required.issubset(policy.BLOCKED_ACTIONS)

    def test_is_blocked_buy(self):
        policy = TradingAdvisorPolicy()
        assert policy.is_blocked("Buy") is True

    def test_is_blocked_sell(self):
        policy = TradingAdvisorPolicy()
        assert policy.is_blocked("Sell") is True

    def test_is_blocked_cancel_order(self):
        policy = TradingAdvisorPolicy()
        assert policy.is_blocked("Cancel Order") is True

    def test_is_not_blocked_view(self):
        policy = TradingAdvisorPolicy()
        assert policy.is_blocked("View Portfolio") is False

    def test_is_not_blocked_analyze(self):
        policy = TradingAdvisorPolicy()
        assert policy.is_blocked("Analyze Stock") is False

    def test_check_click_blocked(self):
        policy = TradingAdvisorPolicy()
        allowed, info = policy.check_click(
            "https://groww.in/portfolio",
            "button.place-order-btn",
            "Place Order",
        )
        assert allowed is False
        assert isinstance(info, BlockedAction)
        assert info.element_text == "Place Order"
        assert info.action_type == "click"

    def test_check_click_allowed(self):
        policy = TradingAdvisorPolicy()
        allowed, info = policy.check_click(
            "https://groww.in/portfolio",
            "div.holding",
            "View Holdings",
        )
        assert allowed is True
        assert info is None


# ===================================================================
# TestSessionDetection  (7 tests)
# ===================================================================

class TestSessionDetection:
    def setup_method(self):
        GrowwBrowserBridge.reset_instance()
        GrowwDataExtractor.reset_instance()
        TradingAdvisorPolicy.reset_instance()
        GrowwSessionManager.reset_instance()

    def test_session_state_values(self):
        states = list(SessionState)
        assert len(states) == 8

    def test_detect_logged_in(self):
        mgr = GrowwSessionManager()
        content = (
            "<div>My Portfolio</div>"
            "<span>holdings</span>"
            "<span>invested</span>"
            "<span>current value</span>"
            "<span>returns</span>"
        )
        state = mgr.detect_session_state(content, "https://groww.in/portfolio")
        assert state == SessionState.LOGGED_IN

    def test_detect_login_required(self):
        mgr = GrowwSessionManager()
        content = (
            "<div>Login to Groww</div>"
            "<input placeholder='Enter your phone number'>"
            "<input type='password'>"
            "<button>Continue with Google</button>"
        )
        state = mgr.detect_session_state(content, "https://groww.in/login")
        assert state == SessionState.LOGIN_REQUIRED

    def test_detect_otp_pending(self):
        mgr = GrowwSessionManager()
        content = (
            "<div>Login</div>"
            "<div>Enter OTP</div>"
            "<input placeholder='Enter the otp'>"
            "<button>Resend OTP</button>"
        )
        state = mgr.detect_session_state(content, "https://groww.in/otp")
        assert state == SessionState.OTP_PENDING

    def test_build_url_portfolio(self):
        mgr = GrowwSessionManager()
        url = mgr.build_url("portfolio")
        assert "portfolio" in url
        assert url.startswith("https://")

    def test_build_url_stock(self):
        mgr = GrowwSessionManager()
        url = mgr.build_url("charts", "RELIANCE")
        assert "reliance" in url.lower()
        assert "groww.in" in url

    def test_is_groww_page(self):
        mgr = GrowwSessionManager()
        assert mgr.is_groww_page("https://groww.in/portfolio") is True
        assert mgr.is_groww_page("https://google.com") is False


# ===================================================================
# TestDataExtractor  (8 tests)
# ===================================================================

class TestDataExtractor:
    def setup_method(self):
        GrowwBrowserBridge.reset_instance()
        GrowwDataExtractor.reset_instance()
        TradingAdvisorPolicy.reset_instance()
        GrowwSessionManager.reset_instance()

    def test_extract_holding_from_html(self):
        ext = GrowwDataExtractor()
        holdings = ext.extract_holdings_from_dom(SAMPLE_PORTFOLIO_HTML)
        assert len(holdings) >= 1
        symbols = [h.symbol for h in holdings]
        assert "RELIANCE" in symbols

    def test_parse_number_indian(self):
        ext = GrowwDataExtractor()
        assert ext._parse_number("1,23,456.78") == 123456.78

    def test_parse_number_plain(self):
        ext = GrowwDataExtractor()
        assert ext._parse_number("12345") == 12345.0

    def test_parse_quantity(self):
        ext = GrowwDataExtractor()
        assert ext._parse_quantity("100") == 100

    def test_detect_stale_data(self):
        ext = GrowwDataExtractor()
        assert ext._detect_data_freshness(STALE_HTML) is True

    def test_detect_fresh_data(self):
        ext = GrowwDataExtractor()
        assert ext._detect_data_freshness(FRESH_HTML) is False

    def test_confidence_score(self):
        ext = GrowwDataExtractor()
        score = ext._calculate_confidence(10, 10)
        assert score == 1.0

    def test_extraction_stats(self):
        ext = GrowwDataExtractor()
        ext.extract_portfolio(SAMPLE_PORTFOLIO_HTML, "https://groww.in/portfolio")
        stats = ext.get_extraction_stats()
        assert stats["total_extractions"] >= 1
        assert stats["successful_extractions"] >= 1


# ===================================================================
# TestBrowserBridge  (6 tests)
# ===================================================================

class TestBrowserBridge:
    def setup_method(self):
        GrowwBrowserBridge.reset_instance()
        GrowwDataExtractor.reset_instance()
        TradingAdvisorPolicy.reset_instance()
        GrowwSessionManager.reset_instance()

    def test_bridge_singleton(self):
        b1 = GrowwBrowserBridge()
        b2 = GrowwBrowserBridge()
        assert b1 is b2

    def test_open_groww_returns_dict(self):
        bridge = GrowwBrowserBridge()
        result = bridge.open_groww()
        assert isinstance(result, dict)
        assert "status" in result

    def test_read_portfolio_returns_dict(self):
        bridge = GrowwBrowserBridge()
        result = bridge.read_portfolio()
        assert isinstance(result, dict)
        assert "status" in result
        # Without a live browser, bridge returns error status
        if result.get("status") == "error":
            assert "error" in result
        else:
            assert "data" in result

    def test_read_positions_returns_dict(self):
        bridge = GrowwBrowserBridge()
        result = bridge.read_positions()
        assert isinstance(result, dict)
        assert "status" in result
        # Without a live browser, bridge returns error status
        if result.get("status") == "error":
            assert "error" in result
        else:
            assert "data" in result

    def test_health_returns_dict(self):
        bridge = GrowwBrowserBridge()
        health = bridge.get_health()
        assert isinstance(health, dict)
        assert "session_state" in health
        assert "extraction_stats" in health
        assert "blocker_stats" in health

    def test_bridge_blocks_dangerous_navigation(self):
        bridge = GrowwBrowserBridge()
        result = bridge._safe_navigate("https://groww.in/place-order")
        assert result["status"] == "blocked"


# ===================================================================
# TestBlockedAction  (3 tests)
# ===================================================================

class TestBlockedAction:
    def setup_method(self):
        GrowwBrowserBridge.reset_instance()
        GrowwDataExtractor.reset_instance()
        TradingAdvisorPolicy.reset_instance()
        GrowwSessionManager.reset_instance()

    def test_blocked_action_creation(self):
        action = BlockedAction(
            action_type="click",
            element_text="Buy",
            url="https://groww.in/order",
            timestamp=1000.0,
            blocked_reason="matches blocked financial action",
        )
        assert action.action_type == "click"
        assert action.element_text == "Buy"
        assert action.url == "https://groww.in/order"
        assert action.timestamp == 1000.0
        assert action.blocked_reason == "matches blocked financial action"

    def test_blocked_history_tracked(self):
        policy = TradingAdvisorPolicy()
        policy.check_click(
            "https://groww.in/order", "button.sell", "Sell",
        )
        history = policy.get_blocked_history()
        assert len(history) >= 1
        assert history[-1].element_text == "Sell"
        assert history[-1].action_type == "click"

    def test_history_bounded(self):
        policy = TradingAdvisorPolicy()
        for i in range(150):
            policy.check_click(
                "https://groww.in/pay", "button.pay", "Pay",
            )
        history = policy.get_blocked_history()
        assert len(history) == 100
