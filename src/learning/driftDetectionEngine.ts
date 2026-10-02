// ============================================================================
// MYRAA Phase 28 — Drift Detection Engine
// Detects meaningful changes in performance, confidence, data, signals,
// regimes, providers, and calibration over configurable windows.
// ============================================================================

import type { DriftAlert } from './contracts';

export type DriftType = 'PERFORMANCE' | 'CONFIDENCE' | 'DATA' | 'SIGNAL' | 'REGIME' | 'MODEL' | 'PROVIDER' | 'CALIBRATION';
export type DriftSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface DriftConfig {
  readonly minSampleSize: number;
  readonly performanceThreshold: number;
  readonly confidenceThreshold: number;
  readonly dataMissingRateThreshold: number;
  readonly signalImbalanceThreshold: number;
  readonly regimeChangeThreshold: number;
  readonly cooldownMs: number;
}

const DEFAULT_CONFIG: DriftConfig = {
  minSampleSize: 20,
  performanceThreshold: 0.15,
  confidenceThreshold: 0.2,
  dataMissingRateThreshold: 0.3,
  signalImbalanceThreshold: 0.7,
  regimeChangeThreshold: 0.4,
  cooldownMs: 3600000,
};

export interface DataPoint {
  readonly value: number;
  readonly timestamp: string;
}

export class DriftDetectionEngine {
  private alerts: DriftAlert[] = [];
  private lastAlertByType = new Map<string, number>();
  private config: DriftConfig;

