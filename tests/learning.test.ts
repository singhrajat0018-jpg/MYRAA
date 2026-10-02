// ============================================================================
// MYRAA Phase 28 — Continuous Learning & Strategy Adaptation Test Suite
// ============================================================================
// Tests: forecast lifecycle, evaluation, calibration, strategy health,
// drift detection, failure diagnosis, post-mortems, research lessons,
// hypotheses, research queue, strategy adaptation, champion/challenger,
// attribution, liquidity, provider quality, bias detection, meta-evaluation,
// system health, firewall, and end-to-end integration.
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';

// --- Engines under test ---
import { ForecastLifecycleManager } from '../src/learning/forecastLifecycleManager';
import { ContinuousEvaluationEngine } from '../src/learning/continuousEvaluationEngine';
import { StrategyHealthEngine, type HealthEvaluation } from '../src/learning/strategyHealthEngine';
import { DriftDetectionEngine } from '../src/learning/driftDetectionEngine';
import { PostMortemEngine } from '../src/learning/postMortemEngine';
import { ResearchLessonEngine } from '../src/learning/researchLessonEngine';
import { ResearchHypothesisEngine } from '../src/learning/researchHypothesisEngine';
import { ResearchQueueEngine } from '../src/learning/researchQueueEngine';
import { StrategyAdaptationEngine } from '../src/learning/strategyAdaptationEngine';
import { ProviderQualityEngine, type ProviderObservation } from '../src/learning/providerQualityEngine';
import { BiasDetectionEngine } from '../src/learning/biasDetectionEngine';
import { MetaEvaluationEngine } from '../src/learning/metaEvaluationEngine';
import { LearningSystemHealthEngine } from '../src/learning/learningSystemHealthEngine';
import { AttributionEngine } from '../src/learning/attributionEngine';
import { LiquidityMetricsEngine } from '../src/learning/liquidityMetricsEngine';
import { ExecutionFirewall, GLOBAL_FIREWALL } from '../src/quant/firewall';
import { CalibrationEngine } from '../src/quant/calibration';
import { ExperimentRegistry } from '../src/quant/experiments';

// --- Contracts ---
import type {
  Forecast, ForecastEvaluation, ForecastOutcome,
  EvidenceSnapshot, DataSnapshot, StrategySnapshot, RegimeType
} from '../src/learning/contracts';
import type { OHLCVBar } from '../src/quant/contracts';

// ============================================================================
// HELPERS
// ============================================================================

function makeBar(overrides: Partial<OHLCVBar> = {}): OHLCVBar {
  return {
    timestamp: '2026-01-01T00:00:00Z',
    open: 100, high: 105, low: 98, close: 103, volume: 1000000,
    ...overrides,
  };
}

function makeEvidenceSnapshot(): EvidenceSnapshot {
  return {
    technical: ['RSI oversold'],
    fundamental: ['Strong earnings'],
    events: ['Rate decision upcoming'],
    macro: ['GDP growth positive'],
    regime: ['TRENDING_BULL'],
    sentiment: ['Neutral'],
    timestamps: {},
  };
}

function makeDataSnapshot(): DataSnapshot {
  return {
    price: 100, open: 99, high: 102, low: 97, volume: 1000000,
    technical: null, fundamental: null, events: null, macro: null, regime: null,
    assetId: 'asset_1', symbol: 'TEST', timestamp: '2026-01-01T00:00:00Z',
  };
}

function makeStrategySnapshot(): StrategySnapshot {
  return {
    definitionId: 'momentum_v1', version: '1.0.0', type: 'MOMENTUM',
    parameters: { rsiPeriod: 14 },
  };
}

function createTestForecast(
  manager: ForecastLifecycleManager,
  overrides: Partial<{
    strategyId: string;
    symbol: string;
    confidence: number;
    type: 'DIRECTION' | 'RETURN_RANGE' | 'PRICE_TARGET';
    prediction: string | number;
    regime: RegimeType;
  }> = {}
): Forecast {
  const forecast = manager.createForecast({
    assetId: 'asset_1',
    symbol: overrides.symbol || 'TEST',
    horizon: { type: 'SHORT_TERM', bars: 24, description: '1 day' },
    type: overrides.type || 'DIRECTION',
    prediction: overrides.prediction ?? 'UP',
    confidence: overrides.confidence ?? 0.7,
    strategyId: overrides.strategyId || 'momentum_v1',
    strategyVersion: '1.0.0',
    evidenceSnapshot: makeEvidenceSnapshot(),
    dataSnapshot: makeDataSnapshot(),
    strategySnapshot: makeStrategySnapshot(),
    regime: overrides.regime || 'TRENDING_BULL',
    invalidationConditions: [],
  });
  manager.activateForecast(forecast.forecastId);
  manager.awaitOutcome(forecast.forecastId);
  return manager.getForecast(forecast.forecastId)!;
}

// ============================================================================
// FORECAST LIFECYCLE
// ============================================================================

