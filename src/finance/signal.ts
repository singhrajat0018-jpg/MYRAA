// ============================================================================
// MYRAA Phase 26 — Signal Engine
// Generates trading signals by weighting evidence from all analysis sources.
// Deterministic, no fabrication. All scores derived from input data only.
// ============================================================================

import type {
  TechnicalAnalysis,
  FundamentalAnalysis,
  EventAnalysis,
  MacroContext,
  MarketRegime,
  RiskAssessment,
  SignalComponents,
  SignalWeights,
  TradingSignal,
  SignalBias,
  StrategyType,
  TimeHorizon,
} from './contracts';

import { DEFAULT_SIGNAL_WEIGHTS } from './contracts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function hasData<T>(v: T | undefined | null): boolean {
  return v !== undefined && v !== null;
}

let signalCounter = 0;
const nextSignalId = () => `sig-${Date.now()}-${++signalCounter}`;

// ---------------------------------------------------------------------------
// Regime–Strategy compatibility matrix
// ---------------------------------------------------------------------------

const REGIME_STRATEGY_BIAS: Record<string, Record<string, number>> = {
  TRENDING_BULL:  { MOMENTUM: 0.8, TREND: 0.9, BREAKOUT: 0.7, MEAN_REVERSION: -0.3, VALUE: 0.2, GROWTH: 0.5, QUALITY: 0.3, RELATIVE_STRENGTH: 0.6, EVENT_DRIVEN: 0.1, MACRO: 0.2 },
  TRENDING_BEAR:  { MOMENTUM: -0.6, TREND: -0.7, BREAKOUT: -0.5, MEAN_REVERSION: 0.4, VALUE: 0.3, GROWTH: -0.4, QUALITY: 0.4, RELATIVE_STRENGTH: -0.3, EVENT_DRIVEN: 0.1, MACRO: -0.2 },
  RANGE:          { MOMENTUM: -0.1, TREND: -0.2, BREAKOUT: 0.1, MEAN_REVERSION: 0.7, VALUE: 0.5, GROWTH: 0.1, QUALITY: 0.4, RELATIVE_STRENGTH: 0.0, EVENT_DRIVEN: 0.3, MACRO: 0.0 },
  HIGH_VOLATILITY:{ MOMENTUM: 0.2, TREND: 0.0, BREAKOUT: 0.5, MEAN_REVERSION: -0.4, VALUE: 0.1, GROWTH: -0.3, QUALITY: 0.3, RELATIVE_STRENGTH: 0.1, EVENT_DRIVEN: 0.4, MACRO: 0.3 },
  LOW_VOLATILITY: { MOMENTUM: 0.5, TREND: 0.6, BREAKOUT: -0.1, MEAN_REVERSION: 0.4, VALUE: 0.2, GROWTH: 0.4, QUALITY: 0.3, RELATIVE_STRENGTH: 0.5, EVENT_DRIVEN: 0.0, MACRO: 0.1 },
  RISK_ON:        { MOMENTUM: 0.7, TREND: 0.6, BREAKOUT: 0.6, MEAN_REVERSION: -0.2, VALUE: 0.1, GROWTH: 0.7, QUALITY: 0.2, RELATIVE_STRENGTH: 0.5, EVENT_DRIVEN: 0.2, MACRO: 0.5 },
  RISK_OFF:       { MOMENTUM: -0.5, TREND: -0.4, BREAKOUT: -0.3, MEAN_REVERSION: 0.5, VALUE: 0.6, GROWTH: -0.6, QUALITY: 0.7, RELATIVE_STRENGTH: -0.2, EVENT_DRIVEN: 0.3, MACRO: 0.4 },
  MIXED:          { MOMENTUM: 0.0, TREND: 0.0, BREAKOUT: 0.1, MEAN_REVERSION: 0.1, VALUE: 0.2, GROWTH: 0.0, QUALITY: 0.2, RELATIVE_STRENGTH: 0.1, EVENT_DRIVEN: 0.1, MACRO: 0.1 },
  UNKNOWN:        { MOMENTUM: 0.0, TREND: 0.0, BREAKOUT: 0.0, MEAN_REVERSION: 0.0, VALUE: 0.0, GROWTH: 0.0, QUALITY: 0.0, RELATIVE_STRENGTH: 0.0, EVENT_DRIVEN: 0.0, MACRO: 0.0 },
};

// ---------------------------------------------------------------------------
// SignalEngine
// ---------------------------------------------------------------------------

