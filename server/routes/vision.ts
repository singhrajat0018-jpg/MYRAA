// ============================================================================
// MYRAA Vision REST API Routes
// ============================================================================

import type { Express, Request, Response } from 'express';
import { VisionEngine } from '../../src/vision/index';
import type { MonitorId } from '../../src/vision/contracts';
import { monitorId } from '../../src/vision/contracts';

let engine: VisionEngine | null = null;

export function setVisionEngine(ve: VisionEngine): void {
  engine = ve;
}

export function getVisionEngine(): VisionEngine | null {
  return engine;
}

export function registerVisionRoutes(
  app: Express,
  ctx: { DESKTOP_AGENT_URL: string; logCommand: (m: string) => void; logError: (m: string) => void },
): void {
  // --- Health ---

  app.get('/api/vision/health', (_req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    res.json({
      status: 'ok',
      module: 'vision',
      running: engine.isEngineRunning,
      cacheStats: engine.getSceneCacheStats(),
    });
  });

  app.get('/api/vision/telemetry', (_req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    res.json(engine.getTelemetry());
  });

  // --- Observe (full screen) ---

  app.post('/api/vision/observe', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const { monitorId: mid } = req.body as { monitorId?: string };
      const scene = await engine.observeOnce(mid ? monitorId(mid) : undefined);
      res.json(scene);
    } catch (err: any) {
      ctx.logError(`[Vision] observe failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- Observe Region ---

  app.post('/api/vision/observe-region', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const { region, monitorId: mid } = req.body as {
        region?: { x: number; y: number; width: number; height: number };
        monitorId?: string;
      };
      if (!region || typeof region.x !== 'number' || typeof region.y !== 'number' ||
          typeof region.width !== 'number' || typeof region.height !== 'number') {
        return res.status(400).json({ error: 'region { x, y, width, height } is required' });
      }
      const targetMonitor = mid ? monitorId(mid) : monitorId('primary');
      const scene = await engine.observeRegion(region, targetMonitor);
      res.json(scene);
    } catch (err: any) {
      ctx.logError(`[Vision] observe-region failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- Context ---

  app.get('/api/vision/context', (_req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const scene = engine.getLatestScene();
      if (!scene) return res.json({ error: 'No scene available. Observe the screen first.' });
      const context = engine.getContext(scene);
      res.json(context);
    } catch (err: any) {
      ctx.logError(`[Vision] context failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- Resolve Target ---

  app.post('/api/vision/resolve-target', (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const { query } = req.body as { query?: string };
      if (!query || typeof query !== 'string') {
        return res.status(400).json({ error: 'query (string) is required' });
      }
      const result = engine.resolveTarget(query);
      res.json(result);
    } catch (err: any) {
      ctx.logError(`[Vision] resolve-target failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- Diff ---

  app.post('/api/vision/diff', (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const { fromSceneId, toSceneId } = req.body as { fromSceneId?: string; toSceneId?: string };
      const history = engine.getSceneHistory();
      if (history.length < 2) {
        return res.status(400).json({ error: 'Need at least 2 scenes to diff' });
      }

      let fromScene, toScene;
      if (fromSceneId && toSceneId) {
        fromScene = history.find(s => s.sceneId === fromSceneId);
        toScene = history.find(s => s.sceneId === toSceneId);
        if (!fromScene || !toScene) {
          return res.status(404).json({ error: 'Scene not found in history' });
        }
      } else {
        fromScene = history[history.length - 2];
        toScene = history[history.length - 1];
      }

      const diff = engine.getSceneDiff(fromScene, toScene);
      res.json(diff);
    } catch (err: any) {
      ctx.logError(`[Vision] diff failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- History ---

  app.get('/api/vision/history', (_req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const history = engine.getSceneHistory();
      res.json({ count: history.length, scenes: history.map(s => ({
        sceneId: s.sceneId,
        timestamp: s.timestamp,
        monitorId: s.monitorId,
        elementCount: s.elements.length,
        confidence: s.confidence,
      }))});
    } catch (err: any) {
      ctx.logError(`[Vision] history failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- OCR (manual image analysis) ---

  app.post('/api/vision/ocr', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const { imageData, region } = req.body as {
        imageData?: string;
        region?: { x: number; y: number; width: number; height: number };
      };
      if (!imageData || typeof imageData !== 'string') {
        return res.status(400).json({ error: 'imageData (base64 string) is required' });
      }
      // Use observeRegion if region provided, otherwise use the latest scene OCR
      if (region) {
        const scene = await engine.observeRegion(region, monitorId('primary'));
        res.json({ ocrBlocks: scene.ocrBlocks, textContent: scene.textContent });
      } else {
        const scene = engine.getLatestScene();
        if (!scene) return res.status(400).json({ error: 'No scene available. Observe the screen first.' });
        res.json({ ocrBlocks: scene.ocrBlocks, textContent: scene.textContent });
      }
    } catch (err: any) {
      ctx.logError(`[Vision] ocr failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- Config (GET) ---

  app.get('/api/vision/config', (_req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const monitors = engine.getMonitors();
      const cacheStats = engine.getSceneCacheStats();
      res.json({
        running: engine.isEngineRunning,
        monitors,
        cacheStats,
      });
    } catch (err: any) {
      ctx.logError(`[Vision] config get failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  // --- Config (POST) ---

  app.post('/api/vision/config', (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Vision engine not initialized' });
    try {
      const { action } = req.body as { action?: string };
      if (action === 'start') {
        engine.start().then(() => res.json({ success: true, running: true }));
        return;
      }
      if (action === 'stop') {
        engine.stop();
        res.json({ success: true, running: false });
        return;
      }
      res.status(400).json({ error: 'action must be "start" or "stop"' });
    } catch (err: any) {
      ctx.logError(`[Vision] config post failed: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });
}
