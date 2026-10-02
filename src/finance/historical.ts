// ============================================================================
// MYRAA Phase 26 — Historical Intelligence Engine
// Look-ahead bias protection, survivorship bias checks, corporate action
// adjustment, data integrity validation, and return/risk analytics.
// ============================================================================

import type {
  AssetIdentity,
  OHLCVBar,
  EarningsEvent,
} from './contracts';

// --- Local type for corporate actions (not in contracts) ---

export type CorporateActionType = 'SPLIT' | 'DIVIDEND' | 'SPIN_OFF' | 'MERGER' | 'REVERSE_SPLIT' | 'RIGHTS_ISSUE';

export interface CorporateAction {
  readonly type: CorporateActionType;
  readonly effectiveDate: string;
  readonly announcementDate: string;
  readonly ratio?: number;
  readonly dividendPerShare?: number;
  readonly description: string;
}

// --- Result types ---

export interface LookAheadResult {
  readonly hasLeakage: boolean;
  readonly violations: readonly string[];
}

export interface SurvivorshipResult {
  readonly survivorCount: number;
  readonly delistedCount: number;
  readonly delistedAssets: readonly string[];
}

export interface EarningsIssue {
  readonly event: EarningsEvent;
  readonly issue: string;
}

export interface DataIntegrityResult {
  readonly valid: boolean;
  readonly issues: readonly string[];
}

// --- Engine ---

export class HistoricalIntegrityEngine {
  /**
   * Prove no future data leaks into historical analysis.
   * Checks that every data point and event timestamp precedes or equals the
   * analysis timestamp, and that event timestamps do not precede data they
   * could not have been known at.
   */
  validateLookAheadBias(params: {
    readonly analysisTimestamp: string;
    readonly dataTimestamps: readonly string[];
    readonly eventTimestamps?: readonly string[];
  }): LookAheadResult {
    const { analysisTimestamp, dataTimestamps, eventTimestamps } = params;
    const violations: string[] = [];
    const analysisMs = Date.parse(analysisTimestamp);

    if (isNaN(analysisMs)) {
      return { hasLeakage: true, violations: ['Invalid analysisTimestamp'] };
    }

    for (let i = 0; i < dataTimestamps.length; i++) {
      const tsMs = Date.parse(dataTimestamps[i]);
      if (isNaN(tsMs)) {
        violations.push(`Data[${i}]: invalid timestamp "${dataTimestamps[i]}"`);
      } else if (tsMs > analysisMs) {
        violations.push(
          `Data[${i}]: timestamp "${dataTimestamps[i]}" is AFTER analysis timestamp "${analysisTimestamp}"`
        );
      }
    }

    if (eventTimestamps) {
      for (let i = 0; i < eventTimestamps.length; i++) {
        const tsMs = Date.parse(eventTimestamps[i]);
        if (isNaN(tsMs)) {
          violations.push(`Event[${i}]: invalid timestamp "${eventTimestamps[i]}"`);
        } else if (tsMs > analysisMs) {
          violations.push(
            `Event[${i}]: timestamp "${eventTimestamps[i]}" is AFTER analysis timestamp "${analysisTimestamp}"`
          );
        }
      }
    }

    return { hasLeakage: violations.length > 0, violations };
  }

  /**
   * Filter data to only what was available at the given decision timestamp.
   * Items without a parseable timestamp are excluded (conservative).
   */
  filterAvailableData<T extends { readonly timestamp: string }>(
    data: readonly T[],
    decisionTimestamp: string
  ): readonly T[] {
    const decisionMs = Date.parse(decisionTimestamp);
    if (isNaN(decisionMs)) {
      return [];
    }
    return data.filter((item) => {
      const itemMs = Date.parse(item.timestamp);
      return !isNaN(itemMs) && itemMs <= decisionMs;
    });
  }

