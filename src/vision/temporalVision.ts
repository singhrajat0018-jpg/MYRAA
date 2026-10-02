// ============================================================================
// MYRAA Temporal Vision Engine — Change Over Time & Visual History
// ============================================================================

import type { ObservedScene, VisualDelta, VisualEvent, VisionEvidence } from './contracts';

export class TemporalVisionEngine {
  private history: ObservedScene[] = [];
  private maxHistorySize = 50;

  /**
   * Record a new observed scene into temporal history, pruning oldest entries.
   */
  public recordScene(scene: ObservedScene): void {
    // Event compression: if identical to last scene, update timestamp instead of bloating array
    if (this.history.length > 0) {
      const last = this.history[this.history.length - 1];
      const isIdentical =
        last.activeWindow.application === scene.activeWindow.application &&
        last.activeWindow.title === scene.activeWindow.title &&
        last.textContent === scene.textContent &&
        (!scene.delta || !scene.delta.changed);

      if (isIdentical) {
        last.timestamp = scene.timestamp;
        return;
      }
    }

    this.history.push(scene);
    if (this.history.length > this.maxHistorySize) {
      this.history.shift();
    }
  }

  public getHistory(limit = 20): ObservedScene[] {
    return this.history.slice(-limit);
  }

  public getLatestScene(): ObservedScene | null {
    return this.history.length > 0 ? this.history[this.history.length - 1] : null;
  }

  /**
   * Diff two scenes from history.
   */
  public diffScenes(fromScene: ObservedScene, toScene: ObservedScene): {
    fromSceneId: string;
    toSceneId: string;
    timeDeltaMs: number;
    changed: boolean;
    appChanged: boolean;
    diffScore: number;
    events: VisualEvent[];
  } {
    const timeDeltaMs = toScene.timestamp - fromScene.timestamp;
    const appChanged = fromScene.activeWindow.application !== toScene.activeWindow.application;
    const titleChanged = fromScene.activeWindow.title !== toScene.activeWindow.title;
    const textChanged = fromScene.textContent !== toScene.textContent;

    const changed = appChanged || titleChanged || textChanged;
    const diffScore = appChanged ? 0.9 : titleChanged ? 0.5 : textChanged ? 0.3 : 0.0;

    return {
      fromSceneId: fromScene.sceneId,
      toSceneId: toScene.sceneId,
      timeDeltaMs,
      changed,
      appChanged,
      diffScore,
      events: toScene.events,
    };
  }

  /**
   * Query temporal evidence for a specific hypothesis or claim (e.g. "build failed", "terminal opened").
   */
  public findEvidence(claimKeyword: string): VisionEvidence[] {
    const kw = claimKeyword.toLowerCase();
    const evidenceList: VisionEvidence[] = [];

    for (let i = this.history.length - 1; i >= 0; i--) {
      const scene = this.history[i];
      // Check active window
      if (scene.activeWindow.application.toLowerCase().includes(kw) ||
          scene.activeWindow.title.toLowerCase().includes(kw)) {
        evidenceList.push({
          claim: `Window matched: ${scene.activeWindow.title}`,
          source: 'WINDOWS_API',
          timestamp: scene.timestamp,
          text: scene.activeWindow.title,
          confidence: 0.95,
        });
      }

      // Check OCR blocks
      for (const block of scene.ocrBlocks) {
        if (block.text.toLowerCase().includes(kw)) {
          evidenceList.push({
            claim: `On-screen text matched: "${block.text}"`,
            source: 'OCR',
            region: block.bbox,
            timestamp: scene.timestamp,
            text: block.text,
            confidence: block.confidence,
          });
          if (evidenceList.length >= 5) break;
        }
      }
      if (evidenceList.length >= 5) break;
    }

    return evidenceList;
  }
}
