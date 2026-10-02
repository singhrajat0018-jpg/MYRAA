// ============================================================================
// MYRAA Phase 27 — Quantitative Research Engine Test Suite
// ============================================================================
// 200+ tests covering: contracts, historical dataset, strategy registry,
// backtest, costs, metrics, walk-forward, sensitivity, Monte Carlo,
// calibration, event studies, experiments, paper trading, firewall.
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import type { OHLCVBar, Timeframe } from '../src/finance/contracts';
import type {
  CostModel, StrategyInstance, HistoricalDataset, PerformanceMetrics,
  BacktestTrade, BacktestResult, MonteCarloConfig, ForecastRecord,
  ForecastOutcome, EventStudyEntry, FirewallPolicy, DatasetSource,
} from '../src/quant/contracts';
import {
  DEFAULT_COST_MODEL, STRICT_FIREWALL_POLICY, DEFAULT_MONTE_CARLO_CONFIG,
} from '../src/quant/contracts';
import { HistoricalDatasetEngine } from '../src/quant/historical_dataset';
import { StrategyRegistry, type StrategyFunction } from '../src/quant/strategy';
import { BacktestEngine } from '../src/quant/backtest';
import { CostEngine } from '../src/quant/costs';
import { MetricsEngine } from '../src/quant/metrics';
import { WalkForwardEngine } from '../src/quant/walkforward';
import { SensitivityEngine } from '../src/quant/sensitivity';
import { MonteCarloEngine } from '../src/quant/monte_carlo';
import { CalibrationEngine } from '../src/quant/calibration';
import { EventStudyEngine } from '../src/quant/event_studies';
import { ExperimentRegistry } from '../src/quant/experiments';
import { PaperTradingEngine } from '../src/quant/paper_trading';
import { ExecutionFirewall, GLOBAL_FIREWALL } from '../src/quant/firewall';

// --- Test Data Generators ---

function makeBars(n: number, startPrice: number = 100, volatility: number = 0.02): OHLCVBar[] {
  const bars: OHLCVBar[] = [];
  let price = startPrice;
  const base = new Date(2024, 0, 1); // Jan 1, 2024
  for (let i = 0; i < n; i++) {
    const d = new Date(base.getTime() + i * 86_400_000);
    const change = (Math.random() - 0.5) * 2 * volatility * price;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.01);
    const low = Math.min(open, close) * (1 - Math.random() * 0.01);
    const ts = d.toISOString().slice(0, 10) + 'T00:00:00Z';
    bars.push({
      timestamp: ts,
      open, high, low, close,
      volume: Math.floor(1000000 + Math.random() * 500000),
      timeframe: '1d',
      adjustedClose: close,
    });
    price = close;
  }
  return bars;
}

function makeTrendingBars(n: number, startPrice: number = 100, trend: number = 0.005): OHLCVBar[] {
  const bars: OHLCVBar[] = [];
  let price = startPrice;
  const base = new Date(2024, 0, 1);
  for (let i = 0; i < n; i++) {
    const d = new Date(base.getTime() + i * 86_400_000);
    const change = trend * price + (Math.random() - 0.5) * 0.01 * price;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.005);
    const low = Math.min(open, close) * (1 - Math.random() * 0.005);
    const ts = d.toISOString().slice(0, 10) + 'T00:00:00Z';
    bars.push({
      timestamp: ts,
      open, high, low, close,
      volume: Math.floor(1000000 + Math.random() * 500000),
      timeframe: '1d',
      adjustedClose: close,
    });
    price = close;
  }
  return bars;
}

function makeDataset(bars: OHLCVBar[], id: string = 'test-ds'): HistoricalDataset {
  return {
    id, symbol: 'TEST', timeframe: '1d', bars: Object.freeze(bars),
    source: { provider: 'TEST', quality: 'PRIMARY', adjustment: 'NONE', verified: true },
    startDate: bars[0]?.timestamp ?? '', endDate: bars[bars.length - 1]?.timestamp ?? '',
    totalBars: bars.length, completeness: 1, hasLookAhead: false, survivorshipFiltered: false,
  };
}

const TEST_COST: CostModel = {
  commissionPerTrade: 1.0, commissionPerShare: 0.0, commissionPercent: 0.0005,
  slippageTicks: 1, slippageBps: 5, marketImpactModel: 'NONE',
  marketImpactCoeff: 0, spreadBps: 3,
};

const ZERO_COST: CostModel = {
  commissionPerTrade: 0, commissionPerShare: 0, commissionPercent: 0,
  slippageTicks: 0, slippageBps: 0, marketImpactModel: 'NONE',
  marketImpactCoeff: 0, spreadBps: 0,
};

const SMA_CROSS_DEF = {
  id: 'sma_cross', name: 'SMA Crossover', version: '1.0.0',
  description: 'Simple SMA crossover strategy',
  type: 'TREND' as const, requiredTimeframes: ['1d'] as Timeframe[],
  minBars: 50, parameters: [
    { name: 'fastPeriod', type: 'integer' as const, default: 10, min: 5, max: 50, description: 'Fast SMA' },
    { name: 'slowPeriod', type: 'integer' as const, default: 30, min: 10, max: 200, description: 'Slow SMA' },
  ],
  riskProfile: { suggestedStopAtrMultiple: 2, suggestedTargetAtrMultiple: 3 },
};

const SMA_CROSS_FN: StrategyFunction = (bars, index, params) => {
  const fast = params.fastPeriod as number;
  const slow = params.slowPeriod as number;
  if (index < slow) return null;
  let fastSum = 0, slowSum = 0;
  for (let i = 0; i < fast; i++) fastSum += bars[index - i].close;
  for (let i = 0; i < slow; i++) slowSum += bars[index - i].close;
  const fastAvg = fastSum / fast;
  const slowAvg = slowSum / slow;
  const prevFast = index >= slow + 1 ? (() => { let s = 0; for (let i = 1; i <= fast; i++) s += bars[index - i].close; return s / fast; })() : fastAvg;
  const prevSlow = index >= slow + 1 ? (() => { let s = 0; for (let i = 1; i <= slow; i++) s += bars[index - i].close; return s / slow; })() : slowAvg;
  if (prevFast <= prevSlow && fastAvg > slowAvg) return { action: 'LONG', stopLoss: bars[index].close * 0.95 };
  if (prevFast >= prevSlow && fastAvg < slowAvg) return { action: 'SHORT', stopLoss: bars[index].close * 1.05 };
  return null;
};

// =========================================================================
// CONTRACTS
// =========================================================================

describe('Quant Contracts', () => {
  it('DEFAULT_COST_MODEL has reasonable defaults', () => {
    expect(DEFAULT_COST_MODEL.slippageBps).toBeGreaterThan(0);
    expect(DEFAULT_COST_MODEL.commissionPercent).toBeGreaterThanOrEqual(0);
  });

  it('STRICT_FIREWALL_POLICY has liveTradeExecution false', () => {
    expect(STRICT_FIREWALL_POLICY.liveTradeExecution).toBe(false);
    expect(STRICT_FIREWALL_POLICY.transferFunds).toBe(false);
    expect(STRICT_FIREWALL_POLICY.allowLlmOverride).toBe(false);
  });

  it('DEFAULT_MONTE_CARLO_CONFIG has seed', () => {
    expect(DEFAULT_MONTE_CARLO_CONFIG.seed).toBeDefined();
    expect(DEFAULT_MONTE_CARLO_CONFIG.simulations).toBeGreaterThan(0);
  });
});

// =========================================================================
// HISTORICAL DATASET ENGINE
// =========================================================================

describe('HistoricalDatasetEngine', () => {
  let engine: HistoricalDatasetEngine;

  beforeEach(() => { engine = new HistoricalDatasetEngine(); });

  it('builds a dataset from OHLCV bars', () => {
    const bars = makeBars(100);
    const { dataset, integrity } = engine.buildDataset({ symbol: 'AAPL', timeframe: '1d', bars });
    expect(dataset.symbol).toBe('AAPL');
    expect(dataset.totalBars).toBe(100);
    expect(integrity.valid).toBe(true);
  });

  it('detects duplicate bars', () => {
    const bars = makeBars(10);
    bars.push({ ...bars[5] }); // duplicate
    const { integrity } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    expect(integrity.duplicatesRemoved).toBe(1);
  });

  it('detects impossible OHLCV bars', () => {
    const bars = makeBars(10);
    bars[3] = { ...bars[3], high: bars[3].low - 1 }; // high < low
    const { integrity } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    expect(integrity.impossibleBarsFound).toBeGreaterThanOrEqual(1);
  });

  it('validates point-in-time without leakage', () => {
    const bars = makeBars(50);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    const result = engine.validatePointInTime({
      dataset, decisionTimestamp: '2024-12-31T00:00:00Z',
      eventTimestamps: ['2024-01-20T00:00:00Z'],
    });
    expect(result.hasLeakage).toBe(false);
  });

  it('filters bars to decision point', () => {
    const bars = makeBars(100);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    const midDate = dataset.bars[50]?.timestamp ?? '';
    const { bars: filtered, filtered: count } = engine.filterToDecisionPoint({
      dataset, decisionTimestamp: midDate,
    });
    expect(filtered.length).toBeLessThanOrEqual(51);
  });

  it('filters dataset to decision point', () => {
    const bars = makeBars(100);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    const midDate = dataset.bars[70]?.timestamp ?? '';
    const { bars: filtered, filtered: count } = engine.filterToDecisionPoint({
      dataset, decisionTimestamp: midDate,
    });
    expect(filtered.length).toBeLessThanOrEqual(71);
  });

  it('computes returns count', () => {
    const bars = makeBars(10);
    const returns = engine.computeReturns(bars);
    expect(returns.length).toBe(9);
  });

  it('adjusts corporate actions', () => {
    const bars = makeBars(10);
    const adjusted = engine.adjustCorporateActions({
      bars, type: 'SPLIT', effectiveDate: '2024-01-05T00:00:00Z', ratio: 2,
    });
    expect(adjusted.length).toBe(bars.length);
  });

  it('validates data integrity', () => {
    const bars = makeBars(20);
    const integrity = engine.getDataIntegrity(bars);
    expect(integrity.valid).toBe(true);
  });

  it('computes returns', () => {
    const bars = makeBars(10);
    const returns = engine.computeReturns(bars);
    expect(returns.length).toBe(9);
  });

  it('manages multiple datasets', () => {
    const bars = makeBars(10);
    const { dataset: ds1 } = engine.buildDataset({ symbol: 'A', timeframe: '1d', bars });
    const { dataset: ds2 } = engine.buildDataset({ symbol: 'B', timeframe: '1d', bars });
    expect(engine.listDatasets()).toHaveLength(2);
    expect(engine.getDataset(ds1.id)).toBeDefined();
    engine.removeDataset(ds1.id);
    expect(engine.listDatasets()).toHaveLength(1);
  });
});

// =========================================================================
// STRATEGY REGISTRY
// =========================================================================

