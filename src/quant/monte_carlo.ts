// ============================================================================
// MYRAA Phase 27 — Monte Carlo Simulation Engine
// ============================================================================

import type {
  MonteCarloConfig, MonteCarloResult, PerformanceMetrics,
  StrategyInstance,
} from './contracts';

export class MonteCarloEngine {
  run(params: {
    returns: number[];
    strategy: StrategyInstance;
    config?: Partial<MonteCarloConfig>;
  }): MonteCarloResult {
    const { returns, strategy, config: partialConfig } = params;
    const config: MonteCarloConfig = {
      simulations: partialConfig?.simulations ?? 1000,
      periodsPerSim: partialConfig?.periodsPerSim ?? 252,
      seed: partialConfig?.seed ?? 42,
      bootstrapMethod: partialConfig?.bootstrapMethod ?? 'BLOCK',
      blockSize: partialConfig?.blockSize ?? 10,
      confidenceLevel: partialConfig?.confidenceLevel ?? 0.95,
    };
    const rng = this.createRNG(config.seed);
    const paths: number[][] = [];
    const finalReturns: number[] = [];
    const worstDrawdowns: number[] = [];
    for (let sim = 0; sim < config.simulations; sim++) {
      const sampledReturns = this.bootstrap(returns, config.periodsPerSim, config, rng);
      let equity = 1;
      const path = [equity];
      let peak = equity;
      let maxDD = 0;
      for (const r of sampledReturns) {
        equity *= (1 + r);
        path.push(equity);
        peak = Math.max(peak, equity);
        const dd = (peak - equity) / peak;
        maxDD = Math.max(maxDD, dd);
      }
      paths.push(path);
      finalReturns.push(equity - 1);
      worstDrawdowns.push(maxDD);
    }
    finalReturns.sort((a, b) => a - b);
    worstDrawdowns.sort((a, b) => a - b);
    const pct = (arr: number[], p: number) => arr[Math.floor(arr.length * p)] ?? 0;
    const meanReturn = finalReturns.reduce((s, r) => s + r, 0) / finalReturns.length;
    const stdReturn = Math.sqrt(finalReturns.reduce((s, r) => s + (r - meanReturn) ** 2, 0) / finalReturns.length);
    const losses = finalReturns.filter(r => r < 0);
    const allDD = worstDrawdowns;
    const meanDD = allDD.reduce((s, d) => s + d, 0) / allDD.length;
    return {
      strategy: { ...strategy },
      config,
      simulations: config.simulations,
      paths: paths.map(p => [...p]) as unknown as readonly number[][],
      percentiles: {
        p5: pct(finalReturns, 0.05),
        p25: pct(finalReturns, 0.25),
        p50: pct(finalReturns, 0.50),
        p75: pct(finalReturns, 0.75),
        p95: pct(finalReturns, 0.95),
      },
      stats: {
        meanReturn,
        medianReturn: pct(finalReturns, 0.50),
        stdReturn,
        worstDrawdown: pct(allDD, 0.95),
        worstDrawdownProb: allDD.filter(d => d > 0.5).length / config.simulations,
        valueAtRisk95: -pct(finalReturns, 0.05),
        conditionalVaR95: -losses.length > 0
          ? losses.reduce((s, r) => s + r, 0) / losses.length
          : 0,
        probabilityOfLoss: losses.length / config.simulations,
        probabilityOfRuin: finalReturns.filter(r => r < -0.5).length / config.simulations,
        expectedShortfall: this.expectedShortfall(finalReturns, 0.05),
      },
      timestamp: new Date().toISOString(),
    };
  }

  private bootstrap(
    returns: readonly number[],
    count: number,
    config: MonteCarloConfig,
    rng: () => number,
  ): number[] {
    const result: number[] = [];
    if (config.bootstrapMethod === 'BLOCK') {
      const blockSize = Math.max(1, config.blockSize ?? 10);
      for (let i = 0; i < count; i++) {
        const idx = Math.floor(rng() * Math.max(1, returns.length - blockSize));
        const posInBlock = Math.floor(rng() * blockSize);
        result.push(returns[(idx + posInBlock) % returns.length]);
      }
    } else {
      for (let i = 0; i < count; i++) {
        const idx = Math.floor(rng() * returns.length);
        result.push(returns[idx]);
      }
    }
    return result;
  }

  private expectedShortfall(returns: readonly number[], alpha: number): number {
    const sorted = [...returns].sort((a, b) => a - b);
    const cutoff = Math.floor(sorted.length * alpha);
    const tail = sorted.slice(0, Math.max(1, cutoff));
    return -tail.reduce((s, r) => s + r, 0) / tail.length;
  }

  private createRNG(seed: number): () => number {
    let s = seed;
    return () => {
      s = (s * 1664525 + 1013904223) & 0xFFFFFFFF;
      return (s >>> 0) / 0xFFFFFFFF;
    };
  }
}
