// ============================================================================
// MYRAA Phase 25 — Reliability System: Public API Barrel Export
// ============================================================================

export type {
  StateSnapshot, StateVersion, StateDiff, StateChange, StateChangeType,
  WindowStateSnapshot, ScreenStateSnapshot, FocusStateSnapshot,
  TargetStateSnapshot, ProcessStateSnapshot, FileStateSnapshot,
  BrowserStateSnapshot, DialogInfo,
  ActionLifecycle, ActionLifecycleStatus, LifecycleTransition,
  VerificationLevel, VerificationStatus, VerificationSource,
  VerificationResult, MultiSignalVerification, VerificationConflict,
  FailureClass, Recoverability, DiagnosticHypothesis, DiagnosisResult,
  RecoveryAction, RecoveryCandidate, RecoveryExecution, RecoveryBudget,
  OutcomeStatus, OutcomeAssessment,
  PlanPatch, PlanPatchType,
  ExperienceType, ExecutionExperience,
  TraceEvent, TraceEventType,
  TaskCompletionStatus, TaskOutcome,
} from './contracts';

export {
  DEFAULT_RECOVERY_BUDGET, VERIFICATION_LEVEL_RISK,
  RECOVERY_RISK_ORDER, HIGH_IMPACT_ACTIONS,
} from './contracts';

export { StateEstimator } from './state_estimator';
export type { StateObservations } from './state_estimator';
export { StateDiffEngine } from './state_diff';
export { VerificationEngine } from './verification_engine';
export { FailureDiagnosisEngine } from './failure_diagnosis';
export type { DiagnosisContext } from './failure_diagnosis';
export { AdaptiveRecoveryEngine } from './adaptive_recovery';
export { UnknownOutcomeHandler } from './unknown_outcome';
export { PlanPatcher } from './plan_patching';
export { ExperienceLearningEngine } from './experience_learning';
export type { StrategySuggestion, ExperienceStats } from './experience_learning';
export { ClosedLoopOrchestrator } from './orchestrator';
export type { ClosedLoopResult } from './orchestrator';
