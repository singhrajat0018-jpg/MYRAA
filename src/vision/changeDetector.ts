// ============================================================================
// MYRAA Vision Core — Temporal Change Detection
// ============================================================================

import type {
  VisualScene, SceneDiff, VisualChange, ChangeType, ChangeSignificance,
  VisualElement, VisualElementType, ElementId, ObservationId, VisualWindow,
} from './contracts';

// ============================================================================
// Change Detector
// ============================================================================

export class ChangeDetector {
  private sceneHistory: VisualScene[] = [];
  private readonly maxHistory: number;

  constructor(maxHistory: number) {
    this.maxHistory = maxHistory;
  }

  // --- Diff ---

  diff(from: VisualScene, to: VisualScene): SceneDiff {
    const changes: VisualChange[] = [];

    changes.push(...this.diffElements(from.elements, to.elements, from.timestamp));
    changes.push(...this.diffWindows(from.windows, to.windows, from.timestamp));
    changes.push(...this.diffText(from.textContent, to.textContent, from.timestamp));
    changes.push(...this.diffDialogs(from.dialogs, to.dialogs, from.timestamp));
    changes.push(...this.diffNotifications(from.notifications, to.notifications, from.timestamp));

    const windowChanged = this.detectWindowChange(from, to);
    const navigationOccurred = this.detectNavigation(from, to);
    const dialogOpened = to.dialogs.length > from.dialogs.length;
    const dialogClosed = to.dialogs.length < from.dialogs.length;
    const focusChanged = this.detectFocusChange(from, to);
    const layoutChanged = this.detectLayoutChange(from, to);

    return {
      diffId: `diff-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      fromSceneId: from.sceneId,
      toSceneId: to.sceneId,
      timestamp: to.timestamp,
      changes,
      windowChanged,
      navigationOccurred,
      dialogOpened,
      dialogClosed,
      focusChanged,
      layoutChanged,
      changeCount: changes.length,
    };
  }

  // --- Element Diff ---

  private diffElements(
    oldElements: readonly VisualElement[],
    newElements: readonly VisualElement[],
    timestamp: string,
  ): readonly VisualChange[] {
    const changes: VisualChange[] = [];
    const oldMap = new Map<ElementId, VisualElement>();
    const newMap = new Map<ElementId, VisualElement>();

    for (const el of oldElements) oldMap.set(el.elementId, el);
    for (const el of newElements) newMap.set(el.elementId, el);

    for (const [id, newEl] of newMap) {
      const oldEl = oldMap.get(id);
      if (!oldEl) {
        changes.push(this.createChange('ADDED', newEl.type, id, null, newEl, timestamp, 'minor'));
        continue;
      }

      const positionChanged = oldEl.bounds.x !== newEl.bounds.x || oldEl.bounds.y !== newEl.bounds.y;
      const sizeChanged = oldEl.bounds.width !== newEl.bounds.width || oldEl.bounds.height !== newEl.bounds.height;
      const textChanged = oldEl.text !== newEl.text;
      const focusChanged = oldEl.isFocused !== newEl.isFocused;
      const selectedChanged = oldEl.isSelected !== newEl.isSelected;
      const visibilityChanged = oldEl.isVisible !== newEl.isVisible;
      const enabledChanged = oldEl.isEnabled !== newEl.isEnabled;

      if (visibilityChanged && !newEl.isVisible) {
        changes.push(this.createChange('REMOVED', newEl.type, id, oldEl, newEl, timestamp, 'minor'));
        continue;
      }

      if (focusChanged) {
        changes.push(this.createChange(
          newEl.isFocused ? 'FOCUSED' : 'UNFOCUSED',
          newEl.type, id, oldEl, newEl, timestamp, 'trivial',
        ));
      }

      if (selectedChanged) {
        changes.push(this.createChange(
          newEl.isSelected ? 'SELECTED' : 'DESELECTED',
          newEl.type, id, oldEl, newEl, timestamp, 'trivial',
        ));
      }

      if (textChanged || positionChanged || sizeChanged || enabledChanged) {
        const significance = this.computeChangeSignificance(oldEl, newEl, {
          textChanged, positionChanged, sizeChanged, enabledChanged,
        });
        changes.push(this.createChange('CHANGED', newEl.type, id, oldEl, newEl, timestamp, significance));
      }
    }

    for (const [id, oldEl] of oldMap) {
      if (!newMap.has(id)) {
        changes.push(this.createChange('REMOVED', oldEl.type, id, oldEl, null, timestamp, 'minor'));
      }
    }

    return changes;
  }

  // --- Window Diff ---

  private diffWindows(
    oldWindows: readonly VisualWindow[],
    newWindows: readonly VisualWindow[],
    timestamp: string,
  ): readonly VisualChange[] {
    const changes: VisualChange[] = [];
    const oldMap = new Map<string, VisualWindow>();
    const newMap = new Map<string, VisualWindow>();

    for (const w of oldWindows) oldMap.set(w.windowId, w);
    for (const w of newWindows) newMap.set(w.windowId, w);

    for (const [id, newWin] of newMap) {
      const oldWin = oldMap.get(id);
      if (!oldWin) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'OPENED',
          elementType: 'WINDOW',
          elementId: null,
          previousState: null,
          currentState: { text: newWin.title } as Partial<VisualElement>,
          timestamp,
          significance: 'moderate',
        });
        continue;
      }

      if (oldWin.isFocused !== newWin.isFocused) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: newWin.isFocused ? 'FOCUSED' : 'UNFOCUSED',
          elementType: 'WINDOW',
          elementId: null,
          previousState: { text: oldWin.title } as Partial<VisualElement>,
          currentState: { text: newWin.title } as Partial<VisualElement>,
          timestamp,
          significance: 'trivial',
        });
      }

      if (oldWin.title !== newWin.title) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'NAVIGATED',
          elementType: 'WINDOW',
          elementId: null,
          previousState: { text: oldWin.title } as Partial<VisualElement>,
          currentState: { text: newWin.title } as Partial<VisualElement>,
          timestamp,
          significance: 'moderate',
        });
      }
    }

    for (const [id, oldWin] of oldMap) {
      if (!newMap.has(id)) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'CLOSED',
          elementType: 'WINDOW',
          elementId: null,
          previousState: { text: oldWin.title } as Partial<VisualElement>,
          currentState: null,
          timestamp,
          significance: 'moderate',
        });
      }
    }

    return changes;
  }

  // --- Text Diff ---

  private diffText(
    oldText: string,
    newText: string,
    timestamp: string,
  ): readonly VisualChange[] {
    if (oldText === newText) return [];

    return [{
      changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type: 'CHANGED',
      elementType: 'TEXT_BLOCK',
      elementId: null,
      previousState: { text: oldText.slice(0, 256) } as Partial<VisualElement>,
      currentState: { text: newText.slice(0, 256) } as Partial<VisualElement>,
      timestamp,
      significance: oldText.length > 0 && newText.length > 0 ? 'minor' : 'trivial',
    }];
  }

  // --- Dialog Diff ---

  private diffDialogs(
    oldDialogs: readonly import('./contracts').VisualDialog[],
    newDialogs: readonly import('./contracts').VisualDialog[],
    timestamp: string,
  ): readonly VisualChange[] {
    const changes: VisualChange[] = [];

    for (const d of newDialogs) {
      if (!oldDialogs.some(od => od.dialogId === d.dialogId)) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'OPENED',
          elementType: 'DIALOG',
          elementId: null,
          previousState: null,
          currentState: { text: d.title } as Partial<VisualElement>,
          timestamp,
          significance: 'major',
        });
      }
    }

    for (const d of oldDialogs) {
      if (!newDialogs.some(nd => nd.dialogId === d.dialogId)) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'CLOSED',
          elementType: 'DIALOG',
          elementId: null,
          previousState: { text: d.title } as Partial<VisualElement>,
          currentState: null,
          timestamp,
          significance: 'moderate',
        });
      }
    }

    return changes;
  }

  // --- Notification Diff ---

  private diffNotifications(
    oldNotifs: readonly import('./contracts').VisualNotification[],
    newNotifs: readonly import('./contracts').VisualNotification[],
    timestamp: string,
  ): readonly VisualChange[] {
    const changes: VisualChange[] = [];

    for (const n of newNotifs) {
      if (!oldNotifs.some(on => on.notificationId === n.notificationId)) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'ADDED',
          elementType: 'NOTIFICATION',
          elementId: null,
          previousState: null,
          currentState: { text: n.text } as Partial<VisualElement>,
          timestamp,
          significance: n.severity === 'error' ? 'major' : 'minor',
        });
      }
    }

    for (const n of oldNotifs) {
      if (!newNotifs.some(nn => nn.notificationId === n.notificationId)) {
        changes.push({
          changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'REMOVED',
          elementType: 'NOTIFICATION',
          elementId: null,
          previousState: { text: n.text } as Partial<VisualElement>,
          currentState: null,
          timestamp,
          significance: 'trivial',
        });
      }
    }

    return changes;
  }

  // --- Detection Helpers ---

  private detectWindowChange(from: VisualScene, to: VisualScene): boolean {
    if (from.windows.length !== to.windows.length) return true;

    const fromIds = from.windows.map(w => w.windowId).sort();
    const toIds = to.windows.map(w => w.windowId).sort();
    return fromIds.some((id, i) => id !== toIds[i]);
  }

  private detectNavigation(from: VisualScene, to: VisualScene): boolean {
    if (!from.activeWindow || !to.activeWindow) {
      return from.activeWindow !== to.activeWindow;
    }
    return from.activeWindow.title !== to.activeWindow.title ||
           from.activeWindow.processName !== to.activeWindow.processName;
  }

  private detectFocusChange(from: VisualScene, to: VisualScene): boolean {
    const fromFocused = from.elements.find(e => e.isFocused);
    const toFocused = to.elements.find(e => e.isFocused);

    if (!fromFocused && !toFocused) return false;
    if (!fromFocused || !toFocused) return true;

    return fromFocused.elementId !== toFocused.elementId;
  }

  private detectLayoutChange(from: VisualScene, to: VisualScene): boolean {
    if (from.elements.length !== to.elements.length) return true;

    const fromBounds = from.elements.map(e => `${e.bounds.x},${e.bounds.y}`).sort().join('|');
    const toBounds = to.elements.map(e => `${e.bounds.x},${e.bounds.y}`).sort().join('|');

    return fromBounds !== toBounds;
  }

  // --- Significance ---

  private computeChangeSignificance(
    oldEl: VisualElement,
    newEl: VisualElement,
    diffs: { textChanged: boolean; positionChanged: boolean; sizeChanged: boolean; enabledChanged: boolean },
  ): ChangeSignificance {
    if (diffs.enabledChanged) return 'major';
    if (diffs.textChanged && oldEl.type === 'BUTTON') return 'moderate';
    if (diffs.positionChanged) return 'minor';
    if (diffs.textChanged) return 'minor';
    if (diffs.sizeChanged) return 'trivial';
    return 'trivial';
  }

  private createChange(
    type: ChangeType,
    elementType: VisualElementType,
    elementId: ElementId | null,
    previousState: VisualElement | null,
    currentState: VisualElement | null,
    timestamp: string,
    significance: ChangeSignificance,
  ): VisualChange {
    return {
      changeId: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type,
      elementType,
      elementId,
      previousState,
      currentState,
      timestamp,
      significance,
    };
  }

  // --- History Management ---

  pushScene(scene: VisualScene): void {
    this.sceneHistory.push(scene);
    if (this.sceneHistory.length > this.maxHistory) {
      this.sceneHistory = this.sceneHistory.slice(-this.maxHistory);
    }
  }

  getHistory(): readonly VisualScene[] {
    return this.sceneHistory;
  }

  getRecentChanges(count: number): readonly VisualChange[] {
    const changes: VisualChange[] = [];
    for (let i = this.sceneHistory.length - 1; i > 0 && changes.length < count; i--) {
      const diff = this.diff(this.sceneHistory[i - 1], this.sceneHistory[i]);
      changes.push(...diff.changes);
    }
    return changes;
  }

  clearHistory(): void {
    this.sceneHistory = [];
  }
}
