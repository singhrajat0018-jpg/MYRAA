// ============================================================================
// MYRAA Phase 27 — Forecast Evaluation & Calibration Engine
// ============================================================================

import type {
  CalibrationResult, CalibrationBin, ForecastRecord, ForecastOutcome,
} from './contracts';

export class CalibrationEngine {
  private readonly forecasts: ForecastRecord[] = [];
  private readonly outcomes: ForecastOutcome[] = [];

  recordForecast(forecast: ForecastRecord): void {
    this.forecasts.push(forecast);
  }

  recordOutcome(outcome: ForecastOutcome): void {
    this.outcomes.push(outcome);
  }

  getForecasts(): readonly ForecastRecord[] {
    return Object.freeze([...this.forecasts]);
  }

  getOutcomes(): readonly ForecastOutcome[] {
    return Object.freeze([...this.outcomes]);
  }

  clearHistory(): void {
    this.forecasts.length = 0;
    this.outcomes.length = 0;
  }

  evaluate(strategyId?: string): CalibrationResult {
    const matched = this.matchForecastsToOutcomes(strategyId);
    if (matched.length === 0) {
      return this.emptyResult(strategyId ?? '');
    }
    const totalForecasts = matched.length;
    const correct = matched.filter(m => m.outcome.correct).length;
    const overallAccuracy = correct / totalForecasts;
    const bins = this.buildCalibrationBins(matched);
    const ece = this.computeECE(bins);
    const mce = this.computeMCE(bins);
    const brierScore = this.computeBrierScore(matched);
    const logLoss = this.computeLogLoss(matched);
    const isWellCalibrated = ece < 0.05;
    const warnings: string[] = [];
    if (ece >= 0.1) warnings.push('High expected calibration error');
    if (mce >= 0.2) warnings.push('Severe miscalibration in at least one bin');
    if (brierScore > 0.3) warnings.push('Poor Brier score');
    if (totalForecasts < 30) warnings.push('Small sample size affects calibration reliability');
    return {
      strategyId: strategyId ?? '',
      totalForecasts,
      overallAccuracy,
      expectedCalibrationError: ece,
      maximumCalibrationError: mce,
      brierScore,
      logLoss,
      bins: Object.freeze(bins),
      isWellCalibrated,
      warnings: Object.freeze(warnings),
      timestamp: new Date().toISOString(),
    };
  }

  private matchForecastsToOutcomes(strategyId?: string): Array<{ forecast: ForecastRecord; outcome: ForecastOutcome }> {
    const result: Array<{ forecast: ForecastRecord; outcome: ForecastOutcome }> = [];
    const outcomeMap = new Map(this.outcomes.map(o => [o.forecastId, o]));
    for (const f of this.forecasts) {
      if (strategyId && f.strategyId !== strategyId) continue;
      const outcome = outcomeMap.get(f.forecastId);
      if (outcome) result.push({ forecast: f, outcome });
    }
    return result;
  }

  private buildCalibrationBins(matched: Array<{ forecast: ForecastRecord; outcome: ForecastOutcome }>): CalibrationBin[] {
    const binCount = 10;
    const bins: CalibrationBin[] = [];
    for (let i = 0; i < binCount; i++) {
      const binStart = i / binCount;
      const binEnd = (i + 1) / binCount;
      const binMid = (binStart + binEnd) / 2;
      const inBin = matched.filter(
        m => m.forecast.confidence >= binStart && m.forecast.confidence < binEnd,
      );
      const forecastCount = inBin.length;
      const avgConfidence = forecastCount > 0
        ? inBin.reduce((s, m) => s + m.forecast.confidence, 0) / forecastCount
        : binMid;
      const observedAccuracy = forecastCount > 0
        ? inBin.filter(m => m.outcome.correct).length / forecastCount
        : binMid;
      const expectedAccuracy = binMid;
      const miscalibration = Math.abs(observedAccuracy - expectedAccuracy);
      bins.push({ binStart, binEnd, binMid, forecastCount, avgConfidence, observedAccuracy, expectedAccuracy, miscalibration });
    }
    return bins;
  }

  private computeECE(bins: CalibrationBin[]): number {
    const total = bins.reduce((s, b) => s + b.forecastCount, 0);
    if (total === 0) return 0;
    return bins.reduce((s, b) => s + (b.forecastCount / total) * b.miscalibration, 0);
  }

  private computeMCE(bins: CalibrationBin[]): number {
    if (bins.length === 0) return 0;
    return Math.max(...bins.map(b => b.miscalibration));
  }

  private computeBrierScore(matched: Array<{ forecast: ForecastRecord; outcome: ForecastOutcome }>): number {
    if (matched.length === 0) return 1;
    const correct = matched.map(m => m.outcome.correct ? 1 : 0);
    const confidences = matched.map(m => m.forecast.confidence);
    return correct.reduce((s, c, i) => s + (confidences[i] - c) ** 2, 0) / matched.length;
  }

  private computeLogLoss(matched: Array<{ forecast: ForecastRecord; outcome: ForecastOutcome }>): number {
    if (matched.length === 0) return Infinity;
    const eps = 1e-15;
    let sum = 0;
    for (const m of matched) {
      const p = Math.min(1 - eps, Math.max(eps, m.forecast.confidence));
      const y = m.outcome.correct ? 1 : 0;
      sum += -(y * Math.log(p) + (1 - y) * Math.log(1 - p));
    }
    return sum / matched.length;
  }

  private emptyResult(strategyId: string): CalibrationResult {
    return {
      strategyId,
      totalForecasts: 0,
      overallAccuracy: 0,
      expectedCalibrationError: 0,
      maximumCalibrationError: 0,
      brierScore: 0,
      logLoss: 0,
      bins: Object.freeze([]),
      isWellCalibrated: false,
      warnings: Object.freeze(['No forecast-outcome pairs available']),
      timestamp: new Date().toISOString(),
    };
  }
}
