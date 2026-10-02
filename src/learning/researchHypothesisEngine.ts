// ============================================================================
// MYRAA Phase 28 — Research Hypothesis Engine
// Manages research hypotheses lifecycle from proposal to validation.
// ============================================================================

import type { ResearchHypothesis, HypothesisStatus } from './contracts';

export class ResearchHypothesisEngine {
  private hypotheses = new Map<string, ResearchHypothesis>();

  createHypothesis(params: {
    description: string;
    rationale: string;
    testablePrediction: string;
    sourceForecastId?: string;
    confidence?: number;
    evidenceFor?: string[];
    evidenceAgainst?: string[];
  }): ResearchHypothesis {
    const id = `hypo_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();
    const hypothesis: ResearchHypothesis = {
      hypothesisId: id,
      sourceForecastId: params.sourceForecastId,
      description: params.description,
      rationale: params.rationale,
      status: 'PROPOSED',
      createdAt: now,
      updatedAt: now,
      evidenceFor: params.evidenceFor || [],
      evidenceAgainst: params.evidenceAgainst || [],
      testablePrediction: params.testablePrediction,
      confidence: params.confidence || 0.5,
      experimentId: undefined,
      sampleSize: 0,
    };
    this.hypotheses.set(id, hypothesis);
    return hypothesis;
  }

  getHypothesis(hypothesisId: string): ResearchHypothesis | undefined {
    return this.hypotheses.get(hypothesisId);
  }

  getAllHypotheses(): ResearchHypothesis[] {
    return Array.from(this.hypotheses.values());
  }

  getHypothesesByStatus(status: HypothesisStatus): ResearchHypothesis[] {
    return this.getAllHypotheses().filter(h => h.status === status);
  }

  updateStatus(hypothesisId: string, status: HypothesisStatus): ResearchHypothesis | undefined {
    const h = this.hypotheses.get(hypothesisId);
    if (!h) return undefined;
    const updated: ResearchHypothesis = {
      ...h,
      status,
      updatedAt: new Date().toISOString(),
    };
    this.hypotheses.set(hypothesisId, updated);
    return updated;
  }

  linkExperiment(hypothesisId: string, experimentId: string): ResearchHypothesis | undefined {
    const h = this.hypotheses.get(hypothesisId);
    if (!h) return undefined;
    const updated: ResearchHypothesis = {
      ...h,
      experimentId,
      status: 'TESTING',
      updatedAt: new Date().toISOString(),
    };
    this.hypotheses.set(hypothesisId, updated);
    return updated;
  }

  addEvidence(hypothesisId: string, evidence: string, isSupporting: boolean): ResearchHypothesis | undefined {
    const h = this.hypotheses.get(hypothesisId);
    if (!h) return undefined;
    const updated: ResearchHypothesis = {
      ...h,
      evidenceFor: isSupporting ? [...h.evidenceFor, evidence] : h.evidenceFor,
      evidenceAgainst: !isSupporting ? [...h.evidenceAgainst, evidence] : h.evidenceAgainst,
      sampleSize: h.sampleSize + 1,
      updatedAt: new Date().toISOString(),
    };
    this.hypotheses.set(hypothesisId, updated);
    return updated;
  }

  evaluateHypothesis(hypothesisId: string, supported: boolean, pValue?: number): ResearchHypothesis | undefined {
    const h = this.hypotheses.get(hypothesisId);
    if (!h) return undefined;
    const status: HypothesisStatus = supported ? 'SUPPORTED' : 'REFUTED';
    const updated: ResearchHypothesis = {
      ...h,
      status,
      pValue,
      confidence: supported ? Math.min(0.95, h.confidence + 0.1) : Math.max(0.05, h.confidence - 0.2),
      updatedAt: new Date().toISOString(),
    };
    this.hypotheses.set(hypothesisId, updated);
    return updated;
  }

  expireHypothesis(hypothesisId: string): ResearchHypothesis | undefined {
    return this.updateStatus(hypothesisId, 'INCONCLUSIVE');
  }

  deleteHypothesis(hypothesisId: string): boolean {
    return this.hypotheses.delete(hypothesisId);
  }

  getActiveHypotheses(): ResearchHypothesis[] {
    return this.getAllHypotheses().filter(h =>
      h.status === 'PROPOSED' || h.status === 'TESTING'
    );
  }

  getValidatedHypotheses(): ResearchHypothesis[] {
    return this.getHypothesesByStatus('SUPPORTED');
  }

  getRefutedHypotheses(): ResearchHypothesis[] {
    return this.getHypothesesByStatus('REFUTED');
  }
}

export const researchHypothesisEngine = new ResearchHypothesisEngine();
