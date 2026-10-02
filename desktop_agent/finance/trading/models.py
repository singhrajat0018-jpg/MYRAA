"""
MYRAA Trading Intelligence — Canonical Data Models (Part 1)

All market data records flow through these normalized structures.
Never mix stale and current data without labeling it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


# ==========================================================
# Enums
# ==========================================================

class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"
    UNKNOWN = "UNKNOWN"


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    CURRENCY = "CURRENCY"
    COMMODITY = "COMMODITY"


class MarketStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_OPEN = "PRE_OPEN"
    POST_CLOSE = "POST_CLOSE"
    HOLIDAY = "HOLIDAY"
    UNKNOWN = "UNKNOWN"


class DataQuality(str, Enum):
    LIVE = "LIVE"
    FRESH = "FRESH"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"


class Timeframe(str, Enum):
    MONTHLY = "1M"
    WEEKLY = "1W"
    DAILY = "1D"
    FOUR_H = "4H"
    ONE_H = "1H"
    FIFTEEN_M = "15M"
    FIVE_M = "5M"
    ONE_MIN = "1M"


class TrendDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WATCH = "WATCH"
    WAIT = "WAIT"
    AVOID = "AVOID"
    HOLD = "HOLD"


class RiskLevel(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class DataLabel(str, Enum):
    ACTUAL = "ACTUAL"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


# ==========================================================
# Core Market Data Models
# ==========================================================

@dataclass
class Instrument:
    symbol: str
    exchange: Exchange = Exchange.NSE
    instrument_type: InstrumentType = InstrumentType.EQUITY
    name: str = ""
    sector: str = ""
    industry: str = ""
    isin: str = ""
    lot_size: int = 1
    tick_size: float = 0.05
    currency: str = "INR"


@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    timeframe: Timeframe = Timeframe.DAILY
    source: str = ""
    confidence: float = 1.0


@dataclass
class MarketQuote:
    symbol: str
    current_price: float
    previous_close: float
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    volume: int = 0
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_size: int = 0
    ask_size: int = 0
    exchange: Exchange = Exchange.NSE
    currency: str = "INR"
    market_status: MarketStatus = MarketStatus.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    data_quality: DataQuality = DataQuality.UNAVAILABLE
    freshness_seconds: float = 0.0

    @property
    def day_change(self) -> float:
        return self.current_price - self.previous_close

    @property
    def day_change_percent(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return ((self.current_price - self.previous_close) / self.previous_close) * 100

    @property
    def spread(self) -> float:
        if self.bid_price > 0 and self.ask_price > 0:
            return self.ask_price - self.bid_price
        return 0.0

    @property
    def spread_percent(self) -> float:
        if self.current_price == 0:
            return 0.0
        return (self.spread / self.current_price) * 100


@dataclass
class MarketSnapshot:
    symbol: str
    quote: MarketQuote
    ohlcv_bars: List[OHLCV] = field(default_factory=list)
    instrument: Optional[Instrument] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    data_quality: DataQuality = DataQuality.UNAVAILABLE
    freshness_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FundamentalSnapshot:
    symbol: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    label: DataLabel = DataLabel.UNAVAILABLE
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    eps: Optional[float] = None
    book_value: Optional[float] = None
    dividend_yield: Optional[float] = None
    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    net_income: Optional[float] = None
    net_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    avg_volume: Optional[int] = None
    shares_outstanding: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NewsItem:
    title: str
    source: str = ""
    url: str = ""
    published: datetime = field(default_factory=datetime.utcnow)
    summary: str = ""
    sentiment: str = "NEUTRAL"
    sentiment_score: float = 0.0
    relevance_score: float = 0.0
    symbols: List[str] = field(default_factory=list)
    is_event: bool = False
    event_type: str = ""
    category: str = ""


@dataclass
class CorporateEvent:
    symbol: str
    event_type: str
    date: datetime
    description: str = ""
    impact: str = ""
    category: str = ""


@dataclass
class SectorComparison:
    sector: str
    symbol: str
    sector_avg_change: float = 0.0
    stock_change: float = 0.0
    relative_strength: float = 0.0
    sector_rank: int = 0
    total_in_sector: int = 0
    classification: str = ""


@dataclass
class MarketMover:
    symbol: str
    current_price: float
    change_percent: float
    volume: int
    relative_volume: float = 0.0
    reason: str = ""
    category: str = ""
    score: float = 0.0


# ==========================================================
# Options Data Models
# ==========================================================

@dataclass
class OptionContract:
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # "CE" or "PE"
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    open_interest: int = 0
    change_in_oi: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    in_the_money: bool = False
    margin_required: float = 0.0
    lot_size: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OptionChain:
    symbol: str
    underlying_price: float
    expiry: datetime
    contracts: List[OptionContract] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    data_quality: DataQuality = DataQuality.UNAVAILABLE

    @property
    def calls(self) -> List[OptionContract]:
        return [c for c in self.contracts if c.option_type == "CE"]

    @property
    def puts(self) -> List[OptionContract]:
        return [c for c in self.contracts if c.option_type == "PE"]

    @property
    def pcr_oi(self) -> float:
        total_call_oi = sum(c.open_interest for c in self.calls)
        total_put_oi = sum(c.open_interest for c in self.puts)
        if total_call_oi == 0:
            return 0.0
        return total_put_oi / total_call_oi

    @property
    def pcr_volume(self) -> float:
        total_call_vol = sum(c.volume for c in self.calls)
        total_put_vol = sum(c.volume for c in self.puts)
        if total_call_vol == 0:
            return 0.0
        return total_put_vol / total_call_vol

    @property
    def max_pain(self) -> float:
        if not self.contracts:
            return 0.0
        strikes = sorted(set(c.strike for c in self.contracts))
        min_pain = float("inf")
        max_pain_strike = 0.0
        for k in strikes:
            total_pain = 0.0
            for c in self.contracts:
                if c.option_type == "CE" and c.strike < k:
                    total_pain += (k - c.strike) * c.open_interest
                elif c.option_type == "PE" and c.strike > k:
                    total_pain += (c.strike - k) * c.open_interest
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = k
        return max_pain_strike

    def get_oi_walls(self, count: int = 3) -> Dict[str, List[OptionContract]]:
        call_oi = sorted(self.calls, key=lambda c: c.open_interest, reverse=True)[:count]
        put_oi = sorted(self.puts, key=lambda c: c.open_interest, reverse=True)[:count]
        return {"call_walls": call_oi, "put_walls": put_oi}


@dataclass
class OptionStrategy:
    name: str
    direction: str
    legs: List[Dict[str, Any]] = field(default_factory=list)
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    breakeven: Optional[float] = None
    capital_required: float = 0.0
    risk_reward: float = 0.0
    net_premium: float = 0.0
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0
    confidence: float = 0.0
    reasoning: str = ""


# ==========================================================
# Portfolio Models
# ==========================================================

@dataclass
class PortfolioPosition:
    symbol: str
    quantity: float
    average_price: float
    current_price: float = 0.0
    previous_close: float = 0.0
    exchange: Exchange = Exchange.NSE
    sector: str = ""
    instrument_type: InstrumentType = InstrumentType.EQUITY
    entry_date: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""

    @property
    def invested_value(self) -> float:
        return self.quantity * self.average_price

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.invested_value

    @property
    def unrealized_pnl_percent(self) -> float:
        if self.invested_value == 0:
            return 0.0
        return (self.unrealized_pnl / self.invested_value) * 100

    @property
    def day_pnl(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return self.quantity * (self.current_price - self.previous_close)

    @property
    def day_change_percent(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return ((self.current_price - self.previous_close) / self.previous_close) * 100

    @property
    def holding_duration_days(self) -> int:
        return (datetime.utcnow() - self.entry_date).days

    @property
    def weight(self) -> float:
        return 0.0


@dataclass
class PortfolioSnapshot:
    positions: List[PortfolioPosition] = field(default_factory=list)
    cash: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_invested(self) -> float:
        return sum(p.invested_value for p in self.positions)

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions)

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions)

    @property
    def total_pnl_percent(self) -> float:
        invested = self.total_invested
        if invested == 0:
            return 0.0
        return (self.total_unrealized_pnl / invested) * 100

    @property
    def total_day_pnl(self) -> float:
        return sum(p.day_pnl for p in self.positions)

    @property
    def total_portfolio_value(self) -> float:
        return self.total_market_value + self.cash

    @property
    def allocation(self) -> Dict[str, float]:
        total = self.total_market_value
        if total == 0:
            return {}
        alloc: Dict[str, float] = {}
        for p in self.positions:
            sector = p.sector or "Unknown"
            alloc[sector] = alloc.get(sector, 0.0) + p.market_value
        return {k: (v / total) * 100 for k, v in alloc.items()}

    @property
    def concentration(self) -> Dict[str, float]:
        total = self.total_market_value
        if total == 0:
            return {}
        return {p.symbol: (p.market_value / total) * 100 for p in self.positions}

    @property
    def max_concentration(self) -> float:
        conc = self.concentration
        return max(conc.values()) if conc else 0.0

    @property
    def max_sector_concentration(self) -> float:
        alloc = self.allocation
        return max(alloc.values()) if alloc else 0.0

    @property
    def position_count(self) -> int:
        return len(self.positions)

    @property
    def holding_period_avg_days(self) -> float:
        if not self.positions:
            return 0.0
        return sum(p.holding_duration_days for p in self.positions) / len(self.positions)

    def get_positions_by_sector(self) -> Dict[str, List[PortfolioPosition]]:
        result: Dict[str, List[PortfolioPosition]] = {}
        for p in self.positions:
            sector = p.sector or "Unknown"
            result.setdefault(sector, []).append(p)
        return result


# ==========================================================
# Trade Plan Models
# ==========================================================

@dataclass
class TradePlan:
    symbol: str
    direction: str  # "LONG" or "SHORT"
    setup: str
    entry_zone: str
    stop_loss: str
    target_1: str = ""
    target_2: str = ""
    target_3: str = ""
    risk_reward: float = 0.0
    confidence: float = 0.0
    catalyst: str = ""
    invalidation: str = ""
    expected_horizon: str = ""
    signal_type: SignalType = SignalType.WAIT
    reasoning: str = ""
    evidence: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "setup": self.setup,
            "entry_zone": self.entry_zone,
            "stop_loss": self.stop_loss,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "target_3": self.target_3,
            "risk_reward": self.risk_reward,
            "confidence": self.confidence,
            "catalyst": self.catalyst,
            "invalidation": self.invalidation,
            "expected_horizon": self.expected_horizon,
            "signal_type": self.signal_type.value,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
            "risk_level": self.risk_level.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class NoTradePlan:
    symbol: str
    reason: str
    signal_type: SignalType = SignalType.WAIT
    alternatives: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "signal_type": "NO_TRADE",
            "reason": self.reason,
            "alternatives": self.alternatives,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TradeRecommendation:
    symbol: str
    signal: SignalType
    confidence: float
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    trade_plan: Optional[TradePlan] = None
    no_trade: Optional[NoTradePlan] = None
    risk_level: RiskLevel = RiskLevel.MEDIUM
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "symbol": self.symbol,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
            "risk_level": self.risk_level.value,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.trade_plan:
            result["trade_plan"] = self.trade_plan.to_dict()
        if self.no_trade:
            result["no_trade"] = self.no_trade.to_dict()
        return result


# ==========================================================
# Analysis Result Models
# ==========================================================

@dataclass
class TechnicalAnalysis:
    symbol: str
    trend: TrendDirection = TrendDirection.UNKNOWN
    trend_strength: float = 0.0
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    market_structure: str = ""
    momentum: str = ""
    volume_profile: str = ""
    indicators: Dict[str, Any] = field(default_factory=dict)
    timeframe_analyses: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "trend": self.trend.value,
            "trend_strength": self.trend_strength,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
            "market_structure": self.market_structure,
            "momentum": self.momentum,
            "volume_profile": self.volume_profile,
            "indicators": self.indicators,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


@dataclass
class FundamentalAnalysis:
    symbol: str
    valuation: str = ""
    growth_quality: str = ""
    financial_health: str = ""
    earnings_quality: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 0.0
    data_label: DataLabel = DataLabel.UNAVAILABLE
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "valuation": self.valuation,
            "growth_quality": self.growth_quality,
            "financial_health": self.financial_health,
            "earnings_quality": self.earnings_quality,
            "details": self.details,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "data_label": self.data_label.value,
        }


@dataclass
class NewsAnalysis:
    symbol: str
    sentiment: str = "NEUTRAL"
    sentiment_score: float = 0.0
    confidence: float = 0.0
    headline_count: int = 0
    top_headlines: List[str] = field(default_factory=list)
    event_flags: List[str] = field(default_factory=list)
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "headline_count": self.headline_count,
            "top_headlines": self.top_headlines,
            "event_flags": self.event_flags,
            "reasoning": self.reasoning,
        }


@dataclass
class OptionsAnalysis:
    symbol: str
    pcr_oi: float = 0.0
    pcr_volume: float = 0.0
    max_pain: float = 0.0
    iv_percentile: float = 0.0
    iv_rank: float = 0.0
    iv_regime: str = ""
    oi_concentration_call: List[float] = field(default_factory=list)
    oi_concentration_put: List[float] = field(default_factory=list)
    support_from_options: float = 0.0
    resistance_from_options: float = 0.0
    strategy_suggestions: List[OptionStrategy] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "pcr_oi": self.pcr_oi,
            "pcr_volume": self.pcr_volume,
            "max_pain": self.max_pain,
            "iv_regime": self.iv_regime,
            "iv_percentile": self.iv_percentile,
            "support_from_options": self.support_from_options,
            "resistance_from_options": self.resistance_from_options,
            "reasoning": self.reasoning,
        }


@dataclass
class RiskAssessment:
    symbol: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 0.5
    max_position_size: float = 0.0
    stop_distance: float = 0.0
    risk_per_trade: float = 0.0
    portfolio_impact: str = ""
    concentration_risk: str = ""
    correlation_risk: str = ""
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "max_position_size": self.max_position_size,
            "stop_distance": self.stop_distance,
            "risk_per_trade": self.risk_per_trade,
            "portfolio_impact": self.portfolio_impact,
            "concentration_risk": self.concentration_risk,
            "reasoning": self.reasoning,
        }


@dataclass
class TradeThesis:
    thesis_id: str
    symbol: str
    direction: str
    entry_rationale: str
    invalidation: str
    date_created: datetime = field(default_factory=datetime.utcnow)
    date_resolved: Optional[datetime] = None
    outcome: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl_percent: float = 0.0
    status: str = "ACTIVE"
    post_trade_review: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_rationale": self.entry_rationale,
            "invalidation": self.invalidation,
            "date_created": self.date_created.isoformat(),
            "date_resolved": self.date_resolved.isoformat() if self.date_resolved else None,
            "outcome": self.outcome,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_percent": self.pnl_percent,
            "status": self.status,
            "post_trade_review": self.post_trade_review,
            "tags": self.tags,
        }


@dataclass
class PaperTrade:
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    quantity: float
    entry_date: datetime = field(default_factory=datetime.utcnow)
    exit_price: float = 0.0
    exit_date: Optional[datetime] = None
    stop_loss: float = 0.0
    target: float = 0.0
    status: str = "OPEN"
    pnl: float = 0.0
    pnl_percent: float = 0.0
    notes: str = ""
    thesis_id: str = ""

    def close(self, exit_price: float) -> None:
        self.exit_price = exit_price
        self.exit_date = datetime.utcnow()
        self.status = "CLOSED"
        if self.direction == "LONG":
            self.pnl = (exit_price - self.entry_price) * self.quantity
            self.pnl_percent = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity
            self.pnl_percent = ((self.entry_price - exit_price) / self.entry_price) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "status": self.status,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
        }


@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    total_return: float = 0.0
    trades: List[PaperTrade] = field(default_factory=list)

    def calculate_stats(self) -> None:
        if not self.trades:
            return
        self.total_trades = len(self.trades)
        self.winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        self.losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0
        wins = [t.pnl_percent for t in self.trades if t.pnl > 0]
        losses = [t.pnl_percent for t in self.trades if t.pnl < 0]
        self.avg_win = sum(wins) / len(wins) if wins else 0.0
        self.avg_loss = sum(losses) / len(losses) if losses else 0.0
        if self.avg_loss != 0:
            self.expectancy = (self.win_rate * self.avg_win) + ((1 - self.win_rate) * self.avg_loss)
        self.total_return = sum(t.pnl_percent for t in self.trades)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "expectancy": self.expectancy,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
        }


# ==========================================================
# Daily Market Close Report
# ==========================================================

@dataclass
class DailyMarketCloseReport:
    date: datetime
    market_regime: str = ""
    nifty_snapshot: Optional[MarketSnapshot] = None
    banknifty_snapshot: Optional[MarketSnapshot] = None
    biggest_gainers: List[MarketMover] = field(default_factory=list)
    biggest_losers: List[MarketMover] = field(default_factory=list)
    unusual_movers: List[MarketMover] = field(default_factory=list)
    portfolio_changes: List[Dict[str, Any]] = field(default_factory=list)
    top_opportunities: List[TradeRecommendation] = field(default_factory=list)
    top_risks: List[RiskAssessment] = field(default_factory=list)
    nifty_outlook: str = ""
    options_setup_candidates: List[str] = field(default_factory=list)
    tomorrow_scenarios: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "market_regime": self.market_regime,
            "biggest_gainers": [{"symbol": m.symbol, "change": m.change_percent} for m in self.biggest_gainers[:5]],
            "biggest_losers": [{"symbol": m.symbol, "change": m.change_percent} for m in self.biggest_losers[:5]],
            "unusual_movers": [{"symbol": m.symbol, "reason": m.reason} for m in self.unusual_movers[:5]],
            "top_opportunities": [r.to_dict() for r in self.top_opportunities[:5]],
            "nifty_outlook": self.nifty_outlook,
            "tomorrow_scenarios": self.tomorrow_scenarios,
        }
