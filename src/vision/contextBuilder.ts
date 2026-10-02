// ============================================================================
// MYRAA Vision Core — Vision Context Builder
// ============================================================================

import type {
  VisualScene, VisionContext, VisualElement, VisualChange,
  ObservationId, MonitorId, ElementId,
} from './contracts';
import { CONFIDENCE_MEDIUM, SCREEN_TEXT_MAX_LENGTH } from './contracts';

// ============================================================================
// Context Builder
// ============================================================================

export class ContextBuilder {
  private readonly maxKeyElements: number;
  private readonly maxImportantControls: number;
  private readonly maxRecentChanges: number;
  private readonly textMaxLength: number;
  private readonly minConfidence: number;

  constructor(options?: {
    maxKeyElements?: number;
    maxImportantControls?: number;
    maxRecentChanges?: number;
    textMaxLength?: number;
    minConfidence?: number;
  }) {
    this.maxKeyElements = options?.maxKeyElements ?? 15;
    this.maxImportantControls = options?.maxImportantControls ?? 10;
    this.maxRecentChanges = options?.maxRecentChanges ?? 20;
    this.textMaxLength = options?.textMaxLength ?? SCREEN_TEXT_MAX_LENGTH;
    this.minConfidence = options?.minConfidence ?? CONFIDENCE_MEDIUM;
  }

  // --- Build ---

  build(
    scene: VisualScene,
    recentChanges?: readonly VisualChange[],
  ): VisionContext {
    const keyElements = this.extractKeyElements(scene);
    const importantControls = this.extractImportantControls(scene);
    const screenText = this.summarizeScreenText(scene);
    const changes = recentChanges ?? [];

    return {
      timestamp: scene.timestamp,
      sceneId: scene.sceneId,
      activeApplication: this.inferActiveApplication(scene),
      activeWindowTitle: scene.activeWindow?.title ?? '',
      screenText,
      keyElements,
      importantControls,
      currentDialog: scene.dialogs.length > 0 ? scene.dialogs[0] : null,
      notifications: scene.notifications,
      confidence: scene.confidence,
      monitorId: scene.monitorId,
      dpiScale: scene.dpiScale,
      recentChanges: changes.slice(0, this.maxRecentChanges),
    };
  }

  // --- Key Elements ---

  private extractKeyElements(scene: VisualScene): readonly VisualElement[] {
    const scored = scene.elements
      .filter(e => e.confidence >= this.minConfidence)
      .map(e => ({
        element: e,
        score: this.scoreElementImportance(e, scene),
      }))
      .sort((a, b) => b.score - a.score);

    return scored.slice(0, this.maxKeyElements).map(s => s.element);
  }

  private extractImportantControls(scene: VisualScene): readonly VisualElement[] {
    const interactableTypes = new Set([
      'BUTTON', 'TEXT_FIELD', 'LINK', 'TAB', 'DROPDOWN',
      'CHECKBOX', 'RADIO', 'COMBOBOX', 'SLIDER', 'TOGGLE',
      'MENU', 'LIST_ROW',
    ]);

    return scene.elements
      .filter(e =>
        interactableTypes.has(e.type) &&
        e.isClickable &&
        e.isEnabled &&
        e.isVisible &&
        e.confidence >= this.minConfidence
      )
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, this.maxImportantControls);
  }

  private scoreElementImportance(element: VisualElement, scene: VisualScene): number {
    let score = 0;

    if (element.isFocused) score += 3.0;
    if (element.isSelected) score += 1.5;
    if (element.isClickable) score += 0.5;
    if (element.isEnabled) score += 0.3;
    if (element.isVisible) score += 0.2;

    if (scene.activeWindow && this.elementInWindow(element, scene.activeWindow.bounds)) {
      score += 1.0;
    }

    const typeScores: Record<string, number> = {
      BUTTON: 2.0,
      DIALOG: 2.5,
      TEXT_FIELD: 1.5,
      DROPDOWN: 1.5,
      TAB: 1.2,
      CHECKBOX: 1.0,
      RADIO: 1.0,
      LINK: 0.8,
      MENU: 1.0,
      NOTIFICATION: 1.8,
      TOOLBAR: 0.5,
      PANEL: 0.3,
      TEXT_BLOCK: 0.4,
      IMAGE: 0.3,
      ICON: 0.2,
      WINDOW: 0.4,
      TABLE: 0.6,
      LIST_ROW: 0.7,
      SCROLLBAR: 0.2,
      COMBOBOX: 1.5,
      SLIDER: 1.0,
      TOGGLE: 1.0,
      PROGRESS: 0.3,
      TREE: 0.5,
      CARD: 0.5,
      UNKNOWN: 0.1,
    };
    score += typeScores[element.type] ?? 0.1;

    score *= element.confidence;

    return score;
  }

  private elementInWindow(element: VisualElement, windowBounds: { x: number; y: number; width: number; height: number }): boolean {
    return (
      element.bounds.x >= windowBounds.x &&
      element.bounds.y >= windowBounds.y &&
      element.bounds.x + element.bounds.width <= windowBounds.x + windowBounds.width &&
      element.bounds.y + element.bounds.height <= windowBounds.y + windowBounds.height
    );
  }

  // --- Text ---

  private summarizeScreenText(scene: VisualScene): string {
    const sorted = scene.ocrBlocks
      .slice()
      .sort((a, b) => a.readingOrder - b.readingOrder);

    const text = sorted.map(b => b.text).join('\n');
    if (text.length <= this.textMaxLength) return text;

    return text.slice(0, this.textMaxLength) + '...';
  }

  // --- Application Inference ---

  private inferActiveApplication(scene: VisualScene): string {
    if (scene.activeWindow) {
      return scene.activeWindow.processName;
    }
    if (scene.windows.length > 0) {
      const focused = scene.windows.find(w => w.isFocused);
      if (focused) return focused.processName;
      return scene.windows[0].processName;
    }
    return '';
  }
}
