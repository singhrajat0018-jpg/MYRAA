// ============================================================================
// MYRAA Phase 26 — Trading Thesis Engine
// ============================================================================

import type {
  TradingThesis,
  ThesisAuditEntry,
  ThesisStatus,
  TechnicalAnalysis,
  FundamentalAnalysis,
  EventAnalysis,
  MacroContext,
  MarketRegime,
  EvidenceMatrix,
  EvidenceEntry,
  TradingSignal,
  ScenarioAnalysis,
  RiskAssessment,
  MarketSnapshot,
  TimeHorizon,
  SignalBias,
  Catalyst,
  Scenario,
  RiskLevel,
} from './contracts';

const THESIS_STALE_HOURS: Record<TimeHorizon, number> = {
  INTRADAY: 4, SHORT_TERM: 24, SWING: 72, MEDIUM_TERM: 168, LONG_TERM: 720,
};

let thesisCounter = 0;
function generateThesisId(): string { thesisCounter += 1; return `thesis_${Date.now()}_${thesisCounter}`; }
function nowIso(): string { return new Date().toISOString(); }
function riskLabel(l: RiskLevel): string {
  return { LOW: 'low risk', MEDIUM: 'moderate risk', HIGH: 'high risk', EXTREME: 'extreme risk', UNKNOWN: 'unknown risk' }[l];
}

export interface BuildThesisParams {
  readonly symbol: string; readonly assetId: string; readonly timeHorizon: TimeHorizon;
  readonly technical?: TechnicalAnalysis; readonly fundamental?: FundamentalAnalysis;
  readonly events?: EventAnalysis; readonly macro?: MacroContext; readonly regime?: MarketRegime;
  readonly evidenceMatrix: EvidenceMatrix; readonly signal: TradingSignal;
  readonly scenarios: ScenarioAnalysis; readonly risk: RiskAssessment; readonly currentPrice: MarketSnapshot;
}

export interface InvalidationCheckResult { readonly invalidated: boolean; readonly reason?: string; }

export class ThesisEngine {
  build(params: BuildThesisParams): TradingThesis {
    const { symbol, assetId, timeHorizon, technical, fundamental, events, macro, regime,
      evidenceMatrix, signal, scenarios, risk, currentPrice } = params;
    const timestamp = nowIso();
    const id = generateThesisId();
    const bullCase = this.buildBullCase(technical, fundamental, events, regime);
    const bearCase = this.buildBearCase(technical, fundamental, events, risk);
    const baseCase = this.buildBaseCase(signal, scenarios);
    const invalidationConditions = this.defineInvalidation(technical, fundamental, risk);
    const catalysts = this.identifyCatalysts(events, fundamental);
    const risks = this.identifyRisks(risk, events, technical);
    return {
      id, version: 1, assetId, symbol, timeHorizon,
      marketContext: this.buildMarketContext(currentPrice, regime, macro),
      technicalContext: this.buildTechnicalContext(technical),
      fundamentalContext: this.buildFundamentalContext(fundamental),
      eventContext: this.buildEventContext(events),
      macroContext: this.buildMacroContext(macro),
      bullCase, bearCase, baseCase,
      keyRisks: [...risks], keyCatalysts: catalysts.map((c) => c.description),
      invalidationConditions: [...invalidationConditions],
      confidence: signal.confidence, signalBias: signal.bias, signalStrength: signal.strength,
      evidence: [...evidenceMatrix.entries], scenarios: [...scenarios.scenarios],
      riskAssessment: risk, createdAt: timestamp, updatedAt: timestamp,
      expiresAt: this.computeExpiry(timeHorizon, timestamp),
      status: 'ACTIVE', auditTrail: [{ timestamp, action: 'CREATED', reason: 'Initial thesis construction' }],
    };
  }

