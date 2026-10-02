// ============================================================================
// MYRAA Phase 26 — Risk Engine
// Comprehensive risk assessment across volatility, liquidity, event, drawdown,
// correlation, data quality, and gap risk. Deterministic, no fabrication.
// ============================================================================

import type {
  MarketSnapshot,
  TechnicalAnalysis,
  FundamentalAnalysis,
  EventAnalysis,
  PortfolioContext,
  RiskAssessment,
  RiskLevel,
  DataQuality,
  Freshness,
} from './contracts';

import { RISK_SCORE_MAP } from './contracts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function hasData<T>(v: T | undefined | null): boolean {
  return v !== undefined && v !== null;
}

// ---------------------------------------------------------------------------
// RiskEngine
// ---------------------------------------------------------------------------

export class RiskEngine {
  private readonly source = 'RiskEngine';

  // -----------------------------------------------------------------------
  // 1. Main entry point — comprehensive risk assessment
  // -----------------------------------------------------------------------
  assess(params: {
    snapshot: MarketSnapshot;
    technical?: TechnicalAnalysis;
    fundamental?: FundamentalAnalysis;
    events?: EventAnalysis;
    portfolio?: PortfolioContext;
    symbol: string;
    assetId: string;
  }): RiskAssessment {
    const { snapshot, technical, fundamental, events, portfolio, symbol, assetId } = params;

    const volatilityRisk = this.assessVolatilityRisk(technical);
    const liquidityRisk = this.assessLiquidityRisk(snapshot);
    const eventRisk = this.assessEventRisk(events);
    const drawdownRisk = this.assessDrawdownRisk(technical);
    const correlationRisk = this.assessCorrelationRisk(portfolio, fundamental?.metrics?.marketCap !== undefined ? 'LARGE_CAP' : undefined);
    const dataRisk = this.assessDataRisk(
      this.computeDataQuality(technical, fundamental, events),
      snapshot.freshness,
    );
    const gapRisk = this.assessGapRisk(technical);

    const evidence: string[] = [];
    evidence.push(`Volatility: ${volatilityRisk}`);
    evidence.push(`Liquidity: ${liquidityRisk}`);
    evidence.push(`Event risk: ${eventRisk}`);
    evidence.push(`Drawdown: ${drawdownRisk}`);
    evidence.push(`Correlation: ${correlationRisk}`);
    evidence.push(`Data quality: ${dataRisk}`);
    evidence.push(`Gap risk: ${gapRisk}`);

    if (technical?.volatility) {
      evidence.push(`ATR(14): ${technical.volatility.atr14.toFixed(2)}`);
      evidence.push(`Volatility regime: ${technical.volatility.regime}`);
    }

    if (portfolio) {
      evidence.push(`Portfolio concentration: ${portfolio.concentrationRisk}`);
      const existingPosition = portfolio.positions.find(p => p.symbol === symbol);
      if (existingPosition) {
        evidence.push(`Existing position weight: ${(existingPosition.weight * 100).toFixed(1)}%`);
      }
    }

    if (events?.upcomingCatalysts) {
      const upcoming = events.upcomingCatalysts.filter(c => c.status === 'UPCOMING');
      if (upcoming.length > 0) {
        evidence.push(`${upcoming.length} upcoming catalyst(s)`);
      }
    }

    const overallRisk = this.computeOverallRisk(volatilityRisk, liquidityRisk, eventRisk, drawdownRisk, correlationRisk, dataRisk, gapRisk);
    const riskRewardRatio = technical ? this.computeRiskReward(technical, { overallRisk, volatilityRisk } as RiskAssessment) : undefined;
    const stopLossGuidance = technical ? this.suggestStopLoss(technical, { overallRisk, volatilityRisk } as RiskAssessment) : undefined;
    const positionSizingGuidance = this.suggestPositionSize({ overallRisk, volatilityRisk, correlationRisk } as RiskAssessment, portfolio);

    return {
      assetId,
      symbol,
      timestamp: new Date().toISOString(),
      overallRisk,
      volatilityRisk,
      liquidityRisk,
      eventRisk,
      drawdownRisk,
      correlationRisk,
      dataRisk,
      gapRisk,
      evidence,
      maxDrawdownScenario: this.estimateMaxDrawdown(technical, volatilityRisk),
      stopLossGuidance,
      positionSizingGuidance,
      riskRewardRatio,
    };
  }

