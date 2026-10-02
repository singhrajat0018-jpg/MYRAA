// ============================================================================
// MYRAA Phase 25 — Contracts: State Estimation, Verification, Diagnosis, Recovery
// ============================================================================

// ============================================================================
// State Estimation
// ============================================================================

export type StateVersion = number;

export interface StateSnapshot {
  readonly version: StateVersion;
  readonly timestamp: string;
  readonly hash: string;
  readonly windowState: WindowStateSnapshot;
  readonly screenState: ScreenStateSnapshot;
  readonly focusState: FocusStateSnapshot;
  readonly targetState: TargetStateSnapshot;
  readonly processState: ProcessStateSnapshot;
  readonly fileState: FileStateSnapshot;
  readonly browserState: BrowserStateSnapshot;
  readonly pendingDialogs: readonly DialogInfo[];
}

export interface WindowStateSnapshot {
  readonly hwnd: number | null;
  readonly title: string;
  readonly processName: string;
  readonly bounds: { x: number; y: number; width: number; height: number };
  readonly state: 'NORMAL' | 'MINIMIZED' | 'MAXIMIZED' | 'HIDDEN';
  readonly visible: boolean;
}

export interface ScreenStateSnapshot {
  readonly monitorCount: number;
  readonly activeMonitor: number;
  readonly resolution: { width: number; height: number };
  readonly dpi: number;
  readonly scaleFactor: number;
}

export interface FocusStateSnapshot {
  readonly focusedHwnd: number | null;
  readonly focusedTitle: string;
  readonly focusedProcess: string;
  readonly ownsInput: boolean;
}

export interface TargetStateSnapshot {
  readonly targetId: string | null;
  readonly targetLabel: string;
  readonly targetBounds: { x: number; y: number; width: number; height: number } | null;
  readonly targetVisible: boolean;
  readonly targetEnabled: boolean;
  readonly targetConfidence: number;
  readonly targetSource: string;
  readonly lastVerifiedAt: string | null;
}

export interface ProcessStateSnapshot {
  readonly running: boolean;
  readonly pid: number | null;
  readonly responsive: boolean;
}

export interface FileStateSnapshot {
  readonly exists: boolean;
  readonly lastModified: string | null;
  readonly size: number | null;
}

export interface BrowserStateSnapshot {
  readonly url: string | null;
  readonly title: string | null;
  readonly ready: boolean;
  readonly domElementCount: number;
}

export interface DialogInfo {
  readonly type: string;
  readonly title: string;
  readonly visible: boolean;
}

// ============================================================================
// State Diff
// ============================================================================

export type StateChangeType =
  | 'WINDOW_OPENED' | 'WINDOW_CLOSED' | 'WINDOW_MOVED' | 'WINDOW_RESIZED'
  | 'WINDOW_STATE_CHANGED' | 'FOCUS_CHANGED' | 'FOCUS_LOST'
  | 'ELEMENT_APPEARED' | 'ELEMENT_DISAPPEARED' | 'ELEMENT_MOVED'
  | 'ELEMENT_STATE_CHANGED' | 'TEXT_CHANGED' | 'VALUE_CHANGED'
  | 'PAGE_CHANGED' | 'URL_CHANGED' | 'DOM_CHANGED'
  | 'FILE_CREATED' | 'FILE_DELETED' | 'FILE_MODIFIED' | 'FILE_MOVED'
  | 'PROCESS_STARTED' | 'PROCESS_EXITED' | 'PROCESS_UNRESPONSIVE'
  | 'DIALOG_APPEARED' | 'DIALOG_DISMISSED'
  | 'SCREEN_CHANGED' | 'DPI_CHANGED' | 'MONITOR_CHANGED'
  | 'TARGET_STALE' | 'TARGET_CONFIDENCE_CHANGED'
  | 'UNKNOWN_CHANGE';

export interface StateDiff {
  readonly fromVersion: StateVersion;
  readonly toVersion: StateVersion;
  readonly changes: readonly StateChange[];
  readonly material: boolean;
  readonly timestamp: string;
}

