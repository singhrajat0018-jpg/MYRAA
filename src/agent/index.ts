// ============================================================================
// MYRAA Reasoning Engine — Main orchestrator: Observe→Understand→Decompose→Plan→Gather→Reason→Act→Verify→Learn
// ============================================================================

import type {
  Goal, GoalStatus, StructuredIntent, ExecutionPlan, PlanTask, TaskResult,
  FinalTaskResult, DecisionResult, GatheredEvidence, VerificationResult,
  AgentEvent, AgentEventType, PlanBudget, RiskLevel, EvidenceSufficiency,
} from './contracts';
import { generateAgentId, nowISO } from './contracts';
import { GoalEngine } from './goal';
import { IntentUnderstanding } from './intent';
import { StrategySelector } from './strategy';
import { PlanBuilder } from './planner';
import { PlanGraph } from './plan_graph';
import { EvidenceEngine } from './evidence';
import { DecisionEngine } from './decision';
import { ExecutionEngine } from './execution';
import { VerificationEngine } from './verifier';
import { Replanner } from './replanner';
import { PolicyEngine } from './policy';
import { ExperienceEngine } from './experience';
import { ContextManager, type Interaction, type GoalContext } from './context';
import { AgentPersistence } from './persistence';

// ============================================================================
// Reasoning Engine
// ============================================================================

export class ReasoningEngine {
  readonly goalEngine: GoalEngine;
  readonly intentEngine: IntentUnderstanding;
  readonly strategySelector: StrategySelector;
  readonly planBuilder: PlanBuilder;
  readonly evidenceEngine: EvidenceEngine;
  readonly decisionEngine: DecisionEngine;
  readonly executionEngine: ExecutionEngine;
  readonly verificationEngine: VerificationEngine;
  readonly replanner: Replanner;
  readonly policyEngine: PolicyEngine;
  readonly experienceEngine: ExperienceEngine;
  readonly contextManager: ContextManager;
  readonly persistence: AgentPersistence;

  private eventLog: AgentEvent[] = [];
  private eventHandlers: ((event: AgentEvent) => void)[] = [];
  private activeGoals: Map<string, Goal> = new Map();
  private activePlans: Map<string, ExecutionPlan> = new Map();
  private approvedTasks: Map<string, Set<string>> = new Map(); // planId → approved taskIds
  private pendingApprovals: Map<string, { planId: string; taskId: string; reason: string }> = new Map();

  constructor(persistenceDir?: string) {
    this.goalEngine = new GoalEngine();
    this.intentEngine = new IntentUnderstanding();
    this.strategySelector = new StrategySelector();
    this.planBuilder = new PlanBuilder();
    this.evidenceEngine = new EvidenceEngine();
    this.decisionEngine = new DecisionEngine();
    this.executionEngine = new ExecutionEngine();
    this.verificationEngine = new VerificationEngine();
    this.replanner = new Replanner();
    this.policyEngine = new PolicyEngine();
    this.experienceEngine = new ExperienceEngine();
    this.contextManager = new ContextManager();
    this.persistence = new AgentPersistence(persistenceDir);

    // Wire events
    const eventForwarder = (event: AgentEvent) => this.recordEvent(event);
    this.goalEngine.setEventHandler(eventForwarder);
    this.planBuilder.setEventHandler(eventForwarder);
    this.evidenceEngine.setEventHandler(eventForwarder);
    this.decisionEngine.setEventHandler(eventForwarder);
    this.executionEngine.setEventHandler(eventForwarder);
    this.verificationEngine.setEventHandler(eventForwarder);
    this.replanner.setEventHandler(eventForwarder);
    this.policyEngine.setEventHandler(eventForwarder);
    this.experienceEngine.setEventHandler(eventForwarder);
    this.persistence.setEventHandler(eventForwarder);
  }

  // --- Main Entry: Process User Request ---