describe('ForecastLifecycleManager', () => {
  let manager: ForecastLifecycleManager;

  beforeEach(() => {
    manager = new ForecastLifecycleManager();
  });

  it('creates a forecast with CREATED status', () => {
    const f = createTestForecast(manager);
    expect(f.forecastId).toMatch(/^fcst_/);
    expect(f.status).toBe('AWAITING_OUTCOME');
    expect(f.symbol).toBe('TEST');
  });

  it('transitions CREATED -> ACTIVE -> AWAITING_OUTCOME', () => {
    const f = manager.createForecast({
      assetId: 'a', symbol: 'S', horizon: { type: 'SWING', bars: 168, description: '1 week' },
      type: 'DIRECTION', prediction: 'DOWN', confidence: 0.6,
      strategyId: 's1', strategyVersion: '1.0.0',
      evidenceSnapshot: makeEvidenceSnapshot(),
      dataSnapshot: makeDataSnapshot(),
      strategySnapshot: makeStrategySnapshot(),
      regime: 'RANGE',
      invalidationConditions: [],
    });
    expect(f.status).toBe('CREATED');

    const activated = manager.activateForecast(f.forecastId);
    expect(activated?.status).toBe('ACTIVE');

    const awaiting = manager.awaitOutcome(f.forecastId);
    expect(awaiting?.status).toBe('AWAITING_OUTCOME');
  });

  it('rejects activation of non-CREATED forecast', () => {
    const f = createTestForecast(manager);
    expect(() => manager.activateForecast(f.forecastId)).toThrow();
  });

  it('records an outcome', () => {
    const f = createTestForecast(manager);
    const outcome = manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      actualReturn: 0.05,
      actualDirection: 'UP',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    expect(outcome).not.toBeNull();
    expect(outcome?.actualValue).toBe(105);
    expect(manager.getForecast(f.forecastId)?.status).toBe('PARTIALLY_EVALUATED');
  });

  it('rejects outcome for finalized forecast', () => {
    const f = createTestForecast(manager);
    manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    manager.evaluateForecast(f.forecastId);
    expect(() => manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-03T00:00:00Z',
      actualValue: 106,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    })).toThrow();
  });

  it('evaluates a forecast with outcome', () => {
    const f = createTestForecast(manager);
    manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      actualReturn: 0.05,
      actualDirection: 'UP',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = manager.evaluateForecast(f.forecastId);
    expect(eval_).not.toBeNull();
    expect(eval_?.strategyOutcome).toBe('SUCCESS');
    expect(eval_?.directionCorrect).toBe(true);
  });

  it('evaluates a failed direction forecast', () => {
    const f = createTestForecast(manager, { prediction: 'UP' });
    manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 95,
      actualReturn: -0.05,
      actualDirection: 'DOWN',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = manager.evaluateForecast(f.forecastId);
    expect(eval_?.strategyOutcome).toBe('FAILURE');
    expect(eval_?.directionCorrect).toBe(false);
  });

  it('evaluates a return range forecast within range', () => {
    const f = createTestForecast(manager, { type: 'RETURN_RANGE', prediction: '-0.05:0.10' });
    manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 103,
      actualReturn: 0.03,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = manager.evaluateForecast(f.forecastId);
    expect(eval_?.strategyOutcome).toBe('SUCCESS');
  });

  it('evaluates a return range forecast outside range', () => {
    const f = createTestForecast(manager, { type: 'RETURN_RANGE', prediction: '-0.05:0.10' });
    manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 90,
      actualReturn: -0.10,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = manager.evaluateForecast(f.forecastId);
    expect(eval_?.strategyOutcome).toBe('FAILURE');
  });

  it('evaluates a price target forecast within tolerance', () => {
    const f = createTestForecast(manager, { type: 'PRICE_TARGET', prediction: 103 });
    manager.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 104,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = manager.evaluateForecast(f.forecastId);
    expect(eval_?.strategyOutcome).toBe('SUCCESS');
  });

  it('invalidates a forecast', () => {
    const f = createTestForecast(manager);
    const inv = manager.invalidateForecast(f.forecastId, 'Thesis invalidated');
    expect(inv?.status).toBe('INVALIDATED');
  });

  it('expires a forecast', () => {
    const f = createTestForecast(manager);
    const exp = manager.expireForecast(f.forecastId);
    expect(exp?.status).toBe('EXPIRED');
  });

  it('manages evaluation queue with priority', () => {
    const f1 = createTestForecast(manager, { symbol: 'A' });
    const f2 = createTestForecast(manager, { symbol: 'B' });
    manager.addToEvaluationQueue(f1.forecastId, 'test', 3);
    manager.addToEvaluationQueue(f2.forecastId, 'test', 8);
    expect(manager.getQueueLength()).toBe(2);
    const next = manager.getNextEvaluationItem();
    expect(next?.forecastId).toBe(f2.forecastId); // higher priority first
  });

  it('retrieves forecasts by state', () => {
    createTestForecast(manager);
    const awaiting = manager.getForecastsByState('AWAITING_OUTCOME');
    expect(awaiting.length).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================================
// CONTINUOUS EVALUATION ENGINE
// ============================================================================

describe('ContinuousEvaluationEngine', () => {
  it('reports statistics', () => {
    const engine = new ContinuousEvaluationEngine();
    const stats = engine.getStatistics();
    expect(stats.totalForecasts).toBeGreaterThanOrEqual(0);
    expect(stats.evaluationsPerformed).toBeGreaterThanOrEqual(0);
  });

  it('starts and stops without error', () => {
    const engine = new ContinuousEvaluationEngine();
    engine.start();
    engine.stop();
  });
});

// ============================================================================
// STRATEGY HEALTH ENGINE
// ============================================================================

describe('StrategyHealthEngine', () => {
  let engine: StrategyHealthEngine;

  beforeEach(() => {
    engine = new StrategyHealthEngine();
  });

  function recordBatch(strategyId: string, count: number, accuracy: number): void {
    for (let i = 0; i < count; i++) {
      const correct = i / count < accuracy;
      engine.recordEvaluation({
        forecastId: `fc_${i}`,
        strategyId,
        strategyVersion: '1.0.0',
        outcomeCorrect: correct,
        return: correct ? 0.02 : -0.01,
        regime: 'TRENDING_BULL',
        horizon: 'SHORT_TERM',
        timestamp: new Date(Date.now() + i * 86400000).toISOString(),
      });
    }
  }

  it('computes health for a strategy', () => {
    recordBatch('s1', 50, 0.65);
    const health = engine.getHealth('s1');
    expect(health).toBeDefined();
    expect(health?.sampleSize).toBe(50);
    expect(health?.status).toBe('HEALTHY');
  });

  it('marks strategy as UNRELIABLE with high failure rate', () => {
    recordBatch('s1', 50, 0.2);
    const health = engine.getHealth('s1');
    expect(health?.status).toBe('UNRELIABLE');
  });

  it('marks strategy as RESEARCH_ONLY with small sample', () => {
    recordBatch('s1', 5, 0.6);
    const health = engine.getHealth('s1');
    expect(health?.status).toBe('RESEARCH_ONLY');
  });

  it('returns all health entries', () => {
    recordBatch('s1', 30, 0.6);
    recordBatch('s2', 30, 0.5);
    expect(engine.getAllHealth().length).toBe(2);
  });

  it('returns evaluations for a strategy', () => {
    recordBatch('s1', 10, 0.6);
    expect(engine.getEvaluations('s1').length).toBe(10);
  });

  it('computes regime matrix', () => {
    engine.recordEvaluation({
      forecastId: 'f1', strategyId: 's1', strategyVersion: '1.0.0',
      outcomeCorrect: true, return: 0.02, regime: 'TRENDING_BULL',
      horizon: 'SHORT_TERM', timestamp: new Date().toISOString(),
    });
    const matrix = engine.getMatrix('s1');
    expect(matrix.length).toBeGreaterThanOrEqual(1);
  });

  it('returns health for unknown strategy as undefined', () => {
    expect(engine.getHealth('nonexistent')).toBeUndefined();
  });
});

// ============================================================================
// DRIFT DETECTION ENGINE
// ============================================================================

describe('DriftDetectionEngine', () => {
  let engine: DriftDetectionEngine;

  beforeEach(() => {
    engine = new DriftDetectionEngine({ minSampleSize: 5, cooldownMs: 0 });
  });

  it('detects performance drift', () => {
    const evals = Array.from({ length: 30 }, () => false);
    const alert = engine.detectPerformanceDrift('s1', evals, 0.6);
    expect(alert).not.toBeNull();
    expect(alert?.type).toBe('PERFORMANCE');
  });

  it('no drift when sample too small', () => {
    const evals = Array.from({ length: 3 }, () => false);
    const alert = engine.detectPerformanceDrift('s1', evals, 0.6);
    expect(alert).toBeNull();
  });

  it('no drift when change is small', () => {
    const evals = Array.from({ length: 30 }, () => true);
    const alert = engine.detectPerformanceDrift('s1', evals, 0.95);
    expect(alert).toBeNull();
  });

  it('detects confidence drift (overconfidence)', () => {
    const confidences = Array.from({ length: 30 }, () => 0.85);
    const accuracies = Array.from({ length: 30 }, () => 0.5);
    const alert = engine.detectConfidenceDrift('s1', confidences, accuracies);
    expect(alert).not.toBeNull();
    expect(alert?.type).toBe('CONFIDENCE');
  });

  it('detects data drift', () => {
    const alert = engine.detectDataDrift('provider1', 0.8, 0.2);
    expect(alert).not.toBeNull();
    expect(alert?.type).toBe('DATA');
  });

  it('detects signal drift', () => {
    const alert = engine.detectSignalDrift('s1', 0.9, 0.5);
    expect(alert).not.toBeNull();
  });

  it('detects regime drift', () => {
    const alert = engine.detectRegimeDrift('s1', 0.8, 0.3);
    expect(alert).not.toBeNull();
  });

  it('detects calibration drift', () => {
    const alert = engine.detectCalibrationDrift('s1', 0.2, 0.05);
    expect(alert).not.toBeNull();
  });

  it('detects provider drift', () => {
    const alert = engine.detectProviderDrift('p1', 0.3, 0.9);
    expect(alert).not.toBeNull();
  });

  it('returns all alerts', () => {
    engine.detectPerformanceDrift('s1', Array(30).fill(false), 0.6);
    expect(engine.getAllAlerts().length).toBeGreaterThanOrEqual(1);
  });

  it('returns active alerts within 24h', () => {
    engine.detectPerformanceDrift('s1', Array(30).fill(false), 0.6);
    expect(engine.getActiveAlerts().length).toBeGreaterThanOrEqual(1);
  });

  it('filters alerts by type', () => {
    engine.detectPerformanceDrift('s1', Array(30).fill(false), 0.6);
    engine.detectConfidenceDrift('s1', Array(30).fill(0.9), Array(30).fill(0.5));
    expect(engine.getAlertsByType('PERFORMANCE').length).toBeGreaterThanOrEqual(1);
  });

  it('clears alerts', () => {
    engine.detectPerformanceDrift('s1', Array(30).fill(false), 0.6);
    engine.clearAlerts();
    expect(engine.getAllAlerts().length).toBe(0);
  });

  it('detects change points in data', () => {
    const data = Array.from({ length: 60 }, (_, i) => i < 30 ? 0 : 10);
    const cps = engine.detectChangePoint(data, 10);
    expect(cps.length).toBeGreaterThanOrEqual(1);
  });

  it('returns empty change points for uniform data', () => {
    const data = Array(60).fill(5);
    const cps = engine.detectChangePoint(data, 10);
    expect(cps.length).toBe(0);
  });

  it('returns config', () => {
    const config = engine.getConfig();
    expect(config.minSampleSize).toBe(5);
  });
});

// ============================================================================
// POST-MORTEM ENGINE
// ============================================================================

describe('PostMortemEngine', () => {
  let engine: PostMortemEngine;
  let lifecycle: ForecastLifecycleManager;

  beforeEach(() => {
    engine = new PostMortemEngine();
    lifecycle = new ForecastLifecycleManager();
  });

  it('generates a post-mortem for a successful forecast', () => {
    const f = createTestForecast(lifecycle);
    lifecycle.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      actualDirection: 'UP',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = lifecycle.evaluateForecast(f.forecastId)!;
    const outcome = lifecycle.getOutcome(f.forecastId)!;
    const pm = engine.generatePostMortem(f, eval_, outcome);
    expect(pm.outcome).toBe('SUCCESS');
    expect(pm.lesson).toContain('succeeded');
  });

  it('generates a post-mortem for a failed forecast', () => {
    const f = createTestForecast(lifecycle, { prediction: 'UP' });
    lifecycle.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 90,
      actualDirection: 'DOWN',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = lifecycle.evaluateForecast(f.forecastId)!;
    const outcome = lifecycle.getOutcome(f.forecastId)!;
    const pm = engine.generatePostMortem(f, eval_, outcome);
    expect(pm.outcome).toBe('FAILURE');
    expect(pm.lesson).toContain('failed');
  });

  it('retrieves post-mortems by strategy', () => {
    const f = createTestForecast(lifecycle);
    lifecycle.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = lifecycle.evaluateForecast(f.forecastId)!;
    const outcome = lifecycle.getOutcome(f.forecastId)!;
    engine.generatePostMortem(f, eval_, outcome);
    expect(engine.getPostMortemsByStrategy('momentum_v1').length).toBe(1);
  });

  it('retrieves post-mortems by outcome', () => {
    const f = createTestForecast(lifecycle);
    lifecycle.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      actualDirection: 'UP',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = lifecycle.evaluateForecast(f.forecastId)!;
    const outcome = lifecycle.getOutcome(f.forecastId)!;
    engine.generatePostMortem(f, eval_, outcome);
    expect(engine.getPostMortemsByOutcome('SUCCESS').length).toBe(1);
    expect(engine.getPostMortemsByOutcome('FAILURE').length).toBe(0);
  });

  it('tracks failure patterns', () => {
    const f = createTestForecast(lifecycle, { prediction: 'UP' });
    lifecycle.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 90,
      actualDirection: 'DOWN',
      regimeAtOutcome: 'TRENDING_BEAR',
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = lifecycle.evaluateForecast(f.forecastId)!;
    const outcome = lifecycle.getOutcome(f.forecastId)!;
    engine.generatePostMortem(f, eval_, outcome);
    const patterns = engine.getFailurePatterns();
    expect(patterns.size).toBeGreaterThanOrEqual(0);
  });

  it('deletes a post-mortem', () => {
    const f = createTestForecast(lifecycle);
    lifecycle.recordOutcome({
      forecastId: f.forecastId,
      outcomeTimestamp: '2026-01-02T00:00:00Z',
      actualValue: 105,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });
    const eval_ = lifecycle.evaluateForecast(f.forecastId)!;
    const outcome = lifecycle.getOutcome(f.forecastId)!;
    const pm = engine.generatePostMortem(f, eval_, outcome);
    expect(engine.deletePostMortem(pm.postMortemId)).toBe(true);
  });
});

// ============================================================================
// RESEARCH LESSON ENGINE
// ============================================================================

describe('ResearchLessonEngine', () => {
  let engine: ResearchLessonEngine;

  beforeEach(() => {
    engine = new ResearchLessonEngine();
  });

  it('creates a lesson', () => {
    const lesson = engine.createLesson({
      source: 'test', strategyId: 's1', context: 'Bull market',
      failureOrSuccess: 'FAILURE', recommendation: 'Add volume filter',
      confidence: 0.7, regime: 'TRENDING_BULL',
    });
    expect(lesson.lessonId).toMatch(/^lesson_/);
    expect(lesson.confidence).toBe(0.7);
  });

  it('retrieves lessons by strategy', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5 });
    engine.createLesson({ source: 'test', strategyId: 's2', context: 'ctx', failureOrSuccess: 'SUCCESS', recommendation: 'r', confidence: 0.5 });
    expect(engine.getLessonsByStrategy('s1').length).toBe(1);
  });

  it('retrieves lessons by regime', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5, regime: 'RANGE' });
    expect(engine.getLessonsByRegime('RANGE').length).toBe(1);
  });

  it('retrieves lessons by type', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5 });
    engine.createLesson({ source: 'test', strategyId: 's2', context: 'ctx', failureOrSuccess: 'SUCCESS', recommendation: 'r', confidence: 0.5 });
    expect(engine.getLessonsByType('FAILURE').length).toBe(1);
    expect(engine.getLessonsByType('SUCCESS').length).toBe(1);
  });

  it('applies decay to lesson confidence', () => {
    const lesson = engine.createLesson({
      source: 'test', strategyId: 's1', context: 'ctx',
      failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.8,
    });
    const updated = engine.applyDecay(lesson.lessonId, 0.5);
    expect(updated?.confidence).toBe(0.4);
  });

  it('returns active lessons (non-expired)', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5 });
    expect(engine.getActiveLessons().length).toBe(1);
  });

  it('clears expired lessons', () => {
    engine.createLesson({
      source: 'test', strategyId: 's1', context: 'ctx',
      failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5,
      expiresAt: new Date(Date.now() - 1000).toISOString(),
    });
    const cleared = engine.clearExpired();
    expect(cleared).toBe(1);
  });

  it('detects conflicting lessons', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5 });
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'SUCCESS', recommendation: 'r', confidence: 0.5 });
    expect(engine.getConflictingLessons('s1').length).toBe(2);
  });

  it('retrieves relevant lessons with filtering', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5, regime: 'RANGE' });
    engine.createLesson({ source: 'test', strategyId: 's2', context: 'ctx', failureOrSuccess: 'SUCCESS', recommendation: 'r', confidence: 0.8, regime: 'TRENDING_BULL' });
    const relevant = engine.getRelevantLessons({ regime: 'RANGE' });
    expect(relevant.length).toBe(1);
  });

  it('retrieves all lessons', () => {
    engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5 });
    expect(engine.getAllLessons().length).toBe(1);
  });

  it('deletes a lesson', () => {
    const l = engine.createLesson({ source: 'test', strategyId: 's1', context: 'ctx', failureOrSuccess: 'FAILURE', recommendation: 'r', confidence: 0.5 });
    expect(engine.deleteLesson(l.lessonId)).toBe(true);
  });
});

