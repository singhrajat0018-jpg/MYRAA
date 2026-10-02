// ============================================================================
// MYRAA Phase 26 — Financial Screener
// Asset screening against configurable filters with scoring, ranking,
// default strategy presets, validation, and human-readable explanations.
// ============================================================================

import type {
  AssetIdentity,
  MarketSnapshot,
  TechnicalAnalysis,
  FundamentalAnalysis,
  ScreenFilter,
  ScreenResult,
  SignalBias,
  RiskLevel,
  StrategyType,
  MarketRegime,
} from './contracts';

// --- Internal helpers ---

type FilterValue = number | string | readonly (number | string)[];

function extractNumericValue(
  asset: AssetIdentity,
  snapshot: MarketSnapshot | undefined,
  technical: TechnicalAnalysis | undefined,
  fundamental: FundamentalAnalysis | undefined,
  field: string
): number | undefined {
  // Market snapshot fields.
  if (snapshot) {
    switch (field) {
      case 'price': return snapshot.price;
      case 'changePercent': return snapshot.changePercent;
      case 'volume': return snapshot.volume;
      case 'pe': return snapshot.pe;
      case 'eps': return snapshot.eps;
      case 'dividendYield': return snapshot.dividendYield;
      case 'marketCap': return snapshot.marketCap;
      case 'fiftyTwoWeekHigh': return snapshot.fiftyTwoWeekHigh;
      case 'fiftyTwoWeekLow': return snapshot.fiftyTwoWeekLow;
      case 'dayHigh': return snapshot.dayHigh;
      case 'dayLow': return snapshot.dayLow;
    }
  }

  // Technical indicator fields.
  if (technical) {
    const ind = technical.indicators;
    switch (field) {
      case 'rsi14': return ind.rsi14?.value;
      case 'macdHistogram': return ind.macd?.histogram;
      case 'macdLine': return ind.macd?.macd;
      case 'macdSignal': return ind.macd?.signal;
      case 'sma20': return ind.sma20?.value;
      case 'sma50': return ind.sma50?.value;
      case 'sma200': return ind.sma200?.value;
      case 'ema9': return ind.ema9?.value;
      case 'ema21': return ind.ema21?.value;
      case 'ema50': return ind.ema50?.value;
      case 'atr14': return ind.atr14?.value;
      case 'bollingerBandwidth': return ind.bollinger?.bandwidth;
      case 'bollingerUpper': return ind.bollinger?.upper;
      case 'bollingerLower': return ind.bollinger?.lower;
      case 'adx14': return ind.adx14?.value;
      case 'volumeRatio': return ind.volumeRatio;
      case 'relativeVolume': return ind.relativeVolume;
      case 'signalStrength': return technical.signalStrength;
      case 'trendStrength': return technical.trend.strength;
    }
  }

  // Fundamental fields.
  if (fundamental) {
    const m = fundamental.metrics;
    switch (field) {
      case 'revenue': return m.revenue;
      case 'revenueGrowthYoy': return m.revenueGrowthYoy;
      case 'netIncome': return m.netIncome;
      case 'epsActual': return m.eps;
      case 'grossMargin': return m.grossMargin;
      case 'operatingMargin': return m.operatingMargin;
      case 'netMargin': return m.netMargin;
      case 'roe': return m.roe;
      case 'roic': return m.roic;
      case 'debtToEquity': return m.debtToEquity;
      case 'currentRatio': return m.currentRatio;
      case 'freeCashFlow': return m.freeCashFlow;
      case 'forwardPE': return m.forwardPE;
      case 'ps': return m.ps;
      case 'pb': return m.pb;
      case 'evToEbitda': return m.evToEbitda;
      case 'beta': return m.beta;
      case 'qualityScore': return fundamental.qualityScore;
    }
  }

  // Asset identity fields.
  if (field === 'marketCap' && asset.metadata['marketCap'] !== undefined) {
    return typeof asset.metadata['marketCap'] === 'number'
      ? (asset.metadata['marketCap'] as number)
      : undefined;
  }

  return undefined;
}

