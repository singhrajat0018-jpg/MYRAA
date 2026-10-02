"""
MYRAA Trading Intelligence — Market Structure Engine (Part 5)

Swing structure, trend, support/resistance, breakout/breakdown patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..models import OHLCV, TrendDirection


@dataclass
class SwingPoint:
    index: int
    price: float
    timestamp: object
    swing_type: str


@dataclass
class StructureAnalysis:
    trend: TrendDirection = TrendDirection.UNKNOWN
    trend_description: str = ""
    swing_highs: List[SwingPoint] = field(default_factory=list)
    swing_lows: List[SwingPoint] = field(default_factory=list)
    higher_highs: bool = False
    higher_lows: bool = False
    lower_highs: bool = False
    lower_lows: bool = False
    key_support: List[float] = field(default_factory=list)
    key_resistance: List[float] = field(default_factory=list)
    pattern: str = ""
    is_breakout: bool = False
    is_breakdown: bool = False
    is_retest: bool = False
    is_consolidation: bool = False
    is_reversal: bool = False
    market_quality: str = ""
    reasoning: str = ""


class MarketStructureEngine:

    def __init__(self, swing_lookback: int = 3):
        self._swing_lookback = swing_lookback

    def analyze(self, bars: List[OHLCV]) -> StructureAnalysis:
        if len(bars) < 5:
            return StructureAnalysis(
                trend=TrendDirection.UNKNOWN,
                reasoning="Insufficient data for structure analysis",
            )
        swing_highs = self._find_swing_highs(bars)
        swing_lows = self._find_swing_lows(bars)
        structure = StructureAnalysis(swing_highs=swing_highs, swing_lows=swing_lows)
        self._analyze_trend(structure)
        self._find_support_resistance(structure, bars)
        self._detect_patterns(structure, bars)
        self._classify_market_quality(structure)
        return structure

    def _find_swing_highs(self, bars: List[OHLCV]) -> List[SwingPoint]:
        highs: List[SwingPoint] = []
        n = self._swing_lookback
        for i in range(n, len(bars) - n):
            is_high = True
            for j in range(1, n + 1):
                if bars[i].high <= bars[i - j].high or bars[i].high <= bars[i + j].high:
                    is_high = False
                    break
            if is_high:
                highs.append(SwingPoint(index=i, price=bars[i].high, timestamp=bars[i].timestamp, swing_type="HIGH"))
        return highs

    def _find_swing_lows(self, bars: List[OHLCV]) -> List[SwingPoint]:
        lows: List[SwingPoint] = []
        n = self._swing_lookback
        for i in range(n, len(bars) - n):
            is_low = True
            for j in range(1, n + 1):
                if bars[i].low >= bars[i - j].low or bars[i].low >= bars[i + j].low:
                    is_low = False
                    break
            if is_low:
                lows.append(SwingPoint(index=i, price=bars[i].low, timestamp=bars[i].timestamp, swing_type="LOW"))
        return lows

    def _analyze_trend(self, structure: StructureAnalysis) -> None:
        highs = structure.swing_highs
        lows = structure.swing_lows
        if len(highs) >= 2:
            structure.higher_highs = highs[-1].price > highs[-2].price
            structure.lower_highs = highs[-1].price < highs[-2].price
        if len(lows) >= 2:
            structure.higher_lows = lows[-1].price > lows[-2].price
            structure.lower_lows = lows[-1].price < lows[-2].price
        if structure.higher_highs and structure.lower_lows:
            structure.trend = TrendDirection.BULLISH
            structure.trend_description = "Uptrend: Higher Highs / Higher Lows"
        elif structure.lower_highs and structure.lower_lows:
            structure.trend = TrendDirection.BEARISH
            structure.trend_description = "Downtrend: Lower Highs / Lower Lows"
        else:
            structure.trend = TrendDirection.NEUTRAL
            structure.trend_description = "Range-bound or transitioning"

    def _find_support_resistance(self, structure: StructureAnalysis, bars: List[OHLCV]) -> None:
        current_price = bars[-1].close if bars else 0.0
        all_highs = sorted(set(sp.price for sp in structure.swing_highs), reverse=True)
        all_lows = sorted(set(sp.price for sp in structure.swing_lows))
        structure.key_resistance = [h for h in all_highs if h > current_price][:3]
        structure.key_support = [l for l in all_lows if l < current_price][:3]
        if not structure.key_resistance and all_highs:
            structure.key_resistance = [max(all_highs)]
        if not structure.key_support and all_lows:
            structure.key_support = [min(all_lows)]

    def _detect_patterns(self, structure: StructureAnalysis, bars: List[OHLCV]) -> None:
        if len(bars) < 10:
            return
        recent_closes = [b.close for b in bars[-10:]]
        price_range = max(recent_closes) - min(recent_closes)
        avg_price = sum(recent_closes) / len(recent_closes)
        if avg_price > 0 and price_range / avg_price < 0.02:
            structure.is_consolidation = True
            structure.pattern = "CONSOLIDATION"
        if len(bars) >= 3:
            last, prev, prev2 = bars[-1].close, bars[-2].close, bars[-3].close
            if last > prev > prev2 and structure.key_resistance and last > structure.key_resistance[0]:
                structure.is_breakout = True
                structure.pattern = "BREAKOUT"
            if last < prev < prev2 and structure.key_support and last < structure.key_support[0]:
                structure.is_breakdown = True
                structure.pattern = "BREAKDOWN"

    def _classify_market_quality(self, structure: StructureAnalysis) -> None:
        if structure.is_breakout and structure.trend == TrendDirection.BULLISH:
            structure.market_quality = "HIGH_QUALITY_BULLISH_BREAKOUT"
        elif structure.is_breakdown and structure.trend == TrendDirection.BEARISH:
            structure.market_quality = "HIGH_QUALITY_BEARISH_BREAKDOWN"
        elif structure.is_consolidation:
            structure.market_quality = "LOW_QUALITY_RANGE_BOUND"
        elif structure.trend in (TrendDirection.BULLISH, TrendDirection.BEARISH):
            structure.market_quality = "TRENDING"
        else:
            structure.market_quality = "UNCLEAR"
