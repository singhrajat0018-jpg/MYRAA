// ============================================================================
// MYRAA Phase 25 — Failure Diagnosis Engine: Root Cause, Hypotheses
// ============================================================================

import type {
  DiagnosisResult, DiagnosticHypothesis, FailureClass, Recoverability,
  VerificationResult, StateDiff, StateChange, ActionLifecycle,
} from './contracts';

// ============================================================================
// Failure Diagnosis Engine
// ============================================================================

export class FailureDiagnosisEngine {
  private diagnosisHistory: DiagnosisResult[] = [];
  private maxHistory = 200;

  // --- Core Diagnosis ---

  diagnose(
    actionId: string,
    verificationResults: readonly VerificationResult[],
    stateDiff: StateDiff | null,
    lifecycle: ActionLifecycle,
    context: DiagnosisContext = {},
  ): DiagnosisResult {
    const hypotheses: DiagnosticHypothesis[] = [];
    const evidence: string[] = [];

    // Generate hypotheses from verification failures
    this.generateVerificationHypotheses(verificationResults, hypotheses, evidence);

    // Generate hypotheses from state diff
    if (stateDiff) {
      this.generateStateDiffHypotheses(stateDiff, hypotheses, evidence);
    }

    // Generate hypotheses from lifecycle
    this.generateLifecycleHypotheses(lifecycle, hypotheses, evidence);

    // Generate hypotheses from context
    this.generateContextHypotheses(context, hypotheses, evidence);

    // Select best hypothesis
    const bestHypothesis = this.selectBestHypothesis(hypotheses);
    const failureClass = this.classifyFailureClass(bestHypothesis, verificationResults, stateDiff);
    const recoverability = this.assessRecoverability(failureClass, lifecycle, context);
    const recommendedRecovery = this.recommendRecovery(failureClass, recoverability, context);

    const result: DiagnosisResult = {
      actionId,
      failureClass,
      rootCause: bestHypothesis?.hypothesis ?? 'Unknown failure',
      evidence,
      confidence: bestHypothesis?.confidence ?? 0.3,
      recoverability,
      recommendedRecovery,
      hypotheses,
      timestamp: new Date().toISOString(),
    };

    this.diagnosisHistory.push(result);
    if (this.diagnosisHistory.length > this.maxHistory) this.diagnosisHistory.shift();

    return result;
  }

  // --- Hypothesis Generation ---

  private generateVerificationHypotheses(
    results: readonly VerificationResult[],
    hypotheses: DiagnosticHypothesis[],
    evidence: string[],
  ): void {
    for (const r of results) {
      if (r.status === 'FAILED') {
        // Target existence failure
        if (r.source === 'STRUCTURED_STATE' || r.source === 'ACCESSIBILITY') {
          if (r.expected.includes('exist') && !r.actual.includes('exist')) {
            hypotheses.push({
              hypothesis: 'Target element does not exist in the UI',
              confidence: 0.8,
              supportingEvidence: [r.evidence],
              contradictingEvidence: [],
            });
          }
        }

        // Visibility failure
        if (r.source === 'VISUAL' || r.source === 'OCR') {
          if (r.expected.includes('visible') && !r.actual.includes('visible')) {
            hypotheses.push({
              hypothesis: 'Target element is not visible (may be scrolled off or hidden)',
              confidence: 0.7,
              supportingEvidence: [r.evidence],
              contradictingEvidence: [],
            });
          }
        }

        // DOM failure
        if (r.source === 'DOM') {
          hypotheses.push({
            hypothesis: 'Page structure changed, DOM element not found',
            confidence: 0.75,
            supportingEvidence: [r.evidence],
            contradictingEvidence: [],
          });
        }

        // URL mismatch
        if (r.source === 'DOM' && r.expected.includes('url')) {
          hypotheses.push({
            hypothesis: 'Browser navigated to different page',
            confidence: 0.85,
            supportingEvidence: [r.evidence],
            contradictingEvidence: [],
          });
        }

        // Process state
        if (r.source === 'PROCESS' || r.source === 'OS_STATE') {
          if (r.evidence.toLowerCase().includes('focus') || r.expected.toLowerCase().includes('focus')) {
            hypotheses.push({
              hypothesis: 'Window focus was lost during action',
              confidence: 0.8,
              supportingEvidence: [r.evidence],
              contradictingEvidence: [],
            });
          } else {
            hypotheses.push({
              hypothesis: 'Application process is not running or not responsive',
              confidence: 0.8,
              supportingEvidence: [r.evidence],
              contradictingEvidence: [],
            });
          }
        }

        evidence.push(`Verification failed: ${r.source} — ${r.evidence}`);
      }

      if (r.status === 'CONTRADICTED') {
        evidence.push(`Conflicting signals: ${r.source} — ${r.evidence}`);
        hypotheses.push({
          hypothesis: 'Environment state is ambiguous — different sensors disagree',
          confidence: 0.5,
          supportingEvidence: [r.evidence],
          contradictingEvidence: [],
        });
      }
    }
  }

