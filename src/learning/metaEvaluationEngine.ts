// ============================================================================
// MYRAA Phase 28 — Meta Evaluation Engine
// Tracks whether the learning system itself behaves consistently.
// ============================================================================

export interface MetaEvaluationResult {
  readonly metric: string;
  readonly currentValue: number;
  readonly historicalAverage: number;
  readonly consistent: boolean;
  readonly deviation: number;
  readonly sampleSize: number;
  readonly checkedAt: string;
}

export class MetaEvaluationEngine {
  private metricHistory = new Map<string, number[]>();
  private results: MetaEvaluationResult[] = [];
  private readonly MAX_HISTORY = 1000;

  recordMetric(name: string, value: number): void {
    const history = this.metricHistory.get(name) || [];
    history.push(value);
    if (history.length > this.MAX_HISTORY) history.shift();
    this.metricHistory.set(name, history);
  }

  evaluateConsistency(metricName: string, tolerance: number = 0.2): MetaEvaluationResult {
    const history = this.metricHistory.get(metricName) || [];
    const currentValue = history.length > 0 ? history[history.length - 1] : 0;
    const historicalValues = history.slice(0, -1);
    const historicalAverage = historicalValues.length > 0
      ? historicalValues.reduce((s, v) => s + v, 0) / historicalValues.length
      : currentValue;

    const deviation = historicalAverage !== 0
      ? Math.abs(currentValue - historicalAverage) / Math.abs(historicalAverage)
      : currentValue !== 0 ? 1 : 0;

    const consistent = deviation <= tolerance || history.length < 5;

    const result: MetaEvaluationResult = {
      metric: metricName,
      currentValue,
      historicalAverage,
      consistent,
      deviation,
      sampleSize: history.length,
      checkedAt: new Date().toISOString(),
    };

    this.results.push(result);
    return result;
  }

  evaluateAll(tolerance: number = 0.2): MetaEvaluationResult[] {
    const results: MetaEvaluationResult[] = [];
    for (const name of this.metricHistory.keys()) {
      results.push(this.evaluateConsistency(name, tolerance));
    }
    return results;
  }

  getResults(): MetaEvaluationResult[] {
    return [...this.results];
  }

  getInconsistentMetrics(): MetaEvaluationResult[] {
    return this.results.filter(r => !r.consistent);
  }

  getMetricHistory(name: string): number[] {
    return [...(this.metricHistory.get(name) || [])];
  }

  clearHistory(): void {
    this.metricHistory.clear();
    this.results = [];
  }
}

export const metaEvaluationEngine = new MetaEvaluationEngine();
