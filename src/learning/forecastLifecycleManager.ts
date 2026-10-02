// ============================================================================
// MYRAA Phase 28 — Forecast Lifecycle Manager
// ============================================================================

import type {
  Forecast, ForecastLifecycleState, ForecastOutcome, ForecastEvaluation,
  ForecastType, ForecastHorizon, EvidenceSnapshot, DataSnapshot,
  StrategySnapshot, ModelSnapshot, RegimeType, EvaluationQueueItem
} from './contracts';
import { v4 as uuidv4 } from 'uuid';

export class ForecastLifecycleManager {
  private forecasts: Map<string, Forecast> = new Map();
  private outcomes: Map<string, ForecastOutcome> = new Map();
  private evaluations: Map<string, ForecastEvaluation> = new Map();
  private evaluationQueue: EvaluationQueueItem[] = [];
  private nextEvaluationId = 1;

  /**
   * Create a new forecast record
   */
  createForecast(params: {
    assetId: string;
    symbol: string;
    horizon: ForecastHorizon;
    type: ForecastType;
    prediction: string | number;
    confidence: number;
    strategyId: string;
    strategyVersion: string;
    evidenceSnapshot: EvidenceSnapshot;
    dataSnapshot: DataSnapshot;
    strategySnapshot: StrategySnapshot;
    regime: RegimeType;
    invalidationConditions: readonly string[];
    predictionDetails?: Record<string, unknown>;
    probability?: number;
    probabilityType?: 'FREQUENTIST' | 'BAYESIAN' | 'CONFIDENCE';
    thesisId?: string;
    modelSnapshot?: ModelSnapshot;
    researchSnapshot?: Record<string, unknown>;
  }): Forecast {
    const forecastId = `fcst_${uuidv4()}`;
    const now = new Date().toISOString();

    const forecast: Forecast = {
      forecastId,
      assetId: params.assetId,
      symbol: params.symbol,
      createdAt: now,
      decisionTimestamp: now,
      horizon: params.horizon,
      type: params.type,
      prediction: params.prediction,
      predictionDetails: params.predictionDetails,
      confidence: params.confidence,
      probability: params.probability,
      probabilityType: params.probabilityType,
      thesisId: params.thesisId,
      strategyId: params.strategyId,
      strategyVersion: params.strategyVersion,
      evidenceSnapshot: params.evidenceSnapshot,
      dataSnapshot: params.dataSnapshot,
      strategySnapshot: params.strategySnapshot,
      modelSnapshot: params.modelSnapshot,
      researchSnapshot: params.researchSnapshot,
      regime: params.regime,
      invalidationConditions: params.invalidationConditions,
      status: 'CREATED',
      evaluationTimestamp: undefined,
    };

    this.forecasts.set(forecastId, forecast);
    return forecast;
  }

  /**
   * Activate a forecast (move from CREATED to ACTIVE)
   */
  activateForecast(forecastId: string): Forecast | null {
    const forecast = this.forecasts.get(forecastId);
    if (!forecast) return null;

    if (forecast.status !== 'CREATED') {
      throw new Error(`Forecast ${forecastId} is not in CREATED state`);
    }

    const updated: Forecast = {
      ...forecast,
      status: 'ACTIVE',
    };

    this.forecasts.set(forecastId, updated);
    return updated;
  }

  /**
   * Mark forecast as awaiting outcome (after decision timestamp + horizon)
   */
  awaitOutcome(forecastId: string): Forecast | null {
    const forecast = this.forecasts.get(forecastId);
    if (!forecast) return null;

    if (forecast.status !== 'ACTIVE') {
      throw new Error(`Forecast ${forecastId} is not in ACTIVE state`);
    }

    const updated: Forecast = {
      ...forecast,
      status: 'AWAITING_OUTCOME',
    };

    this.forecasts.set(forecastId, updated);
    return updated;
  }

