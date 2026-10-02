// ============================================================================
// MYRAA Phase 27 — Quantitative Research REST API Routes
// ============================================================================

import { Router } from 'express';
import {
  BacktestEngine,
  WalkForwardEngine,
  MonteCarloEngine,
  SensitivityEngine,
  CalibrationEngine,
  EventStudyEngine,
  ExperimentRegistry,
  PaperTradingEngine,
  ExecutionFirewall,
  GLOBAL_FIREWALL,
  HistoricalDatasetEngine,
  StrategyRegistry,
  MetricsEngine,
  CostEngine,
  DEFAULT_COST_MODEL,
  DEFAULT_MONTE_CARLO_CONFIG,
} from '../../src/quant';
import type {
  CostModel, StrategyInstance, MonteCarloConfig,
  ForecastRecord, ForecastOutcome, EventStudyEntry,
} from '../../src/quant/contracts';

// --- Engine singletons ---

const experimentRegistry = new ExperimentRegistry();
const datasetEngine = new HistoricalDatasetEngine();
const strategyRegistry = new StrategyRegistry();
let paperTrading: PaperTradingEngine | null = null;

function ensurePaperTrading(): PaperTradingEngine {
  if (!paperTrading) {
    paperTrading = new PaperTradingEngine(100_000, DEFAULT_COST_MODEL);
  }
  return paperTrading;
}

// --- Router ---

const router = Router();

