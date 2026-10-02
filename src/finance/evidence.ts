import type {
  EvidenceMatrix,
  EvidenceEntry,
  EvidenceCategory,
  TechnicalAnalysis,
  FundamentalAnalysis,
  EventAnalysis,
  MacroContext,
  MarketRegime,
  SectorAnalysis,
  SignalBias,
  Freshness,
  DataQuality,
} from './contracts';

const FRESHNESS_ORDER: Record<Freshness, number> = {
  REALTIME: 0, NEAR_REALTIME: 1, DELAYED: 2, END_OF_DAY: 3,
  HISTORICAL: 4, STALE: 5, UNAVAILABLE: 6,
};

const CATEGORY_WEIGHTS: Record<EvidenceCategory, number> = {
  TECHNICAL: 0.25, FUNDAMENTAL: 0.20, EVENT: 0.15, MACRO: 0.10,
  SENTIMENT: 0.10, REGIME: 0.10, SECTOR: 0.05, CROSS_ASSET: 0.05,
};

let entryCounter = 0;
const nextId = () => `ev-${Date.now()}-${++entryCounter}`;

export class EvidenceMatrixEngine {
  private readonly source = 'EvidenceMatrixEngine';

  buildMatrix(params: {
    technical?: TechnicalAnalysis; fundamental?: FundamentalAnalysis;
    events?: EventAnalysis; macro?: MacroContext; regime?: MarketRegime;
    sector?: SectorAnalysis; symbol: string; assetId: string;
  }): EvidenceMatrix {
    const entries: EvidenceEntry[] = [];
    const { technical, fundamental, events, macro, regime, sector, symbol, assetId } = params;

    if (technical) {
      const ts = technical.timestamp;
      entries.push(this.entry('TECHNICAL', `Trend direction is ${technical.trend.direction}`,
        technical.trend.direction === 'UPTREND' ? 'BULLISH' : technical.trend.direction === 'DOWNTREND' ? 'BEARISH' : 'NEUTRAL',
        technical.trend.strength / 100, technical.timeframe === '1d' ? 'NEAR_REALTIME' : 'END_OF_DAY', 0.85,
        `Technical trend (${technical.timeframe})`, ts));

      if (technical.indicators.rsi14) {
        const rsi = technical.indicators.rsi14.value;
        entries.push(this.entry('TECHNICAL',
          `RSI(14) at ${rsi.toFixed(1)} — ${rsi > 70 ? 'overbought' : rsi < 30 ? 'oversold' : 'neutral'}`,
          rsi > 70 ? 'BEARISH' : rsi < 30 ? 'BULLISH' : 'NEUTRAL',
          rsi > 70 || rsi < 30 ? 0.7 : 0.3, 'NEAR_REALTIME', 0.8, `RSI(14) = ${rsi.toFixed(1)}`, ts));
      }

      if (technical.indicators.macd) {
        const m = technical.indicators.macd;
        entries.push(this.entry('TECHNICAL',
          `MACD ${m.histogram > 0 ? 'bullish' : 'bearish'} crossover (histogram: ${m.histogram.toFixed(3)})`,
          m.histogram > 0 ? 'BULLISH' : m.histogram < 0 ? 'BEARISH' : 'NEUTRAL',
          Math.min(1, Math.abs(m.histogram) / 2), 'NEAR_REALTIME', 0.75, 'MACD signal', ts));
      }

      if (technical.volume.relativeVolume > 1.5) {
        entries.push(this.entry('TECHNICAL',
          `Relative volume ${technical.volume.relativeVolume.toFixed(1)}x — ${technical.volume.trend.toLowerCase()} volume`,
          technical.trend.direction === 'UPTREND' ? 'BULLISH' : 'BEARISH',
          0.6, 'NEAR_REALTIME', 0.7, 'Volume analysis', ts));
      }

      if (technical.signal !== 'NO_SIGNAL' && technical.signal !== 'WATCH') {
        entries.push(this.entry('TECHNICAL',
          `Technical signal: ${technical.signal} (strength: ${technical.signalStrength.toFixed(2)})`,
          technical.signal === 'LONG_BIAS' ? 'BULLISH' : technical.signal === 'SHORT_BIAS' ? 'BEARISH' : 'NEUTRAL',
          technical.signalStrength, technical.timeframe === '1d' ? 'NEAR_REALTIME' : 'END_OF_DAY', 0.9,
          'Technical composite signal', ts));
      }
    }

    if (fundamental) {
      const ts = fundamental.timestamp;
      if (fundamental.valuationAssessment !== 'UNKNOWN') {
        entries.push(this.entry('FUNDAMENTAL', `Valuation: ${fundamental.valuationAssessment.toLowerCase()}`,
          fundamental.valuationAssessment === 'UNDERVALUED' ? 'BULLISH' : fundamental.valuationAssessment === 'OVERVALUED' ? 'BEARISH' : 'NEUTRAL',
          fundamental.qualityScore / 100, fundamental.dataQuality === 'COMPLETE' ? 'END_OF_DAY' : 'DELAYED', 0.8,
          'Fundamental valuation', ts));
      }
      if (fundamental.growthAssessment !== 'UNKNOWN') {
        entries.push(this.entry('FUNDAMENTAL', `Growth: ${fundamental.growthAssessment.replace('_', ' ').toLowerCase()}`,
          fundamental.growthAssessment === 'HIGH_GROWTH' ? 'BULLISH' : fundamental.growthAssessment === 'DECLINE' ? 'BEARISH' : 'NEUTRAL',
          0.65, fundamental.dataQuality === 'COMPLETE' ? 'END_OF_DAY' : 'DELAYED', 0.7, 'Growth assessment', ts));
      }
      if (fundamental.financialHealth !== 'UNKNOWN') {
        entries.push(this.entry('FUNDAMENTAL', `Financial health: ${fundamental.financialHealth.toLowerCase()}`,
          fundamental.financialHealth === 'STRONG' ? 'BULLISH' : fundamental.financialHealth === 'WEAK' || fundamental.financialHealth === 'CRITICAL' ? 'BEARISH' : 'NEUTRAL',
          fundamental.financialHealth === 'STRONG' ? 0.7 : fundamental.financialHealth === 'CRITICAL' ? 0.8 : 0.4,
          fundamental.dataQuality === 'COMPLETE' ? 'END_OF_DAY' : 'DELAYED', 0.75, 'Financial health', ts));
      }
      if (fundamental.metrics.epsSurprise !== undefined && fundamental.metrics.epsSurprise !== 0) {
        entries.push(this.entry('FUNDAMENTAL',
          `EPS surprise: ${fundamental.metrics.epsSurprise > 0 ? '+' : ''}${fundamental.metrics.epsSurprise.toFixed(2)}`,
          fundamental.metrics.epsSurprise > 0 ? 'BULLISH' : 'BEARISH',
          Math.min(1, Math.abs(fundamental.metrics.epsSurprise) / 5), 'END_OF_DAY', 0.85,
          `EPS surprise ${fundamental.metrics.period}`, ts));
      }
    }

    if (events) {
      const ts = events.timestamp;
      const sentDir = events.overallSentiment === 'VERY_BULLISH' || events.overallSentiment === 'BULLISH' ? 'BULLISH'
        : events.overallSentiment === 'BEARISH' || events.overallSentiment === 'VERY_BEARISH' ? 'BEARISH' : 'NEUTRAL';

      entries.push(this.entry('EVENT',
        `News sentiment: ${events.overallSentiment.replace('_', ' ').toLowerCase()} (score: ${events.sentimentScore.toFixed(2)})`,
        sentDir, Math.abs(events.sentimentScore), events.newsFreshness, 0.7, 'News sentiment aggregate', ts));

      const highImpact = events.recentNews.filter((n) => n.importance === 'HIGH');
      if (highImpact.length > 0) {
        const avg = highImpact.reduce((s, n) => s + n.sentimentScore, 0) / highImpact.length;
        entries.push(this.entry('EVENT', `${highImpact.length} high-impact news (avg sentiment: ${avg.toFixed(2)})`,
          avg > 0.1 ? 'BULLISH' : avg < -0.1 ? 'BEARISH' : 'NEUTRAL',
          Math.abs(avg) * 0.8, events.newsFreshness, 0.8, 'High-impact news', ts));
      }
      if (events.contradictionDetected) {
        entries.push(this.entry('EVENT', 'Contradictory news signals — reduced confidence',
          'NEUTRAL', 0.3, events.newsFreshness, 0.6, 'News contradiction', ts));
      }
    }

    if (macro) {
      const riskDir = macro.riskSentiment === 'RISK_ON' ? 'BULLISH' : macro.riskSentiment === 'RISK_OFF' ? 'BEARISH' : 'NEUTRAL';
      entries.push(this.entry('MACRO', `Macro risk sentiment: ${macro.riskSentiment.replace('_', ' ').toLowerCase()}`,
        riskDir, macro.evidence.length > 0 ? 0.7 : 0.4, 'END_OF_DAY', 0.7, 'Macro risk sentiment', macro.timestamp));
      if (macro.rateEnvironment) {
        entries.push(this.entry('MACRO', `Rate environment: ${macro.rateEnvironment.toLowerCase()}`,
          macro.rateEnvironment === 'DOVISH' ? 'BULLISH' : macro.rateEnvironment === 'HAWKISH' ? 'BEARISH' : 'NEUTRAL',
          0.6, 'END_OF_DAY', 0.65, 'Rate environment', macro.timestamp));
      }
    }

    if (regime) {
      const regimeDir: Record<string, 'BULLISH' | 'BEARISH' | 'NEUTRAL'> = {
        TRENDING_BULL: 'BULLISH', TRENDING_BEAR: 'BEARISH', RANGE: 'NEUTRAL',
        HIGH_VOLATILITY: 'BEARISH', LOW_VOLATILITY: 'BULLISH', RISK_ON: 'BULLISH',
        RISK_OFF: 'BEARISH', MIXED: 'NEUTRAL', UNKNOWN: 'NEUTRAL',
      };
      entries.push(this.entry('REGIME',
        `Market regime: ${regime.type.replace('_', ' ').toLowerCase()} (confidence: ${(regime.confidence * 100).toFixed(0)}%)`,
        regimeDir[regime.type] ?? 'NEUTRAL', regime.confidence * 0.7, 'END_OF_DAY', 0.75, 'Regime classification', regime.timestamp));
    }

    if (sector) {
      entries.push(this.entry('SECTOR',
        `Sector ${sector.sector}: RS ${sector.relativeStrength > 0 ? '+' : ''}${sector.relativeStrength.toFixed(2)}%`,
        sector.relativeStrength > 1 ? 'BULLISH' : sector.relativeStrength < -1 ? 'BEARISH' : 'NEUTRAL',
        Math.min(1, Math.abs(sector.relativeStrength) / 5), 'END_OF_DAY', 0.6, `Sector ${sector.sector}`,
        new Date().toISOString()));
    }

    const deduped = this.deduplicate(entries);
    const ranked = this.rankEvidence(deduped);
    const bullishCount = ranked.filter((e) => e.direction === 'BULLISH').length;
    const bearishCount = ranked.filter((e) => e.direction === 'BEARISH').length;
    const neutralCount = ranked.filter((e) => e.direction === 'NEUTRAL').length;
    const contradictions = this.detectContradictions(ranked);

    return {
      assetId, symbol, timestamp: new Date().toISOString(),
      entries: ranked, bullishCount, bearishCount, neutralCount, contradictions,
      overallDirection: this.determineOverallDirection(bullishCount, bearishCount, neutralCount, contradictions.length),
      confidence: this.computeConfidence(ranked),
      dataQuality: this.inferDataQuality(ranked),
    };
  }

