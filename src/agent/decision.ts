// ============================================================================
// MYRAA Decision Engine — Multi-option scoring, uncertainty, trade-offs
// ============================================================================

import type {
  DecisionOption, DecisionResult, GatheredEvidence, VerificationStatus,
  Assumption, AgentEvent,
} from './contracts';
import { generateAgentId, nowISO } from './contracts';

// ============================================================================
// Decision Engine
// ============================================================================

export class DecisionEngine {
  private eventHandler?: (event: AgentEvent) => void;

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  evaluateDecision(
    question: string,
    options: readonly DecisionOption[],
    evidence: readonly GatheredEvidence[],
    assumptions: readonly Assumption[],
  ): DecisionResult {
    // Score each option
    const scoredOptions = options.map(opt => this.scoreOption(opt, evidence));

    // Find best option
    const bestOption = scoredOptions.reduce((best, opt) =>
      (opt.score || 0) > (best.score || 0) ? opt : best
    , scoredOptions[0]);

    // Collect uncertainties
    const uncertainties = this.collectUncertainties(evidence, assumptions);

    // Collect reasons
    const reasons = bestOption ? [
      `Selected ${bestOption.label} based on: ${bestOption.pros.join(', ')}`,
      `Score: ${bestOption.score?.toFixed(2) || 'N/A'}`,
    ] : ['Insufficient evidence to make a clear recommendation'];

    // Determine verification status
    const verificationStatus = this.determineVerificationStatus(evidence, uncertainties);

    // Build risks list
    const risks = scoredOptions.flatMap(opt => opt.risks);

    const result: DecisionResult = {
      decision: bestOption?.description || 'Unable to determine',
      options: scoredOptions,
      selectedOptionId: bestOption?.id,
      evidence,
      confidence: bestOption?.score || 0,
      uncertainties,
      assumptions,
      risks,
      reasons,
      recommendedAction: bestOption?.description,
      verificationStatus,
      timestamp: nowISO(),
    };

    this.emit({
      type: 'DECISION_MADE',
      agentId: 'system',
      timestamp: nowISO(),
      data: { optionCount: options.length, confidence: result.confidence },
    });

    return result;
  }

  // --- Scoring ---

  private scoreOption(option: DecisionOption, evidence: readonly GatheredEvidence[]): DecisionOption {
    let score = 0.5; // Base score

    // Boost for evidence support
    const supportingEvidence = evidence.filter(e =>
      option.evidence.some(oe => e.data === oe || JSON.stringify(e.data).includes(String(oe)))
    );
    score += supportingEvidence.length * 0.05;

    // Boost for pros
    score += option.pros.length * 0.03;

    // Penalty for cons
    score -= option.cons.length * 0.05;

    // Penalty for risks
    score -= option.risks.length * 0.08;

    // Penalty for unmet constraints
    score -= option.constraints.length * 0.02;

    // Clamp
    score = Math.max(0, Math.min(1, score));

    return { ...option, score };
  }

  private collectUncertainties(
    evidence: readonly GatheredEvidence[],
    assumptions: readonly Assumption[],
  ): string[] {
    const uncertainties: string[] = [];

    // Low confidence evidence
    const lowConfidence = evidence.filter(e => e.confidence < 0.5);
    if (lowConfidence.length > 0) {
      uncertainties.push(`${lowConfidence.length} sources have low confidence`);
    }

    // Low confidence assumptions
    const lowConfidenceAssumptions = assumptions.filter(a => a.status === 'ACTIVE' && a.confidence < 0.5);
    if (lowConfidenceAssumptions.length > 0) {
      uncertainties.push(`${lowConfidenceAssumptions.length} assumptions have low confidence`);
    }

    // Stale evidence
    const now = Date.now();
    const stale = evidence.filter(e => now - new Date(e.freshness).getTime() > 86400_000);
    if (stale.length > 0) {
      uncertainties.push(`${stale.length} evidence sources may be stale`);
    }

    // Insufficient evidence
    if (evidence.length < 2) {
      uncertainties.push('Limited evidence available');
    }

    return uncertainties;
  }

  private determineVerificationStatus(
    evidence: readonly GatheredEvidence[],
    uncertainties: readonly string[],
  ): VerificationStatus {
    if (evidence.length === 0) return 'NOT_VERIFIED';
    if (uncertainties.some(u => u.includes('Limited evidence'))) return 'PARTIAL';
    const avgConf = evidence.reduce((s, e) => s + e.confidence, 0) / evidence.length;
    if (avgConf >= 0.7) return 'VERIFIED';
    if (avgConf >= 0.4) return 'PARTIAL';
    return 'STALE';
  }

  // --- Option building helpers ---

  createOption(
    label: string,
    description: string,
    options: { pros?: string[]; cons?: string[]; risks?: string[]; constraints?: string[]; evidence?: string[] } = {},
  ): DecisionOption {
    return {
      id: generateAgentId('opt'),
      label,
      description,
      pros: options.pros || [],
      cons: options.cons || [],
      risks: options.risks || [],
      evidence: options.evidence || [],
      constraints: options.constraints || [],
      score: 0.5,
    };
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }
}
