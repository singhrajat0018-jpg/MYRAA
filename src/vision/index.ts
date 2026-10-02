import { BridgeScreenCaptureAdapter } from './screenCapture';
import { BridgeOcrAdapter } from './ocrAdapter';
import type { MonitorId, ObservedScene, ScreenRegion } from './contracts';

export interface VisionEngineOptions {
  captureAdapter: BridgeScreenCaptureAdapter;
  ocrAdapter: BridgeOcrAdapter;
}

export class VisionEngine {
  public isEngineRunning = true;

  constructor(private options: VisionEngineOptions) {}

  async start(): Promise<void> { this.isEngineRunning = true; }
  async stop(): Promise<void> { this.isEngineRunning = false; }

  getSceneCacheStats() {
    return { size: 0, hits: 0, misses: 0 };
  }

  getLatestScene(): ObservedScene | null {
    return {
      timestamp: Date.now(),
      monitorId: 'default',
      elements: [],
      ocrBlocks: [],
      textContent: '',
    };
  }

  getContext(mid?: any) {
    return { focusedApp: 'Browser', activeWindow: 'MYRAA' };
  }

  resolveTarget(target: any) {
    return { found: false, point: null };
  }

  getSceneHistory(mid?: any, limit?: number) {
    return [];
  }

  getSceneDiff(mid1?: any, mid2?: any) {
    return { changed: false, diffScore: 0 };
  }

  getMonitors() {
    return [{ id: 'default', name: 'Primary Monitor', bounds: { x: 0, y: 0, width: 1920, height: 1080 } }];
  }

  async observeOnce(mid?: MonitorId): Promise<ObservedScene> {
    return {
      timestamp: Date.now(),
      monitorId: mid || 'default',
      elements: [],
      ocrBlocks: [],
      textContent: '',
    };
  }

  async observeRegion(region: ScreenRegion, mid?: MonitorId): Promise<ObservedScene> {
    return {
      timestamp: Date.now(),
      monitorId: mid || 'default',
      elements: [],
      ocrBlocks: [],
      textContent: '',
    };
  }
}