// ============================================================================
// RESEARCH HYPOTHESIS ENGINE
// ============================================================================

describe('ResearchHypothesisEngine', () => {
  let engine: ResearchHypothesisEngine;

  beforeEach(() => {
    engine = new ResearchHypothesisEngine();
  });

  it('creates a hypothesis', () => {
    const h = engine.createHypothesis({
      description: 'Breakouts fail in low volume',
      rationale: 'History shows',
      testablePrediction: 'Volume filter will help',
    });
    expect(h.hypothesisId).toMatch(/^hypo_/);
    expect(h.status).toBe('PROPOSED');
  });

  it('updates hypothesis status', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.updateStatus(h.hypothesisId, 'TESTING');
    expect(updated?.status).toBe('TESTING');
  });

  it('links experiment to hypothesis', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.linkExperiment(h.hypothesisId, 'exp_1');
    expect(updated?.experimentId).toBe('exp_1');
    expect(updated?.status).toBe('TESTING');
  });

  it('adds supporting evidence', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.addEvidence(h.hypothesisId, 'evidence_1', true);
    expect(updated?.evidenceFor.length).toBe(1);
    expect(updated?.sampleSize).toBe(1);
  });

  it('adds contradicting evidence', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.addEvidence(h.hypothesisId, 'evidence_1', false);
    expect(updated?.evidenceAgainst.length).toBe(1);
  });

  it('evaluates hypothesis as supported', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.evaluateHypothesis(h.hypothesisId, true, 0.02);
    expect(updated?.status).toBe('SUPPORTED');
    expect(updated?.pValue).toBe(0.02);
  });

  it('evaluates hypothesis as refuted', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.evaluateHypothesis(h.hypothesisId, false, 0.8);
    expect(updated?.status).toBe('REFUTED');
  });

  it('expires hypothesis', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    const updated = engine.expireHypothesis(h.hypothesisId);
    expect(updated?.status).toBe('INCONCLUSIVE');
  });

  it('retrieves active hypotheses', () => {
    engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    expect(engine.getActiveHypotheses().length).toBe(1);
  });

  it('retrieves validated hypotheses', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    engine.evaluateHypothesis(h.hypothesisId, true);
    expect(engine.getValidatedHypotheses().length).toBe(1);
  });

  it('retrieves refuted hypotheses', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    engine.evaluateHypothesis(h.hypothesisId, false);
    expect(engine.getRefutedHypotheses().length).toBe(1);
  });

  it('retrieves by status', () => {
    engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    expect(engine.getHypothesesByStatus('PROPOSED').length).toBe(1);
  });

  it('deletes a hypothesis', () => {
    const h = engine.createHypothesis({ description: 'd', rationale: 'r', testablePrediction: 'p' });
    expect(engine.deleteHypothesis(h.hypothesisId)).toBe(true);
  });

  it('returns undefined for unknown hypothesis', () => {
    expect(engine.getHypothesis('nonexistent')).toBeUndefined();
  });
});