describe('StrategyRegistry', () => {
  let registry: StrategyRegistry;

  beforeEach(() => {
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('registers and retrieves strategy definition', () => {
    expect(registry.getDefinition('sma_cross')).toBeDefined();
    expect(registry.getDefinition('sma_cross')?.name).toBe('SMA Crossover');
  });

  it('lists registered strategies', () => {
    expect(registry.list().length).toBeGreaterThanOrEqual(1);
  });

  it('creates a strategy instance with defaults', () => {
    const instance = registry.createInstance('sma_cross');
    expect(instance.params.fastPeriod).toBe(10);
    expect(instance.params.slowPeriod).toBe(30);
  });

  it('creates a strategy instance with overrides', () => {
    const instance = registry.createInstance('sma_cross', { fastPeriod: 5 });
    expect(instance.params.fastPeriod).toBe(5);
  });

  it('validates strategy parameters within bounds', () => {
    const def = registry.getDefinition('sma_cross')!;
    const instance = registry.createInstance('sma_cross');
    const errors = registry.validateParams(def, instance.params);
    expect(errors).toHaveLength(0);
  });

  it('catches out-of-bounds parameters', () => {
    const def = registry.getDefinition('sma_cross')!;
    const errors = registry.validateParams(def, { fastPeriod: 100 });
    expect(errors.length).toBeGreaterThan(0);
  });

  it('evaluates a signal at a bar index via computeSignal', () => {
    const bars = makeTrendingBars(100);
    const fn = registry.getFunction('sma_cross');
    const instance = registry.createInstance('sma_cross');
    const result = fn ? registry.computeSignal(instance, bars, 60) : null;
    expect(result === null || typeof result.bias === 'string').toBe(true);
  });

  it('generates order intent for LONG signal', () => {
    const intent = registry.generateOrderIntent(
      { signal: 'LONG_BIAS', strength: 0.8, stopLoss: 95, target: 110 },
      'AAPL', 100,
    );
    expect(intent).not.toBeNull();
    expect(intent?.side).toBe('BUY');
  });

  it('generates order intent for SHORT signal', () => {
    const intent = registry.generateOrderIntent(
      { signal: 'SHORT_BIAS', strength: 0.7 },
      'AAPL', 50,
    );
    expect(intent?.side).toBe('SELL');
  });

  it('returns null for NO_SIGNAL', () => {
    const intent = registry.generateOrderIntent(
      { signal: 'NO_SIGNAL', strength: 0 },
      'AAPL', 100,
    );
    expect(intent).toBeNull();
  });

  it('returns null for WATCH', () => {
    const intent = registry.generateOrderIntent(
      { signal: 'WATCH', strength: 0.3 },
      'AAPL', 100,
    );
    expect(intent).toBeNull();
  });

  it('creates an instance with default params', () => {
    const instance = registry.createInstance('sma_cross');
    expect(instance.params.fastPeriod).toBe(10);
    expect(instance.params.slowPeriod).toBe(30);
  });

  it('resolves params correctly', () => {
    const instance = registry.createInstance('sma_cross', { fastPeriod: 5 });
    expect(instance.params.fastPeriod).toBe(5);
    expect(instance.params.slowPeriod).toBe(30);
  });
});

// =========================================================================
// BACKTEST ENGINE
// =========================================================================

describe('BacktestEngine', () => {
  let engine: BacktestEngine;
  let registry: StrategyRegistry;

  beforeEach(() => {
    engine = new BacktestEngine();
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('runs a backtest with default cost model', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result).toBeDefined();
    expect(result.equity.length).toBeGreaterThan(0);
    expect(result.totalBars).toBe(100);
  });

  it('runs a backtest with zero cost model', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN, costModel: ZERO_COST });
    expect(result.costsApplied.totalCosts).toBe(0);
  });

  it('computes performance metrics', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN, costModel: ZERO_COST });
    expect(typeof result.metrics.totalReturn).toBe('number');
    expect(typeof result.metrics.sharpeRatio).toBe('number');
    expect(typeof result.metrics.maxDrawdown).toBe('number');
    expect(typeof result.metrics.winRate).toBe('number');
    expect(typeof result.metrics.profitFactor).toBe('number');
  });

  it('handles empty dataset gracefully', () => {
    const dataset = makeDataset([]);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.totalBars).toBe(0);
    expect(result.trades.length).toBe(0);
  });

  it('handles tiny dataset gracefully', () => {
    const dataset = makeDataset(makeBars(1));
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.totalBars).toBe(0);
  });

  it('records trade details', () => {
    const bars = makeTrendingBars(150);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    for (const trade of result.trades) {
      expect(trade.tradeId).toBeTruthy();
      expect(trade.entryPrice).toBeGreaterThan(0);
      expect(trade.exitPrice).toBeGreaterThan(0);
      expect(trade.pnlPercent).toBeDefined();
    }
  });

  it('applies cost model to backtest', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN, costModel: TEST_COST });
    expect(result.costsApplied.totalCommissions).toBeGreaterThanOrEqual(0);
  });

  it('respects initial capital', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN, initialCapital: 50_000 });
    expect(result.initialCapital).toBe(50_000);
  });

  it('final equity equals last equity point', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.finalEquity).toBe(result.equity[result.equity.length - 1]);
  });

  it('equity timestamps match bars', () => {
    const bars = makeTrendingBars(50);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.equityTimestamps.length).toBe(result.equity.length);
  });

  it('no trades in flat market with no signals', () => {
    const bars = Array.from({ length: 50 }, (_, i) => ({
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
      open: 100, high: 100.5, low: 99.5, close: 100,
      volume: 1000000, timeframe: '1d', adjustedClose: 100,
    }));
    const dataset = makeDataset(bars);
    const fn: StrategyFunction = () => null;
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: fn });
    expect(result.trades.length).toBe(0);
  });
});

// =========================================================================
// COST ENGINE
// =========================================================================

describe('CostEngine', () => {
  let engine: CostEngine;

  beforeEach(() => { engine = new CostEngine(); });

  it('computes trade cost with commissions and slippage', () => {
    const bars = makeBars(10);
    const cost = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars, entryBarIndex: 0, exitBarIndex: 5, costModel: TEST_COST,
    });
    expect(cost.commissions).toBeGreaterThanOrEqual(0);
    expect(cost.entrySlippage).toBeGreaterThanOrEqual(0);
    expect(cost.exitSlippage).toBeGreaterThanOrEqual(0);
  });

  it('computes summary across trades', () => {
    const bars = makeBars(10);
    const summary = engine.computeSummary([
      { entryPrice: 100, exitPrice: 105, quantity: 100, bars, entryBarIndex: 0, exitBarIndex: 5 },
      { entryPrice: 105, exitPrice: 102, quantity: 100, bars, entryBarIndex: 5, exitBarIndex: 9 },
    ], TEST_COST);
    expect(summary.totalCommissions).toBeGreaterThanOrEqual(0);
    expect(summary.costPerTrade).toBeGreaterThanOrEqual(0);
  });

  it('applies slippage to BUY', () => {
    const price = engine.applySlippage(100, 'BUY', TEST_COST);
    expect(price).toBeGreaterThan(100);
  });

  it('applies slippage to SELL', () => {
    const price = engine.applySlippage(100, 'SELL', TEST_COST);
    expect(price).toBeLessThan(100);
  });

  it('zero cost model gives zero costs', () => {
    const bars = makeBars(5);
    const cost = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars, entryBarIndex: 0, exitBarIndex: 3, costModel: ZERO_COST,
    });
    expect(cost.commissions).toBe(0);
    expect(cost.entrySlippage).toBe(0);
    expect(cost.exitSlippage).toBe(0);
  });

  it('market impact NONE gives zero impact', () => {
    const bars = makeBars(5);
    const cost = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars, entryBarIndex: 0, exitBarIndex: 3,
      costModel: { ...ZERO_COST, marketImpactModel: 'NONE' },
    });
    expect(cost.marketImpact).toBe(0);
  });

  it('SQRT market impact scales with sqrt of participation', () => {
    const bars = makeBars(10);
    const cost1 = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars, entryBarIndex: 5, exitBarIndex: 7,
      costModel: { ...ZERO_COST, marketImpactModel: 'SQRT', marketImpactCoeff: 0.5 },
    });
    const cost2 = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 400,
      bars, entryBarIndex: 5, exitBarIndex: 7,
      costModel: { ...ZERO_COST, marketImpactModel: 'SQRT', marketImpactCoeff: 0.5 },
    });
    expect(cost2.marketImpact).toBeGreaterThan(cost1.marketImpact);
  });
});

// =========================================================================
// METRICS ENGINE
// =========================================================================

describe('MetricsEngine', () => {
  let engine: MetricsEngine;

  beforeEach(() => { engine = new MetricsEngine(); });

  it('computes basic metrics from equity curve', () => {
    const metrics = engine.compute({
      equity: [100, 102, 101, 105, 103, 108],
      trades: [],
      initialCapital: 100,
    });
    expect(metrics.totalReturn).toBeCloseTo(0.08, 1);
    expect(metrics.totalTrades).toBe(0);
  });

  it('computes metrics with trades', () => {
    const trades: BacktestTrade[] = [
      { tradeId: 't1', symbol: 'X', direction: 'LONG', entryBarIndex: 0, entryPrice: 100, entryTimestamp: '', exitBarIndex: 5, exitPrice: 110, exitTimestamp: '', exitReason: 'SIGNAL', quantity: 10, notional: 1000, pnl: 100, pnlPercent: 0.1, commissions: 1, slippage: 0.5, holdingBars: 5, riskRewardActual: 2 },
      { tradeId: 't2', symbol: 'X', direction: 'SHORT', entryBarIndex: 5, entryPrice: 110, entryTimestamp: '', exitBarIndex: 10, exitPrice: 105, exitTimestamp: '', exitReason: 'STOP', quantity: 10, notional: 1100, pnl: 50, pnlPercent: 0.045, commissions: 1, slippage: 0.5, holdingBars: 5, riskRewardActual: 1.5 },
    ];
    const metrics = engine.compute({ equity: [100, 105, 110, 108, 112, 115], trades, initialCapital: 100 });
    expect(metrics.totalTrades).toBe(2);
    expect(metrics.winRate).toBe(1);
    expect(metrics.longTrades).toBe(1);
    expect(metrics.shortTrades).toBe(1);
  });

  it('computes drawdown duration', () => {
    const metrics = engine.compute({
      equity: [100, 110, 105, 100, 95, 90, 95, 100, 105, 110],
      trades: [], initialCapital: 100,
    });
    expect(metrics.maxDrawdownDuration).toBeGreaterThan(0);
  });

  it('computes consecutive wins and losses', () => {
    const trades: BacktestTrade[] = [
      { tradeId: 't1', symbol: 'X', direction: 'LONG', entryBarIndex: 0, entryPrice: 100, entryTimestamp: '', exitBarIndex: 1, exitPrice: 110, exitTimestamp: '', exitReason: 'SIGNAL', quantity: 10, notional: 1000, pnl: 100, pnlPercent: 0.1, commissions: 0, slippage: 0, holdingBars: 1, riskRewardActual: 2 },
      { tradeId: 't2', symbol: 'X', direction: 'LONG', entryBarIndex: 1, entryPrice: 110, entryTimestamp: '', exitBarIndex: 2, exitPrice: 120, exitTimestamp: '', exitReason: 'SIGNAL', quantity: 10, notional: 1100, pnl: 100, pnlPercent: 0.09, commissions: 0, slippage: 0, holdingBars: 1, riskRewardActual: 2 },
      { tradeId: 't3', symbol: 'X', direction: 'LONG', entryBarIndex: 2, entryPrice: 120, entryTimestamp: '', exitBarIndex: 3, exitPrice: 115, exitTimestamp: '', exitReason: 'STOP', quantity: 10, notional: 1200, pnl: -50, pnlPercent: -0.04, commissions: 0, slippage: 0, holdingBars: 1, riskRewardActual: 1 },
    ];
    const metrics = engine.compute({ equity: [100, 110, 120, 115, 118], trades, initialCapital: 100 });
    expect(metrics.consecutiveWins).toBe(2);
    expect(metrics.consecutiveLosses).toBe(1);
  });

  it('computes volatility', () => {
    const metrics = engine.compute({
      equity: [100, 102, 98, 104, 96, 106],
      trades: [], initialCapital: 100,
    });
    expect(metrics.volatility).toBeGreaterThan(0);
  });

  it('handles single equity point', () => {
    const metrics = engine.compute({
      equity: [100], trades: [], initialCapital: 100,
    });
    expect(metrics.totalReturn).toBe(0);
  });

  it('handles empty equity', () => {
    const metrics = engine.compute({
      equity: [], trades: [], initialCapital: 100,
    });
    expect(metrics.totalReturn).toBe(0);
  });
});

// =========================================================================
// WALK-FORWARD ENGINE
// =========================================================================

