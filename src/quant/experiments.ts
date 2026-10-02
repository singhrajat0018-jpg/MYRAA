// ============================================================================
// MYRAA Phase 27 — Experiment Registry & Research Reports
// ============================================================================

import type {
  ResearchExperiment, ExperimentResult, ExperimentStatus,
  StrategyInstance, CostModel, BacktestResult, WalkForwardResult,
  MonteCarloResult, SensitivityResult, OverfittingAnalysis,
  CalibrationResult, ResearchReport,
} from './contracts';

export class ExperimentRegistry {
  private readonly experiments = new Map<string, ResearchExperiment>();
  private readonly results = new Map<string, ExperimentResult>();

  createExperiment(params: {
    name: string;
    description: string;
    strategy: StrategyInstance;
    datasetId: string;
    datasetSymbol: string;
    periodStart: string;
    periodEnd: string;
    costModel: CostModel;
    parameters?: Record<string, number | boolean | string>;
    seed?: number;
  }): ResearchExperiment {
    const id = `exp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const experiment: ResearchExperiment = {
      id,
      name: params.name,
      description: params.description,
      strategy: { ...params.strategy },
      datasetId: params.datasetId,
      datasetSymbol: params.datasetSymbol,
      periodStart: params.periodStart,
      periodEnd: params.periodEnd,
      costModel: { ...params.costModel },
      parameters: params.parameters ?? {},
      seed: params.seed ?? 42,
      createdAt: new Date().toISOString(),
      status: 'PLANNED',
    };
    this.experiments.set(id, experiment);
    this.results.set(id, {
      experiment,
      notes: [],
    });
    return experiment;
  }

  getExperiment(id: string): ResearchExperiment | undefined {
    return this.experiments.get(id);
  }

  getResult(id: string): ExperimentResult | undefined {
    return this.results.get(id);
  }

  updateStatus(id: string, status: ExperimentStatus): boolean {
    const exp = this.experiments.get(id);
    if (!exp) return false;
    this.experiments.set(id, { ...exp, status });
    const result = this.results.get(id);
    if (result) {
      this.results.set(id, { ...result, experiment: { ...exp, status } });
    }
    return true;
  }

  setBacktestResult(id: string, backtest: BacktestResult): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, backtest, completedAt: new Date().toISOString() });
    this.updateStatus(id, 'COMPLETED');
    return true;
  }

  setWalkForwardResult(id: string, walkForward: WalkForwardResult): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, walkForward });
    return true;
  }

  setMonteCarloResult(id: string, monteCarlo: MonteCarloResult): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, monteCarlo });
    return true;
  }

  setSensitivityResult(id: string, sensitivity: readonly SensitivityResult[]): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, sensitivity: [...sensitivity] });
    return true;
  }

  setOverfittingResult(id: string, overfitting: OverfittingAnalysis): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, overfitting });
    return true;
  }

  setCalibrationResult(id: string, calibration: CalibrationResult): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, calibration });
    return true;
  }

  addNote(id: string, note: string): boolean {
    const result = this.results.get(id);
    if (!result) return false;
    this.results.set(id, { ...result, notes: [...result.notes, note] });
    return true;
  }

  listExperiments(): readonly ResearchExperiment[] {
    return Array.from(this.experiments.values());
  }

  listCompleted(): ExperimentResult[] {
    return Array.from(this.results.values()).filter(
      r => r.experiment.status === 'COMPLETED',
    );
  }

  deleteExperiment(id: string): boolean {
    this.experiments.delete(id);
    return this.results.delete(id);
  }

  generateReport(id: string): ResearchReport | null {
    const result = this.results.get(id);
    if (!result) return null;
    const exp = result.experiment;
    const limitations: string[] = [];
    const disclaimers: string[] = [
      'This is a research report for analytical purposes only.',
      'Past performance does not guarantee future results.',
      'No trades were executed. All results are simulated/paper only.',
    ];
    if (result.walkForward && result.walkForward.overfittingScore > 0.5) {
      limitations.push('Walk-forward analysis suggests potential overfitting');
    }
    if (result.monteCarlo && result.monteCarlo.stats.probabilityOfLoss > 0.3) {
      limitations.push('Monte Carlo simulation shows elevated loss probability');
    }
    if (result.calibration && !result.calibration.isWellCalibrated) {
      limitations.push('Forecast calibration is suboptimal');
    }
    if (result.backtest && result.backtest.metrics.totalTrades < 30) {
      limitations.push('Small sample size may affect statistical significance');
    }
    const summary = this.buildSummary(result);
    return {
      reportId: `rpt_${Date.now()}`,
      title: `Research Report: ${exp.name}`,
      strategy: { ...exp.strategy },
      experimentIds: [id],
      datasetId: exp.datasetId,
      periodStart: exp.periodStart,
      periodEnd: exp.periodEnd,
      costModel: { ...exp.costModel },
      backtest: result.backtest,
      walkForward: result.walkForward,
      monteCarlo: result.monteCarlo,
      sensitivity: result.sensitivity,
      overfitting: result.overfitting,
      calibration: result.calibration,
      summary,
      limitations: Object.freeze(limitations),
      disclaimers: Object.freeze(disclaimers),
      generatedAt: new Date().toISOString(),
    };
  }

  private buildSummary(result: ExperimentResult): string {
    const parts: string[] = [];
    parts.push(`Strategy: ${result.experiment.strategy.definitionId} v${result.experiment.strategy.version}`);
    parts.push(`Period: ${result.experiment.periodStart} to ${result.experiment.periodEnd}`);
    parts.push(`Dataset: ${result.experiment.datasetSymbol} (${result.experiment.datasetId})`);
    if (result.backtest) {
      const m = result.backtest.metrics;
      parts.push(`Total Return: ${(m.totalReturn * 100).toFixed(1)}%, Sharpe: ${m.sharpeRatio.toFixed(2)}, Max DD: ${(m.maxDrawdown * 100).toFixed(1)}%`);
    }
    if (result.walkForward) {
      parts.push(`Walk-forward overfitting score: ${result.walkForward.overfittingScore.toFixed(2)}`);
    }
    if (result.monteCarlo) {
      parts.push(`Probability of loss: ${(result.monteCarlo.stats.probabilityOfLoss * 100).toFixed(1)}%`);
    }
    if (result.calibration) {
      parts.push(`Calibration error: ${result.calibration.expectedCalibrationError.toFixed(3)}`);
    }
    return parts.join('. ') + '.';
  }
}
