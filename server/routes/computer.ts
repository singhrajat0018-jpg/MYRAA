// ============================================================================
// MYRAA Computer Control REST API Routes
// ============================================================================

import { Router, Request, Response } from 'express';
import type { ComputerAction, ComputerEnvironment } from '../../src/computer/contracts';
import { getComputerControlEngine } from '../../src/computer/engine';
import type { EngineState } from '../../src/computer/engine';

const router = Router();
const engine = getComputerControlEngine();

// --- Health ---

router.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    module: 'computer-control',
    initialized: engine.getState().initialized,
    actionsExecuted: engine.getState().totalActionsExecuted,
  });
});

// --- State ---

router.get('/state', (_req: Request, res: Response) => {
  const state: EngineState = engine.getState();
  res.json(state);
});

// --- Execute Action ---

router.post('/execute', async (req: Request, res: Response) => {
  try {
    const action: ComputerAction = req.body;
    if (!action.actionId || !action.type) {
      res.status(400).json({ error: 'Missing actionId or type' });
      return;
    }

    // The TS engine is planning/policy logic only: its execution leaf is a
    // simulator and must never report OS-level success. Real desktop control
    // executes exclusively through the Python desktop agent (POST /execute),
    // where ValidationLayer + PermissionManager + F7 recovery apply.
    res.status(501).json({
      error: 'Computer action execution is not served here. Use POST /execute on the Python desktop agent (http://127.0.0.1:8765), which enforces validation, permissions, and recovery.',
    });
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : 'Unknown error' });
  }
});

// --- Execute Transaction ---

router.post('/transaction', async (req: Request, res: Response) => {
  try {
    const { actions } = req.body;
    if (!Array.isArray(actions) || actions.length === 0) {
      res.status(400).json({ error: 'Missing or empty actions array' });
      return;
    }

    // See /execute above: planning/policy only here, no OS execution.
    res.status(501).json({
      error: 'Computer transaction execution is not served here. Use the Python desktop agent, which enforces validation, permissions, and recovery.',
    });
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : 'Unknown error' });
  }
});

// --- Target Resolution ---

router.post('/resolve-target', (req: Request, res: Response) => {
  try {
    const { query } = req.body;
    if (!query || typeof query !== 'string') {
      res.status(400).json({ error: 'Missing query' });
      return;
    }

    const result = engine.findTarget(query);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : 'Unknown error' });
  }
});

// --- Visual Targeting ---

router.post('/find-visual', async (req: Request, res: Response) => {
  try {
    const { description } = req.body;
    if (!description || typeof description !== 'string') {
      res.status(400).json({ error: 'Missing description' });
      return;
    }

    const result = await engine.findTargetVisual(description);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : 'Unknown error' });
  }
});

// --- Environment Update ---

router.post('/environment', (req: Request, res: Response) => {
  try {
    const env: ComputerEnvironment = req.body;
    if (!env.timestamp || !env.screens) {
      res.status(400).json({ error: 'Missing timestamp or screens' });
      return;
    }

    engine.updateEnvironment(env);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : 'Unknown error' });
  }
});

// --- DPI Calibration ---

router.get('/dpi/:screenId', (req: Request, res: Response) => {
  const screenId = parseInt(req.params.screenId, 10);
  if (isNaN(screenId)) {
    res.status(400).json({ error: 'Invalid screenId' });
    return;
  }

  const cal = engine.getDPICalibration(screenId);
  if (!cal) {
    res.status(404).json({ error: 'No calibration for this screen' });
    return;
  }

  res.json(cal);
});

// --- Policy ---

router.get('/policy/rules', (_req: Request, res: Response) => {
  const rules = engine.getPolicyEngine().getRules();
  res.json(rules.map(r => ({ id: r.id, name: r.name, description: r.description, risk: r.risk })));
});

// --- Takeover ---

router.post('/takeover/pause', (_req: Request, res: Response) => {
  engine.pauseForTakeover();
  res.json({ success: true });
});

router.post('/takeover/resume', (_req: Request, res: Response) => {
  engine.resumeAfterTakeover();
  res.json({ success: true });
});

router.post('/emergency-stop', (_req: Request, res: Response) => {
  engine.emergencyStop();
  res.json({ success: true });
});

// --- Budget ---

router.post('/budget/reset', (_req: Request, res: Response) => {
  engine.resetBudget();
  res.json({ success: true, budget: engine.getState().budget });
});

// --- Telemetry ---

router.get('/telemetry', (req: Request, res: Response) => {
  const limit = parseInt(req.query.limit as string) || 50;
  res.json(engine.getTelemetry(limit));
});

export default router;