  // -----------------------------------------------------------------------
  // 2. Assess volatility risk
  // -----------------------------------------------------------------------
  assessVolatilityRisk(technical?: TechnicalAnalysis): RiskLevel {
    if (!technical) return 'UNKNOWN';

    const vol = technical.volatility;
    if (!vol) return 'UNKNOWN';

    const atr = vol.atr14;
    const price = technical.indicators.sma20?.value ?? 0;
    const atrPercent = price > 0 ? atr / price : 0;

    if (vol.regime === 'HIGH' || atrPercent > 0.05) return 'EXTREME';
    if (vol.regime === 'NORMAL' && atrPercent > 0.03) return 'HIGH';
    if (vol.regime === 'NORMAL' && atrPercent > 0.015) return 'MEDIUM';
    if (vol.regime === 'LOW' && atrPercent <= 0.015) return 'LOW';
    return 'MEDIUM';
  }

  // -----------------------------------------------------------------------
  // 3. Assess liquidity risk
  // -----------------------------------------------------------------------
  assessLiquidityRisk(snapshot: MarketSnapshot): RiskLevel {
    const volume = snapshot.volume;
    const marketCap = snapshot.marketCap;

    if (marketCap !== undefined) {
      if (marketCap < 10_000_000) return 'EXTREME';    // Micro-cap
      if (marketCap < 300_000_000) return 'HIGH';       // Small-cap
      if (marketCap < 2_000_000_000) return 'MEDIUM';   // Mid-cap
    }

    if (volume < 10_000) return 'EXTREME';
    if (volume < 100_000) return 'HIGH';
    if (volume < 1_000_000) return 'MEDIUM';
    return 'LOW';
  }

  // -----------------------------------------------------------------------
  // 4. Assess event risk
  // -----------------------------------------------------------------------
  assessEventRisk(events?: EventAnalysis): RiskLevel {
    if (!events) return 'UNKNOWN';

    const upcomingCatalysts = events.upcomingCatalysts.filter(c => c.status === 'UPCOMING');
    const highImpact = upcomingCatalysts.filter(c => c.importance === 'HIGH');

    if (highImpact.length >= 2) return 'EXTREME';
    if (highImpact.length === 1) return 'HIGH';
    if (upcomingCatalysts.length >= 2) return 'MEDIUM';
    if (upcomingCatalysts.length === 1) return 'MEDIUM';
    if (events.contradictionDetected) return 'MEDIUM';
    return 'LOW';
  }

  // -----------------------------------------------------------------------
  // 5. Assess drawdown risk
  // -----------------------------------------------------------------------
  assessDrawdownRisk(technical?: TechnicalAnalysis): RiskLevel {
    if (!technical) return 'UNKNOWN';

    const trend = technical.trend;
    const price = technical.indicators.sma20?.value ?? 0;

    // Estimate drawdown from 52-week high/low context
    const sr = technical.supportResistance;
    const supports = sr.filter(l => l.type === 'SUPPORT');
    const resistances = sr.filter(l => l.type === 'RESISTANCE');

    if (trend.direction === 'DOWNTREND') {
      if (trend.strength > 70) return 'HIGH';
      if (trend.strength > 40) return 'MEDIUM';
      return 'MEDIUM';
    }

    if (supports.length > 0 && price > 0) {
      const nearestSupport = supports.sort((a, b) => b.price - a.price)[0];
      const distanceToSupport = (price - nearestSupport.price) / price;
      if (distanceToSupport < 0.02) return 'HIGH';
      if (distanceToSupport < 0.05) return 'MEDIUM';
    }

    if (trend.direction === 'RANGE') return 'LOW';
    if (trend.direction === 'UPTREND' && trend.strength > 50) return 'LOW';
    return 'MEDIUM';
  }

