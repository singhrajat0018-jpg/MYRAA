// ============================================================================
// MYRAA Phase 26 — Scenario Engine
// Generates bull/base/bear/stress scenarios with sensitivity analysis.
// Deterministic, no fabrication. All targets derived from input data.
// ============================================================================

import type {
  TradingThesis,
  TechnicalAnalysis,
  FundamentalAnalysis,
  RiskAssessment,
  ScenarioAnalysis,
  Scenario,
  ScenarioVariable,
  ScenarioType,
  TimeHorizon,
} from './contracts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function hasData<T>(v: T | undefined | null): boolean {
  return v !== undefined && v !== null;
}

let scenarioCounter = 0;
const nextId = () => `scn-${Date.now()}-${++scenarioCounter}`;

// ---------------------------------------------------------------------------
// ScenarioEngine
// ---------------------------------------------------------------------------

export class ScenarioEngine {
  private readonly source = 'ScenarioEngine';

  // -----------------------------------------------------------------------
  // 1. Main entry point
  // -----------------------------------------------------------------------
  generate(params: {
    thesis: TradingThesis;
    technical?: TechnicalAnalysis;
    fundamental?: FundamentalAnalysis;
    currentPrice: number;
    symbol: string;
    assetId: string;
    timeframe: TimeHorizon;
  }): ScenarioAnalysis {
    const { thesis, technical, fundamental, currentPrice, symbol, assetId, timeframe } = params;

    const risk = thesis.riskAssessment;
    const variables = this.defineVariables(technical, fundamental);
    const bull = this.buildBullScenario(thesis, technical, fundamental, currentPrice);
    const base = this.buildBaseScenario(thesis, technical, fundamental, currentPrice);
    const bear = this.buildBearScenario(thesis, technical, fundamental, currentPrice);
    const stress = this.buildStressScenario(thesis, technical, risk);

    const scenarios: Scenario[] = [bull, base, bear, stress];
    const sensitivityAnalysis = this.computeSensitivity(variables, 'UP')
      .concat(this.computeSensitivity(variables, 'DOWN'));

    return {
      assetId,
      symbol,
      timestamp: new Date().toISOString(),
      scenarios,
      variables,
      sensitivityAnalysis,
      timeframe,
    };
  }

  // -----------------------------------------------------------------------
  // 2. Bull scenario
  // -----------------------------------------------------------------------
  buildBullScenario(
    thesis: TradingThesis,
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    currentPrice?: number,
  ): Scenario {
    const assumptions: string[] = [];
    const risks: string[] = [];
    const implications: string[] = [];

    if (thesis.bullCase) assumptions.push(thesis.bullCase);
    if (thesis.keyCatalysts.length > 0) {
      assumptions.push(`Key catalysts materialize: ${thesis.keyCatalysts.slice(0, 3).join(', ')}`);
    }

    if (technical) {
      const resistance = technical.supportResistance
        .filter(l => l.type === 'RESISTANCE')
        .sort((a, b) => a.price - b.price);
      if (resistance.length > 0) {
        assumptions.push(`Price breaks above resistance at ${resistance[0].price.toFixed(2)}`);
        implications.push(`Next resistance target: ${resistance[resistance.length - 1]?.price.toFixed(2) ?? 'N/A'}`);
      }
      if (technical.trend.direction === 'UPTREND') {
        assumptions.push(`Trend continues with strength ${technical.trend.strength}%`);
      }
    }

    if (fundamental) {
      if (fundamental.valuationAssessment === 'UNDERVALUED') {
        assumptions.push('Valuation re-rates toward fair value');
      }
      if (fundamental.growthAssessment === 'HIGH_GROWTH') {
        assumptions.push('Growth acceleration continues');
      }
    }

    risks.push('Thesis may not fully play out');
    risks.push('Market conditions may deteriorate');
    if (technical?.volatility?.regime === 'HIGH') {
      risks.push('High volatility may cause false breakouts');
    }

    const priceTarget = currentPrice
      ? this.estimatePriceTarget('BULL', currentPrice, technical, fundamental)
      : undefined;

    return {
      type: 'BULL',
      description: `Bull case for ${thesis.symbol}: ${thesis.bullCase || 'upside scenario'}`,
      assumptions,
      expectedImplications: implications.length > 0 ? implications : ['Strong upside potential'],
      risks,
      confidence: clamp(thesis.confidence * 1.2, 0, 1),
      probabilityType: 'QUALITATIVE',
      priceTarget,
      timeframe: this.timeframeToString(thesis.timeHorizon),
    };
  }

