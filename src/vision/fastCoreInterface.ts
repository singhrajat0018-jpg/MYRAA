// ============================================================================
// MYRAA FastCore Vision Integration Interface
// ============================================================================

import type { ObservedScene, FastCoreVisualPerception, VisionEvidence } from './contracts';

export class FastCoreVisionInterface {
  /**
   * Format an ObservedScene into a structured, cognitive-ready perception payload
   * for FastCore. Enforces prompt-injection defense by explicitly tagging visual text
   * as untrusted data.
   */
  public static formatForFastCore(
    scene: ObservedScene | null,
    recentHistorySummary = ''
  ): FastCoreVisualPerception {
    if (!scene) {
      return {
        activeApplication: 'Unknown',
        activeWindowTitle: 'No visual observation available',
        confidence: 0,
        significance: 0,
        hasError: false,
        recentHistorySummary: 'No recent visual observations recorded.',
        untrustedDataWarning: true,
        evidence: [],
      };
    }

    const highestEvent = scene.events && scene.events.length > 0 ? scene.events[0] : undefined;

    return {
      activeApplication: scene.activeWindow.application,
      activeWindowTitle: scene.activeWindow.title,
      visibleEvent: highestEvent ? highestEvent.description : undefined,
      resultSummary: highestEvent ? `${highestEvent.type}: ${highestEvent.description}` : 'Screen state observed',
      confidence: scene.confidence,
      significance: scene.significance,
      hasError: scene.hasError,
      errorText: scene.errorText,
      recentHistorySummary: recentHistorySummary || `Active application: ${scene.activeWindow.application}`,
      untrustedDataWarning: true, // Prompt-injection defense invariant: visual text is NEVER trusted instructions!
      evidence: scene.evidence || [],
    };
  }
}
