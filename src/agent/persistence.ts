// ============================================================================
// MYRAA Persistence — Plan/goal state persistence, recovery, stale detection
// ============================================================================

import type { Goal, ExecutionPlan, TaskExperience, AgentEvent } from './contracts';
import { nowISO } from './contracts';
import * as fs from 'fs';
import * as path from 'path';

// ============================================================================
// Persistence Engine
// ============================================================================

export class AgentPersistence {
  private dataDir: string;
  private eventHandler?: (event: AgentEvent) => void;

  constructor(dataDir?: string) {
    this.dataDir = dataDir || path.join(process.env.HOME || process.env.USERPROFILE || '.', '.myraa', 'agent');
  }

  setEventHandler(handler: (event: AgentEvent) => void): void {
    this.eventHandler = handler;
  }

  // --- Directory ---

  ensureDataDir(): void {
    try {
      if (!fs.existsSync(this.dataDir)) {
        fs.mkdirSync(this.dataDir, { recursive: true });
      }
    } catch {
      // Best effort
    }
  }

  // --- Goals ---

  async saveGoals(goals: Goal[]): Promise<void> {
    this.ensureDataDir();
    const filePath = path.join(this.dataDir, 'goals.json');
    try {
      fs.writeFileSync(filePath, JSON.stringify(goals, null, 2), 'utf8');
    } catch (err) {
      console.error('[AgentPersistence] Failed to save goals:', err);
    }
  }

  async loadGoals(): Promise<Goal[]> {
    const filePath = path.join(this.dataDir, 'goals.json');
    try {
      if (fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf8');
        return JSON.parse(data) as Goal[];
      }
    } catch (err) {
      console.error('[AgentPersistence] Failed to load goals:', err);
    }
    return [];
  }

  // --- Plans ---

  async savePlans(plans: ExecutionPlan[]): Promise<void> {
    this.ensureDataDir();
    const filePath = path.join(this.dataDir, 'plans.json');
    try {
      // Filter out non-persistent fields
      const serializable = plans.map(p => ({
        ...p,
        tasks: p.tasks.map(t => ({
          ...t,
          result: undefined, // Don't serialize large results
        })),
      }));
      fs.writeFileSync(filePath, JSON.stringify(serializable, null, 2), 'utf8');
    } catch (err) {
      console.error('[AgentPersistence] Failed to save plans:', err);
    }
  }

  async loadPlans(): Promise<ExecutionPlan[]> {
    const filePath = path.join(this.dataDir, 'plans.json');
    try {
      if (fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf8');
        return JSON.parse(data) as ExecutionPlan[];
      }
    } catch (err) {
      console.error('[AgentPersistence] Failed to load plans:', err);
    }
    return [];
  }

  // --- Experience ---

  async saveExperience(experiences: TaskExperience[]): Promise<void> {
    this.ensureDataDir();
    const filePath = path.join(this.dataDir, 'experience.json');
    try {
      fs.writeFileSync(filePath, JSON.stringify(experiences, null, 2), 'utf8');
    } catch (err) {
      console.error('[AgentPersistence] Failed to save experience:', err);
    }
  }

  async loadExperience(): Promise<TaskExperience[]> {
    const filePath = path.join(this.dataDir, 'experience.json');
    try {
      if (fs.existsSync(filePath)) {
        const data = fs.readFileSync(filePath, 'utf8');
        return JSON.parse(data) as TaskExperience[];
      }
    } catch (err) {
      console.error('[AgentPersistence] Failed to load experience:', err);
    }
    return [];
  }

  // --- Recovery ---

  async recoverActivePlans(): Promise<ExecutionPlan[]> {
    const plans = await this.loadPlans();
    const now = Date.now();
    const maxAge = 3600_000; // 1 hour

    return plans.filter(plan => {
      if (plan.status === 'COMPLETED' || plan.status === 'CANCELLED' || plan.status === 'FAILED') {
        return false;
      }
      // Check staleness
      const age = now - new Date(plan.updatedAt).getTime();
      if (age > maxAge) return false;
      // Only recover plans with pending tasks
      return plan.tasks.some(t => t.status === 'PENDING' || t.status === 'RUNNING');
    });
  }

  // --- Cleanup ---

  async cleanup(maxAgeMs = 86400_000): Promise<number> {
    let cleaned = 0;
    const now = Date.now();

    // Clean old goals
    const goals = await this.loadGoals();
    const activeGoals = goals.filter(g => now - new Date(g.updatedAt).getTime() < maxAgeMs);
    if (activeGoals.length < goals.length) {
      await this.saveGoals(activeGoals);
      cleaned += goals.length - activeGoals.length;
    }

    // Clean old plans
    const plans = await this.loadPlans();
    const activePlans = plans.filter(p => now - new Date(p.updatedAt).getTime() < maxAgeMs);
    if (activePlans.length < plans.length) {
      await this.savePlans(activePlans);
      cleaned += plans.length - activePlans.length;
    }

    return cleaned;
  }
}