  // -----------------------------------------------------------------------
  // 3. Base scenario
  // -----------------------------------------------------------------------
  buildBaseScenario(
    thesis: TradingThesis,
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    currentPrice?: number,
  ): Scenario {
    const assumptions: string[] = [];
    const risks: string[] = [];
    const implications: string[] = [];

    if (thesis.baseCase) assumptions.push(thesis.baseCase);
    assumptions.push('Current market conditions persist');
    assumptions.push('No major unexpected events');

    if (technical) {
      if (technical.trend.direction === 'RANGE') {
        assumptions.push('Price remains range-bound');
      } else if (technical.trend.direction === 'UPTREND') {
        assumptions.push('Trend continues at moderate pace');
      } else {
        assumptions.push('Current trend persists');
      }
    }

    if (fundamental) {
      if (fundamental.valuationAssessment === 'FAIR') {
        assumptions.push('Valuation remains at fair levels');
      }
    }

    thesis.keyRisks.slice(0, 2).forEach(r => risks.push(r));
    risks.push('Gradual erosion of thesis edge over time');

    implications.push('Moderate returns expected');
    implications.push('Risk/reward remains acceptable');

    const priceTarget = currentPrice
      ? this.estimatePriceTarget('BASE', currentPrice, technical, fundamental)
      : undefined;

    return {
      type: 'BASE',
      description: `Base case for ${thesis.symbol}: ${thesis.baseCase || 'continuation scenario'}`,
      assumptions,
      expectedImplications: implications,
      risks,
      confidence: thesis.confidence,
      probabilityType: 'QUALITATIVE',
      priceTarget,
      timeframe: this.timeframeToString(thesis.timeHorizon),
    };
  }

  // -----------------------------------------------------------------------
  // 4. Bear scenario
  // -----------------------------------------------------------------------
  buildBearScenario(
    thesis: TradingThesis,
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    currentPrice?: number,
  ): Scenario {
    const assumptions: string[] = [];
    const risks: string[] = [];
    const implications: string[] = [];

    if (thesis.bearCase) assumptions.push(thesis.bearCase);
    if (thesis.keyRisks.length > 0) {
      assumptions.push(`Key risks materialize: ${thesis.keyRisks.slice(0, 3).join(', ')}`);
    }

    if (technical) {
      const support = technical.supportResistance
        .filter(l => l.type === 'SUPPORT')
        .sort((a, b) => b.price - a.price);
      if (support.length > 0) {
        assumptions.push(`Price breaks below support at ${support[0].price.toFixed(2)}`);
        implications.push(`Downside target near ${support[support.length - 1]?.price.toFixed(2) ?? 'N/A'}`);
      }
      if (technical.trend.direction === 'DOWNTREND') {
        assumptions.push(`Downtrend accelerates with strength ${technical.trend.strength}%`);
      }
    }

    if (fundamental) {
      if (fundamental.valuationAssessment === 'OVERVALUED') {
        assumptions.push('Valuation contracts toward peers');
      }
      if (fundamental.financialHealth === 'WEAK' || fundamental.financialHealth === 'CRITICAL') {
        assumptions.push('Financial stress intensifies');
      }
    }

    thesis.invalidationConditions.slice(0, 2).forEach(r => risks.push(r));
    risks.push('Thesis may be invalidated');

    implications.push('Significant downside possible');
    implications.push('Risk management critical');

    const priceTarget = currentPrice
      ? this.estimatePriceTarget('BEAR', currentPrice, technical, fundamental)
      : undefined;

    return {
      type: 'BEAR',
      description: `Bear case for ${thesis.symbol}: ${thesis.bearCase || 'downside scenario'}`,
      assumptions,
      expectedImplications: implications,
      risks,
      confidence: clamp(thesis.confidence * 0.8, 0, 1),
      probabilityType: 'QUALITATIVE',
      priceTarget,
      timeframe: this.timeframeToString(thesis.timeHorizon),
    };
  }

