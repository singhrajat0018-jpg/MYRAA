// ============================================================================
// MYRAA Phase 28 — Learning System Index
// ============================================================================

// Core lifecycle
export { forecastLifecycleManager } from './forecastLifecycleManager';
export { continuousEvaluationEngine } from './continuousEvaluationEngine';

// Analysis engines
export { strategyHealthEngine } from './strategyHealthEngine';
export { driftDetectionEngine } from './driftDetectionEngine';
export { postMortemEngine } from './postMortemEngine';
export { researchLessonEngine } from './researchLessonEngine';
export { researchHypothesisEngine } from './researchHypothesisEngine';
export { researchQueueEngine } from './researchQueueEngine';
export { strategyAdaptationEngine } from './strategyAdaptationEngine';
export { providerQualityEngine } from './providerQualityEngine';
export { biasDetectionEngine } from './biasDetectionEngine';
export { metaEvaluationEngine } from './metaEvaluationEngine';
export { learningSystemHealthEngine } from './learningSystemHealthEngine';

// Specialized engines
export { attributionEngine } from './attributionEngine';
export { liquidityMetricsEngine } from './liquidityMetricsEngine';

// Types
export type {
  Forecast, ForecastLifecycleState, ForecastOutcome, ForecastEvaluation,
  ForecastType, ForecastHorizon, EvidenceSnapshot, DataSnapshot,
  StrategySnapshot, ModelSnapshot,
  RegimeType, RiskLevel, TimeHorizon, StrategyType,
  ThesisLifecycleState, ThesisOutcome,
  StrategyHealthStatus, StrategyHealth,
  ResearchLesson,
  HypothesisStatus, ResearchHypothesis,
  AdaptationProposalStatus, StrategyAdaptationProposal,
  FinancialProviderHealth,
  StrategyRegimeHorizonMatrix,
  PerformanceAttribution,
  LiquidityMetrics,
  DriftAlert,
  EvaluationQueueItem,
  FinancialIntelligenceHealth
} from './contracts';

export type { HealthEvaluation } from './strategyHealthEngine';
export type { DriftType, DriftSeverity, DriftConfig, DataPoint } from './driftDetectionEngine';
export type { PostMortem } from './postMortemEngine';
export type { ResearchQueueItem, ResearchPriority, ResearchStatus, ResearchCooldownConfig } from './researchQueueEngine';
export type { ValidationResult, ChampionChallengerResult } from './strategyAdaptationEngine';
export type { ProviderObservation } from './providerQualityEngine';
export type { BiasType, BiasAlert } from './biasDetectionEngine';
export type { MetaEvaluationResult } from './metaEvaluationEngine';
export type { LearningSystemHealth, SystemHealthStatus } from './learningSystemHealthEngine';
