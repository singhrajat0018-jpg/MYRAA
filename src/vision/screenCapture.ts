// ============================================================================
// MYRAA Vision Core — Screen Capture Adapter
// ============================================================================

import type {
  MonitorInfo, MonitorId, ScreenCapture, CaptureRegion, Bounds,
} from './contracts';
import { monitorId } from './contracts';

// ============================================================================
// Capture Adapter Interface
// ============================================================================

export interface IScreenCaptureAdapter {
  getMonitors(): Promise<readonly MonitorInfo[]>;
  captureMonitor(monitorId: MonitorId): Promise<ScreenCapture>;
  captureRegion(region: CaptureRegion, monitorId: MonitorId): Promise<ScreenCapture>;
  captureAll(): Promise<readonly ScreenCapture[]>;
  isAvailable(): boolean;
}

// ============================================================================
// Mock/Demo Adapter — Generates placeholder captures for development
// ============================================================================

export class MockScreenCaptureAdapter implements IScreenCaptureAdapter {
  private monitors: MonitorInfo[];
  private captureCounter = 0;
  private lastCaptureHash = '';
  private unchangedCount = 0;

  constructor(monitors?: MonitorInfo[]) {
    this.monitors = monitors ?? [
      {
        id: monitorId('monitor-0'),
        index: 0,
        bounds: { x: 0, y: 0, width: 1920, height: 1080 },
        dpiScale: 1.0,
        isPrimary: true,
        orientation: 'landscape',
        colorDepth: 32,
      },
    ];
  }

  async getMonitors(): Promise<readonly MonitorInfo[]> {
    return this.monitors;
  }

  async captureMonitor(targetMonitorId: MonitorId): Promise<ScreenCapture> {
    const monitor = this.monitors.find(m => m.id === targetMonitorId);
    if (!monitor) {
      throw new Error(`Monitor not found: ${targetMonitorId}`);
    }

    this.captureCounter++;
    const now = new Date().toISOString();
    const width = Math.round(monitor.bounds.width * monitor.dpiScale);
    const height = Math.round(monitor.bounds.height * monitor.dpiScale);

    return {
      captureId: `capture-${this.captureCounter}-${Date.now()}`,
      timestamp: now,
      monitorId: targetMonitorId,
      bounds: monitor.bounds,
      dpiScale: monitor.dpiScale,
      imageData: this.generatePlaceholderImage(width, height),
      format: 'png',
      width,
      height,
    };
  }

  async captureRegion(region: CaptureRegion, targetMonitorId: MonitorId): Promise<ScreenCapture> {
    const monitor = this.monitors.find(m => m.id === targetMonitorId);
    if (!monitor) {
      throw new Error(`Monitor not found: ${targetMonitorId}`);
    }

    this.captureCounter++;
    const now = new Date().toISOString();
    const scaledWidth = Math.round(region.width * monitor.dpiScale);
    const scaledHeight = Math.round(region.height * monitor.dpiScale);

    return {
      captureId: `capture-region-${this.captureCounter}-${Date.now()}`,
      timestamp: now,
      monitorId: targetMonitorId,
      bounds: { x: region.x, y: region.y, width: region.width, height: region.height },
      dpiScale: monitor.dpiScale,
      imageData: this.generatePlaceholderImage(scaledWidth, scaledHeight),
      format: 'png',
      width: scaledWidth,
      height: scaledHeight,
    };
  }

  async captureAll(): Promise<readonly ScreenCapture[]> {
    const captures: ScreenCapture[] = [];
    for (const monitor of this.monitors) {
      captures.push(await this.captureMonitor(monitor.id));
    }
    return captures;
  }

  isAvailable(): boolean {
    return true;
  }

  isUnchanged(): boolean {
    return this.unchangedCount > 0;
  }

  private generatePlaceholderImage(width: number, height: number): string {
    const payload = `MOCK_CAPTURE:${width}x${height}:${this.captureCounter}`;
    return Buffer.from(payload).toString('base64');
  }
}

// ============================================================================
// Bridge Adapter — Connects to real capture via Python desktop agent
// ============================================================================

export interface CaptureBridgeConfig {
  readonly agentUrl: string;
  readonly timeoutMs: number;
  readonly retryCount: number;
  readonly retryDelayMs: number;
}

const DEFAULT_BRIDGE_CONFIG: CaptureBridgeConfig = {
  agentUrl: 'http://127.0.0.1:8765',
  timeoutMs: 10000,
  retryCount: 2,
  retryDelayMs: 500,
};

export class BridgeScreenCaptureAdapter implements IScreenCaptureAdapter {
  private config: CaptureBridgeConfig;
  private cachedMonitors: MonitorInfo[] | null = null;

