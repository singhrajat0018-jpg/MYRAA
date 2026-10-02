// ============================================================================
// MYRAA World Intelligence — Server API Routes
// ============================================================================

import type { Express, Request, Response } from 'express';
import type { WorldIntelligence } from '../../src/world-intelligence/index';

let worldIntelligence: WorldIntelligence | null = null;

export function setWorldIntelligence(wi: WorldIntelligence): void {
  worldIntelligence = wi;
}

export function getWorldIntelligence(): WorldIntelligence | null {
  return worldIntelligence;
}

export function registerWorldRoutes(app: Express): void {
  // --- Query ---

  app.get('/api/world/query', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    try {
      const query = {
        type: (req.query.type as string) || 'NATURAL_LANGUAGE',
        naturalLanguageQuery: req.query.q as string,
        entityIds: req.query.entityIds ? String(req.query.entityIds).split(',') : undefined,
        eventTypes: req.query.eventTypes ? String(req.query.eventTypes).split(',') as any[] : undefined,
        topics: req.query.topics ? String(req.query.topics).split(',') : undefined,
        timeRange: req.query.from || req.query.to
          ? { from: req.query.from as string, to: req.query.to as string }
          : undefined,
        maxResults: req.query.limit ? parseInt(req.query.limit as string) : 20,
        includeProvenance: req.query.provenance === 'true',
      };
      const result = worldIntelligence.queryWorld(query as any);
      res.json(result);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.get('/api/world/entity/:id', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const entity = worldIntelligence.getEntity(req.params.id);
    if (!entity) return res.status(404).json({ error: 'Entity not found' });
    const facts = worldIntelligence.state.getFactsBySubject(req.params.id);
    const events = worldIntelligence.state.getEventsByEntity(req.params.id);
    res.json({ entity, facts, events });
  });

  app.get('/api/world/events', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const hours = req.query.hours ? parseInt(req.query.hours as string) : 24;
    const limit = req.query.limit ? parseInt(req.query.limit as string) : 50;
    const events = worldIntelligence.getRecentEvents(hours, limit);
    res.json({ events, count: events.length });
  });

  app.get('/api/world/history', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const { entityId, predicate, atTime } = req.query;
    if (!entityId || !predicate) return res.status(400).json({ error: 'entityId and predicate required' });
    const facts = worldIntelligence.queryHistory(entityId as string, predicate as string, atTime as string || new Date().toISOString());
    res.json({ facts });
  });

  app.get('/api/world/changes', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const from = req.query.from as string;
    const to = req.query.to as string;
    if (!from) return res.status(400).json({ error: 'from timestamp required' });
    const diff = worldIntelligence.getChanges(from, to);
    res.json(diff);
  });

  // --- Search ---

  app.get('/api/world/search', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const q = req.query.q as string;
    if (!q) return res.status(400).json({ error: 'q (query) required' });
    const limit = req.query.limit ? parseInt(req.query.limit as string) : 20;
    const entities = worldIntelligence.searchEntities(q, limit);
    res.json({ entities, count: entities.length });
  });

  // --- Ingestion ---

  app.post('/api/world/refresh', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    try {
      await worldIntelligence.refresh();
      res.json({ success: true, message: 'World state refreshed' });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.post('/api/world/ingest/:providerId', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    try {
      const result = await worldIntelligence.ingestFromProvider(req.params.providerId);
      res.json(result);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // --- Watchers ---

  app.post('/api/world/watch', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    try {
      const watcher = worldIntelligence.watch(req.body);
      res.json(watcher);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.get('/api/world/watchers', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const watchers = worldIntelligence.watcher.getAllWatchers();
    res.json({ watchers });
  });

  app.post('/api/world/watch/:id/pause', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const success = worldIntelligence.pauseWatcher(req.params.id);
    res.json({ success });
  });

  app.post('/api/world/watch/:id/resume', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const success = worldIntelligence.resumeWatcher(req.params.id);
    res.json({ success });
  });

  app.delete('/api/world/watch/:id', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const success = worldIntelligence.unwatch(req.params.id);
    res.json({ success });
  });

  app.get('/api/world/alerts', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const watcherId = req.query.watcherId as string;
    const alerts = worldIntelligence.getAlerts(watcherId);
    res.json({ alerts });
  });

  // --- Diagnostics ---

  app.get('/api/world/health', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const health = await worldIntelligence.getHealth();
    res.json(health);
  });

  app.get('/api/world/stats', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const stats = worldIntelligence.getStats();
    res.json(stats);
  });

  app.get('/api/world/quality', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const quality = worldIntelligence.getDataQuality();
    res.json(quality);
  });

  app.get('/api/world/sources', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    const history = worldIntelligence.ingestion.getIngestionHistory(20);
    res.json({ ingestionHistory: history });
  });

  // --- Snapshot ---

  app.post('/api/world/snapshot', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    try {
      const snapshot = await worldIntelligence.createSnapshot();
      res.json({ timestamp: snapshot.timestamp, checksum: snapshot.checksum });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // --- Persistence ---

  app.post('/api/world/save', async (req: Request, res: Response) => {
    if (!worldIntelligence) return res.status(503).json({ error: 'World intelligence not initialized' });
    try {
      await worldIntelligence.save();
      res.json({ success: true });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  console.log('[World Routes] Registered /api/world/* routes');
}
