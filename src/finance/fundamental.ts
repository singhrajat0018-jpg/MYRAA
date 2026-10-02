// ============================================================================
// MYRAA Phase 26 — Fundamental Analysis Engine
// ============================================================================

import type {
  FinancialMetrics,
  EarningsEvent,
  FundamentalAnalysis,
  PeerComparison,
  DataQuality,
} from './contracts';

function safeNum(v: number | undefined, fallback = 0): number {
  return v != null && Number.isFinite(v) ? v : fallback;
}

function hasVal(v: number | undefined): v is number {
  return v != null && Number.isFinite(v);
}

function nowIso(): string {
  return new Date().toISOString();
}

function dataQualityOf(m: FinancialMetrics): DataQuality {
  const fields = [
    m.revenue, m.eps, m.grossMargin, m.operatingMargin, m.netMargin,
    m.freeCashFlow, m.totalDebt, m.totalCash, m.debtToEquity,
    m.currentRatio, m.roe, m.pe, m.ps, m.evToEbitda,
  ];
  const filled = fields.filter((f) => hasVal(f)).length;
  const ratio = filled / fields.length;
  if (ratio >= 0.75) return 'COMPLETE';
  if (ratio >= 0.4) return 'PARTIAL';
  if (ratio >= 0.15) return 'SPARSE';
  return 'UNKNOWN';
}

