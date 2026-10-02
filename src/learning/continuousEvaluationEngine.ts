// ============================================================================
// MYRAA Phase 28 — Continuous Evaluation Engine
// ============================================================================

import type {
  Forecast, ForecastLifecycleState, ForecastOutcome, ForecastEvaluation,
  EvaluationQueueItem, StrategyHealth, ResearchLesson, ResearchHypothesis,
  StrategyAdaptationProposal, FinancialProviderHealth, PerformanceAttribution,
  LiquidityMetrics, DriftAlert, FinancialIntelligenceHealth
} from './contracts';
import type { StrategyInstance } from '../quant/contracts';
import { forecastLifecycleManager } from './forecastLifecycleManager';
import type { StrategyRegistry } from '../quant/strategy';
import type { TechnicalAnalysisEngine } from '../finance/technical';
import { CalibrationEngine } from '../quant/calibration';

// Note: In a full implementation, these would be imported from their actual locations
// For now, we'll define the interfaces we need

export class ContinuousEvaluationEngine {
  private forecastLifecycleManager: typeof forecastLifecycleManager;
  private strategyRegistry: StrategyRegistry | null;
  private technicalEngine: TechnicalAnalysisEngine | null;
  private calibrationEngine: CalibrationEngine;
  private isRunning = false;
  private evaluationInterval: NodeJS.Timeout | null = null;
  private readonly EVALUATION_INTERVAL_MS = 30000; // 30 seconds

  constructor() {
    this.forecastLifecycleManager = forecastLifecycleManager;
    this.calibrationEngine = new CalibrationEngine();
    // In a real implementation, these would be injected via DI
    this.strategyRegistry = null;
    this.technicalEngine = null;
  }

  /**
   * Start the continuous evaluation engine
   */
  start(): void {
    if (this.isRunning) return;

    this.isRunning = true;
    console.log('[ContinuousEvaluationEngine] Started');

    // Start periodic evaluation processing
    this.evaluationInterval = setInterval(() => {
      this.processEvaluationQueue();
    }, this.EVALUATION_INTERVAL_MS);

    // Process any items already in queue
    this.processEvaluationQueue();
  }

  /**
   * Stop the continuous evaluation engine
   */
  stop(): void {
    if (!this.isRunning) return;

    this.isRunning = false;
    if (this.evaluationInterval) {
      clearInterval(this.evaluationInterval);
      this.evaluationInterval = null;
    }
    console.log('[ContinuousEvaluationEngine] Stopped');
  }

  /**
   * Process the evaluation queue
   */
  private async processEvaluationQueue(): Promise<void> {
    if (!this.isRunning) return;

    let processedCount = 0;
    const maxPerCycle = 10; // Limit processing per cycle to prevent blocking

    while (processedCount < maxPerCycle) {
      const item = this.forecastLifecycleManager.getNextEvaluationItem();
      if (!item) break;

      try {
        await this.processEvaluationItem(item);
        processedCount++;
      } catch (error) {
        console.error(`[ContinuousEvaluationEngine] Error processing evaluation item ${item.itemId}:`, error);
        // Continue with next item
      }
    }

    if (processedCount > 0) {
      console.log(`[ContinuousEvaluationEngine] Processed ${processedCount} evaluation items`);
    }
  }