  constructor(config?: Partial<DriftConfig>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  getConfig(): DriftConfig {
    return { ...this.config };
  }

  getAllAlerts(): DriftAlert[] {
    return [...this.alerts];
  }

  getActiveAlerts(): DriftAlert[] {
    const cutoff = Date.now() - 24 * 3600 * 1000;
    return this.alerts.filter(a => new Date(a.detectedAt).getTime() > cutoff);
  }

  getAlertsByType(type: DriftType): DriftAlert[] {
    return this.alerts.filter(a => a.type === type);
  }

  clearAlerts(): void {
    this.alerts = [];
    this.lastAlertByType.clear();
  }

  detectPerformanceDrift(
    strategyId: string, recentEvals: boolean[], historicalRate: number
  ): DriftAlert | null {
    if (recentEvals.length < this.config.minSampleSize) return null;
    const recentRate = recentEvals.filter(Boolean).length / recentEvals.length;
    const change = historicalRate - recentRate;
    if (Math.abs(change) < this.config.performanceThreshold) return null;

    const severity = this.classifySeverity(Math.abs(change), this.config.performanceThreshold);
    const alert = this.createAlert('PERFORMANCE', severity, strategyId,
      `Performance drift: accuracy changed from ${(historicalRate * 100).toFixed(1)}% to ${(recentRate * 100).toFixed(1)}%`,
      'accuracy', recentRate, historicalRate, change,
      change > 0 ? 'Investigate strategy degradation causes' : 'Monitor for sustained improvement');
    this.alerts.push(alert);
    return alert;
  }

  detectConfidenceDrift(
    strategyId: string, confidences: number[], accuracies: number[]
  ): DriftAlert | null {
    if (confidences.length < this.config.minSampleSize) return null;
    const avgConf = confidences.reduce((s, c) => s + c, 0) / confidences.length;
    const avgAcc = accuracies.reduce((s, a) => s + a, 0) / accuracies.length;
    const gap = avgConf - avgAcc;
    if (Math.abs(gap) < this.config.confidenceThreshold) return null;

    const severity = this.classifySeverity(Math.abs(gap), this.config.confidenceThreshold);
    const direction = gap > 0 ? 'overconfident' : 'underconfident';
    const alert = this.createAlert('CONFIDENCE', severity, strategyId,
      `Confidence drift detected: system is ${direction} (avg confidence ${(avgConf * 100).toFixed(1)}% vs accuracy ${(avgAcc * 100).toFixed(1)}%)`,
      'confidence_vs_accuracy', avgConf, avgAcc, gap,
      gap > 0 ? 'Reduce forecast confidence levels' : 'Consider increasing confidence');
    this.alerts.push(alert);
    return alert;
  }

  detectDataDrift(
    sourceId: string, recentMissingRate: number, historicalMissingRate: number
  ): DriftAlert | null {
    const change = recentMissingRate - historicalMissingRate;
    if (change < this.config.dataMissingRateThreshold) return null;

    const severity = this.classifySeverity(change, this.config.dataMissingRateThreshold);
    const alert = this.createAlert('DATA', severity, sourceId,
      `Data quality drift: missing rate increased from ${(historicalMissingRate * 100).toFixed(1)}% to ${(recentMissingRate * 100).toFixed(1)}%`,
      'missing_rate', recentMissingRate, historicalMissingRate, change,
      'Check data provider health and fallback sources');
    this.alerts.push(alert);
    return alert;
  }

  detectSignalDrift(
    strategyId: string, recentSignalDirection: number, historicalSignalDirection: number
  ): DriftAlert | null {
    const change = Math.abs(recentSignalDirection - historicalSignalDirection);
    if (change < (1 - this.config.signalImbalanceThreshold)) return null;

    const severity = this.classifySeverity(change, 0.3);
    const alert = this.createAlert('SIGNAL', severity, strategyId,
      `Signal drift: direction imbalance shifted from ${(historicalSignalDirection * 100).toFixed(1)}% to ${(recentSignalDirection * 100).toFixed(1)}%`,
      'direction_imbalance', recentSignalDirection, historicalSignalDirection, change,
      'Review signal generation logic and market conditions');
    this.alerts.push(alert);
    return alert;
  }

  detectRegimeDrift(
    strategyId: string, currentRegimeRate: number, historicalRegimeRate: number
  ): DriftAlert | null {
    const change = Math.abs(currentRegimeRate - historicalRegimeRate);
    if (change < this.config.regimeChangeThreshold) return null;

    const severity = this.classifySeverity(change, this.config.regimeChangeThreshold);
    const alert = this.createAlert('REGIME', severity, strategyId,
      `Regime drift: regime distribution changed by ${(change * 100).toFixed(1)}%`,
      'regime_distribution', currentRegimeRate, historicalRegimeRate, change,
      'Review strategy regime适应性');
    this.alerts.push(alert);
    return alert;
  }

  detectCalibrationDrift(
    strategyId: string, recentECE: number, historicalECE: number
  ): DriftAlert | null {
    const change = recentECE - historicalECE;
    if (change < 0.05) return null;

    const severity = this.classifySeverity(change, 0.1);
    const alert = this.createAlert('CALIBRATION', severity, strategyId,
      `Calibration drift: ECE increased from ${historicalECE.toFixed(3)} to ${recentECE.toFixed(3)}`,
      'ece', recentECE, historicalECE, change,
      'Recalibrate confidence estimates');
    this.alerts.push(alert);
    return alert;
  }

  detectProviderDrift(
    providerId: string, recentAvailability: number, historicalAvailability: number
  ): DriftAlert | null {
    const change = historicalAvailability - recentAvailability;
    if (change < 0.15) return null;

    const severity = this.classifySeverity(change, 0.15);
    const alert = this.createAlert('PROVIDER', severity, providerId,
      `Provider drift: availability dropped from ${(historicalAvailability * 100).toFixed(1)}% to ${(recentAvailability * 100).toFixed(1)}%`,
      'availability', recentAvailability, historicalAvailability, change,
      'Check provider status and prepare fallback');
    this.alerts.push(alert);
    return alert;
  }

  detectChangePoint(data: number[], windowSize: number = 20): number[] {
    const changePoints: number[] = [];
    if (data.length < windowSize * 2) return changePoints;

    for (let i = windowSize; i < data.length - windowSize; i++) {
      const before = data.slice(i - windowSize, i);
      const after = data.slice(i, i + windowSize);
      const meanBefore = before.reduce((s, v) => s + v, 0) / before.length;
      const meanAfter = after.reduce((s, v) => s + v, 0) / after.length;
      const pooledVariance = (this.variance(before) + this.variance(after)) / 2;
      if (pooledVariance === 0) continue;
      const tStat = Math.abs(meanAfter - meanBefore) / Math.sqrt(pooledVariance * (2 / windowSize));
      if (tStat > 2.5) {
        changePoints.push(i);
      }
    }
    return changePoints;
  }

  private createAlert(
    type: DriftType, severity: DriftSeverity, source: string,
    description: string, metric: string, currentValue: number,
    historicalValue: number, changePercent: number, recommendedAction: string
  ): DriftAlert {
    const now = Date.now();
    const lastAlert = this.lastAlertByType.get(`${type}:${source}`) || 0;
    if (now - lastAlert < this.config.cooldownMs && severity !== 'CRITICAL') {
      return null as any;
    }
    this.lastAlertByType.set(`${type}:${source}`, now);

    return {
      alertId: `drift_${type.toLowerCase()}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      type,
      severity,
      description,
      detectedAt: new Date().toISOString(),
      metric,
      currentValue,
      historicalValue,
      changePercent: historicalValue !== 0 ? (changePercent / Math.abs(historicalValue)) * 100 : 0,
      confidence: Math.min(0.95, 0.5 + (this.config.minSampleSize / 100)),
      recommendedAction,
    };
  }

  private classifySeverity(magnitude: number, threshold: number): DriftSeverity {
    const ratio = magnitude / threshold;
    if (ratio >= 3) return 'CRITICAL';
    if (ratio >= 2) return 'HIGH';
    if (ratio >= 1.5) return 'MEDIUM';
    return 'LOW';
  }

  private variance(values: number[]): number {
    if (values.length < 2) return 0;
    const mean = values.reduce((s, v) => s + v, 0) / values.length;
    return values.reduce((s, v) => s + (v - mean) ** 2, 0) / (values.length - 1);
  }
}

export const driftDetectionEngine = new DriftDetectionEngine();
