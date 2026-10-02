export class StrategyHealthEngine {
  getAllHealth() { return []; }
  getHealth(id: string) { return null; }
  getMatrix(id: string) { return []; }
}
export const strategyHealthEngine = new StrategyHealthEngine();