  /**
   * Process a single evaluation queue item
   */
  private async processEvaluationItem(item: EvaluationQueueItem): Promise<void> {
    const forecast = this.forecastLifecycleManager.getForecast(item.forecastId);
    if (!forecast) {
      console.warn(`[ContinuousEvaluationEngine] Forecast ${item.forecastId} not found for evaluation`);
      return;
    }

    // Check if forecast is ready for evaluation
    if (forecast.status !== 'PARTIALLY_EVALUATED' && forecast.status !== 'AWAITING_OUTCOME') {
      console.warn(`[ContinuousEvaluationEngine] Forecast ${item.forecastId} is not ready for evaluation (status: ${forecast.status})`);
      return;
    }

    // Get outcome if available
    const outcome = this.forecastLifecycleManager.getOutcome(item.forecastId);
    if (!outcome) {
      // Outcome not yet available, reschedule for later
      console.log(`[ContinuousEvaluationEngine] Outcome not yet available for forecast ${item.forecastId}, rescheduling`);
      this.rescheduleEvaluationItem(item);
      return;
    }

    // Perform the evaluation
    const evaluation = this.forecastLifecycleManager.evaluateForecast(item.forecastId);
    if (!evaluation) {
      console.error(`[ContinuousEvaluationEngine] Failed to evaluate forecast ${item.forecastId}`);
      return;
    }

    console.log(`[ContinuousEvaluationEngine] Evaluated forecast ${item.forecastId}: ${evaluation.strategyOutcome} (confidence quality: ${evaluation.confidenceQuality.toFixed(2)})`);

    // Update strategy health based on evaluation
    await this.updateStrategyHealth(forecast, evaluation);

    // Generate research lessons from forecast outcomes
    await this.generateResearchLessons(forecast, evaluation, outcome);

    // Check for hypothesis generation opportunities
    await this.checkHypothesisGeneration(forecast, evaluation, outcome);

    // Check for strategy adaptation opportunities
    await this.checkAdaptationOpportunities(forecast, evaluation, outcome);

    // Update provider health metrics
    await this.updateProviderHealth(forecast, evaluation, outcome);

    // Check for drift conditions
    await this.checkForDrift(forecast, evaluation, outcome);

    // Update overall financial intelligence health
    await this.updateFinancialIntelligenceHealth();
  }

  /**
   * Reschedule an evaluation item for later processing
   */
  private rescheduleEvaluationItem(item: EvaluationQueueItem): void {
    // Schedule for 5 minutes later
    const rescheduledItem: EvaluationQueueItem = {
      ...item,
      scheduledFor: new Date(Date.now() + 300000).toISOString(), // 5 minutes
      metadata: {
        ...item.metadata,
        rescheduled: true,
        originalScheduledFor: item.scheduledFor,
      },
    };

    // Add back to queue with slightly lower priority
    const loweredPriorityItem: EvaluationQueueItem = {
      ...rescheduledItem,
      priority: Math.max(1, item.priority - 1),
    };

    this.forecastLifecycleManager.addToEvaluationQueue(
      loweredPriorityItem.forecastId,
      loweredPriorityItem.reason,
      loweredPriorityItem.priority
    );
  }

  /**
   * Update strategy health based on forecast evaluation
   */
  private async updateStrategyHealth(forecast: Forecast, evaluation: ForecastEvaluation): Promise<void> {
    // In a real implementation, this would update the strategy health metrics
    // For now, we'll log the update
    console.log(`[ContinuousEvaluationEngine] Updating health for strategy ${forecast.strategyId}`);

    // This would typically:
    // 1. Retrieve current strategy health
    // 2. Update sample size, recent accuracy, rolling accuracy
    // 3. Calculate accuracy trend
    // 4. Update return metrics
    // 5. Update regime-specific performance
    // 6. Update failure statistics
    // 7. Persist updated health
  }

