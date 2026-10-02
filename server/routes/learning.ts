// ============================================================================
// MYRAA Phase 28 — Learning System Server Routes
// REST API for continuous learning, evaluation, strategy health, drift,
// research, and the financial execution firewall status.
// ============================================================================

import type { Express, Request, Response } from 'express';
import type { ServerContext } from './types';

// Learning engines
import { forecastLifecycleManager } from '../../src/learning/forecastLifecycleManager';
import { continuousEvaluationEngine } from '../../src/learning/continuousEvaluationEngine';
import { strategyHealthEngine } from '../../src/learning/strategyHealthEngine';
import { driftDetectionEngine } from '../../src/learning/driftDetectionEngine';
import { postMortemEngine } from '../../src/learning/postMortemEngine';
import { researchLessonEngine } from '../../src/learning/researchLessonEngine';
import { researchHypothesisEngine } from '../../src/learning/researchHypothesisEngine';
import { researchQueueEngine } from '../../src/learning/researchQueueEngine';
import { strategyAdaptationEngine } from '../../src/learning/strategyAdaptationEngine';
import { providerQualityEngine } from '../../src/learning/providerQualityEngine';
import { biasDetectionEngine } from '../../src/learning/biasDetectionEngine';
import { metaEvaluationEngine } from '../../src/learning/metaEvaluationEngine';
import { learningSystemHealthEngine } from '../../src/learning/learningSystemHealthEngine';
import { attributionEngine } from '../../src/learning/attributionEngine';
import { liquidityMetricsEngine } from '../../src/learning/liquidityMetricsEngine';
import { GLOBAL_FIREWALL } from '../../src/quant/firewall';

