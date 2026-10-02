// ============================================================================
// MYRAA Phase 25 — State Diff Engine: Compare expected vs actual state
// ============================================================================

import type {
  StateSnapshot, StateDiff, StateChange, StateChangeType, DialogInfo,
} from './contracts';

// ============================================================================
// State Diff Engine
// ============================================================================

export class StateDiffEngine {
  private diffHistory: StateDiff[] = [];
  private maxHistory = 100;

  // --- Core Diff ---

  diff(expected: StateSnapshot, actual: StateSnapshot): StateDiff {
    const changes: StateChange[] = [];

    // Window changes
    this.diffWindowState(expected.windowState, actual.windowState, changes);
    // Screen changes
    this.diffScreenState(expected.screenState, actual.screenState, changes);
    // Focus changes
    this.diffFocusState(expected.focusState, actual.focusState, changes);
    // Target changes
    this.diffTargetState(expected.targetState, actual.targetState, changes);
    // Process changes
    this.diffProcessState(expected.processState, actual.processState, changes);
    // File changes
    this.diffFileState(expected.fileState, actual.fileState, changes);
    // Browser changes
    this.diffBrowserState(expected.browserState, actual.browserState, changes);
    // Dialog changes
    this.diffDialogs(expected.pendingDialogs, actual.pendingDialogs, changes);

    const material = changes.some(c => c.material);

    const diff: StateDiff = {
      fromVersion: expected.version,
      toVersion: actual.version,
      changes,
      material,
      timestamp: new Date().toISOString(),
    };

    this.diffHistory.push(diff);
    if (this.diffHistory.length > this.maxHistory) this.diffHistory.shift();

    return diff;
  }

  // --- Window Diff ---

  private diffWindowState(
    expected: StateSnapshot['windowState'],
    actual: StateSnapshot['windowState'],
    changes: StateChange[],
  ): void {
    if (expected.hwnd !== actual.hwnd) {
      changes.push(this.makeChange('FOCUS_CHANGED', 'windowState.hwnd', expected.hwnd, actual.hwnd, true,
        `Window changed: ${expected.title} → ${actual.title}`));
    }
    if (expected.title !== actual.title) {
      changes.push(this.makeChange('WINDOW_STATE_CHANGED', 'windowState.title', expected.title, actual.title, true,
        `Window title changed: "${expected.title}" → "${actual.title}"`));
    }
    if (expected.state !== actual.state) {
      changes.push(this.makeChange('WINDOW_STATE_CHANGED', 'windowState.state', expected.state, actual.state, true,
        `Window state: ${expected.state} → ${actual.state}`));
    }
    if (expected.visible !== actual.visible) {
      changes.push(this.makeChange(
        actual.visible ? 'WINDOW_OPENED' : 'WINDOW_CLOSED',
        'windowState.visible', expected.visible, actual.visible, true,
        `Window visibility: ${expected.visible} → ${actual.visible}`));
    }
    if (expected.bounds.x !== actual.bounds.x || expected.bounds.y !== actual.bounds.y) {
      changes.push(this.makeChange('WINDOW_MOVED', 'windowState.bounds',
        expected.bounds, actual.bounds, true,
        `Window moved: (${expected.bounds.x},${expected.bounds.y}) → (${actual.bounds.x},${actual.bounds.y})`));
    }
    if (expected.bounds.width !== actual.bounds.width || expected.bounds.height !== actual.bounds.height) {
      changes.push(this.makeChange('WINDOW_RESIZED', 'windowState.bounds',
        expected.bounds, actual.bounds, true,
        `Window resized: ${expected.bounds.width}x${expected.bounds.height} → ${actual.bounds.width}x${actual.bounds.height}`));
    }
  }

  // --- Screen Diff ---

