// ============================================================================
// MYRAA Vision Engine — Central Authority for Live Screen Awareness & Perception
// ============================================================================

import { BridgeScreenCaptureAdapter } from './screenCapture';
import { BridgeOcrAdapter } from './ocrAdapter';
import { FrameDifferenceEngine } from './frameDifference';
import { ROIEngine } from './roiEngine';
import { VisualEventEngine } from './visualEventEngine';
import { SignificanceEngine } from './significanceEngine';
import { TemporalVisionEngine } from './temporalVision';
import { WorldModelVisionBridge } from './worldModelBridge';
import { FastCoreVisionInterface } from './fastCoreInterface';
import type {
  MonitorId,
  ObservedScene,
  ScreenRegion,
  UIElement,
  VisionStatus,
  VisionTelemetry,
  FastCoreVisualPerception,
  VisionEvidence,
} from './contracts';

export interface VisionEngineOptions {
  captureAdapter: BridgeScreenCaptureAdapter;
  ocrAdapter: BridgeOcrAdapter;
  agentUrl?: string;
  pollIntervalMs?: number;
}

export class VisionEngine {
  public isEngineRunning = false;
  public status: VisionStatus = 'INITIALIZING';

  private captureAdapter: BridgeScreenCaptureAdapter;
  private ocrAdapter: BridgeOcrAdapter;
  private frameDiffEngine: FrameDifferenceEngine;
  private roiEngine: ROIEngine;
  private eventEngine: VisualEventEngine;
  private significanceEngine: SignificanceEngine;
  private temporalEngine: TemporalVisionEngine;
  private worldModelBridge: WorldModelVisionBridge;

  private pollIntervalMs: number;
  private loopTimer: NodeJS.Timeout | null = null;
  private inProgress = false;

  // Telemetry metrics
  private totalObservations = 0;
  private framesCaptured = 0;
  private framesSkipped = 0;
  private framesDropped = 0;
  private significantEventsEmitted = 0;
  private lastObservationTime = 0;
  private lastChangeTime = 0;
  private consecutiveNoChangeCount = 0;
  private captureLatencies: number[] = [];
  private analysisLatencies: number[] = [];
  private ocrLatencies: number[] = [];

