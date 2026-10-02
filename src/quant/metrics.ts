// ============================================================================
// MYRAA Phase 27 — Performance Metrics Engine
// ============================================================================

import type { PerformanceMetrics, BacktestTrade } from './contracts';
import { HistoricalIntegrityEngine } from '../finance/historical';
import type { OHLCVBar } from '../finance/contracts';

export class MetricsEngine {
  private readonly historicalEngine = new HistoricalIntegrityEngine();

  compute(params: {
    equity: number[];
    trades: BacktestTrade[];
    initialCapital: number;
    benchmarkReturns?: number[];
    riskFreeRate?: number;
    tradingDaysPerYear?: number;
  }): PerformanceMetrics {
    const { equity, trades, initialCapital, benchmarkReturns, riskFreeRate = 0.0, tradingDaysPerYear = 252 } = params;
    const returns = this.equityToReturns(equity);
    const totalReturn = equity.length > 0 ? (equity[equity.length - 1] - initialCapital) / initialCapital : 0;
    const n = equity.length;
    const years = n / tradingDaysPerYear;
    const annualizedReturn = years > 0 ? Math.pow(1 + totalReturn, 1 / years) - 1 : 0;
    const sharpe = this.historicalEngine.computeSharpe(returns, riskFreeRate);
    const sortino = this.historicalEngine.computeSortino(returns, riskFreeRate);
    const maxDD = this.historicalEngine.computeMaxDrawdown(equity);
    const maxDDDuration = this.computeMaxDrawdownDuration(equity);
    const calmar = maxDD !== 0 ? annualizedReturn / Math.abs(maxDD) : 0;
    const volatility = this.computeVolatility(returns) * Math.sqrt(tradingDaysPerYear);
    const downsideVol = this.computeDownsideVolatility(returns, riskFreeRate / tradingDaysPerYear) * Math.sqrt(tradingDaysPerYear);
    const wins = trades.filter(t => t.pnl > 0);
    const losses = trades.filter(t => t.pnl < 0);
    const winRate = trades.length > 0 ? wins.length / trades.length : 0;
    const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnlPercent, 0) / wins.length : 0;
    const avgLoss = losses.length > 0 ? losses.reduce((s, t) => s + t.pnlPercent, 0) / losses.length : 0;
    const grossWins = wins.reduce((s, t) => s + t.pnl, 0);
    const grossLosses = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
    const profitFactor = grossLosses > 0 ? grossWins / grossLosses : grossWins > 0 ? Infinity : 0;
    const expectancy = trades.length > 0 ? trades.reduce((s, t) => s + t.pnl, 0) / trades.length : 0;
    const longTrades = trades.filter(t => t.direction === 'LONG');
    const shortTrades = trades.filter(t => t.direction === 'SHORT');
    const longWinRate = longTrades.length > 0 ? longTrades.filter(t => t.pnl > 0).length / longTrades.length : 0;
    const shortWinRate = shortTrades.length > 0 ? shortTrades.filter(t => t.pnl > 0).length / shortTrades.length : 0;
    const avgHolding = trades.length > 0 ? trades.reduce((s, t) => s + t.holdingBars, 0) / trades.length : 0;
    const bestTrade = trades.length > 0 ? Math.max(...trades.map(t => t.pnlPercent)) : 0;
    const worstTrade = trades.length > 0 ? Math.min(...trades.map(t => t.pnlPercent)) : 0;
    const avgTrade = trades.length > 0 ? trades.reduce((s, t) => s + t.pnlPercent, 0) / trades.length : 0;
    const { consecutiveWins, consecutiveLosses } = this.computeConsecutive(trades);
    const skewness = this.computeSkewness(returns);
    const kurtosis = this.computeKurtosis(returns);
    const tailRatio = this.computeTailRatio(returns);
    const commonReturn = this.computeCommonReturn(returns);
    let benchmarkReturn: number | undefined;
    let alpha: number | undefined;
    let beta: number | undefined;
    let informationRatio: number | undefined;
    if (benchmarkReturns && benchmarkReturns.length > 0) {
      const bTotalReturn = benchmarkReturns.reduce((s, r) => s + r, 0);
      benchmarkReturn = bTotalReturn;
      beta = this.computeBeta(returns, benchmarkReturns);
      alpha = annualizedReturn - (riskFreeRate + (beta ?? 1) * (bTotalReturn / (years || 1) - riskFreeRate));
      informationRatio = this.computeInformationRatio(returns, benchmarkReturns, tradingDaysPerYear);
    }
    return {
      totalReturn, annualizedReturn, sharpeRatio: sharpe, sortinoRatio: sortino,
      calmarRatio: calmar, maxDrawdown: maxDD, maxDrawdownDuration: maxDDDuration,
      volatility, downsideVolatility: downsideVol, winRate, avgWin, avgLoss,
      profitFactor, expectancy, totalTrades: trades.length, avgHoldingBars: avgHolding,
      bestTrade, worstTrade, avgTrade, consecutiveWins, consecutiveLosses,
      longTrades: longTrades.length, shortTrades: shortTrades.length,
      longWinRate, shortWinRate, skewness, kurtosis, tailRatio, commonReturn,
      benchmarkReturn, alpha, beta, informationRatio,
    };
  }

  private equityToReturns(equity: number[]): number[] {
    const returns: number[] = [];
    for (let i = 1; i < equity.length; i++) {
      returns.push(equity[i - 1] !== 0 ? (equity[i] - equity[i - 1]) / equity[i - 1] : 0);
    }
    return returns;
  }

  private computeVolatility(returns: number[]): number {
    if (returns.length < 2) return 0;
    const mean = returns.reduce((s, r) => s + r, 0) / returns.length;
    const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1);
    return Math.sqrt(variance);
  }

  private computeDownsideVolatility(returns: number[], threshold: number): number {
    const downside = returns.filter(r => r < threshold).map(r => r - threshold);
    if (downside.length < 2) return 0;
    const variance = downside.reduce((s, r) => s + r ** 2, 0) / (downside.length - 1);
    return Math.sqrt(variance);
  }

  private computeMaxDrawdownDuration(equity: number[]): number {
    if (equity.length < 2) return 0;
    let peak = equity[0];
    let maxDuration = 0;
    let currentDuration = 0;
    for (let i = 1; i < equity.length; i++) {
      if (equity[i] >= peak) { peak = equity[i]; currentDuration = 0; }
      else { currentDuration++; maxDuration = Math.max(maxDuration, currentDuration); }
    }
    return maxDuration;
  }

  private computeConsecutive(trades: BacktestTrade[]): { consecutiveWins: number; consecutiveLosses: number } {
    let maxWins = 0, maxLosses = 0, curWins = 0, curLosses = 0;
    for (const t of trades) {
      if (t.pnl > 0) { curWins++; curLosses = 0; maxWins = Math.max(maxWins, curWins); }
      else { curLosses++; curWins = 0; maxLosses = Math.max(maxLosses, curLosses); }
    }
    return { consecutiveWins: maxWins, consecutiveLosses: maxLosses };
  }

  private computeSkewness(returns: number[]): number {
    if (returns.length < 3) return 0;
    const n = returns.length;
    const mean = returns.reduce((s, r) => s + r, 0) / n;
    const std = Math.sqrt(returns.reduce((s, r) => s + (r - mean) ** 2, 0) / n);
    if (std === 0) return 0;
    const m3 = returns.reduce((s, r) => s + ((r - mean) / std) ** 3, 0) / n;
    return m3;
  }

  private computeKurtosis(returns: number[]): number {
    if (returns.length < 4) return 0;
    const n = returns.length;
    const mean = returns.reduce((s, r) => s + r, 0) / n;
    const std = Math.sqrt(returns.reduce((s, r) => s + (r - mean) ** 2, 0) / n);
    if (std === 0) return 0;
    const m4 = returns.reduce((s, r) => s + ((r - mean) / std) ** 4, 0) / n;
    return m4 - 3;
  }

  private computeTailRatio(returns: number[]): number {
    if (returns.length < 20) return 0;
    const sorted = [...returns].sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)];
    const p5 = Math.abs(sorted[Math.floor(sorted.length * 0.05)]);
    return p5 !== 0 ? p95 / p5 : 0;
  }

  private computeCommonReturn(returns: number[]): number {
    if (returns.length === 0) return 0;
    const positiveReturns = returns.filter(r => r > 0);
    return positiveReturns.length / returns.length;
  }

  private computeBeta(returns: number[], benchmarkReturns: number[]): number {
    const n = Math.min(returns.length, benchmarkReturns.length);
    if (n < 2) return 1;
    const r = returns.slice(0, n);
    const b = benchmarkReturns.slice(0, n);
    const meanR = r.reduce((s, v) => s + v, 0) / n;
    const meanB = b.reduce((s, v) => s + v, 0) / n;
    let cov = 0, varB = 0;
    for (let i = 0; i < n; i++) {
      cov += (r[i] - meanR) * (b[i] - meanB);
      varB += (b[i] - meanB) ** 2;
    }
    return varB !== 0 ? cov / varB : 1;
  }

  private computeInformationRatio(returns: number[], benchmarkReturns: number[], daysPerYear: number): number {
    const n = Math.min(returns.length, benchmarkReturns.length);
    if (n < 2) return 0;
    const active = returns.slice(0, n).map((r, i) => r - benchmarkReturns[i]);
    const meanActive = active.reduce((s, v) => s + v, 0) / n;
    const trackingError = Math.sqrt(active.reduce((s, v) => s + (v - meanActive) ** 2, 0) / (n - 1)) * Math.sqrt(daysPerYear);
    return trackingError !== 0 ? (meanActive * daysPerYear) / trackingError : 0;
  }
}
