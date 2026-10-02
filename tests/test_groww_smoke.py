"""
MYRAA Phase D — Real Groww Read-Only Smoke Test

Tests actual Groww API connectivity when credentials are available.
Falls back to fixture/mock verification when credentials are absent.

NEVER places orders, modifies, or cancels any trade.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _credentials_available() -> bool:
    token = os.environ.get("GROWW_ACCESS_TOKEN", "")
    api_key = os.environ.get("GROWW_API_KEY", "")
    cred_file = os.environ.get("GROWW_CREDENTIAL_FILE", "")
    if token:
        return True
    if api_key:
        return True
    if cred_file and Path(cred_file).exists():
        return True
    return False


HAS_CREDENTIALS = _credentials_available()


class TestGrowwSmokeFixtureVerification:
    def test_groww_auth_config_loads_from_env(self):
        with patch.dict(os.environ, {"GROWW_ACCESS_TOKEN": "smoke_test_token_12345"}):
            from desktop_agent.finance.trading.broker.groww.groww_auth import GrowwAuthConfig
            config = GrowwAuthConfig.from_env()
            assert config.access_token == "smoke_test_token_12345"
            assert config.has_token() is True

    def test_groww_auth_config_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            from desktop_agent.finance.trading.broker.groww.groww_auth import GrowwAuthConfig
            config = GrowwAuthConfig.from_env()
            assert config.has_token() is False

    def test_groww_adapter_creates_without_crash(self):
        from desktop_agent.finance.trading.broker.groww.groww_adapter import GrowwAdapter
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            assert adapter.is_connected() is False
            assert adapter.get_holdings() == []
            assert adapter.get_positions() == []
            assert adapter.get_orders() == []

    def test_groww_normalizer_portfolio_flow(self):
        from desktop_agent.finance.trading.broker.groww.normalizer import normalize_groww_portfolio
        from desktop_agent.finance.trading.models import PortfolioSnapshot
        holdings = [
            {"trading_symbol": "RELIANCE", "quantity": 10, "average_price": 245000,
             "ltp": 268000, "previous_close": 265000, "exchange": "NSE"},
        ]
        positions = [
            {"trading_symbol": "TCS", "quantity": 5, "average_price": 380000,
             "ltp": 395000, "previous_close": 390000, "exchange": "NSE"},
        ]
        snapshot = normalize_groww_portfolio(holdings, positions, cash=150000)
        assert isinstance(snapshot, PortfolioSnapshot)
        assert len(snapshot.positions) == 2
        assert snapshot.cash == 150000

    def test_groww_guidance_engine_produces_advice(self):
        from desktop_agent.finance.trading.broker.groww.guidance import PersonalizedGuidanceEngine
        from desktop_agent.finance.trading.models import (
            PortfolioPosition, PortfolioSnapshot, Exchange, InstrumentType
        )
        positions = [
            PortfolioPosition(
                symbol="RELIANCE", quantity=10, average_price=2450,
                current_price=2680, previous_close=2650,
                exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
                entry_date="2024-01-15", notes="",
            ),
        ]
        snapshot = PortfolioSnapshot(
            positions=positions, cash=150000,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        engine = PersonalizedGuidanceEngine()
        advice = engine.analyze_portfolio(snapshot)
        assert advice.portfolio_health in ("STRONG", "MODERATE", "WEAK", "CRITICAL")
        assert len(advice.position_advices) == 1

    def test_groww_option_chain_normalization(self):
        from desktop_agent.finance.trading.broker.groww.normalizer import normalize_groww_option_chain
        from desktop_agent.finance.trading.models import OptionChain
        chain_data = [
            {"trading_symbol": "NIFTY24AUG24800CE", "strike_price": 2480000,
             "expiry_date": "2024-08-29", "ltp": 15000, "volume": 100000,
             "open_interest": 500000, "lot_size": 50, "option_type": "CE"},
            {"trading_symbol": "NIFTY24AUG24800PE", "strike_price": 2480000,
             "expiry_date": "2024-08-29", "ltp": 12000, "volume": 80000,
             "open_interest": 400000, "lot_size": 50, "option_type": "PE"},
        ]
        chain = normalize_groww_option_chain(chain_data, "NIFTY", 24252.0, "2024-08-29")
        assert isinstance(chain, OptionChain)
        assert len(chain.contracts) == 2

    def test_groww_safety_no_execution_methods(self):
        from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
        adapter = BrokerAdapter()
        with pytest.raises(NotImplementedError):
            adapter.execute_order({})
        with pytest.raises(NotImplementedError):
            adapter.cancel_order("test")
        with pytest.raises(NotImplementedError):
            adapter.prepare_order("TEST", "BUY", 10)
        with pytest.raises(NotImplementedError):
            adapter.verify_order("test")


@pytest.mark.skipif(not HAS_CREDENTIALS, reason="Groww credentials not configured")
class TestGrowwLiveSmoke:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from desktop_agent.finance.trading.broker.groww.groww_adapter import GrowwAdapter
        self._adapter = GrowwAdapter()
        self._start = time.time()

    def _elapsed_ms(self) -> float:
        return round((time.time() - self._start) * 1000, 1)

    def test_auth(self):
        assert self._adapter.is_connected(), "Groww authentication failed"

    def test_holdings(self):
        holdings = self._adapter.get_holdings()
        assert isinstance(holdings, list)

    def test_positions(self):
        positions = self._adapter.get_positions()
        assert isinstance(positions, list)

    def test_orders(self):
        orders = self._adapter.get_orders()
        assert isinstance(orders, list)

    def test_quote(self):
        holdings = self._adapter.get_holdings()
        if holdings:
            symbol = holdings[0].get("trading_symbol", holdings[0].get("symbol", "RELIANCE"))
            quote = self._adapter.get_quote(symbol)
            assert isinstance(quote, dict)

    def test_option_chain(self):
        raw = self._adapter.get_option_chain("NIFTY", datetime.now().strftime("%Y-%m-%d"))
        assert isinstance(raw, list)

    def test_account(self):
        account = self._adapter.get_account()
        assert isinstance(account, dict)

    def test_sync_portfolio(self):
        result = self._adapter.sync_portfolio()
        assert isinstance(result, dict)
        assert "positions" in result

    def test_latency_report(self):
        report = {
            "provider": "groww",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "authenticated": self._adapter.is_connected(),
            "latency_ms": self._elapsed_ms(),
        }
        assert report["authenticated"] is True


class TestGrowwSmokeCredentialStatus:
    def test_smoke_status_report(self):
        status = {
            "LIVE GROWW SMOKE": "EXECUTED" if HAS_CREDENTIALS else "NOT EXECUTED",
            "Reason": "credentials/configured" if HAS_CREDENTIALS else "credentials/configuration unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        assert "LIVE GROWW SMOKE" in status
        if not HAS_CREDENTIALS:
            assert status["LIVE GROWW SMOKE"] == "NOT EXECUTED"