  /**
   * Generate research lessons from forecast outcomes
   */
  private async generateResearchLessons(
    forecast: Forecast,
    evaluation: ForecastEvaluation,
    outcome: ForecastOutcome
  ): Promise<void> {
    // Generate lessons from both successes and failures
    const lessonType = evaluation.strategyOutcome === 'SUCCESS' || evaluation.strategyOutcome === 'PARTIAL'
      ? 'SUCCESS'
      : 'FAILURE';

    // Only generate lessons for significant outcomes
    if (evaluation.strategyOutcome === 'UNCERTAIN') return;

    // Determine context from forecast
    const context = `During ${forecast.regime} regime with ${forecast.horizon.type} horizon`;

    // Generate recommendation based on failure category or success factors
    let recommendation = '';
    if (evaluation.failureCategory) {
      switch (evaluation.failureCategory) {
        case 'TREND_REVERSAL':
          recommendation = 'Consider adding trend strength confirmation before entering trades';
          break;
        case 'FALSE_BREAKOUT':
          recommendation = 'Require volume confirmation for breakout signals';
          break;
        case 'EVENT_MISREAD':
          recommendation = 'Improve event impact analysis and timing';
          break;
        case 'MACRO_SHOCK':
          recommendation = 'Add macroeconomic event monitoring to strategy';
          break;
        case 'REGIME_SHIFT':
          recommendation = 'Implement regime detection and adaptive parameters';
          break;
        case 'DATA_ERROR':
          recommendation = 'Improve data validation and use multiple data sources';
          break;
        case 'TIMING_ERROR':
          recommendation = 'Optimize entry/exit timing with better signal confirmation';
          break;
        case 'LIQUIDITY':
          recommendation = 'Add liquidity filters and avoid thinly traded periods';
          break;
        case 'VOLATILITY':
          recommendation = 'Implement volatility-adjusted position sizing';
          break;
        case 'THESIS_INVALIDATION':
          recommendation = 'Strengthen thesis validation with multiple timeframe analysis';
          break;
        default:
          recommendation = 'Review strategy logic and consider parameter adjustments';
      }
    } else {
      // Success case - identify what worked well
      recommendation = 'Strategy performed well; consider increasing position size cautiously';
    }

    // Create the research lesson
    const lesson: ResearchLesson = {
      lessonId: `lesson_${crypto.randomUUID()}`,
      source: `forecast_${forecast.forecastId}`,
      strategyId: forecast.strategyId,
      context,
      failureOrSuccess: lessonType as 'FAILURE' | 'SUCCESS',
      recommendation,
      confidence: evaluation.confidenceQuality,
      createdAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days
      regrets: evaluation.failureCategory ? [`We wish we had considered ${evaluation.failureCategory.toLowerCase()} more carefully`] : [],
      applicability: {
        regime: forecast.regime,
        strategyType: forecast.strategyId.includes('mean_reversion') ? 'MEAN_REVERSION' :
                  forecast.strategyId.includes('momentum') ? 'MOMENTUM' :
                  forecast.strategyId.includes('breakout') ? 'BREAKOUT' : undefined,
        horizon: forecast.horizon.type,
        volatilityRegime: outcome.volatility !== undefined && outcome.volatility > 0.3 ? 'HIGH' :
                         outcome.volatility !== undefined && outcome.volatility < 0.1 ? 'LOW' : 'NORMAL',
      },
    };

    // In a real implementation, this would be persisted to a research lessons database
    console.log(`[ContinuousEvaluationEngine] Generated research lesson: ${lesson.recommendation}`);
  }

  /**
   * Check for hypothesis generation opportunities
   */
  private async checkHypothesisGeneration(
    forecast: Forecast,
    evaluation: ForecastEvaluation,
    outcome: ForecastOutcome
  ): Promise<void> {
    // Generate hypotheses when we see unexpected outcomes or pattern violations
    if (evaluation.strategyOutcome === 'SUCCESS' || evaluation.confidenceQuality > 0.7) {
      return; // No need to generate hypotheses for good outcomes with high confidence
    }

    // Only generate hypotheses for significant failures
    if (!evaluation.failureCategory || evaluation.strategyOutcome === 'UNCERTAIN') {
      return;
    }

    // Create hypothesis based on failure category
    let description = '';
    let rationale = '';
    let testablePrediction = '';

    switch (evaluation.failureCategory) {
      case 'TREND_REVERSAL':
        description = 'Trend reversal signals are not being detected early enough';
        rationale = 'The strategy missed early warning signs of trend exhaustion';
        testablePrediction = 'Adding RSI divergence detection will improve early trend reversal detection';
        break;
      case 'FALSE_BREAKOUT':
        description = 'Breakout strategies are failing due to lack of follow-through';
        rationale = 'Many breakouts lack sufficient volume or momentum to sustain';
        testablePrediction = 'Requiring volume > 1.5x average will reduce false breakouts';
        break;
      case 'REGIME_SHIFT':
        description = 'Strategy fails to adapt to changing market regimes';
        rationale = 'Fixed parameters do not perform well across different market conditions';
        testablePrediction = 'Implementing regime detection will improve cross-regime performance';
        break;
      default:
        description = `Strategy experiencing ${evaluation.failureCategory.toLowerCase()} issues`;
        rationale = `The current approach does not adequately handle ${evaluation.failureCategory.toLowerCase()}`;
        testablePrediction = `Investigating alternative approaches will improve performance`;
    }

    // Create the research hypothesis
    const hypothesis: ResearchHypothesis = {
      hypothesisId: `hypo_${crypto.randomUUID()}`,
      sourceForecastId: forecast.forecastId,
      description,
      rationale,
      status: 'PROPOSED',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      evidenceFor: [forecast.forecastId], // The forecast that led to this hypothesis
      evidenceAgainst: [], // Would be populated with contradicting evidence
      testablePrediction,
      confidence: 0.6, // Initial confidence
      experimentId: undefined,
      sampleSize: 1, // Starting with the forecast that triggered it
    };

    // In a real implementation, this would be persisted and linked to the planner for testing
    console.log(`[ContinuousEvaluationEngine] Generated research hypothesis: ${hypothesis.description}`);
  }

