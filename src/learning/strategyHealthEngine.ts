// ============================================================================
// MYRAA Phase 28 — Strategy Health Engine
// Tracks per-strategy health across rolling windows, regimes, and horizons.
// ============================================================================

import type {
  StrategyHealth, StrategyHealthStatus, ForecastEvaluation,
  StrategyRegimeHorizonMatrix, RegimeType
} from './contracts';

const ALL_REGIMES: RegimeType[] = [
  'TRENDING_BULL', 'TRENDING_BEAR', 'RANGE', 'HIGH_VOLATILITY', 'LOW_VOLATILITY',
  'RISK_ON', 'RISK_OFF', 'MIXED', 'UNKNOWN',
];

export interface HealthEvaluation {
  readonly forecastId: string;
  readonly strategyId: string;
  readonly strategyVersion: string;
  readonly outcomeCorrect: boolean;
  readonly return: number;
  readonly regime: RegimeType;
  readonly horizon: string;
  readonly timestamp: string;
}

export class StrategyHealthEngine {
  private healthByStrategy = new Map<string, StrategyHealth>();
  private evaluationsByStrategy = new Map<string, HealthEvaluation[]>();
  private matrices = new Map<string, StrategyRegimeHorizonMatrix>();

  readonly windows: readonly number[] = [20, 50, 100, 250, 500];

  recordEvaluation(eval_: HealthEvaluation): void {
    const key = eval_.strategyId;
    const list = this.evaluationsByStrategy.get(key) || [];
    list.push(eval_);
    this.evaluationsByStrategy.set(key, list);
    this.recomputeHealth(eval_.strategyId, eval_.strategyVersion);
    this.updateMatrix(eval_);
  }

  getHealth(strategyId: string): StrategyHealth | undefined {
    return this.healthByStrategy.get(strategyId);
  }

  getAllHealth(): StrategyHealth[] {
    return Array.from(this.healthByStrategy.values());
  }

  getMatrix(strategyId: string): StrategyRegimeHorizonMatrix[] {
    return Array.from(this.matrices.values()).filter(m => m.strategyId === strategyId);
  }

  getEvaluations(strategyId: string): HealthEvaluation[] {
    return this.evaluationsByStrategy.get(strategyId) || [];
  }

  private recomputeHealth(strategyId: string, strategyVersion: string): void {
    const evals = this.evaluationsByStrategy.get(strategyId) || [];
    if (evals.length === 0) return;

    const sampleSize = evals.length;
    const recentWindow = evals.slice(-50);
    const recentAccuracy = this.accuracy(recentWindow);

    const rollingAccuracy = this.accuracy(evals.slice(-250));
    const previousRollingAccuracy = evals.length > 250
      ? this.accuracy(evals.slice(-500, -250))
      : rollingAccuracy;
    const accuracyTrend = rollingAccuracy - previousRollingAccuracy;

    const returns = evals.map(e => e.return);
    const averageReturn = returns.reduce((s, r) => s + r, 0) / returns.length;
    const returnVolatility = this.stddev(returns);
    const maxDrawdown = this.maxDrawdown(returns);
    const sharpeRatio = returnVolatility > 0 ? (averageReturn / returnVolatility) * Math.sqrt(252) : 0;
    const downsideReturns = returns.filter(r => r < 0);
    const downsideVol = downsideReturns.length > 0 ? this.stddev(downsideReturns) : 1e-9;
    const sortinoRatio = (averageReturn / downsideVol) * Math.sqrt(252);

    const regimePerformance: Record<RegimeType, number> = {} as Record<RegimeType, number>;
    const drawdownByRegime: Record<RegimeType, number> = {} as Record<RegimeType, number>;
    for (const regime of ALL_REGIMES) {
      const regimeEvals = evals.filter(e => e.regime === regime);
      regimePerformance[regime] = regimeEvals.length > 0 ? this.accuracy(regimeEvals) : 0;
      drawdownByRegime[regime] = regimeEvals.length > 0
        ? this.maxDrawdown(regimeEvals.map(e => e.return))
        : 0;
    }

    const failures = evals.filter(e => !e.outcomeCorrect);
    const failureRate = failures.length / sampleSize;
    const avgFailureMagnitude = failures.length > 0
      ? failures.reduce((s, e) => s + Math.abs(e.return), 0) / failures.length
      : 0;

    let successStreak = 0;
    let failureStreak = 0;
    for (let i = evals.length - 1; i >= 0; i--) {
      if (evals[i].outcomeCorrect) {
        if (failureStreak > 0) break;
        successStreak++;
      } else {
        if (successStreak > 0) break;
        failureStreak++;
      }
    }

    const status = this.determineStatus(sampleSize, recentAccuracy, accuracyTrend, failureRate, maxDrawdown);

    const health: StrategyHealth = {
      strategyId,
      strategyVersion,
      status,
      sampleSize,
      recentAccuracy,
      rollingAccuracy,
      accuracyTrend,
      averageReturn,
      returnVolatility,
      maxDrawdown,
      sharpeRatio,
      sortinoRatio,
      calibrationError: 0,
      confidenceQuality: 0,
      regimePerformance,
      drawdownByRegime,
      lastEvaluatedAt: evals[evals.length - 1].timestamp,
      evaluationCount: sampleSize,
      failureRate,
      avgFailureMagnitude,
      successStreak,
      failureStreak,
      dataQualityScore: Math.min(1, sampleSize / 50),
      providerReliability: {},
    };

    this.healthByStrategy.set(strategyId, health);
  }

