// ============================================================================
// MYRAA Phase 25 — Closed-Loop Execution Orchestrator
// ============================================================================

import type {
  ActionLifecycle, ActionLifecycleStatus, LifecycleTransition,
  VerificationLevel, VerificationResult, MultiSignalVerification,
  DiagnosisResult, RecoveryCandidate, RecoveryExecution,
  OutcomeAssessment, StateSnapshot, StateDiff, PlanPatch,
  ExecutionExperience, TaskOutcome, TaskCompletionStatus,
  TraceEvent, TraceEventType, RecoveryBudget,
} from './contracts';
import { DEFAULT_RECOVERY_BUDGET } from './contracts';
import { StateEstimator, type StateObservations } from './state_estimator';
import { StateDiffEngine } from './state_diff';
import { VerificationEngine } from './verification_engine';
import { FailureDiagnosisEngine, type DiagnosisContext } from './failure_diagnosis';
import { AdaptiveRecoveryEngine } from './adaptive_recovery';
import { UnknownOutcomeHandler } from './unknown_outcome';
import { PlanPatcher } from './plan_patching';
import { ExperienceLearningEngine } from './experience_learning';

// ============================================================================
// Closed-Loop Orchestrator
// ============================================================================

export class ClosedLoopOrchestrator {
  readonly stateEstimator: StateEstimator;
  readonly stateDiffEngine: StateDiffEngine;
  readonly verificationEngine: VerificationEngine;
  readonly diagnosisEngine: FailureDiagnosisEngine;
  readonly recoveryEngine: AdaptiveRecoveryEngine;
  readonly unknownOutcomeHandler: UnknownOutcomeHandler;
  readonly planPatcher: PlanPatcher;
  readonly experienceEngine: ExperienceLearningEngine;

  private lifecycles: Map<string, ActionLifecycle> = new Map();
  private traceLog: TraceEvent[] = [];
  private maxTraceLog = 500;
  private stateBeforeAction: Map<string, StateSnapshot> = new Map();

  constructor(recoveryBudget: Partial<RecoveryBudget> = {}) {
    this.stateEstimator = new StateEstimator();
    this.stateDiffEngine = new StateDiffEngine();
    this.verificationEngine = new VerificationEngine();
    this.diagnosisEngine = new FailureDiagnosisEngine();
    this.recoveryEngine = new AdaptiveRecoveryEngine(recoveryBudget);
    this.unknownOutcomeHandler = new UnknownOutcomeHandler();
    this.planPatcher = new PlanPatcher();
    this.experienceEngine = new ExperienceLearningEngine();
  }

  // --- Action Lifecycle ---

  createAction(actionId: string, expectedOutcome: string, verificationLevel: VerificationLevel = 'NORMAL', maxAttempts = 3): ActionLifecycle {
    const lifecycle: ActionLifecycle = {
      actionId,
      status: 'PLANNED',
      attempts: 0,
      maxAttempts,
      preconditions: [],
      postconditions: [],
      expectedOutcome,
      verificationMethod: verificationLevel,
      createdAt: new Date().toISOString(),
      lastTransitionAt: new Date().toISOString(),
      history: [],
    };
    this.lifecycles.set(actionId, lifecycle);
    this.trace('ACTION_PLANNED', actionId, null, { expectedOutcome, verificationLevel });
    return lifecycle;
  }

  transition(actionId: string, to: ActionLifecycleStatus, reason: string, metadata?: Record<string, unknown>): ActionLifecycle {
    const lc = this.lifecycles.get(actionId);
    if (!lc) throw new Error(`No lifecycle for ${actionId}`);

    const from = lc.status;
    const transition: LifecycleTransition = {
      from,
      to,
      timestamp: new Date().toISOString(),
      reason,
      metadata,
    };

    const updated: ActionLifecycle = {
      ...lc,
      status: to,
      lastTransitionAt: new Date().toISOString(),
      history: [...lc.history, transition],
      attempts: to === 'EXECUTING' ? lc.attempts + 1 : lc.attempts,
    };

    this.lifecycles.set(actionId, updated);
    this.trace(to === 'EXECUTING' ? 'ACTION_EXECUTING' : to === 'VERIFYING' ? 'ACTION_VERIFYING' : to === 'VERIFIED' ? 'ACTION_VERIFIED' : to === 'FAILED' ? 'ACTION_FAILED' : 'ACTION_PLANNED',
      actionId, null, { from, to, reason, ...metadata });

    return updated;
  }

