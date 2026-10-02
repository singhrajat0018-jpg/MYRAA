// ============================================================================
// MYRAA Phase 26 — Market Data Provider & Normalizer
// ============================================================================

import type {
  MarketSnapshot,
  OHLCVBar,
  FinancialMetrics,
  NewsItem,
  Timeframe,
  Exchange,
  Currency,
  Freshness,
  DataQuality,
  DataAdjustment,
} from './contracts';

const FRESHNESS_ORDER: readonly Freshness[] = [
  'REALTIME',
  'NEAR_REALTIME',
  'DELAYED',
  'END_OF_DAY',
  'HISTORICAL',
  'STALE',
  'UNAVAILABLE',
];

const FRESHNESS_MAX_AGE_MS: Record<Freshness, number> = {
  REALTIME: 30_000,
  NEAR_REALTIME: 60_000,
  DELAYED: 300_000,
  END_OF_DAY: 86_400_000,
  HISTORICAL: Infinity,
  STALE: Infinity,
  UNAVAILABLE: 0,
};

const EXCHANGE_CURRENCY_MAP: Record<Exchange, Currency> = {
  NSE: 'INR',
  BSE: 'INR',
  NYSE: 'USD',
  NASDAQ: 'USD',
  LSE: 'GBP',
  TSE: 'JPY',
  HKEX: 'CNY',
  SSE: 'CNY',
  SZSE: 'CNY',
  KRX: 'OTHER',
  ASX: 'AUD',
  TSX: 'CAD',
  CRYPTO_BINANCE: 'USD',
  CRYPTO_COINBASE: 'USD',
  FOREX: 'USD',
  COMEX: 'USD',
  CBOT: 'USD',
  NYMEX: 'USD',
  OTHER: 'USD',
};

function nowIso(): string {
  return new Date().toISOString();
}

function parseTimestamp(ts: string): number {
  const ms = new Date(ts).getTime();
  return isNaN(ms) ? 0 : ms;
}

export class MarketDataProvider {
  private readonly source: string;

  constructor(source: string = 'MARKET_DATA_PROVIDER') {
    this.source = source;
  }

  async getQuote(symbol: string): Promise<MarketSnapshot | null> {
    void symbol;
    return null;
  }

  async getBatchQuotes(symbols: readonly string[]): Promise<readonly MarketSnapshot[]> {
    void symbols;
    return [];
  }

  async getHistoricalBars(
    symbol: string,
    timeframe: Timeframe,
    count: number,
  ): Promise<readonly OHLCVBar[]> {
    void symbol;
    void timeframe;
    void count;
    return [];
  }

  async getFinancialMetrics(symbol: string): Promise<FinancialMetrics | null> {
    void symbol;
    return null;
  }

  async getNews(symbol: string, limit: number): Promise<readonly NewsItem[]> {
    void symbol;
    void limit;
    return [];
  }

  assessFreshness(snapshot: MarketSnapshot): Freshness {
    const ageMs = Date.now() - parseTimestamp(snapshot.timestamp);

    if (ageMs < 0 || snapshot.freshness === 'UNAVAILABLE') {
      return 'UNAVAILABLE';
    }

    if (ageMs <= FRESHNESS_MAX_AGE_MS.REALTIME) return 'REALTIME';
    if (ageMs <= FRESHNESS_MAX_AGE_MS.NEAR_REALTIME) return 'NEAR_REALTIME';
    if (ageMs <= FRESHNESS_MAX_AGE_MS.DELAYED) return 'DELAYED';
    if (ageMs <= FRESHNESS_MAX_AGE_MS.END_OF_DAY) return 'END_OF_DAY';
    if (snapshot.freshness === 'HISTORICAL') return 'HISTORICAL';

    return 'STALE';
  }

  isStale(snapshot: MarketSnapshot, maxAgeMs: number): boolean {
    const ageMs = Date.now() - parseTimestamp(snapshot.timestamp);
    return ageMs > maxAgeMs;
  }
}

export class MarketDataNormalizer {
  normalizeSymbol(symbol: string, exchange?: Exchange): string {
    const cleaned = symbol.trim().toUpperCase();

    if (exchange) {
      const exchangeSuffix = this.exchangeSuffix(exchange);
      if (exchangeSuffix && !cleaned.endsWith(exchangeSuffix)) {
        return `${cleaned}.${exchangeSuffix}`;
      }
    }

    return cleaned;
  }

  normalizePrice(price: number, fromCurrency: Currency, toCurrency: Currency): number {
    if (fromCurrency === toCurrency) return price;
    if (price < 0 || !isFinite(price)) return 0;
    return price;
  }

  validateOHLCV(bar: OHLCVBar): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (bar.open <= 0) errors.push(`Invalid open price: ${bar.open}`);
    if (bar.high <= 0) errors.push(`Invalid high price: ${bar.high}`);
    if (bar.low <= 0) errors.push(`Invalid low price: ${bar.low}`);
    if (bar.close <= 0) errors.push(`Invalid close price: ${bar.close}`);
    if (bar.volume < 0) errors.push(`Invalid volume: ${bar.volume}`);