// 1. POST /quant/backtest
router.post('/quant/backtest', (req, res) => {
  try {
    const { dataset, strategyId, params: stratParams, strategyFn, costModel, initialCapital, riskFreeRate } = req.body;
    if (!dataset || !dataset.bars || !Array.isArray(dataset.bars) || dataset.bars.length === 0) {
      return res.json({ ok: false, error: 'dataset with bars array required' });
    }
    if (!strategyId) {
      return res.json({ ok: false, error: 'strategyId required' });
    }
    const strategy: StrategyInstance = {
      definitionId: strategyId,
      version: req.body.version || '1.0.0',
      params: stratParams || {},
    };
    const fn = strategyRegistry.getFunction(strategyId);
    if (!fn) {
      return res.json({ ok: false, error: `Strategy function '${strategyId}' not registered` });
    }
    const engine = new BacktestEngine();
    const result = engine.run({
      dataset,
      strategy,
      strategyFn: fn,
      costModel,
      initialCapital,
      riskFreeRate,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Backtest failed' });
  }
});

// 2. POST /quant/walkforward
router.post('/quant/walkforward', (req, res) => {
  try {
    const {
      dataset, strategyId, strategyFn, paramGrid,
      trainBars, testBars, stepBars, costModel, initialCapital,
      riskFreeRate, optimizationMetric,
    } = req.body;
    if (!dataset || !dataset.bars || !Array.isArray(dataset.bars) || dataset.bars.length === 0) {
      return res.json({ ok: false, error: 'dataset with bars array required' });
    }
    if (!strategyId) {
      return res.json({ ok: false, error: 'strategyId required' });
    }
    const fn = strategyRegistry.getFunction(strategyId);
    if (!fn) {
      return res.json({ ok: false, error: `Strategy function '${strategyId}' not registered` });
    }
    const engine = new WalkForwardEngine();
    const result = engine.run({
      dataset,
      strategyId,
      strategyFn: fn,
      registry: strategyRegistry,
      paramGrid: paramGrid || {},
      trainBars: trainBars || 252,
      testBars: testBars || 63,
      stepBars,
      costModel,
      initialCapital,
      riskFreeRate,
      optimizationMetric,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Walk-forward analysis failed' });
  }
});

// 3. POST /quant/montecarlo
router.post('/quant/montecarlo', (req, res) => {
  try {
    const { returns, strategyId, params: stratParams, config: cfgOverrides } = req.body;
    if (!returns || !Array.isArray(returns) || returns.length === 0) {
      return res.json({ ok: false, error: 'returns array required' });
    }
    if (!strategyId) {
      return res.json({ ok: false, error: 'strategyId required' });
    }
    const strategy: StrategyInstance = {
      definitionId: strategyId,
      version: req.body.version || '1.0.0',
      params: stratParams || {},
    };
    const engine = new MonteCarloEngine();
    const result = engine.run({
      returns,
      strategy,
      config: cfgOverrides,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Monte Carlo simulation failed' });
  }
});

// 4. POST /quant/sensitivity
router.post('/quant/sensitivity', (req, res) => {
  try {
    const {
      dataset, strategyId, params: stratParams, strategyFn,
      paramName, values, metric, costModel, initialCapital, riskFreeRate,
    } = req.body;
    if (!dataset || !dataset.bars || !Array.isArray(dataset.bars) || dataset.bars.length === 0) {
      return res.json({ ok: false, error: 'dataset with bars array required' });
    }
    if (!strategyId) {
      return res.json({ ok: false, error: 'strategyId required' });
    }
    if (!paramName) {
      return res.json({ ok: false, error: 'paramName required' });
    }
    const fn = strategyRegistry.getFunction(strategyId);
    if (!fn) {
      return res.json({ ok: false, error: `Strategy function '${strategyId}' not registered` });
    }
    const strategy: StrategyInstance = {
      definitionId: strategyId,
      version: req.body.version || '1.0.0',
      params: stratParams || {},
    };
    const engine = new SensitivityEngine();
    const result = engine.analyzeParameter({
      dataset,
      strategy,
      strategyFn: fn,
      paramName,
      values: values || [],
      metric,
      costModel,
      initialCapital,
      riskFreeRate,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Sensitivity analysis failed' });
  }
});

// 5. POST /quant/overfitting
router.post('/quant/overfitting', (req, res) => {
  try {
    const {
      inSampleResult, outOfSampleResult,
      totalStrategiesTested, riskFreeRate,
    } = req.body;
    if (!inSampleResult || !outOfSampleResult) {
      return res.json({ ok: false, error: 'inSampleResult and outOfSampleResult required' });
    }
    const engine = new SensitivityEngine();
    const result = engine.detectOverfitting({
      inSampleResult,
      outOfSampleResult,
      totalStrategiesTested: totalStrategiesTested || 1,
      riskFreeRate,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Overfitting detection failed' });
  }
});

// 6. POST /quant/calibrate
router.post('/quant/calibrate', (req, res) => {
  try {
    const { strategyId, forecasts, outcomes } = req.body;
    if (!forecasts || !Array.isArray(forecasts) || forecasts.length === 0) {
      return res.json({ ok: false, error: 'forecasts array required' });
    }
    if (!outcomes || !Array.isArray(outcomes) || outcomes.length === 0) {
      return res.json({ ok: false, error: 'outcomes array required' });
    }
    const engine = new CalibrationEngine();
    for (const f of forecasts as ForecastRecord[]) {
      engine.recordForecast(f);
    }
    for (const o of outcomes as ForecastOutcome[]) {
      engine.recordOutcome(o);
    }
    const result = engine.evaluate(strategyId);
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Calibration evaluation failed' });
  }
});

// 7. POST /quant/event-study
router.post('/quant/event-study', (req, res) => {
  try {
    const { event, bars, preWindow, postWindow } = req.body;
    if (!event || !event.eventId || !event.symbol || !event.eventTimestamp) {
      return res.json({ ok: false, error: 'event object with eventId, symbol, eventTimestamp required' });
    }
    if (!bars || !Array.isArray(bars) || bars.length === 0) {
      return res.json({ ok: false, error: 'bars array required' });
    }
    const engine = new EventStudyEngine();
    const result = engine.analyzeEvent({
      event,
      bars,
      preWindow: preWindow ?? -20,
      postWindow: postWindow ?? 20,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Event study failed' });
  }
});

// 8. GET /quant/experiments
router.get('/quant/experiments', (_req, res) => {
  try {
    const list = experimentRegistry.listExperiments();
    res.json({ ok: true, data: list });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to list experiments' });
  }
});

// 9. POST /quant/experiments
router.post('/quant/experiments', (req, res) => {
  try {
    const {
      name, description, strategyId, params: stratParams, version,
      datasetId, datasetSymbol, periodStart, periodEnd,
      costModel, parameters, seed,
    } = req.body;
    if (!name) {
      return res.json({ ok: false, error: 'name required' });
    }
    if (!strategyId) {
      return res.json({ ok: false, error: 'strategyId required' });
    }
    if (!datasetId) {
      return res.json({ ok: false, error: 'datasetId required' });
    }
    const strategy: StrategyInstance = {
      definitionId: strategyId,
      version: version || '1.0.0',
      params: stratParams || {},
    };
    const experiment = experimentRegistry.createExperiment({
      name,
      description: description || '',
      strategy,
      datasetId,
      datasetSymbol: datasetSymbol || 'UNKNOWN',
      periodStart: periodStart || '',
      periodEnd: periodEnd || '',
      costModel: costModel || DEFAULT_COST_MODEL,
      parameters,
      seed,
    });
    res.json({ ok: true, data: experiment });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to create experiment' });
  }
});

// 10. GET /quant/experiments/:id
router.get('/quant/experiments/:id', (req, res) => {
  try {
    const experiment = experimentRegistry.getExperiment(req.params.id);
    if (!experiment) {
      return res.json({ ok: false, error: `Experiment ${req.params.id} not found` });
    }
    res.json({ ok: true, data: experiment });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to get experiment' });
  }
});

// 11. GET /quant/experiments/:id/report
router.get('/quant/experiments/:id/report', (req, res) => {
  try {
    const report = experimentRegistry.generateReport(req.params.id);
    if (!report) {
      return res.json({ ok: false, error: `Report for experiment ${req.params.id} not found` });
    }
    res.json({ ok: true, data: report });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to get report' });
  }
});

// 12. POST /quant/paper/open
router.post('/quant/paper/open', (req, res) => {
  try {
    const { symbol, direction, price, quantity, stopLoss, takeProfit } = req.body;
    if (!symbol || !direction || !price || !quantity) {
      return res.json({ ok: false, error: 'symbol, direction, price, quantity required' });
    }
    const engine = ensurePaperTrading();
    const position = engine.openPosition({
      symbol,
      direction,
      entryPrice: price,
      quantity,
      stopLoss,
      takeProfit,
    });
    res.json({ ok: true, data: position });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to open paper position' });
  }
});

// 13. POST /quant/paper/close
router.post('/quant/paper/close', (req, res) => {
  try {
    const { positionId, price, reason } = req.body;
    if (!positionId || !price) {
      return res.json({ ok: false, error: 'positionId and price required' });
    }
    const engine = ensurePaperTrading();
    const result = engine.closePosition({
      positionId,
      exitPrice: price,
      reason,
    });
    if (!result) {
      return res.json({ ok: false, error: `Position ${positionId} not found` });
    }
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to close paper position' });
  }
});

// 14. GET /quant/paper/snapshot
router.get('/quant/paper/snapshot', (_req, res) => {
  try {
    const engine = ensurePaperTrading();
    const snapshot = engine.getSnapshot();
    res.json({ ok: true, data: snapshot });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to get snapshot' });
  }
});

// 15. GET /quant/paper/stats
router.get('/quant/paper/stats', (_req, res) => {
  try {
    const engine = ensurePaperTrading();
    const stats = engine.getStats();
    res.json({ ok: true, data: stats });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to get paper stats' });
  }
});

// 16. POST /quant/firewall/evaluate
router.post('/quant/firewall/evaluate', (req, res) => {
  try {
    const { action } = req.body;
    if (!action) {
      return res.json({ ok: false, error: 'action required' });
    }
    const decision = GLOBAL_FIREWALL.evaluate(action);
    res.json({ ok: true, data: decision });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Firewall evaluation failed' });
  }
});

// 17. GET /quant/strategies
router.get('/quant/strategies', (_req, res) => {
  try {
    const list = strategyRegistry.list();
    res.json({ ok: true, data: list });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to list strategies' });
  }
});

// 18. POST /quant/datasets
router.post('/quant/datasets', (req, res) => {
  try {
    const { symbol, timeframe, bars, source, survivorshipFilter } = req.body;
    if (!symbol) {
      return res.json({ ok: false, error: 'symbol required' });
    }
    if (!bars || !Array.isArray(bars) || bars.length === 0) {
      return res.json({ ok: false, error: 'bars array required' });
    }
    const result = datasetEngine.buildDataset({
      symbol,
      timeframe: timeframe || '1d',
      bars,
      source,
      survivorshipFilter,
    });
    res.json({ ok: true, data: result });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to create dataset' });
  }
});

// 19. GET /quant/datasets
router.get('/quant/datasets', (_req, res) => {
  try {
    const list = datasetEngine.listDatasets();
    res.json({ ok: true, data: list });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Failed to list datasets' });
  }
});

// 20. GET /quant/status
router.get('/quant/status', (_req, res) => {
  try {
    res.json({
      ok: true,
      data: {
        phase: 27,
        engines: {
          backtest: true,
          walkForward: true,
          monteCarlo: true,
          sensitivity: true,
          calibration: true,
          eventStudy: true,
          experiments: true,
          paperTrading: !!paperTrading,
          firewall: true,
          datasets: true,
          strategies: true,
        },
        experimentCount: experimentRegistry.listExperiments().length,
        datasetCount: datasetEngine.listDatasets().length,
        strategyCount: strategyRegistry.list().length,
        firewallPolicy: GLOBAL_FIREWALL.getPolicy(),
      },
    });
  } catch (err) {
    res.json({ ok: false, error: err instanceof Error ? err.message : 'Status check failed' });
  }
});

export default router;