export class SignalEngine {
  private readonly source = 'SignalEngine';

  // -----------------------------------------------------------------------
  // 1. Main entry point
  // -----------------------------------------------------------------------
  generate(params: {
    technical?: TechnicalAnalysis;
    fundamental?: FundamentalAnalysis;
    events?: EventAnalysis;
    macro?: MacroContext;
    regime?: MarketRegime;
    weights?: SignalWeights;
    symbol: string;
    assetId: string;
    timeframe: TimeHorizon;
    strategy: StrategyType;
  }): TradingSignal {
    const { technical, fundamental, events, macro, regime, symbol, assetId, timeframe, strategy } = params;
    const weights = params.weights ?? this.defaultWeights(technical, fundamental, events, macro, regime);

    const components: SignalComponents = {
      technicalScore: this.computeTechnicalScore(technical),
      fundamentalScore: this.computeFundamentalScore(fundamental),
      eventScore: this.computeEventScore(events),
      macroScore: this.computeMacroScore(macro),
      sentimentScore: this.computeSentimentScore(events),
      regimeScore: this.computeRegimeScore(regime, strategy),
      riskScore: this.computeRiskScore(),
    };

    const { score, confidence } = this.weightedComposite(components, weights);
    const { bias, strength } = this.determineBias(score, confidence);
    const evidence = this.collectEvidence(technical, fundamental, events, macro, regime);
    const invalidationConditions = this.defineInvalidationConditions(technical, fundamental, events);

    const now = Date.now();
    const createdAt = new Date(now).toISOString();
    const expiresAt = this.computeExpiry(timeframe, now);

    return {
      id: nextSignalId(),
      assetId,
      symbol,
      bias,
      strength: clamp(strength, 0, 1),
      confidence: clamp(confidence, 0, 1),
      components,
      weights,
      timeframe,
      strategy,
      evidence: evidence.bullish.concat(evidence.bearish, evidence.neutral),
      contradictions: this.collectContradictions(components, evidence),
      invalidationConditions,
      createdAt,
      expiresAt,
      status: 'ACTIVE',
      version: 1,
    };
  }

  // -----------------------------------------------------------------------
  // 2. Compute technical score
  // -----------------------------------------------------------------------
  computeTechnicalScore(technical?: TechnicalAnalysis): number {
    if (!technical) return 0;

    let score = 0;
    let weightSum = 0;

    // Trend direction (0.25 weight)
    const trendMap: Record<string, number> = { UPTREND: 1, DOWNTREND: -1, RANGE: 0, TRANSITION: 0, UNKNOWN: 0 };
    const trendScore = (trendMap[technical.trend.direction] ?? 0) * (technical.trend.strength / 100);
    score += trendScore * 0.25;
    weightSum += 0.25;

    // RSI (0.15 weight)
    if (technical.indicators.rsi14) {
      const rsi = technical.indicators.rsi14.value;
      const rsiScore = rsi > 70 ? -clamp((rsi - 70) / 30, 0, 1)
        : rsi < 30 ? clamp((30 - rsi) / 30, 0, 1)
        : (50 - rsi) / 50 * -0.2;
      score += rsiScore * 0.15;
      weightSum += 0.15;
    }

    // MACD (0.15 weight)
    if (technical.indicators.macd) {
      const m = technical.indicators.macd;
      const macdScore = clamp(m.histogram / 2, -1, 1);
      score += macdScore * 0.15;
      weightSum += 0.15;
    }

    // Multi-timeframe alignment (0.20 weight)
    score += clamp(technical.multiTimeframe.alignmentScore, -1, 1) * 0.20;
    weightSum += 0.20;

    // Breakout (0.10 weight)
    if (technical.breakout) {
      const bScore = technical.breakout.type === 'BREAKOUT' ? 0.6
        : technical.breakout.type === 'BREAKDOWN' ? -0.6
        : technical.breakout.type === 'FALSE_BREAKOUT' ? -0.3
        : 0.1;
      score += bScore * (technical.breakout.confidence) * 0.10;
      weightSum += 0.10;
    }

    // Volume (0.10 weight)
    if (technical.volume) {
      const vScore = technical.volume.relativeVolume > 1.5 ? 0.4
        : technical.volume.relativeVolume < 0.5 ? -0.2
        : 0;
      score += vScore * 0.10;
      weightSum += 0.10;
    }

    // Volatility (0.05 weight)
    if (technical.volatility) {
      const volScore = technical.volatility.regime === 'HIGH' ? -0.3
        : technical.volatility.regime === 'LOW' ? 0.2
        : 0;
      score += volScore * 0.05;
      weightSum += 0.05;
    }

    return weightSum > 0 ? clamp(score / weightSum, -1, 1) : 0;
  }

