// ============================================================================
// MYRAA Agent Routes — REST API for goals, plans, execution, approval
// ============================================================================

import type { Express, Request, Response } from 'express';
import type { ReasoningEngine } from '../../src/agent/index';

let engine: ReasoningEngine | null = null;

export function setReasoningEngine(re: ReasoningEngine): void {
  engine = re;
}

export function getReasoningEngine(): ReasoningEngine | null {
  return engine;
}

export function registerAgentRoutes(app: Express): void {
  // --- Process Goal ---

  app.post('/api/agent/goal', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    try {
      const { request, conversationId, conversationHistory } = req.body;
      if (!request || typeof request !== 'string') {
        return res.status(400).json({ error: 'request (string) is required' });
      }
      const result = await engine.processRequest(request, { conversationId, conversationHistory });
      res.json(result);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // --- Goals ---

  app.get('/api/agent/goals', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const goals = engine.goalEngine.getAllGoals();
    res.json({ goals, count: goals.length });
  });

  app.get('/api/agent/goal/:id', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const goal = engine.getGoal(req.params.id);
    if (!goal) return res.status(404).json({ error: 'Goal not found' });
    res.json(goal);
  });

  app.delete('/api/agent/goal/:id', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const success = engine.cancelGoal(req.params.id);
    res.json({ success });
  });

  // --- Plans ---

  app.get('/api/agent/plan/:id', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const plan = engine.getPlan(req.params.id);
    if (!plan) return res.status(404).json({ error: 'Plan not found' });
    res.json(plan);
  });

  // --- Approval ---

  app.post('/api/agent/plan/:planId/approve/:taskId', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const success = engine.approveTask(req.params.planId, req.params.taskId);
    res.json({ success });
  });

  app.post('/api/agent/plan/:planId/deny/:taskId', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const { reason } = req.body;
    const success = engine.denyTask(req.params.planId, req.params.taskId, reason || 'Denied by user');
    res.json({ success });
  });

  app.get('/api/agent/approvals', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const approvals = engine.getPendingApprovals();
    res.json({ approvals, count: approvals.length });
  });

  // --- Events ---

  app.get('/api/agent/events', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const goalId = req.query.goalId as string | undefined;
    const limit = req.query.limit ? parseInt(req.query.limit as string) : 100;
    const events = engine.getEventLog(goalId).slice(-limit);
    res.json({ events, count: events.length });
  });

  // --- Stats / Health ---

  app.get('/api/agent/stats', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    const stats = engine.getStats();
    res.json(stats);
  });

  app.get('/api/agent/health', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ status: 'uninitialized' });
    res.json({ status: 'healthy', stats: engine.getStats() });
  });

  // --- Persistence ---

  app.post('/api/agent/save', async (req: Request, res: Response) => {
    if (!engine) return res.status(503).json({ error: 'Reasoning engine not initialized' });
    await engine.save();
    res.json({ success: true });
  });

  console.log('[Agent Routes] Registered /api/agent/* routes');
}
