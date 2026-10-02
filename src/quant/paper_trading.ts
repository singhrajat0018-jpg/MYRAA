// ============================================================================
// MYRAA Phase 27 — Paper Trading Simulation Engine
// ============================================================================
// Virtual paper trading — never touches real money or broker APIs
// ============================================================================

import type {
  PaperPosition, PaperPortfolioSnapshot, PaperPositionStatus,
  CostModel, TradeDirection,
} from './contracts';
import { CostEngine } from './costs';

export class PaperTradingEngine {
  private readonly costEngine = new CostEngine();
  private positions: PaperPosition[] = [];
  private closedPositions: PaperPosition[] = [];
  private nextId = 1;

  constructor(
    private readonly initialCash: number = 100_000,
    private readonly costModel: CostModel = {
      commissionPerTrade: 0, commissionPerShare: 0, commissionPercent: 0.001,
      slippageTicks: 1, slippageBps: 5, marketImpactModel: 'NONE',
      marketImpactCoeff: 0, spreadBps: 3,
    },
  ) {}

  openPosition(params: {
    symbol: string;
    direction: TradeDirection;
    entryPrice: number;
    quantity: number;
    stopLoss?: number;
    takeProfit?: number;
  }): PaperPosition {
    const entrySlippage = this.costEngine.applySlippage(
      params.entryPrice, params.direction === 'LONG' ? 'BUY' : 'SELL', this.costModel,
    );
    const commissions = this.costModel.commissionPerTrade + this.costModel.commissionPerShare * params.quantity
      + entrySlippage * params.quantity * this.costModel.commissionPercent;
    const position: PaperPosition = {
      positionId: `paper_${this.nextId++}`,
      symbol: params.symbol,
      direction: params.direction,
      entryPrice: entrySlippage,
      entryTimestamp: new Date().toISOString(),
      quantity: params.quantity,
      stopLoss: params.stopLoss,
      takeProfit: params.takeProfit,
      status: 'OPEN',
      commissions,
      slippage: Math.abs(entrySlippage - params.entryPrice) * params.quantity,
    };
    this.positions.push(position);
    return position;
  }

  closePosition(params: {
    positionId: string;
    exitPrice: number;
    reason?: string;
  }): PaperPosition | null {
    const idx = this.positions.findIndex(p => p.positionId === params.positionId);
    if (idx < 0) return null;
    const pos = this.positions[idx];
    const exitSlippage = this.costEngine.applySlippage(
      params.exitPrice, pos.direction === 'LONG' ? 'SELL' : 'BUY', this.costModel,
    );
    const commissions = this.costModel.commissionPerTrade + this.costModel.commissionPerShare * pos.quantity
      + exitSlippage * pos.quantity * this.costModel.commissionPercent;
    const pnl = pos.direction === 'LONG'
      ? (exitSlippage - pos.entryPrice) * pos.quantity
      : (pos.entryPrice - exitSlippage) * pos.quantity;
    const totalCommissions = pos.commissions + commissions;
    const pnlPercent = (pos.entryPrice * pos.quantity) !== 0
      ? (pnl - totalCommissions) / (pos.entryPrice * pos.quantity)
      : 0;
    const closed: PaperPosition = {
      ...pos,
      status: 'CLOSED' as PaperPositionStatus,
      exitPrice: exitSlippage,
      exitTimestamp: new Date().toISOString(),
      exitReason: params.reason ?? 'SIGNAL',
      pnl: pnl - totalCommissions,
      pnlPercent,
      commissions: totalCommissions,
      slippage: pos.slippage + Math.abs(exitSlippage - params.exitPrice) * pos.quantity,
    };
    this.positions.splice(idx, 1);
    this.closedPositions.push(closed);
    return closed;
  }