export interface StateChange {
  readonly type: StateChangeType;
  readonly field: string;
  readonly oldValue: unknown;
  readonly newValue: unknown;
  readonly material: boolean;
  readonly description: string;
}

// ============================================================================
// Action Lifecycle
// ============================================================================

export type ActionLifecycleStatus =
  | 'PLANNED'
  | 'PRECONDITION_CHECK'
  | 'EXECUTING'
  | 'OBSERVING'
  | 'VERIFYING'
  | 'VERIFIED'
  | 'PARTIALLY_VERIFIED'
  | 'DIAGNOSING'
  | 'RECOVERING'
  | 'REVERIFYING'
  | 'REPLANNING'
  | 'BLOCKED'
  | 'REQUIRES_USER'
  | 'UNKNOWN_OUTCOME'
  | 'COMPLETED'
  | 'FAILED';

export interface ActionLifecycle {
  readonly actionId: string;
  readonly status: ActionLifecycleStatus;
  readonly attempts: number;
  readonly maxAttempts: number;
  readonly preconditions: readonly string[];
  readonly postconditions: readonly string[];
  readonly expectedOutcome: string;
  readonly verificationMethod: VerificationLevel;
  readonly createdAt: string;
  readonly lastTransitionAt: string;
  readonly history: readonly LifecycleTransition[];
}

export interface LifecycleTransition {
  readonly from: ActionLifecycleStatus;
  readonly to: ActionLifecycleStatus;
  readonly timestamp: string;
  readonly reason: string;
  readonly metadata?: Record<string, unknown>;
}

// ============================================================================
// Verification
// ============================================================================

export type VerificationLevel = 'LIGHT' | 'NORMAL' | 'STRICT' | 'CRITICAL';

export type VerificationStatus =
  | 'VERIFIED'
  | 'PARTIALLY_VERIFIED'
  | 'UNVERIFIED'
  | 'CONTRADICTED'
  | 'FAILED'
  | 'NOT_APPLICABLE'
  | 'VERIFICATION_UNAVAILABLE';

export type VerificationSource =
  | 'STRUCTURED_STATE'
  | 'DOM'
  | 'ACCESSIBILITY'
  | 'OS_STATE'
  | 'FILESYSTEM'
  | 'PROCESS'
  | 'VISUAL'
  | 'OCR'
  | 'WEAK_VISUAL'
  | 'API_RESPONSE'
  | 'WORLD_STATE';

export interface VerificationResult {
  readonly actionId: string;
  readonly status: VerificationStatus;
  readonly confidence: number;
  readonly source: VerificationSource;
  readonly evidence: string;
  readonly expected: string;
  readonly actual: string;
  readonly timestamp: string;
  readonly latencyMs: number;
  readonly level: VerificationLevel;
}

export interface MultiSignalVerification {
  readonly actionId: string;
  readonly signals: readonly VerificationResult[];
  readonly consensus: VerificationStatus;
  readonly overallConfidence: number;
  readonly conflicts: readonly VerificationConflict[];
  readonly timestamp: string;
}

export interface VerificationConflict {
  readonly sourceA: VerificationSource;
  readonly sourceB: VerificationSource;
  readonly statusA: VerificationStatus;
  readonly statusB: VerificationStatus;
  readonly description: string;
}

// ============================================================================
// Failure Diagnosis
// ============================================================================

export type FailureClass =
  | 'TARGET_NOT_FOUND' | 'TARGET_AMBIGUOUS' | 'TARGET_STALE'
  | 'FOCUS_LOST' | 'WRONG_WINDOW' | 'UI_CHANGED'
  | 'APP_NOT_READY' | 'APP_CRASHED'
  | 'NETWORK_FAILURE' | 'PROVIDER_FAILURE' | 'AUTH_FAILURE' | 'RATE_LIMIT'
  | 'TIMEOUT' | 'PERMISSION' | 'VALIDATION_ERROR'
  | 'STATE_MISMATCH' | 'VERIFICATION_FAILURE'
  | 'PARTIAL_SUCCESS' | 'UNKNOWN';