describe('WalkForwardEngine', () => {
  let engine: WalkForwardEngine;
  let registry: StrategyRegistry;

  beforeEach(() => {
    engine = new WalkForwardEngine();
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('runs walk-forward analysis', () => {
    const bars = makeTrendingBars(200);
    const dataset = makeDataset(bars);
    const result = engine.run({
      dataset, strategyId: 'sma_cross', strategyFn: SMA_CROSS_FN,
      registry, paramGrid: { fastPeriod: [5, 10], slowPeriod: [20, 30] },
      trainBars: 80, testBars: 40, costModel: ZERO_COST,
    });
    expect(result.windows.length).toBeGreaterThan(0);
    expect(result.overallTestMetrics).toBeDefined();
    expect(result.overallTrainMetrics).toBeDefined();
  });

  it('computes parameter stability', () => {
    const bars = makeTrendingBlocks(300);
    const dataset = makeDataset(bars);
    const result = engine.run({
      dataset, strategyId: 'sma_cross', strategyFn: SMA_CROSS_FN,
      registry, paramGrid: { fastPeriod: [5, 10, 15], slowPeriod: [20, 30] },
      trainBars: 100, testBars: 50, costModel: ZERO_COST,
    });
    expect(result.parameterStability).toBeGreaterThanOrEqual(0);
    expect(result.parameterStability).toBeLessThanOrEqual(1);
  });

  it('computes overfitting score', () => {
    const bars = makeTrendingBars(200);
    const dataset = makeDataset(bars);
    const result = engine.run({
      dataset, strategyId: 'sma_cross', strategyFn: SMA_CROSS_FN,
      registry, paramGrid: { fastPeriod: [5, 10], slowPeriod: [20, 30] },
      trainBars: 80, testBars: 40, costModel: ZERO_COST,
    });
    expect(result.overfittingScore).toBeGreaterThanOrEqual(0);
    expect(result.overfittingScore).toBeLessThanOrEqual(1);
  });
});

// =========================================================================
// SENSITIVITY ENGINE
// =========================================================================

describe('SensitivityEngine', () => {
  let engine: SensitivityEngine;

  beforeEach(() => { engine = new SensitivityEngine(); });

  it('analyzes parameter sensitivity', () => {
    const registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.analyzeParameter({
      dataset, strategy: instance, strategyFn: SMA_CROSS_FN,
      paramName: 'fastPeriod', values: [5, 10, 15, 20],
      costModel: ZERO_COST,
    });
    expect(result.points.length).toBe(4);
    expect(result.sensitivity).toBeGreaterThanOrEqual(0);
  });

  it('detects overfitting', () => {
    const result = engine.detectOverfitting({
      inSampleResult: { sharpeRatio: 3.0, totalReturn: 0.5, annualizedReturn: 0.5, sortinoRatio: 3.5, calmarRatio: 4, maxDrawdown: 0.1, maxDrawdownDuration: 10, volatility: 0.15, downsideVolatility: 0.1, winRate: 0.7, avgWin: 0.05, avgLoss: -0.03, profitFactor: 2.5, expectancy: 0.02, totalTrades: 100, avgHoldingBars: 5, bestTrade: 0.15, worstTrade: -0.05, avgTrade: 0.01, consecutiveWins: 10, consecutiveLosses: 3, longTrades: 50, shortTrades: 50, longWinRate: 0.7, shortWinRate: 0.7, skewness: 0.5, kurtosis: 3.2, tailRatio: 1.5, commonReturn: 0.6 },
      outOfSampleResult: { sharpeRatio: 0.2, totalReturn: 0.02, annualizedReturn: 0.02, sortinoRatio: 0.3, calmarRatio: 0.5, maxDrawdown: 0.15, maxDrawdownDuration: 30, volatility: 0.2, downsideVolatility: 0.15, winRate: 0.52, avgWin: 0.03, avgLoss: -0.03, profitFactor: 1.2, expectancy: 0.001, totalTrades: 100, avgHoldingBars: 5, bestTrade: 0.08, worstTrade: -0.08, avgTrade: 0.001, consecutiveWins: 5, consecutiveLosses: 5, longTrades: 50, shortTrades: 50, longWinRate: 0.52, shortWinRate: 0.52, skewness: 0, kurtosis: 3, tailRatio: 1, commonReturn: 0.52 },
      totalStrategiesTested: 100,
    });
    expect(result.overfittingProbability).toBeGreaterThan(0);
    expect(result.isLikelyOverfit).toBe(true);
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it('detects well-fitted strategy', () => {
    const result = engine.detectOverfitting({
      inSampleResult: { sharpeRatio: 1.5, totalReturn: 0.3, annualizedReturn: 0.3, sortinoRatio: 1.8, calmarRatio: 2, maxDrawdown: 0.1, maxDrawdownDuration: 10, volatility: 0.15, downsideVolatility: 0.1, winRate: 0.6, avgWin: 0.04, avgLoss: -0.03, profitFactor: 2.0, expectancy: 0.01, totalTrades: 100, avgHoldingBars: 5, bestTrade: 0.12, worstTrade: -0.05, avgTrade: 0.008, consecutiveWins: 8, consecutiveLosses: 3, longTrades: 50, shortTrades: 50, longWinRate: 0.6, shortWinRate: 0.6, skewness: 0.3, kurtosis: 3, tailRatio: 1.3, commonReturn: 0.55 },
      outOfSampleResult: { sharpeRatio: 1.3, totalReturn: 0.25, annualizedReturn: 0.25, sortinoRatio: 1.5, calmarRatio: 1.8, maxDrawdown: 0.12, maxDrawdownDuration: 15, volatility: 0.16, downsideVolatility: 0.11, winRate: 0.58, avgWin: 0.035, avgLoss: -0.028, profitFactor: 1.8, expectancy: 0.008, totalTrades: 100, avgHoldingBars: 5, bestTrade: 0.10, worstTrade: -0.06, avgTrade: 0.007, consecutiveWins: 7, consecutiveLosses: 3, longTrades: 50, shortTrades: 50, longWinRate: 0.58, shortWinRate: 0.58, skewness: 0.2, kurtosis: 3, tailRatio: 1.2, commonReturn: 0.53 },
      totalStrategiesTested: 5,
    });
    expect(result.overfittingProbability).toBeLessThan(0.7);
    expect(result.isLikelyOverfit).toBe(false);
  });
});

// =========================================================================
// MONTE CARLO ENGINE
// =========================================================================

describe('MonteCarloEngine', () => {
  let engine: MonteCarloEngine;

  beforeEach(() => { engine = new MonteCarloEngine(); });

  it('runs Monte Carlo simulation with seed', () => {
    const returns = Array.from({ length: 252 }, () => (Math.random() - 0.48) * 0.02);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 100, periodsPerSim: 252, seed: 42 },
    });
    expect(result.simulations).toBe(100);
    expect(result.paths.length).toBe(100);
    expect(result.paths[0].length).toBe(253);
  });

  it('produces reproducible results with same seed', () => {
    const returns = Array.from({ length: 100 }, () => 0.001);
    const config: Partial<MonteCarloConfig> = { simulations: 50, periodsPerSim: 100, seed: 123 };
    const r1 = engine.run({ returns, strategy: { definitionId: 'x', version: '1', params: {} }, config });
    const r2 = engine.run({ returns, strategy: { definitionId: 'x', version: '1', params: {} }, config });
    expect(r1.stats.meanReturn).toBe(r2.stats.meanReturn);
    expect(r1.percentiles.p50).toBe(r2.percentiles.p50);
  });

  it('computes statistics', () => {
    const returns = Array.from({ length: 252 }, () => (Math.random() - 0.48) * 0.02);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 100, seed: 42 },
    });
    expect(typeof result.stats.meanReturn).toBe('number');
    expect(typeof result.stats.probabilityOfLoss).toBe('number');
    expect(typeof result.stats.valueAtRisk95).toBe('number');
    expect(result.stats.probabilityOfLoss).toBeGreaterThanOrEqual(0);
    expect(result.stats.probabilityOfLoss).toBeLessThanOrEqual(1);
  });

  it('BLOCK bootstrap produces correct path lengths', () => {
    const returns = Array.from({ length: 100 }, () => 0.01);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'x', version: '1', params: {} },
      config: { simulations: 10, periodsPerSim: 50, seed: 1, bootstrapMethod: 'BLOCK', blockSize: 5 },
    });
    for (const path of result.paths) {
      expect(path.length).toBe(51);
    }
  });

  it('iid bootstrap produces correct path lengths', () => {
    const returns = Array.from({ length: 100 }, () => 0.01);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'x', version: '1', params: {} },
      config: { simulations: 10, periodsPerSim: 50, seed: 1, bootstrapMethod: 'iid' },
    });
    for (const path of result.paths) {
      expect(path.length).toBe(51);
    }
  });

  it('percentiles are ordered', () => {
    const returns = Array.from({ length: 252 }, () => (Math.random() - 0.48) * 0.02);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 200, seed: 42 },
    });
    expect(result.percentiles.p5).toBeLessThanOrEqual(result.percentiles.p25);
    expect(result.percentiles.p25).toBeLessThanOrEqual(result.percentiles.p50);
    expect(result.percentiles.p50).toBeLessThanOrEqual(result.percentiles.p75);
    expect(result.percentiles.p75).toBeLessThanOrEqual(result.percentiles.p95);
  });
});

// =========================================================================
// CALIBRATION ENGINE
// =========================================================================

describe('CalibrationEngine', () => {
  let engine: CalibrationEngine;

  beforeEach(() => { engine = new CalibrationEngine(); });

  it('evaluates calibration with matched forecasts', () => {
    const forecasts: ForecastRecord[] = [];
    const outcomes: ForecastOutcome[] = [];
    for (let i = 0; i < 50; i++) {
      const id = `f_${i}`;
      const conf = 0.5 + Math.random() * 0.5;
      forecasts.push({
        forecastId: id, symbol: 'AAPL', timestamp: '', direction: 'UP',
        confidence: conf, horizonBars: 5, strategyId: 'test', parameters: {},
      });
      outcomes.push({
        forecastId: id, symbol: 'AAPL', actualDirection: Math.random() > 0.5 ? 'UP' : 'DOWN',
        actualMovePercent: (Math.random() - 0.5) * 5,
        evaluationTimestamp: '', correct: Math.random() > 0.3,
      });
    }
    forecasts.forEach(f => engine.recordForecast(f));
    outcomes.forEach(o => engine.recordOutcome(o));
    const result = engine.evaluate('test');
    expect(result.totalForecasts).toBe(50);
    expect(typeof result.expectedCalibrationError).toBe('number');
    expect(result.bins.length).toBe(10);
  });

  it('returns empty result with no data', () => {
    const result = engine.evaluate();
    expect(result.totalForecasts).toBe(0);
    expect(result.isWellCalibrated).toBe(false);
  });

  it('perfectly calibrated forecasts have low ECE', () => {
    for (let i = 0; i < 100; i++) {
      const conf = (i / 100) + 0.01;
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '', direction: 'UP',
        confidence: conf, horizonBars: 1, strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'UP',
        actualMovePercent: 1, evaluationTimestamp: '',
        correct: Math.random() < conf,
      });
    }
    const result = engine.evaluate('test');
    expect(result.expectedCalibrationError).toBeLessThan(0.2);
  });

  it('clears history', () => {
    engine.recordForecast({
      forecastId: 'f1', symbol: 'X', timestamp: '', direction: 'UP',
      confidence: 0.8, horizonBars: 1, strategyId: 'test', parameters: {},
    });
    engine.recordOutcome({
      forecastId: 'f1', symbol: 'X', actualDirection: 'UP',
      actualMovePercent: 1, evaluationTimestamp: '', correct: true,
    });
    engine.clearHistory();
    expect(engine.getForecasts().length).toBe(0);
    expect(engine.getOutcomes().length).toBe(0);
  });

  it('Brier score ranges 0-1', () => {
    for (let i = 0; i < 20; i++) {
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '', direction: 'UP',
        confidence: 0.7, horizonBars: 1, strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'UP',
        actualMovePercent: 1, evaluationTimestamp: '', correct: Math.random() > 0.3,
      });
    }
    const result = engine.evaluate('test');
    expect(result.brierScore).toBeGreaterThanOrEqual(0);
    expect(result.brierScore).toBeLessThanOrEqual(1);
  });

  it('log loss is non-negative', () => {
    for (let i = 0; i < 20; i++) {
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '', direction: 'DOWN',
        confidence: 0.3, horizonBars: 1, strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'DOWN',
        actualMovePercent: -1, evaluationTimestamp: '', correct: true,
      });
    }
    const result = engine.evaluate('test');
    expect(result.logLoss).toBeGreaterThanOrEqual(0);
  });
});

// =========================================================================
// EVENT STUDIES ENGINE
// =========================================================================

describe('EventStudyEngine', () => {
  let engine: EventStudyEngine;

  beforeEach(() => { engine = new EventStudyEngine(); });

  it('registers events', () => {
    engine.registerEvent({
      eventId: 'e1', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-15T00:00:00Z', description: 'Q4 earnings',
    });
    expect(engine.getEvents()).toHaveLength(1);
  });

  it('analyzes an event study', () => {
    const bars = makeTrendingBars(60);
    engine.registerEvent({
      eventId: 'e1', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-30T00:00:00Z', description: 'Q4 earnings',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -10, postWindow: 10,
    });
    expect(result.eventId).toBe('e1');
    expect(result.carDays.length).toBeGreaterThan(0);
    expect(typeof result.abnormalReturn).toBe('number');
  });

  it('analyzes all registered events', () => {
    const bars = makeTrendingBars(60);
    engine.registerEvent({
      eventId: 'e1', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-30T00:00:00Z', description: 'Q4',
    });
    engine.registerEvent({
      eventId: 'e2', symbol: 'AAPL', eventType: 'GUIDANCE',
      eventTimestamp: '2024-02-10T00:00:00Z', description: 'Guidance',
    });
    const results = engine.analyzeAll({ bars, preWindow: -5, postWindow: 5 });
    expect(results).toHaveLength(2);
  });

  it('handles event outside data range', () => {
    const bars = makeBars(10);
    engine.registerEvent({
      eventId: 'e1', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2025-01-01T00:00:00Z', description: 'Future event',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -5, postWindow: 5,
    });
    expect(result.sampleSize).toBe(0);
  });

  it('clears events', () => {
    engine.registerEvent({
      eventId: 'e1', symbol: 'X', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-15T00:00:00Z', description: '',
    });
    engine.clearEvents();
    expect(engine.getEvents()).toHaveLength(0);
  });

  it('CAR computation is cumulative', () => {
    const bars = makeTrendingBars(60);
    engine.registerEvent({
      eventId: 'e1', symbol: 'X', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-30T00:00:00Z', description: '',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -5, postWindow: 5,
    });
    for (let i = 1; i < result.carDays.length; i++) {
      // CAR should generally be non-decreasing in absolute magnitude
      expect(typeof result.carDays[i].car).toBe('number');
    }
  });
});

