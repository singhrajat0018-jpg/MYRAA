// ============================================================================
// MYRAA Plan Builder — Constructs validated execution plans
// ============================================================================

import type {
  Goal, PlanTask, ExecutionPlan, PlanBudget, PlanStatus,
  RiskLevel, ApprovalRequirement, VerificationPolicy, AgentEvent,
} from './contracts';
import { generateAgentId, nowISO, DEFAULT_PLAN_BUDGET } from './contracts';
import { PlanGraph } from './plan_graph';
import { GoalDecomposer } from './decomposer';
import { StrategySelector } from './strategy';

// ============================================================================
// Plan Builder
// ============================================================================

export class PlanBuilder {
  private decomposer: GoalDecomposer;
  private strategySelector: StrategySelector;
  private eventHandler?: (event: AgentEvent) => void;

  constructor() {
    this.decomposer = new GoalDecomposer();
    this.strategySelector = new StrategySelector();
  }

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  buildPlan(goal: Goal, budget?: Partial<PlanBudget>): ExecutionPlan {
    // 1. Decompose goal into tasks
    const tasks = this.decomposer.decompose(goal);

    // 2. Select strategy
    const strategy = this.strategySelector.selectStrategy(goal);

    // 3. Build DAG
    const graph = new PlanGraph(tasks);

    // 4. Validate
    const validation = graph.validate();
    if (!validation.valid) {
      throw new Error(`Plan validation failed: ${validation.errors.join('; ')}`);
    }

    // 5. Build plan
    const plan = graph.buildPlan(goal.id, strategy, budget);

    // 6. Add verification policies to tasks that need them
    const enrichedTasks = this.enrichTasksWithVerification(plan.tasks, goal);

    // 7. Identify approval requirements
    const approvalReqs = this.identifyApprovalRequirements(enrichedTasks);

    // 8. Build rollback plan
    const rollbackPlan = this.buildRollbackPlan(enrichedTasks);

    const enrichedPlan: ExecutionPlan = {
      ...plan,
      tasks: enrichedTasks,
      approvalRequirements: approvalReqs,
      rollbackPlan,
      requiredEvidence: this.collectEvidenceRequirements(enrichedTasks),
    };

    this.emit({
      type: 'PLAN_CREATED',
      agentId: 'system',
      goalId: goal.id,
      planId: enrichedPlan.planId,
      timestamp: nowISO(),
      data: { taskCount: enrichedTasks.length, strategy, risk: enrichedPlan.riskSummary },
    });

    return enrichedPlan;
  }

  validatePlan(plan: ExecutionPlan): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Validate budget
    if (plan.tasks.length > plan.budget.maxSteps) {
      errors.push(`Task count ${plan.tasks.length} exceeds budget ${plan.budget.maxSteps}`);
    }

    // Validate DAG
    const graph = new PlanGraph(plan.tasks);
    const dagValidation = graph.validate();
    if (!dagValidation.valid) errors.push(...dagValidation.errors);

    // Validate each task
    for (const task of plan.tasks) {
      if (!task.title) errors.push(`Task ${task.taskId} has no title`);
      if (task.timeout <= 0) errors.push(`Task ${task.taskId} has invalid timeout`);
      if (task.retryPolicy.maxRetries < 0) errors.push(`Task ${task.taskId} has invalid retry count`);
    }

    return { valid: errors.length === 0, errors };
  }

  // --- Task Enrichment ---

  private enrichTasksWithVerification(tasks: readonly PlanTask[], goal: Goal): PlanTask[] {
    return tasks.map(task => {
      if (task.type === 'ACTION' && !task.verificationPolicy) {
        return {
          ...task,
          verificationPolicy: {
            strategies: ['STATE_CHECK'] as const,
            required: true,
            timeout: 10_000,
            successCriteria: goal.successCriteria,
          },
        };
      }
      if (task.type === 'INFORMATION_GATHER' && task.requiredEvidence.length > 0 && !task.verificationPolicy) {
        return {
          ...task,
          verificationPolicy: {
            strategies: ['SOURCE_CHECK'] as const,
            required: true,
            timeout: 5_000,
            successCriteria: ['Evidence retrieved from at least one source'],
          },
        };
      }
      return task;
    });
  }

  private identifyApprovalRequirements(tasks: readonly PlanTask[]): ApprovalRequirement[] {
    const reqs: ApprovalRequirement[] = [];
    for (const task of tasks) {
      if (task.risk === 'HIGH' || task.risk === 'CRITICAL') {
        reqs.push({
          taskId: task.taskId,
          reason: `High-risk action: ${task.title}`,
          risk: task.risk,
          actionDescription: task.description,
          reversible: task.reversibility === 'REVERSIBLE',
        });
      }
      if (task.autonomyPolicy === 'HIGH_IMPACT_ACTION' || task.autonomyPolicy === 'IRREVERSIBLE_ACTION') {
        reqs.push({
          taskId: task.taskId,
          reason: `Requires explicit approval: ${task.autonomyPolicy}`,
          risk: task.risk,
          actionDescription: task.description,
          reversible: task.reversibility === 'REVERSIBLE',
        });
      }
    }
    return reqs;
  }

  private buildRollbackPlan(tasks: readonly PlanTask[]): readonly ExecutionPlan['rollbackPlan'][number][] {
    const rollbackSteps: ExecutionPlan['rollbackPlan'][number][] = [];
    for (const task of tasks) {
      if (task.type === 'ACTION' && task.reversibility !== 'IRREVERSIBLE') {
        rollbackSteps.push({
          taskId: task.taskId,
          action: `Rollback: ${task.title}`,
          target: task.inputs?.target as string || 'unknown',
        });
      }
    }
    return rollbackSteps;
  }

  private collectEvidenceRequirements(tasks: readonly PlanTask[]): readonly ExecutionPlan['requiredEvidence'][number][] {
    const reqs: ExecutionPlan['requiredEvidence'][number][] = [];
    for (const task of tasks) {
      for (const req of task.requiredEvidence) {
        if (!reqs.some(r => r.description === req.description)) {
          reqs.push(req);
        }
      }
    }
    return reqs;
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }
}
