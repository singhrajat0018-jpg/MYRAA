// ============================================================================
// MYRAA Phase 28 — Provider Quality Engine
// Tracks data provider performance: availability, freshness, latency,
// error rate, accuracy, and conflict rate.
// ============================================================================

import type { FinancialProviderHealth } from './contracts';

export interface ProviderObservation {
  readonly providerId: string;
  readonly timestamp: string;
  readonly available: boolean;
  readonly latencyMs: number;
  readonly errorOccurred: boolean;
  readonly freshData: boolean;
  readonly correctData?: boolean;
  readonly conflictWithOther?: boolean;
}

export class ProviderQualityEngine {
  private health = new Map<string, FinancialProviderHealth>();
  private observations = new Map<string, ProviderObservation[]>();
  private readonly MAX_OBSERVATIONS = 500;

  recordObservation(obs: ProviderObservation): void {
    const list = this.observations.get(obs.providerId) || [];
    list.push(obs);
    if (list.length > this.MAX_OBSERVATIONS) list.shift();
    this.observations.set(obs.providerId, list);
    this.recomputeHealth(obs.providerId);
  }

  getHealth(providerId: string): FinancialProviderHealth | undefined {
    return this.health.get(providerId);
  }

  getAllHealth(): FinancialProviderHealth[] {
    return Array.from(this.health.values());
  }

  getObservations(providerId: string): ProviderObservation[] {
    return this.observations.get(providerId) || [];
  }

  getTopProviders(count: number = 5): FinancialProviderHealth[] {
    return this.getAllHealth()
      .sort((a, b) => b.reliabilityScore - a.reliabilityScore)
      .slice(0, count);
  }

  getDegradedProviders(): FinancialProviderHealth[] {
    return this.getAllHealth().filter(p => p.reliabilityScore < 0.5);
  }

  private recomputeHealth(providerId: string): void {
    const obs = this.observations.get(providerId) || [];
    if (obs.length === 0) return;

    const totalObs = obs.length;
    const availableObs = obs.filter(o => o.available).length;
    const freshObs = obs.filter(o => o.freshData).length;
    const errorObs = obs.filter(o => o.errorOccurred).length;
    const correctObs = obs.filter(o => o.correctData === true).length;
    const correctTotal = obs.filter(o => o.correctData !== undefined).length;
    const conflictObs = obs.filter(o => o.conflictWithOther).length;
    const latencies = obs.filter(o => o.latencyMs > 0).map(o => o.latencyMs);

    const availabilityScore = availableObs / totalObs;
    const freshnessScore = freshObs / totalObs;
    const accuracyScore = correctTotal > 0 ? correctObs / correctTotal : 0.5;
    const errorRate = errorObs / totalObs;
    const conflictRate = conflictObs / totalObs;
    const avgLatency = latencies.length > 0
      ? latencies.reduce((s, l) => s + l, 0) / latencies.length
      : 1000;
    const latencyScore = Math.max(0, 1 - Math.min(1, avgLatency / 5000));
    const schemaStabilityScore = 1 - conflictRate;

    const reliabilityScore = (
      availabilityScore * 0.25 +
      freshnessScore * 0.2 +
      accuracyScore * 0.25 +
      latencyScore * 0.1 +
      schemaStabilityScore * 0.1 +
      (1 - conflictRate) * 0.1
    );

    const providerType = this.guessProviderType(providerId);

    const health: FinancialProviderHealth = {
      providerId,
      providerType,
      freshnessScore,
      availabilityScore,
      accuracyScore,
      latencyScore,
      schemaStabilityScore,
      conflictRate,
      lastUpdated: obs[obs.length - 1].timestamp,
      sampleSize: totalObs,
      reliabilityScore,
    };

    this.health.set(providerId, health);
  }

  private guessProviderType(providerId: string): 'PRICE' | 'FUNDAMENTAL' | 'NEWS' | 'EVENT' | 'MACRO' {
    const lower = providerId.toLowerCase();
    if (lower.includes('price') || lower.includes('yahoo') || lower.includes('alpha') || lower.includes('quote')) return 'PRICE';
    if (lower.includes('news') || lower.includes('reuters') || lower.includes('bloomberg')) return 'NEWS';
    if (lower.includes('event') || lower.includes('earnings')) return 'EVENT';
    if (lower.includes('macro') || lower.includes('fed') || lower.includes('economic')) return 'MACRO';
    return 'FUNDAMENTAL';
  }
}

export const providerQualityEngine = new ProviderQualityEngine();
