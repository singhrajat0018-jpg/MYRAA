"""Trading Neural Specialist — wraps Trading Intelligence Engine with neural pattern recognition.

Flow:
TradingIntelligenceEngine → structured market data → Trading Neural Specialist
→ pattern scores, regime detection, setup quality → result → Fusion → Super-Brain

DO NOT create orders or execute trades. Advisory only.
"""

from __future__ import annotations

import math
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from ..model_contract import (
    ModelSpec, ModelResult, InferenceRequest, ModelDomain, ModelModality,
    LatencyClass, ModelDeployment, ModelStatus,
)


@dataclass
class TradingAnalysis:
    """Structured trading neural output — all scores in [0.0, 1.0] unless noted."""
    pattern_score: float = 0.0
    trend_score: float = 0.0
    regime: str = "unknown"
    setup_quality: float = 0.0
    probability_estimate: float = 0.0
    risk_signal: float = 0.5
    uncertainty: float = 0.5
    confidence: float = 0.5
    patterns_detected: list[str] = field(default_factory=list)
    regime_detail: dict[str, Any] = field(default_factory=dict)
    feature_vector: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TradingSpecialist:
    """Neural specialist wrapping existing Trading Intelligence Engine.

    Singleton-compatible and thread-safe. Produces pattern scores, trend
    analysis, regime detection, and setup quality assessments from structured
    OHLCV + indicator data. Advisory only — never generates orders.
    """

    _instance: Optional[TradingSpecialist] = None
    _lock_class = threading.Lock()

    SPEC = ModelSpec(
        model_id="trading_specialist_v1",
        domain=ModelDomain.TRADING,
        version="1.0.0",
        modality=ModelModality.STRUCTURED,
        capabilities=[
            "pattern_recognition",
            "trend_analysis",
            "regime_detection",
            "setup_quality",
            "risk_signal",
        ],
        input_schema={
            "ohlcv": "list[OHLCV]",
            "indicators": "dict",
            "market_structure": "dict",
            "volatility": "float",
            "portfolio_context": "dict",
        },
        output_schema={
            "analysis": "TradingAnalysis",
            "confidence": "float",
            "uncertainty": "float",
        },
        latency_class=LatencyClass.FAST,
        deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 128},
        provider="local",
        description="Neural pattern recognition and regime detection for structured trading data. Advisory only.",
    )

    # ── candlestick pattern name constants ──────────────────────
    _PATTERN_DOJI = "doji"
    _PATTERN_HAMMER = "hammer"
    _PATTERN_ENGULFING_BULL = "bullish_engulfing"
    _PATTERN_ENGULFING_BEAR = "bearish_engulfing"
    _PATTERN_MORNING_STAR = "morning_star"
    _PATTERN_EVENING_STAR = "evening_star"
    _PATTERN_THREE_WHITE = "three_white_soldiers"
    _PATTERN_THREE_BLACK = "three_black_crows"
    _PATTERN_HANGING_MAN = "hanging_man"
    _PATTERN_SHOOTING_STAR = "shooting_star"
    _PATTERN_SPINNING_TOP = "spinning_top"

    # ── singleton support ───────────────────────────────────────

    def __new__(cls, *args: Any, **kwargs: Any) -> TradingSpecialist:
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, trading_engine: Any = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self._trading_engine = trading_engine
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0
        self._lock = threading.Lock()
        self._initialized = True

    # ── properties ──────────────────────────────────────────────

    @property
    def model_id(self) -> str:
        return self.SPEC.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    @property
    def health_score(self) -> float:
        return self._health_score

    # ── public API ──────────────────────────────────────────────

    def inference(self, request: InferenceRequest) -> ModelResult:
        """Run neural pattern analysis on structured trading data."""
        start = time.perf_counter()
        with self._lock:
            self._total_calls += 1

        try:
            ctx = request.context
            ohlcv = ctx.get("ohlcv", [])
            indicators = ctx.get("indicators", {})
            market_structure = ctx.get("market_structure", {})
            volatility_val = ctx.get("volatility", 0.0)
            portfolio_ctx = ctx.get("portfolio_context", {})

            analysis = self._analyze(
                ohlcv, indicators, market_structure, volatility_val, portfolio_ctx,
            )

            elapsed = (time.perf_counter() - start) * 1000
            self._update_health(True)

            return ModelResult(
                model_id=self.model_id,
                output=analysis,
                confidence=analysis.confidence,
                uncertainty=analysis.uncertainty,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="trading_specialist",
                warnings=analysis.warnings,
                version=self.SPEC.version,
                metadata={"patterns": analysis.patterns_detected, "regime": analysis.regime},
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            with self._lock:
                self._failures += 1
            self._update_health(False)
            return ModelResult(
                model_id=self.model_id,
                output=TradingAnalysis(confidence=0.0, uncertainty=1.0, warnings=[str(e)]),
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="trading_specialist_error",
                warnings=[str(e)],
                version=self.SPEC.version,
            )

    # ── core analysis ───────────────────────────────────────────

    def _analyze(
        self,
        ohlcv: list[Any],
        indicators: dict[str, Any],
        market_structure: dict[str, Any],
        volatility_val: float,
        portfolio_ctx: dict[str, Any],
    ) -> TradingAnalysis:
        warnings: list[str] = []
        if not ohlcv:
            return TradingAnalysis(
                confidence=0.0, uncertainty=1.0,
                warnings=["No OHLCV data provided"],
            )

        features = self._normalize_features(ohlcv, indicators, volatility_val)
        pattern_score, patterns = self._score_pattern(ohlcv)
        trend_score = self._score_trend(ohlcv, indicators)
        regime, regime_detail = self._assess_regime(ohlcv, indicators, volatility_val)
        setup_q = self._score_setup_quality(
            pattern_score, trend_score, regime, indicators, market_structure,
        )
        risk_signal = self._assess_risk(ohlcv, indicators, portfolio_ctx)
        probability = self._estimate_probability(
            pattern_score, trend_score, setup_q, regime,
        )

        confidence = self._compute_confidence(
            len(ohlcv), pattern_score, trend_score, indicators,
        )
        uncertainty = max(0.0, 1.0 - confidence)

        if len(ohlcv) < 20:
            warnings.append("Limited history — confidence reduced")
        if volatility_val > 40.0:
            warnings.append("High volatility regime — wider uncertainty")
        if not indicators:
            warnings.append("No indicators provided — pattern-only analysis")

        return TradingAnalysis(
            pattern_score=pattern_score,
            trend_score=trend_score,
            regime=regime,
            setup_quality=setup_q,
            probability_estimate=probability,
            risk_signal=risk_signal,
            uncertainty=uncertainty,
            confidence=confidence,
            patterns_detected=patterns,
            regime_detail=regime_detail,
            feature_vector=features,
            warnings=warnings,
        )

    # ── feature normalization ───────────────────────────────────

    def _normalize_features(
        self,
        ohlcv: list[Any],
        indicators: dict[str, Any],
        volatility_val: float,
    ) -> list[float]:
        """Process OHLCV + indicator inputs into a normalized feature vector [0,1].

        Features (20 dims):
          0  close_position   — close within bar range
          1  body_ratio       — |close-open| / (high-low)
          2  upper_shadow     — upper wick / bar range
          3  lower_shadow     — lower wick / bar range
          4  volume_norm      — latest volume / 20-bar avg
          5  price_change     — (close - open) / open, clamped to [-1,1]
          6  range_change     — (high-low) / prev (high-low), clamped
          7  sma20_position   — close relative to SMA20, clamped
          8  sma50_position   — close relative to SMA50, clamped
          9  rsi_norm         — RSI / 100
         10  macd_norm        — tanh(MACD histogram / price * 100)
         11  bb_position      — close position within Bollinger Bands
         12  atr_norm         — ATR / close (normalized volatility)
         13  stoch_k_norm     — Stoch K / 100
         14  williams_norm    — (Williams %R + 100) / 100
         15  trend_strength_n — tanh(trend_strength / 5)
         16  consecutive_up   — count of consecutive up bars / 10
         17  consecutive_down — count of consecutive down bars / 10
         18  high_break       — close relative to 10-bar high
         19  low_break        — close relative to 10-bar low
        """
        n = len(ohlcv)
        if n == 0:
            return [0.0] * 20

        last = ohlcv[-1]
        bar_range = max(last.high - last.low, 1e-9)
        body = abs(last.close - last.open)

        close_pos = (last.close - last.low) / bar_range
        body_ratio = min(body / bar_range, 1.0)
        upper_shadow = (last.high - max(last.close, last.open)) / bar_range
        lower_shadow = (min(last.close, last.open) - last.low) / bar_range

        # volume norm
        volumes = [b.volume for b in ohlcv if b.volume > 0]
        avg_vol = sum(volumes[-20:]) / min(len(volumes), 20) if volumes else 0
        vol_norm = min(last.volume / max(avg_vol, 1), 3.0) / 3.0 if avg_vol > 0 else 0.5

        price_change = (last.close - last.open) / last.open if last.open else 0.0
        price_change = max(-1.0, min(1.0, price_change))

        prev_range = (ohlcv[-2].high - ohlcv[-2].low) if n >= 2 else bar_range
        range_change = min(max((bar_range / max(prev_range, 1e-9)) - 1.0, -1.0), 1.0)

        # indicator-based features
        closes = [b.close for b in ohlcv]

        sma20 = indicators.get("sma_20")
        sma50 = indicators.get("sma_50")
        sma20_val = self._last_valid(sma20)
        sma50_val = self._last_valid(sma50)

        sma20_pos = self._clamp_ratio(last.close, sma20_val)
        sma50_pos = self._clamp_ratio(last.close, sma50_val)

        rsi_vals = indicators.get("rsi_14")
        rsi_val = self._last_valid(rsi_vals)
        rsi_norm = rsi_val / 100.0 if rsi_val is not None else 0.5

        macd_hist = indicators.get("macd_histogram")
        macd_val = self._last_valid(macd_hist)
        macd_norm = self._tanh(macd_val / max(last.close, 1e-9) * 100) if macd_val is not None else 0.0

        bb_upper = self._last_valid(indicators.get("bb_upper"))
        bb_lower = self._last_valid(indicators.get("bb_lower"))
        if bb_upper is not None and bb_lower is not None and bb_upper > bb_lower:
            bb_pos = (last.close - bb_lower) / (bb_upper - bb_lower)
            bb_pos = max(0.0, min(1.0, bb_pos))
        else:
            bb_pos = 0.5

        atr_vals = indicators.get("atr_14")
        atr_val = self._last_valid(atr_vals)
        atr_norm = (atr_val / last.close) if (atr_val is not None and last.close > 0) else 0.0
        atr_norm = min(atr_norm, 0.2) / 0.2  # cap at 20% of price

        stoch_k = indicators.get("stoch_k")
        stoch_val = self._last_valid(stoch_k)
        stoch_norm = stoch_val / 100.0 if stoch_val is not None else 0.5

        wr_vals = indicators.get("williams_r")
        wr_val = self._last_valid(wr_vals)
        williams_norm = ((wr_val + 100.0) / 100.0) if wr_val is not None else 0.5

        trend_str = indicators.get("trend_strength")
        trend_val = self._last_valid(trend_str) if isinstance(trend_str, list) else trend_str
        trend_norm = self._tanh(trend_val / 5.0) if trend_val is not None else 0.0

        # consecutive bars
        cons_up = 0
        cons_down = 0
        for bar in reversed(ohlcv):
            if bar.close > bar.open:
                cons_up += 1
            elif bar.close < bar.open:
                cons_down += 1
            else:
                break
        cons_up_n = min(cons_up / 10.0, 1.0)
        cons_down_n = min(cons_down / 10.0, 1.0)

        # 10-bar breakout position
        lookback = min(10, n)
        hi10 = max(b.high for b in ohlcv[-lookback:])
        lo10 = min(b.low for b in ohlcv[-lookback:])
        hi_range = max(hi10 - lo10, 1e-9)
        hi_break = (last.close - lo10) / hi_range
        lo_break = (hi10 - last.close) / hi_range

        return [
            self._clamp(close_pos),
            self._clamp(body_ratio),
            self._clamp(upper_shadow),
            self._clamp(lower_shadow),
            self._clamp(vol_norm),
            self._clamp(price_change * 0.5 + 0.5),
            self._clamp(range_change * 0.5 + 0.5),
            self._clamp(sma20_pos),
            self._clamp(sma50_pos),
            self._clamp(rsi_norm),
            self._clamp(macd_norm * 0.5 + 0.5),
            self._clamp(bb_pos),
            self._clamp(atr_norm),
            self._clamp(stoch_norm),
            self._clamp(williams_norm),
            self._clamp(trend_norm * 0.5 + 0.5),
            self._clamp(cons_up_n),
            self._clamp(cons_down_n),
            self._clamp(hi_break),
            self._clamp(lo_break),
        ]

    # ── pattern scoring ─────────────────────────────────────────

    def _score_pattern(self, ohlcv: list[Any]) -> tuple[float, list[str]]:
        """Evaluate candlestick and price patterns.

        Returns (score in [0,1], list of detected pattern names).
        """
        n = len(ohlcv)
        if n < 2:
            return 0.0, []

        detected: list[str] = []
        scores: list[float] = []
        weights: list[float] = []

        last = ohlcv[-1]
        prev = ohlcv[-2]

        # ── single-bar patterns ─────────────────────────────────
        bar_range = max(last.high - last.low, 1e-9)
        body = abs(last.close - last.open)
        upper_wick = last.high - max(last.close, last.open)
        lower_wick = min(last.close, last.open) - last.low
        body_ratio = body / bar_range
        upper_ratio = upper_wick / bar_range
        lower_ratio = lower_wick / bar_range
        bullish = last.close > last.open

        # Doji — tiny body relative to range
        if body_ratio < 0.1:
            detected.append(self._PATTERN_DOJI)
            scores.append(0.6)
            weights.append(1.0)

        # Hammer — small body, long lower wick, short upper wick (bullish reversal)
        if body_ratio < 0.35 and lower_ratio > 0.55 and upper_ratio < 0.15:
            detected.append(self._PATTERN_HAMMER)
            scores.append(0.7)
            weights.append(1.2)

        # Hanging Man — same shape as hammer but after uptrend
        if body_ratio < 0.35 and lower_ratio > 0.55 and upper_ratio < 0.15:
            if n >= 5:
                recent_close = [b.close for b in ohlcv[-5:]]
                if all(recent_close[i] <= recent_close[i + 1] for i in range(len(recent_close) - 1)):
                    detected.append(self._PATTERN_HANGING_MAN)
                    scores.append(0.65)
                    weights.append(1.0)

        # Shooting Star — small body, long upper wick, short lower wick (bearish reversal)
        if body_ratio < 0.35 and upper_ratio > 0.55 and lower_ratio < 0.15:
            detected.append(self._PATTERN_SHOOTING_STAR)
            scores.append(0.7)
            weights.append(1.2)

        # Spinning Top — small body, moderate wicks
        if body_ratio < 0.25 and 0.2 < upper_ratio < 0.5 and 0.2 < lower_ratio < 0.5:
            detected.append(self._PATTERN_SPINNING_TOP)
            scores.append(0.4)
            weights.append(0.6)

        # ── two-bar patterns ────────────────────────────────────
        prev_body = abs(prev.close - prev.open)

        # Bullish Engulfing
        if (not (prev.close > prev.open)) and bullish:
            if last.open <= prev.close and last.close >= prev.open and body > prev_body:
                detected.append(self._PATTERN_ENGULFING_BULL)
                scores.append(0.8)
                weights.append(1.5)

        # Bearish Engulfing
        if (prev.close > prev.open) and (not bullish):
            if last.open >= prev.close and last.close <= prev.open and body > prev_body:
                detected.append(self._PATTERN_ENGULFING_BEAR)
                scores.append(0.8)
                weights.append(1.5)

        # ── three-bar patterns ──────────────────────────────────
        if n >= 3:
            b1, b2, b3 = ohlcv[-3], ohlcv[-2], ohlcv[-1]
            b1_bull = b1.close > b1.open
            b2_bull = b2.close > b2.open
            b3_bull = b3.close > b3.open

            # Three White Soldiers
            if b1_bull and b2_bull and b3_bull:
                if b2.close > b1.close and b3.close > b2.close:
                    if b2.open > b1.open and b3.open > b2.open:
                        detected.append(self._PATTERN_THREE_WHITE)
                        scores.append(0.85)
                        weights.append(1.4)

            # Three Black Crows
            if (not b1_bull) and (not b2_bull) and (not b3_bull):
                if b2.close < b1.close and b3.close < b2.close:
                    if b2.open < b1.open and b3.open < b2.open:
                        detected.append(self._PATTERN_THREE_BLACK)
                        scores.append(0.85)
                        weights.append(1.4)

        # ── three-bar reversal patterns ─────────────────────────
        if n >= 3:
            b1, b2, b3 = ohlcv[-3], ohlcv[-2], ohlcv[-1]
            b1_body = abs(b1.close - b1.open)
            b2_body = abs(b2.close - b2.open)
            b3_body = abs(b3.close - b3.open)

            # Morning Star (bullish reversal): big down, small, big up
            b1_down = b1.close < b1.open
            b3_up = b3.close > b3.open
            if b1_down and b3_up:
                if b2_body < b1_body * 0.35 and b3_body > b1_body * 0.5:
                    if b3.close > (b1.open + b1.close) / 2:
                        detected.append(self._PATTERN_MORNING_STAR)
                        scores.append(0.85)
                        weights.append(1.5)

            # Evening Star (bearish reversal): big up, small, big down
            b1_up = b1.close > b1.open
            b3_down = b3.close < b3.open
            if b1_up and b3_down:
                if b2_body < b1_body * 0.35 and b3_body > b1_body * 0.5:
                    if b3.close < (b1.open + b1.close) / 2:
                        detected.append(self._PATTERN_EVENING_STAR)
                        scores.append(0.85)
                        weights.append(1.5)

        # ── combine pattern scores ──────────────────────────────
        if not scores:
            return 0.0, []

        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        combined = weighted_sum / total_weight if total_weight > 0 else 0.0

        # slight bonus for pattern confluence
        if len(scores) >= 2:
            combined = min(1.0, combined + 0.05 * (len(scores) - 1))

        return self._clamp(combined), detected

    # ── trend scoring ───────────────────────────────────────────

    def _score_trend(self, ohlcv: list[Any], indicators: dict[str, Any]) -> float:
        """Score trend strength and direction in [0,1].

        0 = strong bearish, 0.5 = neutral, 1 = strong bullish.
        """
        n = len(ohlcv)
        if n < 5:
            return 0.5

        closes = [b.close for b in ohlcv]

        # price momentum — 5-bar and 10-bar rate of change
        roc5 = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] else 0.0
        roc10 = (closes[-1] - closes[-min(10, n)]) / closes[-min(10, n)] if closes[-min(10, n)] else 0.0

        # moving average alignment
        sma20_val = self._last_valid(indicators.get("sma_20"))
        sma50_val = self._last_valid(indicators.get("sma_50"))
        ema9_val = self._last_valid(indicators.get("ema_9"))
        ema21_val = self._last_valid(indicators.get("ema_21"))

        ma_score = 0.5
        ma_parts = 0
        if sma20_val is not None:
            ma_score += 0.1 if closes[-1] > sma20_val else -0.1
            ma_parts += 1
        if sma50_val is not None:
            ma_score += 0.1 if closes[-1] > sma50_val else -0.1
            ma_parts += 1
        if ema9_val is not None and ema21_val is not None:
            ma_score += 0.1 if ema9_val > ema21_val else -0.1
            ma_parts += 1
        if ma_parts:
            ma_score = 0.5 + (ma_score - 0.5) * (ma_parts / 3)

        # MACD direction
        macd_hist = self._last_valid(indicators.get("macd_histogram"))
        macd_score = 0.5
        if macd_hist is not None:
            macd_score = 0.5 + self._tanh(macd_hist / 2.0) * 0.5

        # RSI directional bias
        rsi_val = self._last_valid(indicators.get("rsi_14"))
        rsi_score = 0.5
        if rsi_val is not None:
            rsi_score = rsi_val / 100.0

        # combine
        roc_combined = (roc5 * 0.6 + roc10 * 0.4)
        roc_norm = self._tanh(roc_combined * 20) * 0.5 + 0.5  # map to [0,1]

        trend = (
            roc_norm * 0.35
            + ma_score * 0.30
            + macd_score * 0.20
            + rsi_score * 0.15
        )

        return self._clamp(trend)

    # ── regime detection ────────────────────────────────────────

    def _assess_regime(
        self,
        ohlcv: list[Any],
        indicators: dict[str, Any],
        volatility_val: float,
    ) -> tuple[str, dict[str, Any]]:
        """Detect market regime: trending, ranging, or volatile.

        Returns (regime_name, detail_dict).
        """
        n = len(ohlcv)
        detail: dict[str, Any] = {}

        if n < 10:
            return "unknown", detail

        closes = [b.close for b in ohlcv]
        highs = [b.high for b in ohlcv]
        lows = [b.low for b in ohlcv]

        # ATR-based volatility
        atr_val = self._last_valid(indicators.get("atr_14"))
        atr_pct = (atr_val / closes[-1] * 100) if (atr_val and closes[-1]) else 0.0

        # trend_strength
        ts = indicators.get("trend_strength")
        trend_val = abs(self._last_valid(ts) if isinstance(ts, list) else ts or 0.0)

        # Bollinger Band width as volatility proxy
        bb_upper = self._last_valid(indicators.get("bb_upper"))
        bb_lower = self._last_valid(indicators.get("bb_lower"))
        bb_middle = self._last_valid(indicators.get("bb_middle"))
        bb_width = 0.0
        if bb_upper is not None and bb_lower is not None and bb_middle and bb_middle > 0:
            bb_width = (bb_upper - bb_lower) / bb_middle * 100

        # price range compression over recent bars
        recent = min(20, n)
        hi_recent = max(highs[-recent:])
        lo_recent = min(lows[-recent:])
        range_pct = ((hi_recent - lo_recent) / lo_recent * 100) if lo_recent else 0.0

        # directional efficiency: net move / total path
        net_move = abs(closes[-1] - closes[-recent])
        total_path = sum(abs(closes[i] - closes[i - 1]) for i in range(-recent + 1, 0))
        efficiency = net_move / max(total_path, 1e-9)

        detail = {
            "atr_pct": round(atr_pct, 3),
            "trend_strength": round(trend_val, 3),
            "bb_width": round(bb_width, 3),
            "range_pct": round(range_pct, 3),
            "efficiency": round(efficiency, 3),
            "volatility_annualized": round(volatility_val, 3),
        }

        # regime decision tree
        vol_score = 0.0
        if volatility_val > 35 or atr_pct > 3.0 or bb_width > 12:
            vol_score = 1.0
        elif volatility_val > 20 or atr_pct > 1.5 or bb_width > 6:
            vol_score = 0.6

        trend_score = 0.0
        if trend_val > 3.0 and efficiency > 0.25:
            trend_score = 1.0
        elif trend_val > 1.5 and efficiency > 0.15:
            trend_score = 0.6

        range_score = 0.0
        if efficiency < 0.1 and range_pct < 5.0 and trend_val < 1.5:
            range_score = 1.0
        elif efficiency < 0.2 and trend_val < 2.0:
            range_score = 0.5

        detail["trend_score"] = round(trend_score, 3)
        detail["vol_score"] = round(vol_score, 3)
        detail["range_score"] = round(range_score, 3)

        # classify
        if vol_score >= 0.8 and trend_score < 0.5:
            return "volatile", detail
        elif trend_score >= 0.6 and range_score < 0.4:
            if closes[-1] > closes[-recent]:
                return "trending_up", detail
            else:
                return "trending_down", detail
        elif range_score >= 0.6 and vol_score < 0.5:
            return "ranging", detail
        else:
            # mixed — use dominant signal
            scores = {"trending": trend_score, "volatile": vol_score, "ranging": range_score}
            best = max(scores, key=scores.get)  # type: ignore[arg-type]
            if scores[best] > 0.3:
                return best, detail
            return "mixed", detail

    # ── setup quality ───────────────────────────────────────────

    def _score_setup_quality(
        self,
        pattern_score: float,
        trend_score: float,
        regime: str,
        indicators: dict[str, Any],
        market_structure: dict[str, Any],
    ) -> float:
        """Rate the overall setup quality in [0,1].

        Higher scores indicate cleaner, higher-probability setups.
        """
        score = 0.0
        parts = 0

        # pattern confluence
        score += pattern_score * 0.25
        parts += 1

        # trend clarity (distance from 0.5 = clarity)
        trend_clarity = abs(trend_score - 0.5) * 2  # 0..1
        score += trend_clarity * 0.25
        parts += 1

        # regime favorability — trending is best for setups
        regime_map = {
            "trending_up": 0.9,
            "trending_down": 0.9,
            "ranging": 0.4,
            "volatile": 0.3,
            "mixed": 0.5,
            "unknown": 0.3,
        }
        score += regime_map.get(regime, 0.3) * 0.20
        parts += 1

        # support/resistance proximity
        sr_levels = market_structure.get("support_levels", [])
        res_levels = market_structure.get("resistance_levels", [])
        if sr_levels or res_levels:
            sr_score = 0.6 if sr_levels and res_levels else 0.4
            score += sr_score * 0.15
            parts += 1

        # RSI zone bonus — oversold/overbought = potential setup
        rsi_val = self._last_valid(indicators.get("rsi_14"))
        if rsi_val is not None:
            if rsi_val < 30 or rsi_val > 70:
                score += 0.7 * 0.15
            elif rsi_val < 40 or rsi_val > 60:
                score += 0.5 * 0.15
            else:
                score += 0.3 * 0.15
            parts += 1

        return self._clamp(score) if parts > 0 else 0.0

    # ── risk signal ─────────────────────────────────────────────

    def _assess_risk(
        self,
        ohlcv: list[Any],
        indicators: dict[str, Any],
        portfolio_ctx: dict[str, Any],
    ) -> float:
        """Compute risk signal in [0,1].

        Higher values = higher risk.
        """
        n = len(ohlcv)
        if n < 5:
            return 0.7  # unknown = elevated risk

        closes = [b.close for b in ohlcv]
        risk = 0.0

        # volatility component
        vol = indicators.get("volatility", 0)
        vol_risk = min(vol / 50.0, 1.0)  # 50% annualized vol = max risk
        risk += vol_risk * 0.30

        # ATR as percentage of price
        atr_val = self._last_valid(indicators.get("atr_14"))
        atr_pct = (atr_val / closes[-1]) if (atr_val and closes[-1]) else 0.0
        atr_risk = min(atr_pct * 20, 1.0)  # 5% ATR/price = max
        risk += atr_risk * 0.20

        # drawdown from recent high
        recent_high = max(b.high for b in ohlcv[-min(20, n):])
        drawdown = (recent_high - closes[-1]) / recent_high if recent_high else 0.0
        dd_risk = min(drawdown * 5, 1.0)  # 20% drawdown = max
        risk += dd_risk * 0.20

        # RSI extreme = risk
        rsi_val = self._last_valid(indicators.get("rsi_14"))
        if rsi_val is not None:
            if rsi_val > 80 or rsi_val < 20:
                risk += 0.15
            elif rsi_val > 70 or rsi_val < 30:
                risk += 0.08

        # portfolio concentration
        existing = portfolio_ctx.get("existing_exposure_pct", 0.0)
        if existing > 0:
            concentration_risk = min(existing / 100.0, 1.0)
            risk += concentration_risk * 0.15

        return self._clamp(risk)

    # ── probability estimate ────────────────────────────────────

    def _estimate_probability(
        self,
        pattern_score: float,
        trend_score: float,
        setup_quality: float,
        regime: str,
    ) -> float:
        """Estimate probability of a favorable move in [0,1].

        Purely heuristic — advisory only, not a prediction.
        """
        # base probability from setup quality
        base = setup_quality * 0.5

        # pattern contribution
        base += pattern_score * 0.2

        # trend alignment bonus — trend in direction of pattern
        trend_aligned = (trend_score > 0.6 and pattern_score > 0.5) or \
                        (trend_score < 0.4 and pattern_score < 0.5)
        if trend_aligned:
            base += 0.15

        # regime modifier
        regime_mod = {
            "trending_up": 0.05,
            "trending_down": 0.05,
            "ranging": -0.05,
            "volatile": -0.10,
            "mixed": 0.0,
            "unknown": -0.05,
        }
        base += regime_mod.get(regime, 0.0)

        return self._clamp(base)

    # ── confidence computation ──────────────────────────────────

    def _compute_confidence(
        self,
        n_bars: int,
        pattern_score: float,
        trend_score: float,
        indicators: dict[str, Any],
    ) -> float:
        """Overall confidence in the analysis result."""
        conf = 0.4  # base

        # data sufficiency
        if n_bars >= 50:
            conf += 0.15
        elif n_bars >= 20:
            conf += 0.10
        elif n_bars >= 10:
            conf += 0.05

        # pattern clarity
        if pattern_score > 0.6:
            conf += 0.15
        elif pattern_score > 0.3:
            conf += 0.08

        # trend clarity
        trend_clarity = abs(trend_score - 0.5) * 2
        conf += trend_clarity * 0.10

        # indicator availability
        indicator_keys = ["rsi_14", "macd_histogram", "sma_20", "atr_14", "bb_upper"]
        available = sum(1 for k in indicator_keys if indicators.get(k) is not None)
        conf += (available / len(indicator_keys)) * 0.10

        return min(conf, 1.0)

    # ── health tracking ─────────────────────────────────────────

    def _update_health(self, success: bool) -> None:
        with self._lock:
            if not success:
                self._failures += 1
            total = max(self._total_calls, 1)
            self._health_score = max(0.0, 1.0 - (self._failures / total))
            if self._health_score < 0.3:
                self._status = ModelStatus.DEGRADED
            elif self._health_score < 0.6:
                self._status = ModelStatus.TESTING
            else:
                self._status = ModelStatus.ACTIVE

    def reset(self) -> None:
        """Reset health counters — useful for tests."""
        with self._lock:
            self._total_calls = 0
            self._failures = 0
            self._health_score = 1.0
            self._status = ModelStatus.ACTIVE

    # ── static helpers ──────────────────────────────────────────

    @staticmethod
    def _last_valid(lst: Any) -> Optional[float]:
        if not lst or not hasattr(lst, "__iter__"):
            return lst if isinstance(lst, (int, float)) else None
        for v in reversed(lst):
            if v is not None:
                return float(v)
        return None

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, v))

    @staticmethod
    def _clamp_ratio(price: float, ref: Optional[float]) -> float:
        if ref is None or ref <= 0 or price <= 0:
            return 0.5
        ratio = price / ref
        return max(0.0, min(1.0, ratio * 0.5))

    @staticmethod
    def _tanh(x: float) -> float:
        """Approximate tanh for normalization."""
        if x >= 20.0:
            return 1.0
        if x <= -20.0:
            return -1.0
        # use math.tanh from stdlib
        return math.tanh(x)

    @classmethod
    def new(cls, trading_engine: Any = None) -> TradingSpecialist:
        """Factory — returns singleton instance."""
        return cls(trading_engine=trading_engine)
