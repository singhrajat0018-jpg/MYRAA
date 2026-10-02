"""
MYRAA Phase D Part 2 — Groww Trading Advisor Tests

34+ tests covering:
- GrowwAdapter: auth, holdings, positions, orders, quotes, option chain
- Normalizer: quote, holdings, positions, portfolio, option chain normalization
- GuidanceEngine: portfolio advice, stock guidance, concentration, risks
- GrowwAdvisor: end-to-end flow, state, error handling

All tests use mock data — no live Groww API calls.
Read-only: no execution or order placement tested.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from desktop_agent.finance.trading.broker.groww.groww_auth import (
    GrowwAuthConfig,
    GrowwAuthenticator,
)
from desktop_agent.finance.trading.broker.groww.groww_adapter import (
    GrowwAdapter,
    GrowwClient,
    _normalize_price,
    _safe_float,
    _safe_int,
)
from desktop_agent.finance.trading.broker.groww.normalizer import (
    normalize_groww_holdings,
    normalize_groww_option_chain,
    normalize_groww_portfolio,
    normalize_groww_positions,
    normalize_groww_quote,
)
from desktop_agent.finance.trading.broker.groww.guidance import (
    PersonalizedGuidanceEngine,
    PortfolioAdvice,
    PositionAdvice,
    StockGuidance,
    _infer_sector,
)
from desktop_agent.finance.trading.broker.groww.advisor import (
    GrowwAdvisor,
    GrowwAdvisorState,
)
from desktop_agent.finance.trading.models import (
    Exchange,
    InstrumentType,
    MarketQuote,
    OHLCV,
    OptionChain,
    OptionContract,
    PortfolioPosition,
    PortfolioSnapshot,
    TrendDirection,
    TechnicalAnalysis,
)


# ─── Fixtures ───────────────────────────────────────────────────────────

MOCK_GROWW_HOLDINGS = [
    {
        "trading_symbol": "RELIANCE",
        "quantity": 10,
        "average_price": 245000,
        "ltp": 268000,
        "previous_close": 265000,
        "exchange": "NSE",
        "created_at": "2024-01-15",
    },
    {
        "trading_symbol": "TCS",
        "quantity": 5,
        "average_price": 380000,
        "ltp": 395000,
        "previous_close": 390000,
        "exchange": "NSE",
        "created_at": "2024-02-20",
    },
    {
        "trading_symbol": "HDFCBANK",
        "quantity": 15,
        "average_price": 165000,
        "ltp": 172000,
        "previous_close": 170000,
        "exchange": "NSE",
        "created_at": "2023-11-10",
    },
]

MOCK_GROWW_POSITIONS = [
    {
        "trading_symbol": "INFY",
        "quantity": 8,
        "average_price": 148000,
        "ltp": 152000,
        "previous_close": 150000,
        "exchange": "NSE",
    },
]

MOCK_GROWW_ORDERS = [
    {
        "order_id": "GROWW-001",
        "trading_symbol": "RELIANCE",
        "side": "BUY",
        "quantity": 10,
        "price": 245000,
        "status": "COMPLETE",
        "created_at": "2024-01-15T09:30:00",
    },
]

MOCK_GROWW_QUOTE = {
    "trading_symbol": "RELIANCE",
    "ltp": 268000,
    "previous_close": 265000,
    "open": 266000,
    "high": 270000,
    "low": 264000,
    "volume": 5000000,
    "best_bid_price": 267500,
    "best_ask_price": 268500,
    "best_bid_quantity": 100,
    "best_ask_quantity": 200,
    "exchange": "NSE",
    "market_status": "OPEN",
}

MOCK_OPTION_CHAIN = [
    {
        "trading_symbol": "NIFTY24AUG24800CE",
        "strike_price": 2480000,
        "expiry_date": "2024-08-29",
        "ltp": 15000,
        "volume": 100000,
        "open_interest": 500000,
        "change_in_oi": 25000,
        "implied_volatility": 15.2,
        "best_bid_price": 14500,
        "best_ask_price": 15500,
        "delta": 0.6,
        "gamma": 0.02,
        "theta": -120,
        "vega": 45,
        "lot_size": 50,
    },
    {
        "trading_symbol": "NIFTY24AUG24800PE",
        "strike_price": 2480000,
        "expiry_date": "2024-08-29",
        "ltp": 12000,
        "volume": 80000,
        "open_interest": 400000,
        "change_in_oi": -10000,
        "implied_volatility": 14.8,
        "best_bid_price": 11500,
        "best_ask_price": 12500,
        "delta": -0.4,
        "gamma": 0.02,
        "theta": -110,
        "vega": 42,
        "lot_size": 50,
    },
]


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=GrowwAdapter)
    adapter.is_connected.return_value = True
    adapter.authenticated = True
    adapter.auth_state = {
        "authenticated": True,
        "auth_method": "direct_token",
        "token_valid": True,
        "token_expiry": datetime(2099, 1, 1).isoformat(),
        "last_error": "",
    }
    adapter.get_holdings.return_value = MOCK_GROWW_HOLDINGS
    adapter.get_positions.return_value = MOCK_GROWW_POSITIONS
    adapter.get_orders.return_value = MOCK_GROWW_ORDERS
    adapter.get_quote.return_value = MOCK_GROWW_QUOTE
    adapter.sync_portfolio.return_value = {
        "positions": [],
        "cash": 150000,
        "broker": "groww",
        "connected": True,
    }
    return adapter


@pytest.fixture
def guidance_engine():
    return PersonalizedGuidanceEngine()


@pytest.fixture
def mock_snapshot():
    positions = [
        PortfolioPosition(
            symbol="RELIANCE", quantity=10, average_price=2450,
            current_price=2680, previous_close=2650,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
            entry_date="2024-01-15", notes="",
        ),
        PortfolioPosition(
            symbol="TCS", quantity=5, average_price=3800,
            current_price=3950, previous_close=3900,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
            entry_date="2024-02-20", notes="",
        ),
        PortfolioPosition(
            symbol="HDFCBANK", quantity=15, average_price=1650,
            current_price=1720, previous_close=1700,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
            entry_date="2023-11-10", notes="",
        ),
    ]
    return PortfolioSnapshot(positions=positions, cash=150000, timestamp=datetime.utcnow().isoformat())


# ─── Test: Normalizer Utilities ─────────────────────────────────────────

class TestNormalizerUtilities:
    def test_normalize_price_normal(self):
        assert _normalize_price(2500.50) == 2500.50

    def test_normalize_price_paise(self):
        assert _normalize_price(250050) == 2500.50

    def test_normalize_price_zero(self):
        assert _normalize_price(0) == 0.0

    def test_normalize_price_none(self):
        assert _normalize_price(None) == 0.0

    def test_safe_float_valid(self):
        assert _safe_float("3.14") == 3.14

    def test_safe_float_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_invalid(self):
        assert _safe_float("abc", 5.0) == 5.0

    def test_safe_int_valid(self):
        assert _safe_int("42") == 42

    def test_safe_int_none(self):
        assert _safe_int(None) == 0


# ─── Test: Groww Quote Normalization ────────────────────────────────────

class TestGrowwQuoteNormalization:
    def test_normalize_groww_quote(self):
        quote = normalize_groww_quote(MOCK_GROWW_QUOTE, "RELIANCE")
        assert quote.symbol == "RELIANCE"
        assert quote.current_price == 2680.0
        assert quote.previous_close == 2650.0
        assert quote.open_price == 2660.0
        assert quote.high_price == 2700.0
        assert quote.low_price == 2640.0
        assert quote.volume == 5000000
        assert quote.exchange == Exchange.NSE
        assert quote.source == "groww"

    def test_normalize_groww_quote_paise_prices(self):
        raw = {**MOCK_GROWW_QUOTE, "ltp": 268000, "open": 266000}
        quote = normalize_groww_quote(raw, "RELIANCE")
        assert quote.current_price == 2680.0
        assert quote.open_price == 2660.0

    def test_normalize_groww_quote_missing_fields(self):
        quote = normalize_groww_quote({}, "TEST")
        assert quote.symbol == "TEST"
        assert quote.current_price == 0.0


# ─── Test: Holdings Normalization ───────────────────────────────────────

class TestHoldingsNormalization:
    def test_normalize_groww_holdings(self):
        positions = normalize_groww_holdings(MOCK_GROWW_HOLDINGS)
        assert len(positions) == 3
        assert positions[0].symbol == "RELIANCE"
        assert positions[0].quantity == 10
        assert positions[0].average_price == 2450.0
        assert positions[0].current_price == 2680.0

    def test_normalize_groww_holdings_empty(self):
        positions = normalize_groww_holdings([])
        assert len(positions) == 0

    def test_normalize_groww_holdings_zero_quantity(self):
        raw = [{"trading_symbol": "TEST", "quantity": 0, "average_price": 100, "ltp": 110}]
        positions = normalize_groww_holdings(raw)
        assert len(positions) == 0

    def test_normalize_groww_holdings_missing_symbol(self):
        raw = [{"quantity": 10, "average_price": 100, "ltp": 110}]
        positions = normalize_groww_holdings(raw)
        assert len(positions) == 0


# ─── Test: Positions Normalization ──────────────────────────────────────

class TestPositionsNormalization:
    def test_normalize_groww_positions(self):
        positions = normalize_groww_positions(
            MOCK_GROWW_POSITIONS, existing_symbols={"RELIANCE", "TCS"}
        )
        # INFY not in existing_symbols, should be included
        assert len(positions) == 1
        assert positions[0].symbol == "INFY"

    def test_normalize_groww_positions_skip_existing(self):
        positions = normalize_groww_positions(
            MOCK_GROWW_POSITIONS, existing_symbols={"INFY"}
        )
        assert len(positions) == 0


# ─── Test: Portfolio Normalization ──────────────────────────────────────

class TestPortfolioNormalization:
    def test_normalize_groww_portfolio(self):
        snapshot = normalize_groww_portfolio(
            MOCK_GROWW_HOLDINGS, MOCK_GROWW_POSITIONS, cash=150000
        )
        assert isinstance(snapshot, PortfolioSnapshot)
        assert snapshot.cash == 150000
        assert len(snapshot.positions) == 4  # 3 holdings + 1 position (INFY not in holdings)

    def test_normalize_groww_portfolio_empty(self):
        snapshot = normalize_groww_portfolio([], [], cash=0)
        assert len(snapshot.positions) == 0
        assert snapshot.cash == 0


# ─── Test: Option Chain Normalization ───────────────────────────────────

class TestOptionChainNormalization:
    def test_normalize_groww_option_chain(self):
        chain = normalize_groww_option_chain(
            MOCK_OPTION_CHAIN, "NIFTY", 24252.0, "2024-08-29"
        )
        assert isinstance(chain, OptionChain)
        assert chain.symbol == "NIFTY"
        assert chain.underlying_price == 24252.0
        assert chain.expiry == "2024-08-29"
        assert len(chain.contracts) == 2

    def test_normalize_groww_option_chain_empty(self):
        chain = normalize_groww_option_chain([], "NIFTY", 24252.0)
        assert len(chain.contracts) == 0

    def test_option_chain_calls_puts(self):
        chain = normalize_groww_option_chain(MOCK_OPTION_CHAIN, "NIFTY", 24252.0)
        calls = [c for c in chain.contracts if c.option_type == "CE"]
        puts = [c for c in chain.contracts if c.option_type == "PE"]
        assert len(calls) == 1
        assert len(puts) == 1


# ─── Test: Sector Inference ─────────────────────────────────────────────

class TestSectorInference:
    def test_reliance_is_energy(self):
        assert _infer_sector("RELIANCE") == "Energy"

    def test_tcs_is_it(self):
        assert _infer_sector("TCS") == "IT"

    def test_hdfcbank_is_banking(self):
        assert _infer_sector("HDFCBANK") == "Banking"

    def test_unknown_is_other(self):
        assert _infer_sector("XYZUNKNOWN") == "Other"

    def test_ns_suffix_handled(self):
        assert _infer_sector("RELIANCE.NS") == "Energy"


# ─── Test: Guidance Engine ──────────────────────────────────────────────

class TestGuidanceEngine:
    def test_analyze_portfolio_basic(self, guidance_engine, mock_snapshot):
        advice = guidance_engine.analyze_portfolio(mock_snapshot)
        assert isinstance(advice, PortfolioAdvice)
        assert advice.portfolio_health in ("STRONG", "MODERATE", "WEAK", "CRITICAL")
        assert len(advice.position_advices) == 3
        assert advice.total_invested > 0
        assert advice.total_value > 0

    def test_analyze_portfolio_empty(self, guidance_engine):
        empty = PortfolioSnapshot(positions=[], cash=0, timestamp=datetime.utcnow().isoformat())
        advice = guidance_engine.analyze_portfolio(empty)
        assert advice.portfolio_health == "CRITICAL"
        assert "khaali" in advice.overall_assessment.lower()

    def test_position_actions(self, guidance_engine, mock_snapshot):
        advice = guidance_engine.analyze_portfolio(mock_snapshot)
        for pa in advice.position_advices:
            assert pa.action in ("HOLD", "ADD", "REDUCE", "EXIT")
            assert 0 <= pa.confidence <= 1

    def test_sector_exposure(self, guidance_engine, mock_snapshot):
        advice = guidance_engine.analyze_portfolio(mock_snapshot)
        assert len(advice.sector_exposure) > 0
        total = sum(advice.sector_exposure.values())
        assert abs(total - 100.0) < 1.0  # Should sum to ~100%

    def test_stock_guidance(self, guidance_engine, mock_snapshot):
        pos = mock_snapshot.positions[0]
        guidance = guidance_engine.get_stock_guidance("RELIANCE", pos)
        assert isinstance(guidance, StockGuidance)
        assert guidance.symbol == "RELIANCE"
        assert guidance.recommendation in ("BUY", "SELL", "HOLD", "WAIT", "AVOID")
        assert guidance.current_price == 2680

    def test_stock_guidance_no_position(self, guidance_engine):
        guidance = guidance_engine.get_stock_guidance("TATAMOTORS", None)
        assert guidance.recommendation == "WAIT"


# ─── Test: Groww Auth ───────────────────────────────────────────────────

class TestGrowwAuth:
    def test_auth_config_from_env(self):
        with patch.dict(os.environ, {"GROWW_ACCESS_TOKEN": "test123"}):
            config = GrowwAuthConfig.from_env()
            assert config.access_token == "test123"
            assert config.has_token() is True

    def test_auth_config_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            config = GrowwAuthConfig.from_env()
            assert config.has_token() is False

    def test_auth_config_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"access_token": "filetoken", "api_key": "key1"}, f)
            f.flush()
            config = GrowwAuthConfig.from_file(f.name)
            assert config.access_token == "filetoken"
            assert config.has_token() is True
        os.unlink(f.name)

    def test_auth_config_file_not_found(self):
        config = GrowwAuthConfig.from_file("nonexistent.json")
        assert config.has_token() is False

    def test_authenticator_direct_token(self):
        auth = GrowwAuthenticator(GrowwAuthConfig(access_token="direct123"))
        assert auth.is_authenticated() is True
        assert auth.get_token() == "direct123"
        headers = auth.get_headers()
        assert "Bearer direct123" in headers["Authorization"]

    def test_authenticator_no_token(self):
        auth = GrowwAuthenticator(GrowwAuthConfig())
        assert auth.is_authenticated() is False
        assert auth.get_headers() == {}

    def test_auth_state(self):
        auth = GrowwAuthenticator(GrowwAuthConfig(access_token="tok"))
        state = auth.get_state()
        assert state["authenticated"] is True
        assert state["auth_method"] == "direct_token"
        assert state["last_error"] == ""


# ─── Test: Groww Client ────────────────────────────────────────────────

class TestGrowwClient:
    def test_client_not_authenticated(self):
        auth = GrowwAuthenticator(GrowwAuthConfig())
        client = GrowwClient(auth)
        result = client.get("/test")
        assert result["error"] == "not_authenticated"

    @patch("desktop_agent.finance.trading.broker.groww.groww_adapter.urlopen")
    def test_client_get_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": {"key": "value"}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        auth = GrowwAuthenticator(GrowwAuthConfig(access_token="test123"))
        client = GrowwClient(auth)
        result = client.get("/test")
        assert result == {"data": {"key": "value"}}


# ─── Test: GrowwAdapter ────────────────────────────────────────────────

class TestGrowwAdapter:
    def test_adapter_not_connected(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            assert adapter.is_connected() is False

    def test_adapter_get_account_not_connected(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            account = adapter.get_account()
            assert account["error"] == "not_connected"

    def test_adapter_get_holdings_not_connected(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            holdings = adapter.get_holdings()
            assert holdings == []

    def test_adapter_sync_not_connected(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            result = adapter.sync_portfolio()
            assert result["connected"] is False

    def test_adapter_auth_state(self):
        auth = GrowwAuthenticator(GrowwAuthConfig(access_token="tok"))
        adapter = GrowwAdapter.__new__(GrowwAdapter)
        adapter._authenticator = auth
        adapter._connected = True
        state = adapter.auth_state
        assert state["authenticated"] is True


# ─── Test: GrowwAdvisor (Orchestrator) ──────────────────────────────────

class TestGrowwAdvisor:
    def test_advisor_not_connected(self):
        with patch.dict(os.environ, {}, clear=True):
            advisor = GrowwAdvisor()
            assert advisor.connected is False

    def test_advisor_state(self):
        with patch.dict(os.environ, {}, clear=True):
            advisor = GrowwAdvisor()
            state = advisor.state
            assert "connected" in state
            assert "holdings_count" in state
            assert "auth_state" in state

    def test_advisor_analyze_empty_portfolio(self):
        with patch.dict(os.environ, {}, clear=True):
            advisor = GrowwAdvisor()
            advice = advisor.analyze_my_portfolio()
            assert isinstance(advice, PortfolioAdvice)
            assert advice.portfolio_health == "CRITICAL"

    def test_advisor_stock_guidance_no_snapshot(self):
        with patch.dict(os.environ, {}, clear=True):
            advisor = GrowwAdvisor()
            guidance = advisor.get_stock_advice("RELIANCE")
            assert isinstance(guidance, StockGuidance)
            assert guidance.recommendation == "WAIT"

    def test_advisor_health(self):
        with patch.dict(os.environ, {}, clear=True):
            advisor = GrowwAdvisor()
            health = advisor.health()
            assert health["groww_connected"] is False
            assert health["portfolio_positions"] == 0


# ─── Test: Integration with Phase D Models ─────────────────────────────

class TestPhaseDIntegration:
    def test_snapshot_to_guidance_flow(self, guidance_engine):
        positions = [
            PortfolioPosition(
                symbol="RELIANCE", quantity=10, average_price=2450,
                current_price=2680, previous_close=2650,
                exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
                entry_date="2024-01-15", notes="",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions, cash=150000, timestamp=datetime.utcnow().isoformat()
        )
        advice = guidance_engine.analyze_portfolio(snapshot)
        assert advice.total_invested == 24500.0
        assert advice.total_value == 26800.0
        assert advice.total_pnl == 2300.0

    def test_portfolio_snapshot_properties(self):
        positions = [
            PortfolioPosition(
                symbol="TCS", quantity=5, average_price=3800,
                current_price=3950, previous_close=3900,
                exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
                entry_date="2024-02-20", notes="",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions, cash=100000, timestamp=datetime.utcnow().isoformat()
        )
        assert snapshot.total_invested == 19000.0
        assert snapshot.total_market_value == 19750.0
        assert snapshot.total_day_pnl == 250.0
        assert snapshot.position_count == 1

    def test_option_chain_model_integration(self):
        chain = normalize_groww_option_chain(MOCK_OPTION_CHAIN, "NIFTY", 24252.0, "2024-08-29")
        calls = chain.calls
        puts = chain.puts
        assert len(calls) > 0
        assert len(puts) > 0
        assert calls[0].option_type == "CE"
        assert puts[0].option_type == "PE"
