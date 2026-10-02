// ============================================================================
// MYRAA Execution Engine — Task scheduling, fallback, retry, budget enforcement
// ============================================================================

import type {
  PlanTask, ExecutionPlan, TaskResult, TaskStatus, FailureClassification,
  PlanBudget, RuntimeBudget, BudgetStatus, AgentEvent, VerificationResult,
} from './contracts';
import { generateAgentId, nowISO, DEFAULT_RETRY_POLICY } from './contracts';

// ============================================================================
// Execution Engine
// ============================================================================

export class ExecutionEngine {
  private activePlans: Map<string, ExecutionPlan> = new Map();
  private completedTasks: Map<string, Set<string>> = new Map(); // planId → completed taskIds
  private runningTasks: Map<string, Set<string>> = new Map();
  private taskResults: Map<string, TaskResult> = new Map();
  private planBudgets: Map<string, PlanBudget> = new Map();
  private budgetUsed: Map<string, RuntimeBudget> = new Map();
  private eventHandler?: (event: AgentEvent) => void;
  private taskExecutor?: (task: PlanTask) => Promise<TaskResult>;
  private verifier?: (task: PlanTask, result: TaskResult) => Promise<VerificationResult>;

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  setTaskExecutor(executor: (task: PlanTask) => Promise<TaskResult>): void {
    this.taskExecutor = executor;
  }

  setVerifier(verifier: (task: PlanTask, result: TaskResult) => Promise<VerificationResult>): void {
    this.verifier = verifier;
  }

  // --- Plan Management ---

  startPlan(plan: ExecutionPlan): void {
    this.activePlans.set(plan.planId, plan);
    this.completedTasks.set(plan.planId, new Set());
    this.runningTasks.set(plan.planId, new Set());
    this.planBudgets.set(plan.planId, plan.budget);
    this.budgetUsed.set(plan.planId, {
      stepsUsed: 0,
      toolCallsUsed: 0,
      researchCallsUsed: 0,
      timeUsedMs: 0,
      replansUsed: 0,
      retriesUsed: 0,
      withinBudget: true,
      exhaustedResources: [],
    });

    this.emit({
      type: 'PLAN_CREATED',
      agentId: 'system',
      planId: plan.planId,
      goalId: plan.goalId,
      timestamp: nowISO(),
      data: { taskCount: plan.tasks.length },
    });
  }

  getPlan(planId: string): ExecutionPlan | undefined {
    return this.activePlans.get(planId);
  }

  // --- Execution Loop ---

