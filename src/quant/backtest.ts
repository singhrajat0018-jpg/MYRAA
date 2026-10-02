// ============================================================================
// MYRAA Phase 27 — Backtest / Simulation Engine
// ============================================================================

import type {
  BacktestResult, BacktestTrade, StrategyInstance, HistoricalDataset,
  CostModel, PerformanceMetrics, TradeDirection,
} from './contracts';
import type { OHLCVBar } from '../finance/contracts';
import { CostEngine } from './costs';
import { MetricsEngine } from './metrics';
import type { StrategyFunction, StrategyRegistry } from './strategy';
import { TechnicalAnalysisEngine } from '../finance/technical';

export class BacktestEngine {
  private readonly costEngine = new CostEngine();
  private readonly metricsEngine = new MetricsEngine();
  private readonly technicalEngine = new TechnicalAnalysisEngine();

  run(params: {
    dataset: HistoricalDataset;
    strategy: StrategyInstance;
    strategyFn: StrategyFunction;
    costModel?: CostModel;
    initialCapital?: number;
    riskFreeRate?: number;
  }): BacktestResult {
    const { dataset, strategy, strategyFn, costModel, initialCapital = 100_000, riskFreeRate = 0.0 } = params;
    const bars = dataset.bars;
    if (bars.length < 2) {
      return this.emptyResult(strategy, dataset, initialCapital);
    }
    const equity: number[] = [initialCapital];
    const equityTimestamps: string[] = [bars[0].timestamp];
    const trades: BacktestTrade[] = [];
    let cash = initialCapital;
    let position: {
      direction: TradeDirection; entryPrice: number; entryBarIndex: number;
      quantity: number; stopLoss?: number; target?: number;
    } | null = null;

    for (let i = 0; i < bars.length; i++) {
      const bar = bars[i];
      if (position) {
        const exit = this.checkExit(bar, position, i, bars);
        if (exit) {
          const trade = this.closePosition(position, exit, bar, i, costModel, bars);
          trades.push(trade);
          cash += trade.pnl;
          position = null;
        }
      }
      if (!position) {
        // Compute technical analysis - single or multi-timeframe as required by strategy
        // Note: In a full implementation, we would get the strategy definition
        // and use it to determine required timeframes
        // For this implementation, we'll assume single timeframe for simplicity
        // and to maintain compatibility with existing strategy functions
        const technical = this.technicalEngine.analyze(bars, dataset.timeframe, '');

        // Call strategy function with technical analysis (same path as live analysis)
        const signalResult = strategyFn(bars as unknown as OHLCVBar[], i, strategy.params, technical);
        if (signalResult && signalResult.action !== 'FLAT') {
          const direction: TradeDirection = signalResult.action === 'LONG' ? 'LONG' : 'SHORT';
          const entryPrice = this.getEntryPrice(bar, direction, costModel);
          const riskPct = strategy.params['riskPerTrade'] as number || 0.02;
          const stopDistance = signalResult.stopLoss ? Math.abs(entryPrice - signalResult.stopLoss) : entryPrice * riskPct;
          const quantity = stopDistance > 0 ? Math.floor((cash * riskPct) / stopDistance) : 0;
          if (quantity > 0) {
            position = {
              direction, entryPrice, entryBarIndex: i,
              quantity, stopLoss: signalResult.stopLoss, target: signalResult.target,
            };
          }
        }
      }
      equity.push(cash + this.positionValue(position, bar));
      equityTimestamps.push(bar.timestamp);
    }

    if (position) {
      const lastBar = bars[bars.length - 1];
      const trade = this.closePosition(position, 'END_OF_DATA', lastBar, bars.length - 1, costModel, bars);
      trades.push(trade);
      cash += trade.pnl;
      equity[equity.length - 1] = cash;
    }

    const costSummary = this.costEngine.computeSummary(
      trades.map(t => ({
        entryPrice: t.entryPrice, exitPrice: t.exitPrice, quantity: t.quantity,
        bars, entryBarIndex: t.entryBarIndex, exitBarIndex: t.exitBarIndex,
      })),
      costModel ?? { commissionPerTrade: 0, commissionPerShare: 0, commissionPercent: 0, slippageTicks: 0, slippageBps: 0, marketImpactModel: 'NONE', marketImpactCoeff: 0, spreadBps: 0 },
    );

    const metrics = this.metricsEngine.compute({ equity, trades, initialCapital, riskFreeRate });

    return {
      strategy: { ...strategy },
      datasetId: dataset.id,
      symbol: dataset.symbol,
      timeframe: dataset.timeframe,
      periodStart: bars[0].timestamp,
      periodEnd: bars[bars.length - 1].timestamp,
      initialCapital,
      finalEquity: equity[equity.length - 1],
      equity: Object.freeze(equity),
      equityTimestamps: Object.freeze(equityTimestamps),
      trades: Object.freeze(trades),
      metrics,
      totalBars: bars.length,
      costsApplied: costSummary,
      timestamp: new Date().toISOString(),
    };
  }

