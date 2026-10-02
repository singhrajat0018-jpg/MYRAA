// ============================================================================
// MYRAA Phase 26 — Watchlist Engine
// ============================================================================

import type {
  WatchlistItem,
  AlertRule,
  TradingThesis,
  Catalyst,
  StrategyType,
  NewsItem,
} from './contracts';

const PRIORITY_ORDER: Record<string, number> = {
  HIGH: 0,
  MEDIUM: 1,
  LOW: 2,
};

const STALE_REVIEW_MS = 7 * 86_400_000;

let alertCounter = 0;

function generateAlertId(): string {
  alertCounter += 1;
  return `alert_${Date.now()}_${alertCounter}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function materialChangeThreshold(bias1: string, bias2: string): boolean {
  if (bias1 === bias2) return false;
  const extremes = ['LONG_BIAS', 'SHORT_BIAS'];
  const neutrals = ['NEUTRAL', 'WATCH', 'NO_SIGNAL'];
  if (extremes.includes(bias1) && extremes.includes(bias2)) return true;
  if (extremes.includes(bias1) && neutrals.includes(bias2)) return true;
  if (neutrals.includes(bias1) && extremes.includes(bias2)) return true;
  return false;
}

export class WatchlistEngine {
  create(item: {
    symbol: string;
    assetId: string;
    reason: string;
    strategy: StrategyType;
    catalysts?: readonly Catalyst[];
    invalidationConditions?: readonly string[];
    priority?: 'HIGH' | 'MEDIUM' | 'LOW';
  }): WatchlistItem {
    const timestamp = nowIso();

    return {
      assetId: item.assetId,
      symbol: item.symbol,
      reason: item.reason,
      strategy: item.strategy,
      catalysts: item.catalysts ? [...item.catalysts] : [],
      invalidationConditions: item.invalidationConditions ? [...item.invalidationConditions] : [],
      alertRules: [],
      createdAt: timestamp,
      lastReviewedAt: timestamp,
      priority: item.priority ?? 'MEDIUM',
    };
  }

  updateReview(item: WatchlistItem): WatchlistItem {
    return {
      ...item,
      lastReviewedAt: nowIso(),
    };
  }

  addAlert(item: WatchlistItem, alert: AlertRule): WatchlistItem {
    const existingIndex = item.alertRules.findIndex(
      (a) => a.type === alert.type && a.threshold === alert.threshold,
    );

    let updatedAlerts: AlertRule[];
    if (existingIndex >= 0) {
      updatedAlerts = item.alertRules.map((a, i) =>
        i === existingIndex ? { ...alert, enabled: true } : a,
      );
    } else {
      updatedAlerts = [...item.alertRules, alert];
    }

    return {
      ...item,
      alertRules: updatedAlerts,
    };
  }

  checkAlerts(
    item: WatchlistItem,
    currentPrice: number,
    volume: number,
    news: readonly NewsItem[],
  ): readonly AlertRule[] {
    const triggered: AlertRule[] = [];

    for (const rule of item.alertRules) {
      if (!rule.enabled) continue;

      switch (rule.type) {
        case 'PRICE_ABOVE':
          if (rule.threshold !== undefined && currentPrice > rule.threshold) {
            triggered.push(rule);
          }
          break;

        case 'PRICE_BELOW':
          if (rule.threshold !== undefined && currentPrice < rule.threshold) {
            triggered.push(rule);
          }
          break;

        case 'VOLUME_SPIKE':
          if (rule.threshold !== undefined && volume > rule.threshold) {
            triggered.push(rule);
          }
          break;

        case 'NEWS_EVENT': {
          const relevantNews = news.filter(
            (n) =>
              n.assetIds.includes(item.assetId) &&
              (n.importance === 'HIGH' || n.importance === 'MEDIUM'),
          );
          if (relevantNews.length > 0) {
            const hasSignificantNews = relevantNews.some(
              (n) =>
                n.sentiment === 'VERY_BULLISH' ||
                n.sentiment === 'VERY_BEARISH' ||
                n.importance === 'HIGH',
            );
            if (hasSignificantNews) {
              triggered.push(rule);
            }
          }
          break;
        }

        case 'TECHNICAL_LEVEL':
          if (rule.threshold !== undefined) {
            const tolerance = rule.threshold * 0.01;
            if (
              Math.abs(currentPrice - rule.threshold) <= tolerance
            ) {
              triggered.push(rule);
            }
          }
          break;

        case 'THESIS_INVALIDATION':
          if (item.invalidationConditions.length > 0) {
            triggered.push(rule);
          }
          break;
      }
    }

    return triggered;
  }

  evaluateThesisChange(
    item: WatchlistItem,
    newThesis: TradingThesis,
  ): { shouldNotify: boolean; reason: string } {
    if (!item.thesis) {
      return {
        shouldNotify: true,
        reason: 'First thesis created for this watchlist item',
      };
    }

    const reasons: string[] = [];

    if (newThesis.status === 'INVALIDATED') {
      return {
        shouldNotify: true,
        reason: 'Thesis has been invalidated',
      };
    }

    const oldConfidence = this.extractConfidenceFromThesisText(item.thesis);
    if (oldConfidence !== null) {
      const confidenceDelta = Math.abs(newThesis.confidence - oldConfidence);
      if (confidenceDelta > 0.2) {
        reasons.push(
          `Confidence shifted from ${oldConfidence.toFixed(2)} to ${newThesis.confidence.toFixed(2)}`,
        );
      }
    }

    const oldBias = this.extractBiasFromThesisText(item.thesis);
    if (oldBias !== null && materialChangeThreshold(oldBias, newThesis.signalBias)) {
      reasons.push(
        `Signal bias changed from ${oldBias} to ${newThesis.signalBias}`,
      );
    }

    if (
      newThesis.keyRisks.length > 0 &&
      newThesis.keyRisks.some(
        (r) => r.includes('EXTREME') || r.includes('CRITICAL'),
      )
    ) {
      reasons.push('New extreme/critical risk identified');
    }

    if (newThesis.keyCatalysts.length > 0) {
      const highCatalysts = newThesis.keyCatalysts.filter(
        (c) => c.includes('HIGH') || c.includes('earnings'),
      );
      if (highCatalysts.length > 0) {
        reasons.push('High-importance catalyst identified');
      }
    }

    if (reasons.length > 0) {
      return {
        shouldNotify: true,
        reason: reasons.join('; '),
      };
    }

    return {
      shouldNotify: false,
      reason: 'No material change detected',
    };
  }

  prioritize(items: readonly WatchlistItem[]): readonly WatchlistItem[] {
    return [...items].sort((a, b) => {
      const priorityDiff =
        (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1);
      if (priorityDiff !== 0) return priorityDiff;

      const aStaleness = a.lastReviewedAt
        ? Date.now() - new Date(a.lastReviewedAt).getTime()
        : Infinity;
      const bStaleness = b.lastReviewedAt
        ? Date.now() - new Date(b.lastReviewedAt).getTime()
        : Infinity;

      return bStaleness - aStaleness;
    });
  }

  private extractConfidenceFromThesisText(thesisText: string): number | null {
    const match = thesisText.match(/confidence\s+(\d+\.?\d*)/i);
    if (match) {
      const val = parseFloat(match[1]);
      if (!isNaN(val) && val >= 0 && val <= 1) return val;
    }
    return null;
  }

  private extractBiasFromThesisText(thesisText: string): string | null {
    const biases = ['LONG_BIAS', 'SHORT_BIAS', 'NEUTRAL', 'WATCH', 'NO_SIGNAL'];
    for (const bias of biases) {
      if (thesisText.toUpperCase().includes(bias)) {
        return bias;
      }
    }
    return null;
  }
}
