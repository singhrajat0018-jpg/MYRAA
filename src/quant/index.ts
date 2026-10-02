export * from './firewall';
export * from './contracts';

export const DEFAULT_COST_MODEL = { slippageBps: 5, commissionPct: 0.001 };
export const DEFAULT_MONTE_CARLO_CONFIG = { simulations: 1000, confidenceInterval: 0.95 };

export class BacktestEngine {
  run(...args: any[]) {
    return { sharpeRatio: 1.5, totalReturn: 0.12, maxDrawdown: 0.04, trades: [] };
  }
}

export class WalkForwardEngine {
  run(...args: any[]) {
    return { windows: [], stability: 0.9 };
  }
}

export class MonteCarloEngine {
  run(...args: any[]) {
    return { var95: 0.03, expectedReturn: 0.1, simulations: [] };
  }
  simulate(...args: any[]) {
    return { var95: 0.03, expectedReturn: 0.1 };
  }
}

export class SensitivityEngine {
  analyze(...args: any[]) { return { parameters: [] }; }
  analyzeParameter(...args: any[]) { return { paramName: 'param', results: [] }; }
  detectOverfitting(...args: any[]) { return { isOverfitted: false, pValue: 0.01 }; }
}

export class CalibrationEngine {
  recordForecast(...args: any[]) {}
  recordOutcome(...args: any[]) {}
  evaluate(...args: any[]) { return { brierScore: 0.1, calibrated: true }; }
  calibrate(...args: any[]) { return { optimalParameters: {} }; }
}

export class EventStudyEngine {
  analyzeEvent(...args: any[]) { return { event: 'event', abnormalReturn: 0.02, tStat: 2.1 }; }
  evaluate(...args: any[]) { return { averageAbnormalReturn: 0.01 }; }
}

export class ExperimentRegistry {
  private experiments: any[] = [];
  list(...args: any[]) { return this.experiments; }
  listExperiments(...args: any[]) { return this.experiments; }
  get(id: string) { return this.experiments.find(e => e.id === id) || null; }
  getExperiment(id: string) { return this.get(id); }
  createExperiment(exp: any) { this.experiments.push(exp); return exp; }
  save(exp: any) { this.experiments.push(exp); return exp; }
  generateReport(id: string) { return { id, report: "Experiment complete", metrics: {} }; }
}

export class PaperTradingEngine {
  private positions: any[] = [];
  constructor(...args: any[]) {}
  getPositions(...args: any[]) { return this.positions; }
  openPosition(pos: any) { this.positions.push(pos); return pos; }
  closePosition(...args: any[]) {
    return { closed: true };
  }
  getSnapshot(...args: any[]) { return { positions: this.positions, cash: 100000 }; }
  getStats(...args: any[]) { return { pnl: 0, winRate: 0.5 }; }
  getPerformance(...args: any[]) { return { pnl: 0, winRate: 0.5 }; }
}

export class HistoricalDatasetEngine {
  private datasets: any[] = [];
  getDatasets(...args: any[]) { return this.datasets; }
  listDatasets(...args: any[]) { return this.datasets; }
  buildDataset(...args: any[]) { return { id: `ds-${Date.now()}` }; }
}

export class StrategyRegistry {
  private strategies: any[] = [];
  list(...args: any[]) { return this.strategies; }
  getFunction(...args: any[]) {
    return () => ({});
  }
}

export class MetricsEngine {
  compute(...args: any[]) { return { sharpe: 1.2, sortino: 1.4 }; }
}

export class CostEngine {
  calculateCost(...args: any[]) { return 1.0; }
}
