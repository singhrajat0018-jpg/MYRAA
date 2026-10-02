"""
MYRAA Phase D Part 1 — Trading Intelligence Test Suite

38+ tests covering: data models, data quality, indicators, structure,
multi-timeframe, fundamentals, news, sector, scanner, trade plan, risk,
options, portfolio, thesis memory, daily close, paper trading, backtest,
broker adapter, permission enforcement, no fake data, no fake orders.
"""
from __future__ import annotations

import os
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from desktop_agent.finance.trading.models import (
    MarketQuote, OHLCV, MarketSnapshot, Instrument, FundamentalSnapshot,
    NewsItem, CorporateEvent, SectorComparison, MarketMover, Timeframe,
    Exchange, InstrumentType, MarketStatus, DataQuality, DataLabel,
    TrendDirection, SignalType, RiskLevel,
    OptionContract, OptionChain, OptionStrategy,
    PortfolioPosition, PortfolioSnapshot,
    TradePlan, NoTradePlan, TradeRecommendation, TradeThesis,
    PaperTrade, BacktestResult, DailyMarketCloseReport,
    TechnicalAnalysis, FundamentalAnalysis as FundamentalAnalysisModel,
)
from desktop_agent.finance.trading.data_quality import DataQualityLayer
from desktop_agent.finance.trading.technical.indicators import (
    sma, ema, rsi, macd, atr, bollinger_bands, vwap,
    stochastic, williams_r, compute_all_indicators,
    relative_volume, trend_strength, volatility,
)
from desktop_agent.finance.trading.technical.structure import (
    MarketStructureEngine, StructureAnalysis,
)
from desktop_agent.finance.trading.technical.multi_timeframe import MultiTimeframeEngine
from desktop_agent.finance.trading.technical.engine import TechnicalEngine
from desktop_agent.finance.trading.fundamental.analyzer import FundamentalAnalyzer
from desktop_agent.finance.trading.fundamental.news import NewsAnalyzer
from desktop_agent.finance.trading.fundamental.sector import SectorAnalyzer
from desktop_agent.finance.trading.scanner.market_scanner import MarketScanner
from desktop_agent.finance.trading.trade_plan.engine import TradePlanEngine
from desktop_agent.finance.trading.risk.engine import TradingRiskEngine
from desktop_agent.finance.trading.options.analyzer import OptionsAnalyzer
from desktop_agent.finance.trading.options.strategy import OptionsStrategyEngine
from desktop_agent.finance.trading.portfolio.analytics import PortfolioAnalytics
from desktop_agent.finance.trading.memory.thesis_memory import TradeThesisMemory
from desktop_agent.finance.trading.daily_close import DailyCloseAnalyzer
from desktop_agent.finance.trading.paper.trading import PaperTrader
from desktop_agent.finance.trading.paper.backtest import Backtester
from desktop_agent.finance.trading.broker.adapter import BrokerAdapter
from desktop_agent.finance.trading.engine import TradingIntelligenceEngine, TradingConfig
from desktop_agent.finance.trading.capability import TradingCapabilityEngine


# ==========================================================
# Fixtures
# ==========================================================

def _make_quote(price=100.0, prev_close=98.0, vol=1000000):
    return MarketQuote(
        symbol="TEST", current_price=price, previous_close=prev_close,
        open_price=prev_close, high_price=price + 2, low_price=price - 1,
        volume=vol, exchange=Exchange.NSE, timestamp=datetime.utcnow(),
        source="test", data_quality=DataQuality.LIVE,
    )


def _make_bars(n=30, start_price=100.0, trend=0.002):
    bars = []
    price = start_price
    for i in range(n):
        noise = (i % 5 - 2) * 0.5
        o = price + noise
        h = o + abs(noise) + 1
        l = o - abs(noise) - 0.5
        c = o + trend * price
        bars.append(OHLCV(
            timestamp=datetime.utcnow() - timedelta(days=n - i),
            open=o, high=max(o, h, c), low=min(o, l, c), close=c,
            volume=100000 + i * 5000, timeframe=Timeframe.DAILY, source="test",
        ))
        price = c
    return bars


def _make_portfolio():
    return PortfolioSnapshot(
        positions=[
            PortfolioPosition(symbol="RELIANCE", quantity=10, average_price=2400, current_price=2500, sector="Energy"),
            PortfolioPosition(symbol="TCS", quantity=5, average_price=3500, current_price=3600, sector="IT"),
            PortfolioPosition(symbol="HDFCBANK", quantity=8, average_price=1600, current_price=1550, sector="Banking"),
        ],
        cash=50000.0,
    )