  buildBullCase(technical?: TechnicalAnalysis, fundamental?: FundamentalAnalysis,
    events?: EventAnalysis, regime?: MarketRegime): string {
    const p: string[] = [];
    if (technical) {
      if (technical.bullishEvidence.length > 0) p.push(`Technical signals: ${technical.bullishEvidence.join('; ')}`);
      if (technical.trend.direction === 'UPTREND') p.push(`Trend is bullish with strength ${technical.trend.strength.toFixed(2)}`);
      if (technical.multiTimeframe.alignmentScore > 0.6) p.push(`Multi-timeframe alignment supports upside (${technical.multiTimeframe.alignmentScore.toFixed(2)})`);
    }
    if (fundamental) {
      if (fundamental.valuationAssessment === 'UNDERVALUED') p.push('Valuation appears attractive');
      if (fundamental.growthAssessment === 'HIGH_GROWTH') p.push('Strong growth supports re-rating');
      if (fundamental.qualityScore > 0.7) p.push(`Quality score strong (${fundamental.qualityScore.toFixed(2)})`);
    }
    if (events?.overallSentiment === 'BULLISH' || events?.overallSentiment === 'VERY_BULLISH') p.push(`News sentiment is ${events.overallSentiment.toLowerCase()}`);
    if (events?.upcomingCatalysts.some((c) => c.directionHypothesis === 'POSITIVE')) {
      const pos = events.upcomingCatalysts.filter((c) => c.directionHypothesis === 'POSITIVE');
      p.push(`Positive catalysts pending: ${pos.map((c) => c.description).join(', ')}`);
    }
    if (regime?.type === 'TRENDING_BULL' || regime?.type === 'RISK_ON') p.push(`Market regime favorable (${regime.type})`);
    return p.length > 0 ? p.join('. ') + '.' : 'No strong bullish evidence identified.';
  }

  buildBearCase(technical?: TechnicalAnalysis, fundamental?: FundamentalAnalysis,
    events?: EventAnalysis, risk?: RiskAssessment): string {
    const p: string[] = [];
    if (technical) {
      if (technical.bearishEvidence.length > 0) p.push(`Technical warnings: ${technical.bearishEvidence.join('; ')}`);
      if (technical.trend.direction === 'DOWNTREND') p.push(`Downtrend in place (strength ${technical.trend.strength.toFixed(2)})`);
      if (technical.multiTimeframe.alignmentScore < 0.4) p.push(`Multi-timeframe alignment weak (${technical.multiTimeframe.alignmentScore.toFixed(2)})`);
    }
    if (fundamental) {
      if (fundamental.valuationAssessment === 'OVERVALUED') p.push('Valuation stretched');
      if (fundamental.financialHealth === 'WEAK' || fundamental.financialHealth === 'CRITICAL') p.push(`Financial health ${fundamental.financialHealth.toLowerCase()}`);
    }
    if (events?.overallSentiment === 'BEARISH' || events?.overallSentiment === 'VERY_BEARISH') p.push(`News sentiment is ${events.overallSentiment.toLowerCase()}`);
    if (events?.contradictionDetected) p.push('Contradictory signals increase uncertainty');
    if (risk) {
      if (risk.overallRisk === 'HIGH' || risk.overallRisk === 'EXTREME') p.push(`Overall risk is ${riskLabel(risk.overallRisk)}`);
      if (risk.eventRisk === 'HIGH' || risk.eventRisk === 'EXTREME') p.push('Elevated event risk');
      if (risk.maxDrawdownScenario !== undefined && risk.maxDrawdownScenario > 0.15) p.push(`Potential max drawdown: ${(risk.maxDrawdownScenario * 100).toFixed(1)}%`);
    }
    return p.length > 0 ? p.join('. ') + '.' : 'No strong bearish evidence identified.';
  }

  buildBaseCase(signal: TradingSignal, scenarios: ScenarioAnalysis): string {
    const p: string[] = [`Signal bias ${signal.bias} (strength ${signal.strength.toFixed(2)}, confidence ${signal.confidence.toFixed(2)})`];
    const base = scenarios.scenarios.find((s) => s.type === 'BASE');
    if (base) {
      p.push(`Base scenario: ${base.description}`);
      if (base.priceTarget !== undefined) p.push(`Price target: ${base.priceTarget}`);
      if (base.probability !== undefined) p.push(`Probability: ${(base.probability * 100).toFixed(1)}%`);
    }
    if (signal.contradictions.length > 0) p.push(`Key contradictions: ${signal.contradictions.join('; ')}`);
    return p.join('. ') + '.';
  }