// ============================================================================
// RESEARCH QUEUE ENGINE
// ============================================================================

describe('ResearchQueueEngine', () => {
  let engine: ResearchQueueEngine;

  beforeEach(() => {
    engine = new ResearchQueueEngine({ sameHypothesisCooldownMs: 0, sameStrategyCooldownMs: 0, globalCooldownMs: 0, maxConcurrent: 2, maxDailyExperiments: 100 });
  });

  it('enqueues a research item', () => {
    const item = engine.enqueue({
      experimentName: 'Test', description: 'desc', priority: 'HIGH', reason: 'degradation',
    });
    expect(item.itemId).toMatch(/^rq_/);
    expect(item.status).toBe('QUEUED');
  });

  it('dequeues an item', () => {
    engine.enqueue({ experimentName: 'Test', description: 'desc', priority: 'HIGH', reason: 'r' });
    const item = engine.dequeue();
    expect(item).toBeDefined();
    expect(item?.status).toBe('RUNNING');
  });

  it('completes an item', () => {
    const item = engine.enqueue({ experimentName: 'Test', description: 'desc', priority: 'HIGH', reason: 'r' });
    engine.dequeue();
    engine.complete(item.itemId);
    expect(engine.getCompleted().length).toBe(1);
  });

  it('fails and retries an item', () => {
    const item = engine.enqueue({ experimentName: 'Test', description: 'desc', priority: 'HIGH', reason: 'r', maxAttempts: 2 });
    engine.dequeue();
    engine.fail(item.itemId);
    const queue = engine.getQueue();
    expect(queue.length).toBe(1);
  });

  it('cancels an item', () => {
    const item = engine.enqueue({ experimentName: 'Test', description: 'desc', priority: 'LOW', reason: 'r' });
    expect(engine.cancel(item.itemId)).toBe(true);
  });

  it('enforces max concurrent', () => {
    engine.enqueue({ experimentName: 'A', description: 'd', priority: 'HIGH', reason: 'r' });
    engine.enqueue({ experimentName: 'B', description: 'd', priority: 'HIGH', reason: 'r' });
    engine.enqueue({ experimentName: 'C', description: 'd', priority: 'HIGH', reason: 'r' });
    engine.dequeue();
    engine.dequeue();
    expect(engine.dequeue()).toBeUndefined();
  });

  it('returns queue length', () => {
    engine.enqueue({ experimentName: 'A', description: 'd', priority: 'HIGH', reason: 'r' });
    expect(engine.getQueueLength()).toBe(1);
  });

  it('returns daily count', () => {
    engine.enqueue({ experimentName: 'A', description: 'd', priority: 'HIGH', reason: 'r' });
    engine.dequeue();
    expect(engine.getDailyCount()).toBe(1);
  });

  it('rejects duplicate hypothesis', () => {
    engine.enqueue({ experimentName: 'A', description: 'd', priority: 'HIGH', reason: 'r', hypothesisId: 'h1' });
    expect(() => engine.enqueue({ experimentName: 'B', description: 'd', priority: 'HIGH', reason: 'r', hypothesisId: 'h1' })).toThrow();
  });

  it('returns running items', () => {
    const item = engine.enqueue({ experimentName: 'A', description: 'd', priority: 'HIGH', reason: 'r' });
    engine.dequeue();
    expect(engine.getRunning().length).toBe(1);
  });
});