  detectContradictions(entries: readonly EvidenceEntry[]): readonly { claim1: string; claim2: string; reason: string }[] {
    const results: { claim1: string; claim2: string; reason: string }[] = [];
    const strongBull = entries.filter((e) => e.direction === 'BULLISH' && e.support > 0.5);
    const strongBear = entries.filter((e) => e.direction === 'BEARISH' && e.support > 0.5);
    if (strongBull.length === 0 || strongBear.length === 0) return results;

    const categories = Array.from(new Set(entries.map((e) => e.category)));
    for (const cat of categories) {
      const catBull = strongBull.filter((e) => e.category === cat);
      const catBear = strongBear.filter((e) => e.category === cat);
      for (const b of catBull) {
        for (const s of catBear) {
          results.push({
            claim1: b.claim, claim2: s.claim,
            reason: `${cat} has conflicting signals: bullish ${(b.support * 100).toFixed(0)}% vs bearish ${(s.support * 100).toFixed(0)}%`,
          });
        }
      }
    }
    if (results.length === 0) {
      results.push({
        claim1: strongBull[0].claim, claim2: strongBear[0].claim,
        reason: `Strong ${strongBull[0].category} bullish conflicts with strong ${strongBear[0].category} bearish`,
      });
    }
    return results;
  }

