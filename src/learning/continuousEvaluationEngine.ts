export class ContinuousEvaluationEngine {
  start() {}
  stop() {}
  getStatistics() {
    return { evaluationsCount: 0, active: false };
  }
}
export const continuousEvaluationEngine = new ContinuousEvaluationEngine();
