// ============================================================================
// MYRAA Autonomous Reasoning Engine — Contracts & Types
// ============================================================================

// ============================================================================
// IDs
// ============================================================================

let _idCounter = 0;
export function generateAgentId(prefix = 'ag'): string {
  return `${prefix}_${Date.now().toString(36)}_${(++_idCounter).toString(36)}`;
}

export function nowISO(): string {
  return new Date().toISOString();
}

// ============================================================================
// Goal Types
// ============================================================================

export type GoalType =
  | 'QUESTION'
  | 'RESEARCH'
  | 'DECISION'
  | 'ACTION'
  | 'MULTI_STEP_TASK'
  | 'MONITORING'
  | 'PLANNED_TASK'
  | 'ANALYSIS'
  | 'COMPARISON'
  | 'OPTIMIZATION'
  | 'TROUBLESHOOTING'
  | 'CREATIVE'
  | 'INFORMATION_GATHERING'
  | 'DESIGN'
  | 'SYSTEM_OPERATION'
  | 'TRADING_DECISION';

export type GoalStatus =
  | 'RECEIVED'
  | 'UNDERSTANDING'
  | 'DECOMPOSING'
  | 'PLANNING'
  | 'WAITING_FOR_INFORMATION'
  | 'WAITING_FOR_APPROVAL'
  | 'READY'
  | 'EXECUTING'
  | 'VERIFYING'
  | 'REPLANNING'
  | 'COMPLETED'
  | 'PARTIALLY_COMPLETED'
  | 'FAILED'
  | 'BLOCKED'
  | 'CANCELLED';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type Reversibility = 'REVERSIBLE' | 'PARTIALLY_REVERSIBLE' | 'IRREVERSIBLE';
export type AutonomyPolicy = 'READ_ONLY' | 'SAFE_ACTION' | 'MODERATE_ACTION' | 'HIGH_IMPACT_ACTION' | 'IRREVERSIBLE_ACTION';

export const VALID_GOAL_TRANSITIONS: Record<GoalStatus, readonly GoalStatus[]> = {
  RECEIVED: ['UNDERSTANDING', 'CANCELLED'],
  UNDERSTANDING: ['DECOMPOSING', 'PLANNING', 'EXECUTING', 'BLOCKED', 'CANCELLED'],
  DECOMPOSING: ['PLANNING', 'BLOCKED', 'CANCELLED'],
  PLANNING: ['READY', 'WAITING_FOR_INFORMATION', 'WAITING_FOR_APPROVAL', 'BLOCKED', 'CANCELLED'],
  WAITING_FOR_INFORMATION: ['PLANNING', 'READY', 'BLOCKED', 'CANCELLED'],
  WAITING_FOR_APPROVAL: ['READY', 'CANCELLED'],
  READY: ['EXECUTING', 'CANCELLED'],
  EXECUTING: ['VERIFYING', 'REPLANNING', 'PARTIALLY_COMPLETED', 'COMPLETED', 'FAILED', 'CANCELLED'],
  VERIFYING: ['COMPLETED', 'REPLANNING', 'PARTIALLY_COMPLETED', 'FAILED'],
  REPLANNING: ['PLANNING', 'EXECUTING', 'BLOCKED', 'CANCELLED'],
  COMPLETED: [],
  PARTIALLY_COMPLETED: ['REPLANNING', 'CANCELLED'],
  FAILED: ['REPLANNING', 'CANCELLED'],
  BLOCKED: ['REPLANNING', 'CANCELLED'],
  CANCELLED: [],
};

export function isValidGoalTransition(from: GoalStatus, to: GoalStatus): boolean {
  return VALID_GOAL_TRANSITIONS[from]?.includes(to) ?? false;
}

// ============================================================================
// Goal
// ============================================================================