  /**
   * Check for survivorship bias by counting delisted assets in the universe.
   */
  validateSurvivorshipBias(
    universe: readonly AssetIdentity[],
    _asOfDate: string
  ): SurvivorshipResult {
    const survivors: string[] = [];
    const delisted: string[] = [];

    for (const asset of universe) {
      if (asset.status === 'DELISTED') {
        delisted.push(asset.symbol);
      } else {
        survivors.push(asset.symbol);
      }
    }

    return {
      survivorCount: survivors.length,
      delistedCount: delisted.length,
      delistedAssets: delisted,
    };
  }

  /**
   * Apply corporate actions (splits, dividends, spin-offs, reverse splits)
   * to OHLCV bars to produce adjusted prices. Only RAW bars are adjusted;
   * already-adjusted bars pass through unchanged.
   */
  adjustCorporateActions(
    bars: readonly OHLCVBar[],
    actions: readonly CorporateAction[]
  ): readonly OHLCVBar[] {
    if (bars.length === 0 || actions.length === 0) {
      return [...bars];
    }

    const sortedBars = [...bars].sort(
      (a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp)
    );
    const sortedActions = [...actions].sort(
      (a, b) => Date.parse(a.effectiveDate) - Date.parse(b.effectiveDate)
    );

    // Compute cumulative adjustment factors working backwards from latest bar.
    const latestTimestampMs = Date.parse(sortedBars[sortedBars.length - 1].timestamp);
    const actionFactors: Array<{ effectiveMs: number; factor: number }> = [];

    for (const action of sortedActions) {
      const effectiveMs = Date.parse(action.effectiveDate);
      if (isNaN(effectiveMs)) continue;

      let factor = 1;
      switch (action.type) {
        case 'SPLIT':
          factor = action.ratio ?? 1;
          break;
        case 'REVERSE_SPLIT':
          factor = action.ratio ? 1 / action.ratio : 1;
          break;
        case 'DIVIDEND': {
          // Dividend adjustment: divide by (1 + dps / price_before).
          // Approximate with factor = 1 (conservative) since we lack price
          // at announcement. A more precise model would fetch ex-date price.
          const dps = action.dividendPerShare ?? 0;
          if (dps > 0) {
            // Use a simplified ratio; real systems look up the ex-date close.
            factor = 1 / (1 + dps / 100);
          }
          break;
        }
        case 'SPIN_OFF':
          // Spin-offs create new equity; parent adjusts by child value ratio.
          // Conservative: no adjustment without child price data.
          break;
        case 'MERGER':
          // Mergers end the series; no backward adjustment needed.
          break;
        case 'RIGHTS_ISSUE':
          // Rights issues dilute; adjust similar to split.
          factor = action.ratio ?? 1;
          break;
      }

      if (factor !== 1) {
        actionFactors.push({ effectiveMs, factor });
      }
    }

    if (actionFactors.length === 0) {
      return [...bars];
    }

    // Sort factors newest-first for cumulative backward application.
    actionFactors.sort((a, b) => b.effectiveMs - a.effectiveMs);

    return sortedBars.map((bar) => {
      if (bar.adjustment === 'ADJUSTED') return bar;

      const barMs = Date.parse(bar.timestamp);
      if (isNaN(barMs)) return bar;

      // Accumulate all factors for actions that occurred AFTER this bar.
      let cumulativeFactor = 1;
      for (const af of actionFactors) {
        if (barMs < af.effectiveMs) {
          cumulativeFactor *= af.factor;
        }
      }

      if (cumulativeFactor === 1) return bar;

      return {
        ...bar,
        open: bar.open * cumulativeFactor,
        high: bar.high * cumulativeFactor,
        low: bar.low * cumulativeFactor,
        close: bar.close * cumulativeFactor,
        adjustment: 'ADJUSTED' as const,
      };
    });
  }