  // -----------------------------------------------------------------------
  // 5. Stress scenario
  // -----------------------------------------------------------------------
  buildStressScenario(
    thesis: TradingThesis,
    technical?: TechnicalAnalysis,
    risk?: RiskAssessment,
  ): Scenario {
    const assumptions: string[] = [];
    const risks: string[] = [];
    const implications: string[] = [];

    assumptions.push('Severe market stress scenario');
    assumptions.push('Correlations spike to 1.0');
    assumptions.push('Liquidity dries up significantly');

    if (risk) {
      if (risk.volatilityRisk === 'EXTREME' || risk.volatilityRisk === 'HIGH') {
        assumptions.push('Volatility spikes to extreme levels');
      }
      if (risk.gapRisk === 'EXTREME' || risk.gapRisk === 'HIGH') {
        assumptions.push('Large gap moves possible');
      }
    }

    if (technical?.volatility) {
      const stressMove = technical.volatility.atr14 * 4;
      assumptions.push(`Expected stress move: ~${stressMove.toFixed(2)} (4x ATR)`);
    }

    risks.push('Worst-case scenario for position');
    risks.push('Margin calls and forced selling possible');
    risks.push('Correlation breakdown across assets');

    implications.push('Maximum drawdown scenario');
    implications.push('Capital preservation paramount');
    implications.push('Thesis likely invalidated under stress');

    const priceTarget = technical?.indicators.sma20?.value
      ? this.estimatePriceTarget('STRESS', technical.indicators.sma20.value, technical)
      : undefined;

    return {
      type: 'STRESS',
      description: `Stress test for ${thesis.symbol}: extreme adverse conditions`,
      assumptions,
      expectedImplications: implications,
      risks,
      confidence: 0.3,
      probabilityType: 'QUALITATIVE',
      probability: 0.05,
      priceTarget,
      timeframe: this.timeframeToString(thesis.timeHorizon),
    };
  }

  // -----------------------------------------------------------------------
  // 6. Sensitivity analysis
  // -----------------------------------------------------------------------
  computeSensitivity(
    variables: readonly ScenarioVariable[],
    direction: 'UP' | 'DOWN',
  ): readonly { variable: string; impact: string }[] {
    const results: { variable: string; impact: string }[] = [];

    for (const v of variables) {
      const bullVal = v.bullValue;
      const bearVal = v.bearValue;
      const baseVal = v.baseValue;

      if (bullVal === undefined || bearVal === undefined || baseVal === undefined) continue;

      if (typeof bullVal === 'number' && typeof bearVal === 'number' && typeof baseVal === 'number') {
        const bullImpact = ((bullVal - baseVal) / Math.abs(baseVal || 1)) * 100;
        const bearImpact = ((bearVal - baseVal) / Math.abs(baseVal || 1)) * 100;

        if (direction === 'UP') {
          results.push({
            variable: v.name,
            impact: `+${bullImpact.toFixed(1)}% if ${v.description} improves`,
          });
        } else {
          results.push({
            variable: v.name,
            impact: `${bearImpact.toFixed(1)}% if ${v.description} deteriorates`,
          });
        }
      } else {
        if (direction === 'UP') {
          results.push({
            variable: v.name,
            impact: `Positive if ${v.description} trends bull case`,
          });
        } else {
          results.push({
            variable: v.name,
            impact: `Negative if ${v.description} trends bear case`,
          });
        }
      }
    }

    return results;
  }