  // -----------------------------------------------------------------------
  // 6. Assess correlation risk
  // -----------------------------------------------------------------------
  assessCorrelationRisk(portfolio?: PortfolioContext, sector?: string): RiskLevel {
    if (!portfolio) return 'UNKNOWN';

    if (portfolio.concentrationRisk === 'EXTREME') return 'EXTREME';
    if (portfolio.concentrationRisk === 'HIGH') return 'HIGH';

    if (sector) {
      const sectorAllocation = portfolio.sectorAllocation.find(s => s.sector === sector);
      if (sectorAllocation && sectorAllocation.weight > 0.4) return 'HIGH';
      if (sectorAllocation && sectorAllocation.weight > 0.25) return 'MEDIUM';
    }

    // Check for same-symbol exposure
    const symbols = portfolio.positions.map(p => p.symbol);
    const uniqueSymbols = new Set(symbols);
    if (symbols.length > 5 && uniqueSymbols.size < symbols.length * 0.7) return 'MEDIUM';

    // High overall allocation to few positions
    const topWeights = portfolio.positions
      .map(p => p.weight)
      .sort((a, b) => b - a)
      .slice(0, 5);
    const topConcentration = topWeights.reduce((s, w) => s + w, 0);
    if (topConcentration > 0.7) return 'HIGH';
    if (topConcentration > 0.5) return 'MEDIUM';

    return 'LOW';
  }

  // -----------------------------------------------------------------------
  // 7. Assess data risk
  // -----------------------------------------------------------------------
  assessDataRisk(dataQuality: DataQuality, freshness: Freshness): RiskLevel {
    const qualityRisk: Record<DataQuality, RiskLevel> = {
      COMPLETE: 'LOW',
      PARTIAL: 'MEDIUM',
      SPARSE: 'HIGH',
      UNKNOWN: 'HIGH',
    };

    const freshnessRisk: Record<Freshness, RiskLevel> = {
      REALTIME: 'LOW',
      NEAR_REALTIME: 'LOW',
      DELAYED: 'MEDIUM',
      END_OF_DAY: 'MEDIUM',
      HISTORICAL: 'LOW',
      STALE: 'EXTREME',
      UNAVAILABLE: 'EXTREME',
    };

    const qRisk = RISK_SCORE_MAP[qualityRisk[dataQuality] ?? 'UNKNOWN'];
    const fRisk = RISK_SCORE_MAP[freshnessRisk[freshness] ?? 'UNKNOWN'];
    const combined = (qRisk + fRisk) / 2;

    if (combined >= 0.85) return 'EXTREME';
    if (combined >= 0.6) return 'HIGH';
    if (combined >= 0.35) return 'MEDIUM';
    return 'LOW';
  }

  // -----------------------------------------------------------------------
  // 8. Assess gap risk
  // -----------------------------------------------------------------------
  assessGapRisk(technical?: TechnicalAnalysis): RiskLevel {
    if (!technical) return 'UNKNOWN';

    const vol = technical.volatility;
    if (!vol) return 'UNKNOWN';

    if (vol.regime === 'HIGH') {
      // High volatility increases gap probability
      if (vol.percentileRank > 90) return 'EXTREME';
      return 'HIGH';
    }

    if (vol.regime === 'NORMAL' && vol.percentileRank > 70) return 'MEDIUM';
    if (vol.regime === 'LOW') return 'LOW';
    return 'MEDIUM';
  }

  // -----------------------------------------------------------------------
  // 9. Compute risk/reward ratio
  // -----------------------------------------------------------------------
  computeRiskReward(technical: TechnicalAnalysis, risk: RiskAssessment): number {
    const sr = technical.supportResistance;
    const price = technical.indicators.sma20?.value ?? 0;
    if (price <= 0) return 0;

    const supports = sr.filter(l => l.type === 'SUPPORT').sort((a, b) => b.price - a.price);
    const resistances = sr.filter(l => l.type === 'RESISTANCE').sort((a, b) => a.price - b.price);

    const riskScore = RISK_SCORE_MAP[risk.overallRisk] ?? 0.5;

    // Estimate downside from nearest support
    const nearestSupport = supports.length > 0 ? supports[0].price : price * (1 - riskScore * 0.1);
    const downside = Math.abs(price - nearestSupport);

    // Estimate upside from nearest resistance
    const nearestResistance = resistances.length > 0 ? resistances[0].price : price * (1 + riskScore * 0.15);
    const upside = Math.abs(nearestResistance - price);

    if (downside === 0) return 0;
    return clamp(upside / downside, 0, 10);
  }

