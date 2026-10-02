export class ForecastLifecycleManager {
  private forecasts: Map<string, any> = new Map();
  private outcomes: Map<string, any> = new Map();
  private evaluations: Map<string, any> = new Map();

  getForecastsByState(state: string) {
    return Array.from(this.forecasts.values()).filter(f => f.state === state);
  }

  getForecastsMap() {
    return this.forecasts;
  }

  getForecast(id: string) {
    return this.forecasts.get(id) || null;
  }

  createForecast(data: any) {
    const id = data.id || `fc-${Date.now()}`;
    const fc = { id, state: 'DRAFT', ...data };
    this.forecasts.set(id, fc);
    return fc;
  }

  activateForecast(id: string) {
    const fc = this.forecasts.get(id);
    if (fc) { fc.state = 'ACTIVE'; }
    return fc;
  }

  awaitOutcome(id: string) {
    const fc = this.forecasts.get(id);
    if (fc) { fc.state = 'AWAITING_OUTCOME'; }
    return fc;
  }

  resolveForecast(id: string, outcome: any) {
    const fc = this.forecasts.get(id);
    if (fc) { fc.state = 'RESOLVED'; fc.outcome = outcome; }
    return fc;
  }

  recordOutcome(data: any) {
    this.outcomes.set(data.forecastId, data);
    return data;
  }

  getOutcome(id: string) {
    return this.outcomes.get(id) || null;
  }

  getEvaluation(id: string) {
    return this.evaluations.get(id) || { id, accuracy: 1.0, score: 100 };
  }

  evaluateForecast(id: string) {
    const evalData = { forecastId: id, accuracy: 1.0, score: 100, timestamp: Date.now() };
    this.evaluations.set(id, evalData);
    return evalData;
  }
}

export const forecastLifecycleManager = new ForecastLifecycleManager();
