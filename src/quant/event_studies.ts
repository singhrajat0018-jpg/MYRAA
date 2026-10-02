// ============================================================================
// MYRAA Phase 27 — Event Studies Engine
// ============================================================================

import type { EventStudyResult, EventStudyEntry } from './contracts';
import type { OHLCVBar } from '../finance/contracts';

export class EventStudyEngine {
  private readonly events: EventStudyEntry[] = [];

  registerEvent(event: EventStudyEntry): void {
    this.events.push(event);
  }

  getEvents(): readonly EventStudyEntry[] {
    return Object.freeze([...this.events]);
  }

  clearEvents(): void {
    this.events.length = 0;
  }

  analyzeEvent(params: {
    event: EventStudyEntry;
    bars: readonly OHLCVBar[];
    preWindow?: number;
    postWindow?: number;
  }): EventStudyResult {
    const { event, bars, preWindow = -20, postWindow = 20 } = params;
    const sorted = [...bars].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const eventIdx = sorted.findIndex(b => b.timestamp >= event.eventTimestamp);
    if (eventIdx < 0) {
      return this.emptyResult(event);
    }
    const returns: number[] = [];
    for (let i = 1; i < sorted.length; i++) {
      returns.push(sorted[i - 1].close !== 0 ? (sorted[i].close - sorted[i - 1].close) / sorted[i - 1].close : 0);
    }
    const startIdx = Math.max(0, eventIdx + preWindow);
    const endIdx = Math.min(returns.length, eventIdx + postWindow + 1);
    const preReturns = returns.slice(startIdx, eventIdx);
    const postReturns = returns.slice(eventIdx, endIdx);
    const benchmarkReturn = preReturns.length > 0
      ? preReturns.reduce((s, r) => s + r, 0) / preReturns.length
      : 0;
    const carDays: { day: number; car: number }[] = [];
    let cumulative = 0;
    for (let d = preWindow; d <= postWindow; d++) {
      const retIdx = eventIdx + d;
      if (retIdx < 0 || retIdx >= returns.length) {
        carDays.push({ day: d, car: cumulative });
        continue;
      }
      const abnormal = returns[retIdx] - benchmarkReturn;
      cumulative += abnormal;
      carDays.push({ day: d, car: cumulative });
    }
    const abnormalReturn = postReturns.length > 0
      ? postReturns[0] - benchmarkReturn
      : 0;
    const cumulativeAbnormalReturn = cumulative;
    const preDrift = preReturns.length > 0
      ? preReturns.reduce((s, r) => s + r, 0) / preReturns.length
      : 0;
    const postDrift = postReturns.length > 0
      ? postReturns.reduce((s, r) => s + r, 0) / postReturns.length
      : 0;
    const tStat = this.computeTStatistic(preReturns, postReturns, benchmarkReturn);
    return {
      eventId: event.eventId,
      symbol: event.symbol,
      eventType: event.eventType,
      eventTimestamp: event.eventTimestamp,
      carDays: Object.freeze(carDays),
      abnormalReturn,
      cumulativeAbnormalReturn,
      tStatistic: tStat,
      significantAtFive: Math.abs(tStat) > 1.96,
      preEventDrift: preDrift,
      postEventDrift: postDrift,
      sampleSize: 1,
    };
  }

  analyzeAll(params: {
    bars: readonly OHLCVBar[];
    preWindow?: number;
    postWindow?: number;
  }): EventStudyResult[] {
    return this.events.map(event => this.analyzeEvent({ ...params, event }));
  }

  private computeTStatistic(
    preReturns: number[], postReturns: number[], benchmarkReturn: number,
  ): number {
    if (postReturns.length < 2) return 0;
    const abnormal = postReturns.map(r => r - benchmarkReturn);
    const mean = abnormal.reduce((s, r) => s + r, 0) / abnormal.length;
    const variance = abnormal.reduce((s, r) => s + (r - mean) ** 2, 0) / (abnormal.length - 1);
    const se = Math.sqrt(variance / abnormal.length);
    return se > 0 ? mean / se : 0;
  }

  private emptyResult(event: EventStudyEntry): EventStudyResult {
    return {
      eventId: event.eventId,
      symbol: event.symbol,
      eventType: event.eventType,
      eventTimestamp: event.eventTimestamp,
      carDays: Object.freeze([]),
      abnormalReturn: 0,
      cumulativeAbnormalReturn: 0,
      tStatistic: 0,
      significantAtFive: false,
      preEventDrift: 0,
      postEventDrift: 0,
      sampleSize: 0,
    };
  }
}
