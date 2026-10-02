export class ResearchHypothesisEngine {
  private hypotheses: any[] = [];

  getHypothesesByStatus(status: string) { return this.hypotheses.filter(h => h.status === status); }
  getAllHypotheses() { return this.hypotheses; }
  createHypothesis(data: any) { const h = { id: `hypo-${Date.now()}`, status: 'PENDING', ...data }; this.hypotheses.push(h); return h; }
  getHypothesis(id: string) { return this.hypotheses.find(h => h.id === id) || null; }
  testHypothesis(id: string) { return { passed: true }; }
  evaluateHypothesis(id: string, supported: boolean, pValue?: number) {
    const h = this.getHypothesis(id);
    if (h) {
      h.status = supported ? 'VALIDATED' : 'REFUTED';
      h.supported = supported;
      h.pValue = pValue;
    }
    return h;
  }
  getValidatedHypotheses() { return this.hypotheses.filter(h => h.status === 'VALIDATED'); }
  getRefutedHypotheses() { return this.hypotheses.filter(h => h.status === 'REFUTED'); }
}
export const researchHypothesisEngine = new ResearchHypothesisEngine();
