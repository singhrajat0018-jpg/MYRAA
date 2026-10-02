// ============================================================================
// MYRAA Phase 25 — Experience Learning: Failure, Recovery, Success Memory
// ============================================================================

import type {
  ExecutionExperience, ExperienceType, FailureClass, RecoveryAction,
  VerificationSource,
} from './contracts';

// ============================================================================
// Experience Learning Engine
// ============================================================================

export class ExperienceLearningEngine {
  private experiences: Map<string, ExecutionExperience> = new Map();
  private maxExperiences = 500;
  private decayFactor = 0.99;

  // --- Record ---

  recordFailure(
    taskType: string,
    actionType: string,
    failureClass: FailureClass,
    rootCause: string,
    recoveryAction: RecoveryAction | null,
    verificationMethod: VerificationSource,
    applicationDomain: string,
    latencyMs: number,
  ): ExecutionExperience {
    return this.record({
      type: 'FAILURE',
      taskType,
      actionType,
      failureClass,
      rootCause,
      recoveryAction,
      recoverySuccess: null,
      verificationMethod,
      applicationDomain,
      strategyUsed: '',
      latencyMs,
    });
  }

  recordRecovery(
    taskType: string,
    actionType: string,
    failureClass: FailureClass,
    recoveryAction: RecoveryAction,
    recoverySuccess: boolean,
    verificationMethod: VerificationSource,
    applicationDomain: string,
    latencyMs: number,
  ): ExecutionExperience {
    return this.record({
      type: 'RECOVERY',
      taskType,
      actionType,
      failureClass,
      rootCause: null,
      recoveryAction,
      recoverySuccess,
      verificationMethod,
      applicationDomain,
      strategyUsed: recoveryAction,
      latencyMs,
    });
  }

  recordSuccess(
    taskType: string,
    actionType: string,
    verificationMethod: VerificationSource,
    applicationDomain: string,
    strategyUsed: string,
    latencyMs: number,
  ): ExecutionExperience {
    return this.record({
      type: 'SUCCESS',
      taskType,
      actionType,
      failureClass: null,
      rootCause: null,
      recoveryAction: null,
      recoverySuccess: null,
      verificationMethod,
      applicationDomain,
      strategyUsed,
      latencyMs,
    });
  }

  recordUserCorrection(
    taskType: string,
    actionType: string,
    correction: string,
    applicationDomain: string,
  ): ExecutionExperience {
    return this.record({
      type: 'USER_CORRECTION',
      taskType,
      actionType,
      failureClass: null,
      rootCause: correction,
      recoveryAction: null,
      recoverySuccess: null,
      verificationMethod: 'VISUAL',
      applicationDomain,
      strategyUsed: '',
      latencyMs: 0,
    });
  }