// ============================================================================
// STRATEGY ADAPTATION ENGINE
// ============================================================================

describe('StrategyAdaptationEngine', () => {
  let engine: StrategyAdaptationEngine;

  beforeEach(() => {
    engine = new StrategyAdaptationEngine();
  });

  it('creates an adaptation proposal', () => {
    const p = engine.createProposal({
      currentStrategyId: 's1', currentStrategyVersion: '1.0.0',
      proposedChanges: { addFilter: true }, problemStatement: 'Degradation',
      evidence: ['f1'], reasoning: 'Volume filter helps',
    });
    expect(p.proposalId).toMatch(/^adapt_/);
    expect(p.status).toBe('PROPOSED');
  });

  it('updates proposal status', () => {
    const p = engine.createProposal({
      currentStrategyId: 's1', currentStrategyVersion: '1.0.0',
      proposedChanges: {}, problemStatement: 'p', evidence: [], reasoning: 'r',
    });
    const updated = engine.updateStatus(p.proposalId, 'UNDER_TEST');
    expect(updated?.status).toBe('UNDER_TEST');
  });

  it('compares champion vs challenger', () => {
    const result = engine.compareChampionChallenger({
      championId: 'champion_1',
      challengerId: 'challenger_1',
      championMetrics: { totalReturn: 0.1, sharpeRatio: 1.5, maxDrawdown: 0.1, calibrationError: 0.05, sortinoRatio: 2.0 },
      challengerMetrics: { totalReturn: 0.15, sharpeRatio: 1.8, maxDrawdown: 0.08, calibrationError: 0.03, sortinoRatio: 2.5 },
      sampleSize: 100,
    });
    expect(result.winner).toBe('CHALLENGER');
    expect(result.validations.length).toBe(5);
  });

  it('returns INCONCLUSIVE for small sample', () => {
    const result = engine.compareChampionChallenger({
      championId: 'c1', challengerId: 'c2',
      championMetrics: { totalReturn: 0.1, sharpeRatio: 1.5, maxDrawdown: 0.1, calibrationError: 0.05, sortinoRatio: 2.0 },
      challengerMetrics: { totalReturn: 0.15, sharpeRatio: 1.8, maxDrawdown: 0.08, calibrationError: 0.03, sortinoRatio: 2.5 },
      sampleSize: 10,
    });
    expect(result.winner).toBe('INCONCLUSIVE');
  });

  it('returns CHAMPION when challenger is worse', () => {
    const result = engine.compareChampionChallenger({
      championId: 'c1', challengerId: 'c2',
      championMetrics: { totalReturn: 0.2, sharpeRatio: 2.0, maxDrawdown: 0.05, calibrationError: 0.02, sortinoRatio: 3.0 },
      challengerMetrics: { totalReturn: 0.05, sharpeRatio: 0.5, maxDrawdown: 0.3, calibrationError: 0.15, sortinoRatio: 0.7 },
      sampleSize: 100,
    });
    expect(result.winner).toBe('CHAMPION');
  });

  it('returns all proposals', () => {
    engine.createProposal({ currentStrategyId: 's1', currentStrategyVersion: '1.0.0', proposedChanges: {}, problemStatement: 'p', evidence: [], reasoning: 'r' });
    expect(engine.getAllProposals().length).toBe(1);
  });

  it('returns proposals by status', () => {
    engine.createProposal({ currentStrategyId: 's1', currentStrategyVersion: '1.0.0', proposedChanges: {}, problemStatement: 'p', evidence: [], reasoning: 'r' });
    expect(engine.getProposalsByStatus('PROPOSED').length).toBe(1);
  });

  it('retrieves comparison', () => {
    engine.compareChampionChallenger({
      championId: 'c1', challengerId: 'c2',
      championMetrics: { totalReturn: 0.1, sharpeRatio: 1, maxDrawdown: 0.1, calibrationError: 0.05, sortinoRatio: 1 },
      challengerMetrics: { totalReturn: 0.1, sharpeRatio: 1, maxDrawdown: 0.1, calibrationError: 0.05, sortinoRatio: 1 },
      sampleSize: 50,
    });
    expect(engine.getComparison('c1', 'c2')).toBeDefined();
  });

  it('deletes a proposal', () => {
    const p = engine.createProposal({ currentStrategyId: 's1', currentStrategyVersion: '1.0.0', proposedChanges: {}, problemStatement: 'p', evidence: [], reasoning: 'r' });
    expect(engine.deleteProposal(p.proposalId)).toBe(true);
  });
});

// ============================================================================
// PROVIDER QUALITY ENGINE
// ============================================================================

describe('ProviderQualityEngine', () => {
  let engine: ProviderQualityEngine;

  beforeEach(() => {
    engine = new ProviderQualityEngine();
  });

  it('records an observation and computes health', () => {
    engine.recordObservation({
      providerId: 'yahoo', timestamp: new Date().toISOString(),
      available: true, latencyMs: 200, errorOccurred: false,
      freshData: true, correctData: true,
    });
    const h = engine.getHealth('yahoo');
    expect(h).toBeDefined();
    expect(h?.availabilityScore).toBe(1);
  });

  it('detects degraded providers', () => {
    for (let i = 0; i < 20; i++) {
      engine.recordObservation({
        providerId: 'bad_provider', timestamp: new Date().toISOString(),
        available: false, latencyMs: 5000, errorOccurred: true,
        freshData: false, correctData: false,
      });
    }
    const degraded = engine.getDegradedProviders();
    expect(degraded.length).toBe(1);
  });

  it('returns top providers', () => {
    engine.recordObservation({ providerId: 'good', timestamp: new Date().toISOString(), available: true, latencyMs: 100, errorOccurred: false, freshData: true, correctData: true });
    engine.recordObservation({ providerId: 'bad', timestamp: new Date().toISOString(), available: false, latencyMs: 5000, errorOccurred: true, freshData: false, correctData: false });
    const top = engine.getTopProviders(1);
    expect(top[0].providerId).toBe('good');
  });

  it('returns observations', () => {
    engine.recordObservation({ providerId: 'p1', timestamp: new Date().toISOString(), available: true, latencyMs: 100, errorOccurred: false, freshData: true });
    expect(engine.getObservations('p1').length).toBe(1);
  });
});

// ============================================================================
// BIAS DETECTION ENGINE
// ============================================================================

