// ============================================================================
// MYRAA Phase 27 — Quantitative Research & Backtesting Contracts
// ============================================================================
// Data models for strategy evaluation, backtesting, paper simulation,
// forecast calibration, and research experiments.
// NEVER executes trades. All simulations are virtual/paper only.
// ============================================================================

import type {
  OHLCVBar, Timeframe, AssetIdentity, StrategyType, OrderSide,
  OrderIntent, TradingSignal, RiskAssessment, PortfolioPosition,
  SignalBias,
} from '../finance/contracts';

export type {
  OHLCVBar, Timeframe, AssetIdentity, StrategyType, OrderSide,
  OrderIntent, TradingSignal, RiskAssessment, PortfolioPosition,
  SignalBias,
};

// --- Strategy Definition ---

export interface StrategyParameter {
  readonly name: string;
  readonly type: 'number' | 'integer' | 'boolean' | 'string' | 'enum';
  readonly default: number | boolean | string;
  readonly min?: number;
  readonly max?: number;
  readonly step?: number;
  readonly options?: readonly string[];
  readonly description: string;
}

export interface StrategyDefinition {
  readonly id: string;
  readonly name: string;
  readonly version: string;
  readonly description: string;
  readonly type: StrategyType;
  readonly requiredTimeframes: readonly Timeframe[];
  readonly minBars: number;
  readonly parameters: readonly StrategyParameter[];
  readonly riskProfile: {
    readonly suggestedStopAtrMultiple: number;
    readonly suggestedTargetAtrMultiple: number;
    readonly maxHoldingBars?: number;
    readonly positionSizeRule?: 'FIXED_RISK' | 'FIXED_NOTIONAL' | 'KELLY';
  };
}

export interface StrategyInstance {
  readonly definitionId: string;
  readonly version: string;
  readonly params: Record<string, number | boolean | string>;
}

// --- Historical Dataset ---

export type DataSourceQuality = 'PRIMARY' | 'SECONDARY' | 'ESTIMATED' | 'INTERPOLATED';
export type AdjustmentType = 'NONE' | 'SPLIT' | 'DIVIDEND' | 'BOTH';

export interface DatasetSource {
  readonly provider: string;
  readonly quality: DataSourceQuality;
  readonly adjustment: AdjustmentType;
  readonly verified: boolean;
}

export interface HistoricalDataset {
  readonly id: string;
  readonly symbol: string;
  readonly timeframe: Timeframe;
  readonly bars: readonly OHLCVBar[];
  readonly source: DatasetSource;
  readonly startDate: string;
  readonly endDate: string;
  readonly totalBars: number;
  readonly completeness: number;
  readonly hasLookAhead: boolean;
  readonly survivorshipFiltered: boolean;
}

export interface DatasetIntegrityCheck {
  readonly datasetId: string;
  readonly duplicatesRemoved: number;
  readonly gapsDetected: readonly string[];
  readonly impossibleBarsFound: number;
  readonly adjustedBars: number;
  readonly valid: boolean;
  readonly issues: readonly string[];
}

// --- Backtest ---

export type TradeDirection = 'LONG' | 'SHORT';

export interface BacktestTrade {
  readonly tradeId: string;
  readonly symbol: string;
  readonly direction: TradeDirection;
  readonly entryBarIndex: number;
  readonly entryPrice: number;
  readonly entryTimestamp: string;
  readonly exitBarIndex: number;
  readonly exitPrice: number;
  readonly exitTimestamp: string;
  readonly exitReason: 'SIGNAL' | 'STOP' | 'TARGET' | 'TIME_LIMIT' | 'END_OF_DATA';
  readonly quantity: number;
  readonly notional: number;
  readonly pnl: number;
  readonly pnlPercent: number;
  readonly commissions: number;
  readonly slippage: number;
  readonly holdingBars: number;
  readonly riskRewardActual: number;
}

