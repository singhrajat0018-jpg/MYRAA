// ============================================================================
// MYRAA Goal Engine — Goal lifecycle, status FSM, CRUD
// ============================================================================

import type {
  Goal, GoalStatus, GoalUpdate, GoalType, RiskLevel, AutonomyPolicy,
  Assumption, AgentEvent, StructuredIntent, TaskComplexity,
} from './contracts';
import { generateAgentId, nowISO, isValidGoalTransition } from './contracts';

// ============================================================================
// Goal Engine
// ============================================================================

export class GoalEngine {
  private goals: Map<string, Goal> = new Map();
  private goalsByConversation: Map<string, string[]> = new Map();
  private eventHandler?: (event: AgentEvent) => void;

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Create ---

  createUserGoal(
    userRequest: string,
    options: {
      conversationId?: string;
      priority?: RiskLevel;
      deadline?: string;
      preferences?: readonly string[];
      metadata?: Record<string, unknown>;
    } = {},
  ): Goal {
    const id = generateAgentId('goal');
    const now = nowISO();
    const goal: Goal = {
      id,
      userRequest,
      conversationId: options.conversationId,
      objective: '',
      constraints: [],
      preferences: options.preferences || [],
      deadline: options.deadline,
      priority: options.priority || 'MEDIUM',
      riskLevel: 'LOW',
      requiredCapabilities: [],
      requiredKnowledge: [],
      successCriteria: [],
      verificationCriteria: [],
      executionPolicy: 'READ_ONLY',
      assumptions: [],
      status: 'RECEIVED',
      createdAt: now,
      updatedAt: now,
      metadata: options.metadata || {},
    };
    this.goals.set(id, goal);
    if (options.conversationId) {
      const list = this.goalsByConversation.get(options.conversationId) || [];
      list.push(id);
      this.goalsByConversation.set(options.conversationId, list);
    }
    this.emit({ type: 'GOAL_CREATED', agentId: 'system', goalId: id, timestamp: now, data: { userRequest } });
    return goal;
  }

  // --- Read ---

  getGoal(id: string): Goal | undefined {
    return this.goals.get(id);
  }

  getGoalsByConversation(conversationId: string): Goal[] {
    const ids = this.goalsByConversation.get(conversationId) || [];
    return ids.map(id => this.goals.get(id)).filter(Boolean) as Goal[];
  }

  getActiveGoals(): Goal[] {
    return Array.from(this.goals.values()).filter(g =>
      !['COMPLETED', 'CANCELLED', 'FAILED'].includes(g.status)
    );
  }

  getAllGoals(): Goal[] {
    return Array.from(this.goals.values());
  }

  // --- Update ---

  updateGoal(id: string, update: GoalUpdate): Goal | null {
    const goal = this.goals.get(id);
    if (!goal) return null;

    // Validate status transition
    if (update.status && update.status !== goal.status) {
      if (!isValidGoalTransition(goal.status, update.status)) {
        throw new Error(`Invalid goal transition: ${goal.status} → ${update.status}`);
      }
    }

    const now = nowISO();
    const updated: Goal = {
      ...goal,
      ...(update.status !== undefined ? { status: update.status } : {}),
      ...(update.error !== undefined ? { error: update.error } : {}),
      ...(update.planId !== undefined ? { planId: update.planId } : {}),
      ...(update.assumptions !== undefined ? { assumptions: update.assumptions } : {}),
      ...(update.metadata !== undefined ? { metadata: { ...goal.metadata, ...update.metadata } } : {}),
      updatedAt: now,
      ...(update.status === 'COMPLETED' ? { completedAt: now } : {}),
    };
    this.goals.set(id, updated);
    this.emit({ type: 'GOAL_UPDATED', agentId: 'system', goalId: id, timestamp: now, data: { status: updated.status } });
    return updated;
  }

  // --- Intent ---

