"""
MYRAA Trading Intelligence -- Trade Plan Engine

Consumes technical, fundamental, news, options, and risk data to produce
a structured TradeRecommendation with actionable entry / stop / target logic.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    FundamentalAnalysis,
    MarketQuote,
    NewsAnalysis,
    NoTradePlan,
    OptionsAnalysis,
    RiskAssessment,
    RiskLevel,
    SignalType,
    TechnicalAnalysis,
    TradePlan,
    TradeRecommendation,
    TrendDirection,
)


_STRONG_BULL_RSI = 55
_STRONG_BEAR_RSI = 45
_OVERSOLD = 30
_OVERBOUGHT = 70
_DEFAULT_ATR_MULT_STOP = 1.5
_DEFAULT_ATR_MULT_TARGET = 3.0
_CONFIDENCE_CEILING = 0.92
_CONFIDENCE_FLOOR = 0.08


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _technicals_summary(ta: TechnicalAnalysis) -> Dict[str, Any]:
    ind = ta.indicators if ta.indicators else {}
    return {
        "rsi_14": ind.get("rsi_14"),
        "macd_histogram": ind.get("macd_histogram"),
        "atr_14": ind.get("atr_14"),
        "sma_20": ind.get("sma_20"),
        "sma_50": ind.get("sma_50"),
        "sma_200": ind.get("sma_200"),
        "ema_9": ind.get("ema_9"),
        "ema_21": ind.get("ema_21"),
        "bb_upper": ind.get("bb_upper"),
        "bb_lower": ind.get("bb_lower"),
        "vwap": ind.get("vwap"),
        "relative_volume": ind.get("relative_volume", 1.0),
        "volatility": ind.get("volatility", 0.0),
    }


def _score_technical_alignment(
    ta: TechnicalAnalysis, direction: str
) -> Tuple[float, List[str]]:
    evidence: List[str] = []
    score = 0.0
    ind = _technicals_summary(ta)
    rsi = ind.get("rsi_14")
    macd_hist = ind.get("macd_histogram")
    sma_20 = ind.get("sma_20")
    sma_50 = ind.get("sma_50")
    sma_200 = ind.get("sma_200")
    ema_9 = ind.get("ema_9")
    ema_21 = ind.get("ema_21")
    bb_upper = ind.get("bb_upper")
    bb_lower = ind.get("bb_lower")
    rel_vol = ind.get("relative_volume", 1.0)
    is_long = direction == "LONG"

    if ta.trend == TrendDirection.BULLISH and is_long:
        score += 0.25
        evidence.append("Bullish trend (strength {:.1f})".format(ta.trend_strength))
    elif ta.trend == TrendDirection.BEARISH and not is_long:
        score += 0.25
        evidence.append("Bearish trend (strength {:.1f})".format(ta.trend_strength))
    elif ta.trend == TrendDirection.NEUTRAL:
        score += 0.05
        evidence.append("Neutral trend -- no directional edge from structure")

    if rsi is not None:
        if is_long and rsi < _OVERSOLD:
            score += 0.15
            evidence.append("RSI oversold at {:.1f} -- mean-reversion long signal".format(rsi))
        elif not is_long and rsi > _OVERBOUGHT:
            score += 0.15
            evidence.append("RSI overbought at {:.1f} -- mean-reversion short signal".format(rsi))
        elif is_long and rsi > _STRONG_BULL_RSI:
            score += 0.08
            evidence.append("RSI bullish at {:.1f}".format(rsi))
        elif not is_long and rsi < _STRONG_BEAR_RSI:
            score += 0.08
            evidence.append("RSI bearish at {:.1f}".format(rsi))

    if macd_hist is not None:
        if (is_long and macd_hist > 0) or (not is_long and macd_hist < 0):
            score += 0.10
            hist_label = "positive" if macd_hist > 0 else "negative"
            evidence.append("MACD histogram {}".format(hist_label))
        elif (is_long and macd_hist < 0) or (not is_long and macd_hist > 0):
            score -= 0.05

    if sma_20 and sma_50 and sma_200:
        if is_long and sma_20 > sma_50 > sma_200:
            score += 0.10
            evidence.append("Bullish MA stack (20 > 50 > 200)")
        elif not is_long and sma_20 < sma_50 < sma_200:
            score += 0.10
            evidence.append("Bearish MA stack (20 < 50 < 200)")

    if ema_9 and ema_21:
        if is_long and ema_9 > ema_21:
            score += 0.05
            evidence.append("EMA 9 > EMA 21 -- short-term bullish")
        elif not is_long and ema_9 < ema_21:
            score += 0.05
            evidence.append("EMA 9 < EMA 21 -- short-term bearish")

    if bb_upper and bb_lower and bb_upper > bb_lower:
        bb_range = bb_upper - bb_lower
        bb_pos = 0.5
        if sma_20:
            bb_pos = (sma_20 - bb_lower) / bb_range
        if is_long and bb_pos < 0.2:
            score += 0.08
            evidence.append("Price near lower Bollinger Band -- potential bounce")
        elif not is_long and bb_pos > 0.8:
            score += 0.08
            evidence.append("Price near upper Bollinger Band -- potential fade")

    if rel_vol and rel_vol > 1.5:
        score += 0.07
        evidence.append("Strong volume ({:.1f}x average)".format(rel_vol))

    return _clamp(score, 0.0, 1.0), evidence


def _score_fundamentals(
    fa: Optional[FundamentalAnalysis], direction: str
) -> Tuple[float, List[str]]:
    if fa is None:
        return 0.5, ["No fundamental data available"]
    evidence: List[str] = []
    score = 0.5
    is_long = direction == "LONG"
    val = fa.valuation.lower() if fa.valuation else ""
    growth = fa.growth_quality.lower() if fa.growth_quality else ""
    health = fa.financial_health.lower() if fa.financial_health else ""
    if is_long:
        if "undervalued" in val or "cheap" in val:
            score += 0.15
            evidence.append("Valuation: {}".format(fa.valuation))
        elif "overvalued" in val or "expensive" in val:
            score -= 0.15
            evidence.append("Valuation concern: {}".format(fa.valuation))
        if "strong" in growth or "high" in growth:
            score += 0.10
            evidence.append("Growth quality: {}".format(fa.growth_quality))
        if "strong" in health or "healthy" in health:
            score += 0.10
            evidence.append("Financial health: {}".format(fa.financial_health))
        elif "weak" in health or "stressed" in health:
            score -= 0.10
            evidence.append("Financial health concern: {}".format(fa.financial_health))
    else:
        if "overvalued" in val:
            score += 0.15
            evidence.append("Valuation stretched: {}".format(fa.valuation))
        if "weak" in growth or "declining" in growth:
            score += 0.10
            evidence.append("Weak growth: {}".format(fa.growth_quality))
        if "weak" in health or "stressed" in health:
            score += 0.10
            evidence.append("Financial stress: {}".format(fa.financial_health))
    return _clamp(score, 0.0, 1.0), evidence


def _score_news(
    na: Optional[NewsAnalysis], direction: str
) -> Tuple[float, List[str]]:
    if na is None:
        return 0.5, ["No news data"]
    evidence: List[str] = []
    score = 0.5
    is_long = direction == "LONG"
    sentiment = na.sentiment.upper() if na.sentiment else "NEUTRAL"
    sent_score = na.sentiment_score
    if is_long and sentiment == "POSITIVE":
        score += 0.20
        evidence.append("Positive news sentiment (score {:.2f})".format(sent_score))
    elif is_long and sentiment == "NEGATIVE":
        score -= 0.20
        evidence.append("Negative news sentiment (score {:.2f})".format(sent_score))
    elif not is_long and sentiment == "NEGATIVE":
        score += 0.20
        evidence.append("Negative news supports short (score {:.2f})".format(sent_score))
    elif not is_long and sentiment == "POSITIVE":
        score -= 0.20
        evidence.append("Positive news contradicts short (score {:.2f})".format(sent_score))
    if na.headline_count >= 5:
        evidence.append("High news flow ({} headlines)".format(na.headline_count))
    if na.event_flags:
        evidence.append("Event flags: {}".format(", ".join(na.event_flags[:3])))
    return _clamp(score, 0.0, 1.0), evidence


def _score_options(
    oa: Optional[OptionsAnalysis], direction: str
) -> Tuple[float, List[str]]:
    if oa is None:
        return 0.5, ["No options data"]
    evidence: List[str] = []
    score = 0.5
    is_long = direction == "LONG"
    pcr_oi = oa.pcr_oi
    iv_regime = oa.iv_regime.lower() if oa.iv_regime else ""
    if pcr_oi > 1.2:
        if is_long:
            score += 0.10
            evidence.append("PCR OI {:.2f} -- put writing supports bullish view".format(pcr_oi))
        else:
            score -= 0.05
    elif pcr_oi < 0.7:
        if not is_long:
            score += 0.10
            evidence.append("PCR OI {:.2f} -- call writing supports bearish view".format(pcr_oi))
        else:
            score -= 0.05
    if "low" in iv_regime:
        evidence.append("Low IV regime -- options cheap")
        if is_long:
            score += 0.05
    elif "high" in iv_regime:
        evidence.append("High IV regime -- options expensive")
        if is_long:
            score -= 0.05
    if oa.support_from_options > 0 and is_long:
        evidence.append("Options support at {:.2f}".format(oa.support_from_options))
        score += 0.05
    if oa.resistance_from_options > 0 and not is_long:
        evidence.append("Options resistance at {:.2f}".format(oa.resistance_from_options))
        score += 0.05
    return _clamp(score, 0.0, 1.0), evidence


class TradePlanEngine:
    """Produces a TradeRecommendation from all available analysis dimensions."""

    def generate_recommendation(
        self,
        symbol: str,
        technical: Optional[TechnicalAnalysis],
        fundamental: Optional[FundamentalAnalysis] = None,
        news: Optional[NewsAnalysis] = None,
        options: Optional[OptionsAnalysis] = None,
        risk: Optional[RiskAssessment] = None,
        quote: Optional[MarketQuote] = None,
    ) -> TradeRecommendation:
        if technical is None:
            technical = TechnicalAnalysis(
                symbol=symbol, reasoning="No technical analysis provided",
            )

        long_score, long_ev = _score_technical_alignment(technical, "LONG")
        short_score, short_ev = _score_technical_alignment(technical, "SHORT")
        fl_score, fl_ev = _score_fundamentals(fundamental, "LONG")
        fs_score, fs_ev = _score_fundamentals(fundamental, "SHORT")
        nl_score, nl_ev = _score_news(news, "LONG")
        ns_score, ns_ev = _score_news(news, "SHORT")
        ol_score, ol_ev = _score_options(options, "LONG")
        os_score, os_ev = _score_options(options, "SHORT")

        risk_penalty = 0.0
        risk_ev: List[str] = []
        if risk:
            rl = risk.risk_level
            if rl == RiskLevel.VERY_HIGH:
                risk_penalty = 0.25
                risk_ev.append("VERY HIGH risk level -- significant position limits")
            elif rl == RiskLevel.HIGH:
                risk_penalty = 0.15
                risk_ev.append("HIGH risk level")
            elif rl == RiskLevel.LOW:
                risk_penalty = -0.05
                risk_ev.append("LOW risk level -- favourable")
            elif rl == RiskLevel.VERY_LOW:
                risk_penalty = -0.10
                risk_ev.append("VERY LOW risk level")

        W = {"tech": 0.40, "fund": 0.20, "news": 0.20, "opt": 0.20}
        long_c = _clamp(
            long_score * W["tech"] + fl_score * W["fund"]
            + nl_score * W["news"] + ol_score * W["opt"] - risk_penalty,
            0.0, 1.0,
        )
        short_c = _clamp(
            short_score * W["tech"] + fs_score * W["fund"]
            + ns_score * W["news"] + os_score * W["opt"] - risk_penalty,
            0.0, 1.0,
        )

        all_long = long_ev + fl_ev + nl_ev + ol_ev + risk_ev
        all_short = short_ev + fs_ev + ns_ev + os_ev + risk_ev

        if long_c >= 0.60 and long_c > short_c + 0.10:
            return self._build_buy(symbol, long_c, all_long, technical, quote, risk)
        if short_c >= 0.60 and short_c > long_c + 0.10:
            return self._build_sell(symbol, short_c, all_short, technical, quote, risk)

        best = max(long_c, short_c)
        if best >= 0.40:
            d = "LONG" if long_c >= short_c else "SHORT"
            ev = all_long if d == "LONG" else all_short
            return self._build_watch(symbol, best, ev, d, technical, quote, risk)

        if risk and risk.risk_level in (RiskLevel.VERY_HIGH, RiskLevel.HIGH) and best < 0.35:
            ev = risk_ev + (all_long if long_c >= short_c else all_short)
            return self._build_avoid(symbol, best, ev, risk)

        combined = all_long if long_c >= short_c else all_short
        return self._build_wait(symbol, best, combined, technical)

    # ---- builders ----

    def _build_buy(self, sym, conf, ev, ta, quote, risk):
        price = quote.current_price if quote else 0.0
        atr = ta.indicators.get("atr_14") if ta.indicators else None
        entry, stop, t1, t2, t3, rr = self._plan(price, atr, "LONG", ta, risk)
        plan = TradePlan(
            symbol=sym, direction="LONG",
            setup="Technical + multi-dimensional bullish confluence",
            entry_zone=entry, stop_loss=stop, target_1=t1, target_2=t2, target_3=t3,
            risk_reward=rr, confidence=round(conf, 3),
            catalyst=self._catalyst(ev), invalidation=self._invalidation('LONG', ta, stop),
            expected_horizon=self._horizon(ta), signal_type=SignalType.BUY,
            reasoning=self._reasoning('LONG', conf, ev), evidence=ev,
            risk_level=self._rl(risk),
        )
        return TradeRecommendation(
            symbol=sym, signal=SignalType.BUY, confidence=round(conf, 3),
            reasoning=plan.reasoning, evidence=ev, trade_plan=plan,
            risk_level=self._rl(risk),
        )

    def _build_sell(self, sym, conf, ev, ta, quote, risk):
        price = quote.current_price if quote else 0.0
        atr = ta.indicators.get("atr_14") if ta.indicators else None
        entry, stop, t1, t2, t3, rr = self._plan(price, atr, "SHORT", ta, risk)
        plan = TradePlan(
            symbol=sym, direction="SHORT",
            setup="Technical + multi-dimensional bearish confluence",
            entry_zone=entry, stop_loss=stop, target_1=t1, target_2=t2, target_3=t3,
            risk_reward=rr, confidence=round(conf, 3),
            catalyst=self._catalyst(ev), invalidation=self._invalidation('SHORT', ta, stop),
            expected_horizon=self._horizon(ta), signal_type=SignalType.SELL,
            reasoning=self._reasoning('SHORT', conf, ev), evidence=ev,
            risk_level=self._rl(risk),
        )
        return TradeRecommendation(
            symbol=sym, signal=SignalType.SELL, confidence=round(conf, 3),
            reasoning=plan.reasoning, evidence=ev, trade_plan=plan,
            risk_level=self._rl(risk),
        )

    def _build_watch(self, sym, conf, ev, d, ta, quote, risk):
        price = quote.current_price if quote else 0.0
        atr = ta.indicators.get("atr_14") if ta.indicators else None
        entry, stop, t1, t2, t3, rr = self._plan(price, atr, d, ta, risk)
        plan = TradePlan(
            symbol=sym, direction=d,
            setup="Developing setup -- awaiting confirmation",
            entry_zone=entry, stop_loss=stop, target_1=t1, target_2=t2, target_3=t3,
            risk_reward=rr, confidence=round(conf, 3), catalyst='',
            invalidation=self._invalidation(d, ta, stop), expected_horizon='',
            signal_type=SignalType.WATCH, reasoning=self._reasoning(d, conf, ev),
            evidence=ev, risk_level=self._rl(risk),
        )
        return TradeRecommendation(
            symbol=sym, signal=SignalType.WATCH, confidence=round(conf, 3),
            reasoning=plan.reasoning, evidence=ev, trade_plan=plan,
            risk_level=self._rl(risk),
        )

    def _build_wait(self, sym, conf, ev, ta):
        reason = "No actionable edge (composite {:.2f}). Insufficient confluence.".format(conf)
        nt = NoTradePlan(
            symbol=sym, reason=reason, signal_type=SignalType.WAIT,
            alternatives=self._alts(ta),
        )
        return TradeRecommendation(
            symbol=sym, signal=SignalType.WAIT, confidence=round(conf, 3),
            reasoning=reason, evidence=ev, no_trade=nt, risk_level=RiskLevel.MEDIUM,
        )

    def _build_avoid(self, sym, conf, ev, risk):
        reason = "AVOID -- risk {} (score {:.2f}). {}".format(
            risk.risk_level.value, risk.risk_score, risk.reasoning)
        nt = NoTradePlan(
            symbol=sym, reason=reason,
            signal_type=SignalType.AVOID if hasattr(SignalType, "AVOID") else SignalType.WAIT,
            alternatives=[],
        )
        return TradeRecommendation(
            symbol=sym, signal=SignalType.AVOID,
            confidence=round(_clamp(1.0 - conf, _CONFIDENCE_FLOOR, _CONFIDENCE_CEILING), 3),
            reasoning=reason,
            evidence=ev + ["Portfolio impact: {}".format(risk.portfolio_impact),
                           "Concentration risk: {}".format(risk.concentration_risk)],
            no_trade=nt, risk_level=risk.risk_level,
        )

    # ---- plan computation ----

    def _plan(self, price, atr, direction, ta, risk):
        if price <= 0:
            return "N/A", "N/A", "N/A", "N/A", "N/A", 0.0
        atr_val = atr if atr and atr > 0 else price * 0.02
        is_long = direction == "LONG"
        stop_dist = atr_val * _DEFAULT_ATR_MULT_STOP
        tgt_dist = atr_val * _DEFAULT_ATR_MULT_TARGET

        if is_long:
            ns = self._near(price, ta.support_levels, below=True)
            if ns and ns < price:
                stop_dist = max(price - ns, atr_val * 0.5)
            sp = price - stop_dist
            t1 = price + tgt_dist
            t2 = price + tgt_dist * 1.618
            t3 = price + tgt_dist * 2.618
            el = price - atr_val * 0.3
            eh = price + atr_val * 0.1
        else:
            nr = self._near(price, ta.resistance_levels, below=False)
            if nr and nr > price:
                stop_dist = max(nr - price, atr_val * 0.5)
            sp = price + stop_dist
            t1 = price - tgt_dist
            t2 = price - tgt_dist * 1.618
            t3 = price - tgt_dist * 2.618
            el = price - atr_val * 0.1
            eh = price + atr_val * 0.3

        rr = tgt_dist / stop_dist if stop_dist > 0 else 0.0
        if risk and risk.stop_distance > 0 and risk.stop_distance < stop_dist:
            sp = (price - risk.stop_distance) if is_long else (price + risk.stop_distance)
            rr = tgt_dist / risk.stop_distance if risk.stop_distance > 0 else rr

        f = lambda v: "{:.2f}".format(v)
        return "{} - {}".format(f(el), f(eh)), f(sp), f(t1), f(t2), f(t3), round(rr, 2)

    def _near(self, price, levels, below=True):
        if not levels:
            return None
        if below:
            c = [l for l in levels if l < price]
            return max(c) if c else None
        c = [l for l in levels if l > price]
        return min(c) if c else None

    def _invalidation(self, d, ta, stop_str):
        parts = ["Stop hit at {}".format(stop_str)]
        if ta.support_levels and d == 'LONG':
            parts.append("Break below key support {:.2f}".format(ta.support_levels[0]))
        elif ta.resistance_levels and d == 'SHORT':
            parts.append("Break above key resistance {:.2f}".format(ta.resistance_levels[0]))
        return ". ".join(parts)

    def _catalyst(self, ev):
        for e in ev:
            low = e.lower()
            if any(k in low for k in ["news", "event", "catalyst", "breakout", "breakdown"]):
                return e
        return ev[0] if ev else ""

    def _horizon(self, ta):
        vol = ta.indicators.get('volatility', 20) if ta.indicators else 20
        if vol and vol > 40:
            return "1-3 days (high volatility)"
        if vol and vol > 25:
            return "3-7 days (moderate volatility)"
        return "1-2 weeks (low volatility)"

    def _reasoning(self, d, conf, ev):
        top = ev[:5] if ev else ["No significant signals"]
        return "{} | confidence {:.0%} | {}".format(
            "LONG" if d == "LONG" else "SHORT", conf, "; ".join(top))

    def _rl(self, risk):
        if risk:
            return risk.risk_level
        return RiskLevel.MEDIUM

    def _alts(self, ta):
        alts = []
        if ta.trend == TrendDirection.BULLISH:
            alts.append("Wait for pullback to support for better entry")
        elif ta.trend == TrendDirection.BEARISH:
            alts.append("Wait for bounce to resistance for short entry")
        else:
            alts.append("Wait for clear trend to develop")
        if ta.support_levels:
            alts.append("Monitor support at {:.2f}".format(ta.support_levels[0]))
        return alts
