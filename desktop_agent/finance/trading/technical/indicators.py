"""
MYRAA Trading Intelligence — Technical Indicators (Part 4)

Pure computation engines. Indicators are evidence, NOT standalone decisions.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ..models import OHLCV


def sma(closes: List[float], period: int) -> List[Optional[float]]:
    if len(closes) < period:
        return [None] * len(closes)
    result: List[Optional[float]] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(closes[i - period + 1:i + 1]) / period)
    return result


def ema(closes: List[float], period: int) -> List[Optional[float]]:
    if not closes:
        return []
    multiplier = 2.0 / (period + 1)
    result: List[Optional[float]] = [None] * (period - 1)
    first_ema = sum(closes[:period]) / period
    result.append(first_ema)
    for i in range(period, len(closes)):
        val = (closes[i] - result[-1]) * multiplier + result[-1]
        result.append(val)
    return result


def rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    if len(closes) < period + 1:
        return [None] * len(closes)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0, d) for d in deltas]
    losses = [max(0, -d) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result: List[Optional[float]] = [None] * period
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - (100.0 / (1.0 + rs)))
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - (100.0 / (1.0 + rs)))
    return result


def macd(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, List[Optional[float]]]:
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_line: List[Optional[float]] = []
    for i in range(len(closes)):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            macd_line.append(fast_ema[i] - slow_ema[i])
        else:
            macd_line.append(None)
    valid_macd = [v for v in macd_line if v is not None]
    signal_line = ema(valid_macd, signal) if len(valid_macd) >= signal else []
    histogram: List[Optional[float]] = []
    signal_idx = 0
    for i in range(len(macd_line)):
        if macd_line[i] is None:
            histogram.append(None)
        elif signal_idx < len(signal_line) and signal_line[signal_idx] is not None:
            histogram.append(macd_line[i] - signal_line[signal_idx])
            signal_idx += 1
        else:
            histogram.append(None)
    while len(signal_line) < len(macd_line):
        signal_line.insert(0, None)
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> List[Optional[float]]:
    if len(highs) < 2:
        return [None] * len(highs)
    trs: List[float] = [highs[0] - lows[0]]
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    result: List[Optional[float]] = [None] * (period - 1)
    if len(trs) >= period:
        first_atr = sum(trs[:period]) / period
        result.append(first_atr)
        for i in range(period, len(trs)):
            val = (result[-1] * (period - 1) + trs[i]) / period
            result.append(val)
    return result


def bollinger_bands(
    closes: List[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> Dict[str, List[Optional[float]]]:
    middle = sma(closes, period)
    upper: List[Optional[float]] = []
    lower: List[Optional[float]] = []
    for i in range(len(closes)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = closes[i - period + 1:i + 1]
            mean = middle[i]
            variance = sum((x - mean) ** 2 for x in window) / period
            sd = math.sqrt(variance)
            upper.append(mean + std_dev * sd)
            lower.append(mean - std_dev * sd)
    return {"upper": upper, "middle": middle, "lower": lower}


def vwap(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[int],
) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    cumulative_tp_vol = 0.0
    cumulative_vol = 0
    for i in range(len(closes)):
        typical_price = (highs[i] + lows[i] + closes[i]) / 3.0
        cumulative_tp_vol += typical_price * volumes[i]
        cumulative_vol += volumes[i]
        if cumulative_vol > 0:
            result.append(cumulative_tp_vol / cumulative_vol)
        else:
            result.append(None)
    return result


def stochastic(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    k_period: int = 14,
    d_period: int = 3,
) -> Dict[str, List[Optional[float]]]:
    k_values: List[Optional[float]] = []
    for i in range(len(closes)):
        if i < k_period - 1:
            k_values.append(None)
        else:
            window_high = max(highs[i - k_period + 1:i + 1])
            window_low = min(lows[i - k_period + 1:i + 1])
            if window_high == window_low:
                k_values.append(50.0)
            else:
                k_values.append(
                    ((closes[i] - window_low) / (window_high - window_low)) * 100.0
                )
    valid_k = [v for v in k_values if v is not None]
    k_sma = sma(valid_k, d_period) if len(valid_k) >= d_period else []
    d_values: List[Optional[float]] = []
    ki = 0
    for i in range(len(k_values)):
        if k_values[i] is None:
            d_values.append(None)
        elif ki < len(k_sma):
            d_values.append(k_sma[ki])
            ki += 1
        else:
            d_values.append(None)
    return {"k": k_values, "d": d_values}


def williams_r(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            window_high = max(highs[i - period + 1:i + 1])
            window_low = min(lows[i - period + 1:i + 1])
            if window_high == window_low:
                result.append(-50.0)
            else:
                result.append(
                    ((window_high - closes[i]) / (window_high - window_low)) * -100.0
                )
    return result


def relative_volume(current_volume: int, avg_volumes: List[int], period: int = 20) -> float:
    if not avg_volumes:
        return 1.0
    recent = avg_volumes[-period:] if len(avg_volumes) >= period else avg_volumes
    avg = sum(recent) / len(recent) if recent else 0.0
    if avg == 0:
        return 1.0
    return current_volume / avg


def trend_strength(closes: List[float], period: int = 14) -> float:
    if len(closes) < period:
        return 0.0
    recent = closes[-period:]
    if recent[0] == 0:
        return 0.0
    change_pct = (recent[-1] - recent[0]) / recent[0]
    up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
    consistency = up_days / (len(recent) - 1) if len(recent) > 1 else 0.5
    directional = 1.0 if change_pct > 0 else -1.0
    return directional * abs(change_pct) * consistency * 100


def volatility(closes: List[float], period: int = 20) -> float:
    if len(closes) < period:
        return 0.0
    recent = closes[-period:]
    if len(recent) < 2:
        return 0.0
    returns = [(recent[i] - recent[i - 1]) / recent[i - 1] for i in range(1, len(recent))]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252) * 100


def compute_all_indicators(bars: List[OHLCV]) -> Dict[str, Any]:
    if not bars:
        return {}
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [b.volume for b in bars]
    result: Dict[str, Any] = {}
    result["sma_20"] = sma(closes, 20)
    result["sma_50"] = sma(closes, 50)
    result["sma_200"] = sma(closes, 200)
    result["ema_9"] = ema(closes, 9)
    result["ema_21"] = ema(closes, 21)
    result["ema_50"] = ema(closes, 50)
    result["rsi_14"] = rsi(closes, 14)
    result["rsi_7"] = rsi(closes, 7)
    macd_data = macd(closes)
    result["macd_line"] = macd_data["macd"]
    result["macd_signal"] = macd_data["signal"]
    result["macd_histogram"] = macd_data["histogram"]
    result["atr_14"] = atr(highs, lows, closes, 14)
    bb = bollinger_bands(closes, 20, 2.0)
    result["bb_upper"] = bb["upper"]
    result["bb_middle"] = bb["middle"]
    result["bb_lower"] = bb["lower"]
    result["vwap"] = vwap(highs, lows, closes, volumes)
    stoch = stochastic(highs, lows, closes)
    result["stoch_k"] = stoch["k"]
    result["stoch_d"] = stoch["d"]
    result["williams_r"] = williams_r(highs, lows, closes)
    result["relative_volume"] = relative_volume(volumes[-1] if volumes else 0, volumes)
    result["trend_strength"] = trend_strength(closes)
    result["volatility"] = volatility(closes)
    return result