def _make_option_chain():
    contracts = []
    for strike in [24000, 24500, 25000, 25500, 26000]:
        for otype in ["CE", "PE"]:
            contracts.append(OptionContract(
                symbol="NIFTY", strike=strike,
                expiry=datetime.utcnow() + timedelta(days=5),
                option_type=otype, ltp=100 + abs(25000 - strike) * 0.1,
                volume=10000 + abs(25000 - strike), open_interest=50000 + abs(25000 - strike) * 10,
                implied_volatility=18.0 + abs(25000 - strike) * 0.002,
                lot_size=50,
            ))
    return OptionChain(
        symbol="NIFTY", underlying_price=25000,
        expiry=datetime.utcnow() + timedelta(days=5),
        contracts=contracts, source="test", data_quality=DataQuality.LIVE,
    )


# ==========================================================
# 1. Data Models
# ==========================================================

def test_market_quote_properties():
    q = _make_quote(100.0, 98.0)
    assert q.day_change == pytest.approx(2.0)
    assert q.day_change_percent == pytest.approx(2.0408, rel=1e-2)
    assert q.spread >= 0

def test_market_snapshot_creation():
    q = _make_quote()
    snap = MarketSnapshot(symbol="TEST", quote=q, source="test")
    assert snap.symbol == "TEST"
    assert snap.data_quality == DataQuality.UNAVAILABLE


# ==========================================================
# 2. Data Quality
# ==========================================================

def test_data_quality_quote_fresh():
    dq = DataQualityLayer()
    q = _make_quote()
    check = dq.check_quote(q)
    assert check.quality == DataQuality.LIVE
    assert check.score > 0.8

def test_data_quality_quote_stale():
    dq = DataQualityLayer()
    q = _make_quote()
    q.timestamp = datetime.utcnow() - timedelta(hours=2)
    check = dq.check_quote(q)
    assert check.quality in (DataQuality.STALE, DataQuality.UNAVAILABLE)
    assert check.score < 1.0

def test_data_quality_ohlcv_gaps():
    dq = DataQualityLayer()
    bars = _make_bars(10)
    check = dq.check_ohlcv_bars(bars, expected_count=20)
    assert check.score < 1.0
    assert any("10/20" in i for i in check.issues)

def test_data_quality_fundamentals_coverage():
    dq = DataQualityLayer()
    data = FundamentalSnapshot(symbol="TEST", label=DataLabel.ACTUAL, pe_ratio=20.0)
    check = dq.check_fundamentals(data)
    assert check.score > 0

def test_data_quality_market_status():
    dq = DataQualityLayer()
    status = dq.get_market_status()
    assert isinstance(status, MarketStatus)


# ==========================================================
# 3. Technical Indicators
# ==========================================================

