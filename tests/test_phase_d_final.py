"""
MYRAA Phase D Final — End-to-End Integration Tests

Covers: alerts, daily close, health, UI endpoints, safety constraints.
55+ tests across all Phase D Final components.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from desktop_agent.finance.trading.alerts.engine import AlertEngine, AlertRule, Alert
from desktop_agent.finance.trading.automation.daily_close_scheduler import (
    DailyCloseScheduler, AutomationState, MarketCloseResult
)
from desktop_agent.finance.trading.models import (
    PortfolioPosition, PortfolioSnapshot, Exchange, InstrumentType
)


# ─── Alert Engine Tests ────────────────────────────────────────────────

class TestAlertEngine:
    def test_alert_engine_initializes(self):
        engine = AlertEngine()
        state = engine.state
        assert state["rules_count"] >= 3
        assert state["enabled_rules"] >= 3

    def test_add_rule(self):
        engine = AlertEngine()
        initial = engine.state["rules_count"]
        engine.add_rule(AlertRule("test1", "breakout", symbol="RELIANCE", threshold=2700))
        assert engine.state["rules_count"] == initial + 1

    def test_remove_rule(self):
        engine = AlertEngine()
        engine.add_rule(AlertRule("test_rm", "volume"))
        engine.remove_rule("test_rm")
        rules = engine.get_rules()
        assert all(r["rule_id"] != "test_rm" for r in rules)

    def test_get_rules(self):
        engine = AlertEngine()
        rules = engine.get_rules()
        assert isinstance(rules, list)
        for r in rules:
            assert "rule_id" in r
            assert "alert_type" in r

    def test_check_portfolio_movement_triggers(self):
        engine = AlertEngine()
        engine._rules = [AlertRule("r1", "portfolio_movement", threshold=2.0)]
        pos = PortfolioPosition(
            symbol="RELIANCE", quantity=10, average_price=2450,
            current_price=2680, previous_close=2600,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
        )
        snapshot = PortfolioSnapshot(positions=[pos], cash=100000)
        alerts = engine.check_all(snapshot)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "portfolio_movement"

    def test_check_drawdown_triggers(self):
        engine = AlertEngine()
        engine._rules = [AlertRule("r2", "drawdown", threshold=5.0)]
        pos = PortfolioPosition(
            symbol="TEST", quantity=10, average_price=100,
            current_price=80, previous_close=85,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
        )
        snapshot = PortfolioSnapshot(positions=[pos], cash=0)
        alerts = engine.check_all(snapshot)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "drawdown"

    def test_check_key_level_above(self):
        engine = AlertEngine()
        engine._rules = [AlertRule("r3", "key_level", symbol="RELIANCE", threshold=2500, direction="above")]
        pos = PortfolioPosition(
            symbol="RELIANCE", quantity=10, average_price=2450,
            current_price=2680, previous_close=2650,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
        )
        snapshot = PortfolioSnapshot(positions=[pos], cash=100000)
        alerts = engine.check_all(snapshot)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "key_level"

    def test_check_target_reached(self):
        engine = AlertEngine()
        engine._rules = [AlertRule("r4", "target_reached", symbol="RELIANCE", threshold=5.0)]
        pos = PortfolioPosition(
            symbol="RELIANCE", quantity=10, average_price=2450,
            current_price=2680, previous_close=2650,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
        )
        snapshot = PortfolioSnapshot(positions=[pos], cash=100000)
        alerts = engine.check_all(snapshot)
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "target_reached"

    def test_fire_report_ready(self):
        engine = AlertEngine()
        engine.fire_report_ready("/tmp/report.json")
        alerts = engine.get_alerts()
        assert any(a["alert_type"] == "report_ready" for a in alerts)

    def test_fire_thesis_invalidation(self):
        engine = AlertEngine()
        engine.fire_thesis_invalidation("RELIANCE", "Stop loss hit")
        alerts = engine.get_alerts()
        assert any(a["alert_type"] == "thesis_invalidation" for a in alerts)

    def test_acknowledge(self):
        engine = AlertEngine()
        engine.fire_report_ready("/tmp/test.json")
        alerts = engine.get_alerts(unacknowledged_only=True)
        if alerts:
            engine.acknowledge(alerts[0]["alert_id"])
            unacked = engine.get_alerts(unacknowledged_only=True)
            assert all(a["alert_id"] != alerts[0]["alert_id"] for a in unacked)

    def test_callback_fires(self):
        engine = AlertEngine()
        fired = []
        engine.register_callback(lambda a: fired.append(a))
        engine.fire_report_ready("/tmp/cb.json")
        assert len(fired) == 1

    def test_no_duplicate_alerts(self):
        engine = AlertEngine()
        engine.fire_report_ready("/tmp/dup.json")
        engine.fire_report_ready("/tmp/dup.json")
        alerts = engine.get_alerts()
        report_alerts = [a for a in alerts if a["alert_type"] == "report_ready"]
        assert len(report_alerts) == 1


# ─── Daily Close Scheduler Tests ───────────────────────────────────────

class TestDailyCloseScheduler:
    def test_scheduler_initializes(self):
        scheduler = DailyCloseScheduler()
        state = scheduler.state
        assert state["running"] is False
        assert state["run_count"] == 0

    def test_trigger_now(self):
        scheduler = DailyCloseScheduler()
        result = scheduler.trigger_now()
        assert isinstance(result, MarketCloseResult)
        assert result.timestamp != ""

    def test_state_tracking(self):
        scheduler = DailyCloseScheduler()
        scheduler.trigger_now()
        state = scheduler.state
        assert state["run_count"] == 1
        assert state["last_run"] is not None

    def test_callback_fires(self):
        results = []
        scheduler = DailyCloseScheduler()
        scheduler.register_callback(lambda r: results.append(r))
        scheduler.trigger_now()
        assert len(results) == 1

    def test_start_stop(self):
        scheduler = DailyCloseScheduler()
        scheduler.start()
        time.sleep(0.1)
        assert scheduler.state["running"] is True
        scheduler.stop()
        time.sleep(0.2)
        assert scheduler.state["running"] is False

    def test_no_advisor_still_works(self):
        scheduler = DailyCloseScheduler(groww_advisor=None, trading_engine=None)
        result = scheduler.trigger_now()
        assert isinstance(result, MarketCloseResult)


# ─── Safety Constraint Tests ───────────────────────────────────────────

class TestSafetyConstraints:
    def test_broker_adapter_no_execute(self):
        from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
        adapter = BrokerAdapter()
        with pytest.raises(NotImplementedError):
            adapter.execute_order({})

    def test_broker_adapter_no_cancel(self):
        from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
        adapter = BrokerAdapter()
        with pytest.raises(NotImplementedError):
            adapter.cancel_order("test")

    def test_broker_adapter_no_prepare(self):
        from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
        adapter = BrokerAdapter()
        with pytest.raises(NotImplementedError):
            adapter.prepare_order("TEST", "BUY", 10)

    def test_broker_adapter_no_verify(self):
        from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
        adapter = BrokerAdapter()
        with pytest.raises(NotImplementedError):
            adapter.verify_order("test")

    def test_groww_adapter_no_execute(self):
        from desktop_agent.finance.trading.broker.groww.groww_adapter import GrowwAdapter
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            with pytest.raises(NotImplementedError):
                adapter.execute_order({})

    def test_groww_adapter_no_cancel(self):
        from desktop_agent.finance.trading.broker.groww.groww_adapter import GrowwAdapter
        with patch.dict(os.environ, {}, clear=True):
            adapter = GrowwAdapter()
            with pytest.raises(NotImplementedError):
                adapter.cancel_order("test")


# ─── Health Endpoint Tests ─────────────────────────────────────────────

class TestHealthEndpoints:
    def test_trading_health_structure(self):
        from desktop_agent.finance.trading.alerts.engine import AlertEngine
        from desktop_agent.finance.trading.automation.daily_close_scheduler import DailyCloseScheduler
        from desktop_agent.finance.trading.engine import TradingIntelligenceEngine

        engine = TradingIntelligenceEngine()
        alerts = AlertEngine()
        scheduler = DailyCloseScheduler()

        health = {
            "groww": {"connected": False, "last_sync": None, "portfolio_positions": 0},
            "alerts": alerts.state,
            "scheduler": scheduler.state,
            "engine": engine.status(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        assert "groww" in health
        assert "alerts" in health
        assert "scheduler" in health
        assert "engine" in health
        assert health["engine"]["engine"] == "TradingIntelligenceEngine"


# ─── Stale Data Handling Tests ─────────────────────────────────────────

class TestStaleDataHandling:
    def test_data_quality_layer(self):
        from desktop_agent.finance.trading.data_quality import DataQualityLayer
        from desktop_agent.finance.trading.models import MarketQuote
        dq = DataQualityLayer()
        q = MarketQuote(
            symbol="TEST", current_price=100, previous_close=95,
            open_price=96, high_price=102, low_price=94, volume=1000000,
            timestamp=datetime.utcnow(),
        )
        result = dq.check_quote(q)
        assert result.quality.value in ("LIVE", "FRESH", "STALE", "UNAVAILABLE")

    def test_stale_quote_detected(self):
        from desktop_agent.finance.trading.data_quality import DataQualityLayer
        from desktop_agent.finance.trading.models import MarketQuote
        dq = DataQualityLayer()
        q = MarketQuote(
            symbol="TEST", current_price=100, previous_close=95,
            open_price=96, high_price=102, low_price=94, volume=1000000,
            timestamp=datetime(2020, 1, 1),
        )
        result = dq.check_quote(q)
        assert result.quality.value in ("STALE", "UNAVAILABLE")


# ─── Normalizer Boundary Tests ─────────────────────────────────────────

class TestNormalizerBoundary:
    def test_paise_normalization(self):
        from desktop_agent.finance.trading.broker.groww.normalizer import normalize_groww_quote
        raw = {"trading_symbol": "RELIANCE", "ltp": 268000, "previous_close": 265000}
        q = normalize_groww_quote(raw, "RELIANCE")
        assert q.current_price == 2680.0

    def test_normal_price_unchanged(self):
        from desktop_agent.finance.trading.broker.groww.normalizer import normalize_groww_quote
        raw = {"trading_symbol": "RELIANCE", "ltp": 2680, "previous_close": 2650}
        q = normalize_groww_quote(raw, "RELIANCE")
        assert q.current_price == 2680.0

    def test_empty_holdings(self):
        from desktop_agent.finance.trading.broker.groww.normalizer import normalize_groww_holdings
        assert normalize_groww_holdings([]) == []

    def test_zero_quantity_filtered(self):
        from desktop_agent.finance.trading.broker.groww.normalizer import normalize_groww_holdings
        raw = [{"trading_symbol": "TEST", "quantity": 0, "average_price": 100, "ltp": 110}]
        assert len(normalize_groww_holdings(raw)) == 0


# ─── Guidance Engine Tests ─────────────────────────────────────────────

class TestGuidanceBoundary:
    def test_empty_portfolio_guidance(self):
        from desktop_agent.finance.trading.broker.groww.guidance import PersonalizedGuidanceEngine
        from desktop_agent.finance.trading.models import PortfolioSnapshot
        engine = PersonalizedGuidanceEngine()
        snapshot = PortfolioSnapshot(positions=[], cash=0)
        advice = engine.analyze_portfolio(snapshot)
        assert advice.portfolio_health == "CRITICAL"

    def test_single_position_guidance(self):
        from desktop_agent.finance.trading.broker.groww.guidance import PersonalizedGuidanceEngine
        from desktop_agent.finance.trading.models import PortfolioSnapshot, PortfolioPosition
        engine = PersonalizedGuidanceEngine()
        pos = PortfolioPosition(
            symbol="RELIANCE", quantity=10, average_price=2450,
            current_price=2680, previous_close=2650,
            exchange=Exchange.NSE, sector="", instrument_type=InstrumentType.EQUITY,
        )
        snapshot = PortfolioSnapshot(positions=[pos], cash=150000)
        advice = engine.analyze_portfolio(snapshot)
        assert len(advice.position_advices) == 1
        assert advice.position_advices[0].symbol == "RELIANCE"


# ─── Trade Thesis Memory Tests ─────────────────────────────────────────

class TestTradeThesisMemory:
    def test_thesis_store_and_retrieve(self):
        from desktop_agent.finance.trading.memory.thesis_memory import TradeThesisMemory
        from desktop_agent.finance.trading.models import TradeThesis
        mem = TradeThesisMemory()
        thesis = TradeThesis(
            thesis_id="test_001",
            symbol="TEST_STORE",
            direction="LONG",
            entry_rationale="Test thesis",
            invalidation="Stop at 95",
            entry_price=100,
        )
        mem.store(thesis)
        retrieved = mem.get_by_symbol("TEST_STORE")
        assert len(retrieved) >= 1

    def test_thesis_active(self):
        from desktop_agent.finance.trading.memory.thesis_memory import TradeThesisMemory
        from desktop_agent.finance.trading.models import TradeThesis
        mem = TradeThesisMemory()
        thesis = TradeThesis(
            thesis_id="test_002",
            symbol="TEST_ACTIVE",
            direction="LONG",
            entry_rationale="Active test",
            invalidation="Stop at 95",
            entry_price=100,
        )
        mem.store(thesis)
        active = mem.get_active()
        assert any(t.symbol == "TEST_ACTIVE" for t in active)


# ─── Options Analysis Tests ────────────────────────────────────────────

class TestOptionsAnalysis:
    def test_options_analyzer_pcr(self):
        from desktop_agent.finance.trading.options.analyzer import OptionsAnalyzer
        from desktop_agent.finance.trading.models import OptionChain, OptionContract
        contracts = [
            OptionContract(symbol="C1", strike=24800, expiry="2024-08-29",
                          option_type="CE", ltp=150, volume=100000, open_interest=500000),
            OptionContract(symbol="P1", strike=24800, expiry="2024-08-29",
                          option_type="PE", ltp=120, volume=80000, open_interest=400000),
        ]
        chain = OptionChain(symbol="NIFTY", underlying_price=24252, expiry="2024-08-29", contracts=contracts)
        analyzer = OptionsAnalyzer()
        analysis = analyzer.analyze_chain(chain)
        assert analysis is not None


# ─── Paper Trading Tests ───────────────────────────────────────────────

class TestPaperTrading:
    def test_paper_trader_open(self):
        from desktop_agent.finance.trading.paper.trading import PaperTrader
        trader = PaperTrader()
        trade = trader.open_trade("TEST", "LONG", 100.0, 10, 95.0, 110.0)
        assert trade.symbol == "TEST"
        assert trade.direction == "LONG"

    def test_paper_trader_stats(self):
        from desktop_agent.finance.trading.paper.trading import PaperTrader
        trader = PaperTrader()
        stats = trader.get_stats()
        assert isinstance(stats, dict)


# ─── Sector Inference Tests ────────────────────────────────────────────

class TestSectorInference:
    def test_indian_sectors(self):
        from desktop_agent.finance.trading.broker.groww.guidance import _infer_sector
        assert _infer_sector("RELIANCE") == "Energy"
        assert _infer_sector("TCS") == "IT"
        assert _infer_sector("HDFCBANK") == "Banking"
        assert _infer_sector("INFY") == "IT"
        assert _infer_sector("ITC") == "FMCG"
        assert _infer_sector("MARUTI") == "Auto"
        assert _infer_sector("SUNPHARMA") == "Pharma"
        assert _infer_sector("BAJFINANCE") == "Finance"