export interface Goal {
  readonly id: string;
  readonly userRequest: string;
  readonly conversationId?: string;
  readonly normalizedIntent?: StructuredIntent;
  readonly objective: string;
  readonly constraints: readonly string[];
  readonly preferences: readonly string[];
  readonly deadline?: string;
  readonly priority: RiskLevel;
  readonly riskLevel: RiskLevel;
  readonly requiredCapabilities: readonly string[];
  readonly requiredKnowledge: readonly string[];
  readonly successCriteria: readonly string[];
  readonly verificationCriteria: readonly string[];
  readonly executionPolicy: AutonomyPolicy;
  readonly assumptions: readonly Assumption[];
  readonly status: GoalStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly completedAt?: string;
  readonly planId?: string;
  readonly error?: string;
  readonly metadata: Record<string, unknown>;
}

export interface GoalUpdate {
  readonly status?: GoalStatus;
  readonly error?: string;
  readonly planId?: string;
  readonly assumptions?: readonly Assumption[];
  readonly metadata?: Record<string, unknown>;
}

// ============================================================================
// Structured Intent
// ============================================================================

export type TaskComplexity = 'TRIVIAL' | 'SIMPLE' | 'MEDIUM' | 'COMPLEX' | 'HIGHLY_COMPLEX';

export interface StructuredIntent {
  readonly goalType: GoalType;
  readonly complexity: TaskComplexity;
  readonly entities: readonly IntentEntity[];
  readonly topics: readonly string[];
  readonly actions: readonly string[];
  readonly questions: readonly string[];
  readonly temporalScope: 'CURRENT' | 'RECENT' | 'HISTORICAL' | 'FUTURE' | 'MIXED';
  readonly domainHints: readonly string[];
  readonly requiresExternalData: boolean;
  readonly requiresAction: boolean;
  readonly requiresDecision: boolean;
  readonly ambiguityScore: number;
  readonly ambiguousFields: readonly string[];
}

export interface IntentEntity {
  readonly name: string;
  readonly entityType: string;
  readonly role: string;
  readonly confidence: number;
}

// ============================================================================
// Assumption
// ============================================================================

export interface Assumption {
  readonly id: string;
  readonly statement: string;
  readonly confidence: number;
  readonly source: 'EXPLICIT' | 'INFERRED' | 'DEFAULT' | 'USER_PROVIDED';
  readonly status: 'ACTIVE' | 'INVALIDATED' | 'REVISED';
  readonly revisedTo?: string;
  readonly invalidatedBy?: string;
  readonly createdAt: string;
}

// ============================================================================
// Task Model
// ============================================================================

export type TaskType = 'INFORMATION_GATHER' | 'RESEARCH' | 'ACTION' | 'REASONING' | 'DECISION' | 'VERIFICATION' | 'SYNTHESIS' | 'USER_INPUT';
export type TaskStatus = 'PENDING' | 'READY' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED' | 'BLOCKED' | 'WAITING_APPROVAL' | 'CANCELLED';
export type FailureClassification = 'TRANSIENT' | 'PERMANENT' | 'INVALID_INPUT' | 'AUTH_REQUIRED' | 'PERMISSION_DENIED' | 'RATE_LIMITED' | 'PROVIDER_DOWN' | 'TIMEOUT' | 'VERIFICATION_FAILED' | 'UNKNOWN';

export interface PlanTask {
  readonly taskId: string;
  readonly goalId: string;
  readonly parentTaskId?: string;
  readonly title: string;
  readonly description: string;
  readonly type: TaskType;
  readonly dependencies: readonly string[];
  readonly requiredCapabilities: readonly string[];
  readonly requiredEvidence: readonly EvidenceRequirement[];
  readonly inputs: Record<string, unknown>;
  readonly expectedOutcome: string;
  readonly risk: RiskLevel;
  readonly reversibility: Reversibility;
  readonly status: TaskStatus;
  readonly priority: number;
  readonly timeout: number;
  readonly retryPolicy: RetryPolicy;
  readonly verificationPolicy?: VerificationPolicy;
  readonly autonomyPolicy: AutonomyPolicy;
  readonly result?: TaskResult;
  readonly error?: string;
  readonly failureClassification?: FailureClassification;
  readonly startedAt?: string;
  readonly completedAt?: string;
  readonly retryCount: number;
  readonly sideEffects: readonly SideEffect[];
  readonly metadata: Record<string, unknown>;
}