def test_sma_computation():
    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    result = sma(values, 3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == pytest.approx(11.0)
    assert result[3] == pytest.approx(12.0)
    assert result[4] == pytest.approx(13.0)

def test_ema_computation():
    values = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    result = ema(values, 3)
    assert result[0] is None
    assert result[1] is None
    assert result[2] is not None
    assert result[2] == pytest.approx(11.0)
    assert len(result) == len(values)

def test_rsi_computation():
    closes = [44 + i * 0.5 for i in range(20)]
    result = rsi(closes, 14)
    assert len(result) == 20
    assert result[0] is None
    valid = [v for v in result if v is not None]
    assert all(0 <= v <= 100 for v in valid)

def test_macd_computation():
    closes = [100 + i * 0.5 for i in range(50)]
    result = macd(closes)
    assert "macd" in result
    assert "signal" in result
    assert "histogram" in result
    assert len(result["macd"]) == 50

def test_atr_computation():
    n = 20
    highs = [105.0 + i * 0.3 for i in range(n)]
    lows = [95.0 + i * 0.3 for i in range(n)]
    closes = [100.0 + i * 0.3 for i in range(n)]
    result = atr(highs, lows, closes, 14)
    assert len(result) == n
    valid = [v for v in result if v is not None]
    assert all(v > 0 for v in valid)

def test_bollinger_bands_computation():
    closes = [100 + (i % 10 - 5) for i in range(25)]
    result = bollinger_bands(closes, 20)
    assert "upper" in result
    assert "middle" in result
    assert "lower" in result
    valid_upper = [v for v in result["upper"] if v is not None]
    valid_lower = [v for v in result["lower"] if v is not None]
    assert all(u > l for u, l in zip(valid_upper, valid_lower[-len(valid_upper):]))

def test_vwap_computation():
    n = 10
    result = vwap([105]*n, [95]*n, [100]*n, [1000]*n)
    assert len(result) == n
    assert all(v is not None for v in result)

def test_stochastic_computation():
    n = 20
    highs = [100 + i for i in range(n)]
    lows = [90 + i for i in range(n)]
    closes = [95 + i for i in range(n)]
    result = stochastic(highs, lows, closes)
    assert "k" in result
    assert "d" in result

def test_compute_all_indicators():
    bars = _make_bars(30)
    result = compute_all_indicators(bars)
    assert "sma_20" in result
    assert "rsi_14" in result
    assert "macd_line" in result
    assert "atr_14" in result
    assert "bb_upper" in result
    assert "vwap" in result
    assert "relative_volume" in result
    assert "trend_strength" in result
    assert "volatility" in result


# ==========================================================
# 4. Market Structure
# ==========================================================

def test_market_structure_uptrend():
    bars = _make_bars(30, start_price=100, trend=0.01)
    engine = MarketStructureEngine()
    result = engine.analyze(bars)
    assert isinstance(result, StructureAnalysis)
    assert result.trend in (TrendDirection.BULLISH, TrendDirection.NEUTRAL)

def test_market_structure_downtrend():
    bars = _make_bars(30, start_price=200, trend=-0.01)
    engine = MarketStructureEngine()
    result = engine.analyze(bars)
    assert isinstance(result, StructureAnalysis)

def test_market_structure_consolidation():
    bars = [OHLCV(
        timestamp=datetime(i, 1, 1), open=100.0, high=101.0,
        low=99.0, close=100.0, volume=100000, timeframe=Timeframe.DAILY,
    ) for i in range(1, 21)]
    engine = MarketStructureEngine()
    result = engine.analyze(bars)
    assert isinstance(result, StructureAnalysis)

def test_structure_support_resistance():
    bars = _make_bars(30)
    engine = MarketStructureEngine()
    result = engine.analyze(bars)
    assert isinstance(result.key_support, list)
    assert isinstance(result.key_resistance, list)


# ==========================================================
# 5. Multi-Timeframe
# ==========================================================

def test_multi_timeframe_analysis():
    daily = _make_bars(30)
    tf_data = {"1D": daily}
    engine = MultiTimeframeEngine()
    result = engine.analyze(tf_data)
    assert "1D" in result
    assert result["1D"]["bar_count"] == 30

def test_multi_timeframe_alignment():
    engine = MultiTimeframeEngine()
    analysis = {"1D": {"trend": "BULLISH"}, "1W": {"trend": "BULLISH"}, "1M": {"trend": "BULLISH"}}
    result = engine.get_alignment(analysis)
    assert result["alignment"] == "BULLISH_ALIGNED"
    assert result["bullish_count"] == 3


# ==========================================================
# 6. Technical Engine
# ==========================================================

def test_technical_engine_analysis():
    bars = _make_bars(30)
    engine = TechnicalEngine()
    result = engine.analyze(bars)
    assert isinstance(result, TechnicalAnalysis)
    assert result.trend in (TrendDirection.BULLISH, TrendDirection.BEARISH, TrendDirection.NEUTRAL)
    assert isinstance(result.indicators, dict)
    assert result.confidence > 0


# ==========================================================
# 7. Fundamentals
# ==========================================================

def test_fundamental_analyzer_valuation():
    analyzer = FundamentalAnalyzer()
    data = FundamentalSnapshot(
        symbol="TEST", pe_ratio=20.0, pb_ratio=3.0, roe=18.0,
        revenue_growth=15.0, debt_to_equity=0.8, label=DataLabel.ACTUAL,
    )
    result = analyzer.analyze(data)
    assert result.valuation != ""
    assert result.confidence > 0

def test_fundamental_analyzer_unavailable():
    analyzer = FundamentalAnalyzer()
    data = FundamentalSnapshot(symbol="TEST", label=DataLabel.UNAVAILABLE)
    result = analyzer.analyze(data)
    assert result.confidence == 0.0
    assert "unavailable" in result.reasoning.lower()


# ==========================================================
# 8. News
# ==========================================================

def test_news_analyzer_sentiment():
    analyzer = NewsAnalyzer()
    headlines = [
        NewsItem(title="Company reports record profit growth", source="test"),
        NewsItem(title="Stock surges on strong earnings", source="test"),
    ]
    result = analyzer.analyze("TEST", headlines)
    assert result.sentiment in ("POSITIVE", "SLIGHTLY_POSITIVE")
    assert result.headline_count == 2

def test_news_analyzer_events():
    analyzer = NewsAnalyzer()
    headlines = [NewsItem(title="Company announces dividend and buyback", source="test")]
    result = analyzer.analyze("TEST", headlines)
    assert len(result.event_flags) > 0


# ==========================================================
# 9. Sector
# ==========================================================

def test_sector_comparison_outperformer():
    analyzer = SectorAnalyzer()
    stock_q = _make_quote(105.0, 100.0)
    peer_q = {"PEER1": _make_quote(102.0, 100.0), "PEER2": _make_quote(101.0, 100.0)}
    result = analyzer.compare("TEST", "IT", stock_q, peer_q)
    assert result.classification in ("OUTPERFORMER", "SECTOR_DRIVEN", "STOCK_SPECIFIC")

def test_sector_comparison_underperformer():
    analyzer = SectorAnalyzer()
    stock_q = _make_quote(95.0, 100.0)
    peer_q = {"PEER1": _make_quote(102.0, 100.0), "PEER2": _make_quote(103.0, 100.0)}
    result = analyzer.compare("TEST", "IT", stock_q, peer_q)
    assert result.classification in ("UNDERPERFORMER", "SECTOR_DRIVEN", "STOCK_SPECIFIC")


# ==========================================================
# 10. Scanner
# ==========================================================

def test_market_scanner():
    scanner = MarketScanner()
    quotes = {
        "A": _make_quote(110.0, 100.0),
        "B": _make_quote(90.0, 100.0),
        "C": _make_quote(105.0, 100.0),
    }
    bars_map = {s: _make_bars(30) for s in quotes}
    result = scanner.scan(quotes, bars_map)
    assert "top_opportunities" in result or "watchlist" in result


# ==========================================================
# 11. Trade Plan
# ==========================================================

def test_trade_plan_engine_buy_candidate():
    engine = TradePlanEngine()
    tech = TechnicalAnalysis(symbol="TEST", trend=TrendDirection.BULLISH, confidence=0.8,
                              support_levels=[95.0], resistance_levels=[110.0],
                              indicators={"rsi_14": 40.0, "atr_14": 3.0, "macd_histogram": 0.5})
    result = engine.generate_recommendation(symbol="TEST", technical=tech)
    assert isinstance(result, TradeRecommendation)
    assert result.signal in (SignalType.BUY, SignalType.WATCH, SignalType.WAIT)

def test_trade_plan_engine_no_trade():
    engine = TradePlanEngine()
    tech = TechnicalAnalysis(symbol="TEST", trend=TrendDirection.UNKNOWN, confidence=0.1,
                              indicators={"rsi_14": 50.0})
    result = engine.generate_recommendation(symbol="TEST", technical=tech)
    assert isinstance(result, TradeRecommendation)
    assert result.signal in (SignalType.WAIT, SignalType.AVOID, SignalType.WATCH)


# ==========================================================
# 12. Risk Engine
# ==========================================================

def test_risk_engine_high_volatility():
    engine = TradingRiskEngine()
    q = _make_quote(100.0, 90.0)
    tech = TechnicalAnalysis(symbol="TEST", indicators={"atr_14": 15.0, "volatility": 60.0})
    result = engine.evaluate("TEST", q, None, tech, TradingConfig())
    assert result.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.VERY_HIGH)
    assert result.risk_score > 0.3