  private diffScreenState(
    expected: StateSnapshot['screenState'],
    actual: StateSnapshot['screenState'],
    changes: StateChange[],
  ): void {
    if (expected.dpi !== actual.dpi) {
      changes.push(this.makeChange('DPI_CHANGED', 'screenState.dpi', expected.dpi, actual.dpi, true,
        `DPI changed: ${expected.dpi} → ${actual.dpi}`));
    }
    if (expected.monitorCount !== actual.monitorCount) {
      changes.push(this.makeChange('MONITOR_CHANGED', 'screenState.monitorCount', expected.monitorCount, actual.monitorCount, true,
        `Monitor count: ${expected.monitorCount} → ${actual.monitorCount}`));
    }
    if (expected.activeMonitor !== actual.activeMonitor) {
      changes.push(this.makeChange('MONITOR_CHANGED', 'screenState.activeMonitor', expected.activeMonitor, actual.activeMonitor, false,
        `Active monitor: ${expected.activeMonitor} → ${actual.activeMonitor}`));
    }
  }

  // --- Focus Diff ---

  private diffFocusState(
    expected: StateSnapshot['focusState'],
    actual: StateSnapshot['focusState'],
    changes: StateChange[],
  ): void {
    if (expected.focusedHwnd !== actual.focusedHwnd) {
      changes.push(this.makeChange('FOCUS_CHANGED', 'focusState.focusedHwnd', expected.focusedHwnd, actual.focusedHwnd, true,
        `Focus changed: ${expected.focusedTitle} → ${actual.focusedTitle}`));
    }
  }

  // --- Target Diff ---

  private diffTargetState(
    expected: StateSnapshot['targetState'],
    actual: StateSnapshot['targetState'],
    changes: StateChange[],
  ): void {
    if (expected.targetId !== actual.targetId) {
      changes.push(this.makeChange('ELEMENT_DISAPPEARED', 'targetState.targetId', expected.targetId, actual.targetId, true,
        `Target changed: ${expected.targetLabel} → ${actual.targetLabel}`));
    }
    if (expected.targetVisible !== actual.targetVisible) {
      changes.push(this.makeChange(
        actual.targetVisible ? 'ELEMENT_APPEARED' : 'ELEMENT_DISAPPEARED',
        'targetState.targetVisible', expected.targetVisible, actual.targetVisible, true,
        `Target visibility: ${expected.targetVisible} → ${actual.targetVisible}`));
    }
    if (expected.targetEnabled !== actual.targetEnabled) {
      changes.push(this.makeChange('ELEMENT_STATE_CHANGED', 'targetState.targetEnabled', expected.targetEnabled, actual.targetEnabled, true,
        `Target enabled: ${expected.targetEnabled} → ${actual.targetEnabled}`));
    }
    if (expected.targetConfidence !== actual.targetConfidence) {
      const material = Math.abs(expected.targetConfidence - actual.targetConfidence) > 0.2;
      changes.push(this.makeChange('TARGET_CONFIDENCE_CHANGED', 'targetState.targetConfidence', expected.targetConfidence, actual.targetConfidence, material,
        `Target confidence: ${expected.targetConfidence.toFixed(2)} → ${actual.targetConfidence.toFixed(2)}`));
    }
    if (expected.targetBounds && actual.targetBounds) {
      const moved = expected.targetBounds.x !== actual.targetBounds.x || expected.targetBounds.y !== actual.targetBounds.y;
      if (moved) {
        changes.push(this.makeChange('ELEMENT_MOVED', 'targetState.targetBounds', expected.targetBounds, actual.targetBounds, true,
          `Target moved: (${expected.targetBounds.x},${expected.targetBounds.y}) → (${actual.targetBounds.x},${actual.targetBounds.y})`));
      }
    }
  }

  // --- Process Diff ---