export function registerLearningRoutes(app: Express, _ctx: ServerContext): void {

  // ============================================================================
  // SYSTEM HEALTH
  // ============================================================================

  app.get('/api/learning/health', (_req: Request, res: Response) => {
    res.json(learningSystemHealthEngine.getHealth());
  });

  // ============================================================================
  // TRADING POLICY — always returns DISABLED
  // ============================================================================

  app.get('/api/learning/trading-policy', (_req: Request, res: Response) => {
    res.json({
      liveTradingExecution: 'DISABLED',
      liveTradingExecutionBoolean: false,
      transferFunds: 'DISABLED',
      allowLlmOverride: false,
      message: 'MYRAA is permanently incapable of executing real financial transactions.',
      firewallPolicy: GLOBAL_FIREWALL.getPolicy(),
    });
  });

  // ============================================================================
  // FORECAST LIFECYCLE
  // ============================================================================

  app.get('/api/learning/forecasts', (req: Request, res: Response) => {
    const state = req.query.state as string | undefined;
    if (state) {
      const forecasts = forecastLifecycleManager.getForecastsByState(state as any);
      res.json(forecasts);
    } else {
      const map = forecastLifecycleManager.getForecastsMap();
      res.json(Array.from(map.values()));
    }
  });

  app.get('/api/learning/forecasts/:id', (req: Request, res: Response) => {
    const forecast = forecastLifecycleManager.getForecast(req.params.id);
    if (!forecast) return res.status(404).json({ error: 'Forecast not found' });
    res.json(forecast);
  });

  app.post('/api/learning/forecasts', (req: Request, res: Response) => {
    try {
      const forecast = forecastLifecycleManager.createForecast(req.body);
      res.status(201).json(forecast);
    } catch (error: any) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post('/api/learning/forecasts/:id/activate', (req: Request, res: Response) => {
    try {
      const forecast = forecastLifecycleManager.activateForecast(req.params.id);
      if (!forecast) return res.status(404).json({ error: 'Forecast not found' });
      res.json(forecast);
    } catch (error: any) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post('/api/learning/forecasts/:id/await-outcome', (req: Request, res: Response) => {
    try {
      const forecast = forecastLifecycleManager.awaitOutcome(req.params.id);
      if (!forecast) return res.status(404).json({ error: 'Forecast not found' });
      res.json(forecast);
    } catch (error: any) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post('/api/learning/forecasts/:id/outcome', (req: Request, res: Response) => {
    try {
      const outcome = forecastLifecycleManager.recordOutcome({
        forecastId: req.params.id,
        outcomeTimestamp: new Date().toISOString(),
        ...req.body,
      });
      if (!outcome) return res.status(404).json({ error: 'Forecast not found' });
      res.status(201).json(outcome);
    } catch (error: any) {
      res.status(400).json({ error: error.message });
    }
  });

  app.get('/api/learning/forecasts/:id/outcome', (req: Request, res: Response) => {
    const outcome = forecastLifecycleManager.getOutcome(req.params.id);
    if (!outcome) return res.status(404).json({ error: 'Outcome not found' });
    res.json(outcome);
  });

  // ============================================================================
  // EVALUATIONS
  // ============================================================================

  app.get('/api/learning/evaluations/:id', (req: Request, res: Response) => {
    const evaluation = forecastLifecycleManager.getEvaluation(req.params.id);
    if (!evaluation) return res.status(404).json({ error: 'Evaluation not found' });
    res.json(evaluation);
  });

  app.post('/api/learning/evaluate', (req: Request, res: Response) => {
    const { forecastId } = req.body;
    if (!forecastId) return res.status(400).json({ error: 'forecastId required' });
    const evaluation = forecastLifecycleManager.evaluateForecast(forecastId);
    if (!evaluation) return res.status(400).json({ error: 'Cannot evaluate' });
    res.json(evaluation);
  });

  app.post('/api/learning/evaluation/start', (_req: Request, res: Response) => {
    continuousEvaluationEngine.start();
    res.json({ message: 'Continuous evaluation engine started' });
  });

  app.post('/api/learning/evaluation/stop', (_req: Request, res: Response) => {
    continuousEvaluationEngine.stop();
    res.json({ message: 'Continuous evaluation engine stopped' });
  });

  app.get('/api/learning/evaluation/statistics', (_req: Request, res: Response) => {
    res.json(continuousEvaluationEngine.getStatistics());
  });

  // ============================================================================
  // STRATEGY HEALTH
  // ============================================================================

  app.get('/api/learning/strategy-health', (_req: Request, res: Response) => {
    res.json(strategyHealthEngine.getAllHealth());
  });

  app.get('/api/learning/strategy-health/:strategyId', (req: Request, res: Response) => {
    const health = strategyHealthEngine.getHealth(req.params.strategyId);
    if (!health) return res.status(404).json({ error: 'Strategy health not found' });
    res.json(health);
  });

  app.get('/api/learning/strategy-health/:strategyId/matrix', (req: Request, res: Response) => {
    res.json(strategyHealthEngine.getMatrix(req.params.strategyId));
  });

  // ============================================================================
  // DRIFT DETECTION
  // ============================================================================

  app.get('/api/learning/drift', (_req: Request, res: Response) => {
    res.json(driftDetectionEngine.getAllAlerts());
  });

  app.get('/api/learning/drift/active', (_req: Request, res: Response) => {
    res.json(driftDetectionEngine.getActiveAlerts());
  });

  app.get('/api/learning/drift/:type', (req: Request, res: Response) => {
    res.json(driftDetectionEngine.getAlertsByType(req.params.type as any));
  });

  // ============================================================================
  // POST-MORTEMS
  // ============================================================================

  app.get('/api/learning/postmortems', (_req: Request, res: Response) => {
    res.json(postMortemEngine.getAllPostMortems());
  });

  app.get('/api/learning/postmortems/:id', (req: Request, res: Response) => {
    const pm = postMortemEngine.getPostMortem(req.params.id);
    if (!pm) return res.status(404).json({ error: 'Post-mortem not found' });
    res.json(pm);
  });

  app.get('/api/learning/postmortems/patterns', (_req: Request, res: Response) => {
    const patterns = postMortemEngine.getFailurePatterns();
    const obj: Record<string, number> = {};
    patterns.forEach((v, k) => { obj[k] = v; });
    res.json(obj);
  });

  // ============================================================================
  // RESEARCH LESSONS
  // ============================================================================

  app.get('/api/learning/lessons', (req: Request, res: Response) => {
    const strategyId = req.query.strategyId as string | undefined;
    const regime = req.query.regime as string | undefined;
    if (strategyId) {
      res.json(researchLessonEngine.getLessonsByStrategy(strategyId));
    } else if (regime) {
      res.json(researchLessonEngine.getLessonsByRegime(regime as any));
    } else {
      res.json(researchLessonEngine.getAllLessons());
    }
  });

  app.post('/api/learning/lessons', (req: Request, res: Response) => {
    const lesson = researchLessonEngine.createLesson(req.body);
    res.status(201).json(lesson);
  });

  app.get('/api/learning/lessons/active', (_req: Request, res: Response) => {
    res.json(researchLessonEngine.getActiveLessons());
  });

  app.get('/api/learning/lessons/conflicts/:strategyId', (req: Request, res: Response) => {
    res.json(researchLessonEngine.getConflictingLessons(req.params.strategyId));
  });

  // ============================================================================
  // RESEARCH HYPOTHESES
  // ============================================================================

  app.get('/api/learning/hypotheses', (req: Request, res: Response) => {
    const status = req.query.status as string | undefined;
    if (status) {
      res.json(researchHypothesisEngine.getHypothesesByStatus(status as any));
    } else {
      res.json(researchHypothesisEngine.getAllHypotheses());
    }
  });

  app.post('/api/learning/hypotheses', (req: Request, res: Response) => {
    const hypothesis = researchHypothesisEngine.createHypothesis(req.body);
    res.status(201).json(hypothesis);
  });

  app.get('/api/learning/hypotheses/:id', (req: Request, res: Response) => {
    const h = researchHypothesisEngine.getHypothesis(req.params.id);
    if (!h) return res.status(404).json({ error: 'Hypothesis not found' });
    res.json(h);
  });

  app.post('/api/learning/hypotheses/:id/evaluate', (req: Request, res: Response) => {
    const { supported, pValue } = req.body;
    const h = researchHypothesisEngine.evaluateHypothesis(req.params.id, supported, pValue);
    if (!h) return res.status(404).json({ error: 'Hypothesis not found' });
    res.json(h);
  });

  // ============================================================================
  // RESEARCH QUEUE
  // ============================================================================

  app.get('/api/learning/research/queue', (_req: Request, res: Response) => {
    res.json(researchQueueEngine.getQueue());
  });

  app.post('/api/learning/research/enqueue', (req: Request, res: Response) => {
    try {
      const item = researchQueueEngine.enqueue(req.body);
      res.status(201).json(item);
    } catch (error: any) {
      res.status(400).json({ error: error.message });
    }
  });

  app.post('/api/learning/research/dequeue', (_req: Request, res: Response) => {
    const item = researchQueueEngine.dequeue();
    if (!item) return res.status(204).send();
    res.json(item);
  });

  // ============================================================================
  // STRATEGY ADAPTATION
  // ============================================================================

  app.get('/api/learning/adaptations', (_req: Request, res: Response) => {
    res.json(strategyAdaptationEngine.getAllProposals());
  });

  app.post('/api/learning/adaptations', (req: Request, res: Response) => {
    const proposal = strategyAdaptationEngine.createProposal(req.body);
    res.status(201).json(proposal);
  });

  app.get('/api/learning/adaptations/:id', (req: Request, res: Response) => {
    const p = strategyAdaptationEngine.getProposal(req.params.id);
    if (!p) return res.status(404).json({ error: 'Proposal not found' });
    res.json(p);
  });

  app.post('/api/learning/adaptations/:id/status', (req: Request, res: Response) => {
    const { status } = req.body;
    const p = strategyAdaptationEngine.updateStatus(req.params.id, status);
    if (!p) return res.status(404).json({ error: 'Proposal not found' });
    res.json(p);
  });

  app.post('/api/learning/adaptations/compare', (req: Request, res: Response) => {
    const result = strategyAdaptationEngine.compareChampionChallenger(req.body);
    res.json(result);
  });

  app.get('/api/learning/adaptations/comparisons', (_req: Request, res: Response) => {
    res.json(strategyAdaptationEngine.getAllComparisons());
  });

  // ============================================================================
  // PROVIDER QUALITY
  // ============================================================================

  app.get('/api/learning/providers', (_req: Request, res: Response) => {
    res.json(providerQualityEngine.getAllHealth());
  });

  app.get('/api/learning/providers/:id', (req: Request, res: Response) => {
    const h = providerQualityEngine.getHealth(req.params.id);
    if (!h) return res.status(404).json({ error: 'Provider health not found' });
    res.json(h);
  });

  app.get('/api/learning/providers/top/:count', (req: Request, res: Response) => {
    const count = parseInt(req.params.count) || 5;
    res.json(providerQualityEngine.getTopProviders(count));
  });

  // ============================================================================
  // BIAS DETECTION
  // ============================================================================

  app.get('/api/learning/bias', (_req: Request, res: Response) => {
    res.json(biasDetectionEngine.getAllAlerts());
  });

  // ============================================================================
  // META EVALUATION
  // ============================================================================

  app.get('/api/learning/meta-evaluation', (_req: Request, res: Response) => {
    res.json(metaEvaluationEngine.getResults());
  });

  app.get('/api/learning/meta-evaluation/inconsistent', (_req: Request, res: Response) => {
    res.json(metaEvaluationEngine.getInconsistentMetrics());
  });

  // ============================================================================
  // ATTRIBUTION
  // ============================================================================

  app.post('/api/learning/attribution', (req: Request, res: Response) => {
    const { strategyId, period, trades, benchmarkReturns, regimeData, factorExposures } = req.body;
    if (!strategyId || !period || !trades) {
      return res.status(400).json({ error: 'strategyId, period, and trades required' });
    }
    const attribution = attributionEngine.calculateAttribution(
      strategyId, period, trades, benchmarkReturns || [], regimeData || [], factorExposures || {}
    );
    res.json(attribution);
  });

  // ============================================================================
  // LIQUIDITY
  // ============================================================================

  app.post('/api/learning/liquidity', (req: Request, res: Response) => {
    const { symbol, currentBar, volume24h, spreadBps, historicalVolume, historicalSpread, historicalVolatility } = req.body;
    if (!symbol || !currentBar || volume24h === undefined || spreadBps === undefined) {
      return res.status(400).json({ error: 'symbol, currentBar, volume24h, spreadBps required' });
    }
    const metrics = liquidityMetricsEngine.calculateLiquidityMetrics(
      symbol, currentBar, volume24h, spreadBps,
      historicalVolume || [], historicalSpread || [], historicalVolatility || []
    );
    res.json(metrics);
  });

  // ============================================================================
  // FIREWALL
  // ============================================================================

  app.get('/api/learning/firewall/audit', (_req: Request, res: Response) => {
    res.json(GLOBAL_FIREWALL.getAuditLog());
  });

  app.get('/api/learning/firewall/policy', (_req: Request, res: Response) => {
    res.json(GLOBAL_FIREWALL.getPolicy());
  });

  app.post('/api/learning/firewall/classify', (req: Request, res: Response) => {
    const { action } = req.body;
    if (!action) return res.status(400).json({ error: 'action required' });
    const classification = GLOBAL_FIREWALL.classifyCapability(action);
    const decision = GLOBAL_FIREWALL.evaluate(action, classification);
    res.json({ classification, decision });
  });

  app.post('/api/learning/firewall/test-broker-block', (_req: Request, res: Response) => {
    const result = GLOBAL_FIREWALL.evaluate('execute_trade_broker', 'EXECUTE_TRADE');
    res.json({ blocked: !result.allowed, reason: result.reason });
  });

  // ============================================================================
  // RESEARCH REPORTS
  // ============================================================================

  app.get('/api/learning/research/hypotheses/validated', (_req: Request, res: Response) => {
    res.json(researchHypothesisEngine.getValidatedHypotheses());
  });

  app.get('/api/learning/research/hypotheses/refuted', (_req: Request, res: Response) => {
    res.json(researchHypothesisEngine.getRefutedHypotheses());
  });

  app.get('/api/learning/research/queue/stats', (_req: Request, res: Response) => {
    res.json({
      queueLength: researchQueueEngine.getQueueLength(),
      running: researchQueueEngine.getRunning().length,
      completed: researchQueueEngine.getCompleted().length,
      dailyCount: researchQueueEngine.getDailyCount(),
    });
  });

  app.get('/api/learning/research/queue/completed', (_req: Request, res: Response) => {
    res.json(researchQueueEngine.getCompleted());
  });
}
