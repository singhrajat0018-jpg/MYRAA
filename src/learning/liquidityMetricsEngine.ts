// ============================================================================
// MYRAA Phase 28 — Advanced Liquidity Metrics Engine
// ============================================================================

import type { LiquidityMetrics } from './contracts';
import type { OHLCVBar } from '../quant/contracts';

/**
 * Advanced Liquidity Metrics Engine
 * Goes beyond basic market impact to provide comprehensive liquidity analysis
 */
export class LiquidityMetricsEngine {
  private volumeHistory: Map<string, number[]> = new Map(); // symbol -> volume history
  private priceHistory: Map<string, number[]> = new Map(); // symbol -> price history
  private spreadHistory: Map<string, number[]> = new Map(); // symbol -> spread history
  private readonly HISTORY_LENGTH = 100; // keep last 100 observations

  /**
   * Calculate liquidity metrics for a symbol
   */
  calculateLiquidityMetrics(
    symbol: string,
    currentBar: OHLCVBar,
    volume24h: number,
    spreadBps: number,
    historicalVolume: number[] = [],
    historicalSpread: number[] = [],
    historicalVolatility: number[] = []
  ): LiquidityMetrics {
    // Update histories
    this.updateHistory(symbol, currentBar.close, volume24h, spreadBps);

    // Calculate volume percentile vs historical
    const volumePercentile = this.calculateVolumePercentile(symbol, volume24h);

    // Estimate market impact coefficient
    const marketImpactCoeff = this.estimateMarketImpactCoefficient(
      symbol, volume24h, spreadBps, historicalVolatility
    );

    // Determine liquidity regime
    const liquidityRegime = this.determineLiquidityRegime(
      volumePercentile, spreadBps, marketImpactCoeff
    );

    // Calculate estimated slippage for typical trade
    const estimatedSlippage = this.calculateEstimatedSlippage(
      volume24h, spreadBps, marketImpactCoeff, liquidityRegime
    );

    // Calculate fill probability
    const fillProbability = this.calculateFillProbability(
      volume24h, spreadBps, liquidityRegime
    );

    const metrics: LiquidityMetrics = {
      timestamp: currentBar.timestamp,
      symbol,
      spreadBps,
      volume24h,
      volumePercentile,
      marketImpactCoeff,
      liquidityRegime,
      estimatedSlippage,
      fillProbability,
    };

    return metrics;
  }

  /**
   * Update historical data for a symbol
   */
  private updateHistory(symbol: string, price: number, volume: number, spread: number): void {
    // Update price history
    let priceHist = this.priceHistory.get(symbol) || [];
    priceHist.push(price);
    if (priceHist.length > this.HISTORY_LENGTH) priceHist.shift();
    this.priceHistory.set(symbol, priceHist);

    // Update volume history
    let volumeHist = this.volumeHistory.get(symbol) || [];
    volumeHist.push(volume);
    if (volumeHist.length > this.HISTORY_LENGTH) volumeHist.shift();
    this.volumeHistory.set(symbol, volumeHist);

    // Update spread history
    let spreadHist = this.spreadHistory.get(symbol) || [];
    spreadHist.push(spread);
    if (spreadHist.length > this.HISTORY_LENGTH) spreadHist.shift();
    this.spreadHistory.set(symbol, spreadHist);
  }

  /**
   * Calculate volume percentile vs historical
   */
  private calculateVolumePercentile(symbol: string, currentVolume: number): number {
    const volumeHist = this.volumeHistory.get(symbol) || [];
    if (volumeHist.length === 0) return 50; // default to median if no history

    // Sort history and find percentile
    const sortedHist = [...volumeHist].sort((a, b) => a - b);
    let countBelow = 0;
    for (const vol of sortedHist) {
      if (vol < currentVolume) countBelow++;
      else break;
    }

    return (countBelow / sortedHist.length) * 100;
  }

  /**
   * Estimate market impact coefficient using advanced models
   */
  private estimateMarketImpactCoefficient(
    symbol: string,
    volume: number,
    spreadBps: number,
    historicalVolatility: number[]
  ): number {
    // In a real implementation, this would use models like:
    // - Almgren-Chriss model
    // - Kissell-Glantz model
    // - Weber-Puchta-Kley model
    // - Or machine learning approaches

    // Simplified version based on volume participation and volatility
    const avgVolume = this.calculateAverageVolume(symbol);
    const volumeParticipation = avgVolume > 0 ? volume / avgVolume : 0;

    // Volatility adjustment
    const avgVolatility = historicalVolatility.length > 0 ?
      historicalVolatility.reduce((sum, v) => sum + v, 0) / historicalVolatility.length :
      0.02; // default 2% daily volatility

    // Market impact increases with volume participation and volatility
    // Base impact from spread + impact from market participation
    const baseImpact = spreadBps * 0.5; // half spread as base
    const participationImpact = Math.pow(volumeParticipation, 0.6) * 10; // empirical factor
    const volatilityImpact = avgVolatility * 100; // convert to bps

    return baseImpact + participationImpact + volatilityImpact;
  }

