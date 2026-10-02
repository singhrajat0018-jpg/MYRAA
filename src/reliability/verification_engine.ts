// ============================================================================
// MYRAA Phase 25 — Verification Engine: Hierarchy, Multi-Signal, Confidence
// ============================================================================

import type {
  VerificationResult, VerificationStatus, VerificationSource, VerificationLevel,
  MultiSignalVerification, VerificationConflict, StateSnapshot, StateDiff,
} from './contracts';

// ============================================================================
// Verification Engine
// ============================================================================

export class VerificationEngine {
  private results: Map<string, VerificationResult[]> = new Map();
  private reliabilityScores: Map<VerificationSource, number> = new Map();

  constructor() {
    // Default reliability scores (higher = more trusted)
    this.reliabilityScores.set('STRUCTURED_STATE', 0.95);
    this.reliabilityScores.set('DOM', 0.90);
    this.reliabilityScores.set('ACCESSIBILITY', 0.85);
    this.reliabilityScores.set('OS_STATE', 0.88);
    this.reliabilityScores.set('FILESYSTEM', 0.92);
    this.reliabilityScores.set('PROCESS', 0.88);
    this.reliabilityScores.set('VISUAL', 0.65);
    this.reliabilityScores.set('OCR', 0.60);
    this.reliabilityScores.set('WEAK_VISUAL', 0.40);
    this.reliabilityScores.set('API_RESPONSE', 0.80);
    this.reliabilityScores.set('WORLD_STATE', 0.70);
  }

  // --- Single Signal Verification ---

  verify(
    actionId: string,
    expected: string,
    actual: string,
    source: VerificationSource,
    level: VerificationLevel,
    evidence: string = '',
  ): VerificationResult {
    const status = this.classifyVerification(expected, actual, source);
    const confidence = this.computeConfidence(status, source, level);

    const result: VerificationResult = {
      actionId,
      status,
      confidence,
      source,
      evidence,
      expected,
      actual,
      timestamp: new Date().toISOString(),
      latencyMs: 0,
      level,
    };

    this.recordResult(result);
    return result;
  }

  // --- Multi-Signal Verification ---

  verifyMultiSignal(
    actionId: string,
    signals: readonly {
      source: VerificationSource;
      expected: string;
      actual: string;
      evidence?: string;
    }[],
    level: VerificationLevel,
  ): MultiSignalVerification {
    const results = signals.map(s =>
      this.verify(actionId, s.expected, s.actual, s.source, level, s.evidence ?? ''),
    );

    const conflicts = this.detectConflicts(results);
    const consensus = this.computeConsensus(results);
    const overallConfidence = this.computeOverallConfidence(results, level);

    const multi: MultiSignalVerification = {
      actionId,
      signals: results,
      consensus,
      overallConfidence,
      conflicts,
      timestamp: new Date().toISOString(),
    };

    return multi;
  }

  // --- Verification from State Diff ---

  verifyFromStateDiff(
    actionId: string,
    diff: StateDiff,
    expectedChangeTypes: readonly string[],
    level: VerificationLevel,
  ): VerificationResult {
    const actualTypes = diff.changes.map(c => c.type);
    const matched = expectedChangeTypes.some(t => actualTypes.includes(t as any));

    const status: VerificationStatus = matched
      ? 'VERIFIED'
      : diff.material
        ? 'PARTIALLY_VERIFIED'
        : 'UNVERIFIED';

    const confidence = this.computeConfidence(status, 'STRUCTURED_STATE', level);

    const result: VerificationResult = {
      actionId,
      status,
      confidence,
      source: 'STRUCTURED_STATE',
      evidence: `Expected changes: ${expectedChangeTypes.join(', ')}. Actual: ${actualTypes.join(', ')}`,
      expected: expectedChangeTypes.join(','),
      actual: actualTypes.join(','),
      timestamp: new Date().toISOString(),
      latencyMs: 0,
      level,
    };

    this.recordResult(result);
    return result;
  }

  // --- Classification ---

  private classifyVerification(expected: string, actual: string, source: VerificationSource): VerificationStatus {
    if (expected === actual) return 'VERIFIED';
    if (!expected || !actual) return 'UNVERIFIED';

    // Fuzzy match for text
    const expLower = expected.toLowerCase().trim();
    const actLower = actual.toLowerCase().trim();

    if (expLower === actLower) return 'VERIFIED';
    if (actLower.includes(expLower) || expLower.includes(actLower)) return 'PARTIALLY_VERIFIED';

    // Source-specific logic
    if (source === 'FILESYSTEM' || source === 'PROCESS' || source === 'OS_STATE') {
      // Binary: exists/not exists, running/not running
      return 'FAILED';
    }

    return 'FAILED';
  }

  // --- Confidence ---

