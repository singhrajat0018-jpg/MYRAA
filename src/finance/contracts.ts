export type Timeframe = "1m" | "5m" | "15m" | "1h" | "1d";
export type TimeHorizon = "INTRADAY" | "SWING" | "POSITION";
export type StrategyType = "TREND_FOLLOWING" | "MEAN_REVERSION" | "BREAKOUT";

export interface OHLCVBar {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MarketSnapshot {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
}

export interface FinancialMetrics {
  pe: number;
  pb: number;
  roe: number;
  marketCap: number;
}

export interface NewsItem {
  id: string;
  headline: string;
  sentiment: number;
}

export interface Catalyst {
  id: string;
  type: string;
  description: string;
}

export interface AssetIdentity {
  symbol: string;
  name: string;
  exchange: string;
}

export interface ScreenFilter {
  field: string;
  operator: string;
  value: any;
}

export interface WatchlistItem {
  symbol?: string;
  addedAt?: number;
  [key: string]: any;
}

export interface AlertRule {
  id: string;
  condition: string;
}

export interface TradingThesis {
  id?: string;
  symbol?: string;
  hypothesis?: string;
  [key: string]: any;
}

export interface RiskAssessment {
  riskScore: number;
  maxDrawdown: number;
  volatility: number;
}