  private determineStatus(
    sampleSize: number, recentAccuracy: number, accuracyTrend: number,
    failureRate: number, maxDrawdown: number
  ): StrategyHealthStatus {
    if (sampleSize < 10) return 'RESEARCH_ONLY';
    if (failureRate > 0.65 || maxDrawdown > 0.3) return 'UNRELIABLE';
    if (failureRate > 0.5 || (accuracyTrend < -0.15 && recentAccuracy < 0.5)) return 'DEGRADED';
    if (failureRate > 0.4 || accuracyTrend < -0.1) return 'WATCH';
    return 'HEALTHY';
  }

  private updateMatrix(eval_: HealthEvaluation): void {
    const key = `${eval_.strategyId}:${eval_.regime}:${eval_.horizon}`;
    const existing = this.matrices.get(key);
    if (existing) {
      existing.sampleSize++;
      const wasCorrect = existing.accuracy * (existing.sampleSize - 1);
      existing.accuracy = (wasCorrect + (eval_.outcomeCorrect ? 1 : 0)) / existing.sampleSize;
      const prevReturn = existing.averageReturn * (existing.sampleSize - 1);
      existing.averageReturn = (prevReturn + eval_.return) / existing.sampleSize;
    } else {
      this.matrices.set(key, {
        strategyId: eval_.strategyId,
        regime: eval_.regime,
        horizon: eval_.horizon as any,
        sampleSize: 1,
        accuracy: eval_.outcomeCorrect ? 1 : 0,
        averageReturn: eval_.return,
        maxDrawdown: 0,
        sharpeRatio: 0,
        calibrationError: 0,
      });
    }
  }

  private accuracy(evals: HealthEvaluation[]): number {
    if (evals.length === 0) return 0;
    return evals.filter(e => e.outcomeCorrect).length / evals.length;
  }

  private stddev(values: number[]): number {
    if (values.length < 2) return 0;
    const mean = values.reduce((s, v) => s + v, 0) / values.length;
    const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / (values.length - 1);
    return Math.sqrt(variance);
  }

  private maxDrawdown(returns: number[]): number {
    let peak = 0;
    let equity = 1;
    let maxDD = 0;
    for (const r of returns) {
      equity *= (1 + r);
      if (equity > peak) peak = equity;
      const dd = (peak - equity) / peak;
      if (dd > maxDD) maxDD = dd;
    }
    return maxDD;
  }
}

export const strategyHealthEngine = new StrategyHealthEngine();