  checkStopsAndTargets(params: {
    bar: { high: number; low: number; open: number };
    check?: (position: PaperPosition, bar: { high: number; low: number; open: number }) => string | null;
  }): PaperPosition[] {
    const closed: PaperPosition[] = [];
    const toClose: string[] = [];
    for (const pos of this.positions) {
      let reason: string | null = null;
      if (pos.stopLoss) {
        if (pos.direction === 'LONG' && params.bar.low <= pos.stopLoss) reason = 'STOP';
        if (pos.direction === 'SHORT' && params.bar.high >= pos.stopLoss) reason = 'STOP';
      }
      if (pos.takeProfit && !reason) {
        if (pos.direction === 'LONG' && params.bar.high >= pos.takeProfit) reason = 'TARGET';
        if (pos.direction === 'SHORT' && params.bar.low <= pos.takeProfit) reason = 'TARGET';
      }
      if (!reason && params.check) reason = params.check(pos, params.bar);
      if (reason) toClose.push(pos.positionId);
    }
    const reasons = new Map<string, string>();
    for (const pos of this.positions) {
      let reason: string | null = null;
      if (pos.stopLoss) {
        if (pos.direction === 'LONG' && params.bar.low <= pos.stopLoss) reason = 'STOP';
        if (pos.direction === 'SHORT' && params.bar.high >= pos.stopLoss) reason = 'STOP';
      }
      if (pos.takeProfit && !reason) {
        if (pos.direction === 'LONG' && params.bar.high >= pos.takeProfit) reason = 'TARGET';
        if (pos.direction === 'SHORT' && params.bar.low <= pos.takeProfit) reason = 'TARGET';
      }
      if (!reason && params.check) reason = params.check(pos, params.bar);
      if (reason) {
        toClose.push(pos.positionId);
        reasons.set(pos.positionId, reason);
      }
    }
    for (const id of toClose) {
      const pos = this.positions.find(p => p.positionId === id);
      if (pos) {
        const exitPrice = pos.direction === 'LONG'
          ? (pos.stopLoss && params.bar.low <= pos.stopLoss ? pos.stopLoss : pos.takeProfit ?? params.bar.open)
          : (pos.stopLoss && params.bar.high >= pos.stopLoss ? pos.stopLoss : pos.takeProfit ?? params.bar.open);
        const result = this.closePosition({ positionId: id, exitPrice, reason: reasons.get(id) ?? 'SIGNAL' });
        if (result) closed.push(result);
      }
    }
    return closed;
  }

  getSnapshot(): PaperPortfolioSnapshot {
    const totalPnl = this.closedPositions.reduce((s, p) => s + (p.pnl ?? 0), 0);
    return {
      cash: this.initialCash + totalPnl,
      positions: Object.freeze([...this.positions]),
      totalEquity: this.initialCash + totalPnl,
      totalPnl,
      totalPnlPercent: this.initialCash > 0 ? totalPnl / this.initialCash : 0,
      openPositionCount: this.positions.length,
      timestamp: new Date().toISOString(),
    };
  }

  getStats(): {
    totalTrades: number; winningTrades: number; losingTrades: number;
    winRate: number; avgWin: number; avgLoss: number; profitFactor: number;
    expectancy: number; maxWin: number; maxLoss: number; totalPnl: number;
  } {
    const closed = this.closedPositions;
    const wins = closed.filter(p => (p.pnl ?? 0) > 0);
    const losses = closed.filter(p => (p.pnl ?? 0) < 0);
    const grossWin = wins.reduce((s, p) => s + (p.pnl ?? 0), 0);
    const grossLoss = Math.abs(losses.reduce((s, p) => s + (p.pnl ?? 0), 0));
    return {
      totalTrades: closed.length,
      winningTrades: wins.length,
      losingTrades: losses.length,
      winRate: closed.length > 0 ? wins.length / closed.length : 0,
      avgWin: wins.length > 0 ? grossWin / wins.length : 0,
      avgLoss: losses.length > 0 ? -grossLoss / losses.length : 0,
      profitFactor: grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0,
      expectancy: closed.length > 0 ? closed.reduce((s, p) => s + (p.pnl ?? 0), 0) / closed.length : 0,
      maxWin: wins.length > 0 ? Math.max(...wins.map(p => p.pnl ?? 0)) : 0,
      maxLoss: losses.length > 0 ? Math.min(...losses.map(p => p.pnl ?? 0)) : 0,
      totalPnl: closed.reduce((s, p) => s + (p.pnl ?? 0), 0),
    };
  }

  reset(): void {
    this.positions = [];
    this.closedPositions = [];
    this.nextId = 1;
  }
}
