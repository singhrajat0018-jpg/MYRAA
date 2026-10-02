// ============================================================================
// MYRAA Phase 28 — Learning System REST API Routes
// ============================================================================

import { Router } from 'express';
import { forecastLifecycleManager } from '../learning/forecastLifecycleManager';
import { continuousEvaluationEngine } from '../learning/continuousEvaluationEngine';
import { attributionEngine } from '../learning/attributionEngine';
import { liquidityMetricsEngine } from '../learning/liquidityMetricsEngine';
import type {
  Forecast, ForecastLifecycleState, ForecastOutcome, ForecastEvaluation,
  EvaluationQueueItem, StrategyHealth, ResearchLesson, ResearchHypothesis,
  StrategyAdaptationProposal, FinancialProviderHealth, PerformanceAttribution,
  LiquidityMetrics, DriftAlert, FinancialIntelligenceHealth,
  ForecastType, ForecastHorizon, TimeHorizon, RegimeType
} from '../learning/contracts';

const router = Router();

// ============================================================================
// FORECAST LIFECYCLE ENDPOINTS
// ============================================================================

/**
 * Create a new forecast
 */
router.post('/forecasts', (req, res) => {
  try {
    const {
      assetId,
      symbol,
      horizon,
      type,
      prediction,
      confidence,
      strategyId,
      strategyVersion,
      evidenceSnapshot,
      dataSnapshot,
      strategySnapshot,
      regime,
      invalidationConditions,
      predictionDetails,
      probability,
      probabilityType,
      thesisId,
      modelSnapshot,
      researchSnapshot
    } = req.body;

    // Validate required fields
    if (!assetId || !symbol || !horizon || !type || prediction === undefined ||
        confidence === undefined || !strategyId || !strategyVersion ||
        !evidenceSnapshot || !dataSnapshot || !strategySnapshot || !regime ||
        !invalidationConditions) {
      return res.status(400).json({
        error: 'Missing required fields for forecast creation'
      });
    }

    // Validate confidence range
    if (confidence < 0 || confidence > 1) {
      return res.status(400).json({
        error: 'Confidence must be between 0 and 1'
      });
    }

    // Validate probability if provided
    if (probability !== undefined && (probability < 0 || probability > 1)) {
      return res.status(400).json({
        error: 'Probability must be between 0 and 1'
      });
    }

    const forecast = forecastLifecycleManager.createForecast({
      assetId,
      symbol,
      horizon: horizon as ForecastHorizon,
      type: type as ForecastType,
      prediction,
      confidence,
      strategyId,
      strategyVersion,
      evidenceSnapshot,
      dataSnapshot,
      strategySnapshot,
      regime: regime as RegimeType,
      invalidationConditions,
      predictionDetails,
      probability,
      probabilityType,
      thesisId,
      modelSnapshot,
      researchSnapshot
    });

    res.status(201).json(forecast);
  } catch (error) {
    console.error('[Learning API] Error creating forecast:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get a forecast by ID
 */
router.get('/forecasts/:forecastId', (req, res) => {
  try {
    const forecast = forecastLifecycleManager.getForecast(req.params.forecastId);
    if (!forecast) {
      return res.status(404).json({ error: 'Forecast not found' });
    }
    res.json(forecast);
  } catch (error) {
    console.error('[Learning API] Error getting forecast:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Activate a forecast
 */
router.post('/forecasts/:forecastId/activate', (req, res) => {
  try {
    const forecast = forecastLifecycleManager.activateForecast(req.params.forecastId);
    if (!forecast) {
      return res.status(404).json({ error: 'Forecast not found' });
    }
    if (forecast === null) {
      return res.status(400).json({ error: 'Forecast cannot be activated' });
    }
    res.json(forecast);
  } catch (error) {
    console.error('[Learning API] Error activating forecast:', error);
    if (error.message.includes('not in CREATED state')) {
      return res.status(400).json({ error: error.message });
    }
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Mark forecast as awaiting outcome
 */
router.post('/forecasts/:forecastId/await-outcome', (req, res) => {
  try {
    const forecast = forecastLifecycleManager.awaitOutcome(req.params.forecastId);
    if (!forecast) {
      return res.status(404).json({ error: 'Forecast not found' });
    }
    if (forecast === null) {
      return res.status(400).json({ error: 'Forecast cannot be moved to await outcome' });
    }
    res.json(forecast);
  } catch (error) {
    console.error('[Learning API] Error marking forecast as awaiting outcome:', error);
    if (error.message.includes('not in ACTIVE state')) {
      return res.status(400).json({ error: error.message });
    }
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Record an outcome for a forecast
 */
router.post('/forecasts/:forecastId/outcome', (req, res) => {
  try {
    const {
      actualValue,
      actualReturn,
      actualDirection,
      directionCorrect,
      magnitudeError,
      relativeError,
      timingError,
      maximumAdverseMove,
      maximumFavorableMove,
      volatility,
      eventOccurred,
      eventImpactActual,
      regimeAtOutcome,
      dataQuality,
      evaluationStatus
    } = req.body;

    // Validate required fields
    if (actualValue === undefined) {
      return res.status(400).json({ error: 'actualValue is required' });
    }

    const outcome = forecastLifecycleManager.recordOutcome({
      forecastId: req.params.forecastId,
      outcomeTimestamp: new Date().toISOString(),
      actualValue,
      actualReturn,
      actualDirection: actualDirection as 'UP' | 'DOWN' | 'FLAT' | undefined,
      directionCorrect,
      magnitudeError,
      relativeError,
      timingError,
      maximumAdverseMove,
      maximumFavorableMove,
      volatility,
      eventOccurred,
      eventImpactActual,
      regimeAtOutcome: regimeAtOutcome as RegimeType | undefined,
      dataQuality: dataQuality as 'COMPLETE' | 'PARTIAL' | 'SPARSE' | 'UNKNOWN',
      evaluationStatus: evaluationStatus as 'FINAL' | 'PROVISIONAL' | 'PARTIAL' | 'FAILED'
    });

    if (!outcome) {
      return res.status(404).json({ error: 'Forecast not found or cannot record outcome' });
    }

    res.status(201).json(outcome);
  } catch (error) {
    console.error('[Learning API] Error recording outcome:', error);
    if (error.message.includes('already finalized')) {
      return res.status(400).json({ error: error.message });
    }
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get outcome for a forecast
 */
router.get('/forecasts/:forecastId/outcome', (req, res) => {
  try {
    const outcome = forecastLifecycleManager.getOutcome(req.params.forecastId);
    if (!outcome) {
      return res.status(404).json({ error: 'Outcome not found' });
    }
    res.json(outcome);
  } catch (error) {
    console.error('[Learning API] Error getting outcome:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================================================
// EVALUATION ENDPOINTS
// ============================================================================

/**
 * Manually trigger evaluation of a forecast
 */
router.post('/forecasts/:forecastId/evaluate', async (req, res) => {
  try {
    const evaluation = await continuousEvaluationEngine.evaluateForecastNow(req.params.forecastId);
    if (!evaluation) {
      return res.status(400).json({
        error: 'Forecast not found, no outcome available, or not ready for evaluation'
      });
    }
    res.json(evaluation);
  } catch (error) {
    console.error('[Learning API] Error evaluating forecast:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get evaluation for a forecast
 */
router.get('/forecasts/:forecastId/evaluation', (req, res) => {
  try {
    const evaluation = forecastLifecycleManager.getEvaluation(req.params.forecastId);
    if (!evaluation) {
      return res.status(404).json({ error: 'Evaluation not found' });
    }
    res.json(evaluation);
  } catch (error) {
    console.error('[Learning API] Error getting evaluation:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get forecast by state
 */
router.get('/forecasts/state/:state', (req, res) => {
  try {
    const state = req.params.state as ForecastLifecycleState;
    const forecasts = forecastLifecycleManager.getForecastsByState(state);
    res.json(forecasts);
  } catch (error) {
    console.error('[Learning API] Error getting forecasts by state:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================================================
// CONTINUOUS EVALUATION ENGINE ENDPOINTS
// ============================================================================

/**
 * Start the continuous evaluation engine
 */
router.post('/evaluation/start', (req, res) => {
  try {
    continuousEvaluationEngine.start();
    res.json({ message: 'Continuous evaluation engine started' });
  } catch (error) {
    console.error('[Learning API] Error starting evaluation engine:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Stop the continuous evaluation engine
 */
router.post('/evaluation/stop', (req, res) => {
  try {
    continuousEvaluationEngine.stop();
    res.json({ message: 'Continuous evaluation engine stopped' });
  } catch (error) {
    console.error('[Learning API] Error stopping evaluation engine:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get evaluation engine statistics
 */
router.get('/evaluation/statistics', (req, res) => {
  try {
    const stats = continuousEvaluationEngine.getStatistics();
    res.json(stats);
  } catch (error) {
    console.error('[Learning API] Error getting evaluation statistics:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get evaluation queue length
 */
router.get('/evaluation/queue-length', (req, res) => {
  try {
    const length = forecastLifecycleManager.getQueueLength();
    res.json({ queueLength: length });
  } catch (error) {
    console.error('[Learning API] Error getting queue length:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================================================
// ATTRIBUTION ENDPOINTS
// ============================================================================

/**
 * Calculate performance attribution
 */
router.post('/attribution', (req, res) => {
  try {
    const {
      strategyId,
      period,
      trades,
      benchmarkReturns,
      regimeData,
      factorExposures
    } = req.body;

    if (!strategyId || !period || !trades) {
      return res.status(400).json({
        error: 'strategyId, period, and trades are required'
      });
    }

    const attribution = attributionEngine.calculateAttribution(
      strategyId,
      period,
      trades,
      benchmarkReturns || [],
      regimeData || [],
      factorExposures || {}
    );

    res.json(attribution);
  } catch (error) {
    console.error('[Learning API] Error calculating attribution:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================================================
// LIQUIDITY METRICS ENDPOINTS
// ============================================================================

/**
 * Calculate liquidity metrics
 */
router.post('/liquidity', (req, res) => {
  try {
    const {
      symbol,
      currentBar,
      volume24h,
      spreadBps,
      historicalVolume,
      historicalSpread,
      historicalVolatility
    } = req.body;

    if (!symbol || !currentBar || volume24h === undefined || spreadBps === undefined) {
      return res.status(400).json({
        error: 'symbol, currentBar, volume24h, and spreadBps are required'
      });
    }

    const metrics = liquidityMetricsEngine.calculateLiquidityMetrics(
      symbol,
      currentBar,
      volume24h,
      spreadBps,
      historicalVolume || [],
      historicalSpread || [],
      historicalVolatility || []
    );

    res.json(metrics);
  } catch (error) {
    console.error('[Learning API] Error calculating liquidity metrics:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
* Get liquidity-adjusted position size
*/
router.post('/liquidity/adjusted-size', (req, res) => {
  try {
    const {
      basePositionSize,
      liquidityMetrics,
      maxSlippageTolerance
    } = req.body;

    if (basePositionSize === undefined || !liquidityMetrics) {
      return res.status(400).json({
        error: 'basePositionSize and liquidityMetrics are required'
      });
    }

    const adjustedSize = liquidityMetricsEngine.calculateLiquidityAdjustedPositionSize(
      basePositionSize,
      liquidityMetrics,
      maxSlippageTolerance || 10
    );

    res.json({ adjustedSize });
  } catch (error) {
    console.error('[Learning API] Error calculating adjusted position size:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get liquidity history for a symbol
 */
router.get('/liquidity/history/:symbol', (req, res) => {
  try {
    const history = liquidityMetricsEngine.getLiquidityHistory(req.params.symbol);
    if (!history) {
      return res.status(404).json({ error: 'No liquidity history found for symbol' });
    }
    res.json(history);
  } catch (error) {
    console.error('[Learning API] Error getting liquidity history:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// ============================================================================
// HEALTH ENDPOINTS
// ============================================================================

/**
 * Get financial intelligence health
 */
router.get('/health/financial-intelligence', (req, res) => {
  try {
    // In a real implementation, this would return actual health metrics
    // For now, we'll return a placeholder
    const health: FinancialIntelligenceHealth = {
      overallStatus: 'HEALTHY',
      dataQuality: 0.85,
      providerHealth: 0.8,
      forecastAccuracy: 0.65,
      calibrationQuality: 0.7,
      strategyHealth: 0.75,
      researchActivity: 0.6,
      driftAlerts: 2,
      lastUpdated: new Date().toISOString()
    };

    res.json(health);
  } catch (error) {
    console.error('[Learning API] Error getting financial intelligence health:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;