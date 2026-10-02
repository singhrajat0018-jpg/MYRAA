// ============================================================================
// MYRAA Significance Engine — Filters Visual Noise & Flags Critical Events
// ============================================================================

import type { VisualEvent, VisualDelta, ActiveWindowInfo } from './contracts';

export interface SignificanceDecision {
  overallSignificance: number; // 0.0 to 1.0
  isSignificant: boolean;
  shouldNotifyCognition: boolean; // Should notify FastCore / SuperBrain
  shouldUpdateWorldModel: boolean;
  primaryReason: string;
}

export class SignificanceEngine {
  private significanceThreshold = 0.5;

  /**
   * Evaluate visual changes and events to determine overall significance.
   */
  public evaluate(
    events: VisualEvent[],
    delta?: VisualDelta,
    activeWindow?: ActiveWindowInfo
  ): SignificanceDecision {
    if (!events || events.length === 0) {
      return {
        overallSignificance: 0.0,
        isSignificant: false,
        shouldNotifyCognition: false,
        shouldUpdateWorldModel: false,
        primaryReason: 'No visual events detected',
      };
    }

    // Find highest scoring event
    let maxSig = 0.0;
    let highestEvent: VisualEvent = events[0];

    for (const ev of events) {
      if (ev.significance > maxSig) {
        maxSig = ev.significance;
        highestEvent = ev;
      }
    }

    // Suppress video/animation noise: if delta magnitude is large (>0.3) but window is video player
    // and no text/dialog/error was flagged, demote significance
    const isMedia = activeWindow && /youtube|netflix|spotify|vlc|media player/i.test(activeWindow.application + ' ' + activeWindow.title);
    if (isMedia && highestEvent.type === 'TEXT_CHANGED') {
      maxSig = Math.min(maxSig, 0.2);
    }

    const isSignificant = maxSig >= this.significanceThreshold;
    const isCritical = maxSig >= 0.8; // Errors, dialogs, build failures

    return {
      overallSignificance: Math.round(maxSig * 100) / 100,
      isSignificant,
      shouldNotifyCognition: isCritical,
      shouldUpdateWorldModel: isSignificant,
      primaryReason: highestEvent.description,
    };
  }
}