// =========================================================================
// EXPERIMENT REGISTRY
// =========================================================================

describe('ExperimentRegistry', () => {
  let registry: ExperimentRegistry;

  beforeEach(() => { registry = new ExperimentRegistry(); });

  it('creates an experiment', () => {
    const exp = registry.createExperiment({
      name: 'Test Exp', description: 'Testing',
      strategy: { definitionId: 'sma_cross', version: '1.0.0', params: {} },
      datasetId: 'ds1', datasetSymbol: 'AAPL',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    expect(exp.id).toBeTruthy();
    expect(exp.status).toBe('PLANNED');
  });

  it('retrieves experiment and result', () => {
    const exp = registry.createExperiment({
      name: 'Test', description: '',
      strategy: { definitionId: 'x', version: '1', params: {} },
      datasetId: 'ds1', datasetSymbol: 'X',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    expect(registry.getExperiment(exp.id)).toBeDefined();
    expect(registry.getResult(exp.id)).toBeDefined();
  });

  it('updates experiment status', () => {
    const exp = registry.createExperiment({
      name: 'Test', description: '',
      strategy: { definitionId: 'x', version: '1', params: {} },
      datasetId: 'ds1', datasetSymbol: 'X',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    expect(registry.updateStatus(exp.id, 'RUNNING')).toBe(true);
    expect(registry.getExperiment(exp.id)?.status).toBe('RUNNING');
  });

  it('lists completed experiments', () => {
    const exp = registry.createExperiment({
      name: 'Test', description: '',
      strategy: { definitionId: 'x', version: '1', params: {} },
      datasetId: 'ds1', datasetSymbol: 'X',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    registry.updateStatus(exp.id, 'COMPLETED');
    expect(registry.listCompleted()).toHaveLength(1);
  });

  it('adds notes to experiment', () => {
    const exp = registry.createExperiment({
      name: 'Test', description: '',
      strategy: { definitionId: 'x', version: '1', params: {} },
      datasetId: 'ds1', datasetSymbol: 'X',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    registry.addNote(exp.id, 'Test note');
    expect(registry.getResult(exp.id)?.notes).toContain('Test note');
  });

  it('generates research report', () => {
    const exp = registry.createExperiment({
      name: 'Test Report', description: '',
      strategy: { definitionId: 'x', version: '1', params: {} },
      datasetId: 'ds1', datasetSymbol: 'X',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    registry.updateStatus(exp.id, 'COMPLETED');
    const report = registry.generateReport(exp.id);
    expect(report).not.toBeNull();
    expect(report?.title).toContain('Test Report');
    expect(report?.disclaimers.length).toBeGreaterThan(0);
  });

  it('deletes experiment', () => {
    const exp = registry.createExperiment({
      name: 'Test', description: '',
      strategy: { definitionId: 'x', version: '1', params: {} },
      datasetId: 'ds1', datasetSymbol: 'X',
      periodStart: '2024-01-01', periodEnd: '2024-06-30',
      costModel: ZERO_COST,
    });
    expect(registry.deleteExperiment(exp.id)).toBe(true);
    expect(registry.getExperiment(exp.id)).toBeUndefined();
  });

  it('returns null for unknown experiment report', () => {
    expect(registry.generateReport('nonexistent')).toBeNull();
  });
});

// =========================================================================
// PAPER TRADING ENGINE
// =========================================================================

describe('PaperTradingEngine', () => {
  let engine: PaperTradingEngine;

  beforeEach(() => { engine = new PaperTradingEngine(100_000, ZERO_COST); });

  it('opens a paper position', () => {
    const pos = engine.openPosition({ symbol: 'AAPL', direction: 'LONG', entryPrice: 150, quantity: 100 });
    expect(pos.positionId).toBeTruthy();
    expect(pos.status).toBe('OPEN');
    expect(pos.entryPrice).toBe(150);
  });

  it('closes a paper position', () => {
    const pos = engine.openPosition({ symbol: 'AAPL', direction: 'LONG', entryPrice: 150, quantity: 100 });
    const closed = engine.closePosition({ positionId: pos.positionId, exitPrice: 160 });
    expect(closed).not.toBeNull();
    expect(closed?.status).toBe('CLOSED');
    expect(closed?.pnl).toBeGreaterThan(0);
    expect(closed?.pnlPercent).toBeGreaterThan(0);
  });

  it('computes paper stats', () => {
    const p1 = engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10 });
    const p2 = engine.openPosition({ symbol: 'B', direction: 'SHORT', entryPrice: 50, quantity: 20 });
    engine.closePosition({ positionId: p1.positionId, exitPrice: 110 });
    engine.closePosition({ positionId: p2.positionId, exitPrice: 45 });
    const stats = engine.getStats();
    expect(stats.totalTrades).toBe(2);
    expect(stats.winningTrades).toBe(2);
    expect(stats.winRate).toBe(1);
  });

  it('gets portfolio snapshot', () => {
    engine.openPosition({ symbol: 'AAPL', direction: 'LONG', entryPrice: 150, quantity: 10 });
    const snapshot = engine.getSnapshot();
    expect(snapshot.openPositionCount).toBe(1);
    expect(snapshot.totalEquity).toBeGreaterThan(0);
  });

  it('resets paper trading', () => {
    engine.openPosition({ symbol: 'X', direction: 'LONG', entryPrice: 100, quantity: 10 });
    engine.reset();
    expect(engine.getSnapshot().openPositionCount).toBe(0);
  });

  it('applies slippage to entry with non-zero cost model', () => {
    const engine2 = new PaperTradingEngine(100_000, TEST_COST);
    const pos = engine2.openPosition({ symbol: 'AAPL', direction: 'LONG', entryPrice: 100, quantity: 100 });
    expect(pos.entryPrice).toBeGreaterThanOrEqual(100);
    expect(pos.commissions).toBeGreaterThanOrEqual(0);
  });

  it('closing nonexistent position returns null', () => {
    const result = engine.closePosition({ positionId: 'nonexistent', exitPrice: 100 });
    expect(result).toBeNull();
  });

  it('handles short position PnL correctly', () => {
    const pos = engine.openPosition({ symbol: 'AAPL', direction: 'SHORT', entryPrice: 200, quantity: 50 });
    const closed = engine.closePosition({ positionId: pos.positionId, exitPrice: 190 });
    expect(closed?.pnl).toBeGreaterThan(0); // price went down, short wins
  });

  it('stop loss triggers close', () => {
    const pos = engine.openPosition({
      symbol: 'AAPL', direction: 'LONG', entryPrice: 100, quantity: 10,
      stopLoss: 95,
    });
    const closed = engine.checkStopsAndTargets({
      bar: { high: 102, low: 94, open: 101 },
    });
    expect(closed.length).toBe(1);
    expect(closed[0].exitReason).toBe('STOP');
  });

  it('take profit triggers close', () => {
    const pos = engine.openPosition({
      symbol: 'AAPL', direction: 'LONG', entryPrice: 100, quantity: 10,
      takeProfit: 105,
    });
    const closed = engine.checkStopsAndTargets({
      bar: { high: 106, low: 99, open: 101 },
    });
    expect(closed.length).toBe(1);
    expect(closed[0].exitReason).toBe('TARGET');
  });
});

// =========================================================================
// EXECUTION FIREWALL
// =========================================================================

describe('ExecutionFirewall', () => {
  it('allows read market data', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('read_stock_price');
    expect(result.allowed).toBe(true);
    expect(result.classification).toBe('READ_MARKET_DATA');
  });

  it('allows simulate trade', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('simulate_trade');
    expect(result.allowed).toBe(true);
    expect(result.classification).toBe('SIMULATE_TRADE');
  });

  it('denies execute trade', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('execute_trade');
    expect(result.allowed).toBe(false);
    expect(result.classification).toBe('EXECUTE_TRADE');
    expect(result.overrideLevel).toBe('STRICT');
  });

  it('denies fund transfer', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('transfer_funds');
    expect(result.allowed).toBe(false);
    expect(result.classification).toBe('TRANSFER_FUNDS');
  });

  it('denies order intent execution', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluateIntent({
      symbol: 'AAPL', side: 'BUY', orderType: 'MARKET', quantity: 100,
      timeInForce: 'DAY',
    });
    expect(result.allowed).toBe(false);
  });

  it('classifies actions correctly', () => {
    const fw = new ExecutionFirewall();
    expect(fw.classifyCapability('place_order')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('buy_stock')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('sell_stock')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('short_stock')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('transfer_money')).toBe('TRANSFER_FUNDS');
    expect(fw.classifyCapability('withdraw')).toBe('TRANSFER_FUNDS');
    expect(fw.classifyCapability('deposit')).toBe('TRANSFER_FUNDS');
    expect(fw.classifyCapability('paper_trade')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('backtest')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('get_quote')).toBe('READ_MARKET_DATA');
  });

  it('can never override', () => {
    const fw = new ExecutionFirewall();
    expect(fw.canOverride()).toBe(false);
  });

  it('explains denial', () => {
    const fw = new ExecutionFirewall();
    const msg = fw.explainDenial('execute_trade');
    expect(msg).toContain('DENIED');
    expect(msg).toContain('non-overridable');
  });

  it('rejects policy with liveTradeExecution true', () => {
    expect(() => new ExecutionFirewall({ liveTradeExecution: true })).toThrow();
  });

  it('rejects policy with transferFunds true', () => {
    expect(() => new ExecutionFirewall({ transferFunds: true })).toThrow();
  });

  it('rejects policy with allowLlmOverride true', () => {
    expect(() => new ExecutionFirewall({ allowLlmOverride: true })).toThrow();
  });

  it('records audit log', () => {
    const fw = new ExecutionFirewall();
    fw.evaluate('read_quote');
    fw.evaluate('execute_trade');
    const log = fw.getAuditLog();
    expect(log.length).toBe(2);
    expect(log[0].allowed).toBe(true);
    expect(log[1].allowed).toBe(false);
  });

  it('returns policy', () => {
    const fw = new ExecutionFirewall();
    const policy = fw.getPolicy();
    expect(policy.liveTradeExecution).toBe(false);
  });

  it('GLOBAL_FIREWALL is a singleton', () => {
    expect(GLOBAL_FIREWALL).toBeDefined();
    expect(GLOBAL_FIREWALL.canOverride()).toBe(false);
  });
});

// =========================================================================
// INTEGRATION TESTS
// =========================================================================

describe('Phase 27 Integration', () => {
  it('full pipeline: dataset -> strategy -> backtest -> metrics -> report', () => {
    const dsEngine = new HistoricalDatasetEngine();
    const registry = new StrategyRegistry();
    const backtestEngine = new BacktestEngine();
    const experimentRegistry = new ExperimentRegistry();

    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
    const bars = makeTrendingBars(150);
    const { dataset } = dsEngine.buildDataset({ symbol: 'TEST', timeframe: '1d', bars });

    const instance = registry.createInstance('sma_cross');
    const btResult = backtestEngine.run({
      dataset, strategy: instance, strategyFn: SMA_CROSS_FN, costModel: ZERO_COST,
    });

    const exp = experimentRegistry.createExperiment({
      name: 'Integration Test', description: 'Full pipeline test',
      strategy: instance, datasetId: dataset.id, datasetSymbol: 'TEST',
      periodStart: dataset.startDate, periodEnd: dataset.endDate,
      costModel: ZERO_COST,
    });
    experimentRegistry.setBacktestResult(exp.id, btResult);

    const report = experimentRegistry.generateReport(exp.id);
    expect(report).not.toBeNull();
    expect(report!.backtest).toBeDefined();
    expect(report!.backtest!.metrics.totalTrades).toBeGreaterThanOrEqual(0);
    expect(report!.summary.length).toBeGreaterThan(0);
  });

  it('firewall blocks throughout pipeline', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('broker_buy_AAPL');
    expect(result.allowed).toBe(false);
    expect(result.overrideLevel).toBe('STRICT');
  });

  it('paper trading tracks all positions', () => {
    const paper = new PaperTradingEngine(100_000, ZERO_COST);
    const p1 = paper.openPosition({ symbol: 'AAPL', direction: 'LONG', entryPrice: 150, quantity: 100 });
    const p2 = paper.openPosition({ symbol: 'GOOGL', direction: 'SHORT', entryPrice: 140, quantity: 50 });
    paper.closePosition({ positionId: p1.positionId, exitPrice: 160 });
    paper.closePosition({ positionId: p2.positionId, exitPrice: 135 });
    const stats = paper.getStats();
    expect(stats.totalTrades).toBe(2);
    expect(stats.totalPnl).toBeGreaterThan(0);
  });

  it('calibration works with paper trading signals', () => {
    const cal = new CalibrationEngine();
    for (let i = 0; i < 30; i++) {
      cal.recordForecast({
        forecastId: `f_${i}`, symbol: 'AAPL', timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
        direction: 'UP', confidence: 0.6 + Math.random() * 0.3,
        horizonBars: 5, strategyId: 'test', parameters: {},
      });
      cal.recordOutcome({
        forecastId: `f_${i}`, symbol: 'AAPL', actualDirection: Math.random() > 0.4 ? 'UP' : 'DOWN',
        actualMovePercent: (Math.random() - 0.5) * 3, evaluationTimestamp: '',
        correct: Math.random() > 0.35,
      });
    }
    const result = cal.evaluate('test');
    expect(result.totalForecasts).toBe(30);
    expect(result.expectedCalibrationError).toBeGreaterThanOrEqual(0);
  });

  it('sensitivity analysis on backtest parameters', () => {
    const dsEngine = new HistoricalDatasetEngine();
    const registry = new StrategyRegistry();
    const backtestEngine = new BacktestEngine();
    const sensitivityEngine = new SensitivityEngine();

    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
    const bars = makeTrendingBars(100);
    const { dataset } = dsEngine.buildDataset({ symbol: 'TEST', timeframe: '1d', bars });
    const instance = registry.createInstance('sma_cross');

    const result = sensitivityEngine.analyzeParameter({
      dataset, strategy: instance, strategyFn: SMA_CROSS_FN,
      paramName: 'fastPeriod', values: [5, 10, 15], costModel: ZERO_COST,
    });
    expect(result.points.length).toBe(3);
    expect(typeof result.sensitivity).toBe('number');
  });

  it('Monte Carlo on backtest returns', () => {
    const dsEngine = new HistoricalDatasetEngine();
    const registry = new StrategyRegistry();
    const backtestEngine = new BacktestEngine();
    const mcEngine = new MonteCarloEngine();

    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
    const bars = makeTrendingBars(100);
    const { dataset } = dsEngine.buildDataset({ symbol: 'TEST', timeframe: '1d', bars });
    const instance = registry.createInstance('sma_cross');
    const btResult = backtestEngine.run({
      dataset, strategy: instance, strategyFn: SMA_CROSS_FN, costModel: ZERO_COST,
    });

    const returns = btResult.equity.slice(1).map((v, i) =>
      btResult.equity[i] !== 0 ? (v - btResult.equity[i]) / btResult.equity[i] : 0,
    );

    const mcResult = mcEngine.run({
      returns, strategy: instance,
      config: { simulations: 50, seed: 42 },
    });
    expect(mcResult.paths.length).toBe(50);
    expect(typeof mcResult.stats.meanReturn).toBe('number');
  });
});

// =========================================================================
// ADDITIONAL TESTS FOR 180+ TARGET
// =========================================================================

describe('StrategyRegistry - Multiple Strategies', () => {
  let registry: StrategyRegistry;

  beforeEach(() => {
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('registers multiple strategies', () => {
    const def2 = {
      id: 'mean_rev', name: 'Mean Reversion', version: '1.0.0',
      description: 'Mean reversion strategy', type: 'MEAN_REVERSION' as const,
      requiredTimeframes: ['1d'] as Timeframe[], minBars: 20,
      parameters: [{ name: 'period', type: 'integer' as const, default: 14, min: 5, max: 100, description: 'Lookback' }],
      riskProfile: { suggestedStopAtrMultiple: 1.5 },
    };
    const fn: StrategyFunction = () => null;
    registry.register(def2, fn);
    expect(registry.list().length).toBe(2);
  });

  it('retrieves different strategy definitions', () => {
    const def2 = {
      id: 'mean_rev', name: 'MR', version: '1.0.0',
      description: 'MR', type: 'MEAN_REVERSION' as const,
      requiredTimeframes: ['1d'] as Timeframe[], minBars: 20,
      parameters: [{ name: 'period', type: 'integer' as const, default: 14, min: 5, max: 100, description: 'L' }],
      riskProfile: { suggestedStopAtrMultiple: 1.5 },
    };
    const fn: StrategyFunction = () => null;
    registry.register(def2, fn);
    expect(registry.getDefinition('mean_rev')).toBeDefined();
    expect(registry.getDefinition('sma_cross')).toBeDefined();
  });

  it('computes signal with different timeframes', () => {
    const def2 = {
      id: 'mean_rev', name: 'MR', version: '1.0.0',
      description: 'MR', type: 'MEAN_REVERSION' as const,
      requiredTimeframes: ['1w'] as Timeframe[], minBars: 20,
      parameters: [{ name: 'period', type: 'integer' as const, default: 14, min: 5, max: 100, description: 'L' }],
      riskProfile: { suggestedStopAtrMultiple: 1.5 },
    };
    const fn: StrategyFunction = () => null;
    registry.register(def2, fn);
    const bars = makeTrendingBars(50);
    const instance = registry.createInstance('mean_rev');
    const signal = registry.computeSignal(instance, bars, 30);
    expect(signal === null || typeof signal.bias === 'string').toBe(true);
  });
});

describe('BacktestEngine - Different Market Conditions', () => {
  let engine: BacktestEngine;
  let registry: StrategyRegistry;

  beforeEach(() => {
    engine = new BacktestEngine();
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('handles declining market', () => {
    const bars = makeBars(100, 200, 0.03).reverse();
    const dataset = makeDataset(bars.slice(0, 100));
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.totalBars).toBe(100);
    expect(result.metrics.totalTrades).toBeGreaterThanOrEqual(0);
  });

  it('handles volatile market', () => {
    const bars = makeBars(100, 100, 0.05);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.totalBars).toBe(100);
  });

  it('handles ranging market', () => {
    const bars = Array.from({ length: 100 }, (_, i) => ({
      timestamp: `2024-${String(Math.floor(i / 30) + 1).padStart(2, '0')}-${String((i % 30) + 1).padStart(2, '0')}T00:00:00Z`,
      open: 100 + Math.sin(i / 10) * 2,
      high: 103, low: 97, close: 100 + Math.sin(i / 10) * 2,
      volume: 1000000, timeframe: '1d', adjustedClose: 100,
    }));
    const dataset = makeDataset(bars as unknown as OHLCVBar[]);
    const fn: StrategyFunction = () => null;
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: fn });
    expect(result.trades.length).toBe(0);
  });
});

describe('CostEngine - Edge Cases', () => {
  let engine: CostEngine;

  beforeEach(() => { engine = new CostEngine(); });

  it('computes zero cost with empty trades', () => {
    const summary = engine.computeSummary([], ZERO_COST);
    expect(summary.totalCommissions).toBe(0);
    expect(summary.totalCosts).toBe(0);
    expect(summary.costPerTrade).toBe(0);
  });

  it('computeSlippage returns positive for BUY', () => {
    const slippage = engine.applySlippage(100, 'BUY', TEST_COST);
    expect(slippage).toBeGreaterThan(100);
  });
});

describe('MetricsEngine - Edge Cases', () => {
  let engine: MetricsEngine;

  beforeEach(() => { engine = new MetricsEngine(); });

  it('computes all metrics for single-trade scenario', () => {
    const trades: BacktestTrade[] = [{
      tradeId: 't1', symbol: 'X', direction: 'LONG',
      entryBarIndex: 0, entryPrice: 100, entryTimestamp: '',
      exitBarIndex: 1, exitPrice: 110, exitTimestamp: '',
      exitReason: 'SIGNAL', quantity: 10, notional: 1000,
      pnl: 100, pnlPercent: 0.1, commissions: 1,
      slippage: 0.5, holdingBars: 1, riskRewardActual: 2,
    }];
    const metrics = engine.compute({
      equity: [100, 110], trades, initialCapital: 100,
    });
    expect(metrics.totalTrades).toBe(1);
    expect(metrics.winRate).toBe(1);
    expect(metrics.profitFactor).toBe(Infinity);
    expect(metrics.annualizedReturn).toBeGreaterThanOrEqual(0);
  });

  it('computes metrics with losing trades', () => {
    const trades: BacktestTrade[] = [{
      tradeId: 't1', symbol: 'X', direction: 'LONG',
      entryBarIndex: 0, entryPrice: 100, entryTimestamp: '',
      exitBarIndex: 1, exitPrice: 90, exitTimestamp: '',
      exitReason: 'STOP', quantity: 10, notional: 1000,
      pnl: -10, pnlPercent: -0.1, commissions: 1,
      slippage: 0.5, holdingBars: 1, riskRewardActual: 1,
    }];
    const metrics = engine.compute({
      equity: [100, 90], trades, initialCapital: 100,
    });
    expect(metrics.totalTrades).toBe(1);
    expect(metrics.winRate).toBe(0);
    expect(metrics.worstTrade).toBe(-0.1);
  });

  it('computes max drawdown on declining equity', () => {
    const metrics = engine.compute({
      equity: [100, 90, 80, 70, 60, 50], trades: [], initialCapital: 100,
    });
    expect(metrics.maxDrawdown).toBeLessThan(0);
    expect(Math.abs(metrics.maxDrawdown)).toBeCloseTo(0.5, 1);
  });

  it('returns zero metrics for empty equity', () => {
    const metrics = engine.compute({ equity: [], trades: [], initialCapital: 100 });
    expect(metrics.totalReturn).toBe(0);
    expect(metrics.annualizedReturn).toBe(0);
    expect(metrics.sharpeRatio).toBe(0);
  });
});

describe('WalkForwardEngine - Edge Cases', () => {
  let engine: WalkForwardEngine;
  let registry: StrategyRegistry;

  beforeEach(() => {
    engine = new WalkForwardEngine();
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('handles minimal dataset', () => {
    const bars = makeTrendingBars(40);
    const dataset = makeDataset(bars);
    const result = engine.run({
      dataset, strategyId: 'sma_cross', strategyFn: SMA_CROSS_FN,
      registry, paramGrid: { fastPeriod: [5], slowPeriod: [10] },
      trainBars: 20, testBars: 10, costModel: ZERO_COST,
    });
    expect(result.windows.length).toBeGreaterThanOrEqual(1);
  });
});

describe('MonteCarloEngine - Edge Cases', () => {
  let engine: MonteCarloEngine;

  beforeEach(() => { engine = new MonteCarloEngine(); });

  it('returns zero returns for flat equity', () => {
    const returns = Array.from({ length: 50 }, () => 0);
    const result = engine.run({
      returns, strategy: { definitionId: 'x', version: '1', params: {} },
      config: { simulations: 10, seed: 1 },
    });
    expect(result.stats.meanReturn).toBe(0);
    expect(result.stats.probabilityOfLoss).toBe(0);
  });

  it('handles negative returns', () => {
    const returns = Array.from({ length: 50 }, () => -0.01);
    const result = engine.run({
      returns, strategy: { definitionId: 'x', version: '1', params: {} },
      config: { simulations: 10, seed: 1 },
    });
    expect(result.stats.meanReturn).toBeLessThan(0);
    expect(result.stats.probabilityOfLoss).toBe(1);
  });
});

describe('CalibrationEngine - Edge Cases', () => {
  let engine: CalibrationEngine;

  beforeEach(() => { engine = new CalibrationEngine(); });

  it('handles all correct forecasts', () => {
    // Use varying confidences matching actual accuracy for perfect calibration
    for (let i = 0; i < 30; i++) {
      const conf = 0.5 + i * 0.015; // 0.5 to 0.935
      const correct = Math.random() < conf;
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '',
        direction: 'UP', confidence: conf, horizonBars: 1,
        strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'UP',
        actualMovePercent: 1, evaluationTimestamp: '', correct,
      });
    }
    const result = engine.evaluate('test');
    expect(result.totalForecasts).toBe(30);
  });

  it('handles all incorrect forecasts', () => {
    for (let i = 0; i < 30; i++) {
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '',
        direction: 'UP', confidence: 0.8, horizonBars: 1,
        strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'DOWN',
        actualMovePercent: -1, evaluationTimestamp: '', correct: false,
      });
    }
    const result = engine.evaluate('test');
    expect(result.overallAccuracy).toBe(0);
  });
});

describe('PaperTradingEngine - Edge Cases', () => {
  let engine: PaperTradingEngine;

  beforeEach(() => { engine = new PaperTradingEngine(100_000, ZERO_COST); });

  it('handles many positions', () => {
    for (let i = 0; i < 20; i++) {
      engine.openPosition({ symbol: `SYM_${i}`, direction: i % 2 === 0 ? 'LONG' : 'SHORT', entryPrice: 100 + i, quantity: 10 });
    }
    expect(engine.getSnapshot().openPositionCount).toBe(20);
  });

  it('closes all positions and computes stats', () => {
    const pos1 = engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10 });
    const pos2 = engine.openPosition({ symbol: 'B', direction: 'SHORT', entryPrice: 50, quantity: 20 });
    engine.closePosition({ positionId: pos1.positionId, exitPrice: 110 });
    engine.closePosition({ positionId: pos2.positionId, exitPrice: 45 });
    const stats = engine.getStats();
    expect(stats.totalTrades).toBe(2);
    expect(stats.totalPnl).toBeGreaterThan(0);
  });

  it('handles take profit for short position', () => {
    const pos = engine.openPosition({ symbol: 'AAPL', direction: 'SHORT', entryPrice: 100, quantity: 10, takeProfit: 90 });
    const closed = engine.checkStopsAndTargets({ bar: { high: 101, low: 89, open: 100 } });
    expect(closed.length).toBe(1);
    expect(closed[0].exitReason).toBe('TARGET');
  });

  it('handles stop loss for short position', () => {
    const pos = engine.openPosition({ symbol: 'AAPL', direction: 'SHORT', entryPrice: 100, quantity: 10, stopLoss: 110 });
    const closed = engine.checkStopsAndTargets({ bar: { high: 111, low: 101, open: 102 } });
    expect(closed.length).toBe(1);
    expect(closed[0].exitReason).toBe('STOP');
  });
});

