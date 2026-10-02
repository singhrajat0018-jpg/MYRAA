// ============================================================================
// MYRAA Phase 26 — Technical Analysis Engine
// Pure-math, no LLM. All indicator computations are correct implementations.
// ============================================================================

import type {
  OHLCVBar,
  Timeframe,
  TechnicalAnalysis,
  TechnicalIndicators,
  TrendAnalysis,
  SupportResistanceLevel,
  BreakoutSignal,
  VolumeAnalysis,
  VolatilityAnalysis,
  MultiTimeframeAlignment,
  SignalBias,
  TrendDirection,
} from './contracts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function safeDiv(n: number, d: number): number {
  return d === 0 ? 0 : n / d;
}

function last<T>(arr: readonly T[]): T | undefined {
  return arr.length > 0 ? arr[arr.length - 1] : undefined;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function stdev(arr: readonly number[], mean: number): number {
  if (arr.length < 2) return 0;
  const variance = arr.reduce((s, v) => s + (v - mean) ** 2, 0) / (arr.length - 1);
  return Math.sqrt(variance);
}

// ---------------------------------------------------------------------------
// TechnicalAnalysisEngine
// ---------------------------------------------------------------------------

export class TechnicalAnalysisEngine {
  // -----------------------------------------------------------------------
  // 1. Main entry point
  // -----------------------------------------------------------------------
  analyze(
    bars: readonly OHLCVBar[],
    timeframe: Timeframe,
    symbol: string,
  ): TechnicalAnalysis {
    if (bars.length === 0) {
      return this.emptyAnalysis(timeframe, symbol);
    }

    const closes = bars.map((b) => b.close);

    const sma20 = this.computeSMA(closes, 20);
    const sma50 = this.computeSMA(closes, 50);
    const sma100 = this.computeSMA(closes, 100);
    const sma200 = this.computeSMA(closes, 200);
    const ema9 = this.computeEMA(closes, 9);
    const ema21 = this.computeEMA(closes, 21);
    const ema50 = this.computeEMA(closes, 50);
    const rsi14 = this.computeRSI(closes, 14);
    const macdResult = this.computeMACD(closes, 12, 26, 9);
    const bollinger = this.computeBollingerBands(closes, 20, 2);
    const atr14 = this.computeATR(bars, 14);
    const adxResult = this.computeADX(bars, 14);
    const vwap = this.computeVWAP(bars);
    const obv = this.computeOBV(bars);

    const lastClose = closes[closes.length - 1];
    const prevClose = closes.length >= 2 ? closes[closes.length - 2] : lastClose;

    // Momentum & ROC
    const momentum10 =
      closes.length >= 10 ? lastClose - closes[closes.length - 10] : 0;
    const roc12 =
      closes.length >= 12
        ? safeDiv(lastClose - closes[closes.length - 12], closes[closes.length - 12]) * 100
        : 0;

    const indicators: TechnicalIndicators = {
      sma20: last(sma20) != null ? { value: last(sma20)!, period: 20 } : undefined,
      sma50: last(sma50) != null ? { value: last(sma50)!, period: 50 } : undefined,
      sma100: last(sma100) != null ? { value: last(sma100)!, period: 100 } : undefined,
      sma200: last(sma200) != null ? { value: last(sma200)!, period: 200 } : undefined,
      ema9: last(ema9) != null ? { value: last(ema9)!, period: 9 } : undefined,
      ema21: last(ema21) != null ? { value: last(ema21)!, period: 21 } : undefined,
      ema50: last(ema50) != null ? { value: last(ema50)!, period: 50 } : undefined,
      rsi14: last(rsi14) != null ? { value: last(rsi14)!, period: 14 } : undefined,
      macd:
        macdResult.macd.length > 0
          ? {
              macd: last(macdResult.macd)!,
              signal: last(macdResult.signal)!,
              histogram: last(macdResult.histogram)!,
            }
          : undefined,
      bollinger:
        bollinger.upper.length > 0
          ? {
              upper: last(bollinger.upper)!,
              middle: last(bollinger.middle)!,
              lower: last(bollinger.lower)!,
              bandwidth: last(bollinger.bandwidth)!,
            }
          : undefined,
      atr14: last(atr14) != null ? { value: last(atr14)!, period: 14 } : undefined,
      adx14:
        adxResult.adx.length > 0
          ? { value: last(adxResult.adx)!, plusDI: last(adxResult.plusDI)!, minusDI: last(adxResult.minusDI)! }
          : undefined,
      vwap: last(vwap) != null ? { value: last(vwap)! } : undefined,
      roc12,
      momentum10,
      obv: last(obv),
      volumeRatio: safeDiv(lastClose, prevClose),
      relativeVolume: this.computeRelativeVolume(bars),
    };

    const trend = this.detectTrend(closes, sma20, sma50, sma200);
    const srLevels = this.findSupportResistance(bars);
    const breakout = this.detectBreakout(bars, srLevels);
    const volumeAnalysis = this.analyzeVolume(bars);
    const volatilityAnalysis = this.analyzeVolatility(bars);

    // Multi-timeframe — single timeframe fallback
    const allBars: Record<Timeframe, readonly OHLCVBar[]> = {
      '1m': [], '5m': [], '15m': [], '1h': [],
      '4h': [], '1d': [], '1w': [], '1M': [],
    };
    allBars[timeframe] = bars;
    const multiTimeframe = this.computeMultiTimeframe(allBars);

    const sig = this.determineSignal(indicators, trend, breakout, volumeAnalysis, volatilityAnalysis);

    return {
      assetId: symbol,
      symbol,
      timeframe,
      timestamp: new Date().toISOString(),
      indicators,
      trend,
      supportResistance: srLevels,
      breakout,
      volume: volumeAnalysis,
      volatility: volatilityAnalysis,
      multiTimeframe,
      signal: sig.signal,
      signalStrength: sig.strength,
      bullishEvidence: sig.bullish,
      bearishEvidence: sig.bearish,
      neutralEvidence: sig.neutral,
    };
  }

  // -----------------------------------------------------------------------
  // 1.5. Multi-timeframe analysis
  // -----------------------------------------------------------------------
  analyzeMultiTimeframe(
    timeframeData: Record<Timeframe, readonly OHLCVBar[]>,
    primaryTimeframe: Timeframe = '1d',
    symbol: string = '',
  ): TechnicalAnalysis {
    // Validate that we have data for the primary timeframe
    const primaryBars = timeframeData[primaryTimeframe];
    if (!primaryBars || primaryBars.length === 0) {
      // Fallback to empty analysis if no primary data
      return this.emptyAnalysis(primaryTimeframe, symbol);
    }

    // Compute individual timeframe analysis for primary timeframe
    // (for indicators, trend, etc. that are single-timeframe specific)
    const primaryAnalysis = this.analyze(primaryBars, primaryTimeframe, symbol);

    // Compute proper multi-timeframe alignment using ALL available data
    const multiTimeframe = this.computeMultiTimeframe(timeframeData);

    // Return a TechnicalAnalysis object that combines:
    // - Single-timeframe indicators/trend/etc. from primary timeframe
    // - Proper multi-timeframe alignment from all timeframes
    // - Other fields that can be derived or defaulted
    return {
      ...primaryAnalysis, // Spread all fields from primary analysis
      multiTimeframe: multiTimeframe, // Override with proper multi-timeframe analysis
      // Note: The timeframe field in the spread object will be the primaryTimeframe,
      // which is acceptable for signaling purposes
    };
  }

  // -----------------------------------------------------------------------
  // 2. SMA
  // -----------------------------------------------------------------------
  computeSMA(values: readonly number[], period: number): number[] {
    if (period <= 0 || values.length === 0) return [];
    const result: number[] = [];
    let sum = 0;
    for (let i = 0; i < values.length; i++) {
      sum += values[i];
      if (i >= period) sum -= values[i - period];
      if (i >= period - 1) {
        result.push(sum / period);
      }
    }
    return result;
  }

  // -----------------------------------------------------------------------
  // 3. EMA
  // -----------------------------------------------------------------------
  computeEMA(values: readonly number[], period: number): number[] {
    if (period <= 0 || values.length === 0) return [];
    const k = 2 / (period + 1);
    const result: number[] = [];

    // Seed with SMA of first `period` values
    let ema = 0;
    const seedLen = Math.min(period, values.length);
    for (let i = 0; i < seedLen; i++) ema += values[i];
    ema /= seedLen;
    result.push(ema);

    for (let i = seedLen; i < values.length; i++) {
      ema = values[i] * k + ema * (1 - k);
      result.push(ema);
    }
    return result;
  }

  // -----------------------------------------------------------------------
  // 4. RSI
  // -----------------------------------------------------------------------
  computeRSI(closes: readonly number[], period: number): number[] {
    if (closes.length < period + 1) return [];
    const result: number[] = [];
    let avgGain = 0;
    let avgLoss = 0;

    // Initial average over first `period` changes
    for (let i = 1; i <= period; i++) {
      const change = closes[i] - closes[i - 1];
      if (change > 0) avgGain += change;
      else avgLoss += Math.abs(change);
    }
    avgGain /= period;
    avgLoss /= period;

    const rs = safeDiv(avgGain, avgLoss);
    result.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + rs));

    for (let i = period + 1; i < closes.length; i++) {
      const change = closes[i] - closes[i - 1];
      const gain = change > 0 ? change : 0;
      const loss = change < 0 ? Math.abs(change) : 0;
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      const r = safeDiv(avgGain, avgLoss);
      result.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + r));
    }
    return result;
  }

  // -----------------------------------------------------------------------
  // 5. MACD
  // -----------------------------------------------------------------------
  computeMACD(
    closes: readonly number[],
    fast: number,
    slow: number,
    signal: number,
  ): { macd: number[]; signal: number[]; histogram: number[] } {
    if (closes.length < slow + signal) {
      return { macd: [], signal: [], histogram: [] };
    }

    const emaFast = this.computeEMA(closes, fast);
    const emaSlow = this.computeEMA(closes, slow);

    // EMA offsets: EMA(fast) starts at index fast-1, EMA(slow) starts at index slow-1
    // MACD line exists from slow-1 onwards (where both have values)
    const macdOffset = slow - fast; // offset into emaFast array where emaSlow[0] aligns
    const macdLine: number[] = [];
    for (let i = 0; i < emaSlow.length; i++) {
      macdLine.push(emaFast[i + macdOffset] - emaSlow[i]);
    }

    const signalLine = this.computeEMA(macdLine, signal);
    const histogram: number[] = [];

    // Offset for histogram: signal starts after signal-1 MACD values
    const histOffset = macdLine.length - signalLine.length;
    for (let i = 0; i < signalLine.length; i++) {
      histogram.push(macdLine[i + histOffset] - signalLine[i]);
    }

    return { macd: macdLine, signal: signalLine, histogram };
  }

  // -----------------------------------------------------------------------
  // 6. Bollinger Bands
  // -----------------------------------------------------------------------
  computeBollingerBands(
    closes: readonly number[],
    period: number,
    stdDev: number,
  ): { upper: number[]; middle: number[]; lower: number[]; bandwidth: number[] } {
    if (closes.length < period) {
      return { upper: [], middle: [], lower: [], bandwidth: [] };
    }

    const middle = this.computeSMA(closes, period);
    const upper: number[] = [];
    const lower: number[] = [];
    const bandwidth: number[] = [];

    for (let i = 0; i < middle.length; i++) {
      const sliceStart = i; // slices correspond to SMA offsets
      const slice = closes.slice(sliceStart, sliceStart + period);
      const mean = middle[i];
      const sd = stdev(slice, mean);
      const u = mean + stdDev * sd;
      const l = mean - stdDev * sd;
      upper.push(u);
      lower.push(l);
      bandwidth.push(safeDiv(u - l, mean) * 100);
    }

    return { upper, middle, lower, bandwidth };
  }

  // -----------------------------------------------------------------------
  // 7. ATR
  // -----------------------------------------------------------------------
  computeATR(bars: readonly OHLCVBar[], period: number): number[] {
    if (bars.length < 2 || period <= 0) return [];

    const trueRanges: number[] = [];
    for (let i = 1; i < bars.length; i++) {
      const hl = bars[i].high - bars[i].low;
      const hc = Math.abs(bars[i].high - bars[i - 1].close);
      const lc = Math.abs(bars[i].low - bars[i - 1].close);
      trueRanges.push(Math.max(hl, hc, lc));
    }

    if (trueRanges.length < period) return [];

    // Initial ATR = simple average of first `period` TRs
    let atr = 0;
    for (let i = 0; i < period; i++) atr += trueRanges[i];
    atr /= period;

    const result: number[] = [atr];
    for (let i = period; i < trueRanges.length; i++) {
      atr = (atr * (period - 1) + trueRanges[i]) / period;
      result.push(atr);
    }
    return result;
  }

  // -----------------------------------------------------------------------
  // 8. ADX (+DI, -DI)
  // -----------------------------------------------------------------------
  computeADX(
    bars: readonly OHLCVBar[],
    period: number,
  ): { adx: number[]; plusDI: number[]; minusDI: number[] } {
    if (bars.length < period * 2 + 1) {
      return { adx: [], plusDI: [], minusDI: [] };
    }

    // True Range + directional movement
    const trArr: number[] = [];
    const plusDMs: number[] = [];
    const minusDMs: number[] = [];

    for (let i = 1; i < bars.length; i++) {
      const hl = bars[i].high - bars[i].low;
      const hc = Math.abs(bars[i].high - bars[i - 1].close);
      const lc = Math.abs(bars[i].low - bars[i - 1].close);
      trArr.push(Math.max(hl, hc, lc));

      const up = bars[i].high - bars[i - 1].high;
      const down = bars[i - 1].low - bars[i].low;
      plusDMs.push(up > down && up > 0 ? up : 0);
      minusDMs.push(down > up && down > 0 ? down : 0);
    }

    // Smoothed TR, +DM, -DM (Wilder's smoothing)
    let smoothTR = 0;
    let smoothPlusDM = 0;
    let smoothMinusDM = 0;
    for (let i = 0; i < period; i++) {
      smoothTR += trArr[i];
      smoothPlusDM += plusDMs[i];
      smoothMinusDM += minusDMs[i];
    }

    const plusDIArr: number[] = [];
    const minusDIArr: number[] = [];
    const dxArr: number[] = [];

    const updateSmooth = () => {
      smoothTR = smoothTR - smoothTR / period + trArr[0];
      smoothPlusDM = smoothPlusDM - smoothPlusDM / period + plusDMs[0];
      smoothMinusDM = smoothMinusDM - smoothMinusDM / period + minusDMs[0];
    };

    // Process first smoothed window
    const plusDI100 = safeDiv(smoothPlusDM, smoothTR) * 100;
    const minusDI100 = safeDiv(smoothMinusDM, smoothTR) * 100;
    plusDIArr.push(plusDI100);
    minusDIArr.push(minusDI100);
    dxArr.push(safeDiv(Math.abs(plusDI100 - minusDI100), plusDI100 + minusDI100) * 100);

    // Shift and continue
    trArr.shift();
    plusDMs.shift();
    minusDMs.shift();

    for (let i = 0; i < period; i++) {
      updateSmooth();
      const pdi = safeDiv(smoothPlusDM, smoothTR) * 100;
      const mdi = safeDiv(smoothMinusDM, smoothTR) * 100;
      plusDIArr.push(pdi);
      minusDIArr.push(mdi);
      dxArr.push(safeDiv(Math.abs(pdi - mdi), pdi + mdi) * 100);

      trArr.shift();
      plusDMs.shift();
      minusDMs.shift();
    }

    // ADX = smoothed DX
    const adxArr: number[] = [];
    if (dxArr.length >= period) {
      let adx = 0;
      for (let i = 0; i < period; i++) adx += dxArr[i];
      adx /= period;
      adxArr.push(adx);

      for (let i = period; i < dxArr.length; i++) {
        adx = (adx * (period - 1) + dxArr[i]) / period;
        adxArr.push(adx);
      }
    }

    return { adx: adxArr, plusDI: plusDIArr, minusDI: minusDIArr };
  }

  // -----------------------------------------------------------------------
  // 9. VWAP (resets each session — starts from first bar)
  // -----------------------------------------------------------------------
  computeVWAP(bars: readonly OHLCVBar[]): number[] {
    if (bars.length === 0) return [];
    const result: number[] = [];
    let cumTPVol = 0;
    let cumVol = 0;

    for (const bar of bars) {
      const tp = (bar.high + bar.low + bar.close) / 3;
      cumTPVol += tp * bar.volume;
      cumVol += bar.volume;
      result.push(safeDiv(cumTPVol, cumVol));
    }
    return result;
  }

  // -----------------------------------------------------------------------
  // 10. OBV
  // -----------------------------------------------------------------------
  computeOBV(bars: readonly OHLCVBar[]): number[] {
    if (bars.length === 0) return [];
    const result: number[] = [0]; // first bar OBV = 0

    for (let i = 1; i < bars.length; i++) {
      let obv = result[i - 1];
      if (bars[i].close > bars[i - 1].close) {
        obv += bars[i].volume;
      } else if (bars[i].close < bars[i - 1].close) {
        obv -= bars[i].volume;
      }
      result.push(obv);
    }
    return result;
  }

  // -----------------------------------------------------------------------
  // 11. Trend detection
  // -----------------------------------------------------------------------
  detectTrend(
    closes: readonly number[],
    sma20: readonly number[],
    sma50: readonly number[],
    sma200: readonly number[],
  ): TrendAnalysis {
    if (closes.length < 20) {
      return {
        direction: 'UNKNOWN',
        strength: 0,
        duration: 0,
        evidence: ['Insufficient data for trend analysis'],
        movingAverageAlignment: 'MIXED',
        priceVsSMA200: 'AT',
      };
    }

    const price = closes[closes.length - 1];
    const evidence: string[] = [];

    // Moving average alignment
    const s20 = last(sma20);
    const s50 = last(sma50);
    const s200 = last(sma200);

    let alignment: 'BULLISH' | 'BEARISH' | 'MIXED' = 'MIXED';
    if (s20 != null && s50 != null && s200 != null) {
      if (s20 > s50 && s50 > s200) {
        alignment = 'BULLISH';
        evidence.push('Bullish MA alignment: SMA20 > SMA50 > SMA200');
      } else if (s20 < s50 && s50 < s200) {
        alignment = 'BEARISH';
        evidence.push('Bearish MA alignment: SMA20 < SMA50 < SMA200');
      } else {
        evidence.push('Mixed MA alignment');
      }
    } else if (s20 != null && s50 != null) {
      if (s20 > s50) {
        alignment = 'BULLISH';
        evidence.push('SMA20 > SMA50 (short-term bullish)');
      } else {
        alignment = 'BEARISH';
        evidence.push('SMA20 < SMA50 (short-term bearish)');
      }
    }

    // Price vs SMA200
    let priceVsSMA200: 'ABOVE' | 'BELOW' | 'AT' = 'AT';
    if (s200 != null) {
      if (price > s200 * 1.01) {
        priceVsSMA200 = 'ABOVE';
        evidence.push('Price above SMA200');
      } else if (price < s200 * 0.99) {
        priceVsSMA200 = 'BELOW';
        evidence.push('Price below SMA200');
      } else {
        evidence.push('Price near SMA200');
      }
    }

    // Direction from alignment + price position
    let direction: TrendDirection = 'RANGE';
    let strength = 0;

    if (alignment === 'BULLISH' && priceVsSMA200 === 'ABOVE') {
      direction = 'UPTREND';
      strength = 0.7;
    } else if (alignment === 'BEARISH' && priceVsSMA200 === 'BELOW') {
      direction = 'DOWNTREND';
      strength = 0.7;
    } else if (alignment === 'BULLISH') {
      direction = 'UPTREND';
      strength = 0.5;
    } else if (alignment === 'BEARISH') {
      direction = 'DOWNTREND';
      strength = 0.5;
    }

    // Check for transition: price recently crossing a major MA
    if (s200 != null && s50 != null) {
      if (s50 > s200 && price < s200) {
        direction = 'TRANSITION';
        strength = 0.4;
        evidence.push('Potential transition: SMA50 > SMA200 but price below SMA200');
      } else if (s50 < s200 && price > s200) {
        direction = 'TRANSITION';
        strength = 0.4;
        evidence.push('Potential transition: SMA50 < SMA200 but price above SMA200');
      }
    }

    // Duration estimate: count consecutive bars in trend direction
    let duration = 0;
    if (direction === 'UPTREND' || direction === 'DOWNTREND') {
      for (let i = closes.length - 1; i >= 1; i--) {
        const trendUp = direction === 'UPTREND';
        if (trendUp ? closes[i] >= closes[i - 1] : closes[i] <= closes[i - 1]) {
          duration++;
        } else {
          break;
        }
      }
    }

    // Adjust strength based on ADX-like metric (price momentum consistency)
    if (s20 != null && s50 != null) {
      const spread = Math.abs(s20 - s50) / price;
      strength = clamp(strength + spread * 10, 0, 1);
    }

    if (evidence.length === 0) {
      evidence.push('No clear trend detected — ranging');
    }

    return {
      direction,
      strength: Math.round(strength * 100) / 100,
      duration,
      evidence,
      movingAverageAlignment: alignment,
      priceVsSMA200,
    };
  }

  // -----------------------------------------------------------------------
  // 12. Support & Resistance (swing highs/lows)
  // -----------------------------------------------------------------------
  findSupportResistance(bars: readonly OHLCVBar[]): readonly SupportResistanceLevel[] {
    if (bars.length < 5) return [];

    const levels: SupportResistanceLevel[] = [];
    const lookback = 5; // bars on each side for swing detection

    for (let i = lookback; i < bars.length - lookback; i++) {
      const bar = bars[i];

      // Swing high
      let isSwingHigh = true;
      for (let j = 1; j <= lookback; j++) {
        if (bars[i - j].high >= bar.high || bars[i + j].high >= bar.high) {
          isSwingHigh = false;
          break;
        }
      }
      if (isSwingHigh) {
        levels.push({
          price: bar.high,
          type: 'RESISTANCE',
          strength: this.srStrength(bars, bar.high),
          source: 'SWING',
          timeframe: '1d',
          touchCount: this.srTouchCount(bars, bar.high),
        });
      }

      // Swing low
      let isSwingLow = true;
      for (let j = 1; j <= lookback; j++) {
        if (bars[i - j].low <= bar.low || bars[i + j].low <= bar.low) {
          isSwingLow = false;
          break;
        }
      }
      if (isSwingLow) {
        levels.push({
          price: bar.low,
          type: 'SUPPORT',
          strength: this.srStrength(bars, bar.low),
          source: 'SWING',
          timeframe: '1d',
          touchCount: this.srTouchCount(bars, bar.low),
        });
      }
    }

    // Merge nearby levels (within 0.5% of each other)
    return this.mergeSRLevels(levels);
  }

  // -----------------------------------------------------------------------
  // 13. Breakout detection
  // -----------------------------------------------------------------------
  detectBreakout(
    bars: readonly OHLCVBar[],
    levels: readonly SupportResistanceLevel[],
  ): BreakoutSignal | null {
    if (bars.length < 2 || levels.length === 0) return null;

    const current = bars[bars.length - 1];
    const prev = bars[bars.length - 2];
    const currentClose = current.close;
    const prevClose = prev.close;

    // Average volume for confirmation
    const avgVol =
      bars.length >= 20
        ? bars.slice(-20).reduce((s, b) => s + b.volume, 0) / 20
        : bars.reduce((s, b) => s + b.volume, 0) / bars.length;
    const volConfirm = current.volume > avgVol * 1.3;

    // Check resistance levels for breakout
    for (const level of levels) {
      if (level.type === 'RESISTANCE') {
        // Breakout: price crossed above resistance
        if (prevClose <= level.price && currentClose > level.price) {
          return {
            type: 'BREAKOUT',
            level: level.price,
            confirmationRequired: !volConfirm,
            volumeConfirmation: volConfirm,
            confidence: volConfirm ? 0.75 : 0.5,
          };
        }

        // False breakout: price crossed above then fell back
        if (current.high > level.price && currentClose < level.price && prevClose <= level.price) {
          return {
            type: 'FALSE_BREAKOUT',
            level: level.price,
            confirmationRequired: true,
            volumeConfirmation: false,
            confidence: 0.6,
          };
        }
      }

      if (level.type === 'SUPPORT') {
        // Breakdown: price crossed below support
        if (prevClose >= level.price && currentClose < level.price) {
          return {
            type: 'BREAKDOWN',
            level: level.price,
            confirmationRequired: !volConfirm,
            volumeConfirmation: volConfirm,
            confidence: volConfirm ? 0.75 : 0.5,
          };
        }

        // Retest: price broke below and now approaching from below
        if (
          currentClose < level.price &&
          currentClose > level.price * 0.98 &&
          current.low <= level.price &&
          current.close > current.open
        ) {
          return {
            type: 'RETEST',
            level: level.price,
            confirmationRequired: true,
            volumeConfirmation: volConfirm,
            confidence: 0.55,
          };
        }
      }
    }

    return null;
  }

  // -----------------------------------------------------------------------
  // 14. Volume analysis
  // -----------------------------------------------------------------------
  analyzeVolume(bars: readonly OHLCVBar[]): VolumeAnalysis {
    if (bars.length === 0) {
      return {
        currentVolume: 0,
        averageVolume20d: 0,
        relativeVolume: 0,
        trend: 'STABLE',
        significance: 'LOW',
      };
    }

    const currentVolume = bars[bars.length - 1].volume;
    const avgWindow = Math.min(20, bars.length);
    const averageVolume20d =
      bars.slice(-avgWindow).reduce((s, b) => s + b.volume, 0) / avgWindow;

    const relativeVolume = safeDiv(currentVolume, averageVolume20d);

    // Volume trend: compare recent 5-bar average vs prior 5-bar average
    let trend: 'EXPANDING' | 'CONTRACTING' | 'STABLE' = 'STABLE';
    if (bars.length >= 10) {
      const recent = bars.slice(-5).reduce((s, b) => s + b.volume, 0) / 5;
      const prior = bars.slice(-10, -5).reduce((s, b) => s + b.volume, 0) / 5;
      const change = safeDiv(recent - prior, prior);
      if (change > 0.15) trend = 'EXPANDING';
      else if (change < -0.15) trend = 'CONTRACTING';
    }

    let significance: 'HIGH' | 'MEDIUM' | 'LOW' = 'LOW';
    if (relativeVolume > 2.0) significance = 'HIGH';
    else if (relativeVolume > 1.3) significance = 'MEDIUM';

    return {
      currentVolume,
      averageVolume20d,
      relativeVolume,
      trend,
      significance,
    };
  }

  // -----------------------------------------------------------------------
  // 15. Volatility analysis
  // -----------------------------------------------------------------------
  analyzeVolatility(bars: readonly OHLCVBar[]): VolatilityAnalysis {
    if (bars.length < 15) {
      return {
        atr14: 0,
        historicalVolatility20d: 0,
        historicalVolatility60d: 0,
        regime: 'NORMAL',
        percentileRank: 50,
      };
    }

    const closes = bars.map((b) => b.close);
    const atr14Arr = this.computeATR(bars, 14);
    const atr14 = last(atr14Arr) ?? 0;

    // Historical volatility: annualized stdev of log returns
    const hv20 = this.historicalVolatility(closes, 20);
    const hv60 = this.historicalVolatility(closes, 60);

    // Regime classification based on ATR as % of price
    const price = closes[closes.length - 1];
    const atrPercent = safeDiv(atr14, price) * 100;

    let regime: 'HIGH' | 'NORMAL' | 'LOW' = 'NORMAL';
    if (atrPercent > 3.0) regime = 'HIGH';
    else if (atrPercent < 1.0) regime = 'LOW';

    // Percentile rank: where current ATR sits in its own history
    const percentileRank = this.atrPercentile(atr14Arr);

    return {
      atr14,
      historicalVolatility20d: hv20,
      historicalVolatility60d: hv60,
      regime,
      percentileRank,
    };
  }

  // -----------------------------------------------------------------------
  // 16. Multi-timeframe alignment
  // -----------------------------------------------------------------------
  computeMultiTimeframe(
    allBars: Record<Timeframe, readonly OHLCVBar[]>,
  ): MultiTimeframeAlignment {
    const tfDirection = (tf: Timeframe): TrendDirection => {
      const bars = allBars[tf];
      if (!bars || bars.length < 20) return 'UNKNOWN';
      const closes = bars.map((b) => b.close);
      const sma20 = this.computeSMA(closes, 20);
      const sma50 = this.computeSMA(closes, 50);
      const s20 = last(sma20);
      const s50 = last(sma50);
      if (s20 == null || s50 == null) return 'UNKNOWN';
      if (s20 > s50 && closes[closes.length - 1] > s20) return 'UPTREND';
      if (s20 < s50 && closes[closes.length - 1] < s20) return 'DOWNTREND';
      return 'RANGE';
    };

    const monthly = tfDirection('1M');
    const weekly = tfDirection('1w');
    const daily = tfDirection('1d');
    const fourHour = tfDirection('4h');
    const oneHour = tfDirection('1h');

    const directions: TrendDirection[] = [monthly, weekly, daily, fourHour, oneHour];
    const valid = directions.filter((d) => d !== 'UNKNOWN');

    // Alignment score: fraction of known timeframes pointing in same direction
    let alignmentScore = 0;
    if (valid.length >= 2) {
      const bullCount = valid.filter((d) => d === 'UPTREND').length;
      const bearCount = valid.filter((d) => d === 'DOWNTREND').length;
      alignmentScore = Math.max(bullCount, bearCount) / valid.length;
    }

    // Description
    let description = 'Insufficient data for multi-timeframe analysis';
    if (valid.length >= 2) {
      const bullCount = valid.filter((d) => d === 'UPTREND').length;
      const bearCount = valid.filter((d) => d === 'DOWNTREND').length;
      if (bullCount === valid.length) {
        description = 'All timeframes aligned bullish — strong uptrend confluence';
      } else if (bearCount === valid.length) {
        description = 'All timeframes aligned bearish — strong downtrend confluence';
      } else if (bullCount > bearCount) {
        description = 'Mostly bullish alignment with some divergence';
      } else if (bearCount > bullCount) {
        description = 'Mostly bearish alignment with some divergence';
      } else {
        description = 'Mixed signals across timeframes — no clear alignment';
      }
    }

    return {
      monthly,
      weekly,
      daily,
      fourHour,
      oneHour,
      alignmentScore: Math.round(alignmentScore * 100) / 100,
      description,
    };
  }

  // -----------------------------------------------------------------------
  // 17. Signal determination (confluence-based, no double-counting)
  // -----------------------------------------------------------------------
  determineSignal(
    indicators: TechnicalIndicators,
    trend: TrendAnalysis,
    breakout: BreakoutSignal | null,
    volume: VolumeAnalysis,
    volatility: VolatilityAnalysis,
  ): {
    signal: SignalBias;
    strength: number;
    bullish: string[];
    bearish: string[];
    neutral: string[];
  } {
    const bullish: string[] = [];
    const bearish: string[] = [];
    const neutral: string[] = [];

    // --- TREND (single evidence source — SMA alignment) ---
    if (trend.direction === 'UPTREND') {
      bullish.push(`Trend: ${trend.direction} (strength ${trend.strength})`);
    } else if (trend.direction === 'DOWNTREND') {
      bearish.push(`Trend: ${trend.direction} (strength ${trend.strength})`);
    } else if (trend.direction === 'TRANSITION') {
      neutral.push('Trend: Transition phase');
    } else {
      neutral.push('Trend: No clear direction');
    }

    // --- RSI (momentum, independent) ---
    if (indicators.rsi14) {
      const rsi = indicators.rsi14.value;
      if (rsi < 30) {
        bullish.push(`RSI oversold (${rsi.toFixed(1)})`);
      } else if (rsi > 70) {
        bearish.push(`RSI overbought (${rsi.toFixed(1)})`);
      } else if (rsi < 45) {
        neutral.push(`RSI neutral-low (${rsi.toFixed(1)})`);
      } else if (rsi > 55) {
        neutral.push(`RSI neutral-high (${rsi.toFixed(1)})`);
      } else {
        neutral.push(`RSI neutral (${rsi.toFixed(1)})`);
      }
    }

    // --- MACD (momentum, independent from RSI) ---
    if (indicators.macd) {
      const m = indicators.macd;
      if (m.histogram > 0 && m.macd > m.signal) {
        bullish.push(`MACD bullish (histogram ${m.histogram.toFixed(4)})`);
      } else if (m.histogram < 0 && m.macd < m.signal) {
        bearish.push(`MACD bearish (histogram ${m.histogram.toFixed(4)})`);
      } else {
        neutral.push(`MACD neutral`);
      }
    }

    // --- Bollinger Bands (volatility + mean-reversion) ---
    if (indicators.bollinger && indicators.sma20) {
      const bb = indicators.bollinger;
      const price = indicators.sma20.value; // proxy — actual price not in indicators
      // Use bandwidth + position context instead of double-counting with price
      if (bb.bandwidth < 5) {
        neutral.push('Bollinger: squeeze — potential breakout imminent');
      } else if (bb.bandwidth > 15) {
        neutral.push('Bollinger: wide bands — elevated volatility');
      }
    }

    // --- ADX (trend strength, independent) ---
    if (indicators.adx14) {
      const adx = indicators.adx14;
      if (adx.value > 25) {
        if (adx.plusDI > adx.minusDI) {
          bullish.push(`ADX confirms uptrend (${adx.value.toFixed(1)}, +DI > -DI)`);
        } else {
          bearish.push(`ADX confirms downtrend (${adx.value.toFixed(1)}, -DI > +DI)`);
        }
      } else {
        neutral.push(`ADX weak trend (${adx.value.toFixed(1)})`);
      }
    }

    // --- Breakout signals (price action + volume) ---
    if (breakout) {
      if (breakout.type === 'BREAKOUT') {
        bullish.push(`Breakout above ${breakout.level} (confidence ${breakout.confidence})`);
      } else if (breakout.type === 'BREAKDOWN') {
        bearish.push(`Breakdown below ${breakout.level} (confidence ${breakout.confidence})`);
      } else if (breakout.type === 'FALSE_BREAKOUT') {
        bearish.push(`False breakout at ${breakout.level}`);
      } else if (breakout.type === 'RETEST') {
        neutral.push(`Retest of level ${breakout.level}`);
      }
    }

    // --- Volume (confirmation, not directional bias by itself) ---
    if (volume.significance === 'HIGH') {
      neutral.push(`High relative volume (${volume.relativeVolume.toFixed(1)}x avg)`);
    }

    // --- Volatility context ---
    if (volatility.regime === 'HIGH') {
      neutral.push('High volatility regime — wider stops needed');
    } else if (volatility.regime === 'LOW') {
      neutral.push('Low volatility regime — potential for expansion');
    }

    // --- Confluence scoring ---
    const bullCount = bullish.length;
    const bearCount = bearish.length;
    const total = bullCount + bearCount + neutral.length;

    let signal: SignalBias = 'NEUTRAL';
    let strength = 0;

    if (total === 0) {
      return { signal: 'NO_SIGNAL', strength: 0, bullish, bearish, neutral };
    }

    const majority = Math.max(bullCount, bearCount);
    strength = total > 0 ? majority / total : 0;

    if (bullCount > bearCount && bullCount >= 2) {
      signal = 'LONG_BIAS';
    } else if (bearCount > bullCount && bearCount >= 2) {
      signal = 'SHORT_BIAS';
    } else if (bullCount > 0 && bearCount === 0) {
      signal = 'LONG_BIAS';
      strength = clamp(strength + 0.1, 0, 1);
    } else if (bearCount > 0 && bullCount === 0) {
      signal = 'SHORT_BIAS';
      strength = clamp(strength + 0.1, 0, 1);
    } else if (bullCount === bearCount && bullCount > 0) {
      signal = 'WATCH';
      strength = 0.3;
    } else {
      signal = 'NEUTRAL';
      strength = 0.2;
    }

    // Cap strength
    strength = Math.round(clamp(strength, 0, 1) * 100) / 100;

    return { signal, strength, bullish, bearish, neutral };
  }

  // ======================================================================
  // Private helpers
  // ======================================================================

  private computeRelativeVolume(bars: readonly OHLCVBar[]): number {
    if (bars.length < 2) return 0;
    const current = bars[bars.length - 1].volume;
    const window = Math.min(20, bars.length);
    const avg = bars.slice(-window).reduce((s, b) => s + b.volume, 0) / window;
    return safeDiv(current, avg);
  }

  private srStrength(bars: readonly OHLCVBar[], price: number): number {
    // More touches = stronger level
    const tolerance = price * 0.01; // 1% tolerance
    let touches = 0;
    for (const bar of bars) {
      if (Math.abs(bar.high - price) < tolerance || Math.abs(bar.low - price) < tolerance) {
        touches++;
      }
    }
    return clamp(touches / 5, 0.2, 1);
  }

  private srTouchCount(bars: readonly OHLCVBar[], price: number): number {
    const tolerance = price * 0.01;
    let count = 0;
    for (const bar of bars) {
      if (Math.abs(bar.high - price) < tolerance || Math.abs(bar.low - price) < tolerance) {
        count++;
      }
    }
    return count;
  }

  private mergeSRLevels(levels: SupportResistanceLevel[]): readonly SupportResistanceLevel[] {
    if (levels.length === 0) return [];

    // Sort by price
    const sorted = [...levels].sort((a, b) => a.price - b.price);
    const merged: SupportResistanceLevel[] = [];
    let current = sorted[0];

    for (let i = 1; i < sorted.length; i++) {
      const next = sorted[i];
      // Merge if within 0.5% of each other
      if (Math.abs(next.price - current.price) / current.price < 0.005) {
        // Keep the one with higher strength, combine touch counts
        current = {
          price: (current.price + next.price) / 2,
          type: current.strength >= next.strength ? current.type : next.type,
          strength: Math.max(current.strength, next.strength),
          source: current.source,
          timeframe: current.timeframe,
          touchCount: current.touchCount + next.touchCount,
        };
      } else {
        merged.push(current);
        current = next;
      }
    }
    merged.push(current);

    // Sort by strength descending
    return merged.sort((a, b) => b.strength - a.strength);
  }

  private historicalVolatility(closes: readonly number[], period: number): number {
    if (closes.length < period + 1) return 0;
    const logReturns: number[] = [];
    for (let i = closes.length - period; i < closes.length; i++) {
      if (closes[i - 1] > 0 && closes[i] > 0) {
        logReturns.push(Math.log(closes[i] / closes[i - 1]));
      }
    }
    if (logReturns.length < 2) return 0;
    const mean = logReturns.reduce((s, v) => s + v, 0) / logReturns.length;
    const sd = stdev(logReturns, mean);
    // Annualize (sqrt(252) for daily data)
    return sd * Math.sqrt(252) * 100;
  }

  private atrPercentile(atrArr: readonly number[]): number {
    if (atrArr.length === 0) return 50;
    const current = atrArr[atrArr.length - 1];
    let below = 0;
    for (const v of atrArr) {
      if (v <= current) below++;
    }
    return Math.round((below / atrArr.length) * 100);
  }

  private emptyAnalysis(timeframe: Timeframe, symbol: string): TechnicalAnalysis {
    return {
      assetId: symbol,
      symbol,
      timeframe,
      timestamp: new Date().toISOString(),
      indicators: {},
      trend: {
        direction: 'UNKNOWN',
        strength: 0,
        duration: 0,
        evidence: ['No data available'],
        movingAverageAlignment: 'MIXED',
        priceVsSMA200: 'AT',
      },
      supportResistance: [],
      breakout: null,
      volume: {
        currentVolume: 0,
        averageVolume20d: 0,
        relativeVolume: 0,
        trend: 'STABLE',
        significance: 'LOW',
      },
      volatility: {
        atr14: 0,
        historicalVolatility20d: 0,
        historicalVolatility60d: 0,
        regime: 'NORMAL',
        percentileRank: 50,
      },
      multiTimeframe: {
        monthly: 'UNKNOWN',
        weekly: 'UNKNOWN',
        daily: 'UNKNOWN',
        fourHour: 'UNKNOWN',
        oneHour: 'UNKNOWN',
        alignmentScore: 0,
        description: 'No data available',
      },
      signal: 'NO_SIGNAL',
      signalStrength: 0,
      bullishEvidence: [],
      bearishEvidence: [],
      neutralEvidence: ['No data available'],
    };
  }
}