  private generateStateDiffHypotheses(
    diff: StateDiff,
    hypotheses: DiagnosticHypothesis[],
    evidence: string[],
  ): void {
    for (const change of diff.changes) {
      if (!change.material) continue;

      switch (change.type) {
        case 'WINDOW_CLOSED':
          hypotheses.push({
            hypothesis: `Target window closed: ${change.description}`,
            confidence: 0.85,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'WINDOW_MOVED':
          hypotheses.push({
            hypothesis: `Window moved, target coordinates may be stale: ${change.description}`,
            confidence: 0.8,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'ELEMENT_DISAPPEARED':
          hypotheses.push({
            hypothesis: `UI element disappeared: ${change.description}`,
            confidence: 0.8,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'URL_CHANGED':
          hypotheses.push({
            hypothesis: `Page navigation occurred: ${change.description}`,
            confidence: 0.9,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'PROCESS_EXITED':
          hypotheses.push({
            hypothesis: `Application process exited: ${change.description}`,
            confidence: 0.9,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'DIALOG_APPEARED':
          hypotheses.push({
            hypothesis: `Dialog appeared blocking interaction: ${change.description}`,
            confidence: 0.75,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'FOCUS_CHANGED':
          hypotheses.push({
            hypothesis: `Window focus changed: ${change.description}`,
            confidence: 0.7,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'FILE_DELETED':
          hypotheses.push({
            hypothesis: `File was deleted: ${change.description}`,
            confidence: 0.9,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
        case 'PROCESS_UNRESPONSIVE':
          hypotheses.push({
            hypothesis: `Application became unresponsive: ${change.description}`,
            confidence: 0.85,
            supportingEvidence: [change.description],
            contradictingEvidence: [],
          });
          break;
      }

      evidence.push(`State change: ${change.type} — ${change.description}`);
    }
  }

  private generateLifecycleHypotheses(
    lifecycle: ActionLifecycle,
    hypotheses: DiagnosticHypothesis[],
    evidence: string[],
  ): void {
    if (lifecycle.attempts >= lifecycle.maxAttempts) {
      hypotheses.push({
        hypothesis: `Maximum attempts (${lifecycle.maxAttempts}) exhausted`,
        confidence: 0.9,
        supportingEvidence: [`Attempts: ${lifecycle.attempts}/${lifecycle.maxAttempts}`],
        contradictingEvidence: [],
      });
    }

    // Check for repeated failures
    const recentTransitions = lifecycle.history.slice(-6);
    const failCount = recentTransitions.filter(t => t.to === 'FAILED').length;
    if (failCount >= 3) {
      hypotheses.push({
        hypothesis: 'Repeated failure pattern detected — possible systematic issue',
        confidence: 0.75,
        supportingEvidence: [`${failCount} failures in last ${recentTransitions.length} transitions`],
        contradictingEvidence: [],
      });
    }
  }

  private generateContextHypotheses(
    context: DiagnosisContext,
    hypotheses: DiagnosticHypothesis[],
    evidence: string[],
  ): void {
    if (context.userTookOver) {
      hypotheses.push({
        hypothesis: 'User took control during action',
        confidence: 0.9,
        supportingEvidence: ['User takeover detected'],
        contradictingEvidence: [],
      });
    }

    if (context.networkError) {
      hypotheses.push({
        hypothesis: 'Network connectivity issue',
        confidence: 0.8,
        supportingEvidence: ['Network error reported'],
        contradictingEvidence: [],
      });
    }

    if (context.providerError) {
      hypotheses.push({
        hypothesis: `Provider failure: ${context.providerError}`,
        confidence: 0.8,
        supportingEvidence: [context.providerError],
        contradictingEvidence: [],
      });
    }
  }

  // --- Hypothesis Selection ---

  private selectBestHypothesis(hypotheses: readonly DiagnosticHypothesis[]): DiagnosticHypothesis | null {
    if (hypotheses.length === 0) return null;

    return hypotheses.reduce((best, current) => {
      const bestScore = this.scoreHypothesis(best);
      const currentScore = this.scoreHypothesis(current);
      return currentScore > bestScore ? current : best;
    });
  }

  private scoreHypothesis(h: DiagnosticHypothesis): number {
    let score = h.confidence;
    score += h.supportingEvidence.length * 0.05;
    score -= h.contradictingEvidence.length * 0.1;
    return Math.max(0, score);
  }

  // --- Failure Classification ---

  private classifyFailureClass(
    hypothesis: DiagnosticHypothesis | null,
    verificationResults: readonly VerificationResult[],
    stateDiff: StateDiff | null,
  ): FailureClass {
    const hText = hypothesis?.hypothesis.toLowerCase() ?? '';

    if (hText.includes('target') && hText.includes('not') && hText.includes('exist')) return 'TARGET_NOT_FOUND';
    if (hText.includes('target') && hText.includes('stale')) return 'TARGET_STALE';
    if (hText.includes('target') && hText.includes('ambiguous')) return 'TARGET_AMBIGUOUS';
    if (hText.includes('focus') || hText.includes('window focus')) return 'FOCUS_LOST';
    if (hText.includes('window') && hText.includes('closed')) return 'WRONG_WINDOW';
    if (hText.includes('page') && hText.includes('navigation')) return 'UI_CHANGED';
    if (hText.includes('layout') || hText.includes('structure changed')) return 'UI_CHANGED';
    if (hText.includes('process') && hText.includes('exit')) return 'APP_CRASHED';
    if (hText.includes('process') && hText.includes('unresponsive')) return 'APP_NOT_READY';
    if (hText.includes('not running') || hText.includes('not ready')) return 'APP_NOT_READY';
    if (hText.includes('network')) return 'NETWORK_FAILURE';
    if (hText.includes('provider')) return 'PROVIDER_FAILURE';
    if (hText.includes('permission')) return 'PERMISSION';
    if (hText.includes('timeout')) return 'TIMEOUT';
    if (hText.includes('dialog')) return 'UI_CHANGED';
    if (hText.includes('file') && hText.includes('deleted')) return 'STATE_MISMATCH';
    if (hText.includes('verification') && hText.includes('conflict')) return 'VERIFICATION_FAILURE';
    if (hText.includes('attempt') && hText.includes('exhausted')) return 'TIMEOUT';

    // Check verification signals
    for (const r of verificationResults) {
      if (r.status === 'FAILED') {
        if (r.source === 'DOM') return 'UI_CHANGED';
        if (r.source === 'PROCESS') return 'APP_CRASHED';
        if (r.source === 'FILESYSTEM') return 'STATE_MISMATCH';
        if (r.source === 'OS_STATE') return 'WRONG_WINDOW';
      }
    }

    return 'UNKNOWN';
  }

  // --- Recoverability ---

  private assessRecoverability(
    failureClass: FailureClass,
    lifecycle: ActionLifecycle,
    context: DiagnosisContext,
  ): Recoverability {
    // Fatal cases
    if (failureClass === 'PERMISSION') return 'REQUIRES_USER';
    if (lifecycle.attempts >= lifecycle.maxAttempts) return 'REQUIRES_USER';

    // Auto-recoverable
    if (failureClass === 'TARGET_NOT_FOUND' || failureClass === 'TARGET_STALE') return 'AUTO_RECOVERABLE';
    if (failureClass === 'FOCUS_LOST') return 'AUTO_RECOVERABLE';
    if (failureClass === 'TIMEOUT') return 'AUTO_RECOVERABLE';
    if (failureClass === 'WRONG_WINDOW') return 'AUTO_RECOVERABLE';

    // Recoverable with replan
    if (failureClass === 'UI_CHANGED') return 'RECOVERABLE_WITH_REPLAN';
    if (failureClass === 'APP_CRASHED') return 'RECOVERABLE_WITH_REPLAN';
    if (failureClass === 'APP_NOT_READY') return 'RECOVERABLE_WITH_REPLAN';
    if (failureClass === 'PROVIDER_FAILURE') return 'RECOVERABLE_WITH_REPLAN';
    if (failureClass === 'NETWORK_FAILURE') return 'RECOVERABLE_WITH_REPLAN';

    // User needed
    if (failureClass === 'VERIFICATION_FAILURE') return 'RECOVERABLE_WITH_REPLAN';
    if (failureClass === 'STATE_MISMATCH') return 'RECOVERABLE_WITH_REPLAN';

    return 'RECOVERABLE_WITH_REPLAN';
  }

  // --- Recovery Recommendation ---

  private recommendRecovery(
    failureClass: FailureClass,
    recoverability: Recoverability,
    context: DiagnosisContext,
  ): string {
    if (recoverability === 'FATAL') return 'ABORT';
    if (recoverability === 'REQUIRES_USER') return 'ASK_USER';

    switch (failureClass) {
      case 'TARGET_NOT_FOUND': return 'RELOCATE_TARGET';
      case 'TARGET_STALE': return 'REOBSERVE';
      case 'TARGET_AMBIGUOUS': return 'RELOCATE_TARGET';
      case 'FOCUS_LOST': return 'REFOCUS';
      case 'WRONG_WINDOW': return 'REFOCUS';
      case 'UI_CHANGED': return 'RELOCATE_TARGET';
      case 'APP_NOT_READY': return 'RETRY';
      case 'APP_CRASHED': return 'REOPEN_APPLICATION';
      case 'NETWORK_FAILURE': return 'RETRY';
      case 'PROVIDER_FAILURE': return 'ALTERNATE_PROVIDER';
      case 'TIMEOUT': return 'REOBSERVE';
      case 'PERMISSION': return 'ASK_USER';
      case 'VERIFICATION_FAILURE': return 'REOBSERVE';
      case 'STATE_MISMATCH': return 'REFRESH_STATE';
      default: return 'REOBSERVE';
    }
  }

  // --- History ---

  getDiagnosisHistory(actionId?: string): readonly DiagnosisResult[] {
    if (actionId) return this.diagnosisHistory.filter(d => d.actionId === actionId);
    return this.diagnosisHistory;
  }

  getMostCommonFailureClass(): FailureClass | null {
    if (this.diagnosisHistory.length === 0) return null;
    const counts = new Map<FailureClass, number>();
    for (const d of this.diagnosisHistory) {
      counts.set(d.failureClass, (counts.get(d.failureClass) ?? 0) + 1);
    }
    let best: FailureClass | null = null;
    let bestCount = 0;
    for (const [cls, count] of counts) {
      if (count > bestCount) { best = cls; bestCount = count; }
    }
    return best;
  }

  clear(): void {
    this.diagnosisHistory = [];
  }
}

// ============================================================================
// Diagnosis Context
// ============================================================================

export interface DiagnosisContext {
  readonly userTookOver?: boolean;
  readonly networkError?: boolean;
  readonly providerError?: string;
  readonly applicationCrashed?: boolean;
  readonly budgetExceeded?: boolean;
  readonly recentFailures?: number;
  readonly targetMethod?: string;
  readonly verificationUnavailable?: boolean;
}