export type Recoverability =
  | 'AUTO_RECOVERABLE'
  | 'RECOVERABLE_WITH_REPLAN'
  | 'REQUIRES_USER'
  | 'FATAL';

export interface DiagnosticHypothesis {
  readonly hypothesis: string;
  readonly confidence: number;
  readonly supportingEvidence: readonly string[];
  readonly contradictingEvidence: readonly string[];
}

export interface DiagnosisResult {
  readonly actionId: string;
  readonly failureClass: FailureClass;
  readonly rootCause: string;
  readonly evidence: readonly string[];
  readonly confidence: number;
  readonly recoverability: Recoverability;
  readonly recommendedRecovery: string;
  readonly hypotheses: readonly DiagnosticHypothesis[];
  readonly timestamp: string;
}

// ============================================================================
// Recovery
// ============================================================================

export type RecoveryAction =
  | 'REOBSERVE' | 'REFRESH_STATE' | 'REFOCUS'
  | 'RELOCATE_TARGET' | 'SCROLL_TO_TARGET'
  | 'RETRY' | 'ALTERNATE_METHOD' | 'ALTERNATE_TARGET'
  | 'ALTERNATE_PROVIDER' | 'RELOAD' | 'REOPEN_APPLICATION'
  | 'RESTART_SAFE' | 'ROLLBACK' | 'REPLAN'
  | 'ASK_USER' | 'ABORT';

export interface RecoveryCandidate {
  readonly action: RecoveryAction;
  readonly risk: 'LOW' | 'MEDIUM' | 'HIGH';
  readonly latencyMs: number;
  readonly probabilityOfSuccess: number;
  readonly cost: number;
  readonly reasoning: string;
}

export interface RecoveryExecution {
  readonly actionId: string;
  readonly diagnosis: DiagnosisResult;
  readonly selectedRecovery: RecoveryCandidate;
  readonly startedAt: string;
  readonly completedAt: string | null;
  readonly success: boolean | null;
  readonly error: string | null;
  readonly resultState: StateSnapshot | null;
}

export interface RecoveryBudget {
  readonly maxRecoveryAttempts: number;
  readonly maxReplans: number;
  readonly maxTargetReacquisitions: number;
  readonly maxVerificationRetries: number;
  readonly maxTotalTimeMs: number;
  readonly recoveryAttemptsUsed: number;
  readonly replansUsed: number;
  readonly targetReacquisitionsUsed: number;
  readonly verificationRetriesUsed: number;
  readonly totalTimeMs: number;
  readonly withinBudget: boolean;
}

// ============================================================================
// Unknown Outcome
// ============================================================================

export type OutcomeStatus =
  | 'SUCCESS'
  | 'FAILURE'
  | 'PARTIAL_SUCCESS'
  | 'UNKNOWN'
  | 'CONTRADICTED';

export interface OutcomeAssessment {
  readonly actionId: string;
  readonly status: OutcomeStatus;
  readonly confidence: number;
  readonly evidence: readonly string[];
  readonly reasoning: string;
  readonly dangerousAction: boolean;
  readonly timestamp: string;
}

// ============================================================================
// Plan Patching
// ============================================================================

export type PlanPatchType =
  | 'INSERT_TASK'
  | 'REMOVE_TASK'
  | 'REPLACE_TASK'
  | 'MODIFY_TASK'
  | 'CHANGE_DEPENDENCY'
  | 'UPDATE_POSTCONDITION';

export interface PlanPatch {
  readonly patchId: string;
  readonly planId: string;
  readonly type: PlanPatchType;
  readonly targetTaskId: string;
  readonly oldTask?: unknown;
  readonly newTask?: unknown;
  readonly reason: string;
  readonly appliedAt: string;
  readonly preservesCompleted: boolean;
}

// ============================================================================
// Experience
// ============================================================================

export type ExperienceType = 'FAILURE' | 'RECOVERY' | 'SUCCESS' | 'USER_CORRECTION';