  private computeConfidence(status: VerificationStatus, source: VerificationSource, level: VerificationLevel): number {
    const sourceReliability = this.reliabilityScores.get(source) ?? 0.5;

    let baseConfidence: number;
    switch (status) {
      case 'VERIFIED': baseConfidence = 0.95; break;
      case 'PARTIALLY_VERIFIED': baseConfidence = 0.65; break;
      case 'UNVERIFIED': baseConfidence = 0.30; break;
      case 'CONTRADICTED': baseConfidence = 0.10; break;
      case 'FAILED': baseConfidence = 0.15; break;
      case 'NOT_APPLICABLE': baseConfidence = 0.50; break;
      case 'VERIFICATION_UNAVAILABLE': baseConfidence = 0.0; break;
      default: baseConfidence = 0.30;
    }

    // Level multiplier: higher levels require higher confidence
    const levelMultiplier: Record<VerificationLevel, number> = {
      LIGHT: 0.8,
      NORMAL: 1.0,
      STRICT: 1.1,
      CRITICAL: 1.2,
    };

    return Math.min(1.0, baseConfidence * sourceReliability * (levelMultiplier[level] ?? 1.0));
  }

  private computeOverallConfidence(results: readonly VerificationResult[], level: VerificationLevel): number {
    if (results.length === 0) return 0;

    // Weighted average by source reliability
    let totalWeight = 0;
    let weightedSum = 0;

    for (const r of results) {
      const weight = this.reliabilityScores.get(r.source) ?? 0.5;
      weightedSum += r.confidence * weight;
      totalWeight += weight;
    }

    const avg = totalWeight > 0 ? weightedSum / totalWeight : 0;

    // Bonus for multiple agreeing signals
    const agreeingCount = results.filter(r => r.status === 'VERIFIED' || r.status === 'PARTIALLY_VERIFIED').length;
    const agreementBonus = results.length > 1 ? Math.min(0.1, (agreeingCount / results.length) * 0.1) : 0;

    return Math.min(1.0, avg + agreementBonus);
  }

  // --- Conflict Detection ---

  private detectConflicts(results: readonly VerificationResult[]): readonly VerificationConflict[] {
    const conflicts: VerificationConflict[] = [];

    for (let i = 0; i < results.length; i++) {
      for (let j = i + 1; j < results.length; j++) {
        const a = results[i];
        const b = results[j];

        if (a.status !== b.status && a.status !== 'UNVERIFIED' && b.status !== 'UNVERIFIED') {
          conflicts.push({
            sourceA: a.source,
            sourceB: b.source,
            statusA: a.status,
            statusB: b.status,
            description: `${a.source} says ${a.status}, ${b.source} says ${b.status}`,
          });
        }
      }
    }

    return conflicts;
  }

  private computeConsensus(results: readonly VerificationResult[]): VerificationStatus {
    if (results.length === 0) return 'UNVERIFIED';

    const statusCounts = new Map<VerificationStatus, number>();
    for (const r of results) {
      statusCounts.set(r.status, (statusCounts.get(r.status) ?? 0) + 1);
    }

    // Majority vote weighted by reliability
    let bestStatus: VerificationStatus = 'UNVERIFIED';
    let bestScore = 0;

    for (const [status, count] of statusCounts) {
      const relevantResults = results.filter(r => r.status === status);
      const avgReliability = relevantResults.reduce((sum, r) =>
        sum + (this.reliabilityScores.get(r.source) ?? 0.5), 0) / relevantResults.length;
      const score = count * avgReliability;

      if (score > bestScore) {
        bestScore = score;
        bestStatus = status;
      }
    }

    return bestStatus;
  }

  // --- Reliability Tracking ---

  updateSourceReliability(source: VerificationSource, observedAccuracy: number): void {
    const current = this.reliabilityScores.get(source) ?? 0.5;
    // Exponential moving average
    const updated = current * 0.8 + observedAccuracy * 0.2;
    this.reliabilityScores.set(source, Math.max(0.1, Math.min(0.99, updated)));
  }

  getSourceReliability(source: VerificationSource): number {
    return this.reliabilityScores.get(source) ?? 0.5;
  }

  // --- Results ---

  getResults(actionId: string): readonly VerificationResult[] {
    return this.results.get(actionId) ?? [];
  }

  getAllResults(): readonly VerificationResult[] {
    const all: VerificationResult[] = [];
    for (const results of this.results.values()) all.push(...results);
    return all;
  }

  private recordResult(result: VerificationResult): void {
    const existing = this.results.get(result.actionId) ?? [];
    existing.push(result);
    this.results.set(result.actionId, existing);
  }

  // --- Verdict Helpers ---

  isVerified(multi: MultiSignalVerification, minConfidence = 0.7): boolean {
    return multi.consensus === 'VERIFIED' && multi.overallConfidence >= minConfidence;
  }

  isFailed(multi: MultiSignalVerification): boolean {
    return multi.consensus === 'FAILED' || multi.consensus === 'CONTRADICTED';
  }

  hasConflicts(multi: MultiSignalVerification): boolean {
    return multi.conflicts.length > 0;
  }

  clear(): void {
    this.results.clear();
  }
}