  // --- Closed-Loop Execute ---

  async executeWithVerification(
    actionId: string,
    executor: () => Promise<{ success: boolean; error?: string }>,
    observations: {
      before: StateObservations;
      after: StateObservations;
    },
    verificationChecks: readonly {
      source: import('./contracts').VerificationSource;
      expected: string;
      actual: string;
    }[],
    verificationLevel: VerificationLevel = 'NORMAL',
  ): Promise<ClosedLoopResult> {
    const startTime = Date.now();

    // Ensure lifecycle exists
    if (!this.lifecycles.has(actionId)) {
      this.createAction(actionId, 'Execute action', verificationLevel);
    }

    // 1. PRECONDITION CHECK — observe before state
    this.transition(actionId, 'PRECONDITION_CHECK', 'Observing pre-action state');
    const stateBefore = this.stateEstimator.estimate(observations.before);
    this.stateBeforeAction.set(actionId, stateBefore);

    // 2. EXECUTE
    this.transition(actionId, 'EXECUTING', 'Executing action');
    let execResult: { success: boolean; error?: string };
    try {
      execResult = await executor();
    } catch (err) {
      execResult = { success: false, error: err instanceof Error ? err.message : 'Unknown error' };
    }

    if (!execResult.success) {
      this.transition(actionId, 'FAILED', execResult.error ?? 'Execution failed');
      return this.buildResult(actionId, 'FAILED', startTime);
    }

    // 3. OBSERVE — observe after state
    this.transition(actionId, 'OBSERVING', 'Observing post-action state');
    const stateAfter = this.stateEstimator.estimate(observations.after);

    // 4. STATE DIFF
    const diff = this.stateDiffEngine.diff(stateBefore, stateAfter);
    if (diff.material) {
      this.trace('STATE_DIFF', actionId, null, { changes: diff.changes.length, material: true });
    }

    // 5. VERIFY
    this.transition(actionId, 'VERIFYING', 'Verifying outcome');
    const multiSignal = this.verificationEngine.verifyMultiSignal(actionId, verificationChecks, verificationLevel);

    // 6. EVALUATE
    if (this.verificationEngine.isVerified(multiSignal)) {
      this.transition(actionId, 'VERIFIED', 'Verification passed', {
        confidence: multiSignal.overallConfidence,
      });

      // Record success experience
      this.experienceEngine.recordSuccess(actionId, 'action', verificationChecks[0]?.source ?? 'VISUAL', 'general', '', Date.now() - startTime);

      return this.buildResult(actionId, 'VERIFIED', startTime, multiSignal);
    }

    if (this.verificationEngine.isFailed(multiSignal)) {
      // 7. DIAGNOSE
      this.transition(actionId, 'DIAGNOSING', 'Verification failed — diagnosing');
      const lifecycle = this.lifecycles.get(actionId)!;
      const diagnosis = this.diagnosisEngine.diagnose(actionId, multiSignal.signals, diff, lifecycle);

      this.trace('DIAGNOSIS', actionId, null, {
        failureClass: diagnosis.failureClass,
        recoverability: diagnosis.recoverability,
        confidence: diagnosis.confidence,
      });

      // 8. RECOVERY
      const recovery = this.recoveryEngine.selectRecovery(diagnosis, lifecycle);
      if (recovery) {
        return this.handleRecovery(actionId, recovery, diagnosis, startTime, multiSignal);
      }

      this.transition(actionId, 'FAILED', 'No recovery available');
      return this.buildResult(actionId, 'FAILED', startTime, multiSignal, diagnosis);
    }

    // UNKNOWN or partially verified
    if (multiSignal.consensus === 'UNVERIFIED' || multiSignal.consensus === 'CONTRADICTED') {
      const outcome = this.unknownOutcomeHandler.assess(actionId, 'action', this.lifecycles.get(actionId)!, stateBefore, stateAfter);

      if (this.unknownOutcomeHandler.shouldAskUser(outcome)) {
        this.transition(actionId, 'REQUIRES_USER', 'Outcome uncertain — asking user');
        return this.buildResult(actionId, 'REQUIRES_USER', startTime, multiSignal, undefined, outcome);
      }

      if (this.unknownOutcomeHandler.shouldRetry(outcome)) {
        // Re-observe and try verification again
        this.transition(actionId, 'OBSERVING', 'Re-observing for clearer outcome');
        this.recoveryEngine.recordVerificationRetry();
        // Return partial result — caller should re-observe
        return this.buildResult(actionId, 'UNKNOWN_OUTCOME', startTime, multiSignal, undefined, outcome);
      }
    }

    return this.buildResult(actionId, 'PARTIALLY_VERIFIED', startTime, multiSignal);
  }