export interface TaskResult {
  readonly success: boolean;
  readonly data: unknown;
  readonly error?: string;
  readonly provider?: string;
  readonly timestamp: string;
  readonly latencyMs: number;
  readonly provenance: readonly ProvenanceEntry[];
  readonly confidence: number;
  readonly retryable: boolean;
  readonly verificationStatus?: VerificationStatus;
}

export interface SideEffect {
  readonly type: string;
  readonly target: string;
  readonly reversible: boolean;
  readonly rollbackData?: unknown;
  readonly timestamp: string;
}

// ============================================================================
// Retry Policy
// ============================================================================

export interface RetryPolicy {
  readonly maxRetries: number;
  readonly baseDelayMs: number;
  readonly maxDelayMs: number;
  readonly backoffMultiplier: number;
  readonly retryableFailures: readonly FailureClassification[];
}

export const DEFAULT_RETRY_POLICY: RetryPolicy = {
  maxRetries: 2,
  baseDelayMs: 1000,
  maxDelayMs: 10000,
  backoffMultiplier: 2,
  retryableFailures: ['TRANSIENT', 'TIMEOUT', 'RATE_LIMITED', 'PROVIDER_DOWN'],
};

// ============================================================================
// Verification
// ============================================================================

export type VerificationStrategy = 'ASSERTION' | 'STATE_CHECK' | 'SOURCE_CHECK' | 'COMPARISON' | 'REQUERY' | 'FILE_CHECK' | 'PROCESS_CHECK' | 'API_CHECK' | 'USER_CONFIRMATION';
export type VerificationStatus = 'NOT_VERIFIED' | 'VERIFIED' | 'FAILED' | 'PARTIAL' | 'STALE';

export interface VerificationPolicy {
  readonly strategies: readonly VerificationStrategy[];
  readonly required: boolean;
  readonly timeout: number;
  readonly successCriteria: readonly string[];
}

export interface VerificationResult {
  readonly taskId: string;
  readonly strategy: VerificationStrategy;
  readonly status: VerificationStatus;
  readonly message: string;
  readonly evidence: readonly string[];
  readonly timestamp: string;
}

// ============================================================================
// Evidence
// ============================================================================

export type EvidenceSource = 'WORLD_INTELLIGENCE' | 'RESEARCH' | 'CAPABILITY' | 'MEMORY' | 'NATIVE_TOOL' | 'CACHED' | 'USER_INPUT' | 'LLM_INFERENCE';
export type EvidenceSufficiency = 'SUFFICIENT' | 'PARTIAL' | 'CONFLICTED' | 'STALE' | 'INSUFFICIENT' | 'UNVERIFIED';

export interface EvidenceRequirement {
  readonly type: EvidenceSource;
  readonly description: string;
  readonly freshness?: 'VERY_FRESH' | 'FRESH' | 'RECENT' | 'HISTORICAL';
  readonly minSources: number;
  readonly domains: readonly string[];
}

export interface GatheredEvidence {
  readonly id: string;
  readonly requirement: EvidenceRequirement;
  readonly source: EvidenceSource;
  readonly providerId?: string;
  readonly data: unknown;
  readonly confidence: number;
  readonly freshness: string;
  readonly retrievedAt: string;
  readonly provenance: ProvenanceEntry[];
  readonly conflictsWith?: readonly string[];
}

export interface EvidenceAssessment {
  readonly requirements: readonly EvidenceRequirement[];
  readonly gathered: readonly GatheredEvidence[];
  readonly sufficiency: EvidenceSufficiency;
  readonly conflicts: readonly EvidenceConflict[];
  readonly missingRequirements: readonly EvidenceRequirement[];
  readonly overallConfidence: number;
}

export interface EvidenceConflict {
  readonly evidenceAId: string;
  readonly evidenceBId: string;
  readonly field: string;
  readonly valueA: unknown;
  readonly valueB: unknown;
  readonly description: string;
}

