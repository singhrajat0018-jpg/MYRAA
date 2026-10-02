"""
MYRAA Trading Intelligence Engine — Main Orchestrator (Part 25)

USER -> SUPER-BRAIN -> TRADING capability -> Trading Intelligence Engine
-> existing data/tools -> verification -> Memory

This is a SPECIALIZED capability under Super-Brain.
It is NOT a second cognitive authority.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import (
    BacktestResult,
    DailyMarketCloseReport,
    DataQuality,
    Exchange,
    FundamentalSnapshot,
    InstrumentType,
    MarketMover,
    MarketQuote,
    MarketSnapshot,
    NewsItem,
    OHLCV,
    OptionChain,
    PaperTrade,
    PortfolioPosition,
    PortfolioSnapshot,
    SignalType,
    TechnicalAnalysis,
    TradePlan,
    TradeRecommendation,
    TradeThesis,
    TrendDirection,
)
from .data_quality import DataQualityLayer
from .technical.engine import TechnicalEngine
from .fundamental.analyzer import FundamentalAnalyzer
from .fundamental.news import NewsAnalyzer
from .fundamental.sector import SectorAnalyzer
from .scanner.market_scanner import MarketScanner
from .trade_plan.engine import TradePlanEngine
from .risk.engine import TradingRiskEngine
from .options.analyzer import OptionsAnalyzer
from .options.strategy import OptionsStrategyEngine
from .portfolio.analytics import PortfolioAnalytics
from .memory.thesis_memory import TradeThesisMemory
from .daily_close import DailyCloseAnalyzer
from .paper.trading import PaperTrader
from .paper.backtest import Backtester
from .broker.adapter import BrokerAdapter

logger = logging.getLogger(__name__)


@dataclass
class TradingConfig:
    max_position_pct: float = 5.0
    max_risk_per_trade_pct: float = 2.0
    max_sector_pct: float = 25.0
    max_single_stock_pct: float = 15.0
    min_risk_reward: float = 1.5
    min_confidence: float = 0.4
    stop_atr_multiplier: float = 2.0
    target_atr_multiplier: float = 3.0
    watchlist_limit: int = 20
    scan_limit: int = 50


@dataclass
class StockAnalysisResult:
    symbol: str
    technical: Optional[TechnicalAnalysis] = None
    fundamental: Optional[Any] = None
    news: Optional[Any] = None
    options: Optional[Any] = None
    sector: Optional[Any] = None
    risk: Optional[Any] = None
    recommendation: Optional[TradeRecommendation] = None
    data_quality: DataQuality = DataQuality.UNAVAILABLE
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TradingIntelligenceEngine:
    """
    Professional-grade trading decision-support and portfolio-intelligence system.
    Orchestrates all analysis modules into coherent recommendations.
    """

    def __init__(self, config: TradingConfig | None = None):
        self.config = config or TradingConfig()
        self._data_quality = DataQualityLayer()
        self._technical = TechnicalEngine()
        self._fundamental = FundamentalAnalyzer()
        self._news = NewsAnalyzer()
        self._sector = SectorAnalyzer()
        self._scanner = MarketScanner()
        self._trade_plan = TradePlanEngine()
        self._risk = TradingRiskEngine()
        self._options = OptionsAnalyzer()
        self._options_strategy = OptionsStrategyEngine()
        self._portfolio_analytics = PortfolioAnalytics()
        self._thesis_memory = TradeThesisMemory()
        self._daily_close = DailyCloseAnalyzer()
        self._paper_trader = PaperTrader()
        self._backtester = Backtester()
        self._broker = BrokerAdapter()

    def analyze_stock(
        self,
        symbol: str,
        quote: MarketQuote,
        bars: List[OHLCV],
        bars_by_tf: Dict[str, List[OHLCV]] | None = None,
        fundamental: FundamentalSnapshot | None = None,
        news_headlines: List[NewsItem] | None = None,
        option_chain: OptionChain | None = None,
        portfolio: PortfolioSnapshot | None = None,
        peer_quotes: Dict[str, MarketQuote] | None = None,
        sector: str = "",
    ) -> StockAnalysisResult:
        """Full professional analysis of a single stock."""
        result = StockAnalysisResult(symbol=symbol)

        dq_check = self._data_quality.check_quote(quote)
        result.data_quality = dq_check.quality

        technical = self._technical.analyze(bars, bars_by_tf)
        technical.symbol = symbol
        result.technical = technical

        if fundamental:
            result.fundamental = self._fundamental.analyze(fundamental)

        if news_headlines:
            result.news = self._news.analyze(symbol, news_headlines)

        if option_chain:
            result.options = self._options.analyze_chain(option_chain)

        if sector and peer_quotes:
            result.sector = self._sector.compare(symbol, sector, quote, peer_quotes)

        risk = self._risk.evaluate(symbol, quote, portfolio, technical, self.config)
        result.risk = risk

        recommendation = self._trade_plan.generate_recommendation(
            symbol=symbol,
            technical=technical,
            fundamental=result.fundamental,
            news=result.news,
            options=result.options,
            risk=risk,
        )

        if portfolio:
            adjusted = self._portfolio_analytics.portfolio_aware_recommendation(
                symbol, recommendation, portfolio
            )
            if adjusted:
                recommendation = adjusted

        result.recommendation = recommendation
        return result

    def scan_market(
        self,
        quotes: Dict[str, MarketQuote],
        bars_map: Dict[str, List[OHLCV]],
    ) -> Dict[str, List[MarketMover]]:
        """Market-wide scanner for opportunities and risks."""
        return self._scanner.scan(quotes, bars_map)

    def analyze_options(
        self,
        chain: OptionChain,
        direction: str = "NEUTRAL",
        risk_tolerance: str = "MEDIUM",
    ) -> Dict[str, Any]:
        """NIFTY/BankNIFTY options analysis."""
        analysis = self._options.analyze_chain(chain)
        strategies = self._options_strategy.rank_strategies(
            self._options_strategy.suggest_strategies(chain, direction, risk_tolerance),
            direction,
            chain.underlying_price,
        )
        return {
            "analysis": analysis,
            "strategies": strategies,
        }

    def analyze_portfolio(
        self,
        positions: List[PortfolioPosition],
        quotes: Dict[str, MarketQuote],
        cash: float = 0.0,
    ) -> PortfolioSnapshot:
        """Full portfolio analysis with allocation and concentration."""
        for pos in positions:
            q = quotes.get(pos.symbol)
            if q:
                pos.current_price = q.current_price
                pos.previous_close = q.previous_close
        snapshot = PortfolioSnapshot(positions=positions, cash=cash)
        return snapshot

    def check_portfolio_risks(self, snapshot: PortfolioSnapshot) -> List[Dict[str, Any]]:
        """Concentration and portfolio-level risk checks."""
        return self._portfolio_analytics.check_concentration(
            snapshot,
            self.config.max_single_stock_pct,
            self.config.max_sector_pct,
        )

    def store_thesis(self, thesis: TradeThesis) -> None:
        """Store a trade thesis in memory."""
        self._thesis_memory.store(thesis)

    def get_thesis_history(self, symbol: str | None = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve trade thesis history."""
        if symbol:
            theses = self._thesis_memory.get_by_symbol(symbol)
        else:
            theses = self._thesis_memory.get_history(limit)
        return [t.to_dict() for t in theses[:limit]]

    def daily_market_close(
        self,
        market_data: Dict[str, Any],
        portfolio: PortfolioSnapshot | None = None,
        scanner_results: Dict[str, List[MarketMover]] | None = None,
    ) -> DailyMarketCloseReport:
        """Autonomous post-close workflow."""
        return self._daily_close.analyze(market_data, portfolio, scanner_results)

    def paper_open(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        stop_loss: float = 0.0,
        target: float = 0.0,
    ) -> PaperTrade:
        return self._paper_trader.open_trade(
            symbol, direction, entry_price, quantity, stop_loss, target
        )

    def paper_close(self, trade_id: str, exit_price: float) -> PaperTrade:
        return self._paper_trader.close_trade(trade_id, exit_price)

    def paper_stats(self) -> Dict[str, Any]:
        return self._paper_trader.get_stats()

    def backtest(
        self,
        symbol: str,
        bars: List[OHLCV],
        strategy_fn,
    ) -> BacktestResult:
        return self._backtester.run(symbol, bars, strategy_fn)

    def broker_account(self) -> Dict[str, Any]:
        return self._broker.get_account()

    def broker_positions(self) -> List[PortfolioPosition]:
        return self._broker.get_positions()

    def status(self) -> Dict[str, Any]:
        return {
            "engine": "TradingIntelligenceEngine",
            "version": "1.0.0",
            "config": {
                "max_position_pct": self.config.max_position_pct,
                "max_risk_per_trade_pct": self.config.max_risk_per_trade_pct,
                "max_sector_pct": self.config.max_sector_pct,
                "min_risk_reward": self.config.min_risk_reward,
            },
            "active_theses": len(self._thesis_memory.get_active()),
            "paper_trades_open": len(self._paper_trader.get_open_trades()),
            "broker_connected": self._broker.is_connected(),
        }
