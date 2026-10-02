// ============================================================================
// MYRAA Phase 28 — Continuous Forecast Learning & Strategy Adaptation Contracts
// ============================================================================

// Import base types from existing contracts
import type {
  StrategyType, OHLCVBar,
  SignalBias, TimeHorizon, TradingSignal,
  AssetIdentity, MarketRegime, TechnicalAnalysis,
  FundamentalAnalysis, EventAnalysis, MacroContext,
  RegimeType, RiskLevel
} from '../finance/contracts';

// Re-export base types for downstream consumers
export type { StrategyType, OHLCVBar, SignalBias, TimeHorizon, TradingSignal,
  AssetIdentity, MarketRegime, TechnicalAnalysis,
  FundamentalAnalysis, EventAnalysis, MacroContext,
  RegimeType, RiskLevel } from '../finance/contracts';

export type { StrategyInstance } from '../quant/contracts';

// ============================================================================
// FORECAST LIFECYCLE
// ============================================================================

export type ForecastLifecycleState =
  | 'CREATED'
  | 'ACTIVE'
  | 'AWAITING_OUTCOME'
  | 'PARTIALLY_EVALUATED'
  | 'EVALUATED'
  | 'INVALIDATED'
  | 'EXPIRED'
  | 'DATA_INSUFFICIENT'
  | 'EVALUATION_ERROR';

export type ForecastType =
  | 'DIRECTION'
  | 'RETURN_RANGE'
  | 'PRICE_TARGET'
  | 'VOLATILITY'
  | 'TREND'
  | 'EVENT_IMPACT'
  | 'SCENARIO'
  | 'REGIME';

export interface ForecastHorizon {
  type: TimeHorizon;
  bars: number; // exact number of bars for the horizon
  description: string;
}

export interface EvidenceSnapshot {
  technical: string[];
  fundamental: string[];
  events: string[];
  macro: string[];
  regime: string[];
  sentiment: string[];
  timestamps: Record<string, string>; // source -> timestamp
}

export interface DataSnapshot {
  price: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  technical: TechnicalAnalysis | null;
  fundamental: FundamentalAnalysis | null;
  events: EventAnalysis | null;
  macro: MacroContext | null;
  regime: MarketRegime | null;
  assetId: string;
  symbol: string;
  timestamp: string;
}

export interface StrategySnapshot {
  definitionId: string;
  version: string;
  type: StrategyType;
  parameters: Record<string, number | boolean | string>;
  riskPerTrade?: number;
  stopLossAtrMultiple?: number;
  targetAtrMultiple?: number;
  maxHoldingBars?: number;
}

export interface ModelSnapshot {
  provider: string; // e.g., 'ollama', 'gemini'
  model: string; // e.g., 'qwen3:8b', 'gemini-3.1-flash'
  version: string;
  timestamp: string;
}

// ==////////////////////////////////////////////////
// FORECAST OBJECT
// ============================================================================

export interface Forecast {
  readonly forecastId: string;
  readonly assetId: string;
  readonly symbol: string;
  readonly createdAt: string;
  readonly decisionTimestamp: string; // when the forecast was made
  readonly horizon: ForecastHorizon;
  readonly type: ForecastType;
  readonly prediction: string | number; // varies by type
  readonly predictionDetails?: Record<string, unknown>; // additional details
  readonly confidence: number; // 0-1, confidence in the prediction
  readonly probability?: number; // 0-1, if probabilistic forecast
  readonly probabilityType?: 'FREQUENTIST' | 'BAYESIAN' | 'CONFIDENCE';
  readonly thesisId?: string;
  readonly strategyId: string;
  readonly strategyVersion: string;
  readonly evidenceSnapshot: EvidenceSnapshot;
  readonly dataSnapshot: DataSnapshot;
  readonly strategySnapshot: StrategySnapshot;
  readonly modelSnapshot?: ModelSnapshot;
  readonly researchSnapshot?: Record<string, unknown>;
  readonly regime: RegimeType;
  readonly invalidationConditions: readonly string[];
  readonly status: ForecastLifecycleState;
  readonly evaluationTimestamp?: string;
}