export interface BacktestResult {
  readonly strategy: StrategyInstance;
  readonly datasetId: string;
  readonly symbol: string;
  readonly timeframe: Timeframe;
  readonly periodStart: string;
  readonly periodEnd: string;
  readonly initialCapital: number;
  readonly finalEquity: number;
  readonly equity: readonly number[];
  readonly equityTimestamps: readonly string[];
  readonly trades: readonly BacktestTrade[];
  readonly metrics: PerformanceMetrics;
  readonly totalBars: number;
  readonly costsApplied: CostSummary;
  readonly timestamp: string;
}

export interface PerformanceMetrics {
  readonly totalReturn: number;
  readonly annualizedReturn: number;
  readonly sharpeRatio: number;
  readonly sortinoRatio: number;
  readonly calmarRatio: number;
  readonly maxDrawdown: number;
  readonly maxDrawdownDuration: number;
  readonly volatility: number;
  readonly downsideVolatility: number;
  readonly winRate: number;
  readonly avgWin: number;
  readonly avgLoss: number;
  readonly profitFactor: number;
  readonly expectancy: number;
  readonly totalTrades: number;
  readonly avgHoldingBars: number;
  readonly bestTrade: number;
  readonly worstTrade: number;
  readonly avgTrade: number;
  readonly consecutiveWins: number;
  readonly consecutiveLosses: number;
  readonly longTrades: number;
  readonly shortTrades: number;
  readonly longWinRate: number;
  readonly shortWinRate: number;
  readonly skewness: number;
  readonly kurtosis: number;
  readonly tailRatio: number;
  readonly commonReturn: number;
  readonly benchmarkReturn?: number;
  readonly alpha?: number;
  readonly beta?: number;
  readonly informationRatio?: number;
}

// --- Cost Model ---

export interface CostModel {
  readonly commissionPerTrade: number;
  readonly commissionPerShare: number;
  readonly commissionPercent: number;
  readonly slippageTicks: number;
  readonly slippageBps: number;
  readonly marketImpactModel: 'NONE' | 'LINEAR' | 'SQRT';
  readonly marketImpactCoeff: number;
  readonly borrowCostAnnualBps?: number;
  readonly spreadBps: number;
}

export interface CostSummary {
  readonly totalCommissions: number;
  readonly totalSlippage: number;
  readonly totalMarketImpact: number;
  readonly totalCosts: number;
  readonly costPerTrade: number;
  readonly costAsPercentOfVolume: number;
}

// --- Walk-Forward ---

export interface WalkForwardWindow {
  readonly windowIndex: number;
  readonly trainStart: string;
  readonly trainEnd: string;
  readonly testStart: string;
  readonly testEnd: string;
  readonly trainBars: number;
  readonly testBars: number;
}

export interface WalkForwardOptimization {
  readonly bestParams: Record<string, number | boolean | string>;
  readonly trainMetrics: PerformanceMetrics;
  readonly testMetrics: PerformanceMetrics;
  readonly window: WalkForwardWindow;
}

export interface WalkForwardResult {
  readonly strategy: StrategyInstance;
  readonly datasetId: string;
  readonly windows: readonly WalkForwardOptimization[];
  readonly overallTestMetrics: PerformanceMetrics;
  readonly overallTrainMetrics: PerformanceMetrics;
  readonly parameterStability: number;
  readonly overfittingScore: number;
  readonly totalTrainBars: number;
  readonly totalTestBars: number;
  readonly timestamp: string;
}

// --- Monte Carlo ---

export interface MonteCarloConfig {
  readonly simulations: number;
  readonly periodsPerSim: number;
  readonly seed: number;
  readonly bootstrapMethod: 'BLOCK' | 'iid';
  readonly blockSize?: number;
  readonly confidenceLevel: number;
}

