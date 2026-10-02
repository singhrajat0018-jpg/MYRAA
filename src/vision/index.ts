// ============================================================================
// MYRAA Vision Core — VisionEngine Orchestrator
// ============================================================================

import type {
  VisionConfig, VisionEvent, VisionEventListener, VisionEventType,
  VisualScene, VisionContext, SceneDiff, VisualChange,
  VisualTarget, TargetResolutionRequest, TargetResolutionResult,
  ScreenCapture, MonitorInfo, MonitorId, ObservationId,
  CacheEntry,
} from './contracts';
import { DEFAULT_VISION_CONFIG } from './contracts';

import { LruCache, SceneCache } from './cache';
import {
  IScreenCaptureAdapter,
  MockScreenCaptureAdapter,
  CaptureHistory,
} from './screenCapture';
import { IOcrAdapter, MockOcrAdapter, OcrResultMerger, OcrTextExtractor } from './ocrAdapter';
import { SceneBuilder } from './sceneBuilder';
import { ChangeDetector } from './changeDetector';
import { TargetResolver } from './targetResolver';
import { ContextBuilder } from './contextBuilder';
import { VisionSecurityManager } from './security';

// ============================================================================
// Vision Engine
// ============================================================================

export class VisionEngine {
  private config: VisionConfig;
  private captureAdapter: IScreenCaptureAdapter;
  private ocrAdapter: IOcrAdapter;
  private securityManager: VisionSecurityManager;

  private sceneBuilder: SceneBuilder;
  private changeDetector: ChangeDetector;
  private targetResolver: TargetResolver;
  private contextBuilder: ContextBuilder;
  private ocrMerger: OcrResultMerger;
  private ocrTextExtractor: OcrTextExtractor;

  private sceneCache: SceneCache;
  private contextCache: LruCache<string, VisionContext>;
  private captureHistory: CaptureHistory;

  private listeners: Map<VisionEventType, Set<VisionEventListener>> = new Map();
  private isRunning = false;
  private captureTimer: ReturnType<typeof setInterval> | null = null;
  private lastScene: VisualScene | null = null;
  private pendingCaptures = 0;

  constructor(options?: {
    config?: Partial<VisionConfig>;
    captureAdapter?: IScreenCaptureAdapter;
    ocrAdapter?: IOcrAdapter;
    securityPolicy?: import('./contracts').ImageSecurityPolicy;
  }) {
    this.config = { ...DEFAULT_VISION_CONFIG, ...options?.config };
    this.captureAdapter = options?.captureAdapter ?? new MockScreenCaptureAdapter();
    this.ocrAdapter = options?.ocrAdapter ?? new MockOcrAdapter();
    this.securityManager = new VisionSecurityManager({
      securityPolicy: options?.securityPolicy,
    });

    this.sceneBuilder = new SceneBuilder();
    this.changeDetector = new ChangeDetector(this.config.maxSceneHistory);
    this.targetResolver = new TargetResolver();
    this.contextBuilder = new ContextBuilder();
    this.ocrMerger = new OcrResultMerger();
    this.ocrTextExtractor = new OcrTextExtractor();

    this.sceneCache = new SceneCache(this.config.cacheSize, 300_000);
    this.contextCache = new LruCache(this.config.cacheSize, 60_000);
    this.captureHistory = new CaptureHistory(this.config.maxSceneHistory);
  }

  // --- Lifecycle ---

  async start(): Promise<void> {
    if (this.isRunning) return;

    this.isRunning = true;
    this.emit('ENGINE_STARTED', {});

    if (this.config.captureInterval > 0) {
      this.captureTimer = setInterval(() => {
        this.captureLoop().catch(err => {
          this.emit('ENGINE_ERROR', { error: String(err) });
        });
      }, this.config.captureInterval);
    }
  }

  stop(): void {
    if (!this.isRunning) return;

    if (this.captureTimer) {
      clearInterval(this.captureTimer);
      this.captureTimer = null;
    }

    this.isRunning = false;
    this.emit('ENGINE_STOPPED', {});
  }

  // --- Single Observation ---

  async observeOnce(monitorId?: MonitorId): Promise<VisualScene> {
    const monitors = await this.captureAdapter.getMonitors();
    const targetMonitor = monitorId
      ? monitors.find(m => m.id === monitorId)
      : monitors.find(m => m.isPrimary) ?? monitors[0];

    if (!targetMonitor) {
      throw new Error(`Monitor not found: ${monitorId ?? 'primary'}`);
    }

    return this.captureAndBuildScene(targetMonitor.id);
  }