  // -----------------------------------------------------------------------
  // 7. Define scenario variables
  // -----------------------------------------------------------------------
  defineVariables(
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
  ): readonly ScenarioVariable[] {
    const variables: ScenarioVariable[] = [];

    if (technical) {
      const price = technical.indicators.sma20?.value ?? 0;

      if (technical.volatility) {
        variables.push({
          name: 'Volatility',
          description: 'market volatility regime',
          bullValue: 'LOW',
          baseValue: technical.volatility.regime,
          bearValue: 'HIGH',
          stressValue: 'EXTREME',
        });
      }

      if (technical.trend) {
        variables.push({
          name: 'Trend',
          description: 'price trend direction',
          bullValue: 'UPTREND',
          baseValue: technical.trend.direction,
          bearValue: 'DOWNTREND',
          stressValue: 'DOWNTREND',
        });
      }

      if (technical.volume) {
        variables.push({
          name: 'Volume',
          description: 'trading volume profile',
          bullValue: 'EXPANDING',
          baseValue: technical.volume.trend,
          bearValue: 'CONTRACTING',
          stressValue: 'CONTRACTING',
        });
      }

      if (technical.multiTimeframe) {
        variables.push({
          name: 'MTF Alignment',
          description: 'multi-timeframe trend alignment',
          bullValue: 1.0,
          baseValue: technical.multiTimeframe.alignmentScore,
          bearValue: -1.0,
          stressValue: -1.0,
        });
      }
    }

    if (fundamental) {
      variables.push({
        name: 'Valuation',
        description: 'fundamental valuation assessment',
        bullValue: 'UNDERVALUED',
        baseValue: fundamental.valuationAssessment,
        bearValue: 'OVERVALUED',
        stressValue: 'OVERVALUED',
      });

      variables.push({
        name: 'Growth',
        description: 'revenue and earnings growth',
        bullValue: 'HIGH_GROWTH',
        baseValue: fundamental.growthAssessment,
        bearValue: 'DECLINE',
        stressValue: 'DECLINE',
      });

      variables.push({
        name: 'Financial Health',
        description: 'balance sheet and cash flow health',
        bullValue: 'STRONG',
        baseValue: fundamental.financialHealth,
        bearValue: 'WEAK',
        stressValue: 'CRITICAL',
      });

      if (fundamental.metrics.pe !== undefined) {
        variables.push({
          name: 'P/E Ratio',
          description: 'price-to-earnings multiple',
          bullValue: Math.max(5, fundamental.metrics.pe * 0.7),
          baseValue: fundamental.metrics.pe,
          bearValue: fundamental.metrics.pe * 1.4,
          stressValue: fundamental.metrics.pe * 2,
        });
      }
    }

    return variables;
  }

  // -----------------------------------------------------------------------
  // 8. Estimate price target
  // -----------------------------------------------------------------------
  estimatePriceTarget(
    type: ScenarioType,
    currentPrice: number,
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
  ): number {
    if (currentPrice <= 0) return 0;

    const atr = technical?.volatility?.atr14 ?? 0;
    const sr = technical?.supportResistance ?? [];
    const supports = sr.filter(l => l.type === 'SUPPORT').sort((a, b) => b.price - a.price);
    const resistances = sr.filter(l => l.type === 'RESISTANCE').sort((a, b) => a.price - b.price);

    switch (type) {
      case 'BULL': {
        // Target: break above nearest resistance + ATR extension
        const nearestRes = resistances.length > 0 ? resistances[0].price : currentPrice * 1.05;
        const extension = atr > 0 ? atr * 1.5 : currentPrice * 0.03;
        return nearestRes + extension;
      }

      case 'BASE': {
        // Target: stay near current or drift toward mean
        const meanTarget = technical?.indicators.sma50?.value ?? currentPrice;
        return currentPrice + (meanTarget - currentPrice) * 0.3;
      }

      case 'BEAR': {
        // Target: break below nearest support - ATR extension
        const nearestSup = supports.length > 0 ? supports[0].price : currentPrice * 0.95;
        const extension = atr > 0 ? atr * 1.5 : currentPrice * 0.03;
        return nearestSup - extension;
      }

      case 'STRESS': {
        // Target: 3-4x ATR downside
        const stressMove = atr > 0 ? atr * 3.5 : currentPrice * 0.1;
        return currentPrice - stressMove;
      }

      default:
        return currentPrice;
    }
  }

  // -----------------------------------------------------------------------
  // Private helpers
  // -----------------------------------------------------------------------
  private timeframeToString(timeframe: TimeHorizon): string {
    const map: Record<TimeHorizon, string> = {
      INTRADAY: 'Intraday',
      SHORT_TERM: '1-5 days',
      SWING: '1-4 weeks',
      MEDIUM_TERM: '1-3 months',
      LONG_TERM: '3-12 months',
    };
    return map[timeframe] ?? 'Unknown';
  }
}