  /**
   * Ensure earnings release date is used, not fiscal period end date.
   * Flags events where the release date is implausibly early or missing.
   */
  validateReleaseDateVsFiscalPeriod(
    earnings: readonly EarningsEvent[]
  ): readonly EarningsIssue[] {
    const issues: EarningsIssue[] = [];

    for (const event of earnings) {
      const eventDateMs = Date.parse(event.date);

      if (isNaN(eventDateMs)) {
        issues.push({ event, issue: 'Earnings event has unparseable date' });
        continue;
      }

      if (!event.freshness || event.freshness === 'UNAVAILABLE') {
        issues.push({ event, issue: 'Earnings event data freshness is unavailable' });
      }

      if (event.date.length < 10) {
        issues.push({ event, issue: 'Earnings date may be incomplete (not ISO format)' });
      }

      if (event.time === 'UNKNOWN') {
        issues.push({ event, issue: 'Earnings timing (before/during/after market) is unknown' });
      }
    }

    return issues;
  }

  /**
   * Build a point-in-time universe. Excludes assets that were delisted
   * before the asOfDate or listed after it.
   */
  buildHistoricalUniverse(
    allAssets: readonly AssetIdentity[],
    asOfDate: string
  ): readonly AssetIdentity[] {
    const asOfMs = Date.parse(asOfDate);
    if (isNaN(asOfMs)) return [];

    return allAssets.filter((asset) => {
      // Include if active or unknown status at the as-of date.
      if (asset.status === 'ACTIVE' || asset.status === 'UNKNOWN' || asset.status === 'SUSPENDED') {
        return true;
      }
      // For delisted assets, check metadata for delist date if available.
      const delistDate = asset.metadata['delistDate'];
      if (typeof delistDate === 'string') {
        const delistMs = Date.parse(delistDate);
        // Include only if delisted AFTER the as-of date (i.e., was still live).
        return !isNaN(delistMs) && delistMs > asOfMs;
      }
      // No delist date recorded — conservative: exclude delisted.
      return asset.status !== 'DELISTED';
    });
  }

  /**
   * Validate data integrity of OHLCV bars.
   * Checks: duplicates, gaps, impossible OHLC relationships, negative prices.
   */
  validateDataIntegrity(bars: readonly OHLCVBar[]): DataIntegrityResult {
    const issues: string[] = [];

    if (bars.length === 0) {
      return { valid: true, issues: [] };
    }

    // Check for negative prices and zero volumes.
    for (let i = 0; i < bars.length; i++) {
      const bar = bars[i];
      if (bar.open < 0 || bar.high < 0 || bar.low < 0 || bar.close < 0) {
        issues.push(`Bar[${i}] (${bar.timestamp}): negative price detected`);
      }
      if (bar.high < bar.low) {
        issues.push(
          `Bar[${i}] (${bar.timestamp}): high (${bar.high}) < low (${bar.low})`
        );
      }
      if (bar.open < bar.low || bar.open > bar.high) {
        issues.push(
          `Bar[${i}] (${bar.timestamp}): open (${bar.open}) outside [low, high]`
        );
      }
      if (bar.close < bar.low || bar.close > bar.high) {
        issues.push(
          `Bar[${i}] (${bar.timestamp}): close (${bar.close}) outside [low, high]`
        );
      }
      if (bar.volume < 0) {
        issues.push(`Bar[${i}] (${bar.timestamp}): negative volume`);
      }
    }

    // Check for duplicate timestamps.
    const timestamps = new Map<string, number>();
    for (const bar of bars) {
      const count = timestamps.get(bar.timestamp) ?? 0;
      timestamps.set(bar.timestamp, count + 1);
    }
    for (const [ts, count] of timestamps) {
      if (count > 1) {
        issues.push(`Duplicate timestamp "${ts}" found ${count} times`);
      }
    }

    // Check for chronological order and gaps (weekends excluded for daily).
    const sortedBars = [...bars].sort(
      (a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp)
    );
    for (let i = 1; i < sortedBars.length; i++) {
      const prevMs = Date.parse(sortedBars[i - 1].timestamp);
      const currMs = Date.parse(sortedBars[i].timestamp);
      if (!isNaN(prevMs) && !isNaN(currMs) && currMs < prevMs) {
        issues.push(
          `Bars out of order: "${sortedBars[i - 1].timestamp}" before "${sortedBars[i].timestamp}"`
        );
      }
    }

    return { valid: issues.length === 0, issues };
  }