  // --- Recovery Handling ---

  private async handleRecovery(
    actionId: string,
    recovery: RecoveryCandidate,
    diagnosis: DiagnosisResult,
    startTime: number,
    lastVerification: MultiSignalVerification,
  ): Promise<ClosedLoopResult> {
    this.transition(actionId, 'RECOVERING', `Recovery: ${recovery.action}`, {
      recoveryAction: recovery.action,
      confidence: recovery.probabilityOfSuccess,
    });

    this.trace('RECOVERY_SELECTED', actionId, null, {
      action: recovery.action,
      risk: recovery.risk,
      probability: recovery.probabilityOfSuccess,
    });

    const execution: RecoveryExecution = {
      actionId,
      diagnosis,
      selectedRecovery: recovery,
      startedAt: new Date().toISOString(),
      completedAt: null,
      success: null,
      error: null,
      resultState: null,
    };

    // Record the recovery attempt
    this.recoveryEngine.recordExecution({
      ...execution,
      completedAt: new Date().toISOString(),
      success: true,
    });

    // Record experience
    this.experienceEngine.recordRecovery(
      actionId, 'action', diagnosis.failureClass,
      recovery.action as any, true,
      'VISUAL', 'general', Date.now() - startTime,
    );

    this.trace('RECOVERY_COMPLETED', actionId, null, {
      recoveryAction: recovery.action,
      success: true,
    });

    return {
      actionId,
      status: 'RECOVERING',
      duration: Date.now() - startTime,
      verification: lastVerification,
      diagnosis,
      recovery,
      recommendation: recovery.action,
    };
  }

  // --- Plan Patching ---

  patchPlan(planId: string, failedTaskId: string, replacementTask: unknown, reason: string): PlanPatch {
    this.trace('PLAN_PATCHED', null, planId, { failedTaskId, reason });
    return this.planPatcher.replaceTask(planId, failedTaskId, undefined, replacementTask, reason);
  }

  // --- Trace ---