  async processRequest(
    userRequest: string,
    options: {
      conversationId?: string;
      conversationHistory?: Interaction[];
      availableCapabilities?: string[];
    } = {},
  ): Promise<FinalTaskResult> {
    const startTime = Date.now();
    const conversationId = options.conversationId || generateAgentId('conv');

    // Record interaction
    this.contextManager.recordInteraction({
      timestamp: nowISO(),
      role: 'USER',
      content: userRequest,
    });

    // Check for follow-up
    const followUp = this.contextManager.isFollowUp(conversationId, userRequest);
    if (followUp) {
      const followUpContext = this.contextManager.buildFollowUpContext(conversationId, userRequest);
      if (followUpContext) {
        // Continue existing goal context
        const parentGoal = this.goalEngine.getGoal(followUpContext.parentGoalId);
        if (parentGoal && parentGoal.status !== 'COMPLETED' && parentGoal.status !== 'CANCELLED') {
          return this.continueGoal(parentGoal, userRequest);
        }
      }
    }

    // 1. UNDERSTAND: Classify intent
    const intent = this.intentEngine.classifyIntent(userRequest);

    // 2. CREATE GOAL
    const goal = this.goalEngine.createUserGoal(userRequest, {
      conversationId,
      priority: intent.complexity === 'TRIVIAL' ? 'LOW' : intent.complexity === 'SIMPLE' ? 'LOW' : 'MEDIUM',
    });

    // Set intent on goal
    this.goalEngine.setIntent(goal.id, intent);
    this.activeGoals.set(goal.id, goal);

    // Set context
    this.contextManager.setActiveGoal(conversationId, goal);

    // Transition to UNDERSTANDING
    this.goalEngine.updateGoal(goal.id, { status: 'UNDERSTANDING' });

    // Fast path check
    const classifier = this.strategySelector.classifyTask(goal);
    if (classifier === 'DIRECT_ANSWER') {
      return this.handleDirectAnswer(goal, intent);
    }

    // 3. DECOMPOSE + PLAN
    this.goalEngine.updateGoal(goal.id, { status: 'DECOMPOSING' });

    let plan: ExecutionPlan;
    try {
      plan = this.planBuilder.buildPlan(goal);
      this.activePlans.set(plan.planId, plan);
      this.goalEngine.updateGoal(goal.id, { status: 'PLANNING', planId: plan.planId });
    } catch (err) {
      this.goalEngine.updateGoal(goal.id, { status: 'FAILED', error: String(err) });
      return this.buildFinalResult(goal, 'FAILED', `Planning failed: ${err}`, Date.now() - startTime);
    }

    // 4. VALIDATE
    const validation = this.planBuilder.validatePlan(plan);
    if (!validation.valid) {
      this.goalEngine.updateGoal(goal.id, { status: 'FAILED', error: validation.errors.join('; ') });
      return this.buildFinalResult(goal, 'FAILED', `Plan validation failed: ${validation.errors.join('; ')}`, Date.now() - startTime);
    }

    // 5. CHECK APPROVALS
    const highRiskTasks = plan.tasks.filter(t => this.policyEngine.requiresApproval(t));
    if (highRiskTasks.length > 0) {
      this.goalEngine.updateGoal(goal.id, { status: 'WAITING_FOR_APPROVAL' });
      for (const task of highRiskTasks) {
        const approval = this.policyEngine.buildApprovalRequest(task);
        this.pendingApprovals.set(task.taskId, { planId: plan.planId, taskId: task.taskId, reason: approval.reason });
        this.recordEvent({
          type: 'APPROVAL_REQUIRED',
          agentId: 'system',
          goalId: goal.id,
          planId: plan.planId,
          taskId: task.taskId,
          timestamp: nowISO(),
          data: { reason: approval.reason, risk: approval.risk },
        });
      }
      return this.buildFinalResult(goal, 'BLOCKED', 'Waiting for approval on high-risk actions', Date.now() - startTime);
    }

    // 6. EXECUTE
    this.goalEngine.updateGoal(goal.id, { status: 'EXECUTING' });
    this.executionEngine.startPlan(plan);

    const maxIterations = plan.budget.maxSteps;
    let iteration = 0;

    while (iteration < maxIterations) {
      iteration++;

      // Execute ready tasks
      const execResult = await this.executionEngine.executeReadyTasks(plan.planId);

      // Check if plan is complete
      const allTasks = plan.tasks;
      const completedCount = execResult.completed.length;
      const failedCount = execResult.failed.length;

      if (completedCount + failedCount >= allTasks.length) {
        break; // All tasks done
      }

      // Check for failures requiring replan
      if (execResult.failed.length > 0) {
        const failedTaskIds = new Set(execResult.failed);
        const completedTaskIds = new Set(execResult.completed);

        // Check replan limit
        const budgetStatus = this.executionEngine.getBudgetStatus(plan.planId);
        if (budgetStatus && budgetStatus.replansUsed < plan.budget.maxReplans) {
          const newPlan = this.replanner.replan(plan, 'Task execution failed', completedTaskIds, failedTaskIds);
          if (newPlan) {
            this.activePlans.set(newPlan.planId, newPlan);
            this.executionEngine.startPlan(newPlan);
            plan = newPlan;
            continue;
          }
        }

        // Cannot replan - check partial success
        if (completedCount > 0) {
          break;
        }
      }

      // Check budget
      const budget = this.executionEngine.getBudgetStatus(plan.planId);
      if (budget && !budget.withinBudget) {
        break;
      }

      // If no progress, break
      if (execResult.completed.length === 0 && execResult.failed.length === 0 && execResult.awaitingApproval.length === 0) {
        break;
      }
    }

    // 7. ASSEMBLE RESULT
    const finalStatus = this.determineFinalStatus(plan);
    const result = this.buildFinalResult(goal, finalStatus, '', Date.now() - startTime);

    // 8. LEARN: Store experience
    this.storeExperience(goal, plan);

    return result;
  }