  // -----------------------------------------------------------------------
  // 3. Compute fundamental score
  // -----------------------------------------------------------------------
  computeFundamentalScore(fundamental?: FundamentalAnalysis): number {
    if (!fundamental) return 0;

    let score = 0;
    let weightSum = 0;

    // Valuation (0.30)
    const valMap: Record<string, number> = { UNDERVALUED: 0.7, FAIR: 0, OVERVALUED: -0.7, UNKNOWN: 0 };
    score += (valMap[fundamental.valuationAssessment] ?? 0) * 0.30;
    weightSum += 0.30;

    // Growth (0.25)
    const growthMap: Record<string, number> = { HIGH_GROWTH: 0.7, MODERATE_GROWTH: 0.3, LOW_GROWTH: 0, DECLINE: -0.6, UNKNOWN: 0 };
    score += (growthMap[fundamental.growthAssessment] ?? 0) * 0.25;
    weightSum += 0.25;

    // Financial health (0.25)
    const healthMap: Record<string, number> = { STRONG: 0.6, ADEQUATE: 0.1, WEAK: -0.5, CRITICAL: -0.8, UNKNOWN: 0 };
    score += (healthMap[fundamental.financialHealth] ?? 0) * 0.25;
    weightSum += 0.25;

    // Quality score (0.20)
    score += clamp(fundamental.qualityScore * 2 - 1, -1, 1) * 0.20;
    weightSum += 0.20;

    return weightSum > 0 ? clamp(score / weightSum, -1, 1) : 0;
  }

  // -----------------------------------------------------------------------
  // 4. Compute event score
  // -----------------------------------------------------------------------
  computeEventScore(events?: EventAnalysis): number {
    if (!events) return 0;

    let score = 0;
    let weightSum = 0;

    // Sentiment score (0.40)
    score += clamp(events.sentimentScore, -1, 1) * 0.40;
    weightSum += 0.40;

    // Catalyst count and direction (0.30)
    const upcomingCatalysts = events.upcomingCatalysts.filter(c => c.status === 'UPCOMING');
    if (upcomingCatalysts.length > 0) {
      const bullishCatalysts = upcomingCatalysts.filter(c => c.directionHypothesis === 'POSITIVE').length;
      const bearishCatalysts = upcomingCatalysts.filter(c => c.directionHypothesis === 'NEGATIVE').length;
      const catalystBias = (bullishCatalysts - bearishCatalysts) / Math.max(upcomingCatalysts.length, 1);
      score += clamp(catalystBias, -1, 1) * 0.30;
      weightSum += 0.30;
    }

    // News volume and importance (0.30)
    const highImportanceNews = events.recentNews.filter(n => n.importance === 'HIGH');
    if (highImportanceNews.length > 0) {
      const avgSentiment = highImportanceNews.reduce((s, n) => s + n.sentimentScore, 0) / highImportanceNews.length;
      score += clamp(avgSentiment, -1, 1) * 0.30;
      weightSum += 0.30;
    }

    return weightSum > 0 ? clamp(score / weightSum, -1, 1) : 0;
  }

  // -----------------------------------------------------------------------
  // 5. Compute macro score
  // -----------------------------------------------------------------------
  computeMacroScore(macro?: MacroContext): number {
    if (!macro) return 0;

    let score = 0;
    let weightSum = 0;

    // Risk sentiment (0.35)
    const riskMap: Record<string, number> = { RISK_ON: 0.5, RISK_OFF: -0.5, NEUTRAL: 0 };
    score += (riskMap[macro.riskSentiment] ?? 0) * 0.35;
    weightSum += 0.35;

    // Rate environment (0.25)
    if (macro.rateEnvironment) {
      const rateMap: Record<string, number> = { DOVISH: 0.4, HAWKISH: -0.4, NEUTRAL: 0 };
      score += (rateMap[macro.rateEnvironment] ?? 0) * 0.25;
      weightSum += 0.25;
    }

    // Inflation trend (0.20)
    if (macro.inflationTrend) {
      const inflMap: Record<string, number> = { FALLING: 0.3, RISING: -0.3, STABLE: 0 };
      score += (inflMap[macro.inflationTrend] ?? 0) * 0.20;
      weightSum += 0.20;
    }

    // GDP growth (0.20)
    if (macro.gdpGrowth !== undefined) {
      score += clamp(macro.gdpGrowth / 5, -1, 1) * 0.20;
      weightSum += 0.20;
    }

    return weightSum > 0 ? clamp(score / weightSum, -1, 1) : 0;
  }

