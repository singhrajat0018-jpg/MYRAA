// ============================================================================
// MYRAA Frame Difference Engine — Visual Change & Region Detection
// ============================================================================

import type { ScreenRegion, VisualDelta, ActiveWindowInfo } from './contracts';

export interface FrameDifferenceOptions {
  threshold?: number; // 0.0 to 1.0 (default 0.02 = 2% change threshold)
  minRegionArea?: number;
}

export class FrameDifferenceEngine {
  private threshold: number;

  constructor(options: FrameDifferenceOptions = {}) {
    this.threshold = options.threshold ?? 0.02;
  }

  /**
   * Compare two observation states (previous vs current) based on window metadata,
   * text changes, and dimensions. Computes delta magnitude and affected regions.
   */
  public computeDelta(
    prev: { textContent: string; activeWindow: ActiveWindowInfo; width: number; height: number } | null,
    curr: { textContent: string; activeWindow: ActiveWindowInfo; width: number; height: number }
  ): VisualDelta {
    if (!prev) {
      return {
        changed: true,
        magnitude: 1.0,
        regions: [{ x: 0, y: 0, width: curr.width, height: curr.height }],
        likelyEvent: 'INITIAL_SCREEN_CAPTURE',
        confidence: 1.0,
      };
    }

    const appChanged = prev.activeWindow.application !== curr.activeWindow.application;
    const titleChanged = prev.activeWindow.title !== curr.activeWindow.title;
    const textChanged = prev.textContent !== curr.textContent;

    // Estimate text difference ratio
    let textDiffScore = 0;
    if (textChanged) {
      const prevLen = prev.textContent.length;
      const currLen = curr.textContent.length;
      const lenDiff = Math.abs(prevLen - currLen);
      textDiffScore = Math.min(1.0, (lenDiff + 50) / (Math.max(prevLen, currLen) + 1));
    }

    let magnitude = 0.0;
    const regions: ScreenRegion[] = [];
    let likelyEvent = 'NO_CHANGE';

    if (appChanged) {
      magnitude = 0.85;
      likelyEvent = 'APPLICATION_SWITCH';
      regions.push({ x: 0, y: 0, width: curr.width, height: curr.height });
    } else if (titleChanged) {
      magnitude = 0.5;
      likelyEvent = 'WINDOW_TITLE_OR_TAB_CHANGE';
      regions.push({ x: 0, y: 0, width: curr.width, height: 80 }); // Top header/titlebar area
    } else if (textChanged) {
      magnitude = Math.max(0.05, textDiffScore);
      likelyEvent = 'CONTENT_TEXT_MODIFIED';
      regions.push({ x: 0, y: 80, width: curr.width, height: curr.height - 80 });
    }

    const changed = magnitude >= this.threshold;

    return {
      changed,
      magnitude: Math.round(magnitude * 1000) / 1000,
      regions,
      likelyEvent,
      confidence: 0.95,
    };
  }

  /**
   * Fast byte-level buffer difference when raw pixel buffers are provided.
   */
  public computeBufferDifference(bufA?: Buffer, bufB?: Buffer): number {
    if (!bufA || !bufB || bufA.length === 0 || bufB.length === 0) return 0;
    if (bufA.length !== bufB.length) return 1.0;

    let diffCount = 0;
    const sampleStep = 16; // Sample every 16th byte for sub-millisecond check
    const totalSamples = Math.floor(bufA.length / sampleStep);

    for (let i = 0; i < bufA.length; i += sampleStep) {
      if (Math.abs(bufA[i] - bufB[i]) > 15) {
        diffCount++;
      }
    }

    return totalSamples > 0 ? diffCount / totalSamples : 0;
  }
}
