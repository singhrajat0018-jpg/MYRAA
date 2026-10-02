// ============================================================================
// MYRAA Experience Memory — Task experience, strategy reuse, user corrections
// ============================================================================

import type {
  TaskExperience, TaskType, GoalType, VerificationStatus, AgentEvent,
} from './contracts';
import { generateAgentId, nowISO } from './contracts';

// ============================================================================
// Experience Engine
// ============================================================================

export class ExperienceEngine {
  private experiences: Map<string, TaskExperience> = new Map();
  private experiencesByType: Map<string, string[]> = new Map();
  private eventHandler?: (event: AgentEvent) => void;

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Store Experience ---

  recordExperience(exp: Omit<TaskExperience, 'id' | 'timestamp' | 'successRate' | 'usageCount'>): TaskExperience {
    const full: TaskExperience = {
      ...exp,
      id: generateAgentId('exp'),
      timestamp: nowISO(),
      successRate: 1.0,
      usageCount: 1,
    };
    this.experiences.set(full.id, full);

    const key = `${exp.goalType}:${exp.taskType}`;
    const list = this.experiencesByType.get(key) || [];
    list.push(full.id);
    this.experiencesByType.set(key, list);

    return full;
  }

  // --- Retrieve Experience ---

  findRelevantExperience(goalType: GoalType, taskType: TaskType): TaskExperience | undefined {
    const key = `${goalType}:${taskType}`;
    const ids = this.experiencesByType.get(key) || [];
    const experiences = ids.map(id => this.experiences.get(id)).filter(Boolean) as TaskExperience[];
    if (experiences.length === 0) return undefined;

    // Sort by success rate and recency
    return experiences.sort((a, b) => {
      const scoreA = a.successRate * 0.7 + (1 - a.usageCount / 100) * 0.3;
      const scoreB = b.successRate * 0.7 + (1 - b.usageCount / 100) * 0.3;
      return scoreB - scoreA;
    })[0];
  }

  findSimilarExperience(goalPattern: string): TaskExperience | undefined {
    const patterns = Array.from(this.experiences.values());
    if (patterns.length === 0) return undefined;

    // Simple similarity: find experience with most matching words
    const goalWords = new Set(goalPattern.toLowerCase().split(/\s+/));
    let bestMatch: TaskExperience | null = null;
    let bestScore = 0;

    for (const exp of patterns) {
      const expWords = new Set(exp.goalPattern.toLowerCase().split(/\s+/));
      let overlap = 0;
      for (const w of goalWords) if (expWords.has(w)) overlap++;
      const score = overlap / Math.max(goalWords.size, expWords.size);
      if (score > bestScore) {
        bestScore = score;
        bestMatch = exp;
      }
    }

    return bestScore > 0.3 ? bestMatch! : undefined;
  }

  // --- Update Experience ---

  recordOutcome(experienceId: string, success: boolean, userCorrection?: string): void {
    const exp = this.experiences.get(experienceId);
    if (!exp) return;

    const total = exp.usageCount + 1;
    const successes = success ? exp.usageCount * exp.successRate + 1 : exp.usageCount * exp.successRate;

    const updated: TaskExperience = {
      ...exp,
      successRate: successes / total,
      usageCount: total,
      userCorrection: userCorrection || exp.userCorrection,
      timestamp: nowISO(),
    };
    this.experiences.set(experienceId, updated);
  }

  recordUserCorrection(experienceId: string, correction: string): void {
    const exp = this.experiences.get(experienceId);
    if (!exp) return;

    this.experiences.set(experienceId, {
      ...exp,
      userCorrection: correction,
      successRate: Math.max(0, exp.successRate - 0.1),
      timestamp: nowISO(),
    });
  }

  // --- Suggest from Experience ---

  suggestStrategy(goalType: GoalType, taskType: TaskType): {
    suggestedCapabilities: string[];
    suggestedApproach: string[];
    warningPoints: string[];
  } {
    const exp = this.findRelevantExperience(goalType, taskType);
    if (!exp) return { suggestedCapabilities: [], suggestedApproach: [], warningPoints: [] };

    return {
      suggestedCapabilities: [...exp.toolsUsed],
      suggestedApproach: [...exp.successfulPlan],
      warningPoints: [...exp.failedApproaches],
    };
  }

  // --- Query ---

  getExperience(id: string): TaskExperience | undefined {
    return this.experiences.get(id);
  }

  getAllExperiences(): TaskExperience[] {
    return Array.from(this.experiences.values());
  }

  getHighConfidenceExperiences(minSuccessRate = 0.7): TaskExperience[] {
    return Array.from(this.experiences.values()).filter(e => e.successRate >= minSuccessRate);
  }

  private emit(event: AgentEvent): void {
    if (this.eventHandler) {
      try { this.eventHandler(event); } catch { /* ignore */ }
    }
  }

  getStats() {
    const exps = Array.from(this.experiences.values());
    return {
      total: exps.length,
      avgSuccessRate: exps.length > 0 ? exps.reduce((s, e) => s + e.successRate, 0) / exps.length : 0,
      highConfidence: exps.filter(e => e.successRate >= 0.7).length,
      withCorrections: exps.filter(e => e.userCorrection).length,
    };
  }
}