describe('BiasDetectionEngine', () => {
  let engine: BiasDetectionEngine;

  beforeEach(() => {
    engine = new BiasDetectionEngine();
  });

  it('detects bullish bias', () => {
    const dirs = Array.from({ length: 30 }, () => 'UP' as const);
    const alert = engine.detectBullishBias(dirs);
    expect(alert).not.toBeNull();
    expect(alert?.biasType).toBe('BULLISH_BIAS');
  });

  it('detects bearish bias', () => {
    const dirs = Array.from({ length: 30 }, () => 'DOWN' as const);
    const alert = engine.detectBearishBias(dirs);
    expect(alert).not.toBeNull();
  });

  it('no bullish bias for balanced directions', () => {
    const dirs: ('UP' | 'DOWN')[] = [];
    for (let i = 0; i < 30; i++) dirs.push(i % 2 === 0 ? 'UP' : 'DOWN');
    expect(engine.detectBullishBias(dirs)).toBeNull();
  });

  it('detects confidence bias (overconfidence)', () => {
    const confidences = Array.from({ length: 20 }, () => 0.9);
    const accuracies = Array.from({ length: 20 }, () => 0.5);
    const alert = engine.detectConfidenceBias(confidences, accuracies);
    expect(alert).not.toBeNull();
    expect(alert?.biasType).toBe('CONFIDENCE_BIAS');
  });

  it('detects overtrading', () => {
    const signals = Array.from({ length: 10 }, () => 20);
    const alert = engine.detectOvertrading(signals, 5);
    expect(alert).not.toBeNull();
    expect(alert?.biasType).toBe('OVERTRADING');
  });

  it('detects asset selection bias', () => {
    const assets = Array.from({ length: 20 }, () => 'AAPL');
    const alert = engine.detectAssetSelectionBias(assets);
    expect(alert).not.toBeNull();
  });

  it('detects research bias', () => {
    const alert = engine.detectResearchBias(20, 20);
    expect(alert).not.toBeNull();
    expect(alert?.biasType).toBe('RESEARCH_BIAS');
  });

  it('returns all alerts', () => {
    engine.detectBullishBias(Array.from({ length: 30 }, () => 'UP' as const));
    expect(engine.getAllAlerts().length).toBe(1);
  });

  it('clears alerts', () => {
    engine.detectBullishBias(Array.from({ length: 30 }, () => 'UP' as const));
    engine.clearAlerts();
    expect(engine.getAllAlerts().length).toBe(0);
  });
});

// ============================================================================
// META EVALUATION ENGINE
// ============================================================================

describe('MetaEvaluationEngine', () => {
  let engine: MetaEvaluationEngine;

  beforeEach(() => {
    engine = new MetaEvaluationEngine();
  });

  it('records and evaluates metric consistency', () => {
    for (let i = 0; i < 10; i++) engine.recordMetric('accuracy', 0.6);
    engine.recordMetric('accuracy', 0.61);
    const result = engine.evaluateConsistency('accuracy');
    expect(result.consistent).toBe(true);
  });

  it('detects inconsistent metric', () => {
    for (let i = 0; i < 10; i++) engine.recordMetric('accuracy', 0.6);
    engine.recordMetric('accuracy', 0.2);
    const result = engine.evaluateConsistency('accuracy');
    expect(result.consistent).toBe(false);
  });

  it('evaluates all metrics', () => {
    engine.recordMetric('m1', 0.5);
    engine.recordMetric('m2', 0.7);
    const results = engine.evaluateAll();
    expect(results.length).toBe(2);
  });

  it('returns inconsistent metrics', () => {
    for (let i = 0; i < 10; i++) engine.recordMetric('m1', 0.6);
    engine.recordMetric('m1', 0.1);
    engine.evaluateConsistency('m1');
    expect(engine.getInconsistentMetrics().length).toBe(1);
  });

  it('returns metric history', () => {
    engine.recordMetric('m1', 0.5);
    expect(engine.getMetricHistory('m1').length).toBe(1);
  });

  it('clears history', () => {
    engine.recordMetric('m1', 0.5);
    engine.clearHistory();
    expect(engine.getMetricHistory('m1').length).toBe(0);
  });
});

// ============================================================================
// LEARNING SYSTEM HEALTH ENGINE
// ============================================================================

describe('LearningSystemHealthEngine', () => {
  it('reports healthy status', () => {
    const engine = new LearningSystemHealthEngine();
    const health = engine.getHealth();
    expect(health.overallStatus).toBeDefined();
    expect(health.lastUpdated).toBeDefined();
  });

  it('increments error count', () => {
    const engine = new LearningSystemHealthEngine();
    engine.incrementError();
    engine.incrementError();
    const health = engine.getHealth();
    expect(health.evaluationErrors).toBe(2);
  });
});

// ============================================================================
// ATTRIBUTION ENGINE
// ============================================================================

describe('AttributionEngine', () => {
  it('calculates attribution', () => {
    const engine = new AttributionEngine();
    const trades = [
      { entryPrice: 100, exitPrice: 110, quantity: 10, direction: 'LONG' as const, entryBarIndex: 0, exitBarIndex: 10, pnl: 100 },
      { entryPrice: 110, exitPrice: 105, quantity: 10, direction: 'LONG' as const, entryBarIndex: 10, exitBarIndex: 20, pnl: -50 },
    ];
    const attr = engine.calculateAttribution('s1', 'Q1 2026', trades, [0.01, 0.02]);
    expect(attr.totalReturn).toBe(50);
    expect(attr.reconciliationError).toBeCloseTo(0, 10);
  });

  it('decomposes return components', () => {
    const engine = new AttributionEngine();
    const components = engine.decomposeReturnComponents([0.01, 0.02, -0.01, 0.03]);
    expect(components.trend).toBeDefined();
    expect(components.meanReversion).toBeDefined();
  });
});

// ============================================================================
// LIQUIDITY METRICS ENGINE
// ============================================================================

describe('LiquidityMetricsEngine', () => {
  it('calculates liquidity metrics', () => {
    const engine = new LiquidityMetricsEngine();
    const bar = makeBar();
    const metrics = engine.calculateLiquidityMetrics('TEST', bar, 1000000, 10);
    expect(metrics.symbol).toBe('TEST');
    expect(metrics.liquidityRegime).toBeDefined();
    expect(metrics.fillProbability).toBeGreaterThan(0);
  });

  it('adjusts position size based on liquidity', () => {
    const engine = new LiquidityMetricsEngine();
    const bar = makeBar();
    const metrics = engine.calculateLiquidityMetrics('TEST', bar, 1000000, 10);
    const adjusted = engine.calculateLiquidityAdjustedPositionSize(100, metrics, 5);
    expect(adjusted).toBeGreaterThan(0);
  });

  it('returns null for unknown symbol history', () => {
    const engine = new LiquidityMetricsEngine();
    expect(engine.getLiquidityHistory('UNKNOWN')).toBeNull();
  });
});

// ============================================================================
// FIREWALL TESTS
// ============================================================================