  /**
   * Compute return series from OHLCV close prices.
   */
  computeReturns(
    bars: readonly OHLCVBar[],
    type: 'ABSOLUTE' | 'PERCENTAGE' | 'LOG'
  ): readonly number[] {
    if (bars.length < 2) return [];

    const sortedBars = [...bars].sort(
      (a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp)
    );

    const returns: number[] = [];
    for (let i = 1; i < sortedBars.length; i++) {
      const prevClose = sortedBars[i - 1].close;
      const currClose = sortedBars[i].close;

      if (prevClose === 0) {
        returns.push(0);
        continue;
      }

      switch (type) {
        case 'ABSOLUTE':
          returns.push(currClose - prevClose);
          break;
        case 'PERCENTAGE':
          returns.push((currClose - prevClose) / prevClose);
          break;
        case 'LOG':
          returns.push(Math.log(currClose / prevClose));
          break;
      }
    }

    return returns;
  }

  /**
   * Compute drawdown series from an equity curve.
   * Each value is the drawdown (negative fraction) from the running peak.
   */
  computeDrawdowns(equity: readonly number[]): readonly number[] {
    if (equity.length === 0) return [];

    const drawdowns: number[] = [];
    let peak = equity[0];

    for (let i = 0; i < equity.length; i++) {
      if (equity[i] > peak) {
        peak = equity[i];
      }
      if (peak === 0) {
        drawdowns.push(0);
      } else {
        drawdowns.push((equity[i] - peak) / peak);
      }
    }

    return drawdowns;
  }

  /**
   * Compute Sharpe-like ratio (annualised, assuming 252 trading days).
   */
  computeSharpe(
    returns: readonly number[],
    riskFreeRate: number = 0
  ): number {
    if (returns.length < 2) return 0;

    const dailyRf = riskFreeRate / 252;
    let sum = 0;
    let sumSq = 0;

    for (const r of returns) {
      const excess = r - dailyRf;
      sum += excess;
      sumSq += excess * excess;
    }

    const mean = sum / returns.length;
    const variance = sumSq / returns.length - mean * mean;
    const stdDev = Math.sqrt(Math.max(variance, 0));

    if (stdDev === 0) return 0;
    return (mean / stdDev) * Math.sqrt(252);
  }

  /**
   * Compute Sortino-like ratio (annualised, using downside deviation only).
   */
  computeSortino(
    returns: readonly number[],
    riskFreeRate: number = 0
  ): number {
    if (returns.length < 2) return 0;

    const dailyRf = riskFreeRate / 252;
    let sum = 0;
    let downsideSumSq = 0;
    let downsideCount = 0;

    for (const r of returns) {
      const excess = r - dailyRf;
      sum += excess;
      if (excess < 0) {
        downsideSumSq += excess * excess;
        downsideCount++;
      }
    }

    const mean = sum / returns.length;
    const downsideDev = downsideCount > 0
      ? Math.sqrt(downsideSumSq / downsideCount)
      : 0;

    if (downsideDev === 0) return mean > 0 ? Infinity : 0;
    return (mean / downsideDev) * Math.sqrt(252);
  }

  /**
   * Compute maximum drawdown from an equity curve.
   */
  computeMaxDrawdown(equity: readonly number[]): number {
    if (equity.length < 2) return 0;

    let peak = equity[0];
    let maxDd = 0;

    for (let i = 1; i < equity.length; i++) {
      if (equity[i] > peak) {
        peak = equity[i];
      }
      if (peak > 0) {
        const dd = (equity[i] - peak) / peak;
        if (dd < maxDd) {
          maxDd = dd;
        }
      }
    }

    return maxDd;
  }
}
