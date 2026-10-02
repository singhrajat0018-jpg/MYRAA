export const DEFAULT_SIGNAL_WEIGHTS = { technical: 0.4, fundamental: 0.3, sentiment: 0.3 };
export const TIMEFRAME_HORIZON_MAP = {
  "1m": "INTRADAY",
  "5m": "INTRADAY",
  "15m": "INTRADAY",
  "1h": "SWING",
  "1d": "POSITION",
};

export class TechnicalAnalysisEngine {
  analyze(...args: any[]) { return { rsi: 50, macd: 0, sma20: 100 }; }
}

export class FundamentalAnalysisEngine {
  analyze(...args: any[]) { return { pe: 15, roe: 0.2 }; }
}

export class EventAnalysisEngine {
  analyze(...args: any[]) { return { events: [] }; }
}

export class MarketRegimeEngine {
  detectRegime(...args: any[]) { return "NORMAL"; }
  classifyRegime(...args: any[]) { return { regime: "NORMAL", confidence: 0.85 }; }
}

export class EvidenceMatrixEngine {
  evaluate(...args: any[]) { return { confidence: 0.8 }; }
  buildMatrix(...args: any[]) { return { matrix: [], overallScore: 75 }; }
}

export class SignalEngine {
  generateSignals(...args: any[]) { return []; }
  generate(...args: any[]) { return { signals: [], confidence: 0.8 }; }
}

export class RiskEngine {
  assessRisk(...args: any[]) { return { riskScore: 10, maxDrawdown: 0.05, volatility: 0.15 }; }
  assess(...args: any[]) { return { riskScore: 10, maxDrawdown: 0.05, volatility: 0.15, approved: true }; }
}

export class ScenarioEngine {
  simulate(...args: any[]) { return []; }
  generate(...args: any[]) { return { scenarios: [], baseCase: {} }; }
}

export class ThesisEngine {
  getTheses(...args: any[]) { return []; }
  build(...args: any[]) { return { id: `thesis-${Date.now()}`, status: 'ACTIVE' }; }
}

export class WatchlistEngine {
  getWatchlist(...args: any[]) { return []; }
  addItem(item: any) { return true; }
  removeItem(symbol: string) { return true; }
  prioritize(...args: any[]) { return []; }
  create(...args: any[]) { return { id: `wl-${Date.now()}`, name: 'Default Watchlist' }; }
}

export class HistoricalIntegrityEngine {
  validate(...args: any[]) { return { valid: true }; }
  validateLookAheadBias(...args: any[]) { return { lookAheadBias: false }; }
  validateDataIntegrity(...args: any[]) { return { integrityScore: 1.0, intact: true }; }
}

export class FinancialScreener {
  screen(...args: any[]) { return []; }
}

export class MarketDataNormalizer {
  normalize(data: any) { return data; }
  normalizeSymbol(...args: any[]) { return typeof args[0] === 'string' ? args[0].toUpperCase() : 'UNKNOWN'; }
  validateOHLCV(bars: any[]) { return { valid: true }; }
}