export interface ExecutionExperience {
  readonly id: string;
  readonly type: ExperienceType;
  readonly taskType: string;
  readonly actionType: string;
  readonly failureClass: FailureClass | null;
  readonly rootCause: string | null;
  readonly recoveryAction: RecoveryAction | null;
  readonly recoverySuccess: boolean | null;
  readonly verificationMethod: VerificationSource;
  readonly applicationDomain: string;
  readonly strategyUsed: string;
  readonly latencyMs: number;
  readonly timestamp: string;
  readonly successRate: number;
  readonly usageCount: number;
  readonly lastUsedAt: string;
}

// ============================================================================
// Telemetry
// ============================================================================

export type TraceEventType =
  | 'ACTION_PLANNED' | 'ACTION_PRECONDITION_CHECK' | 'ACTION_EXECUTING'
  | 'ACTION_OBSERVING' | 'ACTION_VERIFYING' | 'ACTION_VERIFIED'
  | 'ACTION_FAILED' | 'ACTION_DIAGNOSING' | 'ACTION_RECOVERING'
  | 'ACTION_RECOVERED' | 'ACTION_REPLANNING' | 'ACTION_UNKNOWN_OUTCOME'
  | 'STATE_DIFF' | 'VERIFICATION_SIGNAL' | 'VERIFICATION_CONSENSUS'
  | 'DIAGNOSIS' | 'RECOVERY_SELECTED' | 'RECOVERY_COMPLETED'
  | 'PLAN_PATCHED' | 'USER_INTERVENTION' | 'EMERGENCY_STOP'
  | 'EXPERIENCE_STORED' | 'BUDGET_EXCEEDED' | 'LOOP_DETECTED';

export interface TraceEvent {
  readonly id: string;
  readonly type: TraceEventType;
  readonly actionId: string | null;
  readonly planId: string | null;
  readonly timestamp: string;
  readonly data: Record<string, unknown>;
  readonly latencyMs: number;
}

// ============================================================================
// Task Outcome
// ============================================================================

export type TaskCompletionStatus =
  | 'COMPLETED'
  | 'PARTIALLY_COMPLETED'
  | 'FAILED'
  | 'BLOCKED'
  | 'UNKNOWN';

export interface TaskOutcome {
  readonly goalId: string;
  readonly planId: string;
  readonly status: TaskCompletionStatus;
  readonly completedActions: number;
  readonly failedActions: number;
  readonly verifiedResults: number;
  readonly uncertainResults: number;
  readonly recoveryPerformed: number;
  readonly remainingBlockers: readonly string[];
  readonly confidence: number;
  readonly trace: readonly TraceEvent[];
  readonly explanation: string;
}

// ============================================================================
// Constants
// ============================================================================

export const DEFAULT_RECOVERY_BUDGET: RecoveryBudget = {
  maxRecoveryAttempts: 5,
  maxReplans: 3,
  maxTargetReacquisitions: 4,
  maxVerificationRetries: 3,
  maxTotalTimeMs: 120_000,
  recoveryAttemptsUsed: 0,
  replansUsed: 0,
  targetReacquisitionsUsed: 0,
  verificationRetriesUsed: 0,
  totalTimeMs: 0,
  withinBudget: true,
};

export const VERIFICATION_LEVEL_RISK: Record<VerificationLevel, string> = {
  LIGHT: 'safe actions, cursor moves',
  NORMAL: 'standard interactions',
  STRICT: 'destructive, financial, irreversible',
  CRITICAL: 'multiple signals + user confirmation',
};

export const RECOVERY_RISK_ORDER: RecoveryAction[] = [
  'REOBSERVE', 'REFRESH_STATE', 'REFOCUS',
  'RELOCATE_TARGET', 'SCROLL_TO_TARGET',
  'RETRY', 'ALTERNATE_METHOD', 'ALTERNATE_TARGET',
  'ALTERNATE_PROVIDER', 'RELOAD', 'REOPEN_APPLICATION',
  'RESTART_SAFE', 'ROLLBACK', 'REPLAN',
  'ASK_USER', 'ABORT',
];

export const HIGH_IMPACT_ACTIONS = [
  'DELETE_FILE', 'EXECUTE_POWER_ACTION', 'CLOSE_APP',
  'DRAG', 'PASTE_TEXT', 'HOTKEY',
];