  computeConfidence(entries: readonly EvidenceEntry[]): number {
    if (entries.length === 0) return 0;
    let totalWeight = 0;
    let weightedSum = 0;
    for (const e of entries) {
      const catWeight = CATEGORY_WEIGHTS[e.category] ?? 0.05;
      const penalty = FRESHNESS_ORDER[e.freshness] * 0.05;
      const effectiveConf = Math.max(0, e.confidence - penalty);
      const weight = catWeight * e.sourceQuality;
      totalWeight += weight;
      weightedSum += weight * effectiveConf;
    }
    return totalWeight > 0 ? Math.min(1, weightedSum / totalWeight) : 0;
  }

  determineOverallDirection(bullish: number, bearish: number, neutral: number, contradictions: number): SignalBias {
    const total = bullish + bearish + neutral;
    if (total === 0) return 'NO_SIGNAL';
    const bullRatio = bullish / total;
    const bearRatio = bearish / total;
    const penalty = Math.min(0.3, contradictions * 0.1);
    if (bullRatio > 0.6 && bullRatio - penalty > 0.4) return 'LONG_BIAS';
    if (bearRatio > 0.6 && bearRatio - penalty > 0.4) return 'SHORT_BIAS';
    if (contradictions > 2) return 'WATCH';
    if (bullRatio < 0.3 && bearRatio < 0.3) return 'NEUTRAL';
    return 'WATCH';
  }