// ============================================================================
// OUTCOME OBJECT
// ============================================================================

export interface ForecastOutcome {
  readonly forecastId: string;
  readonly outcomeTimestamp: string;
  readonly actualValue: string | number; // actual result
  readonly actualReturn?: number; // percentage return if applicable
  readonly actualDirection?: 'UP' | 'DOWN' | 'FLAT';
  readonly directionCorrect?: boolean;
  readonly magnitudeError?: number; // absolute error in prediction
  readonly relativeError?: number; // relative error
  readonly timingError?: number; // bars off from expected timing
  readonly maximumAdverseMove?: number; // max unfavorable move during horizon
  readonly maximumFavorableMove?: number; // max favorable move during horizon
  readonly volatility?: number; // realized volatility
  readonly eventOccurred?: boolean; // if an event was forecasted
  readonly eventImpactActual?: number; // actual impact if event forecasted
  readonly regimeAtOutcome?: RegimeType;
  readonly dataQuality: 'COMPLETE' | 'PARTIAL' | 'SPARSE' | 'UNKNOWN';
  readonly evaluationStatus: 'FINAL' | 'PROVISIONAL' | 'PARTIAL' | 'FAILED';
}

// ============================================================================
// EVALUATION OBJECT
// ============================================================================

export interface ForecastEvaluation {
  readonly forecastId: string;
  readonly evaluationId: string;
  readonly evaluatedAt: string;
  readonly correctness: boolean | null; // true/false/null for non-binary
  readonly error: number | null; // signed error (positive = overprediction)
  readonly absoluteError: number; // magnitude of error
  readonly relativeError: number; // error as fraction of actual
  readonly directionCorrect: boolean | null;
  readonly timingAccuracy: number; // 0-1, how close timing was
  readonly calibrationBucket: number; // 0-10 for binning confidence
  readonly confidenceQuality: number; // 0-1, how well confidence matched outcome
  readonly strategyOutcome: 'SUCCESS' | 'FAILURE' | 'PARTIAL' | 'UNCERTAIN';
  readonly failureCategory:
    | 'TREND_REVERSAL'
    | 'FALSE_BREAKOUT'
    | 'EVENT_MISREAD'
    | 'MACRO_SHOCK'
    | 'REGIME_SHIFT'
    | 'DATA_ERROR'
    | 'TIMING_ERROR'
    | 'LIQUIDITY'
    | 'VOLATILITY'
    | 'THESIS_INVALIDATION'
    | 'UNKNOWN'
    | null;
  readonly supportingEvidence: string[]; // evidence that should have warned
  readonly missedEvidence: string[]; // evidence that existed but was missed
  readonly falseSignals: string[]; // signals that existed but were misleading
  readonly evaluationVersion: string;
  readonly evaluator: 'CONTINUOUS_ENGINE' | 'USER_REQUESTED' | 'RESEARCH_TRIGGER';
}

// ============================================================================
// THESIS LIFECYCLE
// ============================================================================

export type ThesisLifecycleState =
  | 'CREATED'
  | 'ACTIVE'
  | 'SUPPORTED'
  | 'STRESSED'
  | 'INVALIDATED'
  | 'RESOLVED'
  | 'EXPIRED';

export interface ThesisOutcome {
  readonly thesisId: string;
  readonly evaluationTimestamp: string;
  readonly originalThesisSupported: boolean; // did evidence support original thesis?
  readonly bullCaseRealized: boolean;
  readonly bearCaseRealized: boolean;
  readonly baseCaseRealized: boolean;
  readonly keyRisksMaterialized: readonly string[];
  readonly keyCatalystsOccurred: readonly string[];
  readonly keyCatalystsEffective: readonly string[]; // catalysts that actually mattered
  readonly invalidationTimingAccurate: boolean; // did invalidation occur when expected?
  readonly overallAssessment: 'FULLY_SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'NOT_SUPPORTED' | 'INVALIDATED';
  readonly confidenceInAssessment: number; // 0-1
}