  defineInvalidation(technical?: TechnicalAnalysis, fundamental?: FundamentalAnalysis,
    risk?: RiskAssessment): readonly string[] {
    const c: string[] = [];
    if (technical) {
      const supports = technical.supportResistance.filter((sr) => sr.type === 'SUPPORT').sort((a, b) => a.price - b.price);
      if (supports.length > 0) c.push(`Break below key support at ${supports[0].price}`);
      if (technical.trend.direction === 'UPTREND' && technical.trend.strength > 0.5) c.push('Trend reverses from uptrend to downtrend');
      if (technical.indicators.rsi14) c.push('RSI drops below 30 indicating oversold reversal failure');
      if (technical.breakout?.type === 'BREAKOUT') c.push(`False breakout below ${technical.breakout.level}`);
    }
    if (fundamental) {
      const lastEarnings = fundamental.earnings[fundamental.earnings.length - 1];
      if (lastEarnings?.epsSurprisePercent !== undefined && lastEarnings.epsSurprisePercent < -10) {
        c.push('Subsequent earnings miss exceeds previous miss magnitude');
      }
      if (fundamental.financialHealth === 'STRONG' || fundamental.financialHealth === 'ADEQUATE') {
        c.push('Financial health deteriorates to WEAK or CRITICAL');
      }
    }
    if (risk?.maxDrawdownScenario !== undefined) c.push(`Drawdown exceeds ${(risk.maxDrawdownScenario * 100).toFixed(0)}% scenario`);
    if (risk?.overallRisk === 'EXTREME') c.push('Risk escalates to EXTREME level');
    if (c.length === 0) {
      c.push('Thesis invalidated if price drops more than 10% from entry');
      c.push('Thesis invalidated if fundamental outlook materially deteriorates');
    }
    return c;
  }

  identifyCatalysts(events?: EventAnalysis, fundamental?: FundamentalAnalysis): readonly Catalyst[] {
    const catalysts: Catalyst[] = [];
    if (events) {
      for (const c of events.upcomingCatalysts) {
        if (c.status === 'UPCOMING') catalysts.push(c);
      }
    }
    if (fundamental) {
      for (const e of fundamental.earnings) {
        const daysUntil = Math.ceil((new Date(e.date).getTime() - Date.now()) / 86_400_000);
        if (daysUntil > 0 && daysUntil <= 90) {
          catalysts.push({
            id: `earnings_${e.symbol}_${e.date}`, type: 'EARNINGS',
            description: `Earnings report on ${e.date}`, expectedDate: e.date,
            knownTime: e.time !== 'UNKNOWN', directionHypothesis: 'UNCERTAIN',
            importance: 'HIGH', confidence: 0.8, status: 'UPCOMING', evidence: ['Scheduled earnings report'],
          });
        }
      }
    }
    return catalysts;
  }

  identifyRisks(risk: RiskAssessment, events?: EventAnalysis, technical?: TechnicalAnalysis): readonly string[] {
    const r: string[] = [];
    const addIfHigh = (level: RiskLevel, label: string) => { if (level === 'HIGH' || level === 'EXTREME') r.push(`${label} is ${level.toLowerCase()}`); };
    addIfHigh(risk.volatilityRisk, 'Volatility risk');
    addIfHigh(risk.liquidityRisk, 'Liquidity risk');
    addIfHigh(risk.eventRisk, 'Event risk');
    addIfHigh(risk.drawdownRisk, 'Drawdown risk');
    addIfHigh(risk.correlationRisk, 'Correlation risk');
    addIfHigh(risk.gapRisk, 'Gap risk');
    if (technical?.volatility.regime === 'HIGH') r.push('Elevated volatility regime');
    if (events?.contradictionDetected) r.push('Conflicting news signals');
    for (const evidence of risk.evidence) r.push(evidence);
    return r;
  }

  versionThesis(existing: TradingThesis, updates: Partial<TradingThesis>, reason: string): TradingThesis {
    const timestamp = nowIso();
    const { auditTrail: _, ...restUpdates } = updates;
    return {
      ...existing, ...restUpdates, version: existing.version + 1, updatedAt: timestamp,
      parentId: existing.id,
      auditTrail: [...existing.auditTrail, { timestamp, action: 'UPDATED', reason, previousVersion: existing.version }],
    };
  }