  async observeRegion(
    region: { x: number; y: number; width: number; height: number },
    monitorId: MonitorId,
  ): Promise<VisualScene> {
    this.emit('CAPTURE_STARTED', { monitorId, region });

    const capture = await this.captureAdapter.captureRegion(region, monitorId);

    const validation = this.securityManager.validateAndSanitize(capture);
    if (!validation.valid) {
      throw new Error(`Capture validation failed: ${validation.reason}`);
    }

    this.captureHistory.push(capture);
    const ocrBlocks = await this.ocrAdapter.recognizeRegion(capture, region);
    const mergedBlocks = this.ocrMerger.merge([ocrBlocks]);

    const scene = this.sceneBuilder.buildScene({
      capture,
      ocrBlocks: mergedBlocks,
    });

    this.sceneCache.set(scene);
    this.changeDetector.pushScene(scene);
    this.lastScene = scene;

    if (this.config.changeTrackingEnabled && this.sceneCache.size > 1) {
      const prevScene = this.sceneCache.getByIndex(this.sceneCache.size - 2);
      if (prevScene) {
        const diff = this.changeDetector.diff(prevScene, scene);
        if (diff.changeCount > 0) {
          this.emit('CHANGE_DETECTED', { diff, sceneId: scene.sceneId });
        }
      }
    }

    this.emit('CAPTURE_COMPLETED', { captureId: capture.captureId, sceneId: scene.sceneId });
    return scene;
  }

  // --- Context ---

  getContext(scene: VisualScene): VisionContext {
    const cacheKey = scene.sceneId as string;
    const cached = this.contextCache.get(cacheKey);
    if (cached) return cached;

    const recentChanges = this.changeDetector.getRecentChanges(this.config.maxSceneHistory);
    const context = this.contextBuilder.build(scene, recentChanges);

    this.contextCache.set(cacheKey, context);
    return context;
  }

  // --- Target Resolution ---

  resolveTarget(query: string, scene?: VisualScene): TargetResolutionResult {
    const activeScene = scene ?? this.lastScene;
    if (!activeScene) {
      return {
        primary: null,
        candidates: [],
        confidence: 0,
        ambiguity: 'none',
        suggestion: 'No scene available. Observe the screen first.',
      };
    }

    const context = this.getContext(activeScene);
    const request: TargetResolutionRequest = {
      query,
      context,
      preferredMonitor: null,
      maxCandidates: 5,
      minConfidence: 0.3,
    };

    const result = this.targetResolver.resolve(request);

    this.emit('TARGET_RESOLVED', {
      query,
      targetId: result.primary?.targetId,
      confidence: result.confidence,
      ambiguity: result.ambiguity,
    });

    return result;
  }

  // --- Scene History ---

  getLatestScene(): VisualScene | null {
    return this.lastScene;
  }

  getSceneHistory(): readonly VisualScene[] {
    return this.changeDetector.getHistory();
  }

  getSceneDiff(from: VisualScene, to: VisualScene): SceneDiff {
    return this.changeDetector.diff(from, to);
  }

  // --- Monitors ---

  async getMonitors(): Promise<readonly MonitorInfo[]> {
    return this.captureAdapter.getMonitors();
  }

  // --- Cache ---

  getSceneCacheStats() {
    return this.sceneCache.getStats();
  }

  // --- State ---

  get isEngineRunning(): boolean {
    return this.isRunning;
  }

  // --- Events ---

