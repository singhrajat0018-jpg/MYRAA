// ============================================================================
// MYRAA Phase 28 — Strategy Adaptation Engine
// Manages adaptation proposals, champion/challenger comparisons, and
// research-driven strategy evolution. NEVER triggers live execution.
// ============================================================================

import type {
  StrategyAdaptationProposal, AdaptationProposalStatus
} from './contracts';

export interface ValidationResult {
  readonly metric: string;
  readonly championValue: number;
  readonly challengerValue: number;
  readonly passed: boolean;
  readonly details: string;
}

export interface ChampionChallengerResult {
  readonly championId: string;
  readonly challengerId: string;
  readonly championScore: number;
  readonly challengerScore: number;
  readonly winner: 'CHAMPION' | 'CHALLENGER' | 'INCONCLUSIVE';
  readonly validations: ValidationResult[];
  readonly sampleSize: number;
  readonly evaluatedAt: string;
  readonly recommendation: string;
}

export class StrategyAdaptationEngine {
  private proposals = new Map<string, StrategyAdaptationProposal>();
  private comparisons = new Map<string, ChampionChallengerResult>();

  createProposal(params: {
    currentStrategyId: string;
    currentStrategyVersion: string;
    proposedChanges: Record<string, unknown>;
    problemStatement: string;
    evidence: string[];
    reasoning: string;
    championId?: string;
    challengerId?: string;
  }): StrategyAdaptationProposal {
    const id = `adapt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();
    const proposal: StrategyAdaptationProposal = {
      proposalId: id,
      currentStrategyId: params.currentStrategyId,
      currentStrategyVersion: params.currentStrategyVersion,
      proposedChanges: params.proposedChanges,
      problemStatement: params.problemStatement,
      evidence: params.evidence,
      reasoning: params.reasoning,
      validationRequired: {
        backtest: true,
        walkForward: true,
        outOfSample: true,
        costSensitivity: true,
        regimeRobustness: true,
      },
      status: 'PROPOSED',
      createdAt: now,
      updatedAt: now,
      championVsChallenger: params.championId && params.challengerId
        ? { champion: params.championId, challenger: params.challengerId }
        : null,
    };
    this.proposals.set(id, proposal);
    return proposal;
  }

  getProposal(proposalId: string): StrategyAdaptationProposal | undefined {
    return this.proposals.get(proposalId);
  }

  getAllProposals(): StrategyAdaptationProposal[] {
    return Array.from(this.proposals.values());
  }

  getProposalsByStatus(status: AdaptationProposalStatus): StrategyAdaptationProposal[] {
    return this.getAllProposals().filter(p => p.status === status);
  }

  updateStatus(proposalId: string, status: AdaptationProposalStatus): StrategyAdaptationProposal | undefined {
    const p = this.proposals.get(proposalId);
    if (!p) return undefined;
    const updated: StrategyAdaptationProposal = {
      ...p,
      status,
      updatedAt: new Date().toISOString(),
    };
    this.proposals.set(proposalId, updated);
    return updated;
  }

  deleteProposal(proposalId: string): boolean {
    return this.proposals.delete(proposalId);
  }

  compareChampionChallenger(params: {
    championId: string;
    challengerId: string;
    championMetrics: Record<string, number>;
    challengerMetrics: Record<string, number>;
    sampleSize: number;
  }): ChampionChallengerResult {
    const validations: ValidationResult[] = [];
    let championWins = 0;
    let challengerWins = 0;

    const metrics = ['totalReturn', 'sharpeRatio', 'maxDrawdown', 'calibrationError', 'sortinoRatio'];
    for (const metric of metrics) {
      const cv = params.championMetrics[metric] || 0;
      const chv = params.challengerMetrics[metric] || 0;

      let passed: boolean;
      let details: string;

      if (metric === 'maxDrawdown' || metric === 'calibrationError') {
        passed = chv <= cv;
        details = passed
          ? `Challenger lower ${metric}: ${chv.toFixed(4)} vs ${cv.toFixed(4)}`
          : `Champion better on ${metric}: ${cv.toFixed(4)} vs ${chv.toFixed(4)}`;
        if (passed) challengerWins++; else championWins++;
      } else {
        passed = chv >= cv;
        details = passed
          ? `Challenger higher ${metric}: ${chv.toFixed(4)} vs ${cv.toFixed(4)}`
          : `Champion better on ${metric}: ${cv.toFixed(4)} vs ${chv.toFixed(4)}`;
        if (passed) challengerWins++; else championWins++;
      }

      validations.push({ metric, championValue: cv, challengerValue: chv, passed, details });
    }

    const championScore = championWins / metrics.length;
    const challengerScore = challengerWins / metrics.length;

    let winner: 'CHAMPION' | 'CHALLENGER' | 'INCONCLUSIVE';
    let recommendation: string;

    if (params.sampleSize < 30) {
      winner = 'INCONCLUSIVE';
      recommendation = 'Insufficient sample size for reliable comparison';
    } else if (challengerScore >= 0.8 && challengerWins > championWins) {
      winner = 'CHALLENGER';
      recommendation = 'Challenger shows meaningful improvement across multiple metrics';
    } else if (championScore >= 0.8) {
      winner = 'CHAMPION';
      recommendation = 'Champion remains superior; challenger does not justify switching';
    } else {
      winner = 'INCONCLUSIVE';
      recommendation = 'Results are mixed; more data needed for reliable comparison';
    }

    const result: ChampionChallengerResult = {
      championId: params.championId,
      challengerId: params.challengerId,
      championScore,
      challengerScore,
      winner,
      validations,
      sampleSize: params.sampleSize,
      evaluatedAt: new Date().toISOString(),
      recommendation,
    };

    this.comparisons.set(`${params.championId}:${params.challengerId}`, result);
    return result;
  }

  getComparison(championId: string, challengerId: string): ChampionChallengerResult | undefined {
    return this.comparisons.get(`${championId}:${challengerId}`);
  }

  getAllComparisons(): ChampionChallengerResult[] {
    return Array.from(this.comparisons.values());
  }
}

export const strategyAdaptationEngine = new StrategyAdaptationEngine();
