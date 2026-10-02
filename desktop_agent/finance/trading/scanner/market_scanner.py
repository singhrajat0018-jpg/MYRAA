"""
MYRAA Trading Intelligence — Market Scanner

Scans a universe of instruments, scores each by opportunity or risk,
and returns ranked lists for actionable awareness.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    MarketMover,
    MarketQuote,
    OHLCV,
    RiskLevel,
    TechnicalAnalysis,
    TrendDirection,
)


# ---------------------------------------------------------------------------
# Scoring weights (tunable)
# ---------------------------------------------------------------------------

_WEIGHTS: Dict[str, float] = {
    "change_magnitude": 0.20,
    "relative_volume": 0.25,
    "rsi_signal": 0.15,
    "trend_strength": 0.15,
    "structure_quality": 0.15,
    "liquidity_penalty": 0.10,
}

_RSI_OVERSOLD = 30
_RSI_OVERBOUGHT = 70
_EXTREME_CHANGE_PCT = 5.0
_HIGH_REL_VOLUME = 2.0
_LOW_REL_VOLUME = 0.5
_MIN_HISTORY_BARS = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_last(values: list, default: Any = None) -> Any:
    """Return the last non-None value in *values*, or *default*."""
    for v in reversed(values):
        if v is not None:
            return v
    return default


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Wilder-smoothed RSI over *closes*."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0.0, d) for d in deltas]
    losses = [max(0.0, -d) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_relative_volume(volumes: List[int], lookback: int = 20) -> float:
    """Current volume / average of the last *lookback* bars."""
    if not volumes or volumes[-1] == 0:
        return 1.0
    window = volumes[-lookback:] if len(volumes) >= lookback else volumes
    avg = sum(window) / len(window) if window else 0.0
    if avg == 0:
        return 1.0
    return volumes[-1] / avg


def _compute_trend_strength(closes: List[float], period: int = 14) -> float:
    """Signed trend strength: positive for bullish, negative for bearish."""
    if len(closes) < period:
        return 0.0
    recent = closes[-period:]
    if recent[0] == 0:
        return 0.0
    change_pct = (recent[-1] - recent[0]) / recent[0]
    up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
    consistency = up_days / (len(recent) - 1) if len(recent) > 1 else 0.5
    sign = 1.0 if change_pct > 0 else -1.0
    return sign * abs(change_pct) * consistency * 100


def _compute_volatility(closes: List[float], period: int = 20) -> float:
    """Annualized volatility (stdev of daily returns × √252)."""
    if len(closes) < period:
        return 0.0
    recent = closes[-period:]
    if len(recent) < 2:
        return 0.0
    returns = [
        (recent[i] - recent[i - 1]) / recent[i - 1]
        for i in range(1, len(recent))
        if recent[i - 1] != 0
    ]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252) * 100


def _compute_atr(bars: List[OHLCV], period: int = 14) -> Optional[float]:
    if len(bars) < period:
        return None
    trs: List[float] = [bars[0].high - bars[0].low]
    for i in range(1, len(bars)):
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        trs.append(tr)
    atr_val = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr_val = (atr_val * (period - 1) + trs[i]) / period
    return atr_val


def _structure_score(ta: TechnicalAnalysis) -> float:
    """0-1 score rewarding strong, clean structure."""
    if ta.trend == TrendDirection.UNKNOWN:
        return 0.0
    base = ta.trend_strength / 100.0  # normalised
    has_levels = bool(ta.support_levels or ta.resistance_levels)
    market_structure = ta.market_structure.upper() if ta.market_structure else ""
    if "BREAKOUT" in market_structure or "BREAKDOWN" in market_structure:
        base += 0.3
    if "TRENDING" in market_structure.upper() if ta.market_structure else False:
        base += 0.1
    if has_levels:
        base += 0.1
    return min(base, 1.0)


def _momentum_score(rsi: Optional[float]) -> float:
    """Score RSI signal 0-1. Peaks at extremes, lowest in the middle."""
    if rsi is None:
        return 0.5  # neutral unknown
    if rsi <= _RSI_OVERSOLD:
        # Oversold — opportunity for long reversal
        return 0.5 + 0.5 * ((_RSI_OVERSOLD - rsi) / _RSI_OVERSOLD)
    if rsi >= _RSI_OVERBOUGHT:
        # Overbought — opportunity for short / risk for long
        return 0.5 + 0.5 * ((rsi - _RSI_OVERBOUGHT) / (100 - _RSI_OVERBOUGHT))
    # Neutral zone — proportional distance from midline
    return 0.3 + 0.2 * abs(rsi - 50) / 20


def _risk_score_for_mover(
    change_pct: float,
    rel_vol: float,
    rsi: Optional[float],
    volatility_pct: float,
) -> float:
    """0-1 risk score. Higher = riskier."""
    risk = 0.0
    # Absolute change magnitude adds risk
    risk += min(abs(change_pct) / (_EXTREME_CHANGE_PCT * 2), 1.0) * 0.25
    # Extreme volume adds risk
    risk += min(rel_vol / 5.0, 1.0) * 0.25
    # RSI extremes add risk
    if rsi is not None:
        if rsi < 20 or rsi > 80:
            risk += 0.3
        elif rsi < 30 or rsi > 70:
            risk += 0.15
    # High volatility adds risk
    risk += min(volatility_pct / 60, 1.0) * 0.2
    return min(risk, 1.0)


def _liquidity_score(quote: MarketQuote) -> float:
    """Penalise low liquidity / wide spread. Returns 0-1 (1 = good)."""
    spread_pct = quote.spread_percent
    if spread_pct <= 0.05:
        return 1.0
    if spread_pct >= 2.0:
        return 0.0
    return 1.0 - (spread_pct / 2.0)


# ---------------------------------------------------------------------------
# MarketScanner
# ---------------------------------------------------------------------------

class MarketScanner:
    """Ranks instruments by composite opportunity / risk score."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self._weights = weights or dict(_WEIGHTS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(
        self,
        quotes: Dict[str, MarketQuote],
        bars_map: Dict[str, List[OHLCV]],
        technicals: Optional[Dict[str, TechnicalAnalysis]] = None,
    ) -> Dict[str, List[MarketMover]]:
        """
        Scan all *quotes*, using *bars_map* for history-based indicators.

        Returns
        -------
        dict with keys:
            top_opportunities – best scored bullish / reversal setups
            top_risks         – instruments with the highest risk scores
            watchlist         – moderate opportunity, worth monitoring
            avoid             – worst risk / no-trade situations
        """
        scores: Dict[str, Dict[str, float]] = {}
        for symbol, quote in quotes.items():
            bars = bars_map.get(symbol, [])
            ta = technicals.get(symbol) if technicals else None
            scores[symbol] = self._score_instrument(quote, bars, ta)

        opportunity = sorted(
            scores.items(),
            key=lambda kv: kv[1]["opportunity"],
            reverse=True,
        )
        risk_sorted = sorted(
            scores.items(),
            key=lambda kv: kv[1]["risk"],
            reverse=True,
        )

        top_opps = self._build_movers(opportunity[:10], quotes, scores, "opportunity")
        top_risks = self._build_movers(risk_sorted[:10], quotes, scores, "risk")

        # watchlist: opportunity rank 10-20 with score > 0.3
        watchlist = self._build_movers(
            [item for item in opportunity[10:25] if item[1]["opportunity"] > 0.30][:10],
            quotes,
            scores,
            "watchlist",
        )
        # avoid: risk score > 0.6 and opportunity < 0.25
        avoid = self._build_movers(
            [
                item
                for item in risk_sorted
                if item[1]["risk"] > 0.60 and item[1]["opportunity"] < 0.25
            ][:10],
            quotes,
            scores,
            "avoid",
        )

        return {
            "top_opportunities": top_opps,
            "top_risks": top_risks,
            "watchlist": watchlist,
            "avoid": avoid,
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_instrument(
        self,
        quote: MarketQuote,
        bars: List[OHLCV],
        ta: Optional[TechnicalAnalysis],
    ) -> Dict[str, float]:
        closes = [b.close for b in bars] if bars else []
        volumes = [b.volume for b in bars] if bars else []
        indicators: Dict[str, Any] = ta.indicators if ta and ta.indicators else {}

        # Pull from pre-computed TechnicalAnalysis if available, else compute
        rsi: Optional[float] = indicators.get("rsi_14") if indicators else None
        if rsi is None and rsi is None:
            rsi = _compute_rsi(closes)
        rel_vol: float = (
            indicators.get("relative_volume", 1.0) if indicators
            else _compute_relative_volume(volumes)
        )
        trend_str: float = (
            indicators.get("trend_strength", 0.0) if indicators
            else abs(_compute_trend_strength(closes))
        )
        vol_pct: float = (
            indicators.get("volatility", 0.0) if indicators
            else _compute_volatility(closes)
        )

        change_pct = quote.day_change_percent

        # --- Opportunity score (0-1, higher = better) ---
        opp = 0.0
        w = self._weights

        # 1. Change magnitude (reward strong moves)
        opp += min(abs(change_pct) / _EXTREME_CHANGE_PCT, 1.0) * w["change_magnitude"]

        # 2. Relative volume (reward volume confirmation)
        if rel_vol > _HIGH_REL_VOLUME:
            vol_score = min((rel_vol - 1.0) / 4.0, 1.0)
        elif rel_vol < _LOW_REL_VOLUME:
            vol_score = 0.0
        else:
            vol_score = (rel_vol - _LOW_REL_VOLUME) / (_HIGH_REL_VOLUME - _LOW_REL_VOLUME) * 0.5
        opp += vol_score * w["relative_volume"]

        # 3. RSI signal (reward oversold for buys, overbought for short setups)
        opp += _momentum_score(rsi) * w["rsi_signal"]

        # 4. Trend strength
        opp += min(trend_str / 50.0, 1.0) * w["trend_strength"]

        # 5. Structure quality (from TA or computed)
        if ta:
            struct_score = _structure_score(ta)
        else:
            # Build a minimal TA-like dict for scoring
            tmp = TechnicalAnalysis(
                symbol=quote.symbol,
                trend_strength=trend_str,
                market_structure="",
            )
            struct_score = _structure_score(tmp)
        opp += struct_score * w["structure_quality"]

        # 6. Liquidity bonus
        liq = _liquidity_score(quote)
        opp += liq * w["liquidity_penalty"]

        # --- Risk score (0-1, higher = riskier) ---
        risk = _risk_score_for_mover(change_pct, rel_vol, rsi, vol_pct)

        # Liquidity risk (inverse of liquidity)
        risk += (1.0 - liq) * 0.15
        risk = min(risk, 1.0)

        return {"opportunity": round(opp, 4), "risk": round(risk, 4)}

    # ------------------------------------------------------------------
    # MarketMover construction
    # ------------------------------------------------------------------

    def _build_movers(
        self,
        ranked: List[Tuple[str, Dict[str, float]]],
        quotes: Dict[str, MarketQuote],
        all_scores: Dict[str, Dict[str, float]],
        category: str,
    ) -> List[MarketMover]:
        movers: List[MarketMover] = []
        for symbol, score_dict in ranked:
            q = quotes.get(symbol)
            if q is None:
                continue
            bars: List[OHLCV] = []  # bars not needed here for reason text
            rsi = _compute_rsi([b.close for b in bars]) if bars else None
            rel_vol = _compute_relative_volume([b.volume for b in bars]) if bars else 0.0
            reason = self._build_reason(symbol, q, score_dict, category, rsi, rel_vol)
            movers.append(
                MarketMover(
                    symbol=symbol,
                    current_price=q.current_price,
                    change_percent=round(q.day_change_percent, 2),
                    volume=q.volume,
                    relative_volume=round(rel_vol, 2),
                    reason=reason,
                    category=category,
                    score=round(score_dict.get(category, score_dict.get("opportunity", 0.0)), 4),
                )
            )
        return movers

    def _build_reason(
        self,
        symbol: str,
        quote: MarketQuote,
        score_dict: Dict[str, float],
        category: str,
        rsi: Optional[float],
        rel_vol: float,
    ) -> str:
        parts: List[str] = []
        change = quote.day_change_percent
        if abs(change) >= _EXTREME_CHANGE_PCT:
            direction = "surged" if change > 0 else "crashed"
            parts.append(f"{direction} {abs(change):.1f}%")
        elif abs(change) >= 2.0:
            direction = "up" if change > 0 else "down"
            parts.append(f"{direction} {abs(change):.1f}%")

        if rel_vol >= _HIGH_REL_VOLUME:
            parts.append(f"volume {rel_vol:.1f}x avg")
        elif rel_vol <= _LOW_REL_VOLUME:
            parts.append(f"thin volume ({rel_vol:.1f}x)")

        if rsi is not None:
            if rsi <= _RSI_OVERSOLD:
                parts.append(f"RSI oversold ({rsi:.0f})")
            elif rsi >= _RSI_OVERBOUGHT:
                parts.append(f"RSI overbought ({rsi:.0f})")

        if not parts:
            parts.append(f"score={score_dict.get(category, 0):.2f}")
        return "; ".join(parts)