  /**
   * Calculate average historical volume
   */
  private calculateAverageVolume(symbol: string): number {
    const volumeHist = this.volumeHistory.get(symbol) || [];
    if (volumeHist.length === 0) return 0;
    return volumeHist.reduce((sum, vol) => sum + vol, 0) / volumeHist.length;
  }

  /**
   * Determine liquidity regime based on multiple factors
   */
  private determineLiquidityRegime(
    volumePercentile: number,
    spreadBps: number,
    marketImpactCoeff: number
  ): 'NORMAL' | 'THIN' | 'STRESSED' {
    // Liquidity regime determination based on:
    // 1. Volume percentile (low volume = thin)
    // 2. Spread width (wide spread = stressed)
    // 3. Market impact coefficient (high impact = stressed)

    // Thin liquidity: very low volume
    if (volumePercentile < 20) {
      return 'THIN';
    }

    // Stressed liquidity: wide spreads or high impact
    if (spreadBps > 50 || marketImpactCoeff > 100) { // >50bps spread or >100bps impact
      return 'STRESSED';
    }

    // Normal liquidity: everything else
    return 'NORMAL';
  }

  /**
   * Calculate estimated slippage for typical trade
   */
  private calculateEstimatedSlippage(
    volume24h: number,
    spreadBps: number,
    marketImpactCoeff: number,
    liquidityRegime: 'NORMAL' | 'THIN' | 'STRESSED'
  ): number {
    // Base slippage from spread
    let slippage = spreadBps * 0.3; // 30% of spread as base slippage

    // Add market impact component
    // Typical trade size assumption: 1% of daily volume
    const typicalTradeSize = volume24h * 0.01;
    const avgVolume = this.calculateAverageVolume(''); // would be symbol-specific in reality
    const volumeParticipation = avgVolume > 0 ? typicalTradeSize / avgVolume : 0.001;

    // Market impact slippage (non-linear with participation)
    const impactSlippage = marketImpactCoeff * Math.pow(volumeParticipation, 0.6);

    // Regime adjustments
    let regimeMultiplier = 1.0;
    switch (liquidityRegime) {
      case 'THIN':
        regimeMultiplier = 2.0; // double slippage in thin markets
        break;
      case 'STRESSED':
        regimeMultiplier = 3.0; // triple slippage in stressed markets
        break;
      case 'NORMAL':
        regimeMultiplier = 1.0;
        break;
    }

    return (slippage + impactSlippage) * regimeMultiplier;
  }

  /**
   * Calculate probability of getting filled at desired price
   */
  private calculateFillProbability(
    volume24h: number,
    spreadBps: number,
    liquidityRegime: 'NORMAL' | 'THIN' | 'STRESSED'
  ): number {
    // Base fill probability
    let probability = 0.8; // start with 80% base probability

    // Adjust for volume (higher volume = higher fill probability)
    const volumeFactor = Math.min(1.0, volume24h / 1000000); // normalize to 1M volume
    probability *= 0.5 + volumeFactor * 0.5; // range 0.5 to 1.0

    // Adjust for spread (tighter spread = higher fill probability)
    const spreadFactor = Math.max(0.1, 1 - (spreadBps / 100)); // penalize wide spreads
    probability *= spreadFactor;

    // Adjust for liquidity regime
    let regimeFactor = 1.0;
    switch (liquidityRegime) {
      case 'THIN':
        regimeFactor = 0.6; // lower fill probability in thin markets
        break;
      case 'STRESSED':
        regimeFactor = 0.4; // much lower fill probability in stressed markets
        break;
      case 'NORMAL':
        regimeFactor = 1.0;
        break;
    }

    return Math.max(0.05, Math.min(0.95, probability * regimeFactor)); // clamp between 5% and 95%
  }

  /**
   * Calculate liquidity-adjusted position size
   */
  calculateLiquidityAdjustedPositionSize(
    basePositionSize: number,
    liquidityMetrics: LiquidityMetrics,
    maxSlippageTolerance: number = 10 // basis points
  ): number {
    // Reduce position size if expected slippage exceeds tolerance
    if (liquidityMetrics.estimatedSlippage <= maxSlippageTolerance) {
      return basePositionSize; // no adjustment needed
    }

    // Scale down position size to meet slippage tolerance
    // Assuming slippage scales roughly with square root of position size
    const sizeRatio = Math.max(0.1, Math.pow(maxSlippageTolerance / liquidityMetrics.estimatedSlippage, 2));
    return basePositionSize * sizeRatio;
  }

  /**
   * Get liquidity history for analysis
   */
  getLiquidityHistory(symbol: string): {
    prices: number[];
    volumes: number[];
    spreads: number[];
  } | null {
    const prices = this.priceHistory.get(symbol);
    const volumes = this.volumeHistory.get(symbol);
    const spreads = this.spreadHistory.get(symbol);

    if (!prices || !volumes || !spreads) return null;

    return {
      prices: [...prices],
      volumes: [...volumes],
      spreads: [...spreads],
    };
  }

  /**
   * Clear history for a symbol (useful for testing)
   */
  clearHistory(symbol: string): void {
    this.priceHistory.delete(symbol);
    this.volumeHistory.delete(symbol);
    this.spreadHistory.delete(symbol);
  }
}

// Export singleton instance
export const liquidityMetricsEngine = new LiquidityMetricsEngine();