  /**
   * Record an outcome for a forecast
   */
  recordOutcome(params: Omit<ForecastOutcome, 'forecastId'> & { forecastId: string }): ForecastOutcome | null {
    const forecast = this.forecasts.get(params.forecastId);
    if (!forecast) return null;

    if (forecast.status === 'EVALUATED' || forecast.status === 'INVALIDATED' || forecast.status === 'EXPIRED') {
      throw new Error(`Forecast ${params.forecastId} is already finalized`);
    }

    const outcome: ForecastOutcome = {
      forecastId: params.forecastId,
      outcomeTimestamp: new Date().toISOString(),
      actualValue: params.actualValue,
      actualReturn: params.actualReturn,
      actualDirection: params.actualDirection,
      directionCorrect: params.directionCorrect,
      magnitudeError: params.magnitudeError,
      relativeError: params.relativeError,
      timingError: params.timingError,
      maximumAdverseMove: params.maximumAdverseMove,
      maximumFavorableMove: params.maximumFavorableMove,
      volatility: params.volatility,
      eventOccurred: params.eventOccurred,
      eventImpactActual: params.eventImpactActual,
      regimeAtOutcome: params.regimeAtOutcome,
      dataQuality: params.dataQuality,
      evaluationStatus: params.evaluationStatus,
    };

    this.outcomes.set(params.forecastId, outcome);

    // Update forecast status
    const updatedForecast: Forecast = {
      ...forecast,
      status: 'PARTIALLY_EVALUATED',
    };

    this.forecasts.set(params.forecastId, updatedForecast);

    // Add to evaluation queue for processing
    this.addToEvaluationQueue(params.forecastId, 'OUTCOME_RECORDED');

    return outcome;
  }

  /**
   * Evaluate a forecast against its outcome
   */
  evaluateForecast(forecastId: string): ForecastEvaluation | null {
    const forecast = this.forecasts.get(forecastId);
    const outcome = this.outcomes.get(forecastId);

    if (!forecast || !outcome) return null;

    if (forecast.status !== 'PARTIALLY_EVALUATED' && forecast.status !== 'AWAITING_OUTCOME') {
      throw new Error(`Forecast ${forecastId} is not ready for evaluation`);
    }

    // Calculate evaluation metrics based on forecast type
    const evaluation = this.calculateEvaluation(forecast, outcome);

    const evalId = `eval_${this.nextEvaluationId++}`;
    const evaluatedAt = new Date().toISOString();

    const forecastEvaluation: ForecastEvaluation = {
      forecastId,
      evaluationId: evalId,
      evaluatedAt,
      correctness: evaluation.correctness,
      error: evaluation.error,
      absoluteError: evaluation.absoluteError,
      relativeError: evaluation.relativeError,
      directionCorrect: evaluation.directionCorrect,
      timingAccuracy: evaluation.timingAccuracy,
      calibrationBucket: evaluation.calibrationBucket,
      confidenceQuality: evaluation.confidenceQuality,
      strategyOutcome: evaluation.strategyOutcome,
      failureCategory: evaluation.failureCategory,
      supportingEvidence: evaluation.supportingEvidence,
      missedEvidence: evaluation.missedEvidence,
      falseSignals: evaluation.falseSignals,
      evaluationVersion: '1.0.0',
      evaluator: 'CONTINUOUS_ENGINE',
    };

    this.evaluations.set(evalId, forecastEvaluation);

    // Update forecast status
    const updatedForecast: Forecast = {
      ...forecast,
      status: 'EVALUATED',
      evaluationTimestamp: evaluatedAt,
    };

    this.forecasts.set(forecastId, updatedForecast);

    return forecastEvaluation;
  }

