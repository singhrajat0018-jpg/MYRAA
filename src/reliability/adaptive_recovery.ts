// ============================================================================
// MYRAA Phase 25 — Adaptive Recovery Engine: Strategy Selection, Budget, Loops
// ============================================================================

import type {
  RecoveryAction, RecoveryCandidate, RecoveryExecution, RecoveryBudget,
  DiagnosisResult, Recoverability, ActionLifecycle,
} from './contracts';
import { DEFAULT_RECOVERY_BUDGET, RECOVERY_RISK_ORDER } from './contracts';

// ============================================================================
// Recovery Cost Model
// ============================================================================

interface RecoveryCostModel {
  readonly risk: 'LOW' | 'MEDIUM' | 'HIGH';
  readonly latencyMs: number;
  readonly baseProbability: number;
  readonly cost: number;
}

const RECOVERY_COSTS: Record<RecoveryAction, RecoveryCostModel> = {
  REOBSERVE: { risk: 'LOW', latencyMs: 500, baseProbability: 0.6, cost: 1 },
  REFRESH_STATE: { risk: 'LOW', latencyMs: 300, baseProbability: 0.5, cost: 1 },
  REFOCUS: { risk: 'LOW', latencyMs: 400, baseProbability: 0.7, cost: 1 },
  RELOCATE_TARGET: { risk: 'LOW', latencyMs: 800, baseProbability: 0.65, cost: 2 },
  SCROLL_TO_TARGET: { risk: 'LOW', latencyMs: 600, baseProbability: 0.55, cost: 1 },
  RETRY: { risk: 'LOW', latencyMs: 500, baseProbability: 0.4, cost: 1 },
  ALTERNATE_METHOD: { risk: 'MEDIUM', latencyMs: 1000, baseProbability: 0.6, cost: 3 },
  ALTERNATE_TARGET: { risk: 'MEDIUM', latencyMs: 1200, baseProbability: 0.55, cost: 3 },
  ALTERNATE_PROVIDER: { risk: 'MEDIUM', latencyMs: 2000, baseProbability: 0.7, cost: 4 },
  RELOAD: { risk: 'MEDIUM', latencyMs: 3000, baseProbability: 0.65, cost: 4 },
  REOPEN_APPLICATION: { risk: 'HIGH', latencyMs: 5000, baseProbability: 0.75, cost: 6 },
  RESTART_SAFE: { risk: 'HIGH', latencyMs: 5000, baseProbability: 0.7, cost: 6 },
  ROLLBACK: { risk: 'MEDIUM', latencyMs: 2000, baseProbability: 0.8, cost: 5 },
  REPLAN: { risk: 'MEDIUM', latencyMs: 1500, baseProbability: 0.6, cost: 4 },
  ASK_USER: { risk: 'LOW', latencyMs: 0, baseProbability: 0.9, cost: 2 },
  ABORT: { risk: 'LOW', latencyMs: 100, baseProbability: 1.0, cost: 0 },
};

// ============================================================================
// Adaptive Recovery Engine
// ============================================================================

export class AdaptiveRecoveryEngine {
  private budget: RecoveryBudget;
  private executionHistory: RecoveryExecution[] = [];
  private recoveryLoops: Map<string, number> = new Map();
  private maxHistory = 200;
  private loopThreshold = 3;

  constructor(budget: Partial<RecoveryBudget> = {}) {
    this.budget = { ...DEFAULT_RECOVERY_BUDGET, ...budget };
  }

  // --- Strategy Selection ---