  // -----------------------------------------------------------------------
  // 10. Suggest stop loss (ATR-based)
  // -----------------------------------------------------------------------
  suggestStopLoss(technical: TechnicalAnalysis, risk: RiskAssessment): number {
    const price = technical.indicators.sma20?.value ?? 0;
    if (price <= 0) return 0;

    const atr = technical.volatility?.atr14 ?? 0;
    const riskScore = RISK_SCORE_MAP[risk.overallRisk] ?? 0.5;

    // ATR multiplier based on risk level
    const multiplier = riskScore > 0.7 ? 3 : riskScore > 0.5 ? 2.5 : 2;
    const stopDistance = atr * multiplier;

    return Math.max(0, price - stopDistance);
  }

  // -----------------------------------------------------------------------
  // 11. Suggest position sizing
  // -----------------------------------------------------------------------
  suggestPositionSize(risk: RiskAssessment, portfolio?: PortfolioContext): string {
    const riskScore = RISK_SCORE_MAP[risk.overallRisk] ?? 0.5;
    const volScore = RISK_SCORE_MAP[risk.volatilityRisk] ?? 0.5;

    // Base position size on combined risk
    const combinedRisk = (riskScore + volScore) / 2;

    if (combinedRisk > 0.8) return 'Conservative: 1-2% of portfolio';
    if (combinedRisk > 0.6) return 'Moderate: 2-3% of portfolio';
    if (combinedRisk > 0.4) return 'Standard: 3-5% of portfolio';
    if (combinedRisk > 0.2) return 'Aggressive: 5-7% of portfolio';
    return 'Full conviction: 7-10% of portfolio';
  }

  // -----------------------------------------------------------------------
  // Private helpers
  // -----------------------------------------------------------------------
  private computeDataQuality(
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    events?: EventAnalysis,
  ): DataQuality {
    const sources = [
      hasData(technical),
      hasData(fundamental),
      hasData(events),
    ].filter(Boolean).length;

    if (sources === 3) return 'COMPLETE';
    if (sources === 2) return 'PARTIAL';
    if (sources === 1) return 'SPARSE';
    return 'UNKNOWN';
  }

  private computeOverallRisk(
    volatility: RiskLevel,
    liquidity: RiskLevel,
    event: RiskLevel,
    drawdown: RiskLevel,
    correlation: RiskLevel,
    data: RiskLevel,
    gap: RiskLevel,
  ): RiskLevel {
    const allScores = [
      RISK_SCORE_MAP[volatility],
      RISK_SCORE_MAP[liquidity],
      RISK_SCORE_MAP[event],
      RISK_SCORE_MAP[drawdown],
      RISK_SCORE_MAP[correlation],
      RISK_SCORE_MAP[data],
      RISK_SCORE_MAP[gap],
    ];
    const knownCount = allScores.filter(s => s !== RISK_SCORE_MAP.UNKNOWN).length;
    const scores = allScores.filter(s => s !== RISK_SCORE_MAP.UNKNOWN || knownCount < 4);

    if (scores.length === 0) return 'UNKNOWN';

    const avg = scores.reduce((s, v) => s + v, 0) / scores.length;
    const max = Math.max(...scores);

    // Weighted: 60% average + 40% worst case
    const combined = avg * 0.6 + max * 0.4;

    if (combined >= 0.8) return 'EXTREME';
    if (combined >= 0.6) return 'HIGH';
    if (combined >= 0.35) return 'MEDIUM';
    return 'LOW';
  }

  private estimateMaxDrawdown(technical?: TechnicalAnalysis, volatilityRisk?: RiskLevel): number | undefined {
    if (!technical) return undefined;

    const atr = technical.volatility?.atr14 ?? 0;
    const price = technical.indicators.sma20?.value ?? 0;
    if (price <= 0 || atr <= 0) return undefined;

    const volMultiplier = volatilityRisk === 'EXTREME' ? 4
      : volatilityRisk === 'HIGH' ? 3
      : volatilityRisk === 'MEDIUM' ? 2
      : 1.5;

    return -(atr * volMultiplier) / price;
  }
}