  on(type: VisionEventType, listener: VisionEventListener): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);

    return () => {
      this.listeners.get(type)?.delete(listener);
    };
  }

  off(type: VisionEventType, listener: VisionEventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  private emit(type: VisionEventType, data: Record<string, unknown>): void {
    const event: VisionEvent = {
      type,
      timestamp: new Date().toISOString(),
      data,
    };

    const typeListeners = this.listeners.get(type);
    if (typeListeners) {
      for (const listener of typeListeners) {
        try {
          listener(event);
        } catch {
          // swallow listener errors
        }
      }
    }

    const allListeners = this.listeners.get('*' as VisionEventType);
    if (allListeners) {
      for (const listener of allListeners) {
        try {
          listener(event);
        } catch {
          // swallow listener errors
        }
      }
    }
  }

  // --- Internal ---

  private async captureLoop(): Promise<void> {
    if (!this.isRunning) return;
    if (this.pendingCaptures >= this.config.maxConcurrentCaptures) return;

    try {
      this.pendingCaptures++;
      const monitors = await this.captureAdapter.getMonitors();
      const primary = monitors.find(m => m.isPrimary) ?? monitors[0];
      if (!primary) return;

      await this.captureAndBuildScene(primary.id);
    } finally {
      this.pendingCaptures--;
    }
  }

  private async captureAndBuildScene(targetMonitorId: MonitorId): Promise<VisualScene> {
    this.emit('CAPTURE_STARTED', { monitorId: targetMonitorId });

    const capture = await this.captureAdapter.captureMonitor(targetMonitorId);

    const validation = this.securityManager.validateAndSanitize(capture);
    if (!validation.valid) {
      throw new Error(`Capture validation failed: ${validation.reason}`);
    }

    this.captureHistory.push(capture);

    const ocrBlocks = await this.ocrAdapter.recognizeText(capture);
    const mergedBlocks = this.ocrMerger.merge([ocrBlocks]);

    this.emit('OCR_COMPLETED', {
      captureId: capture.captureId,
      blockCount: mergedBlocks.length,
    });

    const scene = this.sceneBuilder.buildScene({
      capture,
      ocrBlocks: mergedBlocks,
    });

    this.sceneCache.set(scene);
    this.changeDetector.pushScene(scene);

    if (this.config.changeTrackingEnabled && this.lastScene) {
      const diff = this.changeDetector.diff(this.lastScene, scene);
      if (diff.changeCount > 0) {
        this.emit('CHANGE_DETECTED', { diff, sceneId: scene.sceneId });
      }
    }

    this.lastScene = scene;
    this.emit('SCENE_READY', {
      sceneId: scene.sceneId,
      monitorId: scene.monitorId,
      elementCount: scene.elements.length,
      confidence: scene.confidence,
    });

    return scene;
  }
}

// ============================================================================
// Barrel Export
// ============================================================================

export type {
  VisionConfig, VisionEvent, VisionEventListener, VisionEventType,
  VisualScene, VisionContext, SceneDiff, VisualChange,
  VisualTarget, TargetResolutionRequest, TargetResolutionResult,
  ScreenCapture, MonitorInfo, MonitorId, ObservationId,
  VisualElement, ElementId, VisualElementType,
  OcrBlock, OcrLine, OcrWord,
  VisualWindow, VisualRegion, VisualNotification, VisualDialog,
  VisualMenu, VisualMenuItem, VisualTable,
  ChangeType, ChangeSignificance, RegionPurpose, NotificationSeverity,
  ResolutionMethod, CoordinateSpace, AmbiguityLevel,
  CacheEntry, ImageSecurityPolicy,
} from './contracts';

export {
  monitorId, observationId, elementId, regionId,
  DEFAULT_VISION_CONFIG, DEFAULT_SECURITY_POLICY,
  CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW, CONFIDENCE_MINIMUM,
  OCR_BLOCK_SEPARATOR, OCR_LINE_SEPARATOR, OCR_WORD_SEPARATOR,
  SIGNIFICANCE_WEIGHTS, WINDOW_TITLE_MAX_LENGTH, SCREEN_TEXT_MAX_LENGTH,
  ELEMENT_TEXT_MAX_LENGTH,
} from './contracts';

export { LruCache, SceneCache } from './cache';
export type { IScreenCaptureAdapter, CaptureBridgeConfig } from './screenCapture';
export {
  MockScreenCaptureAdapter, BridgeScreenCaptureAdapter, CaptureHistory,
} from './screenCapture';
export type { IOcrAdapter } from './ocrAdapter';
export { MockOcrAdapter, OcrResultMerger, OcrTextExtractor } from './ocrAdapter';
export { SceneBuilder } from './sceneBuilder';
export { ChangeDetector } from './changeDetector';
export { TargetResolver } from './targetResolver';
export { ContextBuilder } from './contextBuilder';
export {
  VisionSecurityManager, ImageValidator, ContentSanitizer, FilePathValidator,
  RateLimiter,
} from './security';
export type { ImageValidationResult } from './security';