  selectRecovery(diagnosis: DiagnosisResult, lifecycle: ActionLifecycle): RecoveryCandidate | null {
    // Check budget
    if (!this.budget.withinBudget) {
      return { action: 'ASK_USER', ...RECOVERY_COSTS.ASK_USER, probabilityOfSuccess: 0.9,
        reasoning: 'Recovery budget exhausted' };
    }

    // Check for recovery loop
    if (this.isRecoveryLoop(diagnosis.actionId, diagnosis.recommendedRecovery)) {
      return { action: 'ASK_USER', ...RECOVERY_COSTS.ASK_USER, probabilityOfSuccess: 0.9,
        reasoning: 'Recovery loop detected — asking user' };
    }

    // Check recoverability
    if (diagnosis.recoverability === 'FATAL') {
      return { action: 'ABORT', ...RECOVERY_COSTS.ABORT, probabilityOfSuccess: 1.0,
        reasoning: 'Failure is fatal — aborting' };
    }

    if (diagnosis.recoverability === 'REQUIRES_USER') {
      return { action: 'ASK_USER', ...RECOVERY_COSTS.ASK_USER, probabilityOfSuccess: 0.9,
        reasoning: 'Recovery requires user intervention' };
    }

    // Build candidate list from diagnosis recommendation + alternatives
    const candidates = this.buildCandidates(diagnosis, lifecycle);

    // Score and select
    return this.selectBestCandidate(candidates);
  }

  // --- Candidate Building ---

  private buildCandidates(diagnosis: DiagnosisResult, lifecycle: ActionLifecycle): RecoveryCandidate[] {
    const candidates: RecoveryCandidate[] = [];

    // Primary recommendation from diagnosis
    const primaryAction = diagnosis.recommendedRecovery as RecoveryAction;
    if (RECOVERY_COSTS[primaryAction]) {
      candidates.push(this.makeCandidate(primaryAction, diagnosis));
    }

    // Alternative strategies based on failure class
    const alternatives = this.getAlternatives(diagnosis.failureClass, diagnosis.recommendedRecovery);
    for (const alt of alternatives) {
      if (RECOVERY_COSTS[alt]) {
        candidates.push(this.makeCandidate(alt, diagnosis));
      }
    }

    // If budget is tight, prefer cheaper options
    if (this.budget.recoveryAttemptsUsed > this.budget.maxRecoveryAttempts * 0.7) {
      // Add ASK_USER as last resort
      candidates.push(this.makeCandidate('ASK_USER', diagnosis));
    }

    return candidates;
  }

  private getAlternatives(failureClass: string, primary: string): RecoveryAction[] {
    const altMap: Record<string, RecoveryAction[]> = {
      TARGET_NOT_FOUND: ['REOBSERVE', 'SCROLL_TO_TARGET', 'ALTERNATE_TARGET'],
      TARGET_STALE: ['REOBSERVE', 'REFRESH_STATE'],
      FOCUS_LOST: ['REFOCUS', 'REOPEN_APPLICATION'],
      WRONG_WINDOW: ['REFOCUS', 'REOPEN_APPLICATION'],
      UI_CHANGED: ['REOBSERVE', 'RELOCATE_TARGET', 'RELOAD'],
      APP_NOT_READY: ['RETRY', 'REFRESH_STATE', 'REOPEN_APPLICATION'],
      APP_CRASHED: ['REOPEN_APPLICATION', 'RESTART_SAFE'],
      NETWORK_FAILURE: ['RETRY', 'ALTERNATE_PROVIDER'],
      PROVIDER_FAILURE: ['ALTERNATE_PROVIDER', 'RETRY'],
      TIMEOUT: ['REOBSERVE', 'RETRY', 'REFRESH_STATE'],
      VERIFICATION_FAILURE: ['REOBSERVE', 'REFRESH_STATE'],
      STATE_MISMATCH: ['REFRESH_STATE', 'REOBSERVE'],
    };

    const alternatives = altMap[failureClass] ?? ['REOBSERVE', 'RETRY'];
    return alternatives.filter(a => a !== primary);
  }

  // --- Candidate Scoring ---

  private makeCandidate(action: RecoveryAction, diagnosis: DiagnosisResult): RecoveryCandidate {
    const model = RECOVERY_COSTS[action];

    // Adjust probability based on diagnosis context
    let adjustedProbability = model.baseProbability;
    if (diagnosis.confidence > 0.7) adjustedProbability *= 1.1;
    if (diagnosis.confidence < 0.4) adjustedProbability *= 0.8;

    return {
      action,
      risk: model.risk,
      latencyMs: model.latencyMs,
      probabilityOfSuccess: Math.min(1.0, adjustedProbability),
      cost: model.cost,
      reasoning: `Diagnosis: ${diagnosis.failureClass} — ${diagnosis.rootCause}`,
    };
  }

