// ============================================================================
// MYRAA Policy Engine — Risk model, approval gates, autonomy policy
// ============================================================================

import type {
  RiskLevel, AutonomyPolicy, PlanTask, Goal, ApprovalRequirement,
  Reversibility, AgentEvent,
} from './contracts';

// ============================================================================
// Policy Engine
// ============================================================================

export class PolicyEngine {
  private eventHandler?: (event: AgentEvent) => void;
  private approvalCallbacks: Map<string, (approved: boolean) => void> = new Map();

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Risk Assessment ---

  assessTaskRisk(task: PlanTask): RiskLevel {
    let risk: RiskLevel = task.risk;

    // Escalate risk for irreversible actions
    if (task.reversibility === 'IRREVERSIBLE') {
      risk = this.escalateRisk(risk);
    }

    // Escalate risk for high autonomy
    if (task.autonomyPolicy === 'HIGH_IMPACT_ACTION' || task.autonomyPolicy === 'IRREVERSIBLE_ACTION') {
      risk = this.escalateRisk(risk);
    }

    // Side effects increase risk
    if (task.sideEffects.length > 0) {
      risk = this.escalateRisk(risk);
    }

    return risk;
  }

  private escalateRisk(current: RiskLevel): RiskLevel {
    const levels: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
    const idx = levels.indexOf(current);
    return levels[Math.min(idx + 1, levels.length - 1)];
  }

  // --- Approval ---

  requiresApproval(task: PlanTask): boolean {
    const risk = this.assessTaskRisk(task);
    return risk === 'HIGH' || risk === 'CRITICAL' ||
           task.autonomyPolicy === 'HIGH_IMPACT_ACTION' ||
           task.autonomyPolicy === 'IRREVERSIBLE_ACTION';
  }

  buildApprovalRequest(task: PlanTask): ApprovalRequirement {
    const risk = this.assessTaskRisk(task);
    return {
      taskId: task.taskId,
      reason: `Risk level: ${risk}. Action: ${task.title}`,
      risk,
      actionDescription: task.description,
      reversible: task.reversibility === 'REVERSIBLE',
    };
  }

  // --- Permission Checks ---

  canExecuteTask(task: PlanTask, approvedTasks: Set<string>): {
    allowed: boolean;
    reason?: string;
  } {
    // Check if approval is required and not granted
    if (this.requiresApproval(task) && !approvedTasks.has(task.taskId)) {
      return { allowed: false, reason: 'Approval required but not yet granted' };
    }

    // Check autonomy policy
    if (task.autonomyPolicy === 'IRREVERSIBLE_ACTION') {
      return { allowed: false, reason: 'Irreversible action requires explicit approval' };
    }

    return { allowed: true };
  }

  // --- Goal-Level Policy ---

  getGoalExecutionPolicy(goal: Goal): AutonomyPolicy {
    // Read-only goals
    if (!goal.normalizedIntent?.requiresAction) return 'READ_ONLY';

    // Use goal's own policy if set
    return goal.executionPolicy;
  }

  // --- Notification Policy ---

  shouldNotifyImportance(risk: RiskLevel): boolean {
    return risk === 'HIGH' || risk === 'CRITICAL';
  }

  // --- Safety Boundaries ---

  isSafeAction(task: PlanTask): boolean {
    const unsafePatterns = [
      /\b(rm\s+-rf|del\s+\/[sSqQ]|format\s+disk|shutdown\s+-f)\b/i,
      /\b(credential|password|secret|api.?key|token)\b/i,
      /\b(execute\s+arbitrary|unrestricted\s+shell|powershell\s+-c)\b/i,
    ];

    const text = `${task.title} ${task.description}`;
    return !unsafePatterns.some(p => p.test(text));
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }
}