export interface ProvenanceEntry {
  readonly sourceId: string;
  readonly sourceType: EvidenceSource;
  readonly providerId?: string;
  readonly url?: string;
  readonly retrievedAt: string;
  readonly confidence: number;
}

// ============================================================================
// Plan Model
// ============================================================================

export type PlanStatus = 'DRAFT' | 'VALIDATED' | 'EXECUTING' | 'PAUSED' | 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED' | 'CANCELLED' | 'REPLANNED';

export interface ExecutionPlan {
  readonly planId: string;
  readonly goalId: string;
  readonly version: number;
  readonly parentPlanId?: string;
  readonly replanReason?: string;
  readonly strategy: string;
  readonly tasks: readonly PlanTask[];
  readonly parallelGroups: readonly string[][];
  readonly requiredEvidence: readonly EvidenceRequirement[];
  readonly riskSummary: RiskLevel;
  readonly approvalRequirements: readonly ApprovalRequirement[];
  readonly estimatedTimeMs: number;
  readonly successCriteria: readonly string[];
  readonly verificationPlan: readonly VerificationPolicy[];
  readonly rollbackPlan: readonly RollbackStep[];
  readonly status: PlanStatus;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly completedAt?: string;
  readonly budget: PlanBudget;
}

export interface RollbackStep {
  readonly taskId: string;
  readonly action: string;
  readonly target: string;
  readonly data?: unknown;
}

export interface ApprovalRequirement {
  readonly taskId: string;
  readonly reason: string;
  readonly risk: RiskLevel;
  readonly actionDescription: string;
  readonly reversible: boolean;
}

export interface PlanBudget {
  readonly maxSteps: number;
  readonly maxToolCalls: number;
  readonly maxResearchCalls: number;
  readonly maxTimeMs: number;
  readonly maxParallelTasks: number;
  readonly maxRetryCount: number;
  readonly maxReplans: number;
}

export interface RuntimeBudget {
  stepsUsed: number;
  toolCallsUsed: number;
  researchCallsUsed: number;
  timeUsedMs: number;
  replansUsed: number;
  retriesUsed: number;
  withinBudget: boolean;
  exhaustedResources: string[];
}

export const DEFAULT_PLAN_BUDGET: PlanBudget = {
  maxSteps: 20,
  maxToolCalls: 15,
  maxResearchCalls: 5,
  maxTimeMs: 120_000,
  maxParallelTasks: 5,
  maxRetryCount: 3,
  maxReplans: 3,
};

// ============================================================================
// Decision Model
// ============================================================================

export interface DecisionOption {
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly pros: readonly string[];
  readonly cons: readonly string[];
  readonly risks: readonly string[];
  readonly evidence: readonly string[];
  readonly score?: number;
  readonly constraints: readonly string[];
}

export interface DecisionResult {
  readonly decision: string;
  readonly options: readonly DecisionOption[];
  readonly selectedOptionId?: string;
  readonly evidence: readonly GatheredEvidence[];
  readonly confidence: number;
  readonly uncertainties: readonly string[];
  readonly assumptions: readonly Assumption[];
  readonly risks: readonly string[];
  readonly reasons: readonly string[];
  readonly recommendedAction?: string;
  readonly verificationStatus: VerificationStatus;
  readonly timestamp: string;
}

// ============================================================================
// Reasoning Types
// ============================================================================

export type ReasoningStrategy = 'DIRECT' | 'STEPWISE' | 'EVIDENCE_DRIVEN' | 'COMPARATIVE' | 'DIAGNOSTIC' | 'SCENARIO' | 'RESEARCH_FIRST' | 'ACTION_FIRST' | 'VERIFY_FIRST';
export type TaskClassifier = 'DIRECT_ANSWER' | 'RETRIEVE' | 'RESEARCH' | 'MULTI_STEP' | 'ACTION' | 'DECISION' | 'MONITOR' | 'HYBRID';