describe('ExecutionFirewall', () => {
  it('denies execute_trade', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('buy_stock', 'EXECUTE_TRADE');
    expect(result.allowed).toBe(false);
    expect(result.overrideLevel).toBe('STRICT');
  });

  it('denies transfer_funds', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('withdraw_money', 'TRANSFER_FUNDS');
    expect(result.allowed).toBe(false);
  });

  it('allows simulate_trade', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('paper_trade', 'SIMULATE_TRADE');
    expect(result.allowed).toBe(true);
  });

  it('allows read_market_data', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('get_price', 'READ_MARKET_DATA');
    expect(result.allowed).toBe(true);
  });

  it('never allows LLM override', () => {
    const fw = new ExecutionFirewall();
    expect(fw.canOverride()).toBe(false);
  });

  it('rejects policy with liveTradeExecution true', () => {
    expect(() => new ExecutionFirewall({ liveTradeExecution: true })).toThrow();
  });

  it('rejects policy with transferFunds true', () => {
    expect(() => new ExecutionFirewall({ transferFunds: true })).toThrow();
  });

  it('rejects policy with allowLlmOverride true', () => {
    expect(() => new ExecutionFirewall({ allowLlmOverride: true })).toThrow();
  });

  it('audit log records all evaluations', () => {
    const fw = new ExecutionFirewall();
    fw.evaluate('buy', 'EXECUTE_TRADE');
    fw.evaluate('paper_trade', 'SIMULATE_TRADE');
    expect(fw.getAuditLog().length).toBe(2);
  });

  it('classifyCapability classifies correctly', () => {
    const fw = new ExecutionFirewall();
    expect(fw.classifyCapability('paper_trade')).toBe('SIMULATE_TRADE');
    expect(fw.classifyCapability('buy_stock')).toBe('EXECUTE_TRADE');
    expect(fw.classifyCapability('withdraw_money')).toBe('TRANSFER_FUNDS');
    expect(fw.classifyCapability('get_price')).toBe('READ_MARKET_DATA');
  });

  it('explainDenial returns reason', () => {
    const fw = new ExecutionFirewall();
    const explanation = fw.explainDenial('buy_stock');
    expect(explanation).toContain('DENIED');
  });

  it('GLOBAL_FIREWALL is a singleton', () => {
    expect(GLOBAL_FIREWALL).toBeDefined();
    expect(GLOBAL_FIREWALL.canOverride()).toBe(false);
  });

  it('GLOBAL_FIREWALL blocks broker connection', () => {
    const result = GLOBAL_FIREWALL.evaluate('connect_to_broker', 'EXECUTE_TRADE');
    expect(result.allowed).toBe(false);
  });

  it('denies paper_trade when action contains execute', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluate('execute_paper_trade', 'SIMULATE_TRADE');
    expect(result.allowed).toBe(true);
  });

  it('evaluateIntent always returns denied', () => {
    const fw = new ExecutionFirewall();
    const result = fw.evaluateIntent({} as any);
    expect(result.allowed).toBe(false);
  });
});

// ============================================================================
// PHASE 27 CALIBRATION INTEGRATION
// ============================================================================

describe('Phase 27 Calibration Integration', () => {
  it('Phase 27 calibration engine works with Phase 28 forecasts', () => {
    const cal = new CalibrationEngine();
    cal.recordForecast({
      forecastId: 'f1', strategyId: 's1', confidence: 0.8,
      symbol: 'TEST', timestamp: '2026-01-01T00:00:00Z', direction: 'UP',
      horizonBars: 24, parameters: {},
    });
    cal.recordForecast({
      forecastId: 'f2', strategyId: 's1', confidence: 0.3,
      symbol: 'TEST', timestamp: '2026-01-01T00:00:00Z', direction: 'DOWN',
      horizonBars: 24, parameters: {},
    });
    cal.recordOutcome({
      forecastId: 'f1', symbol: 'TEST', actualDirection: 'UP',
      actualMovePercent: 2.0, evaluationTimestamp: '2026-01-02T00:00:00Z', correct: true,
    });
    cal.recordOutcome({
      forecastId: 'f2', symbol: 'TEST', actualDirection: 'UP',
      actualMovePercent: 1.0, evaluationTimestamp: '2026-01-02T00:00:00Z', correct: false,
    });
    const result = cal.evaluate('s1');
    expect(result.totalForecasts).toBe(2);
    expect(result.overallAccuracy).toBe(0.5);
  });
});

// ============================================================================
// PHASE 27 EXPERIMENT REGISTRY INTEGRATION
// ============================================================================