  private record(data: Omit<ExecutionExperience, 'id' | 'timestamp' | 'successRate' | 'usageCount' | 'lastUsedAt'>): ExecutionExperience {
    const id = `exp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const experience: ExecutionExperience = {
      ...data,
      id,
      timestamp: new Date().toISOString(),
      successRate: data.type === 'SUCCESS' ? 1.0 : data.type === 'USER_CORRECTION' ? 0.3 : 0.5,
      usageCount: 0,
      lastUsedAt: new Date().toISOString(),
    };

    this.experiences.set(id, experience);
    this.enforceLimit();
    return experience;
  }

  // --- Query ---

  findRelevant(taskType: string, actionType: string, domain: string): readonly ExecutionExperience[] {
    return [...this.experiences.values()]
      .filter(e => e.taskType === taskType || e.applicationDomain === domain)
      .sort((a, b) => this.scoreRelevance(a, taskType, actionType) - this.scoreRelevance(b, taskType, actionType))
      .slice(0, 10);
  }

  findRecoveriesForFailure(failureClass: FailureClass): readonly ExecutionExperience[] {
    return [...this.experiences.values()]
      .filter(e => e.type === 'RECOVERY' && e.failureClass === failureClass && e.recoverySuccess === true)
      .sort((a, b) => b.successRate - a.successRate);
  }

  suggestStrategy(taskType: string, actionType: string, domain: string): StrategySuggestion | null {
    const relevant = this.findRelevant(taskType, actionType, domain);
    if (relevant.length === 0) return null;

    const best = relevant[0];
    return {
      strategy: best.strategyUsed,
      confidence: best.successRate,
      basedOn: relevant.length,
      lastSuccess: best.type === 'SUCCESS' ? best.timestamp : null,
    };
  }

  // --- Update ---

  recordOutcome(experienceId: string, success: boolean): void {
    const exp = this.experiences.get(experienceId);
    if (!exp) return;

    const alpha = 0.2;
    const newRate = success ? exp.successRate + alpha * (1 - exp.successRate) : exp.successRate + alpha * (0 - exp.successRate);

    const updated: ExecutionExperience = {
      ...exp,
      successRate: Math.max(0.01, Math.min(0.99, newRate)),
      usageCount: exp.usageCount + 1,
      lastUsedAt: new Date().toISOString(),
    };

    this.experiences.set(experienceId, updated);
  }

  // --- Decay ---

  applyDecay(): void {
    for (const [id, exp] of this.experiences) {
      const age = Date.now() - new Date(exp.timestamp).getTime();
      const days = age / (1000 * 60 * 60 * 24);
      const decay = Math.pow(this.decayFactor, days);

      const updated: ExecutionExperience = {
        ...exp,
        successRate: exp.successRate * decay,
      };

      this.experiences.set(id, updated);
    }
  }

  // --- Helpers ---

  private scoreRelevance(exp: ExecutionExperience, taskType: string, actionType: string): number {
    let score = 0;
    if (exp.taskType === taskType) score += 10;
    if (exp.actionType === actionType) score += 5;
    score += exp.successRate * 3;
    score -= exp.usageCount * 0.1;
    return -score; // Negate for ascending sort (most relevant first)
  }

  private enforceLimit(): void {
    if (this.experiences.size > this.maxExperiences) {
      const sorted = [...this.experiences.entries()]
        .sort((a, b) => a[1].successRate - b[1].successRate);
      const toRemove = sorted.slice(0, sorted.length - this.maxExperiences);
      for (const [id] of toRemove) this.experiences.delete(id);
    }
  }

  // --- Stats ---

  getStats(): ExperienceStats {
    const all = [...this.experiences.values()];
    return {
      total: all.length,
      byType: {
        FAILURE: all.filter(e => e.type === 'FAILURE').length,
        RECOVERY: all.filter(e => e.type === 'RECOVERY').length,
        SUCCESS: all.filter(e => e.type === 'SUCCESS').length,
        USER_CORRECTION: all.filter(e => e.type === 'USER_CORRECTION').length,
      },
      avgSuccessRate: all.length > 0 ? all.reduce((s, e) => s + e.successRate, 0) / all.length : 0,
      mostCommonFailure: this.getMostCommonFailure(),
    };
  }

  private getMostCommonFailure(): FailureClass | null {
    const failures = [...this.experiences.values()].filter(e => e.failureClass);
    if (failures.length === 0) return null;
    const counts = new Map<FailureClass, number>();
    for (const f of failures) {
      counts.set(f.failureClass!, (counts.get(f.failureClass!) ?? 0) + 1);
    }
    let best: FailureClass | null = null;
    let bestCount = 0;
    for (const [cls, count] of counts) {
      if (count > bestCount) { best = cls; bestCount = count; }
    }
    return best;
  }

  getExperiences(): readonly ExecutionExperience[] {
    return [...this.experiences.values()];
  }

  clear(): void {
    this.experiences.clear();
  }
}

// ============================================================================
// Strategy Suggestion
// ============================================================================

export interface StrategySuggestion {
  readonly strategy: string;
  readonly confidence: number;
  readonly basedOn: number;
  readonly lastSuccess: string | null;
}

// ============================================================================
// Experience Stats
// ============================================================================

export interface ExperienceStats {
  readonly total: number;
  readonly byType: {
    readonly FAILURE: number;
    readonly RECOVERY: number;
    readonly SUCCESS: number;
    readonly USER_CORRECTION: number;
  };
  readonly avgSuccessRate: number;
  readonly mostCommonFailure: FailureClass | null;
}