function avg(vals: readonly number[]): number {
  if (vals.length === 0) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function median(vals: readonly number[]): number {
  if (vals.length === 0) return 0;
  const sorted = [...vals].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function percentileRank(value: number, peers: readonly number[]): number {
  if (peers.length === 0) return 50;
  const below = peers.filter((p) => p < value).length;
  return Math.round((below / peers.length) * 100);
}

function clampScore(v: number): number {
  return Math.max(0, Math.min(1, v));
}

export class FundamentalAnalysisEngine {
  // --- Valuation Assessment ---

  assessValuation(
    metrics: FinancialMetrics,
    peerMetrics?: readonly FinancialMetrics[],
  ): 'UNDERVALUED' | 'FAIR' | 'OVERVALUED' | 'UNKNOWN' {
    const scores: number[] = [];

    // P/E ratio assessment
    if (hasVal(metrics.pe) && metrics.pe! > 0) {
      if (peerMetrics && peerMetrics.length > 0) {
        const peerPEs = peerMetrics.filter((p) => hasVal(p.pe) && p.pe! > 0).map((p) => p.pe!);
        if (peerPEs.length > 0) {
          const peerMedian = median(peerPEs);
          const ratio = metrics.pe! / peerMedian;
          if (ratio < 0.75) scores.push(0.9);
          else if (ratio < 0.9) scores.push(0.7);
          else if (ratio < 1.1) scores.push(0.5);
          else if (ratio < 1.3) scores.push(0.3);
          else scores.push(0.1);
        }
      } else {
        // Heuristic: P/E < 15 cheap, 15-25 fair, > 25 expensive
        if (metrics.pe! < 10) scores.push(0.9);
        else if (metrics.pe! < 15) scores.push(0.7);
        else if (metrics.pe! < 25) scores.push(0.5);
        else if (metrics.pe! < 35) scores.push(0.3);
        else scores.push(0.1);
      }
    }

    // P/S ratio assessment
    if (hasVal(metrics.ps) && metrics.ps! > 0) {
      if (peerMetrics && peerMetrics.length > 0) {
        const peerPS = peerMetrics.filter((p) => hasVal(p.ps) && p.ps! > 0).map((p) => p.ps!);
        if (peerPS.length > 0) {
          const peerMed = median(peerPS);
          const ratio = metrics.ps! / peerMed;
          if (ratio < 0.7) scores.push(0.85);
          else if (ratio < 0.9) scores.push(0.65);
          else if (ratio < 1.1) scores.push(0.5);
          else if (ratio < 1.4) scores.push(0.35);
          else scores.push(0.15);
        }
      } else {
        if (metrics.ps! < 2) scores.push(0.8);
        else if (metrics.ps! < 4) scores.push(0.5);
        else scores.push(0.2);
      }
    }

    // EV/EBITDA assessment
    if (hasVal(metrics.evToEbitda) && metrics.evToEbitda! > 0) {
      if (peerMetrics && peerMetrics.length > 0) {
        const peerEVE = peerMetrics
          .filter((p) => hasVal(p.evToEbitda) && p.evToEbitda! > 0)
          .map((p) => p.evToEbitda!);
        if (peerEVE.length > 0) {
          const peerMed = median(peerEVE);
          const ratio = metrics.evToEbitda! / peerMed;
          if (ratio < 0.75) scores.push(0.85);
          else if (ratio < 0.9) scores.push(0.65);
          else if (ratio < 1.1) scores.push(0.5);
          else if (ratio < 1.3) scores.push(0.35);
          else scores.push(0.15);
        }
      } else {
        if (metrics.evToEbitda! < 8) scores.push(0.8);
        else if (metrics.evToEbitda! < 15) scores.push(0.5);
        else scores.push(0.2);
      }
    }

    if (scores.length === 0) return 'UNKNOWN';

    const composite = avg(scores);
    if (composite >= 0.65) return 'UNDERVALUED';
    if (composite >= 0.4) return 'FAIR';
    return 'OVERVALUED';
  }

  // --- Growth Assessment ---

  assessGrowth(metrics: FinancialMetrics): 'HIGH_GROWTH' | 'MODERATE_GROWTH' | 'LOW_GROWTH' | 'DECLINE' | 'UNKNOWN' {
    const growths: number[] = [];

    if (hasVal(metrics.revenueGrowthYoy)) growths.push(metrics.revenueGrowthYoy!);
    if (hasVal(metrics.revenueGrowthQoQ)) growths.push(metrics.revenueGrowthQoQ!);

    // If we have EPS growth estimate from earnings surprises, factor it in
    if (hasVal(metrics.epsSurprise) && hasVal(metrics.eps) && metrics.eps! > 0) {
      // epsSurprise is in percentage terms; positive surprise hints at growth
      // but it's not direct growth. Skip to avoid misleading signal.
    }

    if (growths.length === 0) return 'UNKNOWN';

    const avgGrowth = avg(growths);

    if (avgGrowth >= 20) return 'HIGH_GROWTH';
    if (avgGrowth >= 5) return 'MODERATE_GROWTH';
    if (avgGrowth >= 0) return 'LOW_GROWTH';
    return 'DECLINE';
  }

  // --- Financial Health ---

  assessFinancialHealth(metrics: FinancialMetrics): 'STRONG' | 'ADEQUATE' | 'WEAK' | 'CRITICAL' | 'UNKNOWN' {
    let score = 0;
    let factors = 0;

    // Debt-to-equity: lower is healthier
    if (hasVal(metrics.debtToEquity)) {
      const dte = metrics.debtToEquity!;
      if (dte < 0.3) score += 1.0;
      else if (dte < 0.6) score += 0.75;
      else if (dte < 1.0) score += 0.5;
      else if (dte < 2.0) score += 0.25;
      else score += 0;
      factors++;
    }

    // Current ratio: > 1.5 strong, > 1.0 adequate
    if (hasVal(metrics.currentRatio)) {
      const cr = metrics.currentRatio!;
      if (cr >= 2.0) score += 1.0;
      else if (cr >= 1.5) score += 0.8;
      else if (cr >= 1.0) score += 0.5;
      else if (cr >= 0.7) score += 0.25;
      else score += 0;
      factors++;
    }

    // Cash position: total cash / total debt
    if (hasVal(metrics.totalCash) && hasVal(metrics.totalDebt) && metrics.totalDebt! > 0) {
      const cashRatio = metrics.totalCash! / metrics.totalDebt!;
      if (cashRatio >= 1.5) score += 1.0;
      else if (cashRatio >= 1.0) score += 0.75;
      else if (cashRatio >= 0.5) score += 0.5;
      else if (cashRatio >= 0.2) score += 0.25;
      else score += 0;
      factors++;
    }

    // Operating cash flow positive
    if (hasVal(metrics.operatingCashFlow)) {
      if (metrics.operatingCashFlow! > 0) score += 0.8;
      else score += 0.1;
      factors++;
    }

    // FCF positive
    if (hasVal(metrics.freeCashFlow)) {
      if (metrics.freeCashFlow! > 0) score += 0.7;
      else score += 0.15;
      factors++;
    }

    if (factors === 0) return 'UNKNOWN';

    const avgScore = score / factors;
    if (avgScore >= 0.75) return 'STRONG';
    if (avgScore >= 0.5) return 'ADEQUATE';
    if (avgScore >= 0.25) return 'WEAK';
    return 'CRITICAL';
  }

  // --- Quality Score ---

  computeQualityScore(metrics: FinancialMetrics): number {
    let total = 0;
    let weights = 0;

    // Gross margin (weight 0.15)
    if (hasVal(metrics.grossMargin)) {
      const gm = metrics.grossMargin!;
      total += clampScore(gm / 60) * 0.15;
      weights += 0.15;
    }

    // Operating margin (weight 0.2)
    if (hasVal(metrics.operatingMargin)) {
      const om = metrics.operatingMargin!;
      total += clampScore((om + 5) / 35) * 0.2;
      weights += 0.2;
    }

    // Net margin (weight 0.15)
    if (hasVal(metrics.netMargin)) {
      const nm = metrics.netMargin!;
      total += clampScore((nm + 5) / 30) * 0.15;
      weights += 0.15;
    }

    // ROE (weight 0.2)
    if (hasVal(metrics.roe)) {
      const roe = metrics.roe!;
      total += clampScore(roe / 25) * 0.2;
      weights += 0.2;
    }

    // Free cash flow relative to revenue (weight 0.15)
    if (hasVal(metrics.freeCashFlow) && hasVal(metrics.revenue) && metrics.revenue! > 0) {
      const fcfMargin = metrics.freeCashFlow! / metrics.revenue!;
      total += clampScore((fcfMargin + 0.05) / 0.25) * 0.15;
      weights += 0.15;
    }

    // Growth component (weight 0.15)
    if (hasVal(metrics.revenueGrowthYoy)) {
      const g = metrics.revenueGrowthYoy!;
      total += clampScore((g + 10) / 40) * 0.15;
      weights += 0.15;
    }

    if (weights === 0) return 0;
    return Math.round((total / weights) * 100) / 100;
  }

  // --- Peer Comparison ---

  comparePeers(metrics: FinancialMetrics, peers: readonly FinancialMetrics[]): PeerComparison {
    if (peers.length === 0) {
      return { peers: [] };
    }

    const symbols = peers.map((p) => p.source || 'peer');

    const peVals = [metrics, ...peers]
      .filter((m) => hasVal(m.pe) && m.pe! > 0)
      .map((m) => ({ src: m.source, val: m.pe! }));

    const growthVals = [metrics, ...peers]
      .filter((m) => hasVal(m.revenueGrowthYoy))
      .map((m) => ({ src: m.source, val: m.revenueGrowthYoy! }));

    const marginVals = [metrics, ...peers]
      .filter((m) => hasVal(m.operatingMargin))
      .map((m) => ({ src: m.source, val: m.operatingMargin! }));

    function rank(vals: readonly { src: string; val: number }[], metric: string): number | undefined {
      if (vals.length < 2) return undefined;
      // For valuation metrics (P/E, P/S), lower is better → rank 1 = lowest
      // For growth/margin, higher is better → rank 1 = highest
      const lowerBetter = metric === 'pe' || metric === 'ps' || metric === 'evToEbitda';
      const sorted = [...vals].sort((a, b) => lowerBetter ? a.val - b.val : b.val - a.val);
      const idx = sorted.findIndex((v) => v.src === metrics.source);
      return idx >= 0 ? idx + 1 : undefined;
    }

    const peRank = rank(peVals, 'pe');
    const growthRank = rank(growthVals, 'growth');
    const marginRank = rank(marginVals, 'margin');

    // Health rank: composite of D/E and current ratio (lower D/E + higher CR = better)
    const healthVals = [metrics, ...peers]
      .map((m) => {
        let score = 50;
        if (hasVal(m.debtToEquity)) score -= m.debtToEquity! * 15;
        if (hasVal(m.currentRatio)) score += m.currentRatio! * 10;
        return { src: m.source, val: score };
      });
    const healthRank = rank(healthVals, 'health');

    return {
      peers: symbols,
      peRank,
      growthRank,
      marginRank,
      healthRank,
    };
  }

  // --- Earnings Analysis ---

  analyzeEarnings(earnings: readonly EarningsEvent[]): {
    trend: string;
    surprisePattern: string;
    upcomingRisk: boolean;
  } {
    if (earnings.length === 0) {
      return { trend: 'NO_DATA', surprisePattern: 'NO_DATA', upcomingRisk: false };
    }

    const sorted = [...earnings].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );

    // Trend: compare consecutive EPS surprises
    const surprises = sorted
      .filter((e) => hasVal(e.epsSurprisePercent))
      .map((e) => e.epsSurprisePercent!);

    let trend = 'INSUFFICIENT_DATA';
    if (surprises.length >= 3) {
      const recentHalf = surprises.slice(Math.floor(surprises.length / 2));
      const olderHalf = surprises.slice(0, Math.floor(surprises.length / 2));
      const recentAvg = avg(recentHalf);
      const olderAvg = avg(olderHalf);
      const improving = recentAvg > olderAvg;

      const allPositive = recentHalf.every((s) => s > 0);
      const allNegative = recentHalf.every((s) => s < 0);

      if (allPositive && improving) trend = 'IMPROVING_BEATS';
      else if (allPositive) trend = 'CONSISTENT_BEATS';
      else if (allNegative && !improving) trend = 'DETERIORATING_MISSES';
      else if (allNegative) trend = 'CONSISTENT_MISSES';
      else if (improving) trend = 'IMPROVING';
      else trend = 'MIXED';
    } else if (surprises.length >= 1) {
      const recent = surprises[surprises.length - 1];
      trend = recent > 0 ? 'RECENT_BEAT' : recent < 0 ? 'RECENT_MISS' : 'INLINE';
    }

    // Surprise pattern
    let surprisePattern = 'NO_DATA';
    if (surprises.length >= 2) {
      const beats = surprises.filter((s) => s > 0).length;
      const misses = surprises.filter((s) => s < 0).length;
      const inline = surprises.length - beats - misses;
      const beatRate = beats / surprises.length;

      if (beatRate >= 0.75) surprisePattern = 'STRONG_BEAT_PATTERN';
      else if (beatRate >= 0.5) surprisePattern = 'MODERATE_BEAT_PATTERN';
      else if (misses / surprises.length >= 0.75) surprisePattern = 'MISS_PATTERN';
      else surprisePattern = 'MIXED_PATTERN';

      // Append average magnitude
      const avgSurprise = avg(surprises.map(Math.abs));
      surprisePattern += ` (avg |surprise|=${avgSurprise.toFixed(1)}%, beats=${beats}/${surprises.length})`;
    } else if (surprises.length === 1) {
      surprisePattern = surprises[0] > 0 ? 'SINGLE_BEAT' : 'SINGLE_MISS';
    }

    // Upcoming risk: any catalyst within 14 days
    const nowMs = Date.now();
    const fourteenDaysMs = 14 * 24 * 60 * 60 * 1000;
    const upcomingRisk = earnings.some((e) => {
      const d = new Date(e.date).getTime();
      return d >= nowMs && d <= nowMs + fourteenDaysMs;
    });

    return { trend, surprisePattern, upcomingRisk };
  }

  // --- Evidence Builder ---

  buildEvidence(analysis: FundamentalAnalysis): readonly string[] {
    const ev: string[] = [];

    if (analysis.valuationAssessment !== 'UNKNOWN') {
      ev.push(`Valuation: ${analysis.valuationAssessment}`);
    }

    if (analysis.growthAssessment !== 'UNKNOWN') {
      ev.push(`Growth profile: ${analysis.growthAssessment}`);
    }

    if (analysis.financialHealth !== 'UNKNOWN') {
      ev.push(`Financial health: ${analysis.financialHealth}`);
    }

    if (analysis.qualityScore > 0) {
      ev.push(`Quality score: ${analysis.qualityScore.toFixed(2)}`);
    }

    const m = analysis.metrics;
    if (hasVal(m.pe)) ev.push(`P/E: ${m.pe!.toFixed(1)}`);
    if (hasVal(m.forwardPE)) ev.push(`Forward P/E: ${m.forwardPE!.toFixed(1)}`);
    if (hasVal(m.ps)) ev.push(`P/S: ${m.ps!.toFixed(1)}`);
    if (hasVal(m.evToEbitda)) ev.push(`EV/EBITDA: ${m.evToEbitda!.toFixed(1)}`);
    if (hasVal(m.revenueGrowthYoy)) ev.push(`Revenue growth YoY: ${m.revenueGrowthYoy!.toFixed(1)}%`);
    if (hasVal(m.epsSurprise)) ev.push(`Last EPS surprise: ${m.epsSurprise!.toFixed(1)}%`);
    if (hasVal(m.debtToEquity)) ev.push(`Debt/Equity: ${m.debtToEquity!.toFixed(2)}`);
    if (hasVal(m.roe)) ev.push(`ROE: ${m.roe!.toFixed(1)}%`);
    if (hasVal(m.freeCashFlow)) ev.push(`Free cash flow: ${m.freeCashFlow! >= 0 ? 'positive' : 'negative'}`);

    if (analysis.peerComparison) {
      const pc = analysis.peerComparison;
      if (pc.peRank != null) ev.push(`P/E rank among ${pc.peers.length} peers: #${pc.peRank}`);
      if (pc.growthRank != null) ev.push(`Growth rank among ${pc.peers.length} peers: #${pc.growthRank}`);
    }

    if (analysis.dataQuality !== 'COMPLETE') {
      ev.push(`Data quality: ${analysis.dataQuality} — analysis may be incomplete`);
    }

    // Earnings events summary
    if (analysis.earnings.length > 0) {
      const sorted = [...analysis.earnings].sort(
        (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
      );
      const latest = sorted[0];
      if (hasVal(latest.epsSurprisePercent)) {
        ev.push(`Latest earnings (${latest.date}): EPS surprise ${latest.epsSurprisePercent!.toFixed(1)}%`);
      }
    }

    return ev;
  }

  // --- Main Analysis ---

  analyze(
    metrics: FinancialMetrics,
    earnings: readonly EarningsEvent[],
    peers?: readonly FinancialMetrics[],
  ): FundamentalAnalysis {
    const valuation = this.assessValuation(metrics, peers);
    const growth = this.assessGrowth(metrics);
    const health = this.assessFinancialHealth(metrics);
    const quality = this.computeQualityScore(metrics);
    const peerComp = peers && peers.length > 0 ? this.comparePeers(metrics, peers) : undefined;

    const analysis: FundamentalAnalysis = {
      assetId: metrics.source,
      symbol: metrics.source,
      timestamp: nowIso(),
      metrics,
      earnings,
      valuationAssessment: valuation,
      growthAssessment: growth,
      financialHealth: health,
      qualityScore: quality,
      peerComparison: peerComp,
      dataQuality: dataQualityOf(metrics),
      evidence: [],
    };

    return {
      ...analysis,
      evidence: this.buildEvidence(analysis),
    };
  }
}