  async executeReadyTasks(planId: string): Promise<{
    completed: string[];
    failed: string[];
    blocked: string[];
    awaitingApproval: string[];
  }> {
    const plan = this.activePlans.get(planId);
    if (!plan) return { completed: [], failed: [], blocked: [], awaitingApproval: [] };

    const completed = this.completedTasks.get(planId) || new Set();
    const running = this.runningTasks.get(planId) || new Set();
    const budget = this.budgetUsed.get(planId);

    // Check budget
    if (budget && !budget.withinBudget) {
      return { completed: [], failed: [], blocked: plan.tasks.map(t => t.taskId), awaitingApproval: [] };
    }

    // Find ready tasks
    const readyTasks = plan.tasks.filter(task => {
      if (completed.has(task.taskId) || running.has(task.taskId)) return false;
      if (task.status === 'BLOCKED' || task.status === 'CANCELLED' || task.status === 'SKIPPED') return false;
      return task.dependencies.every(dep => completed.has(dep));
    });

    const result = { completed: [] as string[], failed: [] as string[], blocked: [] as string[], awaitingApproval: [] as string[] };

    // Check approval requirements
    for (const task of readyTasks) {
      const needsApproval = plan.approvalRequirements.some(ar => ar.taskId === task.taskId);
      if (needsApproval && task.status !== 'WAITING_APPROVAL') {
        result.awaitingApproval.push(task.taskId);
        this.emit({ type: 'APPROVAL_REQUIRED', agentId: 'system', planId, taskId: task.taskId, timestamp: nowISO(), data: { reason: 'High-risk action requires approval' } });
        continue;
      }
    }

    // Execute ready tasks (respecting parallel limits)
    const executable = readyTasks.filter(t => !result.awaitingApproval.includes(t.taskId));
    const parallelLimit = plan.budget.maxParallelTasks;
    const toExecute = executable.slice(0, parallelLimit);

    for (const task of toExecute) {
      running.add(task.taskId);
      this.updateTaskStatus(plan, task.taskId, 'RUNNING');
      this.emit({ type: 'TASK_STARTED', agentId: 'system', planId, taskId: task.taskId, timestamp: nowISO(), data: { type: task.type } });

      try {
        let taskResult = await this.executeTask(task, budget);

        if (taskResult.success) {
          // Verify if required
          if (task.verificationPolicy?.required && this.verifier) {
            const verification = await this.verifier(task, taskResult);
            if (verification.status === 'FAILED') {
              taskResult = {
                ...taskResult,
                verificationStatus: 'FAILED',
                success: false,
                error: `Verification failed: ${verification.message}`,
              };
            }
          }

          if (taskResult.success) {
            completed.add(task.taskId);
            running.delete(task.taskId);
            this.taskResults.set(task.taskId, taskResult);
            this.updateTaskStatus(plan, task.taskId, 'COMPLETED');
            this.emit({ type: 'TASK_COMPLETED', agentId: 'system', planId, taskId: task.taskId, timestamp: nowISO(), data: { latencyMs: taskResult.latencyMs } });
            result.completed.push(task.taskId);
            if (budget) budget.stepsUsed++;
          } else {
            running.delete(task.taskId);
            this.handleTaskFailure(plan, task, taskResult, budget);
            result.failed.push(task.taskId);
          }
        } else {
          running.delete(task.taskId);
          this.handleTaskFailure(plan, task, taskResult, budget);
          result.failed.push(task.taskId);
        }
      } catch (err) {
        running.delete(task.taskId);
        const errorResult: TaskResult = {
          success: false,
          data: null,
          error: String(err),
          timestamp: nowISO(),
          latencyMs: 0,
          provenance: [],
          confidence: 0,
          retryable: true,
        };
        this.handleTaskFailure(plan, task, errorResult, budget);
        result.failed.push(task.taskId);
      }
    }

    return result;
  }

  // --- Task Execution ---

  private async executeTask(task: PlanTask, budget?: RuntimeBudget): Promise<TaskResult> {
    const start = Date.now();

    // Use custom executor if set
    if (this.taskExecutor) {
      try {
        const result = await this.taskExecutor(task);
        if (budget) budget.toolCallsUsed++;
        return result;
      } catch (err) {
        return this.makeResult(false, null, String(err), start, true);
      }
    }

    // Default: simulate task
    return this.makeResult(true, { taskId: task.taskId, type: task.type }, undefined, start, false);
  }

  private handleTaskFailure(plan: ExecutionPlan, task: PlanTask, result: TaskResult, budget?: RuntimeBudget): void {
    const classification = this.classifyFailure(result);
    this.updateTaskStatus(plan, task.taskId, 'FAILED');

    this.emit({
      type: 'TASK_FAILED',
      agentId: 'system',
      planId: plan.planId,
      taskId: task.taskId,
      timestamp: nowISO(),
      data: { error: result.error, classification, retryCount: task.retryCount },
    });

    // Retry if retryable
    if (budget && task.retryCount < task.retryPolicy.maxRetries &&
        task.retryPolicy.retryableFailures.includes(classification)) {
      budget.retriesUsed++;
      // Reset task for retry
      this.updateTaskStatus(plan, task.taskId, 'PENDING');
    }
  }