  rankEvidence(entries: readonly EvidenceEntry[]): readonly EvidenceEntry[] {
    return [...entries].sort((a, b) => {
      const cd = b.confidence - a.confidence;
      if (Math.abs(cd) > 0.01) return cd;
      const fd = FRESHNESS_ORDER[a.freshness] - FRESHNESS_ORDER[b.freshness];
      if (fd !== 0) return fd;
      return b.sourceQuality - a.sourceQuality;
    });
  }

  filterByFreshness(entries: readonly EvidenceEntry[], maxAge: Freshness): readonly EvidenceEntry[] {
    const maxOrder = FRESHNESS_ORDER[maxAge];
    return entries.filter((e) => FRESHNESS_ORDER[e.freshness] <= maxOrder);
  }

  buildExplanation(matrix: EvidenceMatrix): string {
    const { symbol, overallDirection, confidence, bullishCount, bearishCount, neutralCount, contradictions, entries } = matrix;
    const parts: string[] = [
      `${symbol} analysis: ${overallDirection.replace('_', ' ').toLowerCase()} signal.`,
      `Evidence: ${bullishCount} bullish, ${bearishCount} bearish, ${neutralCount} neutral.`,
      `Confidence: ${(confidence * 100).toFixed(0)}%.`,
    ];
    if (contradictions.length > 0) parts.push(`${contradictions.length} contradiction(s) — treat with caution.`);
    const topBull = entries.filter((e) => e.direction === 'BULLISH').slice(0, 3);
    if (topBull.length > 0) parts.push(`Key bullish drivers: ${topBull.map((e) => e.claim).join('; ')}.`);
    const topBear = entries.filter((e) => e.direction === 'BEARISH').slice(0, 3);
    if (topBear.length > 0) parts.push(`Key bearish risks: ${topBear.map((e) => e.claim).join('; ')}.`);
    const cats = Array.from(new Set(entries.map((e) => e.category)));
    const catSummary = cats.map((cat) => {
      const ce = entries.filter((e) => e.category === cat);
      return `${cat.toLowerCase()}: ${ce.filter((e) => e.direction === 'BULLISH').length}B/${ce.filter((e) => e.direction === 'BEARISH').length}S`;
    });
    parts.push(`Category breakdown: ${catSummary.join(', ')}.`);
    return parts.join(' ');
  }

  private entry(
    category: EvidenceCategory, claim: string,
    direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL', support: number,
    freshness: Freshness, sourceQuality: number, source: string, timestamp: string,
  ): EvidenceEntry {
    return {
      id: nextId(), category, claim, direction,
      support: Math.max(0, Math.min(1, support)), contradiction: 0,
      freshness, sourceQuality: Math.max(0, Math.min(1, sourceQuality)),
      confidence: Math.max(0, Math.min(1, support * sourceQuality)),
      source, timestamp,
    };
  }

  private deduplicate(entries: readonly EvidenceEntry[]): readonly EvidenceEntry[] {
    const seen = new Set<string>();
    return entries.filter((e) => {
      const key = `${e.category}|${e.source}|${e.direction}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  private inferDataQuality(entries: readonly EvidenceEntry[]): DataQuality {
    if (entries.length === 0) return 'UNKNOWN';
    const freshCount = entries.filter((e) => FRESHNESS_ORDER[e.freshness] <= FRESHNESS_ORDER.END_OF_DAY).length;
    const ratio = freshCount / entries.length;
    if (ratio > 0.8) return 'COMPLETE';
    if (ratio > 0.5) return 'PARTIAL';
    if (ratio > 0.2) return 'SPARSE';
    return 'UNKNOWN';
  }
}