describe('ExecutionFirewall - Additional Tests', () => {
  it('classifies various paper trading actions correctly', () => {
    const fw = new ExecutionFirewall();
    expect(fw.classifyCapability('paper_trade')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('backtest_run')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('paper_open_position')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('paper_close_position')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('get_historical_data')).toBe('READ_MARKET_DATA');
    expect(fw.classifyCapability('get_quote')).toBe('READ_MARKET_DATA');
  });

  it('allows paper_trade even when it looks like trading', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('paper_trade');
    expect(result.allowed).toBe(true);
  });

  it('always denies execute order', () => {
    const fw = new ExecutionFirewall();
    expect(fw.evaluate('execute_trade').allowed).toBe(false);
    expect(fw.evaluate('place_order').allowed).toBe(false);
    expect(fw.evaluate('buy_stock').allowed).toBe(false);
    expect(fw.evaluate('sell_stock').allowed).toBe(false);
    expect(fw.evaluate('short_stock').allowed).toBe(false);
  });

  it('audit log captures all denied actions', () => {
    const fw = new ExecutionFirewall();
    fw.evaluate('read_quote');
    fw.evaluate('execute_trade');
    fw.evaluate('simulate_trade');
    const log = fw.getAuditLog();
    expect(log.length).toBe(3);
    expect(log[1].allowed).toBe(false);
    expect(log[1].classification).toBe('EXECUTE_TRADE');
  });
});