  checkInvalidation(thesis: TradingThesis, currentData: {
    price?: number; technical?: TechnicalAnalysis; events?: EventAnalysis;
  }): InvalidationCheckResult {
    if (thesis.status !== 'ACTIVE') return { invalidated: true, reason: `Thesis status is ${thesis.status}` };
    if (thesis.expiresAt && Date.now() > new Date(thesis.expiresAt).getTime()) {
      return { invalidated: true, reason: 'Thesis has expired' };
    }
    if (currentData.technical) {
      const t = currentData.technical;
      if ((thesis.signalBias === 'LONG_BIAS' || thesis.signalBias === 'WATCH') && currentData.price !== undefined) {
        const supports = t.supportResistance.filter((sr) => sr.type === 'SUPPORT').sort((a, b) => a.price - b.price);
        if (supports.length > 0 && currentData.price < supports[0].price && supports[0].strength > 0.7) {
          return { invalidated: true, reason: `Price ${currentData.price} broke below key support at ${supports[0].price}` };
        }
      }
      if (thesis.signalBias === 'SHORT_BIAS' && currentData.price !== undefined) {
        const resistances = t.supportResistance.filter((sr) => sr.type === 'RESISTANCE').sort((a, b) => b.price - a.price);
        if (resistances.length > 0 && currentData.price > resistances[0].price && resistances[0].strength > 0.7) {
          return { invalidated: true, reason: `Price ${currentData.price} broke above key resistance at ${resistances[0].price}` };
        }
      }
      if (t.trend.direction === 'DOWNTREND' && thesis.signalBias === 'LONG_BIAS' && t.trend.strength > 0.7) {
        return { invalidated: true, reason: `Strong downtrend (${t.trend.strength.toFixed(2)}) contradicts long bias` };
      }
      if (t.trend.direction === 'UPTREND' && thesis.signalBias === 'SHORT_BIAS' && t.trend.strength > 0.7) {
        return { invalidated: true, reason: `Strong uptrend (${t.trend.strength.toFixed(2)}) contradicts short bias` };
      }
    }
    if (currentData.events?.contradictionDetected && thesis.confidence < 0.3) {
      return { invalidated: true, reason: 'Event contradictions with low confidence' };
    }
    return { invalidated: false };
  }

  expireStale(theses: readonly TradingThesis[]): readonly TradingThesis[] {
    const ts = nowIso();
    return theses.map((thesis) => {
      if (thesis.status !== 'ACTIVE') return thesis;
      if (thesis.expiresAt && Date.now() > new Date(thesis.expiresAt).getTime()) {
        return { ...thesis, status: 'EXPIRED' as ThesisStatus, updatedAt: ts,
          auditTrail: [...thesis.auditTrail, { timestamp: ts, action: 'SUPERSEDED', reason: 'Thesis expired', previousVersion: thesis.version }] };
      }
      const maxAgeMs = THESIS_STALE_HOURS[thesis.timeHorizon] * 3600_000;
      if (Date.now() - new Date(thesis.createdAt).getTime() > maxAgeMs) {
        return { ...thesis, status: 'STALE' as ThesisStatus, updatedAt: ts,
          auditTrail: [...thesis.auditTrail, { timestamp: ts, action: 'REASSESS_REQUIRED',
            reason: `Thesis age exceeds ${THESIS_STALE_HOURS[thesis.timeHorizon]}h for ${thesis.timeHorizon}`, previousVersion: thesis.version }] };
      }
      return thesis;
    });
  }

  buildExplanation(thesis: TradingThesis): string {
    const L: string[] = [];
    L.push(`=== Trading Thesis: ${thesis.symbol} (v${thesis.version}) ===`);
    L.push(`Status: ${thesis.status} | Horizon: ${thesis.timeHorizon}`);
    L.push(`Signal: ${thesis.signalBias} (strength ${thesis.signalStrength.toFixed(2)}, confidence ${thesis.confidence.toFixed(2)})`);
    L.push('', 'Market Context:', `  ${thesis.marketContext}`, '');
    if (thesis.technicalContext) L.push('Technical Context:', `  ${thesis.technicalContext}`, '');
    if (thesis.fundamentalContext) L.push('Fundamental Context:', `  ${thesis.fundamentalContext}`, '');
    if (thesis.eventContext) L.push('Event Context:', `  ${thesis.eventContext}`, '');
    L.push('Bull Case:', `  ${thesis.bullCase}`, '', 'Bear Case:', `  ${thesis.bearCase}`, '', 'Base Case:', `  ${thesis.baseCase}`, '');
    if (thesis.keyCatalysts.length > 0) { L.push('Key Catalysts:'); for (const c of thesis.keyCatalysts) L.push(`  - ${c}`); L.push(''); }
    if (thesis.keyRisks.length > 0) { L.push('Key Risks:'); for (const r of thesis.keyRisks) L.push(`  - ${r}`); L.push(''); }
    if (thesis.invalidationConditions.length > 0) { L.push('Invalidation Conditions:'); for (const ic of thesis.invalidationConditions) L.push(`  - ${ic}`); L.push(''); }
    const risk = thesis.riskAssessment;
    L.push(`Risk: ${risk.overallRisk} | Max drawdown: ${risk.maxDrawdownScenario !== undefined ? `${(risk.maxDrawdownScenario * 100).toFixed(1)}%` : 'N/A'}`);
    return L.join('\n');
  }

