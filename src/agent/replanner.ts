// ============================================================================
// MYRAA Replanner — Replan on failure, stale evidence, user-change
// ============================================================================

import type {
  ExecutionPlan, PlanTask, Goal, AgentEvent, PlanStatus,
} from './contracts';
import { generateAgentId, nowISO } from './contracts';
import { PlanGraph } from './plan_graph';

// ============================================================================
// Replanner
// ============================================================================

export class Replanner {
  private replanHistory: Map<string, { planId: string; reason: string; timestamp: string }[]> = new Map();
  private eventHandler?: (event: AgentEvent) => void;

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Replan ---

  replan(
    currentPlan: ExecutionPlan,
    reason: string,
    completedTasks: Set<string>,
    failedTasks: Set<string>,
  ): ExecutionPlan | null {
    // Check replan limit
    const history = this.replanHistory.get(currentPlan.goalId) || [];
    if (history.length >= currentPlan.budget.maxReplans) {
      return null; // Cannot replan further
    }

    this.emit({
      type: 'REPLAN_TRIGGERED',
      agentId: 'system',
      goalId: currentPlan.goalId,
      planId: currentPlan.planId,
      timestamp: nowISO(),
      data: { reason, completedCount: completedTasks.size, failedCount: failedTasks.size },
    });

    // Strategy: remove failed tasks and their dependents, keep completed
    const remainingTasks = currentPlan.tasks.filter(task => {
      if (completedTasks.has(task.taskId)) return false; // Already done
      if (failedTasks.has(task.taskId)) return false; // Failed
      // Check if any dependency failed
      const hasFailedDep = task.dependencies.some(dep => failedTasks.has(dep));
      if (hasFailedDep) return false;
      return true;
    });

    if (remainingTasks.length === 0) {
      return null; // Nothing to replan
    }

    // Remove references to completed/failed tasks from dependencies
    const cleanedTasks = remainingTasks.map(task => ({
      ...task,
      dependencies: task.dependencies.filter(dep =>
        !completedTasks.has(dep) && !failedTasks.has(dep)
      ),
      status: 'PENDING' as const,
      retryCount: 0,
    }));

    // Build new plan
    const graph = new PlanGraph(cleanedTasks);
    const validation = graph.validate();
    if (!validation.valid) return null;

    const newPlan: ExecutionPlan = {
      ...currentPlan,
      planId: generateAgentId('plan'),
      version: currentPlan.version + 1,
      parentPlanId: currentPlan.planId,
      replanReason: reason,
      tasks: cleanedTasks,
      parallelGroups: graph.computeParallelGroups(completedTasks),
      status: 'DRAFT' as PlanStatus,
      createdAt: nowISO(),
      updatedAt: nowISO(),
    };

    // Record replan
    history.push({ planId: newPlan.planId, reason, timestamp: nowISO() });
    this.replanHistory.set(currentPlan.goalId, history);

    this.emit({
      type: 'PLAN_REPLANNED',
      agentId: 'system',
      goalId: currentPlan.goalId,
      planId: newPlan.planId,
      timestamp: nowISO(),
      data: { originalPlanId: currentPlan.planId, reason, version: newPlan.version },
    });

    return newPlan;
  }

  // --- Stale Plan Detection ---

  isPlanStale(plan: ExecutionPlan, worldStateAge: number): boolean {
    // If world state is newer than plan creation, plan may be stale
    const planAge = Date.now() - new Date(plan.createdAt).getTime();
    return worldStateAge < planAge * 0.5; // World state refreshed more recently than half plan age
  }

  shouldReplanDueToStaleness(plan: ExecutionPlan, worldStateAge: number): boolean {
    if (!this.isPlanStale(plan, worldStateAge)) return false;
    // Check if any task depends on external data
    return plan.tasks.some(t =>
      t.requiredEvidence.some(e => e.type === 'WORLD_INTELLIGENCE')
    );
  }

  // --- Replan Reasons ---

  static REASONS = {
    TASK_FAILED: 'Task execution failed',
    PROVIDER_DOWN: 'Primary provider unavailable',
    EVIDENCE_STALE: 'Evidence became stale',
    EVIDENCE_CONFLICT: 'Conflicting evidence detected',
    USER_CHANGED_MIND: 'User modified requirements',
    VERIFICATION_FAILED: 'Verification check failed',
    BUDGET_EXCEEDED: 'Budget limit reached',
    TIMEOUT: 'Task timed out',
    PERMISSION_DENIED: 'Permission was denied',
  } as const;

  getReplanHistory(goalId: string): readonly { planId: string; reason: string; timestamp: string }[] {
    return this.replanHistory.get(goalId) || [];
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }
}