// ============================================================================
// STRATEGY HEALTH
// ============================================================================

export type StrategyHealthStatus =
  | 'ACTIVE'
  | 'HEALTHY'
  | 'WATCH'
  | 'DEGRADED'
  | 'UNRELIABLE'
  | 'RESEARCH_ONLY'
  | 'RETIRED';

export interface StrategyHealth {
  readonly strategyId: string;
  readonly strategyVersion: string;
  readonly status: StrategyHealthStatus;
  readonly sampleSize: number;
  readonly recentAccuracy: number; // last N forecasts
  rollingAccuracy: number; // rolling window accuracy
  accuracyTrend: number; // positive = improving, negative = degrading
  averageReturn: number;
  returnVolatility: number;
  maxDrawdown: number;
  sharpeRatio: number;
  sortinoRatio: number;
  calibrationError: number; // ECE or similar
  confidenceQuality: number; // how well confidence predicts outcomes
  regimePerformance: Record<RegimeType, number>; // accuracy by regime
  drawdownByRegime: Record<RegimeType, number>; // drawdown by regime
  lastEvaluatedAt: string;
  evaluationCount: number;
  failureRate: number;
  avgFailureMagnitude: number;
  successStreak: number;
  failureStreak: number;
  dataQualityScore: number; // 0-1, quality of data used
  providerReliability: Record<string, number>; // provider -> reliability score
}

// ============================================================================
// RESEARCH LESSON
// ============================================================================

export interface ResearchLesson {
  readonly lessonId: string;
  readonly source: string; // where lesson came from (forecast, experiment, etc.)
  readonly strategyId: string;
  readonly context: string; // description of when lesson applies
  readonly failureOrSuccess: 'FAILURE' | 'SUCCESS';
  readonly recommendation: string;
  readonly confidence: number; // 0-1, confidence in lesson
  readonly createdAt: string;
  readonly expiresAt?: string;
  readonly regrets?: string[]; // what we wish we had done differently
  readonly applicability: {
    regime?: RegimeType;
    strategyType?: StrategyType;
    horizon?: TimeHorizon;
    volatilityRegime?: 'HIGH' | 'NORMAL' | 'LOW';
  };
}

// ============================================================================
// HYPOTHESIS
// ============================================================================

export type HypothesisStatus =
  | 'PROPOSED'
  | 'TESTING'
  | 'SUPPORTED'
  | 'WEAK'
  | 'REFUTED'
  | 'INCONCLUSIVE';

export interface ResearchHypothesis {
  readonly hypothesisId: string;
  readonly sourceForecastId?: string; // which forecast led to this hypothesis
  readonly description: string;
  readonly rationale: string;
  readonly status: HypothesisStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly evidenceFor: string[]; // evidence supporting hypothesis
  readonly evidenceAgainst: string[]; // evidence contradicting hypothesis
  readonly testablePrediction: string; // what would need to happen to support/refute
  readonly confidence: number; // 0-1, confidence in hypothesis
  readonly experimentId?: string; // linked experiment if being tested
  readonly sampleSize: number;
  readonly pValue?: number; // statistical significance if applicable
}

// ============================================================================
// ADAPTATION PROPOSAL
// ============================================================================

export type AdaptationProposalStatus =
  | 'PROPOSED'
  | 'UNDER_TEST'
  | 'TEST_COMPLETED'
  | 'REJECTED'
  | 'ACCEPTED_AS_CANDIDATE';