  /**
   * Check for strategy adaptation opportunities
   */
  private async checkAdaptationOpportunities(
    forecast: Forecast,
    evaluation: ForecastEvaluation,
    outcome: ForecastOutcome
  ): Promise<void> {
    // Only consider adaptation proposals for consistently failing strategies
    // In a real implementation, we would check strategy health over multiple forecasts

    // For now, we'll create a proposal if we see a clear failure pattern
    if (evaluation.strategyOutcome !== 'FAILURE' || !evaluation.failureCategory) {
      return;
    }

    // Check if we already have recent proposals for this strategy
    // (In real impl, would check database for recent proposals)

    // Create adaptation proposal based on failure category
    let proposedChanges: Record<string, unknown> = {};
    let problemStatement = '';
    let evidence: string[] = [];
    let reasoning = '';

    switch (evaluation.failureCategory) {
      case 'TREND_REVERSAL':
        problemStatement = 'Strategy fails to exit positions before trend reversals';
        evidence = [forecast.forecastId]; // In reality, would be multiple failing forecasts
        proposedChanges = {
          addExitSignal: true,
          exitSignalType: 'RSI_DIVERGENCE',
          exitSignalParameters: { rsiPeriod: 14, divergenceLookback: 10 },
        };
        reasoning = 'Adding RSI divergence exit signal will help capture more profit before reversals';
        break;
      case 'FALSE_BREAKOUT':
        problemStatement = 'Strategy enters breakouts that fail to follow through';
        evidence = [forecast.forecastId];
        proposedChanges = {
          addVolumeFilter: true,
          volumeThreshold: 1.5, // 1.5x average volume
          volumeType: 'AVG_VOLUME_20',
        };
        reasoning = 'Requiring higher volume confirmation will reduce false breakouts';
        break;
      case 'REGIME_SHIFT':
        problemStatement = 'Strategy does not adapt to changing market conditions';
        evidence = [forecast.forecastId];
        proposedChanges = {
          addRegimeDetection: true,
          regimeMethod: 'HMM', // Hidden Markov Model
          lookbackPeriod: 50,
        };
        reasoning = 'Adapting strategy parameters to market regime will improve consistency';
        break;
      default:
        problemStatement = `Strategy experiencing ${evaluation.failureCategory.toLowerCase()}`;
        evidence = [forecast.forecastId];
        proposedChanges = { reviewNeeded: true };
        reasoning = 'Strategy requires review and potential adjustment';
    }

    // Only create proposal if we have meaningful changes
    if (Object.keys(proposedChanges).length > 0) {
      const proposal: StrategyAdaptationProposal = {
        proposalId: `prop_${crypto.randomUUID()}`,
        currentStrategyId: forecast.strategyId,
        currentStrategyVersion: '1.0.0', // In reality, would get from forecast
        proposedChanges,
        problemStatement,
        evidence,
        reasoning,
        validationRequired: {
          backtest: true,
          walkForward: true,
          outOfSample: true,
          costSensitivity: true,
          regimeRobustness: true
        },
        status: 'PROPOSED',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        championVsChallenger: {
          champion: forecast.strategyId,
          challenger: `${forecast.strategyId}_adapted_${crypto.randomUUID().substring(0, 8)}`
        }
      };

      // In a real implementation, this would be persisted and made available for review/testing
      console.log(`[ContinuousEvaluationEngine] Generated adaptation proposal: ${proposal.problemStatement}`);
    }
  }

  /**
   * Update provider health metrics based on forecast performance
   */
  private async updateProviderHealth(
    forecast: Forecast,
    evaluation: ForecastEvaluation,
    outcome: ForecastOutcome
  ): Promise<void> {
    // In a real implementation, this would:
    // 1. Identify which providers contributed to the evidence snapshot
    // 2. Update their performance metrics based on forecast outcome
    // 3. Adjust reliability scores
    // 4. Persist updated provider health

    // For now, we'll log that we're updating provider health
    const providersUsed = [
      ...forecast.evidenceSnapshot.technical,
      ...forecast.evidenceSnapshot.fundamental,
      ...forecast.evidenceSnapshot.events,
      ...forecast.evidenceSnapshot.macro,
      ...forecast.evidenceSnapshot.regime,
      ...forecast.evidenceSnapshot.sentiment,
    ];

    if (providersUsed.length > 0) {
      console.log(`[ContinuousEvaluationEngine] Updating health for ${providersUsed.length} providers used in forecast ${forecast.forecastId}`);
    }
  }