  /**
   * Calculate evaluation metrics for a forecast
   */
  private calculateEvaluation(forecast: Forecast, outcome: ForecastOutcome): {
    correctness: boolean | null;
    error: number | null;
    absoluteError: number;
    relativeError: number;
    directionCorrect: boolean | null;
    timingAccuracy: number;
    calibrationBucket: number;
    confidenceQuality: number;
    strategyOutcome: 'SUCCESS' | 'FAILURE' | 'PARTIAL' | 'UNCERTAIN';
    failureCategory:
      | 'TREND_REVERSAL'
      | 'FALSE_BREAKOUT'
      | 'EVENT_MISREAD'
      | 'MACRO_SHOCK'
      | 'REGIME_SHIFT'
      | 'DATA_ERROR'
      | 'TIMING_ERROR'
      | 'LIQUIDITY'
      | 'VOLATILITY'
      | 'THESIS_INVALIDATION'
      | 'UNKNOWN'
      | null;
    supportingEvidence: string[];
    missedEvidence: string[];
    falseSignals: string[];
  } {
    // Initialize default values
    let correctness: boolean | null = null;
    let error: number | null = null;
    let absoluteError = 0;
    let relativeError = 0;
    let directionCorrect: boolean | null = null;
    let timingAccuracy = 0;
    let calibrationBucket = 5; // middle bucket by default
    let confidenceQuality = 0.5; // neutral by default
    let strategyOutcome: 'SUCCESS' | 'FAILURE' | 'PARTIAL' | 'UNCERTAIN' = 'UNCERTAIN';
    let failureCategory:
      | 'TREND_REVERSAL'
      | 'FALSE_BREAKOUT'
      | 'EVENT_MISREAD'
      | 'MACRO_SHOCK'
      | 'REGIME_SHIFT'
      | 'DATA_ERROR'
      | 'TIMING_ERROR'
      | 'LIQUIDITY'
      | 'VOLATILITY'
      | 'THESIS_INVALIDATION'
      | 'UNKNOWN'
      | null = null;
    let supportingEvidence: string[] = [];
    let missedEvidence: string[] = [];
    let falseSignals: string[] = [];

    // Handle different forecast types
    switch (forecast.type) {
      case 'DIRECTION':
        // For direction forecasts, correctness is based on direction match
        if (outcome.actualDirection && typeof forecast.prediction === 'string') {
          const predictedDirection = forecast.prediction.toUpperCase() as 'UP' | 'DOWN' | 'FLAT';
          directionCorrect = predictedDirection === outcome.actualDirection;
          correctness = directionCorrect;

          // Direction correctness contributes to overall correctness
          if (directionCorrect) {
            strategyOutcome = 'SUCCESS';
          } else {
            strategyOutcome = 'FAILURE';
            // Determine likely failure category based on evidence
            failureCategory = this.determineFailureCategory(forecast, outcome);
          }
        }
        break;

      case 'RETURN_RANGE':
        // For return range forecasts, check if actual return falls within predicted range
        if (typeof forecast.prediction === 'string' && outcome.actualReturn !== undefined) {
          // Prediction format: "min:max" (e.g., "-0.05:0.10" for -5% to +10%)
          const [minStr, maxStr] = forecast.prediction.split(':');
          const min = parseFloat(minStr);
          const max = parseFloat(maxStr);

          if (!isNaN(min) && !isNaN(max)) {
            const inRange = outcome.actualReturn >= min && outcome.actualReturn <= max;
            correctness = inRange;

            if (inRange) {
              strategyOutcome = 'SUCCESS';
            } else {
              strategyOutcome = 'FAILURE';
              failureCategory = this.determineFailureCategory(forecast, outcome);
            }

            // Calculate error as distance from nearest bound
            if (outcome.actualReturn < min) {
              error = outcome.actualReturn - min; // negative error (underprediction)
            } else if (outcome.actualReturn > max) {
              error = outcome.actualReturn - max; // positive error (overprediction)
            } else {
              error = 0; // within range
            }

            absoluteError = Math.abs(error);
            // Relative error as percentage of range width
            const rangeWidth = max - min;
            relativeError = rangeWidth > 0 ? absoluteError / rangeWidth : 0;
          }
        }
        break;

      case 'PRICE_TARGET':
        // For price target forecasts, compare actual price to target
        if (typeof forecast.prediction === 'number' && typeof outcome.actualValue === 'number') {
          error = outcome.actualValue - forecast.prediction; // positive = underprediction
          absoluteError = Math.abs(error);

          // Relative error as percentage of prediction
          relativeError = forecast.prediction !== 0 ? absoluteError / Math.abs(forecast.prediction) : 0;

          // Consider correct if within 5% tolerance
          correctness = absoluteError / Math.abs(forecast.prediction) <= 0.05;

          if (correctness) {
            strategyOutcome = 'SUCCESS';
          } else {
            strategyOutcome = 'FAILURE';
            failureCategory = this.determineFailureCategory(forecast, outcome);
          }
        }
        break;

      case 'VOLATILITY':
        // For volatility forecasts, compare predicted vs actual volatility
        if (typeof forecast.prediction === 'number' && outcome.volatility !== undefined) {
          error = outcome.volatility - forecast.prediction; // positive = underprediction
          absoluteError = Math.abs(error);

          // Relative error as percentage of prediction
          relativeError = forecast.prediction !== 0 ? absoluteError / Math.abs(forecast.prediction) : 0;

          // Consider correct if within 20% tolerance (volatility is harder to predict)
          correctness = absoluteError / Math.abs(forecast.prediction) <= 0.20;

          if (correctness) {
            strategyOutcome = 'SUCCESS';
          } else {
            strategyOutcome = 'FAILURE';
            failureCategory = 'VOLATILITY';
          }
        }
        break;

      case 'TREND':
        // For trend forecasts, evaluate based on direction and strength
        if (typeof forecast.prediction === 'string' && outcome.actualDirection) {
          const predictedDirection = forecast.prediction.toUpperCase() as 'UP' | 'DOWN' | 'FLAT';
          directionCorrect = predictedDirection === outcome.actualDirection;

          // Also consider timing accuracy
          timingAccuracy = outcome.timingError !== undefined ?
            Math.max(0, 1 - Math.abs(outcome.timingError) / forecast.horizon.bars) : 0.5;

          correctness = directionCorrect && timingAccuracy > 0.7;

          if (correctness) {
            strategyOutcome = 'SUCCESS';
          } else {
            strategyOutcome = 'PARTIAL'; // trend forecasts often partially correct

            if (!directionCorrect) {
              failureCategory = 'TREND_REVERSAL';
            } else if (timingAccuracy <= 0.7) {
              failureCategory = 'TIMING_ERROR';
            }
          }
        }
        break;

      case 'EVENT_IMPACT':
        // For event impact forecasts, check if event occurred and impact magnitude
        if (outcome.eventOccurred !== undefined) {
          const eventCorrect = outcome.eventOccurred === (typeof forecast.prediction === 'boolean' ? forecast.prediction : false);

          if (outcome.eventOccurred && outcome.eventImpactActual !== undefined && typeof forecast.prediction === 'number') {
            const impactError = Math.abs(outcome.eventImpactActual - forecast.prediction);
            const impactRelativeError = forecast.prediction !== 0 ? impactError / Math.abs(forecast.prediction) : 0;

            correctness = eventCorrect && impactRelativeError <= 0.3; // 30% tolerance for event impact
          } else {
            correctness = eventCorrect;
          }

          if (correctness) {
            strategyOutcome = 'SUCCESS';
          } else {
            strategyOutcome = 'FAILURE';
            if (!outcome.eventOccurred && typeof forecast.prediction === 'boolean' && forecast.prediction) {
              failureCategory = 'EVENT_MISREAD'; // predicted event that didn't happen
            } else if (outcome.eventOccurred && outcome.eventImpactActual !== undefined && typeof forecast.prediction === 'number') {
              failureCategory = 'EVENT_MISREAD'; // wrong impact magnitude
            } else {
              failureCategory = 'EVENT_MISREAD';
            }
          }
        }
        break;

      default:
        // For other types, use a simplified evaluation
        correctness = null;
        strategyOutcome = 'UNCERTAIN';
    }

    // Calculate calibration bucket based on confidence
    calibrationBucket = Math.floor(forecast.confidence * 10); // 0-10 scale

    // Calculate confidence quality: how well confidence matched outcome
    if (correctness !== null) {
      // If correct, high confidence is good; if incorrect, low confidence is good
      const expectedConfidence = correctness ? 0.8 : 0.3; // what confidence should have been
      confidenceQuality = 1 - Math.abs(forecast.confidence - expectedConfidence);
    }

    // Determine supporting/missed evidence based on forecast evidence and outcome
    // This is simplified - in reality would involve deeper analysis
    supportingEvidence = forecast.evidenceSnapshot.technical.slice(0, Math.min(3, forecast.evidenceSnapshot.technical.length));
    missedEvidence = forecast.evidenceSnapshot.fundamental.slice(0, Math.min(2, forecast.evidenceSnapshot.fundamental.length));
    falseSignals = forecast.evidenceSnapshot.events.slice(0, Math.min(2, forecast.evidenceSnapshot.events.length));

    return {
      correctness,
      error,
      absoluteError,
      relativeError,
      directionCorrect,
      timingAccuracy,
      calibrationBucket,
      confidenceQuality,
      strategyOutcome,
      failureCategory,
      supportingEvidence,
      missedEvidence,
      falseSignals,
    };
  }

