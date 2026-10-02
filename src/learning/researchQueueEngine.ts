// ============================================================================
// MYRAA Phase 28 — Research Queue Engine
// Manages research queue with priority, cooldowns, and deduplication.
// ============================================================================

export type ResearchPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type ResearchStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'COOLDOWN';

export interface ResearchQueueItem {
  readonly itemId: string;
  readonly hypothesisId?: string;
  readonly strategyId?: string;
  readonly experimentName: string;
  readonly description: string;
  readonly priority: ResearchPriority;
  status: ResearchStatus;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  readonly reason: string;
  readonly budget: number;
  cooldownUntil?: string;
  attempts: number;
  readonly maxAttempts: number;
  readonly metadata: Record<string, unknown>;
}

export interface ResearchCooldownConfig {
  readonly sameHypothesisCooldownMs: number;
  readonly sameStrategyCooldownMs: number;
  readonly globalCooldownMs: number;
  readonly maxConcurrent: number;
  readonly maxDailyExperiments: number;
}

const DEFAULT_COOLDOWN: ResearchCooldownConfig = {
  sameHypothesisCooldownMs: 3600000,
  sameStrategyCooldownMs: 1800000,
  globalCooldownMs: 600000,
  maxConcurrent: 3,
  maxDailyExperiments: 20,
};

export class ResearchQueueEngine {
  private queue: ResearchQueueItem[] = [];
  private completed: ResearchQueueItem[] = [];
  private config: ResearchCooldownConfig;
  private dailyCount = 0;
  private lastResetDay = '';

  constructor(config?: Partial<ResearchCooldownConfig>) {
    this.config = { ...DEFAULT_COOLDOWN, ...config };
  }

  enqueue(params: {
    hypothesisId?: string;
    strategyId?: string;
    experimentName: string;
    description: string;
    priority: ResearchPriority;
    reason: string;
    budget?: number;
    maxAttempts?: number;
    metadata?: Record<string, unknown>;
  }): ResearchQueueItem {
    if (this.isDuplicate(params.hypothesisId, params.strategyId)) {
      throw new Error('Duplicate research request for same hypothesis/strategy within cooldown period');
    }

    const now = new Date();
    const today = now.toISOString().slice(0, 10);
    if (today !== this.lastResetDay) {
      this.dailyCount = 0;
      this.lastResetDay = today;
    }

    if (this.dailyCount >= this.config.maxDailyExperiments) {
      throw new Error('Daily research budget exhausted');
    }

    const item: ResearchQueueItem = {
      itemId: `rq_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      hypothesisId: params.hypothesisId,
      strategyId: params.strategyId,
      experimentName: params.experimentName,
      description: params.description,
      priority: params.priority,
      status: 'QUEUED',
      createdAt: now.toISOString(),
      reason: params.reason,
      budget: params.budget || 100,
      attempts: 0,
      maxAttempts: params.maxAttempts || 3,
      metadata: params.metadata || {},
    };

    this.queue.push(item);
    this.sortQueue();
    return item;
  }

  dequeue(): ResearchQueueItem | undefined {
    this.resetDailyIfNeeded();
    const running = this.queue.filter(i => i.status === 'RUNNING').length;
    if (running >= this.config.maxConcurrent) return undefined;

    const now = Date.now();
    const available = this.queue.find(i =>
      i.status === 'QUEUED' &&
      (!i.cooldownUntil || new Date(i.cooldownUntil).getTime() <= now)
    );

    if (available) {
      available.status = 'RUNNING';
      available.startedAt = new Date().toISOString();
      available.attempts++;
      this.dailyCount++;
      return available;
    }
    return undefined;
  }

  complete(itemId: string): void {
    const item = this.queue.find(i => i.itemId === itemId);
    if (item) {
      item.status = 'COMPLETED';
      item.completedAt = new Date().toISOString();
      this.completed.push(item);
    }
  }

  fail(itemId: string): void {
    const item = this.queue.find(i => i.itemId === itemId);
    if (item) {
      if (item.attempts >= item.maxAttempts) {
        item.status = 'FAILED';
        this.completed.push(item);
      } else {
        item.status = 'COOLDOWN';
        const cooldownMs = this.getCooldownMs(item);
        item.cooldownUntil = new Date(Date.now() + cooldownMs).toISOString();
        item.status = 'QUEUED';
      }
    }
  }

  cancel(itemId: string): boolean {
    const item = this.queue.find(i => i.itemId === itemId);
    if (item && (item.status === 'QUEUED' || item.status === 'COOLDOWN')) {
      item.status = 'CANCELLED';
      this.completed.push(item);
      return true;
    }
    return false;
  }

  getQueue(): ResearchQueueItem[] {
    return this.queue.filter(i => i.status !== 'CANCELLED' && i.status !== 'COMPLETED' && i.status !== 'FAILED');
  }

  getCompleted(): ResearchQueueItem[] {
    return [...this.completed];
  }

  getRunning(): ResearchQueueItem[] {
    return this.queue.filter(i => i.status === 'RUNNING');
  }

  getQueueLength(): number {
    return this.getQueue().length;
  }

  getDailyCount(): number {
    this.resetDailyIfNeeded();
    return this.dailyCount;
  }

  private isDuplicate(hypothesisId?: string, strategyId?: string): boolean {
    const active = this.getQueue();
    if (hypothesisId) {
      const dup = active.find(i => i.hypothesisId === hypothesisId && i.status !== 'CANCELLED');
      if (dup) return true;
    }
    if (strategyId) {
      const dup = active.find(i =>
        i.strategyId === strategyId &&
        i.status !== 'CANCELLED' &&
        new Date(i.createdAt).getTime() > Date.now() - this.config.sameStrategyCooldownMs
      );
      if (dup) return true;
    }
    return false;
  }

  private getCooldownMs(item: ResearchQueueItem): number {
    if (item.hypothesisId) return this.config.sameHypothesisCooldownMs;
    if (item.strategyId) return this.config.sameStrategyCooldownMs;
    return this.config.globalCooldownMs;
  }

  private sortQueue(): void {
    const priorityOrder: Record<ResearchPriority, number> = {
      CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1,
    };
    this.queue.sort((a, b) => {
      const pa = priorityOrder[a.priority];
      const pb = priorityOrder[b.priority];
      if (pa !== pb) return pb - pa;
      return a.createdAt.localeCompare(b.createdAt);
    });
  }

  private resetDailyIfNeeded(): void {
    const today = new Date().toISOString().slice(0, 10);
    if (today !== this.lastResetDay) {
      this.dailyCount = 0;
      this.lastResetDay = today;
    }
  }
}

export const researchQueueEngine = new ResearchQueueEngine();