    if (bar.high < bar.low) {
      errors.push(`High (${bar.high}) is less than low (${bar.low})`);
    }
    if (bar.open > bar.high) {
      errors.push(`Open (${bar.open}) exceeds high (${bar.high})`);
    }
    if (bar.open < bar.low) {
      errors.push(`Open (${bar.open}) is below low (${bar.low})`);
    }
    if (bar.close > bar.high) {
      errors.push(`Close (${bar.close}) exceeds high (${bar.high})`);
    }
    if (bar.close < bar.low) {
      errors.push(`Close (${bar.close}) is below low (${bar.low})`);
    }

    if (!bar.timestamp) {
      errors.push('Missing timestamp');
    } else {
      const ts = parseTimestamp(bar.timestamp);
      if (ts === 0) {
        errors.push('Invalid timestamp format');
      } else if (ts > Date.now() + 86_400_000) {
        errors.push('Timestamp is in the future');
      }
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  adjustForSplits(
    bars: readonly OHLCVBar[],
    events: readonly { date: string; ratio: number }[],
  ): readonly OHLCVBar[] {
    if (events.length === 0) return bars;

    const sortedEvents = [...events].sort(
      (a, b) => parseTimestamp(b.date) - parseTimestamp(a.date),
    );

    let cumulativeRatio = 1;
    const adjusted: OHLCVBar[] = [];

    for (const bar of bars) {
      const barDate = parseTimestamp(bar.timestamp);

      for (const event of sortedEvents) {
        const eventDate = parseTimestamp(event.date);
        if (barDate < eventDate) {
          cumulativeRatio *= event.ratio;
        }
      }

      adjusted.push({
        ...bar,
        open: bar.open * cumulativeRatio,
        high: bar.high * cumulativeRatio,
        low: bar.low * cumulativeRatio,
        close: bar.close * cumulativeRatio,
        volume: Math.round(bar.volume / cumulativeRatio),
        adjustment: 'ADJUSTED' as DataAdjustment,
      });
    }

    return adjusted;
  }

  detectDataQuality(bars: readonly OHLCVBar[]): DataQuality {
    if (bars.length === 0) return 'UNKNOWN';

    let validCount = 0;
    let missingVolume = 0;
    let zeroPrice = 0;

    for (const bar of bars) {
      const validation = this.validateOHLCV(bar);
      if (validation.valid) {
        validCount++;
      }
      if (bar.volume === 0) missingVolume++;
      if (bar.open === 0 || bar.close === 0) zeroPrice++;
    }

    const totalBars = bars.length;
    const validRatio = validCount / totalBars;
    const missingRatio = missingVolume / totalBars;

    if (validRatio >= 0.95 && missingRatio < 0.05) return 'COMPLETE';
    if (validRatio >= 0.8 && missingRatio < 0.15) return 'PARTIAL';
    if (validRatio >= 0.5) return 'SPARSE';
    return 'UNKNOWN';
  }

  detectAnomalies(bars: readonly OHLCVBar[]): readonly string[] {
    const anomalies: string[] = [];

    for (let i = 0; i < bars.length; i++) {
      const bar = bars[i];
      const validation = this.validateOHLCV(bar);
      if (!validation.valid) {
        anomalies.push(`Bar ${i} (${bar.timestamp}): ${validation.errors.join('; ')}`);
      }

      const range = bar.high - bar.low;
      if (bar.open > 0 && range / bar.open > 0.5) {
        anomalies.push(
          `Bar ${i} (${bar.timestamp}): Extreme range ${(range / bar.open * 100).toFixed(1)}% of open`,
        );
      }

      if (i > 0) {
        const prev = bars[i - 1];
        if (prev.close > 0) {
          const gap = Math.abs(bar.open - prev.close) / prev.close;
          if (gap > 0.1) {
            anomalies.push(
              `Bar ${i} (${bar.timestamp}): Gap of ${(gap * 100).toFixed(1)}% from previous close`,
            );
          }
        }
      }

      if (bar.volume === 0 && i > 0 && bars[i - 1].volume > 0) {
        anomalies.push(
          `Bar ${i} (${bar.timestamp}): Zero volume after non-zero volume`,
        );
      }

      if (i > 2) {
        const recentAvgVolume =
          (bars[i - 1].volume + bars[i - 2].volume + (i > 3 ? bars[i - 3].volume : 0)) /
          (i > 3 ? 3 : 2);
        if (recentAvgVolume > 0 && bar.volume / recentAvgVolume > 10) {
          anomalies.push(
            `Bar ${i} (${bar.timestamp}): Volume spike ${(bar.volume / recentAvgVolume).toFixed(1)}x average`,
          );
        }
      }
    }

    return anomalies;
  }

  private exchangeSuffix(exchange: Exchange): string {
    const suffixes: Partial<Record<Exchange, string>> = {
      NSE: 'NS',
      BSE: 'BO',
      NYSE: '',
      NASDAQ: '',
      LSE: 'L',
      TSE: 'T',
    };
    return suffixes[exchange] ?? '';
  }
}
