// ============================================================================
// MYRAA Phase 27 — Cost, Slippage & Liquidity Model
// ============================================================================

import type { CostModel, CostSummary, OHLCVBar } from './contracts';

export class CostEngine {
  computeTradeCost(params: {
    entryPrice: number;
    exitPrice: number;
    quantity: number;
    bars: readonly OHLCVBar[];
    entryBarIndex: number;
    exitBarIndex: number;
    costModel: CostModel;
  }): { entrySlippage: number; exitSlippage: number; commissions: number; marketImpact: number } {
    const { entryPrice, exitPrice, quantity, bars, entryBarIndex, exitBarIndex, costModel } = params;
    const entrySlippage = this.computeSlippage(entryPrice, costModel);
    const exitSlippage = this.computeSlippage(exitPrice, costModel);
    const commissions = this.computeCommissions(entryPrice, exitPrice, quantity, costModel);
    const avgVolume = this.getAverageVolume(bars, entryBarIndex, 20);
    const marketImpact = this.computeMarketImpact(quantity, avgVolume, costModel);
    return { entrySlippage, exitSlippage, commissions, marketImpact };
  }

  computeSummary(trades: {
    entryPrice: number; exitPrice: number; quantity: number;
    bars: readonly OHLCVBar[]; entryBarIndex: number; exitBarIndex: number;
  }[], costModel: CostModel): CostSummary {
    let totalCommissions = 0;
    let totalSlippage = 0;
    let totalImpact = 0;
    let totalVolume = 0;
    for (const t of trades) {
      const cost = this.computeTradeCost({ ...t, costModel });
      totalCommissions += cost.commissions;
      totalSlippage += cost.entrySlippage + cost.exitSlippage;
      totalImpact += cost.marketImpact;
      totalVolume += t.entryPrice * t.quantity + t.exitPrice * t.quantity;
    }
    const totalCosts = totalCommissions + totalSlippage + totalImpact;
    return {
      totalCommissions,
      totalSlippage,
      totalMarketImpact: totalImpact,
      totalCosts,
      costPerTrade: trades.length > 0 ? totalCosts / trades.length : 0,
      costAsPercentOfVolume: totalVolume > 0 ? (totalCosts / totalVolume) * 100 : 0,
    };
  }

  applySlippage(price: number, side: 'BUY' | 'SELL', costModel: CostModel): number {
    const tickSize = price * 0.0001;
    const slippage = costModel.slippageTicks * tickSize + price * (costModel.slippageBps / 10000);
    return side === 'BUY' ? price + slippage : price - slippage;
  }

  private computeSlippage(price: number, model: CostModel): number {
    const tickSize = price * 0.0001;
    return model.slippageTicks * tickSize + price * (model.slippageBps / 10000);
  }

  private computeCommissions(entryPrice: number, exitPrice: number, quantity: number, model: CostModel): number {
    const entryCommission = model.commissionPerTrade
      + model.commissionPerShare * quantity
      + entryPrice * quantity * (model.commissionPercent);
    const exitCommission = model.commissionPerTrade
      + model.commissionPerShare * quantity
      + exitPrice * quantity * (model.commissionPercent);
    return entryCommission + exitCommission;
  }

  private computeMarketImpact(quantity: number, avgVolume: number, model: CostModel): number {
    if (model.marketImpactModel === 'NONE' || avgVolume <= 0) return 0;
    const participation = quantity / avgVolume;
    if (model.marketImpactModel === 'LINEAR') {
      return model.marketImpactCoeff * participation;
    }
    return model.marketImpactCoeff * Math.sqrt(participation);
  }

  private getAverageVolume(bars: readonly OHLCVBar[], fromIndex: number, lookback: number): number {
    const start = Math.max(0, fromIndex - lookback);
    let sum = 0;
    let count = 0;
    for (let i = start; i < fromIndex && i < bars.length; i++) {
      sum += bars[i].volume;
      count++;
    }
    return count > 0 ? sum / count : 0;
  }
}