export interface MonteCarloResult {
  readonly strategy: StrategyInstance;
  readonly config: MonteCarloConfig;
  readonly simulations: number;
  readonly paths: readonly number[][];
  readonly percentiles: {
    readonly p5: number;
    readonly p25: number;
    readonly p50: number;
    readonly p75: number;
    readonly p95: number;
  };
  readonly stats: {
    readonly meanReturn: number;
    readonly medianReturn: number;
    readonly stdReturn: number;
    readonly worstDrawdown: number;
    readonly worstDrawdownProb: number;
    readonly valueAtRisk95: number;
    readonly conditionalVaR95: number;
    readonly probabilityOfLoss: number;
    readonly probabilityOfRuin: number;
    readonly expectedShortfall: number;
  };
  readonly timestamp: string;
}

// --- Sensitivity / Overfitting ---

export interface SensitivityPoint {
  readonly paramName: string;
  readonly paramValue: number;
  readonly metric: number;
  readonly trades: number;
}

export interface SensitivityResult {
  readonly strategy: StrategyInstance;
  readonly paramName: string;
  readonly points: readonly SensitivityPoint[];
  readonly range: { readonly min: number; readonly max: number };
  readonly sensitivity: number;
  readonly isCritical: boolean;
}

export interface OverfittingAnalysis {
  readonly strategy: StrategyInstance;
  readonly inSampleSharpe: number;
  readonly outOfSampleSharpe: number;
  readonly deflatedSharpe: number;
  readonly overfittingProbability: number;
  readonly parameterStability: number;
  readonly isLikelyOverfit: boolean;
  readonly warnings: readonly string[];
}

// --- Forecast Calibration ---

export type ForecastDirection = 'UP' | 'DOWN' | 'FLAT';

export interface ForecastRecord {
  readonly forecastId: string;
  readonly symbol: string;
  readonly timestamp: string;
  readonly direction: ForecastDirection;
  readonly confidence: number;
  readonly horizonBars: number;
  readonly strategyId: string;
  readonly parameters: Record<string, number | boolean | string>;
}

export interface ForecastOutcome {
  readonly forecastId: string;
  readonly symbol: string;
  readonly actualDirection: ForecastDirection;
  readonly actualMovePercent: number;
  readonly evaluationTimestamp: string;
  readonly correct: boolean;
}

export interface CalibrationBin {
  readonly binStart: number;
  readonly binEnd: number;
  readonly binMid: number;
  readonly forecastCount: number;
  readonly avgConfidence: number;
  readonly observedAccuracy: number;
  readonly expectedAccuracy: number;
  readonly miscalibration: number;
}

export interface CalibrationResult {
  readonly strategyId: string;
  readonly totalForecasts: number;
  readonly overallAccuracy: number;
  readonly expectedCalibrationError: number;
  readonly maximumCalibrationError: number;
  readonly brierScore: number;
  readonly logLoss: number;
  readonly bins: readonly CalibrationBin[];
  readonly isWellCalibrated: boolean;
  readonly warnings: readonly string[];
  readonly timestamp: string;
}

// --- Event Studies ---

export interface EventStudyEntry {
  readonly eventId: string;
  readonly symbol: string;
  readonly eventType: string;
  readonly eventTimestamp: string;
  readonly description: string;
}

export interface EventStudyResult {
  readonly eventId: string;
  readonly symbol: string;
  readonly eventType: string;
  readonly eventTimestamp: string;
  readonly carDays: readonly { readonly day: number; readonly car: number }[];
  readonly abnormalReturn: number;
  readonly cumulativeAbnormalReturn: number;
  readonly tStatistic: number;
  readonly significantAtFive: boolean;
  readonly preEventDrift: number;
  readonly postEventDrift: number;
  readonly sampleSize: number;
}

// --- Experiment Registry ---

export type ExperimentStatus = 'PLANNED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface ResearchExperiment {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly strategy: StrategyInstance;
  readonly datasetId: string;
  readonly datasetSymbol: string;
  readonly periodStart: string;
  readonly periodEnd: string;
  readonly costModel: CostModel;
  readonly parameters: Record<string, number | boolean | string>;
  readonly seed: number;
  readonly createdAt: string;
  readonly status: ExperimentStatus;
}

