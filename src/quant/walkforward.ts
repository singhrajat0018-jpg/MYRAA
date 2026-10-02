// ============================================================================
// MYRAA Phase 27 — Walk-Forward Optimization Engine
// ============================================================================

import type {
  WalkForwardResult, WalkForwardWindow, WalkForwardOptimization,
  StrategyInstance, HistoricalDataset, CostModel, PerformanceMetrics,
  OHLCVBar,
} from './contracts';
import { BacktestEngine } from './backtest';
import { MetricsEngine } from './metrics';
import type { StrategyFunction, StrategyRegistry } from './strategy';

export class WalkForwardEngine {
  private readonly backtestEngine = new BacktestEngine();
  private readonly metricsEngine = new MetricsEngine();

  run(params: {
    dataset: HistoricalDataset;
    strategyId: string;
    strategyFn: StrategyFunction;
    registry: StrategyRegistry;
    paramGrid: Record<string, number[]>;
    trainBars: number;
    testBars: number;
    stepBars?: number;
    costModel?: CostModel;
    initialCapital?: number;
    riskFreeRate?: number;
    optimizationMetric?: keyof PerformanceMetrics;
  }): WalkForwardResult {
    const {
      dataset, strategyId, strategyFn, registry, paramGrid,
      trainBars, testBars, stepBars = testBars, costModel,
      initialCapital = 100_000, riskFreeRate = 0.0, optimizationMetric = 'sharpeRatio',
    } = params;
    const bars = dataset.bars;
    const windows: WalkForwardOptimization[] = [];
    let offset = 0;
    while (offset + trainBars + testBars <= bars.length) {
      const trainStart = offset;
      const trainEnd = offset + trainBars;
      const testStart = trainEnd;
      const testEnd = Math.min(trainEnd + testBars, bars.length);
      const trainBarsSlice = bars.slice(trainStart, trainEnd);
      const testBarsSlice = bars.slice(testStart, testEnd);
      const bestParams = this.optimizeParams({
        bars: trainBarsSlice, strategyFn, registry, strategyId, paramGrid,
        costModel, initialCapital, riskFreeRate, optimizationMetric,
      });
      const def = registry.getDefinition(strategyId);
      const trainInstance: StrategyInstance = {
        definitionId: strategyId,
        version: def?.version ?? '1.0.0',
        params: bestParams,
      };
      const trainDataset: HistoricalDataset = {
        ...dataset, id: `${dataset.id}-train-${offset}`,
        bars: Object.freeze(trainBarsSlice), totalBars: trainBarsSlice.length,
      };
      const testDataset: HistoricalDataset = {
        ...dataset, id: `${dataset.id}-test-${offset}`,
        bars: Object.freeze(testBarsSlice), totalBars: testBarsSlice.length,
      };
      const trainResult = this.backtestEngine.run({
        dataset: trainDataset, strategy: trainInstance, strategyFn,
        costModel, initialCapital, riskFreeRate,
      });
      const testResult = this.backtestEngine.run({
        dataset: testDataset, strategy: trainInstance, strategyFn,
        costModel, initialCapital, riskFreeRate,
      });
      windows.push({
        bestParams,
        trainMetrics: trainResult.metrics,
        testMetrics: testResult.metrics,
        window: {
          windowIndex: windows.length,
          trainStart: trainBarsSlice[0]?.timestamp ?? '',
          trainEnd: trainBarsSlice[trainBarsSlice.length - 1]?.timestamp ?? '',
          testStart: testBarsSlice[0]?.timestamp ?? '',
          testEnd: testBarsSlice[testBarsSlice.length - 1]?.timestamp ?? '',
          trainBars: trainBarsSlice.length,
          testBars: testBarsSlice.length,
        },
      });
      offset += stepBars;
    }
    const overallTestMetrics = this.aggregateMetrics(windows.map(w => w.testMetrics));
    const overallTrainMetrics = this.aggregateMetrics(windows.map(w => w.trainMetrics));
    const paramStability = this.computeParameterStability(windows);
    const overfittingScore = this.computeOverfittingScore(overallTrainMetrics, overallTestMetrics);
    const def = registry.getDefinition(strategyId);
    return {
      strategy: { definitionId: strategyId, version: def?.version ?? '1.0.0', params: {} },
      datasetId: dataset.id,
      windows: Object.freeze(windows),
      overallTestMetrics,
      overallTrainMetrics,
      parameterStability: paramStability,
      overfittingScore,
      totalTrainBars: windows.reduce((s, w) => s + w.window.trainBars, 0),
      totalTestBars: windows.reduce((s, w) => s + w.window.testBars, 0),
      timestamp: new Date().toISOString(),
    };
  }

  private optimizeParams(params: {
    bars: readonly OHLCVBar[];
    strategyFn: StrategyFunction;
    registry: StrategyRegistry;
    strategyId: string;
    paramGrid: Record<string, number[]>;
    costModel?: CostModel;
    initialCapital: number;
    riskFreeRate: number;
    optimizationMetric: keyof PerformanceMetrics;
  }): Record<string, number | boolean | string> {
    const combos = this.generateCombinations(params.paramGrid);
    let bestScore = -Infinity;
    let bestParams: Record<string, number | boolean | string> = {};
    for (const combo of combos) {
      const instance: StrategyInstance = {
        definitionId: params.strategyId,
        version: params.registry.getDefinition(params.strategyId)?.version ?? '1.0.0',
        params: combo,
      };
      const dataset: HistoricalDataset = {
        id: 'opt', symbol: '', timeframe: '1d',
        bars: params.bars as readonly OHLCVBar[], source: { provider: 'LOCAL', quality: 'PRIMARY', adjustment: 'NONE', verified: false },
        startDate: '', endDate: '', totalBars: params.bars.length, completeness: 1,
        hasLookAhead: false, survivorshipFiltered: false,
      };
      const result = this.backtestEngine.run({
        dataset, strategy: instance, strategyFn: params.strategyFn,
        costModel: params.costModel, initialCapital: params.initialCapital,
        riskFreeRate: params.riskFreeRate,
      });
      const score = result.metrics[params.optimizationMetric] as number;
      if (typeof score === 'number' && score > bestScore) {
        bestScore = score;
        bestParams = combo;
      }
    }
    return bestParams;
  }