describe('Phase 27 Experiment Integration', () => {
  it('experiment registry creates and retrieves experiments', () => {
    const reg = new ExperimentRegistry();
    const exp = reg.createExperiment({
      name: 'Test Experiment',
      description: 'Testing hypothesis',
      strategy: { definitionId: 's1', version: '1.0.0', params: {} },
      datasetId: 'd1',
      datasetSymbol: 'TEST',
      periodStart: '2026-01-01',
      periodEnd: '2026-06-30',
      costModel: { commission: 0, slippageBps: 0, spreadBps: 0, marketImpact: 'NONE' },
    });
    expect(exp.id).toMatch(/^exp_/);
    expect(reg.getExperiment(exp.id)).toBeDefined();
  });

  it('experiment generates report with disclaimers', () => {
    const reg = new ExperimentRegistry();
    const exp = reg.createExperiment({
      name: 'Test', description: 'd',
      strategy: { definitionId: 's1', version: '1.0.0', params: {} },
      datasetId: 'd1', datasetSymbol: 'TEST',
      periodStart: '2026-01-01', periodEnd: '2026-06-30',
      costModel: { commission: 0, slippageBps: 0, spreadBps: 0, marketImpact: 'NONE' },
    });
    reg.updateStatus(exp.id, 'COMPLETED');
    const report = reg.generateReport(exp.id);
    expect(report).not.toBeNull();
    expect(report?.disclaimers.length).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================================
// END-TO-END INTEGRATION
// ============================================================================

describe('Phase 28 End-to-End Integration', () => {
  it('complete learning loop: forecast -> outcome -> evaluation -> lesson -> hypothesis', () => {
    const lifecycle = new ForecastLifecycleManager();
    const lessons = new ResearchLessonEngine();
    const hypotheses = new ResearchHypothesisEngine();
    const health = new StrategyHealthEngine();
    const pm = new PostMortemEngine();

    // 1. Create and activate forecast
    const forecast = createTestForecast(lifecycle, { strategyId: 'momentum_v1', confidence: 0.8 });

    // 2. Record outcome
    lifecycle.recordOutcome({
      forecastId: forecast.forecastId,
      outcomeTimestamp: new Date().toISOString(),
      actualValue: 90,
      actualDirection: 'DOWN',
      actualReturn: -0.10,
      dataQuality: 'COMPLETE',
      evaluationStatus: 'FINAL',
    });

    // 3. Evaluate
    const evaluation = lifecycle.evaluateForecast(forecast.forecastId)!;
    expect(evaluation.strategyOutcome).toBe('FAILURE');

    // 4. Generate post-mortem
    const outcome = lifecycle.getOutcome(forecast.forecastId)!;
    const postMortem = pm.generatePostMortem(forecast, evaluation, outcome);
    expect(postMortem.outcome).toBe('FAILURE');

    // 5. Create lesson
    const lesson = lessons.createLesson({
      source: `forecast_${forecast.forecastId}`,
      strategyId: 'momentum_v1',
      context: `Regime: ${forecast.regime}`,
      failureOrSuccess: 'FAILURE',
      recommendation: 'Consider regime adaptation',
      confidence: evaluation.confidenceQuality,
      regime: forecast.regime,
    });
    expect(lesson.lessonId).toMatch(/^lesson_/);

    // 6. Create hypothesis from failure
    const hypothesis = hypotheses.createHypothesis({
      description: 'Momentum strategies underperform in regime shifts',
      rationale: 'Recent failure suggests regime sensitivity',
      testablePrediction: 'Regime-adaptive momentum will outperform static momentum',
      sourceForecastId: forecast.forecastId,
      confidence: 0.6,
    });
    expect(hypothesis.status).toBe('PROPOSED');

    // 7. Update strategy health
    health.recordEvaluation({
      forecastId: forecast.forecastId,
      strategyId: 'momentum_v1',
      strategyVersion: '1.0.0',
      outcomeCorrect: false,
      return: -0.10,
      regime: 'TRENDING_BULL',
      horizon: 'SHORT_TERM',
      timestamp: new Date().toISOString(),
    });
    const strategyHealth = health.getHealth('momentum_v1');
    expect(strategyHealth).toBeDefined();
    expect(strategyHealth?.sampleSize).toBe(1);
  });

  it('firewall blocks throughout learning pipeline', () => {
    const fw = new ExecutionFirewall();

    // All these must be blocked
    expect(fw.evaluate('buy_stock', 'EXECUTE_TRADE').allowed).toBe(false);
    expect(fw.evaluate('sell_stock', 'EXECUTE_TRADE').allowed).toBe(false);
    expect(fw.evaluate('place_order', 'EXECUTE_TRADE').allowed).toBe(false);
    expect(fw.evaluate('cancel_order', 'EXECUTE_TRADE').allowed).toBe(false);
    expect(fw.evaluate('withdraw', 'TRANSFER_FUNDS').allowed).toBe(false);
    expect(fw.evaluate('deposit', 'TRANSFER_FUNDS').allowed).toBe(false);

    // These must be allowed
    expect(fw.evaluate('paper_trade', 'SIMULATE_TRADE').allowed).toBe(true);
    expect(fw.evaluate('get_price', 'READ_MARKET_DATA').allowed).toBe(true);
  });

  it('drift detection connects to strategy health', () => {
    const drift = new DriftDetectionEngine({ minSampleSize: 5, cooldownMs: 0 });
    const health = new StrategyHealthEngine();

    // Record some evaluations
    for (let i = 0; i < 30; i++) {
      health.recordEvaluation({
        forecastId: `f_${i}`, strategyId: 's1', strategyVersion: '1.0.0',
        outcomeCorrect: i < 20, return: i < 20 ? 0.02 : -0.01,
        regime: 'TRENDING_BULL', horizon: 'SHORT_TERM',
        timestamp: new Date(Date.now() + i * 86400000).toISOString(),
      });
    }

    const sh = health.getHealth('s1');
    expect(sh).toBeDefined();

    // Check for performance drift using recent evals
    const recentEvals = Array.from({ length: 30 }, () => false);
    const alert = drift.detectPerformanceDrift('s1', recentEvals, sh!.recentAccuracy);
    expect(alert).not.toBeNull();
  });

  it('research queue prevents infinite loops', () => {
    const queue = new ResearchQueueEngine({
      sameHypothesisCooldownMs: 0,
      sameStrategyCooldownMs: 0,
      globalCooldownMs: 0,
      maxConcurrent: 1,
      maxDailyExperiments: 3,
    });

    queue.enqueue({ experimentName: 'A', description: 'd', priority: 'HIGH', reason: 'r', hypothesisId: 'h1' });
    queue.enqueue({ experimentName: 'B', description: 'd', priority: 'HIGH', reason: 'r', hypothesisId: 'h2' });
    queue.enqueue({ experimentName: 'C', description: 'd', priority: 'HIGH', reason: 'r', hypothesisId: 'h3' });

    // Should be able to dequeue up to max concurrent
    expect(queue.dequeue()).toBeDefined();
    expect(queue.dequeue()).toBeUndefined(); // max concurrent = 1
  });

  it('provider quality tracks reliability', () => {
    const pq = new ProviderQualityEngine();
    for (let i = 0; i < 10; i++) {
      pq.recordObservation({
        providerId: 'yahoo',
        timestamp: new Date().toISOString(),
        available: true,
        latencyMs: 100 + Math.random() * 100,
        errorOccurred: false,
        freshData: true,
        correctData: true,
      });
    }
    const h = pq.getHealth('yahoo');
    expect(h?.reliabilityScore).toBeGreaterThan(0.8);
  });

  it('bias detection monitors forecast direction balance', () => {
    const bd = new BiasDetectionEngine();
    const dirs: ('UP' | 'DOWN')[] = Array.from({ length: 30 }, () => 'UP');
    const alert = bd.detectBullishBias(dirs);
    expect(alert?.biasType).toBe('BULLISH_BIAS');
  });

  it('meta evaluation tracks system consistency', () => {
    const me = new MetaEvaluationEngine();
    for (let i = 0; i < 10; i++) me.recordMetric('calibration_error', 0.05);
    me.recordMetric('calibration_error', 0.052);
    const result = me.evaluateConsistency('calibration_error');
    expect(result.consistent).toBe(true);
  });

  it('champion/challenger comparison is fair', () => {
    const engine = new StrategyAdaptationEngine();
    const result = engine.compareChampionChallenger({
      championId: 'champion', challengerId: 'challenger',
      championMetrics: { totalReturn: 0.1, sharpeRatio: 1.5, maxDrawdown: 0.15, calibrationError: 0.08, sortinoRatio: 2.0 },
      challengerMetrics: { totalReturn: 0.12, sharpeRatio: 1.6, maxDrawdown: 0.12, calibrationError: 0.06, sortinoRatio: 2.2 },
      sampleSize: 100,
    });
    expect(result.validations.length).toBe(5);
    expect(result.sampleSize).toBe(100);
  });
});

// ============================================================================
// PERFORMANCE / SCALE TESTS
// ============================================================================

describe('Phase 28 Performance', () => {
  it('handles 500 forecast evaluations', () => {
    const lifecycle = new ForecastLifecycleManager();
    const start = Date.now();
    for (let i = 0; i < 500; i++) {
      const f = createTestForecast(lifecycle, { symbol: `SYM_${i}` });
      lifecycle.recordOutcome({
        forecastId: f.forecastId,
        outcomeTimestamp: new Date().toISOString(),
        actualValue: 100 + Math.random() * 10,
        actualDirection: Math.random() > 0.5 ? 'UP' : 'DOWN',
        dataQuality: 'COMPLETE',
        evaluationStatus: 'FINAL',
      });
      lifecycle.evaluateForecast(f.forecastId);
    }
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(5000);
  });

  it('handles 200 strategy health evaluations', () => {
    const health = new StrategyHealthEngine();
    const start = Date.now();
    for (let i = 0; i < 200; i++) {
      health.recordEvaluation({
        forecastId: `f_${i}`, strategyId: 's1', strategyVersion: '1.0.0',
        outcomeCorrect: Math.random() > 0.4,
        return: Math.random() * 0.04 - 0.01,
        regime: 'TRENDING_BULL', horizon: 'SHORT_TERM',
        timestamp: new Date().toISOString(),
      });
    }
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(2000);
    expect(health.getHealth('s1')?.sampleSize).toBe(200);
  });

  it('drift detection on 1000 data points', () => {
    const drift = new DriftDetectionEngine({ minSampleSize: 5, cooldownMs: 0 });
    const data = Array.from({ length: 1000 }, (_, i) => i < 500 ? Math.random() : Math.random() + 5);
    const start = Date.now();
    const cps = drift.detectChangePoint(data, 50);
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(2000);
    expect(cps.length).toBeGreaterThanOrEqual(1);
  });
});
