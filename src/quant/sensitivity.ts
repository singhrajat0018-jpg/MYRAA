// ============================================================================
// MYRAA Phase 27 — Parameter Sensitivity & Overfitting Detection
// ============================================================================

import type {
  SensitivityResult, SensitivityPoint, OverfittingAnalysis,
  StrategyInstance, HistoricalDataset, CostModel, PerformanceMetrics,
} from './contracts';
import { BacktestEngine } from './backtest';
import { MetricsEngine } from './metrics';
import type { StrategyFunction } from './strategy';

export class SensitivityEngine {
  private readonly backtestEngine = new BacktestEngine();
  private readonly metricsEngine = new MetricsEngine();

  analyzeParameter(params: {
    dataset: HistoricalDataset;
    strategy: StrategyInstance;
    strategyFn: StrategyFunction;
    paramName: string;
    values: number[];
    metric?: keyof PerformanceMetrics;
    costModel?: CostModel;
    initialCapital?: number;
    riskFreeRate?: number;
  }): SensitivityResult {
    const { paramName, values, metric = 'sharpeRatio' } = params;
    const points: SensitivityPoint[] = [];
    for (const val of values) {
      const instance: StrategyInstance = {
        ...params.strategy,
        params: { ...params.strategy.params, [paramName]: val },
      };
      const result = this.backtestEngine.run({
        dataset: params.dataset, strategy: instance, strategyFn: params.strategyFn,
        costModel: params.costModel, initialCapital: params.initialCapital ?? 100_000,
        riskFreeRate: params.riskFreeRate ?? 0.0,
      });
      points.push({ paramName, paramValue: val, metric: result.metrics[metric] as number, trades: result.metrics.totalTrades });
    }
    const metricValues = points.map(p => p.metric);
    const sensitivity = this.computeSensitivityScore(metricValues);
    const sortedMetrics = [...metricValues].sort((a, b) => a - b);
    const median = sortedMetrics[Math.floor(sortedMetrics.length / 2)];
    const isCritical = sensitivity > 0.5;
    return {
      strategy: params.strategy,
      paramName,
      points: Object.freeze(points),
      range: { min: Math.min(...values), max: Math.max(...values) },
      sensitivity,
      isCritical,
    };
  }

  analyzeAll(params: {
    dataset: HistoricalDataset;
    strategy: StrategyInstance;
    strategyFn: StrategyFunction;
    parameterRanges: Record<string, number[]>;
    metric?: keyof PerformanceMetrics;
    costModel?: CostModel;
    initialCapital?: number;
    riskFreeRate?: number;
  }): SensitivityResult[] {
    const results: SensitivityResult[] = [];
    for (const [name, values] of Object.entries(params.parameterRanges)) {
      results.push(this.analyzeParameter({ ...params, paramName: name, values }));
    }
    return results;
  }

  detectOverfitting(params: {
    inSampleResult: PerformanceMetrics;
    outOfSampleResult: PerformanceMetrics;
    totalStrategiesTested: number;
    riskFreeRate?: number;
  }): OverfittingAnalysis {
    const { inSampleResult, outOfSampleResult, totalStrategiesTested, riskFreeRate = 0.0 } = params;
    const inSharpe = inSampleResult.sharpeRatio;
    const outSharpe = outOfSampleResult.sharpeRatio;
    const deflatedSharpe = this.deflatedSharpeRatio(inSharpe, totalStrategiesTested);
    const paramStability = Math.abs(inSharpe) > 0 ? Math.min(1, Math.abs(outSharpe / inSharpe)) : 0;
    const overfitProb = this.computeOverfitProbability(inSharpe, outSharpe, totalStrategiesTested);
    const isLikelyOverfit = overfitProb > 0.7;
    const warnings: string[] = [];
    if (isLikelyOverfit) warnings.push('High overfitting probability detected');
    if (paramStability < 0.3) warnings.push('Parameter stability is poor');
    if (Math.abs(inSharpe) > 3) warnings.push('In-sample Sharpe suspiciously high');
    if (outSharpe < 0 && inSharpe > 0) warnings.push('Out-of-sample Sharpe negative while in-sample positive');
    return {
      strategy: { definitionId: '', version: '', params: {} },
      inSampleSharpe: inSharpe,
      outOfSampleSharpe: outSharpe,
      deflatedSharpe,
      overfittingProbability: overfitProb,
      parameterStability: paramStability,
      isLikelyOverfit,
      warnings: Object.freeze(warnings),
    };
  }

  private computeSensitivityScore(values: number[]): number {
    if (values.length < 2) return 0;
    const mean = values.reduce((s, v) => s + v, 0) / values.length;
    const range = Math.max(...values) - Math.min(...values);
    const avgMag = values.reduce((s, v) => s + Math.abs(v - mean), 0) / values.length;
    return mean !== 0 ? Math.min(1, avgMag / (Math.abs(mean) + 0.001)) : range;
  }

  private deflatedSharpeRatio(sharpe: number, nStrategies: number): number {
    const eulerMascheroni = 0.5772156649;
    const maxExpectedSharpe = Math.sqrt(2 * Math.log(Math.max(nStrategies, 1))) - eulerMascheroni / Math.sqrt(2 * Math.log(Math.max(nStrategies, 1)));
    const stdMax = Math.max(0.01, Math.sqrt(1 - eulerMascheroni * Math.PI / 6 + eulerMascheroni * Math.log(Math.max(nStrategies, 1)) / (2 * Math.log(Math.max(nStrategies, 1)))));
    const z = stdMax > 0 ? (sharpe - maxExpectedSharpe) / stdMax : 0;
    return 1 - 0.5 * (1 + this.erf(z / Math.SQRT2));
  }

  private erf(x: number): number {
    const t = 1 / (1 + 0.3275911 * Math.abs(x));
    const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))));
    const val = 1 - poly * Math.exp(-x * x);
    return x >= 0 ? val : -val;
  }

  private computeOverfitProbability(inSharpe: number, outSharpe: number, nStrategies: number): number {
    const degradation = Math.abs(inSharpe) > 0 ? Math.max(0, 1 - outSharpe / Math.abs(inSharpe)) : 0;
    const multipleTestingPenalty = Math.min(1, nStrategies / 100);
    const reversalBonus = outSharpe < 0 && inSharpe > 0 ? 0.2 : 0;
    return Math.min(1, degradation * 0.6 + multipleTestingPenalty * 0.2 + reversalBonus);
  }
}