  private diffProcessState(
    expected: StateSnapshot['processState'],
    actual: StateSnapshot['processState'],
    changes: StateChange[],
  ): void {
    if (expected.running !== actual.running) {
      changes.push(this.makeChange(
        actual.running ? 'PROCESS_STARTED' : 'PROCESS_EXITED',
        'processState.running', expected.running, actual.running, true,
        `Process: ${expected.running ? 'running' : 'stopped'} → ${actual.running ? 'running' : 'stopped'}`));
    }
    if (expected.responsive !== actual.responsive) {
      changes.push(this.makeChange('PROCESS_UNRESPONSIVE', 'processState.responsive', expected.responsive, actual.responsive, true,
        `Process responsive: ${expected.responsive} → ${actual.responsive}`));
    }
  }

  // --- File Diff ---

  private diffFileState(
    expected: StateSnapshot['fileState'],
    actual: StateSnapshot['fileState'],
    changes: StateChange[],
  ): void {
    if (expected.exists !== actual.exists) {
      changes.push(this.makeChange(
        actual.exists ? 'FILE_CREATED' : 'FILE_DELETED',
        'fileState.exists', expected.exists, actual.exists, true,
        `File exists: ${expected.exists} → ${actual.exists}`));
    }
    if (expected.lastModified !== actual.lastModified) {
      changes.push(this.makeChange('FILE_MODIFIED', 'fileState.lastModified', expected.lastModified, actual.lastModified, false,
        `File modified: ${expected.lastModified} → ${actual.lastModified}`));
    }
  }

  // --- Browser Diff ---

  private diffBrowserState(
    expected: StateSnapshot['browserState'],
    actual: StateSnapshot['browserState'],
    changes: StateChange[],
  ): void {
    if (expected.url !== actual.url) {
      changes.push(this.makeChange('URL_CHANGED', 'browserState.url', expected.url, actual.url, true,
        `URL changed: ${expected.url} → ${actual.url}`));
    }
    if (expected.title !== actual.title) {
      changes.push(this.makeChange('PAGE_CHANGED', 'browserState.title', expected.title, actual.title, false,
        `Page title changed: "${expected.title}" → "${actual.title}"`));
    }
    if (expected.domElementCount !== actual.domElementCount) {
      const diff = Math.abs((expected.domElementCount ?? 0) - (actual.domElementCount ?? 0));
      if (diff > 10) {
        changes.push(this.makeChange('DOM_CHANGED', 'browserState.domElementCount', expected.domElementCount, actual.domElementCount, false,
          `DOM elements: ${expected.domElementCount} → ${actual.domElementCount}`));
      }
    }
  }

  // --- Dialog Diff ---

  private diffDialogs(
    expected: readonly DialogInfo[],
    actual: readonly DialogInfo[],
    changes: StateChange[],
  ): void {
    const expectedTitles = new Set(expected.map(d => d.title));
    const actualTitles = new Set(actual.map(d => d.title));

    for (const dialog of actual) {
      if (!expectedTitles.has(dialog.title)) {
        changes.push(this.makeChange('DIALOG_APPEARED', 'pendingDialogs', null, dialog, true,
          `Dialog appeared: "${dialog.title}"`));
      }
    }
    for (const dialog of expected) {
      if (!actualTitles.has(dialog.title)) {
        changes.push(this.makeChange('DIALOG_DISMISSED', 'pendingDialogs', dialog, null, false,
          `Dialog dismissed: "${dialog.title}"`));
      }
    }
  }

  // --- Helpers ---

  private makeChange(
    type: StateChangeType,
    field: string,
    oldValue: unknown,
    newValue: unknown,
    material: boolean,
    description: string,
  ): StateChange {
    return { type, field, oldValue, newValue, material, description };
  }

  // --- Materiality ---

  hasMaterialChanges(diff: StateDiff): boolean {
    return diff.material;
  }

  getMaterialChanges(diff: StateDiff): readonly StateChange[] {
    return diff.changes.filter(c => c.material);
  }

  getChangesByType(diff: StateDiff, type: StateChangeType): readonly StateChange[] {
    return diff.changes.filter(c => c.type === type);
  }

  // --- History ---

  getDiffHistory(): readonly StateDiff[] {
    return this.diffHistory;
  }

  clearHistory(): void {
    this.diffHistory = [];
  }
}