  // -----------------------------------------------------------------------
  // 6. Compute sentiment score
  // -----------------------------------------------------------------------
  computeSentimentScore(events?: EventAnalysis): number {
    if (!events) return 0;

    const sentimentMap: Record<string, number> = {
      VERY_BULLISH: 1, BULLISH: 0.5, NEUTRAL: 0, BEARISH: -0.5, VERY_BEARISH: -1,
    };
    const labelScore = sentimentMap[events.overallSentiment] ?? 0;
    const rawScore = (labelScore * 0.5) + (clamp(events.sentimentScore, -1, 1) * 0.5);

    // Penalize contradictions
    const penalty = events.contradictionDetected ? 0.3 : 0;
    return clamp(rawScore * (1 - penalty), -1, 1);
  }

  // -----------------------------------------------------------------------
  // 7. Compute regime–strategy score
  // -----------------------------------------------------------------------
  computeRegimeScore(regime?: MarketRegime, strategy?: StrategyType): number {
    if (!regime || !strategy) return 0;

    const table = REGIME_STRATEGY_BIAS[regime.type];
    if (!table) return 0;

    const baseScore = table[strategy] ?? 0;
    return clamp(baseScore * regime.confidence, -1, 1);
  }

  // -----------------------------------------------------------------------
  // 8. Compute risk score (placeholder until RiskEngine is wired)
  // -----------------------------------------------------------------------
  computeRiskScore(): number {
    return 0;
  }

  // -----------------------------------------------------------------------
  // 9. Weighted composite
  // -----------------------------------------------------------------------
  weightedComposite(components: SignalComponents, weights: SignalWeights): { score: number; confidence: number } {
    const weightSum =
      weights.technical + weights.fundamental + weights.event +
      weights.macro + weights.sentiment + weights.regime;

    if (weightSum === 0) return { score: 0, confidence: 0 };

    const rawScore =
      components.technicalScore * weights.technical +
      components.fundamentalScore * weights.fundamental +
      components.eventScore * weights.event +
      components.macroScore * weights.macro +
      components.sentimentScore * weights.sentiment +
      components.regimeScore * weights.regime;

    const score = rawScore / weightSum;

    // Confidence from data availability: more sources → higher confidence
    const activeSources = [
      components.technicalScore !== 0,
      components.fundamentalScore !== 0,
      components.eventScore !== 0,
      components.macroScore !== 0,
      components.sentimentScore !== 0,
      components.regimeScore !== 0,
    ].filter(Boolean).length;

    const dataConfidence = activeSources / 6;
    const scoreConfidence = Math.abs(score);
    const confidence = clamp(dataConfidence * 0.6 + scoreConfidence * 0.4, 0, 1);

    return { score: clamp(score, -1, 1), confidence };
  }

  // -----------------------------------------------------------------------
  // 10. Determine bias from score
  // -----------------------------------------------------------------------
  determineBias(score: number, confidence: number): { bias: SignalBias; strength: number } {
    const absScore = Math.abs(score);

    if (confidence < 0.2 || absScore < 0.1) {
      return { bias: 'NO_SIGNAL', strength: 0 };
    }

    if (absScore < 0.25) {
      return { bias: 'WATCH', strength: absScore };
    }

    if (score > 0) {
      return { bias: 'LONG_BIAS', strength: absScore };
    } else {
      return { bias: 'SHORT_BIAS', strength: absScore };
    }
  }

