// ============================================================================
// MYRAA Phase 25 — State Estimator: Observe → Estimate → Version
// ============================================================================

import type {
  StateSnapshot, StateVersion, WindowStateSnapshot, ScreenStateSnapshot,
  FocusStateSnapshot, TargetStateSnapshot, ProcessStateSnapshot,
  FileStateSnapshot, BrowserStateSnapshot, DialogInfo,
} from './contracts';

// ============================================================================
// State Estimator
// ============================================================================

export class StateEstimator {
  private currentState: StateSnapshot | null = null;
  private history: StateSnapshot[] = [];
  private maxHistory = 50;

  // --- Core ---

  estimate(observations: StateObservations): StateSnapshot {
    const prevVersion = this.currentState?.version ?? 0;
    const newVersion = prevVersion + 1;

    const snapshot: StateSnapshot = {
      version: newVersion,
      timestamp: new Date().toISOString(),
      hash: this.computeHash(observations),
      windowState: this.estimateWindowState(observations),
      screenState: this.estimateScreenState(observations),
      focusState: this.estimateFocusState(observations),
      targetState: this.estimateTargetState(observations),
      processState: this.estimateProcessState(observations),
      fileState: this.estimateFileState(observations),
      browserState: this.estimateBrowserState(observations),
      pendingDialogs: this.estimateDialogs(observations),
    };

    this.currentState = snapshot;
    this.history.push(snapshot);
    if (this.history.length > this.maxHistory) this.history.shift();

    return snapshot;
  }

  getCurrentState(): StateSnapshot | null {
    return this.currentState;
  }

  getHistory(): readonly StateSnapshot[] {
    return this.history;
  }

  getStateByVersion(version: StateVersion): StateSnapshot | undefined {
    return this.history.find(s => s.version === version);
  }

  getLatestVersion(): StateVersion {
    return this.currentState?.version ?? 0;
  }

  // --- State Estimation Helpers ---

  private estimateWindowState(obs: StateObservations): WindowStateSnapshot {
    return {
      hwnd: obs.activeWindow?.hwnd ?? null,
      title: obs.activeWindow?.title ?? '',
      processName: obs.activeWindow?.processName ?? '',
      bounds: obs.activeWindow?.bounds ?? { x: 0, y: 0, width: 0, height: 0 },
      state: obs.activeWindow?.state ?? 'NORMAL',
      visible: obs.activeWindow?.visible ?? false,
    };
  }

  private estimateScreenState(obs: StateObservations): ScreenStateSnapshot {
    return {
      monitorCount: obs.screens?.length ?? 1,
      activeMonitor: obs.activeMonitorIndex ?? 0,
      resolution: obs.screens?.[0]?.resolution ?? { width: 1920, height: 1080 },
      dpi: obs.screens?.[0]?.dpi ?? 96,
      scaleFactor: obs.screens?.[0]?.scaleFactor ?? 1.0,
    };
  }

  private estimateFocusState(obs: StateObservations): FocusStateSnapshot {
    return {
      focusedHwnd: obs.activeWindow?.hwnd ?? null,
      focusedTitle: obs.activeWindow?.title ?? '',
      focusedProcess: obs.activeWindow?.processName ?? '',
      ownsInput: obs.inputOwnsMouse || obs.inputOwnsKeyboard,
    };
  }

  private estimateTargetState(obs: StateObservations): TargetStateSnapshot {
    return {
      targetId: obs.currentTarget?.id ?? null,
      targetLabel: obs.currentTarget?.label ?? '',
      targetBounds: obs.currentTarget?.bounds ?? null,
      targetVisible: obs.currentTarget?.visible ?? false,
      targetEnabled: obs.currentTarget?.enabled ?? false,
      targetConfidence: obs.currentTarget?.confidence ?? 0,
      targetSource: obs.currentTarget?.source ?? '',
      lastVerifiedAt: obs.currentTarget?.lastVerifiedAt ?? null,
    };
  }

  private estimateProcessState(obs: StateObservations): ProcessStateSnapshot {
    return {
      running: obs.processRunning ?? false,
      pid: obs.processPid ?? null,
      responsive: obs.processResponsive ?? true,
    };
  }

  private estimateFileState(obs: StateObservations): FileStateSnapshot {
    return {
      exists: obs.fileExists ?? false,
      lastModified: obs.fileLastModified ?? null,
      size: obs.fileSize ?? null,
    };
  }

  private estimateBrowserState(obs: StateObservations): BrowserStateSnapshot {
    return {
      url: obs.browserUrl ?? null,
      title: obs.browserTitle ?? null,
      ready: obs.browserReady ?? false,
      domElementCount: obs.domElementCount ?? 0,
    };
  }

  private estimateDialogs(obs: StateObservations): readonly DialogInfo[] {
    return obs.pendingDialogs ?? [];
  }

  private computeHash(obs: StateObservations): string {
    const parts = [
      obs.activeWindow?.title ?? '',
      obs.activeWindow?.processName ?? '',
      obs.currentTarget?.id ?? '',
      obs.browserUrl ?? '',
      String(obs.fileExists ?? false),
      String(obs.processRunning ?? false),
      String(Date.now()),
    ];
    return parts.join('|');
  }

  // --- Staleness ---

  isStateStale(maxAgeMs = 5000): boolean {
    if (!this.currentState) return true;
    return Date.now() - new Date(this.currentState.timestamp).getTime() > maxAgeMs;
  }

  clear(): void {
    this.currentState = null;
    this.history = [];
  }
}

// ============================================================================
// State Observations Input
// ============================================================================

export interface StateObservations {
  readonly activeWindow?: {
    readonly hwnd: number;
    readonly title: string;
    readonly processName: string;
    readonly bounds: { x: number; y: number; width: number; height: number };
    readonly state: 'NORMAL' | 'MINIMIZED' | 'MAXIMIZED' | 'HIDDEN';
    readonly visible: boolean;
  };
  readonly screens?: readonly {
    readonly resolution: { width: number; height: number };
    readonly dpi: number;
    readonly scaleFactor: number;
  }[];
  readonly activeMonitorIndex?: number;
  readonly currentTarget?: {
    readonly id: string;
    readonly label: string;
    readonly bounds: { x: number; y: number; width: number; height: number } | null;
    readonly visible: boolean;
    readonly enabled: boolean;
    readonly confidence: number;
    readonly source: string;
    readonly lastVerifiedAt: string | null;
  };
  readonly inputOwnsMouse?: boolean;
  readonly inputOwnsKeyboard?: boolean;
  readonly processRunning?: boolean;
  readonly processPid?: number | null;
  readonly processResponsive?: boolean;
  readonly fileExists?: boolean;
  readonly fileLastModified?: string | null;
  readonly fileSize?: number | null;
  readonly browserUrl?: string | null;
  readonly browserTitle?: string | null;
  readonly browserReady?: boolean;
  readonly domElementCount?: number;
  readonly pendingDialogs?: readonly DialogInfo[];
}