export interface ExperimentResult {
  readonly experiment: ResearchExperiment;
  readonly backtest?: BacktestResult;
  readonly walkForward?: WalkForwardResult;
  readonly monteCarlo?: MonteCarloResult;
  readonly sensitivity?: readonly SensitivityResult[];
  readonly overfitting?: OverfittingAnalysis;
  readonly calibration?: CalibrationResult;
  readonly eventStudies?: readonly EventStudyResult[];
  readonly notes: readonly string[];
  readonly completedAt?: string;
}

// --- Paper Trading Simulation ---

export type PaperPositionStatus = 'OPEN' | 'CLOSED' | 'STOPPED';

export interface PaperPosition {
  readonly positionId: string;
  readonly symbol: string;
  readonly direction: TradeDirection;
  readonly entryPrice: number;
  readonly entryTimestamp: string;
  readonly quantity: number;
  readonly stopLoss?: number;
  readonly takeProfit?: number;
  readonly status: PaperPositionStatus;
  readonly exitPrice?: number;
  readonly exitTimestamp?: string;
  readonly exitReason?: string;
  readonly pnl?: number;
  readonly pnlPercent?: number;
  readonly commissions: number;
  readonly slippage: number;
}

export interface PaperPortfolioSnapshot {
  readonly cash: number;
  readonly positions: readonly PaperPosition[];
  readonly totalEquity: number;
  readonly totalPnl: number;
  readonly totalPnlPercent: number;
  readonly openPositionCount: number;
  readonly timestamp: string;
}

// --- Execution Firewall ---

export type CapabilityClassification = 'READ_MARKET_DATA' | 'SIMULATE_TRADE' | 'EXECUTE_TRADE' | 'TRANSFER_FUNDS';

export interface FirewallDecision {
  readonly allowed: boolean;
  readonly classification: CapabilityClassification;
  readonly reason: string;
  readonly overrideLevel: 'NONE' | 'STRICT' | 'FLEXIBLE';
}

export interface FirewallPolicy {
  readonly liveTradeExecution: boolean;
  readonly transferFunds: boolean;
  readonly simulateTrade: boolean;
  readonly readMarketData: boolean;
  readonly allowLlmOverride: boolean;
}

// --- Research Report ---

export interface ResearchReport {
  readonly reportId: string;
  readonly title: string;
  readonly strategy: StrategyInstance;
  readonly experimentIds: readonly string[];
  readonly datasetId: string;
  readonly periodStart: string;
  readonly periodEnd: string;
  readonly costModel: CostModel;
  readonly backtest?: BacktestResult;
  readonly walkForward?: WalkForwardResult;
  readonly monteCarlo?: MonteCarloResult;
  readonly sensitivity?: readonly SensitivityResult[];
  readonly overfitting?: OverfittingAnalysis;
  readonly calibration?: CalibrationResult;
  readonly summary: string;
  readonly limitations: readonly string[];
  readonly disclaimers: readonly string[];
  readonly generatedAt: string;
}

// --- Defaults ---

export const DEFAULT_COST_MODEL: CostModel = {
  commissionPerTrade: 0.0,
  commissionPerShare: 0.0,
  commissionPercent: 0.001,
  slippageTicks: 1,
  slippageBps: 5,
  marketImpactModel: 'SQRT',
  marketImpactCoeff: 0.1,
  spreadBps: 3,
};

export const STRICT_FIREWALL_POLICY: FirewallPolicy = {
  liveTradeExecution: false,
  transferFunds: false,
  simulateTrade: true,
  readMarketData: true,
  allowLlmOverride: false,
};

export const DEFAULT_MONTE_CARLO_CONFIG: MonteCarloConfig = {
  simulations: 1000,
  periodsPerSim: 252,
  seed: 42,
  bootstrapMethod: 'BLOCK',
  blockSize: 10,
  confidenceLevel: 0.95,
};
