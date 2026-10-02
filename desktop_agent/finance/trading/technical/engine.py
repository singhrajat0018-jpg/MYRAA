"""
MYRAA Trading Intelligence — Technical Analysis Engine (Part 3-4)

Combines indicators, structure, and multi-timeframe into a cohesive analysis.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import OHLCV, TechnicalAnalysis, TrendDirection
from .indicators import compute_all_indicators
from .structure import MarketStructureEngine
from .multi_timeframe import MultiTimeframeEngine


class TechnicalEngine:

    def __init__(self):
        self._structure = MarketStructureEngine()
        self._multi_tf = MultiTimeframeEngine()

    def analyze(self, bars: List[OHLCV], bars_by_tf: Dict[str, List[OHLCV]] | None = None) -> TechnicalAnalysis:
        if not bars:
            return TechnicalAnalysis(symbol="", reasoning="No data available")

        symbol = ""
        indicators = compute_all_indicators(bars)
        structure = self._structure.analyze(bars)
        tf_analysis = self._multi_tf.analyze(bars_by_tf) if bars_by_tf else {}
        alignment = self._multi_tf.get_alignment(tf_analysis) if tf_analysis else {}

        trend = structure.trend
        trend_strength_val = indicators.get("trend_strength", 0)
        rsi_val = self._last_valid(indicators.get("rsi_14"))
        macd_hist = indicators.get("macd_histogram", [])
        macd_val = self._last_valid(macd_hist)
        atr_val = self._last_valid(indicators.get("atr_14"))
        bb_upper = self._last_valid(indicators.get("bb_upper"))
        bb_lower = self._last_valid(indicators.get("bb_lower"))
        rel_vol = indicators.get("relative_volume", 1.0)

        momentum_parts = []
        if rsi_val is not None:
            if rsi_val < 30:
                momentum_parts.append(f"RSI oversold ({rsi_val:.1f})")
            elif rsi_val > 70:
                momentum_parts.append(f"RSI overbought ({rsi_val:.1f})")
            else:
                momentum_parts.append(f"RSI neutral ({rsi_val:.1f})")
        if macd_val is not None:
            if macd_val > 0:
                momentum_parts.append("MACD bullish")
            else:
                momentum_parts.append("MACD bearish")

        volume_parts = []
        if rel_vol > 2.0:
            volume_parts.append(f"Very high volume ({rel_vol:.1f}x avg)")
        elif rel_vol > 1.5:
            volume_parts.append(f"Above average volume ({rel_vol:.1f}x)")
        elif rel_vol < 0.5:
            volume_parts.append(f"Low volume ({rel_vol:.1f}x)")

        if tf_analysis and alignment:
            vol_label = alignment.get("alignment", "MIXED")
            volume_parts.append(f"Multi-TF alignment: {vol_label}")

        reasoning_parts = [structure.trend_description] if structure.trend_description else []
        reasoning_parts.extend(momentum_parts)
        reasoning_parts.extend(volume_parts)
        if structure.pattern:
            reasoning_parts.append(f"Pattern: {structure.pattern}")

        indicators_summary = {
            "rsi_14": rsi_val,
            "rsi_7": self._last_valid(indicators.get("rsi_7")),
            "macd_line": self._last_valid(indicators.get("macd_line")),
            "macd_signal": self._last_valid(indicators.get("macd_signal")),
            "macd_histogram": macd_val,
            "atr_14": atr_val,
            "sma_20": self._last_valid(indicators.get("sma_20")),
            "sma_50": self._last_valid(indicators.get("sma_50")),
            "sma_200": self._last_valid(indicators.get("sma_200")),
            "ema_9": self._last_valid(indicators.get("ema_9")),
            "ema_21": self._last_valid(indicators.get("ema_21")),
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_middle": self._last_valid(indicators.get("bb_middle")),
            "vwap": self._last_valid(indicators.get("vwap")),
            "stoch_k": self._last_valid(indicators.get("stoch_k")),
            "stoch_d": self._last_valid(indicators.get("stoch_d")),
            "williams_r": self._last_valid(indicators.get("williams_r")),
            "relative_volume": rel_vol,
            "trend_strength": trend_strength_val,
            "volatility": indicators.get("volatility", 0),
        }

        return TechnicalAnalysis(
            symbol=symbol,
            trend=trend,
            trend_strength=abs(trend_strength_val) if trend_strength_val else 0.0,
            support_levels=structure.key_support,
            resistance_levels=structure.key_resistance,
            market_structure=structure.pattern or structure.market_quality,
            momentum=" ".join(momentum_parts) if momentum_parts else "Neutral",
            volume_profile=" ".join(volume_parts) if volume_parts else "Normal",
            indicators=indicators_summary,
            timeframe_analyses=tf_analysis,
            reasoning=" | ".join(reasoning_parts),
            confidence=self._compute_confidence(trend, rsi_val, macd_val, alignment),
        )

    def _last_valid(self, lst: list | None) -> float | None:
        if not lst:
            return None
        for v in reversed(lst):
            if v is not None:
                return float(v)
        return None

    def _compute_confidence(self, trend: TrendDirection, rsi, macd, alignment: dict) -> float:
        conf = 0.5
        if trend in (TrendDirection.BULLISH, TrendDirection.BEARISH):
            conf += 0.1
        if rsi is not None and (rsi < 30 or rsi > 70):
            conf += 0.1
        if macd is not None:
            conf += 0.05
        if alignment:
            aligned = alignment.get("alignment", "")
            if aligned.endswith("ALIGNED"):
                conf += 0.15
        return min(conf, 1.0)
