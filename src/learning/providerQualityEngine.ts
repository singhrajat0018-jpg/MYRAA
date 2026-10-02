export class ProviderQualityEngine {
  getAllHealth() { return []; }
  getHealth(id: string) { return null; }
  getTopProviders(count: number) { return []; }
}
export const providerQualityEngine = new ProviderQualityEngine();
