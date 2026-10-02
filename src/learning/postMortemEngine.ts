// ============================================================================
// MYRAA Phase 28 — Post-Mortem Engine
// Generates structured post-mortems for forecast failures and successes.
// ============================================================================

import type {
  Forecast, ForecastEvaluation, ForecastOutcome, ResearchLesson, RegimeType
} from './contracts';

export interface PostMortem {
  readonly postMortemId: string;
  readonly forecastId: string;
  readonly strategyId: string;
  readonly outcome: 'SUCCESS' | 'FAILURE' | 'PARTIAL' | 'UNKNOWN';
  readonly failureCategory: string | null;
  readonly primaryCause: string;
  readonly secondaryCauses: string[];
  readonly supportingEvidence: string[];
  readonly contradictingEvidence: string[];
  readonly missedEvidence: string[];
  readonly regime: RegimeType;
  readonly confidence: number;
  readonly lesson: string;
  readonly createdAt: string;
}

export class PostMortemEngine {
  private postMortems = new Map<string, PostMortem>();

  generatePostMortem(
    forecast: Forecast,
    evaluation: ForecastEvaluation,
    outcome: ForecastOutcome
  ): PostMortem {
    const pmId = `pm_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const outcomeLabel = evaluation.strategyOutcome === 'SUCCESS' ? 'SUCCESS'
      : evaluation.strategyOutcome === 'FAILURE' ? 'FAILURE'
      : evaluation.strategyOutcome === 'PARTIAL' ? 'PARTIAL' : 'UNKNOWN';

    const primaryCause = this.determinePrimaryCause(evaluation);
    const secondaryCauses = this.determineSecondaryCauses(evaluation, outcome);
    const lesson = this.generateLesson(forecast, evaluation, outcome, primaryCause);

    const pm: PostMortem = {
      postMortemId: pmId,
      forecastId: forecast.forecastId,
      strategyId: forecast.strategyId,
      outcome: outcomeLabel,
      failureCategory: evaluation.failureCategory,
      primaryCause,
      secondaryCauses,
      supportingEvidence: evaluation.supportingEvidence,
      contradictingEvidence: evaluation.missedEvidence,
      missedEvidence: evaluation.missedEvidence,
      regime: forecast.regime,
      confidence: evaluation.confidenceQuality,
      lesson,
      createdAt: new Date().toISOString(),
    };

    this.postMortems.set(pmId, pm);
    return pm;
  }

  getPostMortem(postMortemId: string): PostMortem | undefined {
    return this.postMortems.get(postMortemId);
  }

  getPostMortemByForecast(forecastId: string): PostMortem | undefined {
    return Array.from(this.postMortems.values()).find(pm => pm.forecastId === forecastId);
  }

  getAllPostMortems(): PostMortem[] {
    return Array.from(this.postMortems.values());
  }

  getPostMortemsByStrategy(strategyId: string): PostMortem[] {
    return Array.from(this.postMortems.values()).filter(pm => pm.strategyId === strategyId);
  }

  getPostMortemsByOutcome(outcome: 'SUCCESS' | 'FAILURE' | 'PARTIAL' | 'UNKNOWN'): PostMortem[] {
    return Array.from(this.postMortems.values()).filter(pm => pm.outcome === outcome);
  }

  getFailurePatterns(): Map<string, number> {
    const patterns = new Map<string, number>();
    for (const pm of this.postMortems.values()) {
      if (pm.failureCategory) {
        patterns.set(pm.failureCategory, (patterns.get(pm.failureCategory) || 0) + 1);
      }
    }
    return patterns;
  }

  deletePostMortem(postMortemId: string): boolean {
    return this.postMortems.delete(postMortemId);
  }

  private determinePrimaryCause(evaluation: ForecastEvaluation): string {
    if (evaluation.failureCategory) {
      switch (evaluation.failureCategory) {
        case 'TREND_REVERSAL': return 'Strategy failed to detect trend exhaustion';
        case 'FALSE_BREAKOUT': return 'Breakout signal lacked sufficient confirmation';
        case 'EVENT_MISREAD': return 'Event impact was misjudged';
        case 'MACRO_SHOCK': return 'External macro event disrupted expected pattern';
        case 'REGIME_SHIFT': return 'Market regime changed during forecast horizon';
        case 'DATA_ERROR': return 'Input data was inaccurate or incomplete';
        case 'TIMING_ERROR': return 'Entry or exit timing was suboptimal';
        case 'LIQUIDITY': return 'Liquidity conditions were unfavorable';
        case 'VOLATILITY': return 'Volatility exceeded expected range';
        case 'THESIS_INVALIDATION': return 'Core thesis assumption was invalidated';
        default: return 'Cause could not be determined from available evidence';
      }
    }
    if (evaluation.strategyOutcome === 'SUCCESS') return 'Strategy conditions were met and market moved as expected';
    return 'Insufficient evidence to determine primary cause';
  }

  private determineSecondaryCauses(evaluation: ForecastEvaluation, outcome: ForecastOutcome): string[] {
    const causes: string[] = [];
    if (outcome.regimeAtOutcome && outcome.regimeAtOutcome !== 'UNKNOWN') {
      causes.push(`Market was in ${outcome.regimeAtOutcome} regime at outcome`);
    }
    if (outcome.volatility !== undefined && outcome.volatility > 0.3) {
      causes.push(`Elevated volatility (${(outcome.volatility * 100).toFixed(1)}%) contributed to uncertainty`);
    }
    if (evaluation.missedEvidence.length > 0) {
      causes.push(`${evaluation.missedEvidence.length} pieces of evidence were available but underweighted`);
    }
    if (outcome.timingError !== undefined && Math.abs(outcome.timingError) > 3) {
      causes.push(`Timing was off by ${Math.abs(outcome.timingError)} periods`);
    }
    return causes;
  }

  private generateLesson(
    forecast: Forecast, evaluation: ForecastEvaluation,
    outcome: ForecastOutcome, primaryCause: string
  ): string {
    if (evaluation.strategyOutcome === 'SUCCESS') {
      return `Strategy ${forecast.strategyId} succeeded in ${forecast.regime} regime with ${forecast.horizon.type} horizon. Conditions were favorable for this approach.`;
    }
    const category = evaluation.failureCategory || 'UNKNOWN';
    return `Strategy ${forecast.strategyId} failed due to ${category}: ${primaryCause}. ` +
      `Regime: ${forecast.regime}. Horizon: ${forecast.horizon.type}. ` +
      `Consider adjusting approach for similar future conditions.`;
  }
}

export const postMortemEngine = new PostMortemEngine();
