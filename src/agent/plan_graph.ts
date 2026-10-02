// ============================================================================
// MYRAA Plan Graph — DAG with dependency resolution, parallel groups, cycle detection
// ============================================================================

import type { PlanTask, PlanStatus, ExecutionPlan, PlanBudget } from './contracts';
import { generateAgentId, nowISO, DEFAULT_PLAN_BUDGET } from './contracts';

// ============================================================================
// Plan Graph (DAG)
// ============================================================================

export class PlanGraph {
  private adjacency: Map<string, Set<string>> = new Map(); // taskId → dependents
  private reverseAdj: Map<string, Set<string>> = new Map(); // taskId → dependencies
  private tasks: Map<string, PlanTask> = new Map();

  constructor(tasks?: readonly PlanTask[] | PlanTask[]) {
    if (tasks) {
      for (const task of tasks) this.addTask(task);
    }
  }

  addTask(task: PlanTask): void {
    this.tasks.set(task.taskId, task);
    if (!this.adjacency.has(task.taskId)) this.adjacency.set(task.taskId, new Set());
    if (!this.reverseAdj.has(task.taskId)) this.reverseAdj.set(task.taskId, new Set());

    for (const dep of task.dependencies) {
      if (!this.adjacency.has(dep)) this.adjacency.set(dep, new Set());
      this.adjacency.get(dep)!.add(task.taskId);
      this.reverseAdj.get(task.taskId)!.add(dep);
    }
  }

  removeTask(taskId: string): void {
    const dependents = this.adjacency.get(taskId) || new Set();
    for (const dep of dependents) {
      this.reverseAdj.get(dep)?.delete(taskId);
    }
    for (const [id, deps] of this.reverseAdj) {
      if (deps.has(taskId)) {
        this.adjacency.get(id)?.delete(taskId);
        deps.delete(taskId);
      }
    }
    this.adjacency.delete(taskId);
    this.reverseAdj.delete(taskId);
    this.tasks.delete(taskId);
  }

  getTask(taskId: string): PlanTask | undefined {
    return this.tasks.get(taskId);
  }

  getAllTasks(): PlanTask[] {
    return Array.from(this.tasks.values());
  }

  // --- Dependency Resolution ---

  getDependencies(taskId: string): string[] {
    return Array.from(this.reverseAdj.get(taskId) || []);
  }

  getDependents(taskId: string): string[] {
    return Array.from(this.adjacency.get(taskId) || []);
  }

  areDependenciesSatisfied(taskId: string, completedTasks: Set<string>): boolean {
    const deps = this.reverseAdj.get(taskId) || new Set();
    for (const dep of deps) {
      if (!completedTasks.has(dep)) return false;
    }
    return true;
  }

  // --- Ready Tasks ---

  getReadyTasks(completedTasks: Set<string>, runningTasks: Set<string>): PlanTask[] {
    const ready: PlanTask[] = [];
    for (const [taskId, task] of this.tasks) {
      if (completedTasks.has(taskId) || runningTasks.has(taskId)) continue;
      if (task.status === 'BLOCKED' || task.status === 'CANCELLED' || task.status === 'SKIPPED') continue;
      if (this.areDependenciesSatisfied(taskId, completedTasks)) {
        ready.push(task);
      }
    }
    return ready.sort((a, b) => b.priority - a.priority);
  }

  // --- Parallel Groups ---

  computeParallelGroups(completedTasks: Set<string>): string[][] {
    const groups: string[][] = [];
    const remaining = new Set(this.tasks.keys());

    // Remove completed
    for (const id of completedTasks) remaining.delete(id);

    while (remaining.size > 0) {
      const group: string[] = [];
      for (const taskId of remaining) {
        const deps = this.reverseAdj.get(taskId) || new Set();
        const allDepsComplete = Array.from(deps).every(d => completedTasks.has(d) || group.includes(d));
        if (allDepsComplete) {
          group.push(taskId);
        }
      }
      if (group.length === 0) {
        // Deadlock or cycle
        break;
      }
      groups.push(group);
      for (const id of group) remaining.delete(id);
    }

    return groups;
  }

