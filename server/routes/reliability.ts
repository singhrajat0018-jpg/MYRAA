// ============================================================================
// MYRAA Phase 25 — Reliability REST API Routes
// ============================================================================

import { Router, Request, Response } from 'express';
import { ClosedLoopOrchestrator } from '../../src/reliability/orchestrator';

const router = Router();
const orchestrator = new ClosedLoopOrchestrator();

// --- Health ---

router.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    module: 'reliability',
    traceCount: orchestrator.getTrace().length,
    experienceStats: orchestrator.experienceEngine.getStats(),
  });
});

// --- Trace ---

router.get('/trace', (req: Request, res: Response) => {
  const actionId = req.query.actionId as string | undefined;
  res.json(orchestrator.getTrace(actionId));
});

router.get('/trace/:actionId/summary', (req: Request, res: Response) => {
  res.json({ summary: orchestrator.getTraceSummary(req.params.actionId) });
});

// --- Verification ---

router.get('/verification/:actionId', (req: Request, res: Response) => {
  res.json(orchestrator.verificationEngine.getResults(req.params.actionId));
});

router.get('/verification/source-reliability/:source', (req: Request, res: Response) => {
  const source = req.params.source as any;
  res.json({ source, reliability: orchestrator.verificationEngine.getSourceReliability(source) });
});

// --- Diagnosis ---

router.get('/diagnosis', (req: Request, res: Response) => {
  const actionId = req.query.actionId as string | undefined;
  res.json(orchestrator.diagnosisEngine.getDiagnosisHistory(actionId));
});

router.get('/diagnosis/most-common', (_req: Request, res: Response) => {
  res.json({ failureClass: orchestrator.diagnosisEngine.getMostCommonFailureClass() });
});

// --- Recovery ---

router.get('/recovery/budget', (_req: Request, res: Response) => {
  res.json(orchestrator.recoveryEngine.getBudget());
});

router.get('/recovery/history', (_req: Request, res: Response) => {
  res.json(orchestrator.recoveryEngine.getExecutionHistory());
});

router.get('/recovery/success-rate', (_req: Request, res: Response) => {
  res.json({ successRate: orchestrator.recoveryEngine.getSuccessRate() });
});

router.post('/recovery/reset-budget', (_req: Request, res: Response) => {
  orchestrator.recoveryEngine.resetBudget();
  res.json({ success: true });
});

// --- Experience ---

router.get('/experience', (_req: Request, res: Response) => {
  res.json(orchestrator.experienceEngine.getExperiences());
});

router.get('/experience/stats', (_req: Request, res: Response) => {
  res.json(orchestrator.experienceEngine.getStats());
});

router.post('/experience/suggest', (req: Request, res: Response) => {
  const { taskType, actionType, domain } = req.body;
  const suggestion = orchestrator.experienceEngine.suggestStrategy(taskType, actionType, domain);
  res.json(suggestion);
});

// --- Plan Patching ---

router.get('/patches', (req: Request, res: Response) => {
  const planId = req.query.planId as string | undefined;
  res.json(planId ? orchestrator.planPatcher.getPatchesForPlan(planId) : orchestrator.planPatcher.getAllPatches());
});

// --- Unknown Outcome ---

router.get('/outcomes', (_req: Request, res: Response) => {
  res.json(orchestrator.unknownOutcomeHandler.getAllAssessments());
});

// --- State ---

router.get('/state', (_req: Request, res: Response) => {
  const current = orchestrator.stateEstimator.getCurrentState();
  const version = orchestrator.stateEstimator.getLatestVersion();
  res.json({ current, version, historyLength: orchestrator.stateEstimator.getHistory().length });
});

// --- Clear ---

router.post('/clear', (_req: Request, res: Response) => {
  orchestrator.clear();
  res.json({ success: true });
});

export default router;
