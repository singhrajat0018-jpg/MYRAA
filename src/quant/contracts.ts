export interface CostModel {
  slippageBps: number;
  commissionPct: number;
}

export interface StrategyInstance {
  id?: string;
  name?: string;
  definitionId?: string;
  version?: string;
  params?: Record<string, any>;
  parameters?: Record<string, any>;
  [key: string]: any;
}

export interface MonteCarloConfig {
  simulations: number;
  confidenceInterval: number;
}

export interface ForecastRecord {
  id: string;
  symbol: string;
  forecast: string;
  timestamp: number;
}

export interface ForecastOutcome {
  recordId: string;
  actual: string;
  correct: boolean;
}

export interface EventStudyEntry {
  event: string;
  date: string;
  impact: number;
}