  private generateCombinations(grid: Record<string, number[]>): Record<string, number | boolean | string>[] {
    const keys = Object.keys(grid);
    if (keys.length === 0) return [{}];
    const result: Record<string, number | boolean | string>[] = [{}];
    for (const key of keys) {
      const next: Record<string, number | boolean | string>[] = [];
      for (const existing of result) {
        for (const val of grid[key]) {
          next.push({ ...existing, [key]: val });
        }
      }
      result.length = 0;
      result.push(...next);
    }
    return result;
  }

  private aggregateMetrics(all: PerformanceMetrics[]): PerformanceMetrics {
    if (all.length === 0) return this.emptyMetrics();
    const avg = (fn: (m: PerformanceMetrics) => number) => all.reduce((s, m) => s + fn(m), 0) / all.length;
    return {
      totalReturn: avg(m => m.totalReturn),
      annualizedReturn: avg(m => m.annualizedReturn),
      sharpeRatio: avg(m => m.sharpeRatio),
      sortinoRatio: avg(m => m.sortinoRatio),
      calmarRatio: avg(m => m.calmarRatio),
      maxDrawdown: avg(m => m.maxDrawdown),
      maxDrawdownDuration: Math.max(...all.map(m => m.maxDrawdownDuration)),
      volatility: avg(m => m.volatility),
      downsideVolatility: avg(m => m.downsideVolatility),
      winRate: avg(m => m.winRate),
      avgWin: avg(m => m.avgWin),
      avgLoss: avg(m => m.avgLoss),
      profitFactor: avg(m => m.profitFactor),
      expectancy: avg(m => m.expectancy),
      totalTrades: all.reduce((s, m) => s + m.totalTrades, 0),
      avgHoldingBars: avg(m => m.avgHoldingBars),
      bestTrade: Math.max(...all.map(m => m.bestTrade)),
      worstTrade: Math.min(...all.map(m => m.worstTrade)),
      avgTrade: avg(m => m.avgTrade),
      consecutiveWins: Math.max(...all.map(m => m.consecutiveWins)),
      consecutiveLosses: Math.max(...all.map(m => m.consecutiveLosses)),
      longTrades: all.reduce((s, m) => s + m.longTrades, 0),
      shortTrades: all.reduce((s, m) => s + m.shortTrades, 0),
      longWinRate: avg(m => m.longWinRate),
      shortWinRate: avg(m => m.shortWinRate),
      skewness: avg(m => m.skewness),
      kurtosis: avg(m => m.kurtosis),
      tailRatio: avg(m => m.tailRatio),
      commonReturn: avg(m => m.commonReturn),
    };
  }

  private computeParameterStability(windows: WalkForwardOptimization[]): number {
    if (windows.length < 2) return 1;
    const paramNames = Object.keys(windows[0].bestParams);
    if (paramNames.length === 0) return 1;
    let totalStability = 0;
    for (const name of paramNames) {
      const values = windows.map(w => Number(w.bestParams[name]) || 0);
      const mean = values.reduce((s, v) => s + v, 0) / values.length;
      const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
      const cv = mean !== 0 ? Math.sqrt(variance) / Math.abs(mean) : 0;
      totalStability += Math.max(0, 1 - cv);
    }
    return totalStability / paramNames.length;
  }

  private computeOverfittingScore(train: PerformanceMetrics, test: PerformanceMetrics): number {
    if (train.sharpeRatio === 0) return 1;
    const ratio = test.sharpeRatio / train.sharpeRatio;
    return Math.max(0, 1 - ratio);
  }

  private emptyMetrics(): PerformanceMetrics {
    return {
      totalReturn: 0, annualizedReturn: 0, sharpeRatio: 0, sortinoRatio: 0,
      calmarRatio: 0, maxDrawdown: 0, maxDrawdownDuration: 0,
      volatility: 0, downsideVolatility: 0, winRate: 0, avgWin: 0,
      avgLoss: 0, profitFactor: 0, expectancy: 0, totalTrades: 0,
      avgHoldingBars: 0, bestTrade: 0, worstTrade: 0, avgTrade: 0,
      consecutiveWins: 0, consecutiveLosses: 0, longTrades: 0,
      shortTrades: 0, longWinRate: 0, shortWinRate: 0,
      skewness: 0, kurtosis: 0, tailRatio: 0, commonReturn: 0,
    };
  }
}

interface WalkForwardParams {
  bars: readonly OHLCVBar[];
  strategyFn: StrategyFunction;
  registry: StrategyRegistry;
  strategyId: string;
  paramGrid: Record<string, number[]>;
  costModel?: CostModel;
  initialCapital: number;
  riskFreeRate: number;
  optimizationMetric: keyof PerformanceMetrics;
}
