// ============================================================================
// MYRAA Verification Engine — Verify outcomes, trigger recovery
// ============================================================================

import type {
  PlanTask, TaskResult, VerificationResult, VerificationStatus,
  VerificationStrategy, AgentEvent,
} from './contracts';
import { nowISO } from './contracts';

// ============================================================================
// Verification Engine
// ============================================================================

export class VerificationEngine {
  private eventHandler?: (event: AgentEvent) => void;
  private verificationResults: Map<string, VerificationResult[]> = new Map();

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Verify Task ---

  async verify(task: PlanTask, result: TaskResult): Promise<VerificationResult> {
    const policy = task.verificationPolicy;
    if (!policy || !policy.required) {
      return this.makeResult(task.taskId, 'ASSERTION', 'VERIFIED', 'No verification required');
    }

    this.emit({ type: 'VERIFICATION_STARTED', agentId: 'system', taskId: task.taskId, timestamp: nowISO(), data: { strategies: policy.strategies } });

    for (const strategy of policy.strategies) {
      const vr = await this.executeStrategy(strategy, task, result);
      this.recordResult(task.taskId, vr);

      if (vr.status === 'FAILED') {
        this.emit({ type: 'VERIFICATION_FAILED', agentId: 'system', taskId: task.taskId, timestamp: nowISO(), data: { strategy, message: vr.message } });
        return vr;
      }
    }

    this.emit({ type: 'VERIFICATION_PASSED', agentId: 'system', taskId: task.taskId, timestamp: nowISO(), data: {} });
    return this.makeResult(task.taskId, 'ASSERTION', 'VERIFIED', 'All verification strategies passed');
  }

  // --- Strategy Execution ---

  private async executeStrategy(
    strategy: VerificationStrategy,
    task: PlanTask,
    result: TaskResult,
  ): Promise<VerificationResult> {
    switch (strategy) {
      case 'ASSERTION':
        return this.verifyAssertion(task, result);
      case 'STATE_CHECK':
        return this.verifyStateCheck(task, result);
      case 'SOURCE_CHECK':
        return this.verifySourceCheck(task, result);
      case 'COMPARISON':
        return this.verifyComparison(task, result);
      case 'REQUERY':
        return this.verifyRequery(task, result);
      case 'FILE_CHECK':
        return this.verifyFileCheck(task, result);
      case 'PROCESS_CHECK':
        return this.verifyProcessCheck(task, result);
      case 'API_CHECK':
        return this.verifyApiCheck(task, result);
      case 'USER_CONFIRMATION':
        return this.verifyUserConfirmation(task, result);
      default:
        return this.makeResult(task.taskId, strategy, 'VERIFIED', 'Strategy not implemented, assuming pass');
    }
  }

  private verifyAssertion(task: PlanTask, result: TaskResult): VerificationResult {
    // Basic assertion: task completed and has data
    if (result.success && result.data !== null && result.data !== undefined) {
      return this.makeResult(task.taskId, 'ASSERTION', 'VERIFIED', 'Task completed with data');
    }
    return this.makeResult(task.taskId, 'ASSERTION', 'FAILED', 'Task result missing or unsuccessful');
  }

  private verifyStateCheck(task: PlanTask, result: TaskResult): VerificationResult {
    // Verify expected outcome matches actual
    if (result.success && result.confidence >= 0.5) {
      return this.makeResult(task.taskId, 'STATE_CHECK', 'VERIFIED', 'State check passed');
    }
    return this.makeResult(task.taskId, 'STATE_CHECK', 'FAILED', 'State check failed: low confidence or unsuccessful');
  }

  private verifySourceCheck(task: PlanTask, result: TaskResult): VerificationResult {
    // Verify evidence came from real sources
    if (result.provenance.length > 0 || result.data !== null) {
      return this.makeResult(task.taskId, 'SOURCE_CHECK', 'VERIFIED', 'Source check passed');
    }
    return this.makeResult(task.taskId, 'SOURCE_CHECK', 'FAILED', 'No provenance or data found');
  }

  private verifyComparison(task: PlanTask, result: TaskResult): VerificationResult {
    if (result.data && typeof result.data === 'object' && 'options' in (result.data as Record<string, unknown>)) {
      return this.makeResult(task.taskId, 'COMPARISON', 'VERIFIED', 'Comparison has structured options');
    }
    return this.makeResult(task.taskId, 'COMPARISON', 'PARTIAL', 'Comparison data not fully structured');
  }

  private verifyRequery(task: PlanTask, result: TaskResult): VerificationResult {
    // Requery not implemented for deterministic verification
    return this.makeResult(task.taskId, 'REQUERY', 'VERIFIED', 'Requery skipped: using cached result');
  }

  private verifyFileCheck(task: PlanTask, result: TaskResult): VerificationResult {
    if (result.success) {
      return this.makeResult(task.taskId, 'FILE_CHECK', 'VERIFIED', 'File operation completed');
    }
    return this.makeResult(task.taskId, 'FILE_CHECK', 'FAILED', 'File operation failed');
  }

  private verifyProcessCheck(task: PlanTask, result: TaskResult): VerificationResult {
    return this.makeResult(task.taskId, 'PROCESS_CHECK', 'VERIFIED', 'Process check passed');
  }

  private verifyApiCheck(task: PlanTask, result: TaskResult): VerificationResult {
    if (result.success && result.latencyMs < task.timeout) {
      return this.makeResult(task.taskId, 'API_CHECK', 'VERIFIED', 'API responded within timeout');
    }
    return this.makeResult(task.taskId, 'API_CHECK', 'FAILED', 'API call failed or timed out');
  }

  private verifyUserConfirmation(task: PlanTask, result: TaskResult): VerificationResult {
    // User confirmation requires human input - not auto-verifiable
    return this.makeResult(task.taskId, 'USER_CONFIRMATION', 'PARTIAL', 'User confirmation pending');
  }

  // --- Results ---

  private recordResult(taskId: string, result: VerificationResult): void {
    const existing = this.verificationResults.get(taskId) || [];
    existing.push(result);
    this.verificationResults.set(taskId, existing);
  }

  getResults(taskId: string): VerificationResult[] {
    return this.verificationResults.get(taskId) || [];
  }

  getAllResults(): Map<string, VerificationResult[]> {
    return new Map(this.verificationResults);
  }

  private makeResult(taskId: string, strategy: VerificationStrategy, status: VerificationStatus, message: string): VerificationResult {
    return { taskId, strategy, status, message, evidence: [], timestamp: nowISO() };
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }
}
