// ============================================================================
// MYRAA Phase 27 — Quantitative Research Engine (Barrel Export)
// ============================================================================

export * from './contracts';
export { HistoricalDatasetEngine } from './historical_dataset';
export { StrategyRegistry } from './strategy';
export type { StrategyFunction } from './strategy';
export { BacktestEngine } from './backtest';
export { CostEngine } from './costs';
export { MetricsEngine } from './metrics';
export { WalkForwardEngine } from './walkforward';
export { SensitivityEngine } from './sensitivity';
export { MonteCarloEngine } from './monte_carlo';
export { CalibrationEngine } from './calibration';
export { EventStudyEngine } from './event_studies';
export { ExperimentRegistry } from './experiments';
export { PaperTradingEngine } from './paper_trading';
export { ExecutionFirewall, GLOBAL_FIREWALL } from './firewall';