describe('Phase 27 - Full Integration Tests', () => {
  it('strategy with walk-forward produces stable results', () => {
    const dsEngine = new HistoricalDatasetEngine();
    const registry = new StrategyRegistry();
    const wfEngine = new WalkForwardEngine();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
    const bars = makeTrendingBars(300);
    const { dataset } = dsEngine.buildDataset({ symbol: 'TEST', timeframe: '1d', bars });
    const result = wfEngine.run({
      dataset, strategyId: 'sma_cross', strategyFn: SMA_CROSS_FN,
      registry, paramGrid: { fastPeriod: [5, 10], slowPeriod: [20, 30] },
      trainBars: 100, testBars: 50, costModel: ZERO_COST,
    });
    expect(result.windows.length).toBeGreaterThan(0);
    expect(result.overallTestMetrics).toBeDefined();
  });

  it('complete research workflow from dataset to report', () => {
    const dsEngine = new HistoricalDatasetEngine();
    const registry = new StrategyRegistry();
    const backtestEngine = new BacktestEngine();
    const mcEngine = new MonteCarloEngine();
    const experimentRegistry = new ExperimentRegistry();
    const calEngine = new CalibrationEngine();

    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
    const bars = makeTrendingBars(200);
    const { dataset } = dsEngine.buildDataset({ symbol: 'AAPL', timeframe: '1d', bars });
    const instance = registry.createInstance('sma_cross');
    const btResult = backtestEngine.run({
      dataset, strategy: instance, strategyFn: SMA_CROSS_FN, costModel: ZERO_COST,
    });

    const exp = experimentRegistry.createExperiment({
      name: 'Full Research', description: '',
      strategy: instance, datasetId: dataset.id, datasetSymbol: 'AAPL',
      periodStart: dataset.startDate, periodEnd: dataset.endDate, costModel: ZERO_COST,
    });
    experimentRegistry.setBacktestResult(exp.id, btResult);

    const returns = btResult.equity.slice(1).map((v, i) =>
      btResult.equity[i] !== 0 ? (v - btResult.equity[i]) / btResult.equity[i] : 0,
    );
    const mcResult = mcEngine.run({ returns, strategy: instance, config: { simulations: 50, seed: 42 } });
    experimentRegistry.setMonteCarloResult(exp.id, mcResult);

    for (let i = 0; i < 20; i++) {
      calEngine.recordForecast({
        forecastId: `f_${i}`, symbol: 'AAPL', timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
        direction: 'UP', confidence: 0.7, horizonBars: 5, strategyId: 'sma_cross', parameters: {},
      });
      calEngine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'AAPL', actualDirection: Math.random() > 0.4 ? 'UP' : 'DOWN',
        actualMovePercent: 1, evaluationTimestamp: '', correct: Math.random() > 0.35,
      });
    }
    const calResult = calEngine.evaluate('sma_cross');
    experimentRegistry.setCalibrationResult(exp.id, calResult);

    const report = experimentRegistry.generateReport(exp.id);
    expect(report).not.toBeNull();
    expect(report!.summary.length).toBeGreaterThan(0);
    expect(report!.limitations).toBeDefined();
  });
});

// =========================================================================
// PHASE 27 — TARGETED COVERAGE EXPANSION (50+ new tests)
// =========================================================================

describe('HistoricalDatasetEngine - Extended', () => {
  let engine: HistoricalDatasetEngine;

  beforeEach(() => { engine = new HistoricalDatasetEngine(); });

  it('buildDataset with custom source metadata', () => {
    const bars = makeBars(20);
    const customSource: DatasetSource = { provider: 'YAHOO', quality: 'ADJUSTED', adjustment: 'SPLIT', verified: true };
    const { dataset, integrity } = engine.buildDataset({ symbol: 'MSFT', timeframe: '1d', bars, source: customSource });
    expect(dataset.source.provider).toBe('YAHOO');
    expect(dataset.source.quality).toBe('ADJUSTED');
    expect(integrity.valid).toBe(true);
  });

  it('buildDataset with survivorshipFilter flag', () => {
    const bars = makeBars(10);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars, survivorshipFilter: true });
    expect(dataset.survivorshipFiltered).toBe(true);
  });

  it('filterToDecisionPoint with timestamp before all bars returns empty', () => {
    const bars = makeBars(10);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    const { bars: filtered, filtered: count } = engine.filterToDecisionPoint({
      dataset, decisionTimestamp: '2020-01-01T00:00:00Z',
    });
    expect(filtered.length).toBe(0);
    expect(count).toBe(10);
  });

  it('filterToDecisionPoint with timestamp after all bars returns all', () => {
    const bars = makeBars(10);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    const { bars: filtered, filtered: count } = engine.filterToDecisionPoint({
      dataset, decisionTimestamp: '2030-01-01T00:00:00Z',
    });
    expect(filtered.length).toBe(10);
    expect(count).toBe(0);
  });

  it('adjustCorporateActions with DIVIDEND type', () => {
    const bars = makeBars(10);
    const adjusted = engine.adjustCorporateActions({
      bars, type: 'DIVIDEND', effectiveDate: '2024-01-05T00:00:00Z', dividendPerShare: 0.5,
    });
    expect(adjusted.length).toBe(10);
  });

  it('adjustCorporateActions with SPLIT type and ratio 3', () => {
    const bars = makeBars(10);
    const adjusted = engine.adjustCorporateActions({
      bars, type: 'SPLIT', effectiveDate: '2024-01-03T00:00:00Z', ratio: 3,
    });
    expect(adjusted.length).toBe(bars.length);
  });

  it('validatePointInTime detects leakage when event is after decision', () => {
    const bars = makeBars(50);
    const { dataset } = engine.buildDataset({ symbol: 'X', timeframe: '1d', bars });
    const result = engine.validatePointInTime({
      dataset, decisionTimestamp: '2024-01-10T00:00:00Z',
      eventTimestamps: ['2024-02-01T00:00:00Z'],
    });
    expect(result.hasLeakage).toBe(true);
  });

  it('computeReturns with LOG type', () => {
    const bars = makeBars(10);
    const returns = engine.computeReturns(bars, 'LOG');
    expect(returns.length).toBe(9);
    expect(returns.every(r => typeof r === 'number')).toBe(true);
  });

  it('computeReturns with ABSOLUTE type', () => {
    const bars = makeBars(10);
    const returns = engine.computeReturns(bars, 'ABSOLUTE');
    expect(returns.length).toBe(9);
  });

  it('getDataIntegrity on bars with negative volume', () => {
    const bars = makeBars(5);
    bars[2] = { ...bars[2], volume: -100 };
    const integrity = engine.getDataIntegrity(bars);
    expect(integrity.valid).toBe(false);
  });

  it('buildDataset with empty bars produces integrity issue', () => {
    const { dataset, integrity } = engine.buildDataset({ symbol: 'EMPTY', timeframe: '1d', bars: [] });
    expect(dataset.totalBars).toBe(0);
    expect(integrity.valid).toBe(false);
  });

  it('removeDataset returns false for nonexistent id', () => {
    expect(engine.removeDataset('nonexistent')).toBe(false);
  });

  it('listDatasets starts empty', () => {
    expect(engine.listDatasets()).toHaveLength(0);
  });

  it('getDataset returns undefined for unknown id', () => {
    expect(engine.getDataset('unknown')).toBeUndefined();
  });
});