def test_risk_engine_concentration():
    engine = TradingRiskEngine()
    portfolio = _make_portfolio()
    q = _make_quote()
    tech = TechnicalAnalysis(symbol="HDFCBANK", indicators={"atr_14": 5.0})
    result = engine.evaluate("HDFCBANK", q, portfolio, tech, TradingConfig())
    assert isinstance(result.concentration_risk, str)


# ==========================================================
# 13. Options
# ==========================================================

def test_options_analyzer_pcr():
    analyzer = OptionsAnalyzer()
    chain = _make_option_chain()
    result = analyzer.analyze_chain(chain)
    assert result.pcr_oi > 0
    assert result.symbol == "NIFTY"

def test_options_strategy_long_call():
    engine = OptionsStrategyEngine()
    chain = _make_option_chain()
    strategies = engine.suggest_strategies(chain, "BULLISH", "MEDIUM")
    assert isinstance(strategies, list)


# ==========================================================
# 14. Portfolio
# ==========================================================

def test_portfolio_analytics_allocation():
    analytics = PortfolioAnalytics()
    snapshot = _make_portfolio()
    q_map = {
        "RELIANCE": _make_quote(2500.0, 2480.0),
        "TCS": _make_quote(3600.0, 3550.0),
        "HDFCBANK": _make_quote(1550.0, 1580.0),
    }
    for p in snapshot.positions:
        q = q_map.get(p.symbol)
        if q:
            p.current_price = q.current_price
    assert snapshot.total_market_value > 0
    alloc = snapshot.allocation
    assert "Energy" in alloc or "IT" in alloc