  /**
   * Determine likely failure category based on forecast and outcome
   */
  private determineFailureCategory(forecast: Forecast, outcome: ForecastOutcome):
    | 'TREND_REVERSAL'
    | 'FALSE_BREAKOUT'
    | 'EVENT_MISREAD'
    | 'MACRO_SHOCK'
    | 'REGIME_SHIFT'
    | 'DATA_ERROR'
    | 'TIMING_ERROR'
    | 'LIQUIDITY'
    | 'VOLATILITY'
    | 'THESIS_INVALIDATION'
    | 'UNKNOWN' {
    // Simplified heuristic - in reality would analyze evidence vs outcome
    if (outcome.regimeAtOutcome && outcome.regimeAtOutcome !== forecast.regime) {
      return 'REGIME_SHIFT';
    }

    if (outcome.volatility !== undefined && outcome.volatility > 0.5) { // high volatility threshold
      return 'VOLATILITY';
    }

    if (outcome.timingError !== undefined && Math.abs(outcome.timingError) > forecast.horizon.bars * 0.5) {
      return 'TIMING_ERROR';
    }

    // Default to unknown
    return 'UNKNOWN';
  }

  /**
   * Add a forecast to the evaluation queue
   */
  addToEvaluationQueue(forecastId: string, reason: string, priority: number = 5): void {
    const item: EvaluationQueueItem = {
      itemId: `evalq_${uuidv4()}`,
      forecastId,
      priority, // 1-10, higher = higher priority
      reason,
      createdAt: new Date().toISOString(),
      scheduledFor: new Date(Date.now() + 60000).toISOString(), // schedule for 1 minute from now
      evaluatorType: 'AUTOMATIC',
      metadata: {},
    };

    this.evaluationQueue.push(item);
    // Sort by priority (higher first) then by creation time
    this.evaluationQueue.sort((a, b) => {
      if (a.priority !== b.priority) return b.priority - a.priority;
      return a.createdAt.localeCompare(b.createdAt);
    });
  }