  // -----------------------------------------------------------------------
  // 11. Collect evidence
  // -----------------------------------------------------------------------
  collectEvidence(
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    events?: EventAnalysis,
    macro?: MacroContext,
    regime?: MarketRegime,
  ): { bullish: string[]; bearish: string[]; neutral: string[] } {
    const bullish: string[] = [];
    const bearish: string[] = [];
    const neutral: string[] = [];

    if (technical) {
      technical.bullishEvidence.forEach(e => bullish.push(`[TA] ${e}`));
      technical.bearishEvidence.forEach(e => bearish.push(`[TA] ${e}`));
      technical.neutralEvidence.forEach(e => neutral.push(`[TA] ${e}`));
    }

    if (fundamental) {
      fundamental.evidence.forEach(e => {
        const lower = e.toLowerCase();
        if (lower.includes('overvalued') || lower.includes('weak') || lower.includes('decline') || lower.includes('high debt')) {
          bearish.push(`[FA] ${e}`);
        } else if (lower.includes('undervalued') || lower.includes('strong') || lower.includes('growth') || lower.includes('low debt')) {
          bullish.push(`[FA] ${e}`);
        } else {
          neutral.push(`[FA] ${e}`);
        }
      });
    }

    if (events) {
      events.evidence.forEach(e => {
        const lower = e.toLowerCase();
        if (lower.includes('positive') || lower.includes('upgrade') || lower.includes('beat') || lower.includes('growth')) {
          bullish.push(`[EVT] ${e}`);
        } else if (lower.includes('negative') || lower.includes('downgrade') || lower.includes('miss') || lower.includes('decline')) {
          bearish.push(`[EVT] ${e}`);
        } else {
          neutral.push(`[EVT] ${e}`);
        }
      });
    }

    if (macro) {
      macro.evidence.forEach(e => {
        const lower = e.toLowerCase();
        if (lower.includes('risk-on') || lower.includes('dovish') || lower.includes('improving') || lower.includes('growth')) {
          bullish.push(`[MAC] ${e}`);
        } else if (lower.includes('risk-off') || lower.includes('hawkish') || lower.includes('weakening') || lower.includes('recession')) {
          bearish.push(`[MAC] ${e}`);
        } else {
          neutral.push(`[MAC] ${e}`);
        }
      });
    }

    if (regime) {
      regime.evidence.forEach(e => {
        const lower = e.toLowerCase();
        if (lower.includes('bull') || lower.includes('risk-on') || lower.includes('expanding')) {
          bullish.push(`[REG] ${e}`);
        } else if (lower.includes('bear') || lower.includes('risk-off') || lower.includes('contracting')) {
          bearish.push(`[REG] ${e}`);
        } else {
          neutral.push(`[REG] ${e}`);
        }
      });
    }

    return { bullish, bearish, neutral };
  }

  // -----------------------------------------------------------------------
  // 12. Invalidation conditions
  // -----------------------------------------------------------------------
  defineInvalidationConditions(
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    events?: EventAnalysis,
  ): readonly string[] {
    const conditions: string[] = [];

    if (technical) {
      const sr = technical.supportResistance;
      if (sr.length > 0) {
        const supports = sr.filter(l => l.type === 'SUPPORT').sort((a, b) => a.price - b.price);
        if (supports.length > 0) {
          conditions.push(`Price closes below support at ${supports[0].price.toFixed(2)}`);
        }
        const resistances = sr.filter(l => l.type === 'RESISTANCE').sort((a, b) => b.price - a.price);
        if (resistances.length > 0) {
          conditions.push(`Price closes above resistance at ${resistances[0].price.toFixed(2)}`);
        }
      }

      if (technical.indicators.rsi14) {
        conditions.push(`RSI reaches ${technical.indicators.rsi14.value > 50 ? 'oversold below 30' : 'overbought above 70'}`);
      }

      if (technical.trend.direction === 'UPTREND') {
        conditions.push('Trend direction shifts to DOWNTREND');
      } else if (technical.trend.direction === 'DOWNTREND') {
        conditions.push('Trend direction shifts to UPTREND');
      }

      if (technical.multiTimeframe.alignmentScore < -0.5) {
        conditions.push('Multi-timeframe alignment flips to strongly bearish');
      } else if (technical.multiTimeframe.alignmentScore > 0.5) {
        conditions.push('Multi-timeframe alignment flips to strongly bullish');
      }
    }

    if (fundamental) {
      if (fundamental.valuationAssessment === 'OVERVALUED') {
        conditions.push('Fundamental valuation remains overextended');
      } else if (fundamental.valuationAssessment === 'UNDERVALUED') {
        conditions.push('Fundamental valuation loses discount');
      }
      if (fundamental.financialHealth === 'CRITICAL') {
        conditions.push('Financial health deteriorates to critical');
      }
    }

    if (events) {
      const highImpact = events.upcomingCatalysts.filter(c => c.importance === 'HIGH' && c.status === 'UPCOMING');
      if (highImpact.length > 0) {
        conditions.push(`High-impact catalyst: ${highImpact[0].description}`);
      }
      if (events.contradictionDetected) {
        conditions.push('Contradictory signals detected in news/events');
      }
    }

    return conditions;
  }