function extractStringValue(
  asset: AssetIdentity,
  technical: TechnicalAnalysis | undefined,
  fundamental: FundamentalAnalysis | undefined,
  field: string
): string | undefined {
  switch (field) {
    case 'symbol': return asset.symbol;
    case 'exchange': return asset.exchange;
    case 'assetType': return asset.assetType;
    case 'currency': return asset.currency;
    case 'country': return asset.country;
    case 'sector': return asset.sector;
    case 'industry': return asset.industry;
    case 'status': return asset.status;
    case 'signal': return technical?.signal;
    case 'trend': return technical?.trend.direction;
    case 'valuationAssessment': return fundamental?.valuationAssessment;
    case 'growthAssessment': return fundamental?.growthAssessment;
    case 'financialHealth': return fundamental?.financialHealth;
    default: return undefined;
  }
}

function matchesFilter(value: number | string | undefined, filter: ScreenFilter): boolean {
  if (value === undefined) return false;
  const filterVal = filter.value;

  switch (filter.operator) {
    case 'GT':
      return typeof value === 'number' && typeof filterVal === 'number' && value > filterVal;
    case 'LT':
      return typeof value === 'number' && typeof filterVal === 'number' && value < filterVal;
    case 'EQ':
      return value === filterVal;
    case 'GTE':
      return typeof value === 'number' && typeof filterVal === 'number' && value >= filterVal;
    case 'LTE':
      return typeof value === 'number' && typeof filterVal === 'number' && value <= filterVal;
    case 'BETWEEN': {
      if (typeof value !== 'number' || !Array.isArray(filterVal) || filterVal.length < 2) return false;
      const [lo, hi] = filterVal;
      return typeof lo === 'number' && typeof hi === 'number' && value >= lo && value <= hi;
    }
    case 'IN': {
      if (!Array.isArray(filterVal)) return false;
      return filterVal.includes(value);
    }
    case 'CONTAINS': {
      if (typeof value !== 'string' || typeof filterVal !== 'string') return false;
      return value.toLowerCase().includes(filterVal.toLowerCase());
    }
    default:
      return false;
  }
}

// --- Screener class ---

export class FinancialScreener {
  /**
   * Screen a universe of assets against a set of filters.
   * Returns matched assets with scores, ordered by score descending.
   */
  screen(params: {
    readonly universe: readonly AssetIdentity[];
    readonly filters: readonly ScreenFilter[];
    readonly marketData: Map<string, MarketSnapshot>;
    readonly technicals?: Map<string, TechnicalAnalysis>;
    readonly fundamentals?: Map<string, FundamentalAnalysis>;
    readonly limit?: number;
  }): readonly ScreenResult[] {
    const {
      universe,
      filters,
      marketData,
      technicals,
      fundamentals,
      limit = 50,
    } = params;

    const results: ScreenResult[] = [];

    for (const asset of universe) {
      const snapshot = marketData.get(asset.assetId);
      const technical = technicals?.get(asset.assetId);
      const fundamental = fundamentals?.get(asset.assetId);

      const matchedFilters: string[] = [];
      let allMatch = true;

      for (const filter of filters) {
        const passed = this.applyFilter(asset, snapshot, technical, fundamental, filter);
        if (passed) {
          matchedFilters.push(`${filter.field} ${filter.operator} ${filter.value}`);
        } else {
          allMatch = false;
          break;
        }
      }

      if (!allMatch) continue;

      const result: ScreenResult = {
        assetId: asset.assetId,
        symbol: asset.symbol,
        name: asset.name,
        score: 0,
        matchedFilters,
        signal: technical?.signal ?? 'NEUTRAL',
        risk: this.inferRiskLevel(snapshot, technical),
        evidence: matchedFilters,
      };

      results.push(result);
    }

    // Score all results.
    const scored = results.map((r) => {
      const asset = universe.find((a) => a.assetId === r.assetId);
      const snapshot = marketData.get(r.assetId);
      const technical = technicals?.get(r.assetId);
      const fundamental = fundamentals?.get(r.assetId);
      const score = this.scoreCandidate(r);
      return { result: r, score, asset, snapshot, technical, fundamental };
    });

    scored.sort((a, b) => b.score - a.score);

    return scored.slice(0, limit).map((s) => ({
      ...s.result,
      score: s.score,
    }));
  }