  constructor(config?: Partial<CaptureBridgeConfig>) {
    this.config = { ...DEFAULT_BRIDGE_CONFIG, ...config };
  }

  async getMonitors(): Promise<readonly MonitorInfo[]> {
    if (this.cachedMonitors) return this.cachedMonitors;

    const fallback: MonitorInfo[] = [{ id: monitorId('default'), index: 0, bounds: { x: 0, y: 0, width: 1920, height: 1080 }, dpiScale: 1, isPrimary: true, orientation: 'landscape' as const, colorDepth: 24 }];
    let monitors: MonitorInfo[];
    try {
      monitors = await this.executeTool<MonitorInfo[]>('systemInfo', {}) ?? fallback;
    } catch {
      monitors = fallback;
    }
    this.cachedMonitors = monitors;
    return monitors;
  }

  async captureMonitor(targetMonitorId: MonitorId): Promise<ScreenCapture> {
    const result = await this.executeTool<{ image: string; width: number; height: number }>('takeScreenshot', {});
    return {
      captureId: `cap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      monitorId: targetMonitorId,
      bounds: { x: 0, y: 0, width: result.width ?? 1920, height: result.height ?? 1080 },
      dpiScale: 1,
      imageData: result.image ?? '',
      format: 'jpeg' as const,
      width: result.width ?? 1920,
      height: result.height ?? 1080,
    };
  }

  async captureRegion(region: CaptureRegion, targetMonitorId: MonitorId): Promise<ScreenCapture> {
    const result = await this.executeTool<{ image: string; width: number; height: number }>('takeRegionScreenshot', {
      x: region.x, y: region.y, width: region.width, height: region.height,
    });
    return {
      captureId: `cap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      monitorId: targetMonitorId,
      bounds: { x: region.x, y: region.y, width: result.width ?? region.width, height: result.height ?? region.height },
      dpiScale: 1,
      imageData: result.image ?? '',
      format: 'jpeg' as const,
      width: result.width ?? region.width,
      height: result.height ?? region.height,
    };
  }

  async captureAll(): Promise<readonly ScreenCapture[]> {
    return [await this.captureMonitor(monitorId('default'))];
  }

  isAvailable(): boolean {
    return true;
  }

  invalidateMonitorCache(): void {
    this.cachedMonitors = null;
  }

  private async executeTool<T>(tool: string, args: Record<string, unknown>): Promise<T> {
    const url = `${this.config.agentUrl}/execute`;
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.config.retryCount; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.config.timeoutMs);

        const response = await fetch(url, {
          method: 'POST',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool, args }),
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json() as { result?: T; error?: string };
        if (data.error) throw new Error(data.error);
        return (data.result ?? data) as T;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (attempt < this.config.retryCount) {
          await this.delay(this.config.retryDelayMs * (attempt + 1));
        }
      }
    }

    throw lastError ?? new Error('Capture failed after retries');
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ============================================================================
// Capture History Tracker
// ============================================================================

export class CaptureHistory {
  private history: ScreenCapture[] = [];
  private readonly maxHistory: number;

  constructor(maxHistory: number) {
    this.maxHistory = maxHistory;
  }

  push(capture: ScreenCapture): void {
    this.history.push(capture);
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory);
    }
  }

  getLatest(): ScreenCapture | null {
    return this.history.length > 0 ? this.history[this.history.length - 1] : null;
  }

  getByIndex(index: number): ScreenCapture | null {
    if (index < 0 || index >= this.history.length) return null;
    return this.history[index];
  }

  getAll(): readonly ScreenCapture[] {
    return this.history;
  }

  get size(): number {
    return this.history.length;
  }

  clear(): void {
    this.history = [];
  }

  findUnchanged(current: ScreenCapture, threshold = 0.99): ScreenCapture | null {
    if (this.history.length === 0) return null;

    for (let i = this.history.length - 1; i >= 0; i--) {
      const prev = this.history[i];
      if (prev.monitorId !== current.monitorId) continue;

      if (this.compareImageSimilarity(prev.imageData, current.imageData) >= threshold) {
        return prev;
      }
    }

    return null;
  }

  private compareImageSimilarity(a: string, b: string): number {
    if (a === b) return 1.0;
    if (a.length === 0 || b.length === 0) return 0;

    let matches = 0;
    const len = Math.min(a.length, b.length);
    const step = Math.max(1, Math.floor(len / 200));

    for (let i = 0; i < len; i += step) {
      if (a[i] === b[i]) matches++;
    }

    return matches / Math.ceil(len / step);
  }
}
