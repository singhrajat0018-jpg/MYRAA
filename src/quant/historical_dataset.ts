// ============================================================================
// MYRAA Phase 27 — Historical Dataset & Point-in-Time Reconstruction
// ============================================================================

import type { OHLCVBar, Timeframe, AssetIdentity } from '../finance/contracts';
import { HistoricalIntegrityEngine } from '../finance/historical';
import type {
  HistoricalDataset, DatasetIntegrityCheck, DatasetSource,
  DataSourceQuality, AdjustmentType,
} from './contracts';

export class HistoricalDatasetEngine {
  private readonly integrityEngine = new HistoricalIntegrityEngine();
  private readonly datasets = new Map<string, HistoricalDataset>();

  buildDataset(params: {
    symbol: string;
    timeframe: Timeframe;
    bars: OHLCVBar[];
    source?: DatasetSource;
    survivorshipFilter?: boolean;
  }): { dataset: HistoricalDataset; integrity: DatasetIntegrityCheck } {
    const { symbol, timeframe, bars, source, survivorshipFilter } = params;
    const datasetSource: DatasetSource = source ?? {
      provider: 'LOCAL', quality: 'PRIMARY' as DataSourceQuality,
      adjustment: 'BOTH' as AdjustmentType, verified: false,
    };
    const integrity = this.validateDataset(bars);
    const cleanBars = integrity.valid ? bars : bars.slice(integrity.duplicatesRemoved);
    const dataset: HistoricalDataset = {
      id: `${symbol}_${timeframe}_${Date.now()}`,
      symbol,
      timeframe,
      bars: Object.freeze(cleanBars),
      source: datasetSource,
      startDate: cleanBars[0]?.timestamp ?? '',
      endDate: cleanBars[cleanBars.length - 1]?.timestamp ?? '',
      totalBars: cleanBars.length,
      completeness: this.computeCompleteness(cleanBars),
      hasLookAhead: false,
      survivorshipFiltered: survivorshipFilter ?? false,
    };
    this.datasets.set(dataset.id, dataset);
    return { dataset, integrity };
  }

  filterToDecisionPoint(params: {
    dataset: HistoricalDataset;
    decisionTimestamp: string;
  }): { bars: readonly OHLCVBar[]; filtered: number } {
    const { dataset, decisionTimestamp } = params;
    const filtered = this.integrityEngine.filterAvailableData(
      dataset.bars as OHLCVBar[], decisionTimestamp,
    );
    return { bars: filtered, filtered: dataset.bars.length - filtered.length };
  }

  validatePointInTime(params: {
    dataset: HistoricalDataset;
    eventTimestamps: string[];
    decisionTimestamp: string;
  }): { hasLeakage: boolean; violations: readonly string[] } {
    return this.integrityEngine.validateLookAheadBias({
      analysisTimestamp: params.decisionTimestamp,
      dataTimestamps: params.dataset.bars.map(b => b.timestamp),
      eventTimestamps: params.eventTimestamps,
    });
  }

  validateSurvivorship(params: {
    dataset: HistoricalDataset;
    allAssets: AssetIdentity[];
    asOfDate: string;
  }): { survivorCount: number; delistedCount: number; delistedAssets: readonly AssetIdentity[] } {
    return this.integrityEngine.validateSurvivorshipBias(params.allAssets, params.asOfDate) as any;
  }

  adjustCorporateActions(params: {
    bars: readonly OHLCVBar[];
    type: 'SPLIT' | 'DIVIDEND';
    effectiveDate: string;
    ratio?: number;
    dividendPerShare?: number;
  }): readonly OHLCVBar[] {
    return this.integrityEngine.adjustCorporateActions(params.bars as OHLCVBar[], [{
      type: params.type,
      effectiveDate: params.effectiveDate,
      ratio: params.ratio,
      dividendPerShare: params.dividendPerShare,
      announcementDate: params.effectiveDate,
      description: `${params.type} adjustment`,
    }]);
  }

  getDataIntegrity(bars: OHLCVBar[]): DatasetIntegrityCheck {
    const validation = this.integrityEngine.validateDataIntegrity(bars);
    return {
      datasetId: '',
      duplicatesRemoved: 0,
      gapsDetected: [],
      impossibleBarsFound: validation.issues.filter(i => i.includes('impossible')).length,
      adjustedBars: 0,
      valid: validation.valid,
      issues: validation.issues,
    };
  }

  computeReturns(bars: readonly OHLCVBar[], type: 'ABSOLUTE' | 'PERCENTAGE' | 'LOG' = 'PERCENTAGE'): number[] {
    return [...this.integrityEngine.computeReturns(bars as OHLCVBar[], type)];
  }

  getDataset(id: string): HistoricalDataset | undefined {
    return this.datasets.get(id);
  }

  listDatasets(): readonly HistoricalDataset[] {
    return Array.from(this.datasets.values());
  }

  removeDataset(id: string): boolean {
    return this.datasets.delete(id);
  }

  private validateDataset(bars: OHLCVBar[]): DatasetIntegrityCheck {
    const issues: string[] = [];
    let duplicatesRemoved = 0;
    const seen = new Set<string>();
    for (const bar of bars) {
      if (seen.has(bar.timestamp)) { duplicatesRemoved++; }
      seen.add(bar.timestamp);
    }
    if (duplicatesRemoved > 0) { issues.push(`${duplicatesRemoved} duplicate timestamps`); }
    if (bars.length === 0) { issues.push('Empty dataset'); }
    const impossible = bars.filter(b => b.high < b.low || b.open < 0 || b.close < 0 || b.volume < 0);
    if (impossible.length > 0) { issues.push(`${impossible.length} impossible OHLCV bars`); }
    const gaps: string[] = [];
    for (let i = 1; i < bars.length; i++) {
      const prev = new Date(bars[i - 1].timestamp).getTime();
      const curr = new Date(bars[i].timestamp).getTime();
      if (curr <= prev) { gaps.push(`Gap at index ${i}`); }
    }
    return {
      datasetId: '', duplicatesRemoved, gapsDetected: gaps,
      impossibleBarsFound: impossible.length, adjustedBars: 0,
      valid: issues.length === 0, issues,
    };
  }

  private computeCompleteness(bars: OHLCVBar[]): number {
    if (bars.length < 2) return 1;
    const first = new Date(bars[0].timestamp).getTime();
    const last = new Date(bars[bars.length - 1].timestamp).getTime();
    const expectedSpan = last - first;
    if (expectedSpan <= 0) return 1;
    const actualBars = bars.length;
    const expectedBars = Math.floor(expectedSpan / (86400000)) + 1;
    return Math.min(1, actualBars / expectedBars);
  }
}