  /**
   * Apply a single filter to an asset.
   */
  applyFilter(
    asset: AssetIdentity,
    snapshot: MarketSnapshot | undefined,
    technical: TechnicalAnalysis | undefined,
    fundamental: FundamentalAnalysis | undefined,
    filter: ScreenFilter
  ): boolean {
    // Try numeric extraction first, then string.
    const numVal = extractNumericValue(asset, snapshot, technical, fundamental, filter.field);
    if (numVal !== undefined) {
      return matchesFilter(numVal, filter);
    }

    const strVal = extractStringValue(asset, technical, fundamental, filter.field);
    if (strVal !== undefined) {
      return matchesFilter(strVal, filter);
    }

    // If the field cannot be extracted at all, the filter fails (conservative).
    return false;
  }

  /**
   * Score a candidate based on matched filters and signal alignment.
   * Higher scores are better. Range: [0, 1].
   */
  scoreCandidate(result: ScreenResult, _regime?: MarketRegime): number {
    if (result.matchedFilters.length === 0) return 0;

    // Base score: proportion of matched filters (all matched to get here, so 1.0).
    let score = 0.5;

    // Bonus for signal alignment.
    if (result.signal === 'LONG_BIAS') score += 0.15;
    else if (result.signal === 'SHORT_BIAS') score -= 0.1;
    else if (result.signal === 'NEUTRAL') score += 0.05;

    // Bonus for lower risk.
    if (result.risk === 'LOW') score += 0.15;
    else if (result.risk === 'MEDIUM') score += 0.05;
    else if (result.risk === 'HIGH') score -= 0.1;
    else if (result.risk === 'EXTREME') score -= 0.2;

    // Bonus for more matched filters (broader confluence).
    const filterBonus = Math.min(result.matchedFilters.length * 0.03, 0.2);
    score += filterBonus;

    return Math.max(0, Math.min(1, score));
  }

  /**
   * Build default filters for a given strategy type.
   */
  buildDefaultFilters(strategy: StrategyType): readonly ScreenFilter[] {
    switch (strategy) {
      case 'MOMENTUM':
        return [
          { field: 'changePercent', operator: 'GT', value: 0 },
          { field: 'rsi14', operator: 'BETWEEN', value: [50, 80] },
          { field: 'volumeRatio', operator: 'GT', value: 1.2 },
          { field: 'trendStrength', operator: 'GT', value: 0.5 },
        ];
      case 'TREND':
        return [
          { field: 'trend', operator: 'EQ', value: 'UPTREND' },
          { field: 'sma50', operator: 'GT', value: 0 },
          { field: 'sma200', operator: 'GT', value: 0 },
          { field: 'adx14', operator: 'GT', value: 25 },
        ];
      case 'MEAN_REVERSION':
        return [
          { field: 'rsi14', operator: 'LT', value: 35 },
          { field: 'bollingerBandwidth', operator: 'GT', value: 0 },
          { field: 'price', operator: 'LT', value: 0 }, // placeholder — real uses bollinger lower
        ];
      case 'BREAKOUT':
        return [
          { field: 'volumeRatio', operator: 'GT', value: 2 },
          { field: 'changePercent', operator: 'GT', value: 1 },
          { field: 'trendStrength', operator: 'GT', value: 0.4 },
        ];
      case 'VALUE':
        return [
          { field: 'pe', operator: 'BETWEEN', value: [0, 20] },
          { field: 'pb', operator: 'LT', value: 3 },
          { field: 'dividendYield', operator: 'GT', value: 1 },
        ];
      case 'GROWTH':
        return [
          { field: 'revenueGrowthYoy', operator: 'GT', value: 15 },
          { field: 'epsActual', operator: 'GT', value: 0 },
          { field: 'roe', operator: 'GT', value: 15 },
        ];
      case 'QUALITY':
        return [
          { field: 'roe', operator: 'GT', value: 20 },
          { field: 'debtToEquity', operator: 'LT', value: 1 },
          { field: 'qualityScore', operator: 'GT', value: 70 },
          { field: 'financialHealth', operator: 'IN', value: ['STRONG', 'ADEQUATE'] },
        ];
      case 'RELATIVE_STRENGTH':
        return [
          { field: 'changePercent', operator: 'GT', value: 0 },
          { field: 'signal', operator: 'EQ', value: 'LONG_BIAS' },
          { field: 'volumeRatio', operator: 'GT', value: 1 },
        ];
      case 'EVENT_DRIVEN':
        return [
          { field: 'volumeRatio', operator: 'GT', value: 1.5 },
          { field: 'changePercent', operator: 'GT', value: 2 },
        ];
      case 'MACRO':
        return [
          { field: 'status', operator: 'EQ', value: 'ACTIVE' },
          { field: 'assetType', operator: 'IN', value: ['STOCK', 'ETF'] },
        ];
      default:
        return [];
    }
  }