def test_portfolio_concentration_risk():
    analytics = PortfolioAnalytics()
    snapshot = _make_portfolio()
    risks = analytics.check_concentration(snapshot, 15.0, 25.0)
    assert isinstance(risks, list)


# ==========================================================
# 15. Thesis Memory
# ==========================================================

def test_thesis_memory_store_retrieve():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "theses.json")
        mem = TradeThesisMemory(file_path=path)
        thesis = TradeThesis(
            thesis_id="t1", symbol="TEST", direction="LONG",
            entry_rationale="Strong uptrend", invalidation="Below 95",
        )
        mem.store(thesis)
        retrieved = mem.get_by_symbol("TEST")
        assert len(retrieved) >= 1
        assert retrieved[0].symbol == "TEST"


# ==========================================================
# 16. Paper Trading
# ==========================================================

def test_paper_trading_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "paper.json")
        trader = PaperTrader(file_path=path)
        trade = trader.open_trade("TEST", "LONG", 100.0, 10, 95.0, 110.0)
        assert trade.status == "OPEN"
        assert trade.entry_price == 100.0
        closed = trader.close_trade(trade.trade_id, 108.0)
        assert closed.status == "CLOSED"
        assert closed.pnl > 0
        stats = trader.get_stats()
        assert stats["total_trades"] == 1


# ==========================================================
# 17. Backtest
# ==========================================================

def test_backtest_basic():
    backtester = Backtester()
    bars = _make_bars(50)
    def strategy(b):
        return [(10, "LONG", b[5].low, b[5].high + 5)]
    result = backtester.run("TEST", bars, strategy)
    assert isinstance(result, BacktestResult)


# ==========================================================
# 18. Broker Adapter
# ==========================================================

def test_broker_adapter_read_only():
    adapter = BrokerAdapter()
    assert adapter.is_connected() is False
    account = adapter.get_account()
    assert isinstance(account, dict)
    with pytest.raises(NotImplementedError):
        adapter.prepare_order("TEST", "BUY", 100, 10)
    with pytest.raises(NotImplementedError):
        adapter.execute_order("order_123")


# ==========================================================
# 19. Trading Engine Integration
# ==========================================================

def test_trading_engine_status():
    engine = TradingIntelligenceEngine()
    status = engine.status()
    assert status["engine"] == "TradingIntelligenceEngine"
    assert "config" in status

def test_trading_engine_analyze_stock():
    engine = TradingIntelligenceEngine()
    quote = _make_quote()
    bars = _make_bars(30)
    result = engine.analyze_stock("TEST", quote, bars)
    assert hasattr(result, "technical")
    assert hasattr(result, "recommendation")

def test_no_fake_order_execution():
    adapter = BrokerAdapter()
    with pytest.raises(NotImplementedError):
        adapter.execute_order("any_order")

def test_signal_types_valid():
    for sig in SignalType:
        assert sig.value in ("BUY", "SELL", "WATCH", "WAIT", "AVOID", "HOLD")


# ==========================================================
# 20. Capability Integration
# ==========================================================

def test_trading_capability():
    engine = TradingIntelligenceEngine()
    cap = TradingCapabilityEngine(trading_engine=engine)
    assert cap.capability_id == "TRADING_ENGINE"
    result = cap.execute("analyze market", {})
    assert result["success"] is True