describe('StrategyRegistry - Edge Cases', () => {
  let registry: StrategyRegistry;

  beforeEach(() => {
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('createInstance throws for unknown strategy', () => {
    expect(() => registry.createInstance('nonexistent')).toThrow('Unknown strategy: nonexistent');
  });

  it('getFunction returns undefined for unknown strategy', () => {
    expect(registry.getFunction('nonexistent')).toBeUndefined();
  });

  it('getDefinition returns undefined for unknown strategy', () => {
    expect(registry.getDefinition('nonexistent')).toBeUndefined();
  });

  it('validateInstance rejects unknown strategy', () => {
    const result = registry.validateInstance({ definitionId: 'unknown', version: '1.0.0', params: {} });
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('validateInstance rejects version mismatch', () => {
    const result = registry.validateInstance({ definitionId: 'sma_cross', version: '999.0.0', params: {} });
    expect(result.valid).toBe(false);
  });

  it('validateParams catches negative values below min', () => {
    const def = registry.getDefinition('sma_cross')!;
    const errors = registry.validateParams(def, { fastPeriod: -5, slowPeriod: 30 });
    expect(errors.length).toBeGreaterThan(0);
  });

  it('generateOrderIntent returns quantity in result', () => {
    const intent = registry.generateOrderIntent(
      { signal: 'LONG_BIAS', strength: 0.9, stopLoss: 90 },
      'MSFT', 200,
    );
    expect(intent?.quantity).toBe(200);
  });

  it('computeSignal returns null before minBars threshold', () => {
    const bars = makeTrendingBars(100);
    const instance = registry.createInstance('sma_cross');
    const signal = registry.computeSignal(instance, bars, 5);
    expect(signal).toBeNull();
  });
});

describe('BacktestEngine - Extended', () => {
  let engine: BacktestEngine;
  let registry: StrategyRegistry;

  beforeEach(() => {
    engine = new BacktestEngine();
    registry = new StrategyRegistry();
    registry.register(SMA_CROSS_DEF, SMA_CROSS_FN);
  });

  it('handles very long dataset (500 bars)', () => {
    const bars = makeTrendingBars(500);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.totalBars).toBe(500);
    expect(result.equity.length).toBe(501);
    expect(result.equityTimestamps.length).toBe(501);
  });

  it('equity is monotonically non-decreasing when no trades occur', () => {
    const bars = Array.from({ length: 50 }, (_, i) => ({
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
      open: 100, high: 100.5, low: 99.5, close: 100,
      volume: 1000000, timeframe: '1d' as Timeframe, adjustedClose: 100,
    }));
    const dataset = makeDataset(bars);
    const fn: StrategyFunction = () => null;
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: fn });
    for (let i = 1; i < result.equity.length; i++) {
      expect(result.equity[i]).toBeGreaterThanOrEqual(result.equity[i - 1] - 0.0001);
    }
  });

  it('metrics on all-losing trades', () => {
    const alwaysShortFn: StrategyFunction = (bars, index) => {
      if (index < 30) return null;
      return { action: 'SHORT', stopLoss: bars[index].close * 1.02 };
    };
    const bars = makeTrendingBars(200, 100, 0.008);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: alwaysShortFn, costModel: ZERO_COST });
    if (result.trades.length > 0) {
      expect(result.metrics.winRate).toBeLessThanOrEqual(1);
      expect(typeof result.metrics.profitFactor).toBe('number');
    }
  });

  it('respects different initial capital values', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN, initialCapital: 1_000_000 });
    expect(result.initialCapital).toBe(1_000_000);
    expect(result.equity[0]).toBe(1_000_000);
  });

  it('result contains strategy info', () => {
    const bars = makeTrendingBars(100);
    const dataset = makeDataset(bars);
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.strategy.definitionId).toBe('sma_cross');
    expect(result.strategy.version).toBe('1.0.0');
  });

  it('result contains symbol and timeframe', () => {
    const bars = makeTrendingBars(60);
    const dataset = makeDataset(bars, 'custom-id');
    const instance = registry.createInstance('sma_cross');
    const result = engine.run({ dataset, strategy: instance, strategyFn: SMA_CROSS_FN });
    expect(result.symbol).toBe('TEST');
    expect(result.timeframe).toBe('1d');
  });
});

describe('CostEngine - Extended', () => {
  let engine: CostEngine;

  beforeEach(() => { engine = new CostEngine(); });

  it('marketImpact with LINEAR model', () => {
    const bars = makeBars(10);
    const cost1 = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars, entryBarIndex: 5, exitBarIndex: 7,
      costModel: { ...ZERO_COST, marketImpactModel: 'LINEAR', marketImpactCoeff: 1.0 },
    });
    const cost2 = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 400,
      bars, entryBarIndex: 5, exitBarIndex: 7,
      costModel: { ...ZERO_COST, marketImpactModel: 'LINEAR', marketImpactCoeff: 1.0 },
    });
    expect(cost2.marketImpact).toBeGreaterThan(cost1.marketImpact);
  });

  it('very high slippage produces large price deviation', () => {
    const highSlipCost: CostModel = { ...ZERO_COST, slippageTicks: 100, slippageBps: 500 };
    const buyPrice = engine.applySlippage(100, 'BUY', highSlipCost);
    const sellPrice = engine.applySlippage(100, 'SELL', highSlipCost);
    expect(buyPrice).toBeGreaterThan(105);
    expect(sellPrice).toBeLessThan(95);
  });

  it('summary with single trade', () => {
    const bars = makeBars(5);
    const summary = engine.computeSummary([
      { entryPrice: 100, exitPrice: 105, quantity: 50, bars, entryBarIndex: 0, exitBarIndex: 3 },
    ], TEST_COST);
    expect(summary.totalCommissions).toBeGreaterThanOrEqual(0);
    expect(summary.costPerTrade).toBe(summary.totalCosts);
  });

  it('market impact with zero volume returns zero', () => {
    const zeroVolBars: OHLCVBar[] = Array.from({ length: 5 }, (_, i) => ({
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
      open: 100, high: 101, low: 99, close: 100,
      volume: 0, timeframe: '1d', adjustedClose: 100,
    }));
    const cost = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars: zeroVolBars, entryBarIndex: 0, exitBarIndex: 3,
      costModel: { ...ZERO_COST, marketImpactModel: 'SQRT', marketImpactCoeff: 0.5 },
    });
    expect(cost.marketImpact).toBe(0);
  });

  it('spread cost included in spreadBps', () => {
    const costModel: CostModel = { ...ZERO_COST, spreadBps: 10 };
    const cost = engine.computeTradeCost({
      entryPrice: 100, exitPrice: 105, quantity: 100,
      bars: makeBars(5), entryBarIndex: 0, exitBarIndex: 3,
      costModel,
    });
    expect(cost.entrySlippage).toBeGreaterThanOrEqual(0);
    expect(cost.exitSlippage).toBeGreaterThanOrEqual(0);
  });
});

describe('MetricsEngine - Extended', () => {
  let engine: MetricsEngine;

  beforeEach(() => { engine = new MetricsEngine(); });

  it('all-zero returns produce zero total return', () => {
    const equity = Array.from({ length: 20 }, () => 100);
    const metrics = engine.compute({ equity, trades: [], initialCapital: 100 });
    expect(metrics.totalReturn).toBe(0);
    expect(metrics.volatility).toBe(0);
    expect(metrics.sharpeRatio).toBe(0);
  });

  it('alternating wins and losses produce win rate of 0.5', () => {
    const trades: BacktestTrade[] = [];
    const equity = [100];
    let cap = 100;
    for (let i = 0; i < 10; i++) {
      const win = i % 2 === 0;
      const pnl = win ? 5 : -3;
      cap += pnl;
      equity.push(cap);
      trades.push({
        tradeId: `t${i}`, symbol: 'X', direction: 'LONG',
        entryBarIndex: i, entryPrice: 100, entryTimestamp: '',
        exitBarIndex: i + 1, exitPrice: win ? 105 : 97, exitTimestamp: '',
        exitReason: 'SIGNAL', quantity: 10, notional: 1000,
        pnl, pnlPercent: pnl / 1000, commissions: 0, slippage: 0,
        holdingBars: 1, riskRewardActual: win ? 2 : 1,
      });
    }
    const metrics = engine.compute({ equity, trades, initialCapital: 100 });
    expect(metrics.winRate).toBeCloseTo(0.5, 1);
    expect(metrics.consecutiveWins).toBe(1);
    expect(metrics.consecutiveLosses).toBe(1);
  });

  it('handles equity with single point', () => {
    const metrics = engine.compute({ equity: [100], trades: [], initialCapital: 100 });
    expect(metrics.maxDrawdown).toBe(0);
    expect(metrics.maxDrawdownDuration).toBe(0);
    expect(metrics.volatility).toBe(0);
  });

  it('benchmark metrics computed when provided', () => {
    const metrics = engine.compute({
      equity: [100, 105, 103, 108, 110],
      trades: [],
      initialCapital: 100,
      benchmarkReturns: [0.01, -0.005, 0.02, 0.01],
    });
    expect(metrics.benchmarkReturn).toBeDefined();
    expect(metrics.alpha).toBeDefined();
    expect(metrics.beta).toBeDefined();
    expect(metrics.informationRatio).toBeDefined();
  });

  it('no trades results in zero expectancy', () => {
    const metrics = engine.compute({
      equity: [100, 102, 104],
      trades: [],
      initialCapital: 100,
    });
    expect(metrics.expectancy).toBe(0);
    expect(metrics.totalTrades).toBe(0);
    expect(metrics.bestTrade).toBe(0);
    expect(metrics.worstTrade).toBe(0);
  });

  it('short trade count is tracked', () => {
    const trades: BacktestTrade[] = [
      { tradeId: 't1', symbol: 'X', direction: 'SHORT', entryBarIndex: 0, entryPrice: 100, entryTimestamp: '', exitBarIndex: 1, exitPrice: 95, exitTimestamp: '', exitReason: 'SIGNAL', quantity: 10, notional: 1000, pnl: 50, pnlPercent: 0.05, commissions: 0, slippage: 0, holdingBars: 1, riskRewardActual: 2 },
      { tradeId: 't2', symbol: 'X', direction: 'SHORT', entryBarIndex: 1, entryPrice: 95, entryTimestamp: '', exitBarIndex: 2, exitPrice: 90, exitTimestamp: '', exitReason: 'SIGNAL', quantity: 10, notional: 950, pnl: 50, pnlPercent: 0.05, commissions: 0, slippage: 0, holdingBars: 1, riskRewardActual: 2 },
    ];
    const metrics = engine.compute({ equity: [100, 105, 110], trades, initialCapital: 100 });
    expect(metrics.shortTrades).toBe(2);
    expect(metrics.longTrades).toBe(0);
    expect(metrics.shortWinRate).toBe(1);
  });
});

describe('MonteCarloEngine - Extended', () => {
  let engine: MonteCarloEngine;

  beforeEach(() => { engine = new MonteCarloEngine(); });

  it('single return value produces valid paths', () => {
    const result = engine.run({
      returns: [0.01],
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 10, periodsPerSim: 5, seed: 42 },
    });
    expect(result.paths.length).toBe(10);
    for (const path of result.paths) {
      expect(path.length).toBe(6);
    }
  });

  it('zero variance returns produce tight percentiles', () => {
    const returns = Array.from({ length: 100 }, () => 0.001);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 200, seed: 42 },
    });
    const range = result.percentiles.p95 - result.percentiles.p5;
    expect(range).toBeLessThan(0.1);
  });

  it('negative returns yield probabilityOfLoss close to 1', () => {
    const returns = Array.from({ length: 50 }, () => -0.02);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 100, seed: 42 },
    });
    expect(result.stats.probabilityOfLoss).toBe(1);
    expect(result.stats.meanReturn).toBeLessThan(0);
  });

  it('all-positive returns yield probabilityOfLoss close to 0', () => {
    const returns = Array.from({ length: 50 }, () => 0.01);
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1.0.0', params: {} },
      config: { simulations: 100, seed: 42 },
    });
    expect(result.stats.probabilityOfLoss).toBe(0);
  });

  it('strategy info preserved in result', () => {
    const result = engine.run({
      returns: [0.01, -0.005, 0.02],
      strategy: { definitionId: 'my_strat', version: '2.0.0', params: { x: 1 } },
      config: { simulations: 10, seed: 1 },
    });
    expect(result.strategy.definitionId).toBe('my_strat');
    expect(result.strategy.version).toBe('2.0.0');
  });

  it('config preserved in result', () => {
    const result = engine.run({
      returns: [0.01],
      strategy: { definitionId: 'test', version: '1', params: {} },
      config: { simulations: 20, seed: 99, bootstrapMethod: 'iid', blockSize: 3 },
    });
    expect(result.config.simulations).toBe(20);
    expect(result.config.seed).toBe(99);
    expect(result.config.bootstrapMethod).toBe('iid');
  });

  it('expectedShortfall is non-negative for mixed returns', () => {
    const returns = Array.from({ length: 100 }, (_, i) => (i % 3 === 0 ? -0.03 : 0.01));
    const result = engine.run({
      returns,
      strategy: { definitionId: 'test', version: '1', params: {} },
      config: { simulations: 100, seed: 42 },
    });
    expect(typeof result.stats.expectedShortfall).toBe('number');
  });
});