  /**
   * Validate filter definitions. Returns errors for malformed filters.
   */
  validateFilters(filters: readonly ScreenFilter[]): {
    readonly valid: boolean;
    readonly errors: readonly string[];
  } {
    const errors: string[] = [];

    if (filters.length === 0) {
      errors.push('No filters provided');
      return { valid: false, errors };
    }

    for (let i = 0; i < filters.length; i++) {
      const f = filters[i];
      const field = f.field;
      const op = f.operator;
      const val = f.value;

      if (!field || field.trim().length === 0) {
        errors.push(`Filter[${i}]: empty field name`);
      }

      if (!['GT', 'LT', 'EQ', 'GTE', 'LTE', 'BETWEEN', 'IN', 'CONTAINS'].includes(op)) {
        errors.push(`Filter[${i}]: unknown operator "${op}"`);
      }

      if (op === 'BETWEEN') {
        if (!Array.isArray(val) || val.length !== 2) {
          errors.push(`Filter[${i}]: BETWEEN requires array of exactly 2 values`);
        } else {
          const [lo, hi] = val;
          if (typeof lo !== 'number' || typeof hi !== 'number') {
            errors.push(`Filter[${i}]: BETWEEN values must be numbers`);
          } else if (lo > hi) {
            errors.push(`Filter[${i}]: BETWEEN lower bound (${lo}) > upper bound (${hi})`);
          }
        }
      } else if (op === 'IN') {
        if (!Array.isArray(val) || val.length === 0) {
          errors.push(`Filter[${i}]: IN requires non-empty array`);
        }
      } else if (op === 'CONTAINS') {
        if (typeof val !== 'string') {
          errors.push(`Filter[${i}]: CONTAINS requires a string value`);
        }
      } else {
        if (typeof val !== 'number') {
          errors.push(`Filter[${i}]: operator "${op}" requires a numeric value`);
        }
      }
    }

    return { valid: errors.length === 0, errors };
  }

  /**
   * Explain why an asset matched the screen, in plain language.
   */
  explainResult(result: ScreenResult): string {
    if (result.matchedFilters.length === 0) {
      return `${result.symbol} did not match any filters.`;
    }

    const parts: string[] = [];
    parts.push(`${result.symbol} passed ${result.matchedFilters.length} filter(s):`);
    for (const mf of result.matchedFilters) {
      parts.push(`  - ${mf}`);
    }
    parts.push(`Signal: ${result.signal}, Risk: ${result.risk}`);
    parts.push(`Score: ${result.score.toFixed(3)}`);

    return parts.join('\n');
  }

  // --- Private helpers ---

  private inferRiskLevel(
    snapshot: MarketSnapshot | undefined,
    technical: TechnicalAnalysis | undefined
  ): RiskLevel {
    const vol = technical?.volatility;
    if (vol) {
      if (vol.regime === 'HIGH') return 'HIGH';
      if (vol.regime === 'LOW') return 'LOW';
    }

    if (snapshot) {
      const absChange = Math.abs(snapshot.changePercent);
      if (absChange > 5) return 'HIGH';
      if (absChange > 3) return 'MEDIUM';
    }

    return 'MEDIUM';
  }
}