  setIntent(goalId: string, intent: StructuredIntent): Goal | null {
    const goal = this.goals.get(goalId);
    if (!goal) return null;

    const riskLevel = this.inferRiskLevel(intent);
    const executionPolicy = this.inferExecutionPolicy(riskLevel, intent.requiresAction);
    const objective = this.buildObjective(goal.userRequest, intent);

    const updated: Goal = {
      ...goal,
      normalizedIntent: intent,
      objective,
      riskLevel,
      executionPolicy,
      requiredCapabilities: this.inferRequiredCapabilities(intent),
      requiredKnowledge: this.inferRequiredKnowledge(intent),
      updatedAt: nowISO(),
    };
    this.goals.set(goalId, updated);
    this.emit({ type: 'INTENT_PARSED', agentId: 'system', goalId, timestamp: nowISO(), data: { intent } });
    return updated;
  }

  // --- Assumptions ---

  addAssumption(goalId: string, statement: string, confidence: number, source: Assumption['source']): Goal | null {
    const goal = this.goals.get(goalId);
    if (!goal) return null;

    const assumption: Assumption = {
      id: generateAgentId('asm'),
      statement,
      confidence,
      source,
      status: 'ACTIVE',
      createdAt: nowISO(),
    };
    const updated: Goal = {
      ...goal,
      assumptions: [...goal.assumptions, assumption],
      updatedAt: nowISO(),
    };
    this.goals.set(goalId, updated);
    return updated;
  }

  invalidateAssumption(goalId: string, assumptionId: string, reason: string): Goal | null {
    const goal = this.goals.get(goalId);
    if (!goal) return null;

    const assumptions = goal.assumptions.map(a =>
      a.id === assumptionId ? { ...a, status: 'INVALIDATED' as const, invalidatedBy: reason } : a
    );
    const updated: Goal = { ...goal, assumptions, updatedAt: nowISO() };
    this.goals.set(goalId, updated);
    return updated;
  }

  // --- Cancel ---

  cancelGoal(id: string, reason: string): Goal | null {
    return this.updateGoal(id, { status: 'CANCELLED', error: reason });
  }

  // --- Complexity ---

  private inferRiskLevel(intent: StructuredIntent): RiskLevel {
    if (intent.requiresAction) return intent.complexity === 'TRIVIAL' ? 'LOW' : 'MEDIUM';
    if (intent.requiresDecision) return 'MEDIUM';
    if (intent.complexity === 'HIGHLY_COMPLEX') return 'HIGH';
    return 'LOW';
  }

  private inferExecutionPolicy(risk: RiskLevel, requiresAction: boolean): AutonomyPolicy {
    if (!requiresAction) return 'READ_ONLY';
    if (risk === 'LOW') return 'SAFE_ACTION';
    if (risk === 'MEDIUM') return 'MODERATE_ACTION';
    if (risk === 'HIGH') return 'HIGH_IMPACT_ACTION';
    return 'IRREVERSIBLE_ACTION';
  }

  private buildObjective(userRequest: string, intent: StructuredIntent): string {
    const parts: string[] = [];
    if (intent.actions.length > 0) parts.push(intent.actions.join(' + '));
    if (intent.topics.length > 0) parts.push(`regarding ${intent.topics.join(', ')}`);
    if (intent.questions.length > 0) parts.push(`answering: ${intent.questions.join('; ')}`);
    return parts.length > 0 ? parts.join(' ') : userRequest;
  }

  private inferRequiredCapabilities(intent: StructuredIntent): string[] {
    const caps: string[] = [];
    if (intent.requiresExternalData) caps.push('web.search', 'news.search');
    if (intent.requiresAction) caps.push('system.execute');
    if (intent.requiresDecision) caps.push('reasoning.decision');
    return caps;
  }

  private inferRequiredKnowledge(intent: StructuredIntent): string[] {
    return intent.topics.map(t => `topic:${t}`);
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }

  // --- Stats ---

  getStats() {
    const goals = Array.from(this.goals.values());
    const byStatus: Record<string, number> = {};
    for (const g of goals) byStatus[g.status] = (byStatus[g.status] || 0) + 1;
    return { total: goals.length, byStatus };
  }
}