  private checkExit(
    bar: OHLCVBar, position: { direction: TradeDirection; entryPrice: number; stopLoss?: number; target?: number },
    index: number, bars: readonly OHLCVBar[],
  ): TradeDirection | 'STOP' | 'TARGET' | 'END_OF_DATA' | null {
    if (position.direction === 'LONG') {
      if (position.stopLoss && bar.low <= position.stopLoss) return 'STOP';
      if (position.target && bar.high >= position.target) return 'TARGET';
    } else {
      if (position.stopLoss && bar.high >= position.stopLoss) return 'STOP';
      if (position.target && bar.low <= position.target) return 'TARGET';
    }
    return null;
  }

  private closePosition(
    position: { direction: TradeDirection; entryPrice: number; entryBarIndex: number; quantity: number },
    reason: string,
    bar: OHLCVBar,
    barIndex: number,
    costModel: CostModel | undefined,
    bars: readonly OHLCVBar[],
  ): BacktestTrade {
    const exitPrice = this.getExitPrice(bar, position.direction, reason as any, costModel);
    const cost = this.costEngine.computeTradeCost({
      entryPrice: position.entryPrice, exitPrice, quantity: position.quantity,
      bars, entryBarIndex: position.entryBarIndex, exitBarIndex: barIndex,
      costModel: costModel ?? { commissionPerTrade: 0, commissionPerShare: 0, commissionPercent: 0, slippageTicks: 0, slippageBps: 0, marketImpactModel: 'NONE', marketImpactCoeff: 0, spreadBps: 0 },
    });
    const rawPnl = position.direction === 'LONG'
      ? (exitPrice - position.entryPrice) * position.quantity
      : (position.entryPrice - exitPrice) * position.quantity;
    const totalCost = cost.commissions + cost.entrySlippage + cost.exitSlippage + cost.marketImpact;
    const netPnl = rawPnl - totalCost;
    const pnlPercent = position.entryPrice * position.quantity !== 0 ? netPnl / (position.entryPrice * position.quantity) : 0;
    const riskReward = Math.abs(position.entryPrice - exitPrice) / Math.abs(position.entryPrice - (position.direction === 'LONG' ? position.entryPrice * 0.97 : position.entryPrice * 1.03));

    return {
      tradeId: `t_${Date.now()}_${barIndex}`,
      symbol: '',
      direction: position.direction,
      entryBarIndex: position.entryBarIndex,
      entryPrice: position.entryPrice,
      entryTimestamp: bars[position.entryBarIndex]?.timestamp ?? '',
      exitBarIndex: barIndex,
      exitPrice,
      exitTimestamp: bar.timestamp,
      exitReason: reason as any,
      quantity: position.quantity,
      notional: position.entryPrice * position.quantity,
      pnl: netPnl,
      pnlPercent,
      commissions: cost.commissions,
      slippage: cost.entrySlippage + cost.exitSlippage,
      holdingBars: barIndex - position.entryBarIndex,
      riskRewardActual: riskReward,
    };
  }

  private getEntryPrice(bar: OHLCVBar, direction: TradeDirection, costModel?: CostModel): number {
    if (!costModel) return bar.open;
    return this.costEngine.applySlippage(bar.open, direction === 'LONG' ? 'BUY' : 'SELL', costModel);
  }

  private getExitPrice(bar: OHLCVBar, direction: TradeDirection, reason: string, costModel?: CostModel): number {
    let price = bar.open;
    if (reason === 'STOP' || reason === 'END_OF_DATA') {
      price = direction === 'LONG' ? bar.low : bar.high;
    } else if (reason === 'TARGET') {
      price = direction === 'LONG' ? bar.high : bar.low;
    }
    if (!costModel) return price;
    return this.costEngine.applySlippage(price, direction === 'LONG' ? 'SELL' : 'BUY', costModel);
  }

  private positionValue(
    position: { direction: TradeDirection; entryPrice: number; quantity: number } | null,
    bar: OHLCVBar,
  ): number {
    if (!position) return 0;
    return position.direction === 'LONG'
      ? (bar.close - position.entryPrice) * position.quantity
      : (position.entryPrice - bar.close) * position.quantity;
  }

  private emptyResult(strategy: StrategyInstance, dataset: HistoricalDataset, capital: number): BacktestResult {
    return {
      strategy: { ...strategy },
      datasetId: dataset.id,
      symbol: dataset.symbol,
      timeframe: dataset.timeframe,
      periodStart: '',
      periodEnd: '',
      initialCapital: capital,
      finalEquity: capital,
      equity: Object.freeze([capital]),
      equityTimestamps: Object.freeze(['']),
      trades: Object.freeze([]),
      metrics: this.metricsEngine.compute({ equity: [capital], trades: [], initialCapital: capital }),
      totalBars: 0,
      costsApplied: { totalCommissions: 0, totalSlippage: 0, totalMarketImpact: 0, totalCosts: 0, costPerTrade: 0, costAsPercentOfVolume: 0 },
      timestamp: new Date().toISOString(),
    };
  }
}