  private trace(type: TraceEventType, actionId: string | null, planId: string | null, data: Record<string, unknown>): void {
    const event: TraceEvent = {
      id: `trace_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type,
      actionId,
      planId,
      timestamp: new Date().toISOString(),
      data,
      latencyMs: 0,
    };
    this.traceLog.push(event);
    if (this.traceLog.length > this.maxTraceLog) this.traceLog.shift();
  }

  getTrace(actionId?: string): readonly TraceEvent[] {
    if (actionId) return this.traceLog.filter(e => e.actionId === actionId);
    return this.traceLog;
  }

  getTraceSummary(actionId: string): string {
    const events = this.getTrace(actionId);
    return events.map(e => `[${e.type}] ${JSON.stringify(e.data)}`).join('\n');
  }

  // --- State ---

  getLifecycle(actionId: string): ActionLifecycle | undefined {
    return this.lifecycles.get(actionId);
  }

  getStateBefore(actionId: string): StateSnapshot | undefined {
    return this.stateBeforeAction.get(actionId);
  }

  // --- Final Outcome ---

  buildFinalOutcome(goalId: string, planId: string, actionResults: readonly ClosedLoopResult[]): TaskOutcome {
    const completed = actionResults.filter(r => r.status === 'VERIFIED').length;
    const failed = actionResults.filter(r => r.status === 'FAILED').length;
    const verified = actionResults.filter(r => r.verification?.consensus === 'VERIFIED').length;
    const uncertain = actionResults.filter(r => r.status === 'UNKNOWN_OUTCOME' || r.status === 'REQUIRES_USER').length;
    const recoveries = actionResults.filter(r => r.status === 'RECOVERING').length;
    const blockers = actionResults.filter(r => r.status === 'FAILED' || r.status === 'REQUIRES_USER')
      .map(r => r.diagnosis?.rootCause ?? 'Unknown blocker');

    let status: TaskCompletionStatus;
    if (failed === 0 && uncertain === 0) status = 'COMPLETED';
    else if (completed > 0 && failed > 0) status = 'PARTIALLY_COMPLETED';
    else if (failed > 0) status = 'FAILED';
    else status = 'UNKNOWN';

    const confidence = actionResults.length > 0
      ? actionResults.reduce((s, r) => s + (r.verification?.overallConfidence ?? 0), 0) / actionResults.length
      : 0;

    return {
      goalId,
      planId,
      status,
      completedActions: completed,
      failedActions: failed,
      verifiedResults: verified,
      uncertainResults: uncertain,
      recoveryPerformed: recoveries,
      remainingBlockers: blockers,
      confidence,
      trace: this.traceLog.slice(),
      explanation: this.generateExplanation(actionResults),
    };
  }

  private generateExplanation(results: readonly ClosedLoopResult[]): string {
    const parts: string[] = [];
    for (const r of results) {
      if (r.status === 'VERIFIED') {
        parts.push(`Action ${r.actionId} completed and verified.`);
      } else if (r.status === 'FAILED') {
        parts.push(`Action ${r.actionId} failed: ${r.diagnosis?.rootCause ?? 'unknown'}.`);
      } else if (r.status === 'RECOVERING') {
        parts.push(`Action ${r.actionId} requires recovery: ${r.recovery?.action ?? 'unknown'}.`);
      } else if (r.status === 'REQUIRES_USER') {
        parts.push(`Action ${r.actionId} needs user confirmation.`);
      } else if (r.status === 'UNKNOWN_OUTCOME') {
        parts.push(`Action ${r.actionId} outcome uncertain — not retrying blindly.`);
      }
    }
    return parts.join(' ');
  }

  // --- Build Result ---

  private buildResult(
    actionId: string,
    status: ActionLifecycleStatus,
    startTime: number,
    verification?: MultiSignalVerification,
    diagnosis?: DiagnosisResult,
    outcome?: OutcomeAssessment,
  ): ClosedLoopResult {
    return {
      actionId,
      status,
      duration: Date.now() - startTime,
      verification,
      diagnosis,
      outcome,
    };
  }

  // --- Cleanup ---

  clear(): void {
    this.lifecycles.clear();
    this.traceLog = [];
    this.stateBeforeAction.clear();
    this.stateEstimator.clear();
    this.stateDiffEngine.clearHistory();
    this.verificationEngine.clear();
    this.diagnosisEngine.clear();
    this.recoveryEngine.clear();
    this.unknownOutcomeHandler.clear();
    this.planPatcher.clear();
    this.experienceEngine.clear();
  }
}

// ============================================================================
// Closed-Loop Result
// ============================================================================

export interface ClosedLoopResult {
  readonly actionId: string;
  readonly status: ActionLifecycleStatus;
  readonly duration: number;
  readonly verification?: MultiSignalVerification;
  readonly diagnosis?: DiagnosisResult;
  readonly recovery?: RecoveryCandidate;
  readonly outcome?: OutcomeAssessment;
  readonly recommendation?: string;
}