  private classifyFailure(result: TaskResult): FailureClassification {
    const error = (result.error || '').toLowerCase();
    if (error.includes('timeout') || error.includes('timed out')) return 'TIMEOUT';
    if (error.includes('rate limit') || error.includes('429')) return 'RATE_LIMITED';
    if (error.includes('unauthorized') || error.includes('401') || error.includes('auth')) return 'AUTH_REQUIRED';
    if (error.includes('forbidden') || error.includes('403') || error.includes('permission')) return 'PERMISSION_DENIED';
    if (error.includes('not found') || error.includes('404')) return 'PERMANENT';
    if (error.includes('network') || error.includes('econnrefused') || error.includes('fetch')) return 'TRANSIENT';
    if (error.includes('provider') && error.includes('down')) return 'PROVIDER_DOWN';
    if (error.includes('verification')) return 'VERIFICATION_FAILED';
    if (error.includes('invalid input') || error.includes('validation')) return 'INVALID_INPUT';
    return 'UNKNOWN';
  }

  private makeResult(success: boolean, data: unknown, error: string | undefined, start: number, retryable: boolean): TaskResult {
    return {
      success,
      data,
      error,
      timestamp: nowISO(),
      latencyMs: Date.now() - start,
      provenance: [],
      confidence: success ? 0.8 : 0,
      retryable,
    };
  }

  private updateTaskStatus(plan: ExecutionPlan, taskId: string, status: TaskStatus): void {
    // Update in place (plan.tasks is readonly, but we track status separately)
    // For a real implementation, we'd have a mutable task store
  }

  // --- Approval ---

  approveTask(planId: string, taskId: string): boolean {
    const plan = this.activePlans.get(planId);
    if (!plan) return false;
    this.emit({ type: 'APPROVAL_GRANTED', agentId: 'system', planId, taskId, timestamp: nowISO(), data: {} });
    return true;
  }

  denyTask(planId: string, taskId: string, reason: string): boolean {
    const plan = this.activePlans.get(planId);
    if (!plan) return false;
    this.updateTaskStatus(plan, taskId, 'BLOCKED');
    this.emit({ type: 'APPROVAL_DENIED', agentId: 'system', planId, taskId, timestamp: nowISO(), data: { reason } });
    return true;
  }

  // --- Cancellation ---

  cancelPlan(planId: string): boolean {
    const plan = this.activePlans.get(planId);
    if (!plan) return false;
    this.activePlans.delete(planId);
    this.completedTasks.delete(planId);
    this.runningTasks.delete(planId);
    this.emit({ type: 'PLAN_CANCELLED', agentId: 'system', planId, timestamp: nowISO(), data: {} });
    return true;
  }

  // --- Budget ---

  getBudgetStatus(planId: string): BudgetStatus | undefined {
    const budget = this.budgetUsed.get(planId);
    const planBudget = this.planBudgets.get(planId);
    if (!budget || !planBudget) return undefined;

    const exhausted: string[] = [];
    if (budget.stepsUsed >= planBudget.maxSteps) exhausted.push('steps');
    if (budget.toolCallsUsed >= planBudget.maxToolCalls) exhausted.push('toolCalls');
    if (budget.researchCallsUsed >= planBudget.maxResearchCalls) exhausted.push('researchCalls');
    if (budget.timeUsedMs >= planBudget.maxTimeMs) exhausted.push('time');
    if (budget.replansUsed >= planBudget.maxReplans) exhausted.push('replans');

    return {
      stepsUsed: budget.stepsUsed,
      toolCallsUsed: budget.toolCallsUsed,
      researchCallsUsed: budget.researchCallsUsed,
      timeUsedMs: budget.timeUsedMs,
      replansUsed: budget.replansUsed,
      retriesUsed: budget.retriesUsed,
      withinBudget: exhausted.length === 0,
      exhaustedResources: exhausted,
    };
  }

  getTaskResult(taskId: string): TaskResult | undefined {
    return this.taskResults.get(taskId);
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }

  getStats() {
    return {
      activePlans: this.activePlans.size,
      totalCompleted: Array.from(this.completedTasks.values()).reduce((s, set) => s + set.size, 0),
      totalRunning: Array.from(this.runningTasks.values()).reduce((s, set) => s + set.size, 0),
    };
  }
}