  private selectBestCandidate(candidates: readonly RecoveryCandidate[]): RecoveryCandidate | null {
    if (candidates.length === 0) return null;

    // Score: expected value = probability / (1 + cost) * riskMultiplier
    const riskMultiplier: Record<string, number> = { LOW: 1.0, MEDIUM: 0.8, HIGH: 0.5 };

    return candidates.reduce((best, current) => {
      const bestScore = this.scoreCandidate(best);
      const currentScore = this.scoreCandidate(current);
      return currentScore > bestScore ? current : best;
    });
  }

  private scoreCandidate(c: RecoveryCandidate): number {
    const riskMul = riskMultiplierMap[c.risk] ?? 0.5;
    return (c.probabilityOfSuccess * riskMul) / (1 + c.cost * 0.1);
  }

  // --- Execution Tracking ---

  recordExecution(execution: RecoveryExecution): void {
    this.executionHistory.push(execution);
    if (this.executionHistory.length > this.maxHistory) this.executionHistory.shift();

    // Track recovery loops
    const key = `${execution.actionId}:${execution.selectedRecovery.action}`;
    const count = (this.recoveryLoops.get(key) ?? 0) + 1;
    this.recoveryLoops.set(key, count);

    // Update budget
    (this.budget as { recoveryAttemptsUsed: number }).recoveryAttemptsUsed++;
    (this.budget as { totalTimeMs: number }).totalTimeMs += execution.completedAt
      ? new Date(execution.completedAt).getTime() - new Date(execution.startedAt).getTime()
      : 0;
    (this.budget as { withinBudget: boolean }).withinBudget =
      this.budget.recoveryAttemptsUsed < this.budget.maxRecoveryAttempts &&
      this.budget.totalTimeMs < this.budget.maxTotalTimeMs;
  }

  recordReplan(): void {
    (this.budget as { replansUsed: number }).replansUsed++;
    (this.budget as { withinBudget: boolean }).withinBudget =
      this.budget.recoveryAttemptsUsed < this.budget.maxRecoveryAttempts &&
      this.budget.replansUsed < this.budget.maxReplans;
  }

  recordTargetReacquisition(): void {
    (this.budget as { targetReacquisitionsUsed: number }).targetReacquisitionsUsed++;
  }

  recordVerificationRetry(): void {
    (this.budget as { verificationRetriesUsed: number }).verificationRetriesUsed++;
  }

  // --- Loop Detection ---

  private isRecoveryLoop(actionId: string, recoveryAction: string): boolean {
    const key = `${actionId}:${recoveryAction}`;
    return (this.recoveryLoops.get(key) ?? 0) >= this.loopThreshold;
  }

  getRecoveryLoopCount(actionId: string, recoveryAction: string): number {
    return this.recoveryLoops.get(`${actionId}:${recoveryAction}`) ?? 0;
  }

  // --- Budget ---

  getBudget(): RecoveryBudget {
    return { ...this.budget };
  }

  resetBudget(): void {
    this.budget = { ...DEFAULT_RECOVERY_BUDGET };
    this.recoveryLoops.clear();
  }

  // --- History ---

  getExecutionHistory(): readonly RecoveryExecution[] {
    return this.executionHistory;
  }

  getSuccessRate(): number {
    if (this.executionHistory.length === 0) return 0;
    const successes = this.executionHistory.filter(e => e.success === true).length;
    return successes / this.executionHistory.length;
  }

  clear(): void {
    this.executionHistory = [];
    this.recoveryLoops.clear();
    this.budget = { ...DEFAULT_RECOVERY_BUDGET };
  }
}

// Risk multiplier map
const riskMultiplierMap: Record<string, number> = { LOW: 1.0, MEDIUM: 0.8, HIGH: 0.5 };