export interface StrategyAdaptationProposal {
  readonly proposalId: string;
  readonly currentStrategyId: string;
  readonly currentStrategyVersion: string;
  readonly proposedChanges: Record<string, unknown>; // what to change
  readonly problemStatement: string; // what problem we're trying to solve
  readonly evidence: string[]; // evidence supporting need for change
  readonly reasoning: string; // why we think this change will help
  readonly validationRequired: {
    backtest: boolean;
    walkForward: boolean;
    outOfSample: boolean;
    costSensitivity: boolean;
    regimeRobustness: boolean;
  };
  readonly status: AdaptationProposalStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly championVsChallenger: {
    champion: string; // current strategy being challenged
    challenger: string; // proposed strategy
  } | null;
}

// ============================================================================
// PROVIDER HEALTH
// ============================================================================

export interface FinancialProviderHealth {
  readonly providerId: string;
  readonly providerType: 'PRICE' | 'FUNDAMENTAL' | 'NEWS' | 'EVENT' | 'MACRO';
  readonly freshnessScore: number; // 0-1, how fresh the data is
  readonly availabilityScore: number; // 0-1, % of time data is available
  accuracyScore: number; // 0-1, accuracy when ground truth exists
  latencyScore: number; // 0-1, latency (lower is better, so 1-low latency)
  schemaStabilityScore: number; // 0-1, how stable the data schema is
  conflictRate: number; // how often this provider conflicts with others
  lastUpdated: string;
  sampleSize: number; // number of data points evaluated
  reliabilityScore: number; // 0-1, overall reliability
}

// ============================================================================
// MARKET MATRIX TRACKING
// ============================================================================

export interface StrategyRegimeHorizonMatrix {
  readonly strategyId: string;
  readonly regime: RegimeType;
  readonly horizon: TimeHorizon;
  sampleSize: number;
  accuracy: number;
  averageReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
  calibrationError: number;
}

// ============================================================================
// ATTRIBUTION RESULT
// ============================================================================

export interface PerformanceAttribution {
  readonly strategyId: string;
  readonly period: string;
  readonly totalReturn: number;
  attribution: {
    assetSelection: number; // return from picking good assets
    timing: number; // return from buying/selling at right time
    sector: number; // return from buying/selling at right time
    factor: number; // return from factor exposures (value, momentum, etc.)
    regime: number; // return from being in right regime
    interaction: number; // interaction effects
    unexplained: number; // returns not explained by above
  };
  reconciliationError: number; // should be near 0
  confidence: number; // 0-1, confidence in attribution
}

// ============================================================================
// LIQUIDITY METRICS
// ============================================================================

export interface LiquidityMetrics {
  readonly timestamp: string;
  readonly symbol: string;
  readonly spreadBps: number; // bid-ask spread in basis points
  readonly volume24h: number; // 24h volume
  volumePercentile: number; // volume percentile vs historical
  marketImpactCoeff: number; // estimated market impact coefficient
  liquidityRegime: 'NORMAL' | 'THIN' | 'STRESSED';
  estimatedSlippage: number; // expected slippage for typical trade
  fillProbability: number; // probability of getting filled at desired price
}

// ============================================================================
// DRIFT DETECTION
// ============================================================================

export interface DriftAlert {
  readonly alertId: string;
  readonly type:
    | 'PERFORMANCE'
    | 'CONFIDENCE'
    | 'DATA'
    | 'SIGNAL'
    | 'REGIME'
    | 'MODEL'
    | 'PROVIDER'
    | 'CALIBRATION';
  readonly severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  readonly description: string;
  detectedAt: string;
  metric: string; // what metric drifted
  currentValue: number;
  historicalValue: number;
  changePercent: number;
  confidence: number; // 0-1, confidence in drift detection
  recommendedAction: string;
}

// ============================================================================
// CONTINUOUS EVALUATION QUEUE ITEM
// ============================================================================

