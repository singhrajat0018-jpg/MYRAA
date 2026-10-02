// ============================================================================
// MYRAA Phase 25 — Unknown Outcome Handler: Prevent Blind Retries
// ============================================================================

import type {
  OutcomeAssessment, OutcomeStatus, ActionLifecycle, StateSnapshot,
} from './contracts';

// ============================================================================
// Unknown Outcome Handler
// ============================================================================

export class UnknownOutcomeHandler {
  private assessments: Map<string, OutcomeAssessment> = new Map();
  private dangerousActions = new Set<string>([
    'DELETE_FILE', 'EXECUTE_POWER_ACTION', 'CLOSE_APP',
    'DRAG', 'PASTE_TEXT', 'HOTKEY',
    'SEND_MESSAGE', 'SUBMIT_FORM', 'PURCHASE', 'TRANSFER',
  ]);

  // --- Assessment ---

  assess(actionId: string, actionType: string, lifecycle: ActionLifecycle, stateBefore: StateSnapshot | null, stateAfter: StateSnapshot | null): OutcomeAssessment {
    const dangerous = this.dangerousActions.has(actionType);

    // If we have verification, use it
    const lastVerified = lifecycle.history.filter(t => t.to === 'VERIFIED');
    if (lastVerified.length > 0) {
      return this.makeAssessment(actionId, 'SUCCESS', 0.9, ['Verification confirmed success'], false, dangerous);
    }

    // If we have failure, use it
    const lastFailed = lifecycle.history.filter(t => t.to === 'FAILED');
    if (lastFailed.length > 0) {
      return this.makeAssessment(actionId, 'FAILURE', 0.8, ['Action failed'], false, dangerous);
    }

    // If action executed but no verification
    const executed = lifecycle.history.filter(t => t.to === 'EXECUTING' || t.to === 'OBSERVING');
    if (executed.length > 0 && lifecycle.history.every(t => t.to !== 'VERIFIED' && t.to !== 'FAILED')) {
      // No verification occurred — outcome is unknown
      return this.makeAssessment(actionId, 'UNKNOWN', 0.3,
        ['Action executed but not verified — outcome uncertain'],
        true, dangerous);
    }

    return this.makeAssessment(actionId, 'UNKNOWN', 0.2, ['No execution evidence'], true, dangerous);
  }

  // --- Policy ---

  shouldRetry(assessment: OutcomeAssessment): boolean {
    if (assessment.status === 'SUCCESS') return true;
    if (assessment.status === 'FAILURE') return true;

    // UNKNOWN: never blindly retry dangerous actions
    if (assessment.status === 'UNKNOWN' && assessment.dangerousAction) return false;

    // UNKNOWN: low-risk actions may be safe to re-observe
    if (assessment.status === 'UNKNOWN' && !assessment.dangerousAction) return true;

    return false;
  }

  shouldAskUser(assessment: OutcomeAssessment): boolean {
    // Dangerous + unknown = ask user
    if (assessment.status === 'UNKNOWN' && assessment.dangerousAction) return true;
    // Contradicted = ask user
    if (assessment.status === 'CONTRADICTED') return true;
    return false;
  }

  getRecommendedAction(assessment: OutcomeAssessment): string {
    switch (assessment.status) {
      case 'SUCCESS': return 'CONTINUE';
      case 'FAILURE': return 'RETRY_OR_RECOVER';
      case 'PARTIAL_SUCCESS': return 'REOBSERVE_AND_CONTINUE';
      case 'UNKNOWN':
        if (assessment.dangerousAction) return 'ASK_USER';
        return 'REOBSERVE_FIRST';
      case 'CONTRADICTED': return 'ASK_USER';
      default: return 'ASK_USER';
    }
  }

  // --- Deduplication ---

  private recentActions: Map<string, string[]> = new Map();
  private deduplicationWindowMs = 10_000;

  isDuplicate(actionId: string, actionType: string, target: string): boolean {
    const key = `${actionType}:${target}`;
    const recent = this.recentActions.get(key) ?? [];

    // Clean old entries
    const now = Date.now();
    const valid = recent.filter(id => {
      const ts = parseInt(id.split('_')[1] ?? '0', 10);
      return now - ts < this.deduplicationWindowMs;
    });

    this.recentActions.set(key, valid);

    if (valid.length > 0) return true;

    valid.push(actionId);
    this.recentActions.set(key, valid);
    return false;
  }

  // --- Results ---

  getAssessment(actionId: string): OutcomeAssessment | undefined {
    return this.assessments.get(actionId);
  }

  getAllAssessments(): readonly OutcomeAssessment[] {
    return [...this.assessments.values()];
  }

  private makeAssessment(
    actionId: string,
    status: OutcomeStatus,
    confidence: number,
    evidence: readonly string[],
    dangerousAction: boolean,
    _actualDangerous: boolean,
  ): OutcomeAssessment {
    const assessment: OutcomeAssessment = {
      actionId,
      status,
      confidence,
      evidence,
      reasoning: `Outcome ${status} with confidence ${confidence.toFixed(2)}`,
      dangerousAction: dangerousAction,
      timestamp: new Date().toISOString(),
    };
    this.assessments.set(actionId, assessment);
    return assessment;
  }

  clear(): void {
    this.assessments.clear();
    this.recentActions.clear();
  }
}
