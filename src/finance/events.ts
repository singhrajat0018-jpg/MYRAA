// ============================================================================
// MYRAA Phase 26 — Event Analysis Engine
// ============================================================================

import type {
  NewsItem,
  Catalyst,
  EventAnalysis,
  SentimentLabel,
  Freshness,
  EventType,
} from './contracts';

function nowIso(): string {
  return new Date().toISOString();
}

function safeNum(v: number | undefined, fallback = 0): number {
  return v != null && Number.isFinite(v) ? v : fallback;
}

function hasVal(v: number | undefined): v is number {
  return v != null && Number.isFinite(v);
}

const SENTIMENT_SCORE_MAP: Record<SentimentLabel, number> = {
  VERY_BULLISH: 1.0,
  BULLISH: 0.5,
  NEUTRAL: 0.0,
  BEARISH: -0.5,
  VERY_BEARISH: -1.0,
};

const SENTIMENT_FROM_SCORE = (s: number): SentimentLabel => {
  if (s >= 0.6) return 'VERY_BULLISH';
  if (s >= 0.2) return 'BULLISH';
  if (s >= -0.2) return 'NEUTRAL';
  if (s >= -0.6) return 'BEARISH';
  return 'VERY_BEARISH';
};

const FRESHNESS_ORDER: readonly Freshness[] = [
  'REALTIME', 'NEAR_REALTIME', 'DELAYED', 'END_OF_DAY', 'HISTORICAL', 'STALE', 'UNAVAILABLE',
];