  /**
   * Get next item from evaluation queue
   */
  getNextEvaluationItem(): EvaluationQueueItem | null {
    if (this.evaluationQueue.length === 0) return null;
    return this.evaluationQueue.shift()!;
  }

  /**
   * Get forecast by ID
   */
  getForecast(forecastId: string): Forecast | null {
    return this.forecasts.get(forecastId) || null;
  }

  /**
   * Get outcome by forecast ID
   */
  getOutcome(forecastId: string): ForecastOutcome | null {
    return this.outcomes.get(forecastId) || null;
  }

  /**
   * Get evaluation by forecast ID
   */
  getEvaluation(forecastId: string): ForecastEvaluation | null {
    // Find evaluation for this forecast
    for (const [evalId, evaluation] of this.evaluations.entries()) {
      if (evaluation.forecastId === forecastId) {
        return evaluation;
      }
    }
    return null;
  }

  /**
   * Get all forecasts in a specific state
   */
  getForecastsByState(state: ForecastLifecycleState): Forecast[] {
    return Array.from(this.forecasts.values()).filter(f => f.status === state);
  }

  /**
   * Get evaluation queue length
   */
  getQueueLength(): number {
    return this.evaluationQueue.length;
  }

  /**
   * Get internal forecasts map (for debugging/internal use)
   */
  getForecastsMap(): Map<string, Forecast> {
    return this.forecasts;
  }

  /**
   * Get internal evaluations map (for debugging/internal use)
   */
  getEvaluationsMap(): Map<string, ForecastEvaluation> {
    return this.evaluations;
  }

  /**
   * Invalidate a forecast (mark as invalidated)
   */
  invalidateForecast(forecastId: string, reason: string): Forecast | null {
    const forecast = this.forecasts.get(forecastId);
    if (!forecast) return null;

    const updated: Forecast = {
      ...forecast,
      status: 'INVALIDATED',
    };

    this.forecasts.set(forecastId, updated);
    return updated;
  }

  /**
   * Expire a forecast (mark as expired)
   */
  expireForecast(forecastId: string): Forecast | null {
    const forecast = this.forecasts.get(forecastId);
    if (!forecast) return null;

    const updated: Forecast = {
      ...forecast,
      status: 'EXPIRED',
    };

    this.forecasts.set(forecastId, updated);
    return updated;
  }
}

// Export singleton instance
export const forecastLifecycleManager = new ForecastLifecycleManager();