  // --- Cycle Detection ---

  hasCycle(): boolean {
    const visited = new Set<string>();
    const inStack = new Set<string>();

    const dfs = (node: string): boolean => {
      if (inStack.has(node)) return true;
      if (visited.has(node)) return false;
      visited.add(node);
      inStack.add(node);
      for (const dep of this.adjacency.get(node) || []) {
        if (dfs(dep)) return true;
      }
      inStack.delete(node);
      return false;
    };

    for (const nodeId of this.tasks.keys()) {
      if (dfs(nodeId)) return true;
    }
    return false;
  }

  // --- Deadlock Detection ---

  detectDeadlocks(completedTasks: Set<string>): string[] {
    const blocked: string[] = [];
    for (const [taskId, task] of this.tasks) {
      if (completedTasks.has(taskId) || task.status !== 'PENDING') continue;
      const deps = this.reverseAdj.get(taskId) || new Set();
      const unfulfilled = Array.from(deps).filter(d => !completedTasks.has(d));
      // Check if any unfulfilled dep is itself permanently blocked
      for (const uf of unfulfilled) {
        const ufTask = this.tasks.get(uf);
        if (ufTask?.status === 'FAILED' || ufTask?.status === 'CANCELLED') {
          blocked.push(taskId);
          break;
        }
      }
    }
    return blocked;
  }

  // --- Topological Sort ---

  topologicalSort(): string[] {
    const inDegree = new Map<string, number>();
    for (const [id] of this.tasks) inDegree.set(id, 0);
    for (const [, deps] of this.reverseAdj) {
      for (const dep of deps) {
        inDegree.set(dep, (inDegree.get(dep) || 0));
      }
    }
    for (const [id, task] of this.tasks) {
      for (const dep of task.dependencies) {
        inDegree.set(id, (inDegree.get(id) || 0) + 1);
      }
    }

    const queue: string[] = [];
    for (const [id, degree] of inDegree) {
      if (degree === 0) queue.push(id);
    }

    const sorted: string[] = [];
    while (queue.length > 0) {
      const node = queue.shift()!;
      sorted.push(node);
      for (const dependent of this.adjacency.get(node) || []) {
        const newDegree = (inDegree.get(dependent) || 1) - 1;
        inDegree.set(dependent, newDegree);
        if (newDegree === 0) queue.push(dependent);
      }
    }

    return sorted;
  }

  // --- Validation ---

  validate(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    if (this.hasCycle()) errors.push('Plan contains circular dependencies');
    for (const [taskId, task] of this.tasks) {
      for (const dep of task.dependencies) {
        if (!this.tasks.has(dep)) {
          errors.push(`Task ${taskId} depends on non-existent task ${dep}`);
        }
      }
    }
    return { valid: errors.length === 0, errors };
  }

  // --- Build Execution Plan ---

  buildPlan(goalId: string, strategy: string, budget?: Partial<PlanBudget>): ExecutionPlan {
    const tasks = this.topologicalSort().map(id => this.tasks.get(id)!).filter(Boolean);
    const parallelGroups = this.computeParallelGroups(new Set());
    const maxRisk = this.computeMaxRisk(tasks);

    return {
      planId: generateAgentId('plan'),
      goalId,
      version: 1,
      strategy,
      tasks,
      parallelGroups,
      requiredEvidence: [],
      riskSummary: maxRisk,
      approvalRequirements: [],
      estimatedTimeMs: tasks.length * 5000,
      successCriteria: [],
      verificationPlan: [],
      rollbackPlan: [],
      status: 'DRAFT',
      createdAt: nowISO(),
      updatedAt: nowISO(),
      budget: { ...DEFAULT_PLAN_BUDGET, ...budget },
    };
  }

  private computeMaxRisk(tasks: PlanTask[]): PlanTask['risk'] {
    const riskOrder = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;
    let max = 'LOW';
    for (const t of tasks) {
      if (riskOrder.indexOf(t.risk) > riskOrder.indexOf(max as any)) {
        max = t.risk;
      }
    }
    return max as PlanTask['risk'];
  }
}
