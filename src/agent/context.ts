// ============================================================================
// MYRAA Context Manager — Conversation continuity, goal context, long-task context
// ============================================================================

import type { Goal, StructuredIntent, AgentEvent } from './contracts';
import { nowISO } from './contracts';

// ============================================================================
// Context Manager
// ============================================================================

export class ContextManager {
  private activeGoals: Map<string, Goal> = new Map(); // conversationId → active goal
  private goalContext: Map<string, GoalContext> = new Map(); // goalId → context
  private recentInteractions: Interaction[] = [];

  // --- Active Goal Tracking ---

  setActiveGoal(conversationId: string, goal: Goal): void {
    this.activeGoals.set(conversationId, goal);
  }

  getActiveGoal(conversationId: string): Goal | undefined {
    return this.activeGoals.get(conversationId);
  }

  clearActiveGoal(conversationId: string): void {
    this.activeGoals.delete(conversationId);
  }

  // --- Goal Context ---

  setGoalContext(goalId: string, context: GoalContext): void {
    this.goalContext.set(goalId, context);
  }

  getGoalContext(goalId: string): GoalContext | undefined {
    return this.goalContext.get(goalId);
  }

  updateGoalContext(goalId: string, update: Partial<GoalContext>): void {
    const existing = this.goalContext.get(goalId);
    if (existing) {
      this.goalContext.set(goalId, { ...existing, ...update });
    }
  }

  // --- Follow-up Detection ---

  isFollowUp(conversationId: string, newRequest: string): boolean {
    const activeGoal = this.activeGoals.get(conversationId);
    if (!activeGoal) return false;

    // Check if the new request references the active goal
    const lower = newRequest.toLowerCase();
    const goalWords = activeGoal.userRequest.toLowerCase().split(/\s+/);
    const overlap = goalWords.filter(w => w.length > 3 && lower.includes(w));

    // If significant overlap, likely a follow-up
    return overlap.length >= 2 || /\b(it|that|this|those|them|also|what about|how about)\b/.test(lower);
  }

  buildFollowUpContext(conversationId: string, newRequest: string): {
    parentGoalId: string;
    inheritedContext: string[];
    continuationHint: string;
  } | null {
    const activeGoal = this.activeGoals.get(conversationId);
    if (!activeGoal) return null;

    return {
      parentGoalId: activeGoal.id,
      inheritedContext: [
        `Original request: ${activeGoal.userRequest}`,
        `Objective: ${activeGoal.objective}`,
        `Status: ${activeGoal.status}`,
      ],
      continuationHint: `User is following up on: "${activeGoal.userRequest}"`,
    };
  }

  // --- Interaction History ---

  recordInteraction(interaction: Interaction): void {
    this.recentInteractions.push(interaction);
    // Keep last 20 interactions
    if (this.recentInteractions.length > 20) {
      this.recentInteractions = this.recentInteractions.slice(-20);
    }
  }

  getRecentInteractions(limit = 20): Interaction[] {
    return this.recentInteractions.slice(-limit);
  }

  // --- Intent Context ---

  buildIntentContext(goal: Goal): string {
    const parts: string[] = [];
    parts.push(`User request: ${goal.userRequest}`);
    if (goal.normalizedIntent) {
      parts.push(`Goal type: ${goal.normalizedIntent.goalType}`);
      parts.push(`Complexity: ${goal.normalizedIntent.complexity}`);
      if (goal.normalizedIntent.entities.length > 0) {
        parts.push(`Key entities: ${goal.normalizedIntent.entities.map(e => e.name).join(', ')}`);
      }
      if (goal.normalizedIntent.topics.length > 0) {
        parts.push(`Topics: ${goal.normalizedIntent.topics.join(', ')}`);
      }
    }
    return parts.join('\n');
  }
}

// --- Types ---

export interface GoalContext {
  readonly goalId: string;
  readonly keyEntities: string[];
  readonly keyTopics: string[];
  readonly gatheredEvidence: string[];
  readonly decisions: string[];
  readonly assumptions: string[];
  readonly pendingClarifications: string[];
  readonly parentGoalId?: string;
  readonly childGoalIds: string[];
}

export interface Interaction {
  readonly timestamp: string;
  readonly role: 'USER' | 'SYSTEM';
  readonly content: string;
  readonly goalId?: string;
  readonly planId?: string;
}