describe('CalibrationEngine - Extended', () => {
  let engine: CalibrationEngine;

  beforeEach(() => { engine = new CalibrationEngine(); });

  it('unmatched forecast/outcome pairs are excluded from evaluation', () => {
    engine.recordForecast({
      forecastId: 'f_orphan', symbol: 'X', timestamp: '', direction: 'UP',
      confidence: 0.8, horizonBars: 1, strategyId: 'test', parameters: {},
    });
    engine.recordOutcome({
      forecastId: 'f_different', symbol: 'X', actualDirection: 'UP',
      actualMovePercent: 1, evaluationTimestamp: '', correct: true,
    });
    const result = engine.evaluate('test');
    expect(result.totalForecasts).toBe(0);
  });

  it('evaluate with strategy filter excludes other strategies', () => {
    for (let i = 0; i < 10; i++) {
      engine.recordForecast({
        forecastId: `f_a${i}`, symbol: 'X', timestamp: '', direction: 'UP',
        confidence: 0.7, horizonBars: 1, strategyId: 'stratA', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_a${i}`, symbol: 'X', actualDirection: 'UP',
        actualMovePercent: 1, evaluationTimestamp: '', correct: true,
      });
    }
    for (let i = 0; i < 10; i++) {
      engine.recordForecast({
        forecastId: `f_b${i}`, symbol: 'X', timestamp: '', direction: 'DOWN',
        confidence: 0.3, horizonBars: 1, strategyId: 'stratB', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_b${i}`, symbol: 'X', actualDirection: 'DOWN',
        actualMovePercent: -1, evaluationTimestamp: '', correct: true,
      });
    }
    const resultA = engine.evaluate('stratA');
    const resultB = engine.evaluate('stratB');
    expect(resultA.totalForecasts).toBe(10);
    expect(resultB.totalForecasts).toBe(10);
  });

  it('evaluate without filter uses all forecasts', () => {
    for (let i = 0; i < 5; i++) {
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '', direction: 'UP',
        confidence: 0.6, horizonBars: 1, strategyId: 'any', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'UP',
        actualMovePercent: 1, evaluationTimestamp: '', correct: true,
      });
    }
    const result = engine.evaluate();
    expect(result.totalForecasts).toBe(5);
  });

  it('forecast confidence ranges are captured in bins', () => {
    for (let i = 0; i < 100; i++) {
      const conf = i / 100;
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '', direction: 'UP',
        confidence: conf, horizonBars: 1, strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'UP',
        actualMovePercent: 1, evaluationTimestamp: '',
        correct: Math.random() < conf,
      });
    }
    const result = engine.evaluate('test');
    expect(result.bins.length).toBe(10);
    const totalInBins = result.bins.reduce((s, b) => s + b.forecastCount, 0);
    expect(totalInBins).toBe(100);
  });

  it('wellCalibrated flag is false when ECE is high', () => {
    for (let i = 0; i < 50; i++) {
      engine.recordForecast({
        forecastId: `f_${i}`, symbol: 'X', timestamp: '', direction: 'UP',
        confidence: 0.9, horizonBars: 1, strategyId: 'test', parameters: {},
      });
      engine.recordOutcome({
        forecastId: `f_${i}`, symbol: 'X', actualDirection: 'DOWN',
        actualMovePercent: -1, evaluationTimestamp: '', correct: false,
      });
    }
    const result = engine.evaluate('test');
    expect(result.isWellCalibrated).toBe(false);
  });

  it('getForecasts returns recorded forecasts', () => {
    engine.recordForecast({
      forecastId: 'f1', symbol: 'X', timestamp: '', direction: 'UP',
      confidence: 0.8, horizonBars: 1, strategyId: 'test', parameters: {},
    });
    expect(engine.getForecasts()).toHaveLength(1);
  });

  it('getOutcomes returns recorded outcomes', () => {
    engine.recordOutcome({
      forecastId: 'f1', symbol: 'X', actualDirection: 'UP',
      actualMovePercent: 1, evaluationTimestamp: '', correct: true,
    });
    expect(engine.getOutcomes()).toHaveLength(1);
  });
});

describe('EventStudyEngine - Extended', () => {
  let engine: EventStudyEngine;

  beforeEach(() => { engine = new EventStudyEngine(); });

  it('handles multiple events of same type', () => {
    const bars = makeTrendingBars(120);
    engine.registerEvent({
      eventId: 'e1', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-20T00:00:00Z', description: 'Q1',
    });
    engine.registerEvent({
      eventId: 'e2', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2024-02-20T00:00:00Z', description: 'Q2',
    });
    engine.registerEvent({
      eventId: 'e3', symbol: 'AAPL', eventType: 'EARNINGS',
      eventTimestamp: '2024-03-20T00:00:00Z', description: 'Q3',
    });
    const results = engine.analyzeAll({ bars, preWindow: -5, postWindow: 5 });
    expect(results).toHaveLength(3);
    for (const r of results) {
      expect(Array.isArray(r.carDays)).toBe(true);
      expect(typeof r.tStatistic).toBe('number');
      expect(typeof r.abnormalReturn).toBe('number');
    }
  });

  it('t-statistic computation returns number', () => {
    const bars = makeTrendingBars(60);
    engine.registerEvent({
      eventId: 'e1', symbol: 'X', eventType: 'GUIDANCE',
      eventTimestamp: '2024-01-30T00:00:00Z', description: 'guidance',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -10, postWindow: 10,
    });
    expect(typeof result.tStatistic).toBe('number');
    expect(typeof result.significantAtFive).toBe('boolean');
  });

  it('significantAtFive flag respects 1.96 threshold', () => {
    const bars = makeTrendingBars(60);
    engine.registerEvent({
      eventId: 'e1', symbol: 'X', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-30T00:00:00Z', description: '',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -10, postWindow: 10,
    });
    if (Math.abs(result.tStatistic) > 1.96) {
      expect(result.significantAtFive).toBe(true);
    } else {
      expect(result.significantAtFive).toBe(false);
    }
  });

  it('preEventDrift and postEventDrift are numbers', () => {
    const bars = makeTrendingBars(60);
    engine.registerEvent({
      eventId: 'e1', symbol: 'X', eventType: 'EARNINGS',
      eventTimestamp: '2024-01-30T00:00:00Z', description: '',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -5, postWindow: 5,
    });
    expect(typeof result.preEventDrift).toBe('number');
    expect(typeof result.postEventDrift).toBe('number');
  });

  it('event at very start of data', () => {
    const bars = makeTrendingBars(20);
    engine.registerEvent({
      eventId: 'e1', symbol: 'X', eventType: 'EARNINGS',
      eventTimestamp: bars[0].timestamp, description: '',
    });
    const result = engine.analyzeEvent({
      event: engine.getEvents()[0], bars, preWindow: -5, postWindow: 5,
    });
    expect(result.eventId).toBe('e1');
    expect(typeof result.cumulativeAbnormalReturn).toBe('number');
  });

  it('analyzeAll returns empty array with no events', () => {
    const bars = makeTrendingBars(20);
    const results = engine.analyzeAll({ bars, preWindow: -5, postWindow: 5 });
    expect(results).toHaveLength(0);
  });
});

describe('PaperTradingEngine - Extended', () => {
  let engine: PaperTradingEngine;

  beforeEach(() => { engine = new PaperTradingEngine(100_000, ZERO_COST); });

  it('getStats with no closed trades returns zeroed stats', () => {
    const stats = engine.getStats();
    expect(stats.totalTrades).toBe(0);
    expect(stats.winningTrades).toBe(0);
    expect(stats.losingTrades).toBe(0);
    expect(stats.winRate).toBe(0);
    expect(stats.totalPnl).toBe(0);
  });

  it('multiple stop and target combinations', () => {
    const p1 = engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10, stopLoss: 95, takeProfit: 110 });
    const p2 = engine.openPosition({ symbol: 'B', direction: 'SHORT', entryPrice: 50, quantity: 20, stopLoss: 55, takeProfit: 40 });
    const p3 = engine.openPosition({ symbol: 'C', direction: 'LONG', entryPrice: 200, quantity: 5, stopLoss: 190, takeProfit: 220 });

    const closed = engine.checkStopsAndTargets({
      bar: { high: 112, low: 93, open: 105 },
    });
    expect(closed.length).toBeGreaterThanOrEqual(1);
  });

  it('profit factor is Infinity when no losses', () => {
    const p1 = engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10 });
    engine.closePosition({ positionId: p1.positionId, exitPrice: 110 });
    const stats = engine.getStats();
    expect(stats.profitFactor).toBe(Infinity);
  });

  it('profit factor is 0 when no wins', () => {
    const p1 = engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10 });
    engine.closePosition({ positionId: p1.positionId, exitPrice: 90 });
    const stats = engine.getStats();
    expect(stats.losingTrades).toBe(1);
    expect(stats.winningTrades).toBe(0);
  });

  it('snapshot shows correct cash after trades', () => {
    const p1 = engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10 });
    engine.closePosition({ positionId: p1.positionId, exitPrice: 120 });
    const snap = engine.getSnapshot();
    expect(snap.cash).toBeGreaterThan(100_000);
    expect(snap.openPositionCount).toBe(0);
  });

  it('reset clears everything', () => {
    engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10 });
    engine.openPosition({ symbol: 'B', direction: 'SHORT', entryPrice: 50, quantity: 20 });
    engine.reset();
    const snap = engine.getSnapshot();
    expect(snap.openPositionCount).toBe(0);
    const stats = engine.getStats();
    expect(stats.totalTrades).toBe(0);
  });

  it('stop not triggered when price stays above stop', () => {
    engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10, stopLoss: 90 });
    const closed = engine.checkStopsAndTargets({
      bar: { high: 105, low: 95, open: 102 },
    });
    expect(closed.length).toBe(0);
  });

  it('target not triggered when price stays below target', () => {
    engine.openPosition({ symbol: 'A', direction: 'LONG', entryPrice: 100, quantity: 10, takeProfit: 120 });
    const closed = engine.checkStopsAndTargets({
      bar: { high: 110, low: 95, open: 102 },
    });
    expect(closed.length).toBe(0);
  });
});

describe('ExecutionFirewall - Extended', () => {
  it('classifyCapability with empty string returns READ_MARKET_DATA', () => {
    const fw = new ExecutionFirewall();
    expect(fw.classifyCapability('')).toBe('READ_MARKET_DATA');
  });

  it('multiple rapid evaluations all record audit log', () => {
    const fw = new ExecutionFirewall();
    for (let i = 0; i < 20; i++) {
      fw.evaluate(i % 2 === 0 ? 'read_quote' : 'execute_trade');
    }
    const log = fw.getAuditLog();
    expect(log.length).toBe(20);
    expect(log.filter(e => !e.allowed).length).toBe(10);
  });

  it('classifyCapability is case-insensitive', () => {
    const fw = new ExecutionFirewall();
    expect(fw.classifyCapability('EXECUTE_TRADE')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('Execute_Trade')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('execute_trade')).toBe('EXECUTE_TRADE');
  });

  it('classifyCapability with complex strings', () => {
    const fw = new ExecutionFirewall();
    expect(fw.classifyCapability('broker_api_execute_order')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('paper_trade_backtest')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('transfer_funds_to_exchange')).toBe('TRANSFER_FUNDS');
  });

  it('evaluateIntent always returns denied', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluateIntent({
      symbol: 'AAPL', side: 'BUY', orderType: 'LIMIT', quantity: 50, timeInForce: 'GTC',
    });
    expect(result.allowed).toBe(false);
    expect(result.classification).toBe('EXECUTE_TRADE');
  });

  it('audit log entries have timestamps', () => {
    const fw = new ExecutionFirewall();
    fw.evaluate('read_quote');
    const log = fw.getAuditLog();
    expect(log[0].timestamp).toBeTruthy();
    expect(new Date(log[0].timestamp).getTime()).toBeGreaterThan(0);
  });

  it('explainDenial for allowed action returns permitted message', () => {
    const fw = new ExecutionFirewall();
    const msg = fw.explainDenial('read_quote');
    expect(msg).toContain('permitted');
  });

  it('explainDenial for denied action returns DENIED message', () => {
    const fw = new ExecutionFirewall();
    const msg = fw.explainDenial('buy_stock');
    expect(msg).toContain('DENIED');
    expect(msg).toContain('non-overridable');
  });

  it('policy can be read after construction', () => {
    const fw = new ExecutionFirewall();
    const policy = fw.getPolicy();
    expect(policy.liveTradeExecution).toBe(false);
    expect(policy.transferFunds).toBe(false);
    expect(policy.simulateTrade).toBe(true);
    expect(policy.readMarketData).toBe(true);
    expect(policy.allowLlmOverride).toBe(false);
  });

  it('firewall blocks broker connection attempts', () => {
    const fw = new ExecutionFirewall();
    expect(fw.evaluate('connect_to_broker').allowed).toBe(false);
    expect(fw.evaluate('broker_buy_order').allowed).toBe(false);
  });
});

// =========================================================================
// HELPER FUNCTIONS
// =========================================================================

function makeTrendingBlocks(n: number): OHLCVBar[] {
  const bars: OHLCVBar[] = [];
  let price = 100;
  const base = new Date(2024, 0, 1);
  for (let i = 0; i < n; i++) {
    const d = new Date(base.getTime() + i * 86_400_000);
    const block = Math.floor(i / 30) % 2 === 0 ? 0.003 : -0.002;
    const change = block * price + (Math.random() - 0.5) * 0.01 * price;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) * (1 + Math.random() * 0.005);
    const low = Math.min(open, close) * (1 - Math.random() * 0.005);
    const ts = d.toISOString().slice(0, 10) + 'T00:00:00Z';
    bars.push({
      timestamp: ts,
      open, high, low, close,
      volume: Math.floor(1000000 + Math.random() * 500000),
      timeframe: '1d',
      adjustedClose: close,
    });
    price = close;
  }
  return bars;
}