  // --- Fast Path: Direct Answer ---

  private async handleDirectAnswer(goal: Goal, intent: StructuredIntent): Promise<FinalTaskResult> {
    this.goalEngine.updateGoal(goal.id, { status: 'EXECUTING' });

    // For simple questions, provide a direct response
    const answer = `Based on my analysis: ${goal.userRequest}`;

    this.goalEngine.updateGoal(goal.id, { status: 'COMPLETED' });

    return {
      status: 'COMPLETED',
      goalId: goal.id,
      summary: `Direct answer for: ${goal.userRequest}`,
      answer,
      evidence: [],
      actionsPerformed: [],
      verification: [],
      uncertainties: [],
      followUpRequired: [],
      duration: 0,
      timestamp: nowISO(),
    };
  }

  // --- Continue Existing Goal (Follow-up) ---

  private async continueGoal(goal: Goal, followUpRequest: string): Promise<FinalTaskResult> {
    const context = this.contextManager.getGoalContext(goal.id);
    // For now, treat follow-up as a continuation of the same goal
    return this.buildFinalResult(goal, 'COMPLETED', `Follow-up processed: ${followUpRequest}`, 0);
  }

  // --- Approval ---

  approveTask(planId: string, taskId: string): boolean {
    const plan = this.activePlans.get(planId);
    if (!plan) return false;

    const approved = this.approvedTasks.get(planId) || new Set();
    approved.add(taskId);
    this.approvedTasks.set(planId, approved);
    this.pendingApprovals.delete(taskId);

    this.recordEvent({
      type: 'APPROVAL_GRANTED',
      agentId: 'system',
      planId,
      taskId,
      timestamp: nowISO(),
      data: {},
    });

    return true;
  }

  denyTask(planId: string, taskId: string, reason: string): boolean {
    this.pendingApprovals.delete(taskId);
    this.executionEngine.denyTask(planId, taskId, reason);
    return true;
  }

  // --- Cancel ---

  cancelGoal(goalId: string): boolean {
    const goal = this.goalEngine.getGoal(goalId);
    if (!goal) return false;

    this.goalEngine.cancelGoal(goalId, 'User cancelled');

    // Cancel associated plans
    for (const [planId, plan] of this.activePlans) {
      if (plan.goalId === goalId) {
        this.executionEngine.cancelPlan(planId);
      }
    }

    this.activeGoals.delete(goalId);
    return true;
  }

  // --- Query ---

  getGoal(goalId: string): Goal | undefined {
    return this.goalEngine.getGoal(goalId);
  }

  getPlan(planId: string): ExecutionPlan | undefined {
    return this.activePlans.get(planId) || this.executionEngine.getPlan(planId);
  }

  getEventLog(goalId?: string): AgentEvent[] {
    if (goalId) return this.eventLog.filter(e => e.goalId === goalId);
    return [...this.eventLog];
  }

  getPendingApprovals(): { planId: string; taskId: string; reason: string }[] {
    return Array.from(this.pendingApprovals.values());
  }