  /**
   * Check for drift conditions in strategy performance, confidence, data, etc.
   */
  private async checkForDrift(
    forecast: Forecast,
    evaluation: ForecastEvaluation,
    outcome: ForecastOutcome
  ): Promise<void> {
    // Check for various types of drift that might indicate degrading performance

    // Performance drift - significant change in strategy accuracy
    // Confidence drift - confidence no longer matching outcomes
    // Data drift - incoming data characteristics changing
    // Signal drift - signals becoming less predictive
    // Regime drift - market regime characteristics shifting

    // For now, we'll simulate checking for confidence drift
    if (evaluation.confidenceQuality < 0.3 && forecast.confidence > 0.7) {
      // High confidence but poor outcome - potential overconfidence
      const alert: DriftAlert = {
        alertId: `drift_${crypto.randomUUID()}`,
        type: 'CONFIDENCE',
        severity: 'MEDIUM',
        description: 'Forecast confidence consistently exceeding actual accuracy',
        detectedAt: new Date().toISOString(),
        metric: 'confidence_vs_accuracy',
        currentValue: evaluation.confidenceQuality,
        historicalValue: 0.7, // assumed historical confidence quality
        changePercent: ((evaluation.confidenceQuality - 0.7) / 0.7) * 100,
        confidence: 0.8,
        recommendedAction: 'Review confidence calibration and consider reducing forecast confidence levels',
      };

      // In a real implementation, this would be persisted and potentially trigger notifications
      console.log(`[ContinuousEvaluationEngine] Detected confidence drift: ${alert.description}`);
    }

    // Check for performance drift
    if (evaluation.strategyOutcome === 'FAILURE') {
      // Would check if failure rate is increasing beyond acceptable threshold
      console.log(`[ContinuousEvaluationEngine] Monitoring for performance drift on strategy ${forecast.strategyId}`);
    }
  }

  /**
   * Update overall financial intelligence health metrics
   */
  private async updateFinancialIntelligenceHealth(): Promise<void> {
    // In a real implementation, this would calculate:
    // 1. Overall data quality from provider health
    // 2. Recent forecast accuracy across all strategies
    // 3. Calibration quality from confidence vs outcomes
    // 4. Average strategy health across all strategies
    // 5. Research activity level
    // 6. Number of active drift alerts
    // 7. Composite health score

    // For now, we'll log that we're updating health
    console.log('[ContinuousEvaluationEngine] Updating financial intelligence health metrics');
  }

  /**
   * Manually trigger evaluation of a specific forecast
   */
  async evaluateForecastNow(forecastId: string): Promise<ForecastEvaluation | null> {
    const forecast = this.forecastLifecycleManager.getForecast(forecastId);
    if (!forecast) {
      console.warn(`[ContinuousEvaluationEngine] Forecast ${forecastId} not found`);
      return null;
    }

    const outcome = this.forecastLifecycleManager.getOutcome(forecastId);
    if (!outcome) {
      console.warn(`[ContinuousEvaluationEngine] No outcome available for forecast ${forecastId}`);
      return null;
    }

    return this.forecastLifecycleManager.evaluateForecast(forecastId);
  }

  /**
   * Get statistics about the evaluation engine
   */
  getStatistics(): {
    totalForecasts: number;
    activeForecasts: number;
    awaitingOutcome: number;
    evaluatedForecasts: number;
    queueLength: number;
    evaluationsPerformed: number;
  } {
    const forecasts = Array.from(this.forecastLifecycleManager.getForecastsMap().values());
    const evaluations = Array.from(this.forecastLifecycleManager.getEvaluationsMap().values());

    return {
      totalForecasts: forecasts.length,
      activeForecasts: forecasts.filter(f => f.status === 'ACTIVE').length,
      awaitingOutcome: forecasts.filter(f => f.status === 'AWAITING_OUTCOME').length,
      evaluatedForecasts: evaluations.length,
      queueLength: this.forecastLifecycleManager.getQueueLength(),
      evaluationsPerformed: evaluations.length,
    };
  }
}

// Export singleton instance
export const continuousEvaluationEngine = new ContinuousEvaluationEngine();