  private buildMarketContext(p: MarketSnapshot, regime?: MarketRegime, macro?: MacroContext): string {
    const parts = [`${p.symbol} at ${p.price} (${p.changePercent >= 0 ? '+' : ''}${p.changePercent.toFixed(2)}%)`,
      `Day range: ${p.dayLow} - ${p.dayHigh}`];
    if (p.fiftyTwoWeekHigh !== undefined && p.fiftyTwoWeekLow !== undefined) {
      const range = p.fiftyTwoWeekHigh - p.fiftyTwoWeekLow;
      parts.push(`52-week position: ${range > 0 ? ((p.price - p.fiftyTwoWeekLow) / range * 100).toFixed(0) : '50'}%`);
    }
    if (regime) parts.push(`Regime: ${regime.type} (${regime.confidence.toFixed(2)})`);
    if (macro?.riskSentiment) parts.push(`Macro: ${macro.riskSentiment}`);
    return parts.join('. ') + '.';
  }

  private buildTechnicalContext(t?: TechnicalAnalysis): string {
    if (!t) return 'Technical analysis not available.';
    const parts = [`Trend: ${t.trend.direction} (${t.trend.strength.toFixed(2)})`,
      `Signal: ${t.signal} (${t.signalStrength.toFixed(2)})`,
      `Volatility: ${t.volatility.regime} (ATR ${t.volatility.atr14.toFixed(2)})`,
      `Volume: ${t.volume.significance.toLowerCase()} (${t.volume.relativeVolume.toFixed(2)}x)`];
    if (t.indicators.rsi14) parts.push(`RSI: ${t.indicators.rsi14.value.toFixed(1)}`);
    if (t.indicators.macd) parts.push(`MACD: ${t.indicators.macd.macd.toFixed(3)}/${t.indicators.macd.signal.toFixed(3)}`);
    return parts.join('. ') + '.';
  }

  private buildFundamentalContext(f?: FundamentalAnalysis): string {
    if (!f) return 'Fundamental analysis not available.';
    const parts = [`Valuation: ${f.valuationAssessment}`, `Growth: ${f.growthAssessment}`,
      `Health: ${f.financialHealth}`, `Quality: ${f.qualityScore.toFixed(2)}`];
    if (f.metrics.pe !== undefined) parts.push(`P/E: ${f.metrics.pe.toFixed(1)}`);
    if (f.metrics.eps !== undefined) parts.push(`EPS: ${f.metrics.eps.toFixed(2)}`);
    return parts.join('. ') + '.';
  }

  private buildEventContext(e?: EventAnalysis): string {
    if (!e) return 'Event analysis not available.';
    const parts = [`Sentiment: ${e.overallSentiment} (${e.sentimentScore.toFixed(2)})`, `Type: ${e.eventClassification}`];
    if (e.upcomingCatalysts.length > 0) parts.push(`${e.upcomingCatalysts.length} upcoming catalyst(s)`);
    if (e.contradictionDetected) parts.push('Contradictory signals');
    return parts.join('. ') + '.';
  }

  private buildMacroContext(m?: MacroContext): string {
    if (!m) return 'Macro context not available.';
    const parts = [`Sentiment: ${m.riskSentiment}`];
    if (m.inflationTrend) parts.push(`Inflation: ${m.inflationTrend}`);
    if (m.rateEnvironment) parts.push(`Rates: ${m.rateEnvironment}`);
    if (m.usdStrength) parts.push(`USD: ${m.usdStrength}`);
    return parts.join('. ') + '.';
  }

  private computeExpiry(timeHorizon: TimeHorizon, createdAt: string): string {
    return new Date(new Date(createdAt).getTime() + THESIS_STALE_HOURS[timeHorizon] * 3600_000).toISOString();
  }
}