export interface Hypothesis {
  readonly id: string;
  readonly statement: string;
  readonly confidence: number;
  readonly supportingEvidence: readonly string[];
  readonly contradictingEvidence: readonly string[];
  readonly status: 'PROPOSED' | 'SUPPORTED' | 'REFUTED' | 'UNCERTAIN';
}

export interface ReasoningStep {
  readonly stepId: string;
  readonly type: 'OBSERVE' | 'INFER' | 'DEDUCE' | 'HYPOTHESIZE' | 'VERIFY' | 'CONCLUDE' | 'ASK_USER';
  readonly input: unknown;
  readonly output: unknown;
  readonly evidence: readonly string[];
  readonly confidence: number;
  readonly timestamp: string;
}

// ============================================================================
// Experience Model
// ============================================================================

export interface TaskExperience {
  readonly id: string;
  readonly taskType: TaskType;
  readonly goalType: GoalType;
  readonly goalPattern: string;
  readonly successfulPlan: readonly string[];
  readonly failedApproaches: readonly string[];
  readonly toolsUsed: readonly string[];
  readonly providersUsed: readonly string[];
  readonly verificationOutcome: VerificationStatus;
  readonly duration: number;
  readonly userCorrection?: string;
  readonly successRate: number;
  readonly usageCount: number;
  readonly timestamp: string;
  readonly metadata: Record<string, unknown>;
}

// ============================================================================
// Progress Events
// ============================================================================

export type AgentEventType =
  | 'GOAL_CREATED' | 'GOAL_UPDATED' | 'GOAL_COMPLETED' | 'GOAL_FAILED'
  | 'INTENT_PARSED' | 'GOAL_DECOMPOSED'
  | 'PLAN_CREATED' | 'PLAN_VALIDATED' | 'PLAN_REPLANNED' | 'PLAN_COMPLETED' | 'PLAN_FAILED' | 'PLAN_CANCELLED'
  | 'TASK_READY' | 'TASK_STARTED' | 'TASK_COMPLETED' | 'TASK_FAILED' | 'TASK_BLOCKED'
  | 'EVIDENCE_GATHERED' | 'EVIDENCE_SUFFICIENT' | 'EVIDENCE_INSUFFICIENT' | 'EVIDENCE_CONFLICT'
  | 'DECISION_MADE' | 'APPROVAL_REQUIRED' | 'APPROVAL_GRANTED' | 'APPROVAL_DENIED'
  | 'VERIFICATION_STARTED' | 'VERIFICATION_PASSED' | 'VERIFICATION_FAILED'
  | 'REPLAN_TRIGGERED' | 'RECOVERY_ATTEMPTED'
  | 'PROGRESS_UPDATE' | 'ERROR';

export interface AgentEvent {
  readonly type: AgentEventType;
  readonly agentId: string;
  readonly goalId?: string;
  readonly planId?: string;
  readonly taskId?: string;
  readonly timestamp: string;
  readonly data: Record<string, unknown>;
  readonly message?: string;
}

// ============================================================================
// Final Result
// ============================================================================

export type FinalResultStatus = 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED' | 'BLOCKED' | 'CANCELLED' | 'NEEDS_CLARIFICATION';

export interface FinalTaskResult {
  readonly status: FinalResultStatus;
  readonly goalId: string;
  readonly planId?: string;
  readonly summary: string;
  readonly answer?: string;
  readonly evidence: readonly GatheredEvidence[];
  readonly actionsPerformed: readonly string[];
  readonly verification: readonly VerificationResult[];
  readonly uncertainties: readonly string[];
  readonly followUpRequired: readonly string[];
  readonly recommendations?: readonly string[];
  readonly duration: number;
  readonly timestamp: string;
}

// ============================================================================
// Budget Check
// ============================================================================

export interface BudgetStatus {
  readonly stepsUsed: number;
  readonly toolCallsUsed: number;
  readonly researchCallsUsed: number;
  readonly timeUsedMs: number;
  readonly replansUsed: number;
  readonly retriesUsed: number;
  readonly withinBudget: boolean;
  readonly exhaustedResources: readonly string[];
}