export interface EvaluationQueueItem {
  readonly itemId: string;
  readonly forecastId: string;
  priority: number; // 1-10, higher = higher priority
  reason: string; // why this needs evaluation
  createdAt: string;
  scheduledFor: string; // when it should be evaluated
  evaluatorType: 'AUTOMATIC' | 'USER_REQUESTED' | 'RESEARCH_TRIGGER' | 'SYSTEM';
  metadata: Record<string, unknown>;
}

// ============================================================================
// RESEARCH QUEUE (for research scheduling)
// ============================================================================

export interface ResearchQueueItemState {
  readonly itemId: string;
  readonly hypothesisId?: string;
  readonly strategyId?: string;
  readonly experimentName: string;
  readonly description: string;
  priority: number;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'COOLDOWN';
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  readonly reason: string;
  readonly budget: number;
  cooldownUntil?: string;
  attempts: number;
  readonly maxAttempts: number;
  readonly metadata: Record<string, unknown>;
}

// ============================================================================
// HEALTH & STATUS
// ============================================================================

export interface FinancialIntelligenceHealth {
  readonly overallStatus: 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'UNKNOWN';
  readonly dataQuality: number; // 0-1
  readonly providerHealth: number; // 0-1 average provider health
  forecastAccuracy: number; // recent forecast accuracy
  calibrationQuality: number; // how well calibrated we are
  strategyHealth: number; // 0-1 average strategy health
  researchActivity: number; // 0-1, how active research is
  driftAlerts: number; // number of active drift alerts
  lastUpdated: string;
}

// ============================================================================
// DEFAULTS
// ============================================================================

export const DEFAULT_FORECAST_HORIZONS: Record<TimeHorizon, ForecastHorizon> = {
  INTRADAY: { type: 'INTRADAY', bars: 4, description: '4 hours' },
  SHORT_TERM: { type: 'SHORT_TERM', bars: 24, description: '1 day' },
  SWING: { type: 'SWING', bars: 168, description: '1 week' },
  MEDIUM_TERM: { type: 'MEDIUM_TERM', bars: 720, description: '1 month' },
  LONG_TERM: { type: 'LONG_TERM', bars: 2160, description: '3 months' },
};

export const DEFAULT_MODEL_SNAPSHOT: ModelSnapshot = {
  provider: 'ollama',
  model: 'qwen3:4b', // installed model (qwen3:8b is not; see request_router.MODEL_ROUTES)
  version: '1.0.0',
  timestamp: new Date().toISOString(),
};

export const DEFAULT_STRATEGY_HEALTH: StrategyHealth = {
  strategyId: '',
  strategyVersion: '1.0.0',
  status: 'RESEARCH_ONLY',
  sampleSize: 0,
  recentAccuracy: 0,
  rollingAccuracy: 0,
  accuracyTrend: 0,
  averageReturn: 0,
  returnVolatility: 0,
  maxDrawdown: 0,
  sharpeRatio: 0,
  sortinoRatio: 0,
  calibrationError: 0,
  confidenceQuality: 0,
  regimePerformance: {
    TRENDING_BULL: 0,
    TRENDING_BEAR: 0,
    RANGE: 0,
    HIGH_VOLATILITY: 0,
    LOW_VOLATILITY: 0,
    RISK_ON: 0,
    RISK_OFF: 0,
    MIXED: 0,
    UNKNOWN: 0,
  },
  drawdownByRegime: {
    TRENDING_BULL: 0,
    TRENDING_BEAR: 0,
    RANGE: 0,
    HIGH_VOLATILITY: 0,
    LOW_VOLATILITY: 0,
    RISK_ON: 0,
    RISK_OFF: 0,
    MIXED: 0,
    UNKNOWN: 0,
  },
  lastEvaluatedAt: '',
  evaluationCount: 0,
  failureRate: 0,
  avgFailureMagnitude: 0,
  successStreak: 0,
  failureStreak: 0,
  dataQualityScore: 0,
  providerReliability: {},
};