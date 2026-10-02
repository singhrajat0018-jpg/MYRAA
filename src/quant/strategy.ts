// ============================================================================
// MYRAA Phase 27 — Strategy Contract & Versioning
// ============================================================================

import type {
  StrategyDefinition, StrategyInstance, StrategyParameter, OHLCVBar,
  TradingSignal, Timeframe,
} from './contracts';
import { TechnicalAnalysisEngine } from '../finance/technical';

export type StrategyFunction = (
  bars: OHLCVBar[],
  index: number,
  params: Record<string, number | boolean | string>,
  technical?: ReturnType<TechnicalAnalysisEngine['analyze']>,
) => { action: 'LONG' | 'SHORT' | 'FLAT'; stopLoss?: number; target?: number } | null;

export class StrategyRegistry {
  private readonly definitions = new Map<string, StrategyDefinition>();
  private readonly functions = new Map<string, StrategyFunction>();
  private readonly technicalEngine = new TechnicalAnalysisEngine();

  register(def: StrategyDefinition, fn: StrategyFunction): void {
    this.definitions.set(def.id, def);
    this.functions.set(def.id, fn);
  }

  getDefinition(id: string): StrategyDefinition | undefined {
    return this.definitions.get(id);
  }

  getFunction(id: string): StrategyFunction | undefined {
    return this.functions.get(id);
  }

  list(): readonly StrategyDefinition[] {
    return Array.from(this.definitions.values());
  }

  validateInstance(instance: StrategyInstance): { valid: boolean; errors: string[] } {
    const def = this.definitions.get(instance.definitionId);
    if (!def) return { valid: false, errors: [`Unknown strategy: ${instance.definitionId}`] };
    if (instance.version !== def.version) {
      return { valid: false, errors: [`Version mismatch: expected ${def.version}, got ${instance.version}`] };
    }
    const errors: string[] = [];
    for (const p of def.parameters) {
      const val = instance.params[p.name];
      if (val === undefined) {
        if (p.default === undefined) errors.push(`Missing required parameter: ${p.name}`);
        continue;
      }
      if (p.type === 'number' || p.type === 'integer') {
        const num = val as number;
        if (typeof num !== 'number' || isNaN(num)) { errors.push(`${p.name} must be a number`); continue; }
        if (p.min !== undefined && num < p.min) errors.push(`${p.name} < min (${p.min})`);
        if (p.max !== undefined && num > p.max) errors.push(`${p.name} > max (${p.max})`);
      }
    }
    return { valid: errors.length === 0, errors };
  }

  createInstance(definitionId: string, params?: Record<string, number | boolean | string>): StrategyInstance {
    const def = this.definitions.get(definitionId);
    if (!def) throw new Error(`Unknown strategy: ${definitionId}`);
    const merged: Record<string, number | boolean | string> = {};
    for (const p of def.parameters) {
      merged[p.name] = params?.[p.name] ?? p.default;
    }
    return { definitionId, version: def.version, params: merged };
  }

  computeSignal(instance: StrategyInstance, bars: OHLCVBar[], index: number): TradingSignal | null {
    const def = this.definitions.get(instance.definitionId);
    if (!def) return null;
    const fn = this.functions.get(instance.definitionId);
    if (!fn) return null;
    const technical = this.technicalEngine.analyze(bars, def.requiredTimeframes[0] ?? '1d', '');
    const result = fn(bars, index, instance.params, technical);
    if (!result) return null;
    return {
      id: `sig_${instance.definitionId}_${index}`,
      symbol: '',
      assetId: '',
      timeframe: def.requiredTimeframes[0] === '1d' ? 'SWING' : 'SHORT_TERM',
      strategy: def.type,
      bias: result.action === 'LONG' ? 'LONG_BIAS' as const : result.action === 'SHORT' ? 'SHORT_BIAS' as const : 'WATCH' as const,
      strength: 0.7,
      confidence: 0.6,
      components: { technicalScore: 0.7, fundamentalScore: 0, eventScore: 0, macroScore: 0, sentimentScore: 0, regimeScore: 0, riskScore: 0 },
      weights: { technical: 1, fundamental: 0, event: 0, macro: 0, sentiment: 0, regime: 0 },
      evidence: [],
      contradictions: [],
      invalidationConditions: [],
      createdAt: bars[index]?.timestamp ?? '',
      expiresAt: '',
      status: 'ACTIVE' as const,
      version: 1,
    };
  }

  validateParams(def: StrategyDefinition, params: Record<string, number | boolean | string>): string[] {
    const errors: string[] = [];
    for (const p of def.parameters) {
      const val = params[p.name];
      if (val === undefined || val === null) {
        if (p.default === undefined) errors.push(`Missing required parameter: ${p.name}`);
        continue;
      }
      if (p.type === 'number' || p.type === 'integer') {
        const num = val as number;
        if (typeof num !== 'number' || isNaN(num)) { errors.push(`${p.name} must be a number`); continue; }
        if (p.min !== undefined && num < p.min) errors.push(`${p.name} < min (${p.min})`);
        if (p.max !== undefined && num > p.max) errors.push(`${p.name} > max (${p.max})`);
        if (p.type === 'integer' && !Number.isInteger(num)) errors.push(`${p.name} must be integer`);
      } else if (p.type === 'boolean') {
        if (typeof val !== 'boolean') errors.push(`${p.name} must be boolean`);
      } else if (p.type === 'enum') {
        if (p.options && !p.options.includes(val as string)) errors.push(`${p.name}: invalid option`);
      }
    }
    return errors;
  }

  generateOrderIntent(
    signal: { signal: string; strength: number; stopLoss?: number; target?: number },
    symbol: string,
    quantity: number,
  ): { symbol: string; side: 'BUY' | 'SELL'; orderType: string; quantity: number; stopPrice?: string; timeInForce: string; note: string } | null {
    if (signal.signal === 'NO_SIGNAL' || signal.signal === 'WATCH') return null;
    const side: 'BUY' | 'SELL' = signal.signal === 'LONG_BIAS' ? 'BUY' : 'SELL';
    return {
      symbol,
      side,
      orderType: 'MARKET',
      quantity,
      stopPrice: signal.stopLoss?.toString(),
      timeInForce: 'DAY',
      note: `Strategy signal: ${signal.signal} strength ${signal.strength.toFixed(3)}`,
    };
  }
}