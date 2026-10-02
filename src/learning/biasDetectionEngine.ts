// ============================================================================
// MYRAA Phase 28 — Bias Detection Engine
// Monitors for systematic biases in forecasts, research, and analysis.
// ============================================================================

export type BiasType =
  | 'BULLISH_BIAS'
  | 'BEARISH_BIAS'
  | 'CONFIDENCE_BIAS'
  | 'OVERTRADING'
  | 'ASSET_SELECTION_BIAS'
  | 'REGIME_BIAS'
  | 'RESEARCH_BIAS'
  | 'SURVIVORSHIP_BIAS'
  | 'LOOKAHEAD_BIAS'
  | 'CHERRY_PICKING';

export interface BiasAlert {
  readonly biasType: BiasType;
  readonly severity: 'LOW' | 'MEDIUM' | 'HIGH';
  readonly description: string;
  readonly metric: string;
  readonly currentValue: number;
  readonly expectedRange: [number, number];
  readonly sampleSize: number;
  readonly detectedAt: string;
}

export class BiasDetectionEngine {
  private alerts: BiasAlert[] = [];

  detectBullishBias(directions: ('UP' | 'DOWN' | 'FLAT')[]): BiasAlert | null {
    if (directions.length < 10) return null;
    const upCount = directions.filter(d => d === 'UP').length;
    const ratio = upCount / directions.length;
    if (ratio < 0.6) return null;
    return this.createAlert('BULLISH_BIAS', ratio > 0.75 ? 'HIGH' : 'MEDIUM',
      `Forecast direction is biased bullish: ${(ratio * 100).toFixed(1)}% UP predictions`,
      'up_ratio', ratio, [0.3, 0.6], directions.length);
  }

  detectBearishBias(directions: ('UP' | 'DOWN' | 'FLAT')[]): BiasAlert | null {
    if (directions.length < 10) return null;
    const downCount = directions.filter(d => d === 'DOWN').length;
    const ratio = downCount / directions.length;
    if (ratio < 0.6) return null;
    return this.createAlert('BEARISH_BIAS', ratio > 0.75 ? 'HIGH' : 'MEDIUM',
      `Forecast direction is biased bearish: ${(ratio * 100).toFixed(1)}% DOWN predictions`,
      'down_ratio', ratio, [0.3, 0.6], directions.length);
  }

  detectConfidenceBias(confidences: number[], accuracies: number[]): BiasAlert | null {
    if (confidences.length < 10) return null;
    const avgConf = confidences.reduce((s, c) => s + c, 0) / confidences.length;
    const avgAcc = accuracies.length > 0
      ? accuracies.reduce((s, a) => s + a, 0) / accuracies.length
      : 0.5;
    const gap = avgConf - avgAcc;
    if (Math.abs(gap) < 0.15) return null;
    return this.createAlert('CONFIDENCE_BIAS', Math.abs(gap) > 0.3 ? 'HIGH' : 'MEDIUM',
      gap > 0
        ? `Overconfidence: avg confidence ${(avgConf * 100).toFixed(1)}% vs accuracy ${(avgAcc * 100).toFixed(1)}%`
        : `Underconfidence: avg confidence ${(avgConf * 100).toFixed(1)}% vs accuracy ${(avgAcc * 100).toFixed(1)}%`,
      'confidence_gap', gap, [-0.15, 0.15], confidences.length);
  }

  detectOvertrading(signalsPerDay: number[], expectedSignalsPerDay: number = 5): BiasAlert | null {
    if (signalsPerDay.length < 5) return null;
    const avgSignals = signalsPerDay.reduce((s, v) => s + v, 0) / signalsPerDay.length;
    if (avgSignals <= expectedSignalsPerDay * 1.5) return null;
    return this.createAlert('OVERTRADING', avgSignals > expectedSignalsPerDay * 3 ? 'HIGH' : 'MEDIUM',
      `Signal frequency is high: ${avgSignals.toFixed(1)} signals/day vs expected ${expectedSignalsPerDay}`,
      'signals_per_day', avgSignals, [expectedSignalsPerDay * 0.5, expectedSignalsPerDay * 1.5], signalsPerDay.length);
  }

  detectAssetSelectionBias(assetsSelected: string[]): BiasAlert | null {
    if (assetsSelected.length < 10) return null;
    const assetCounts = new Map<string, number>();
    for (const a of assetsSelected) assetCounts.set(a, (assetCounts.get(a) || 0) + 1);
    const uniqueAssets = assetCounts.size;
    const maxConcentration = Math.max(...assetCounts.values()) / assetsSelected.length;
    if (uniqueAssets >= 5 && maxConcentration < 0.5) return null;
    return this.createAlert('ASSET_SELECTION_BIAS', maxConcentration > 0.8 ? 'HIGH' : 'MEDIUM',
      `Asset selection concentrated: ${uniqueAssets} unique assets, top concentration ${(maxConcentration * 100).toFixed(1)}%`,
      'concentration', maxConcentration, [0, 0.5], assetsSelected.length);
  }

  detectResearchBias(experimentsCount: number, successfulCount: number): BiasAlert | null {
    if (experimentsCount < 5) return null;
    const successRate = successfulCount / experimentsCount;
    if (successRate < 0.8) return null;
    return this.createAlert('RESEARCH_BIAS', successRate > 0.95 ? 'HIGH' : 'MEDIUM',
      `Research success rate suspiciously high: ${(successRate * 100).toFixed(1)}% (${successfulCount}/${experimentsCount})`,
      'research_success_rate', successRate, [0.3, 0.8], experimentsCount);
  }

  getAllAlerts(): BiasAlert[] {
    return [...this.alerts];
  }

  getAlertsByType(biasType: BiasType): BiasAlert[] {
    return this.alerts.filter(a => a.biasType === biasType);
  }

  clearAlerts(): void {
    this.alerts = [];
  }

  private createAlert(
    biasType: BiasType, severity: 'LOW' | 'MEDIUM' | 'HIGH',
    description: string, metric: string, currentValue: number,
    expectedRange: [number, number], sampleSize: number
  ): BiasAlert {
    const alert: BiasAlert = {
      biasType,
      severity,
      description,
      metric,
      currentValue,
      expectedRange,
      sampleSize,
      detectedAt: new Date().toISOString(),
    };
    this.alerts.push(alert);
    return alert;
  }
}

export const biasDetectionEngine = new BiasDetectionEngine();