const IMPORTANCE_ORDER: Record<string, number> = {
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

const HIGH_IMPACT_TYPES: readonly EventType[] = [
  'EARNINGS', 'GUIDANCE', 'MERGER', 'ACQUISITION', 'REGULATION',
  'RATING_CHANGE', 'SEC_FILING', 'IPO',
];

function freshnessRank(f: Freshness): number {
  return FRESHNESS_ORDER.indexOf(f);
}

function clusterKey(item: NewsItem): string {
  if (item.clusteringId) return item.clusteringId;
  // Group by eventType + same-day
  const day = item.publishedAt.slice(0, 10);
  return `${item.eventType}:${day}`;
}

export class EventAnalysisEngine {
  // --- Main Analysis ---

  analyze(
    news: readonly NewsItem[],
    upcomingCatalysts: readonly Catalyst[],
    assetId: string,
  ): EventAnalysis {
    const relevantNews = news.filter((n) => n.assetIds.includes(assetId));
    const relevantCatalysts = upcomingCatalysts;

    const sentiment = this.classifySentiment(relevantNews);
    const contradiction = this.detectContradictions(relevantNews);
    const freshness = this.assessNewsFreshness(relevantNews);
    const dominantType = this.dominantEventType(relevantNews);
    const rankedCatalysts = this.rankCatalysts(relevantCatalysts);

    const analysis: EventAnalysis = {
      assetId,
      symbol: assetId,
      timestamp: nowIso(),
      recentNews: relevantNews.slice(0, 20),
      upcomingCatalysts: rankedCatalysts.slice(0, 10),
      eventClassification: dominantType,
      overallSentiment: sentiment.overall,
      sentimentScore: sentiment.score,
      newsFreshness: freshness,
      contradictionDetected: contradiction,
      evidence: [],
    };

    return {
      ...analysis,
      evidence: this.buildEventEvidence(analysis),
    };
  }

  // --- Sentiment Classification ---

  classifySentiment(news: readonly NewsItem[]): {
    overall: SentimentLabel;
    score: number;
    evidence: string[];
  } {
    if (news.length === 0) {
      return { overall: 'NEUTRAL', score: 0, evidence: ['No news available for sentiment analysis'] };
    }

    let weightedSum = 0;
    let weightTotal = 0;
    const evidence: string[] = [];

    for (const item of news) {
      const baseScore = SENTIMENT_SCORE_MAP[item.sentiment] ?? 0;
      // Weight by importance and reliability
      const importanceW = (IMPORTANCE_ORDER[item.importance] ?? 1) / 3;
      const reliabilityW = Math.max(0.1, Math.min(1, item.reliability));
      const freshnessW = 1 - freshnessRank(item.freshness) / FRESHNESS_ORDER.length;
      const weight = importanceW * reliabilityW * Math.max(0.3, freshnessW);

      weightedSum += baseScore * weight;
      weightTotal += weight;
    }

    const avgScore = weightTotal > 0 ? weightedSum / weightTotal : 0;
    const overall = SENTIMENT_FROM_SCORE(avgScore);

    // Build evidence strings for high-impact items
    for (const item of news.filter((n) => n.importance === 'HIGH').slice(0, 5)) {
      evidence.push(`[${item.sentiment}] ${item.title} (${item.source}, ${item.publishedAt.slice(0, 10)})`);
    }

    return {
      overall,
      score: Math.round(avgScore * 100) / 100,
      evidence,
    };
  }

  // --- Contradiction Detection ---

  detectContradictions(news: readonly NewsItem[]): boolean {
    if (news.length < 2) return false;

    // Check 1: Conflicting sentiment among high-importance items
    const highItems = news.filter((n) => n.importance === 'HIGH');
    if (highItems.length >= 2) {
      const hasBullish = highItems.some((n) => n.sentiment === 'BULLISH' || n.sentiment === 'VERY_BULLISH');
      const hasBearish = highItems.some((n) => n.sentiment === 'BEARISH' || n.sentiment === 'VERY_BEARISH');
      if (hasBullish && hasBearish) return true;
    }

    // Check 2: News with same clustering ID but different sentiment
    const clusters = new Map<string, NewsItem[]>();
    for (const item of news) {
      const key = clusterKey(item);
      if (!clusters.has(key)) clusters.set(key, []);
      clusters.get(key)!.push(item);
    }

    for (const items of clusters.values()) {
      if (items.length < 2) continue;
      const sentiments = new Set(items.map((n) => n.sentiment));
      if (sentiments.has('BULLISH') || sentiments.has('VERY_BULLISH')) {
        if (sentiments.has('BEARISH') || sentiments.has('VERY_BEARISH')) {
          return true;
        }
      }
    }

    return false;
  }

  // --- Catalyst Ranking ---

  rankCatalysts(catalysts: readonly Catalyst[]): readonly Catalyst[] {
    return [...catalysts]
      .filter((c) => c.status === 'UPCOMING')
      .sort((a, b) => {
        // Score: importance (40%) + proximity (40%) + confidence (20%)
        const aScore = this.catalystScore(a);
        const bScore = this.catalystScore(b);
        return bScore - aScore;
      });
  }

  private catalystScore(c: Catalyst): number {
    const impScore = (IMPORTANCE_ORDER[c.importance] ?? 1) / 3;

    let proximityScore = 0.5;
    if (c.expectedDate) {
      const daysUntil = (new Date(c.expectedDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24);
      if (daysUntil < 0) proximityScore = 0;
      else if (daysUntil <= 7) proximityScore = 1.0;
      else if (daysUntil <= 30) proximityScore = 0.8;
      else if (daysUntil <= 90) proximityScore = 0.5;
      else proximityScore = 0.3;
    }

    const confScore = Math.max(0, Math.min(1, c.confidence));

    return impScore * 0.4 + proximityScore * 0.4 + confScore * 0.2;
  }

  // --- News Freshness ---

  assessNewsFreshness(news: readonly NewsItem[]): Freshness {
    if (news.length === 0) return 'UNAVAILABLE';

    // Find the best freshness across all news
    let bestRank = FRESHNESS_ORDER.length - 1;
    for (const item of news) {
      const rank = freshnessRank(item.freshness);
      if (rank < bestRank) bestRank = rank;
    }

    return FRESHNESS_ORDER[bestRank];
  }

  // --- Event Clustering ---

  clusterEvents(
    news: readonly NewsItem[],
  ): readonly { clusterId: string; items: readonly NewsItem[]; summary: string }[] {
    if (news.length === 0) return [];

    const clusters = new Map<string, NewsItem[]>();

    for (const item of news) {
      const key = clusterKey(item);
      if (!clusters.has(key)) clusters.set(key, []);
      clusters.get(key)!.push(item);
    }

    return [...clusters.entries()]
      .filter(([, items]) => items.length > 0)
      .sort((a, b) => b[1].length - a[1].length)
      .map(([clusterId, items]) => {
        const types = [...new Set(items.map((n) => n.eventType))];
        const sources = [...new Set(items.map((n) => n.source))];
        const avgReliability = items.reduce((s, n) => s + n.reliability, 0) / items.length;
        const summary =
          `${items.length} reports from ${sources.length} source(s), type: ${types.join(', ')}. ` +
          `Avg reliability: ${(avgReliability * 100).toFixed(0)}%.`;
        return { clusterId, items, summary };
      });
  }

  // --- Evidence Builder ---

  buildEventEvidence(analysis: EventAnalysis): readonly string[] {
    const ev: string[] = [];

    if (analysis.overallSentiment !== 'NEUTRAL') {
      ev.push(`Overall sentiment: ${analysis.overallSentiment} (score: ${analysis.sentimentScore.toFixed(2)})`);
    }

    if (analysis.contradictionDetected) {
      ev.push('Contradictory signals detected in recent news');
    }

    ev.push(`News freshness: ${analysis.newsFreshness}`);

    if (analysis.eventClassification !== 'OTHER') {
      ev.push(`Dominant event type: ${analysis.eventClassification}`);
    }

    if (analysis.upcomingCatalysts.length > 0) {
      const top = analysis.upcomingCatalysts[0];
      ev.push(`Top catalyst: ${top.description} (${top.importance}, ${top.expectedDate ?? 'undated'})`);
    }

    // Summarize news items
    for (const item of analysis.recentNews.slice(0, 5)) {
      ev.push(`[${item.importance}] ${item.title} — ${item.sentiment} (${item.source})`);
    }

    return ev;
  }

  // --- Helpers ---

  private dominantEventType(news: readonly NewsItem[]): EventType {
    if (news.length === 0) return 'OTHER';

    const counts = new Map<EventType, number>();
    for (const item of news) {
      const w = IMPORTANCE_ORDER[item.importance] ?? 1;
      counts.set(item.eventType, (counts.get(item.eventType) ?? 0) + w);
    }

    let best: EventType = 'OTHER';
    let bestCount = 0;
    for (const [type, count] of counts) {
      if (count > bestCount) {
        bestCount = count;
        best = type;
      }
    }

    return best;
  }
}
