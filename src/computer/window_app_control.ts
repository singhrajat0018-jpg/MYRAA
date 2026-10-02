// ============================================================================
// MYRAA Window & Application Control
// ============================================================================

import type { WindowInfo, ApplicationInfo, AppReadiness, WindowState } from './contracts';

// ============================================================================
// Window Control
// ============================================================================

export interface WindowControlResult {
  readonly success: boolean;
  readonly windowId: number;
  readonly operation: string;
  readonly newState?: WindowState;
  readonly error?: string;
}

export class WindowControl {
  private knownWindows: Map<number, WindowInfo> = new Map();
  private lastScanAt = 0;
  private scanIntervalMs = 2000;

  // --- Window Operations ---

  async focusWindow(hwnd: number): Promise<WindowControlResult> {
    const win = this.knownWindows.get(hwnd);
    if (!win) return { success: false, windowId: hwnd, operation: 'focus', error: 'Window not found' };
    if (!win.visible) return { success: false, windowId: hwnd, operation: 'focus', error: 'Window not visible' };
    // Actual execution via Python — this is the TypeScript state model
    return { success: true, windowId: hwnd, operation: 'focus', newState: 'NORMAL' };
  }

  async minimizeWindow(hwnd: number): Promise<WindowControlResult> {
    const win = this.knownWindows.get(hwnd);
    if (!win) return { success: false, windowId: hwnd, operation: 'minimize', error: 'Window not found' };
    return { success: true, windowId: hwnd, operation: 'minimize', newState: 'MINIMIZED' };
  }

  async maximizeWindow(hwnd: number): Promise<WindowControlResult> {
    const win = this.knownWindows.get(hwnd);
    if (!win) return { success: false, windowId: hwnd, operation: 'maximize', error: 'Window not found' };
    return { success: true, windowId: hwnd, operation: 'maximize', newState: 'MAXIMIZED' };
  }

  async restoreWindow(hwnd: number): Promise<WindowControlResult> {
    const win = this.knownWindows.get(hwnd);
    if (!win) return { success: false, windowId: hwnd, operation: 'restore', error: 'Window not found' };
    return { success: true, windowId: hwnd, operation: 'restore', newState: 'NORMAL' };
  }

  async closeWindow(hwnd: number): Promise<WindowControlResult> {
    const win = this.knownWindows.get(hwnd);
    if (!win) return { success: false, windowId: hwnd, operation: 'close', error: 'Window not found' };
    return { success: true, windowId: hwnd, operation: 'close' };
  }

  // --- Window Search ---

  findWindowByTitle(title: string, exact = false): WindowInfo | undefined {
    for (const win of this.knownWindows.values()) {
      if (exact ? win.title === title : win.title.toLowerCase().includes(title.toLowerCase())) {
        return win;
      }
    }
    return undefined;
  }

  findWindowByProcess(processName: string): WindowInfo | undefined {
    const lower = processName.toLowerCase();
    for (const win of this.knownWindows.values()) {
      if (win.processName.toLowerCase().includes(lower)) return win;
    }
    return undefined;
  }

  getFocusedWindow(): WindowInfo | undefined {
    for (const win of this.knownWindows.values()) {
      if (win.focused) return win;
    }
    return undefined;
  }

  getAllWindows(): readonly WindowInfo[] {
    return [...this.knownWindows.values()];
  }

  // --- State Update ---

  updateWindows(windows: readonly WindowInfo[]): void {
    this.knownWindows.clear();
    for (const w of windows) this.knownWindows.set(w.hwnd, w);
    this.lastScanAt = Date.now();
  }

  isStale(): boolean {
    return Date.now() - this.lastScanAt > this.scanIntervalMs;
  }

  getWindow(hwnd: number): WindowInfo | undefined {
    return this.knownWindows.get(hwnd);
  }
}

// ============================================================================
// Application Control
// ============================================================================

export class ApplicationControl {
  private knownApps: Map<string, ApplicationInfo> = new Map();

  async openApp(name: string): Promise<{ success: boolean; appId: string; error?: string }> {
    const app = this.knownApps.get(name.toLowerCase());
    if (app && app.processId) {
      // Already running — focus it
      return { success: true, appId: name };
    }
    return { success: true, appId: name };
  }

  async closeApp(name: string): Promise<{ success: boolean; error?: string }> {
    const app = this.knownApps.get(name.toLowerCase());
    if (!app || !app.processId) {
      return { success: false, error: `Application "${name}" not running` };
    }
    return { success: true };
  }

  async getAppInfo(name: string): Promise<ApplicationInfo | undefined> {
    return this.knownApps.get(name.toLowerCase());
  }

  async isAppReady(name: string): Promise<boolean> {
    const app = this.knownApps.get(name.toLowerCase());
    return app?.readiness === 'READY';
  }

  updateApps(apps: readonly ApplicationInfo[]): void {
    this.knownApps.clear();
    for (const a of apps) this.knownApps.set(a.name.toLowerCase(), a);
  }

  getRunningApps(): readonly ApplicationInfo[] {
    return [...this.knownApps.values()].filter(a => a.processId !== null);
  }
}