  constructor(options: VisionEngineOptions) {
    this.captureAdapter = options.captureAdapter;
    this.ocrAdapter = options.ocrAdapter;
    this.pollIntervalMs = options.pollIntervalMs || 2500;

    const agentUrl = options.agentUrl || 'http://127.0.0.1:8765';
    this.frameDiffEngine = new FrameDifferenceEngine();
    this.roiEngine = new ROIEngine();
    this.eventEngine = new VisualEventEngine();
    this.significanceEngine = new SignificanceEngine();
    this.temporalEngine = new TemporalVisionEngine();
    this.worldModelBridge = new WorldModelVisionBridge({ agentUrl });

    this.status = 'HEALTHY';
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  public async start(): Promise<void> {
    if (this.isEngineRunning) return;
    this.isEngineRunning = true;
    this.status = 'CAPTURING';

    // Immediate initial observation
    this.observeOnce().catch(() => {});

    // Adaptive continuous loop
    this.scheduleNextLoop(this.pollIntervalMs);
  }

  public stop(): void {
    this.isEngineRunning = false;
    this.status = 'PAUSED';
    if (this.loopTimer) {
      clearTimeout(this.loopTimer);
      this.loopTimer = null;
    }
  }

  private scheduleNextLoop(delayMs: number): void {
    if (!this.isEngineRunning) return;
    if (this.loopTimer) clearTimeout(this.loopTimer);

    this.loopTimer = setTimeout(async () => {
      if (!this.isEngineRunning) return;

      // Frame coalescing: if observation is currently running, drop this tick
      if (this.inProgress) {
        this.framesDropped++;
        this.scheduleNextLoop(this.pollIntervalMs);
        return;
      }

      await this.observeOnce().catch(() => {});

      // Adaptive throttle: slow down if idle, speed up if active
      let nextDelay = this.pollIntervalMs;
      if (this.consecutiveNoChangeCount >= 6) {
        nextDelay = Math.min(6000, this.pollIntervalMs * 2); // Idle backoff
      } else if (this.consecutiveNoChangeCount === 0) {
        nextDelay = Math.max(1500, this.pollIntervalMs * 0.8); // Active responsive
      }

      this.scheduleNextLoop(nextDelay);
    }, delayMs);
  }

  // ── Core Perception Pipeline ──────────────────────────────────────────────

  /**
   * Performs one complete cycle of the vision perception pipeline:
   * CAPTURE → ACTIVE WINDOW → DELTA → OCR → EVENTS → SIGNIFICANCE → TEMPORAL → WORLD MODEL.
   */
  public async observeOnce(mid?: MonitorId): Promise<ObservedScene> {
    this.inProgress = true;
    const startT = Date.now();
    const prevScene = this.temporalEngine.getLatestScene();

    try {
      this.status = 'ANALYZING';

      // 1. Capture Frame & Active Window Metadata
      const capStart = Date.now();
      let frame;
      try {
        frame = await this.captureAdapter.captureScreen(mid);
      } catch (err: any) {
        this.status = 'DEGRADED';
        throw err;
      }
      const capLat = Date.now() - capStart;
      this.recordLatency(this.captureLatencies, capLat);
      this.framesCaptured++;

      // 2. Active Window & Title
      const activeWindow = frame.activeWindow;

      // 3. Preliminary Delta Analysis (Cheap Perception)
      const prevLite = prevScene
        ? {
            textContent: prevScene.textContent,
            activeWindow: prevScene.activeWindow,
            width: prevScene.width,
            height: prevScene.height,
          }
        : null;

      const currLite = {
        textContent: prevScene ? prevScene.textContent : '',
        activeWindow,
        width: frame.width,
        height: frame.height,
      };

      const preliminaryDelta = this.frameDiffEngine.computeDelta(prevLite, currLite);

      // 4. Adaptive OCR: if window switched, or preliminary change detected, run OCR
      let ocrResult = { text: '', blocks: [] as any[], confidence: 0, hasErrors: false, sensitiveRedacted: false };
      const shouldRunOcr = !prevScene || preliminaryDelta.changed || this.totalObservations % 4 === 0;

      if (shouldRunOcr) {
        const ocrStart = Date.now();
        ocrResult = await this.ocrAdapter.recognizeWithMetadata(frame.buffer);
        const ocrLat = Date.now() - ocrStart;
        this.recordLatency(this.ocrLatencies, ocrLat);
      } else if (prevScene) {
        // Reuse cached OCR text for unchanged static screen
        ocrResult = {
          text: prevScene.textContent,
          blocks: prevScene.ocrBlocks,
          confidence: prevScene.confidence,
          hasErrors: prevScene.hasError,
          sensitiveRedacted: false,
        };
        this.framesSkipped++;
      }

      // 5. Final Full Delta Calculation with OCR text
      currLite.textContent = ocrResult.text;
      const finalDelta = this.frameDiffEngine.computeDelta(prevLite, currLite);

      // 6. Detect Semantic Visual Events
      const events = this.eventEngine.detectEvents(
        prevScene ? { activeWindow: prevScene.activeWindow, textContent: prevScene.textContent, timestamp: prevScene.timestamp } : null,
        { activeWindow, textContent: ocrResult.text, timestamp: Date.now(), ocrBlocks: ocrResult.blocks }
      );

      // 7. Significance Evaluation
      const sigDecision = this.significanceEngine.evaluate(events, finalDelta, activeWindow);

      // 8. Track Consecutive Change State
      if (finalDelta.changed) {
        this.lastChangeTime = Date.now();
        this.consecutiveNoChangeCount = 0;
      } else {
        this.consecutiveNoChangeCount++;
      }

      if (sigDecision.isSignificant) {
        this.significantEventsEmitted++;
      }

      // 9. Build UI Elements from ROIs and OCR blocks
      const rois = this.roiEngine.extractROIs(activeWindow, ocrResult.blocks, frame.width, frame.height);
      const elements: UIElement[] = rois.map((r, i) => ({
        id: `roi-el-${i}-${Date.now()}`,
        type: r.type === 'DIALOG' ? 'dialog' : r.type === 'TERMINAL' ? 'terminal' : 'panel',
        text: r.description,
        box: r.region,
        confidence: 0.95,
        interactive: r.priority === 1,
      }));

      // Evidence building
      const evidence: VisionEvidence[] = [];
      if (ocrResult.hasErrors) {
        const errBlock = ocrResult.blocks.find(b => /(error|failed|exception)/i.test(b.text));
        if (errBlock) {
          evidence.push({
            claim: 'Error detected on screen',
            source: 'OCR',
            region: errBlock.bbox,
            timestamp: Date.now(),
            text: errBlock.text,
            confidence: 0.95,
          });
        }
      }

      // 10. Construct ObservedScene
      const scene: ObservedScene = {
        sceneId: `sc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: Date.now(),
        monitorId: mid || 'primary',
        width: frame.width,
        height: frame.height,
        activeWindow,
        elements,
        ocrBlocks: ocrResult.blocks,
        textContent: ocrResult.text,
        delta: finalDelta,
        events,
        significance: sigDecision.overallSignificance,
        confidence: ocrResult.confidence || 0.9,
        provenance: 'WINDOWS_API',
        untrustedScreenData: true, // Prompt-injection defense: screen text is untrusted data!
        hasError: ocrResult.hasErrors,
        errorText: ocrResult.hasErrors ? ocrResult.text.slice(0, 200) : undefined,
        evidence,
      };

      // 11. Record into Temporal Engine
      this.temporalEngine.recordScene(scene);

      // 12. World Model Bridge Sync
      if (sigDecision.shouldUpdateWorldModel) {
        void this.worldModelBridge.syncToWorldModel(scene, events);
      }

      this.totalObservations++;
      this.lastObservationTime = Date.now();
      const anaLat = Date.now() - startT;
      this.recordLatency(this.analysisLatencies, anaLat);

      this.status = 'HEALTHY';
      return scene;
    } finally {
      this.inProgress = false;
    }
  }

  /**
   * Observe a targeted bounding region of interest.
   */
  public async observeRegion(region: ScreenRegion, mid?: MonitorId): Promise<ObservedScene> {
    const frame = await this.captureAdapter.captureRegion(region, mid);
    const ocrResult = await this.ocrAdapter.recognizeWithMetadata(frame.buffer, region);

    const scene: ObservedScene = {
      sceneId: `sc-reg-${Date.now()}`,
      timestamp: Date.now(),
      monitorId: mid || 'primary',
      width: frame.width,
      height: frame.height,
      activeWindow: frame.activeWindow,
      elements: [{
        id: `reg-${Date.now()}`,
        type: 'panel',
        text: 'Region Observation',
        box: region,
        confidence: 0.95,
        interactive: true,
      }],
      ocrBlocks: ocrResult.blocks,
      textContent: ocrResult.text,
      events: [],
      significance: 0.5,
      confidence: 0.92,
      provenance: 'OCR',
      untrustedScreenData: true,
      hasError: ocrResult.hasErrors,
      errorText: ocrResult.hasErrors ? ocrResult.text.slice(0, 150) : undefined,
    };

    return scene;
  }

  // ── Public Accessors & Route Implementations ──────────────────────────────

  public getLatestScene(): ObservedScene | null {
    return this.temporalEngine.getLatestScene();
  }

  public getSceneHistory(mid?: any, limit = 20): ObservedScene[] {
    return this.temporalEngine.getHistory(limit);
  }

  public getSceneDiff(fromScene: any, toScene: any) {
    if (!fromScene || !toScene) {
      return { changed: false, diffScore: 0 };
    }
    return this.temporalEngine.diffScenes(fromScene, toScene);
  }

  public getContext(sceneOrMid?: any) {
    const scene = (sceneOrMid && typeof sceneOrMid.activeWindow === 'object')
      ? (sceneOrMid as ObservedScene)
      : this.getLatestScene();

    if (!scene) {
      return { focusedApp: 'Desktop', activeWindow: 'Active Desktop' };
    }

    return {
      focusedApp: scene.activeWindow.application,
      activeWindow: scene.activeWindow.title,
      textContentSnippet: scene.textContent.slice(0, 300),
      hasError: scene.hasError,
      significance: scene.significance,
    };
  }

  public resolveTarget(query: string) {
    const scene = this.getLatestScene();
    if (!scene || !query) {
      return { found: false, point: null };
    }

    const qLower = query.toLowerCase();
    const matchedBlock = scene.ocrBlocks.find(b => b.text.toLowerCase().includes(qLower));

    if (matchedBlock) {
      const centerX = Math.round(matchedBlock.bbox.x + matchedBlock.bbox.width / 2);
      const centerY = Math.round(matchedBlock.bbox.y + matchedBlock.bbox.height / 2);
      return {
        found: true,
        point: { x: centerX, y: centerY },
        matchedText: matchedBlock.text,
        confidence: matchedBlock.confidence,
      };
    }

    return { found: false, point: null };
  }

  public getMonitors() {
    return [
      { id: 'primary', name: 'Primary Display', bounds: { x: 0, y: 0, width: 1920, height: 1080 } },
    ];
  }

  public getSceneCacheStats() {
    const history = this.temporalEngine.getHistory(50);
    return {
      size: history.length,
      hits: this.framesSkipped,
      misses: this.framesCaptured,
    };
  }

  public getTelemetry(): VisionTelemetry {
    return {
      status: this.status,
      isCapturing: this.isEngineRunning,
      totalObservations: this.totalObservations,
      framesCaptured: this.framesCaptured,
      framesSkipped: this.framesSkipped,
      framesDropped: this.framesDropped,
      significantEventsEmitted: this.significantEventsEmitted,
      avgCaptureLatencyMs: this.calcAvg(this.captureLatencies),
      avgAnalysisLatencyMs: this.calcAvg(this.analysisLatencies),
      avgOcrLatencyMs: this.calcAvg(this.ocrLatencies),
      lastObservationTime: this.lastObservationTime,
      lastChangeTime: this.lastChangeTime,
      consecutiveNoChangeCount: this.consecutiveNoChangeCount,
      desktopAgentConnected: this.status !== 'DEGRADED' && this.status !== 'OFFLINE',
    };
  }

  public getFastCorePerception(): FastCoreVisualPerception {
    const scene = this.getLatestScene();
    return FastCoreVisionInterface.formatForFastCore(scene);
  }

  private recordLatency(arr: number[], val: number): void {
    arr.push(val);
    if (arr.length > 50) arr.shift();
  }

  private calcAvg(arr: number[]): number {
    if (arr.length === 0) return 0;
    const sum = arr.reduce((a, b) => a + b, 0);
    return Math.round(sum / arr.length);
  }
}