  // -----------------------------------------------------------------------
  // 13. Correlation check — adjust weights to prevent double-counting
  // -----------------------------------------------------------------------
  checkCorrelation(technical: TechnicalAnalysis): SignalWeights {
    const base = { ...DEFAULT_SIGNAL_WEIGHTS };

    // If trend and multi-timeframe are strongly aligned, reduce trend overlap
    if (Math.abs(technical.trend.strength) > 70 && Math.abs(technical.multiTimeframe.alignmentScore) > 0.7) {
      base.technical *= 0.85;
      base.regime *= 1.10;
    }

    // If volatility is extreme, it may be dominating the technical signal
    if (technical.volatility && technical.volatility.regime === 'HIGH') {
      base.technical *= 0.90;
      base.event *= 1.10;
    }

    // Breakout with volume confirmation — boost event weight
    if (technical.breakout && technical.breakout.volumeConfirmation) {
      base.event *= 1.15;
      base.technical *= 0.90;
    }

    // Normalize weights to sum to 1
    const sum = base.technical + base.fundamental + base.event + base.macro + base.sentiment + base.regime;
    if (sum > 0) {
      return {
        technical: base.technical / sum,
        fundamental: base.fundamental / sum,
        event: base.event / sum,
        macro: base.macro / sum,
        sentiment: base.sentiment / sum,
        regime: base.regime / sum,
      };
    }

    return { ...DEFAULT_SIGNAL_WEIGHTS };
  }

  // -----------------------------------------------------------------------
  // Private helpers
  // -----------------------------------------------------------------------
  private defaultWeights(
    technical?: TechnicalAnalysis,
    fundamental?: FundamentalAnalysis,
    events?: EventAnalysis,
    macro?: MacroContext,
    regime?: MarketRegime,
  ): SignalWeights {
    const base = { ...DEFAULT_SIGNAL_WEIGHTS };
    const available = [
      hasData(technical), hasData(fundamental), hasData(events),
      hasData(macro), hasData(regime),
    ].filter(Boolean).length;

    // If most sources unavailable, reduce all weights proportionally
    if (available < 3) {
      const factor = available / 5;
      return {
        technical: base.technical * factor + (1 - factor) * (1 / 6),
        fundamental: base.fundamental * factor + (1 - factor) * (1 / 6),
        event: base.event * factor + (1 - factor) * (1 / 6),
        macro: base.macro * factor + (1 - factor) * (1 / 6),
        sentiment: base.sentiment * factor + (1 - factor) * (1 / 6),
        regime: base.regime * factor + (1 - factor) * (1 / 6),
      };
    }

    return base;
  }

  private computeExpiry(timeframe: TimeHorizon, now: number): string {
    const durations: Record<TimeHorizon, number> = {
      INTRADAY: 4 * 60 * 60 * 1000,
      SHORT_TERM: 24 * 60 * 60 * 1000,
      SWING: 7 * 24 * 60 * 60 * 1000,
      MEDIUM_TERM: 30 * 24 * 60 * 60 * 1000,
      LONG_TERM: 90 * 24 * 60 * 60 * 1000,
    };
    return new Date(now + (durations[timeframe] ?? durations.SWING)).toISOString();
  }

  private collectContradictions(components: SignalComponents, evidence: { bullish: string[]; bearish: string[]; neutral: string[] }): readonly string[] {
    const contradictions: string[] = [];

    if (components.technicalScore > 0.3 && components.fundamentalScore < -0.3) {
      contradictions.push('Technical bullish vs Fundamental bearish');
    }
    if (components.technicalScore < -0.3 && components.fundamentalScore > 0.3) {
      contradictions.push('Technical bearish vs Fundamental bullish');
    }
    if (components.eventScore > 0.3 && components.macroScore < -0.3) {
      contradictions.push('Events bullish vs Macro bearish');
    }
    if (components.eventScore < -0.3 && components.macroScore > 0.3) {
      contradictions.push('Events bearish vs Macro bullish');
    }
    if (evidence.bullish.length > 0 && evidence.bearish.length > 0) {
      const ratio = evidence.bullish.length / evidence.bearish.length;
      if (ratio > 3 || ratio < 1 / 3) {
        contradictions.push(`Evidence imbalance: ${evidence.bullish.length} bullish vs ${evidence.bearish.length} bearish`);
      }
    }

    return contradictions;
  }
}