  // --- Stats ---

  getStats() {
    return {
      goals: this.goalEngine.getStats(),
      plans: this.executionEngine.getStats(),
      evidence: this.evidenceEngine.getStats(),
      experience: this.experienceEngine.getStats(),
      events: this.eventLog.length,
      pendingApprovals: this.pendingApprovals.size,
    };
  }

  // --- Helpers ---

  private determineFinalStatus(plan: ExecutionPlan): FinalTaskResult['status'] {
    const completed = plan.tasks.filter(t => t.status === 'COMPLETED').length;
    const total = plan.tasks.length;
    if (completed === total) return 'COMPLETED';
    if (completed > 0) return 'PARTIALLY_COMPLETED';
    return 'FAILED';
  }

  private buildFinalResult(goal: Goal, status: FinalTaskResult['status'], summary: string, duration: number): FinalTaskResult {
    return {
      status,
      goalId: goal.id,
      planId: goal.planId,
      summary: summary || `Goal: ${goal.objective || goal.userRequest}`,
      evidence: this.evidenceEngine.getAllEvidence(),
      actionsPerformed: [],
      verification: [],
      uncertainties: [],
      followUpRequired: [],
      duration,
      timestamp: nowISO(),
    };
  }

  private storeExperience(goal: Goal, plan: ExecutionPlan): void {
    try {
      const success = plan.tasks.every(t => t.status === 'COMPLETED');
      this.experienceEngine.recordExperience({
        taskType: plan.tasks[0]?.type || 'INFORMATION_GATHER',
        goalType: goal.normalizedIntent?.goalType || 'QUESTION',
        goalPattern: goal.userRequest,
        successfulPlan: plan.tasks.filter(t => t.status === 'COMPLETED').map(t => t.title),
        failedApproaches: plan.tasks.filter(t => t.status === 'FAILED').map(t => t.title),
        toolsUsed: plan.tasks.flatMap(t => t.requiredCapabilities),
        providersUsed: [],
        verificationOutcome: success ? 'VERIFIED' : 'FAILED',
        duration: plan.tasks.reduce((s, t) => s + (t.completedAt && t.startedAt ? new Date(t.completedAt).getTime() - new Date(t.startedAt).getTime() : 0), 0),
        metadata: { planVersion: plan.version },
      });
    } catch {
      // Best effort experience storage
    }
  }

  private recordEvent(event: AgentEvent): void {
    this.eventLog.push(event);
    // Keep last 500 events
    if (this.eventLog.length > 500) {
      this.eventLog = this.eventLog.slice(-500);
    }
    // Notify handlers
    for (const handler of this.eventHandlers) {
      try { handler(event); } catch { /* ignore */ }
    }
  }

  onEvent(handler: (event: AgentEvent) => void): void {
    this.eventHandlers.push(handler);
  }

  // --- Persistence ---

  async save(): Promise<void> {
    const goals = Array.from(this.activeGoals.values());
    const plans = Array.from(this.activePlans.values());
    const experiences = this.experienceEngine.getAllExperiences();
    await Promise.all([
      this.persistence.saveGoals(goals),
      this.persistence.savePlans(plans),
      this.persistence.saveExperience(experiences),
    ]);
  }

  async recover(): Promise<{ goals: Goal[]; plans: ExecutionPlan[] }> {
    const plans = await this.persistence.recoverActivePlans();
    const goals = await this.persistence.loadGoals();
    const experiences = await this.persistence.loadExperience();
    for (const exp of experiences) {
      this.experienceEngine.recordExperience(exp);
    }
    return { goals, plans };
  }
}

// ============================================================================
// Re-exports
// ============================================================================

export { GoalEngine } from './goal';
export { IntentUnderstanding } from './intent';
export { StrategySelector } from './strategy';
export { PlanBuilder } from './planner';
export { PlanGraph } from './plan_graph';
export { EvidenceEngine } from './evidence';
export { DecisionEngine } from './decision';
export { ExecutionEngine } from './execution';
export { VerificationEngine } from './verifier';
export { Replanner } from './replanner';
export { PolicyEngine } from './policy';
export { ExperienceEngine } from './experience';
export { ContextManager } from './context';
export { AgentPersistence } from './persistence';
export * from './contracts';
