// ============================================================================
// MYRAA Phase 28 — Learning System Health Engine
// Aggregates health across all learning subsystems into a unified view.
// ============================================================================

import type { FinancialIntelligenceHealth, DriftAlert } from './contracts';
import { strategyHealthEngine } from './strategyHealthEngine';
import { driftDetectionEngine } from './driftDetectionEngine';
import { researchQueueEngine } from './researchQueueEngine';
import { providerQualityEngine } from './providerQualityEngine';
import { forecastLifecycleManager } from './forecastLifecycleManager';

export type SystemHealthStatus = 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'UNKNOWN';

export interface LearningSystemHealth {
  readonly overallStatus: SystemHealthStatus;
  readonly forecastsPending: number;
  readonly forecastsEvaluated: number;
  readonly evaluationErrors: number;
  readonly calibrationHealth: number;
  readonly strategyHealth: number;
  readonly driftAlerts: number;
  readonly researchQueueLength: number;
  readonly providerHealth: number;
  readonly storageHealth: number;
  readonly lastUpdated: string;
}

export class LearningSystemHealthEngine {
  private errorCount = 0;

  incrementError(): void {
    this.errorCount++;
  }

  getHealth(): LearningSystemHealth {
    const forecasts = forecastLifecycleManager.getForecastsMap();
    const evaluations = forecastLifecycleManager.getEvaluationsMap();
    const queueLength = forecastLifecycleManager.getQueueLength();

    const strategies = strategyHealthEngine.getAllHealth();
    const avgStrategyHealth = strategies.length > 0
      ? strategies.reduce((s, h) => {
          const score = h.status === 'HEALTHY' ? 1
            : h.status === 'WATCH' ? 0.7
            : h.status === 'DEGRADED' ? 0.4
            : h.status === 'RESEARCH_ONLY' ? 0.3
            : h.status === 'RETIRED' ? 0
            : 0.5;
          return s + score;
        }, 0) / strategies.length
      : 0.5;

    const activeDriftAlerts = driftDetectionEngine.getActiveAlerts().length;

    const researchQueueLength = researchQueueEngine.getQueueLength();

    const providers = providerQualityEngine.getAllHealth();
    const avgProviderHealth = providers.length > 0
      ? providers.reduce((s, p) => s + p.reliabilityScore, 0) / providers.length
      : 0.5;

    const evaluatedCount = evaluations.size;
    const calibrationHealth = this.estimateCalibrationHealth();

    const storageHealth = forecasts.size > 0 ? Math.min(1, 1 - (this.errorCount / Math.max(1, forecasts.size))) : 1;

    const overallStatus = this.determineOverallStatus(
      avgStrategyHealth, activeDriftAlerts, avgProviderHealth, queueLength, this.errorCount
    );

    return {
      overallStatus,
      forecastsPending: queueLength,
      forecastsEvaluated: evaluatedCount,
      evaluationErrors: this.errorCount,
      calibrationHealth,
      strategyHealth: avgStrategyHealth,
      driftAlerts: activeDriftAlerts,
      researchQueueLength,
      providerHealth: avgProviderHealth,
      storageHealth,
      lastUpdated: new Date().toISOString(),
    };
  }

  private estimateCalibrationHealth(): number {
    const evaluations = Array.from(forecastLifecycleManager.getEvaluationsMap().values());
    if (evaluations.length < 5) return 0.5;

    const recent = evaluations.slice(-50);
    const avgConfidenceQuality = recent.reduce((s, e) => s + e.confidenceQuality, 0) / recent.length;
    return avgConfidenceQuality;
  }

  private determineOverallStatus(
    strategyHealth: number, driftAlerts: number,
    providerHealth: number, queueLength: number, errorCount: number
  ): SystemHealthStatus {
    if (errorCount > 10 || strategyHealth < 0.3 || providerHealth < 0.3) return 'DEGRADED';
    if (driftAlerts > 5 || strategyHealth < 0.5 || queueLength > 100) return 'WATCH';
    if (strategyHealth >= 0.5 && providerHealth >= 0.5) return 'HEALTHY';
    return 'UNKNOWN';
  }
}

export const learningSystemHealthEngine = new LearningSystemHealthEngine();
