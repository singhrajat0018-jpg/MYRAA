"""
MYRAA Trading Intelligence — Multi-Timeframe Analysis (Part 3)

Analyzes charts at multiple timeframes: Monthly, Weekly, Daily, 4H, 1H, 15M, 5M.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import OHLCV, Timeframe, TrendDirection
from .indicators import compute_all_indicators
from .structure import MarketStructureEngine


class MultiTimeframeEngine:

    def __init__(self):
        self._structure = MarketStructureEngine()
        self._timeframes = [
            Timeframe.MONTHLY, Timeframe.WEEKLY, Timeframe.DAILY,
            Timeframe.FOUR_H, Timeframe.ONE_H, Timeframe.FIFTEEN_M, Timeframe.FIVE_M,
        ]

    def analyze(self, bars_by_timeframe: Dict[str, List[OHLCV]]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for tf in self._timeframes:
            key = tf.value
            bars = bars_by_timeframe.get(key, [])
            if not bars:
                results[key] = {"status": "no_data"}
                continue
            indicators = compute_all_indicators(bars)
            structure = self._structure.analyze(bars)
            results[key] = {
                "trend": structure.trend.value,
                "pattern": structure.pattern,
                "market_quality": structure.market_quality,
                "support": structure.key_support,
                "resistance": structure.key_resistance,
                "higher_highs": structure.higher_highs,
                "higher_lows": structure.higher_lows,
                "lower_highs": structure.lower_highs,
                "lower_lows": structure.lower_lows,
                "rsi": indicators.get("rsi_14", [None])[-1] if indicators.get("rsi_14") else None,
                "atr": indicators.get("atr_14", [None])[-1] if indicators.get("atr_14") else None,
                "trend_strength": indicators.get("trend_strength", 0),
                "bar_count": len(bars),
            }
        return results

    def get_alignment(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        trends = {}
        for tf, data in analysis.items():
            if isinstance(data, dict) and "trend" in data:
                trends[tf] = data["trend"]
        bullish = sum(1 for t in trends.values() if t == "BULLISH")
        bearish = sum(1 for t in trends.values() if t == "BEARISH")
        total = len(trends) or 1
        if bullish > bearish and bullish / total >= 0.6:
            alignment = "BULLISH_ALIGNED"
        elif bearish > bullish and bearish / total >= 0.6:
            alignment = "BEARISH_ALIGNED"
        else:
            alignment = "MIXED"
        return {
            "alignment": alignment,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "total_timeframes": total,
            "trends": trends,
        }
