// ============================================================================
// MYRAA Live Ingestion Engine — Checkpoints, Incremental, Backpressure
// ============================================================================

import type { RawWorldData, RawWorldItem, IngestionResult, WorldIntelligenceConfig } from './contracts';
import { nowISO, generateWorldId } from './contracts';
import type { IngestionProvider } from './ingestion';

// ============================================================================
// Checkpoint State
// ============================================================================

export interface IngestionCheckpoint {
  readonly providerId: string;
  readonly lastIngestedAt: string;
  readonly lastSuccessfulAt: string;
  readonly cursor?: string;
  readonly etag?: string;
  readonly lastModified?: string;
  readonly lastProcessedId?: string;
  readonly itemCount: number;
  readonly version: number;
}

// ============================================================================
// Ingestion Queue Item
// ============================================================================

export interface IngestionQueueItem {
  readonly id: string;
  readonly providerId: string;
  readonly priority: 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';
  readonly enqueuedAt: string;
  readonly data?: RawWorldData;
  readonly isIncremental: boolean;
  readonly checkpoint?: IngestionCheckpoint;
}

// ============================================================================
// Ingestion Metrics
// ============================================================================

export interface IngestionMetrics {
  totalIngestions: number;
  successfulIngestions: number;
  failedIngestions: number;
  totalItemsFetched: number;
  totalItemsAccepted: number;
  totalDuplicatesSkipped: number;
  totalConflicts: number;
  totalErrors: number;
  avgProviderLatencyMs: number;
  avgItemsPerSecond: number;
  queueDepth: number;
  providerMetrics: Record<string, {
    readonly ingested: number;
    readonly succeeded: number;
    readonly failed: number;
    readonly avgLatencyMs: number;
    readonly lastIngestedAt?: string;
  }>;
}

// ============================================================================
// Bounded Queue with Backpressure
// ============================================================================

class BoundedQueue<T> {
  private items: T[] = [];
  private maxSize: number;
  private waiters: ((item: T) => void)[] = [];

  constructor(maxSize: number) {
    this.maxSize = maxSize;
  }

  enqueue(item: T): boolean {
    if (this.items.length >= this.maxSize) {
      return false; // backpressure
    }
    if (this.waiters.length > 0) {
      const waiter = this.waiters.shift()!;
      waiter(item);
    } else {
      this.items.push(item);
    }
    return true;
  }

  dequeue(): T | undefined {
    return this.items.shift();
  }

  size(): number {
    return this.items.length;
  }

  isFull(): boolean {
    return this.items.length >= this.maxSize;
  }

  clear(): void {
    this.items = [];
    this.waiters = [];
  }

  drain(max?: number): T[] {
    const count = max || this.items.length;
    return this.items.splice(0, count);
  }
}

// ============================================================================
// Live Ingestion Engine
// ============================================================================

export class LiveIngestionEngine {
  private providers: Map<string, IngestionProvider> = new Map();
  private checkpoints: Map<string, IngestionCheckpoint> = new Map();
  private queue: BoundedQueue<IngestionQueueItem>;
  private metrics: IngestionMetrics;
  private processing = false;
  private config: WorldIntelligenceConfig;
  private onItemReady?: (providerId: string, data: RawWorldData) => Promise<IngestionResult>;

  constructor(config: WorldIntelligenceConfig, queueSize = 1000) {
    this.config = config;
    this.queue = new BoundedQueue(queueSize);
    this.metrics = this.createEmptyMetrics();
  }

  // --- Provider Management ---

  registerProvider(provider: IngestionProvider): void {
    this.providers.set(provider.id, provider);
    // Initialize checkpoint if not exists
    if (!this.checkpoints.has(provider.id)) {
      this.checkpoints.set(provider.id, {
        providerId: provider.id,
        lastIngestedAt: '',
        lastSuccessfulAt: '',
        itemCount: 0,
        version: 1,
      });
    }
  }

  unregisterProvider(providerId: string): void {
    this.providers.delete(providerId);
    this.checkpoints.delete(providerId);
  }

  setItemHandler(handler: (providerId: string, data: RawWorldData) => Promise<IngestionResult>): void {
    this.onItemReady = handler;
  }

  // --- Queue Operations ---

  enqueue(providerId: string, priority: IngestionQueueItem['priority'] = 'NORMAL'): boolean {
    const item: IngestionQueueItem = {
      id: generateWorldId(),
      providerId,
      priority,
      enqueuedAt: nowISO(),
      isIncremental: false,
      checkpoint: this.checkpoints.get(providerId),
    };
    return this.queue.enqueue(item);
  }

  enqueueIncremental(providerId: string, data: RawWorldData, priority: IngestionQueueItem['priority'] = 'HIGH'): boolean {
    const item: IngestionQueueItem = {
      id: generateWorldId(),
      providerId,
      priority,
      enqueuedAt: nowISO(),
      data,
      isIncremental: true,
      checkpoint: this.checkpoints.get(providerId),
    };
    return this.queue.enqueue(item);
  }

  queueDepth(): number {
    return this.queue.size();
  }

  queueFull(): boolean {
    return this.queue.isFull();
  }

  // --- Ingestion ---

  async ingestProvider(providerId: string): Promise<IngestionResult> {
    const provider = this.providers.get(providerId);
    if (!provider || !provider.enabled) {
      return this.makeResult(providerId, false, 0, 0, 0, 0, 0, ['Provider not found or disabled']);
    }
    const start = Date.now();
    const checkpoint = this.checkpoints.get(providerId);
    try {
      const data = await provider.fetch();
      const duration = Date.now() - start;
      // Update checkpoint
      this.checkpoints.set(providerId, {
        ...checkpoint!,
        providerId,
        lastIngestedAt: nowISO(),
        lastSuccessfulAt: nowISO(),
        itemCount: checkpoint!.itemCount + data.items.length,
        version: checkpoint!.version + 1,
      });
      // Forward to handler
      let result: IngestionResult;
      if (this.onItemReady) {
        result = await this.onItemReady(providerId, data);
      } else {
        result = this.makeResult(providerId, true, 0, data.items.length, 0, 0, 0);
      }
      // Update metrics
      this.updateProviderMetrics(providerId, true, data.items.length, duration);
      return { ...result, durationMs: duration };
    } catch (err) {
      const duration = Date.now() - start;
      this.updateProviderMetrics(providerId, false, 0, duration);
      return this.makeResult(providerId, false, 0, 0, 0, 0, 0, [String(err)]);
    }
  }

  async ingestAll(): Promise<IngestionResult[]> {
    const results: IngestionResult[] = [];
    const enabled = Array.from(this.providers.values()).filter(p => p.enabled);
    for (let i = 0; i < enabled.length; i += this.config.ingestionConcurrency) {
      const batch = enabled.slice(i, i + this.config.ingestionConcurrency);
      const batchResults = await Promise.allSettled(batch.map(p => this.ingestProvider(p.id)));
      for (const r of batchResults) {
        if (r.status === 'fulfilled') results.push(r.value);
        else results.push(this.makeResult('unknown', false, 0, 0, 0, 0, 0, [String(r.reason)]));
      }
    }
    this.metrics.totalIngestions += results.length;
    this.metrics.successfulIngestions += results.filter(r => r.success).length;
    this.metrics.failedIngestions += results.filter(r => !r.success).length;
    return results;
  }

  async processQueue(maxItems = 100): Promise<IngestionResult[]> {
    const results: IngestionResult[] = [];
    const items = this.queue.drain(maxItems);
    // Sort by priority
    const priorityOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, NORMAL: 2, LOW: 3 };
    items.sort((a, b) => (priorityOrder[a.priority] || 2) - (priorityOrder[b.priority] || 2));
    for (const item of items) {
      try {
        if (item.data && this.onItemReady) {
          const result = await this.onItemReady(item.providerId, item.data);
          results.push(result);
        } else {
          const result = await this.ingestProvider(item.providerId);
          results.push(result);
        }
      } catch {
        results.push(this.makeResult(item.providerId, false, 0, 0, 0, 0, 0, ['Queue processing error']));
      }
    }
    return results;
  }

  // --- Checkpoint Management ---

  getCheckpoint(providerId: string): IngestionCheckpoint | undefined {
    return this.checkpoints.get(providerId);
  }

  setCheckpoint(providerId: string, checkpoint: Partial<IngestionCheckpoint>): void {
    const existing = this.checkpoints.get(providerId);
    if (existing) {
      this.checkpoints.set(providerId, { ...existing, ...checkpoint });
    }
  }

  resetCheckpoint(providerId: string): void {
    this.checkpoints.set(providerId, {
      providerId,
      lastIngestedAt: '',
      lastSuccessfulAt: '',
      itemCount: 0,
      version: 1,
    });
  }

  getAllCheckpoints(): IngestionCheckpoint[] {
    return Array.from(this.checkpoints.values());
  }

  // --- Watermark Protection ---

  isStaleWrite(providerId: string, itemTimestamp: string): boolean {
    const checkpoint = this.checkpoints.get(providerId);
    if (!checkpoint || !checkpoint.lastSuccessfulAt) return false;
    return itemTimestamp < checkpoint.lastSuccessfulAt;
  }

  // --- Metrics ---

  getMetrics(): IngestionMetrics {
    return { ...this.metrics };
  }

  private updateProviderMetrics(providerId: string, success: boolean, items: number, latencyMs: number): void {
    const existing = this.metrics.providerMetrics[providerId] || {
      ingested: 0, succeeded: 0, failed: 0, avgLatencyMs: 0, lastIngestedAt: '',
    };
    const total = existing.succeeded + existing.failed + (success ? 1 : 0);
    this.metrics.providerMetrics[providerId] = {
      ingested: existing.ingested + 1,
      succeeded: existing.succeeded + (success ? 1 : 0),
      failed: existing.failed + (success ? 0 : 1),
      avgLatencyMs: total > 0 ? (existing.avgLatencyMs * existing.ingested + latencyMs) / total : latencyMs,
      lastIngestedAt: nowISO(),
    };
    this.metrics.totalItemsFetched += items;
    this.metrics.totalItemsAccepted += items;
  }

  private createEmptyMetrics(): IngestionMetrics {
    return {
      totalIngestions: 0,
      successfulIngestions: 0,
      failedIngestions: 0,
      totalItemsFetched: 0,
      totalItemsAccepted: 0,
      totalDuplicatesSkipped: 0,
      totalConflicts: 0,
      totalErrors: 0,
      avgProviderLatencyMs: 0,
      avgItemsPerSecond: 0,
      queueDepth: 0,
      providerMetrics: {},
    };
  }

  private makeResult(
    providerId: string, success: boolean,
    entities: number, items: number, events: number,
    duplicates: number, conflicts: number, errors: string[] = []
  ): IngestionResult {
    return {
      sourceId: providerId,
      success,
      entitiesFound: entities,
      factsFound: 0,
      eventsFound: events || items,
      duplicatesSkipped: duplicates,
      conflictsDetected: conflicts,
      errors,
      ingestedAt: nowISO(),
      durationMs: 0,
    };
  }

  // --- Provider Discovery from public-apis ---

  async discoverFromPublicApis(category?: string): Promise<{ id: string; name: string; description: string; auth: string; https: boolean; url: string }[]> {
    try {
      const url = category
        ? `https://api.publicapis.org/entries?category=${category}&https=true`
        : 'https://api.publicapis.org/entries?https=true';
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 10_000);
      const res = await fetch(url, { signal: controller.signal });
      clearTimeout(timer);
      const data = await res.json() as Record<string, unknown>;
      const entries = (data.entries || []) as Record<string, unknown>[];
      return entries.slice(0, 50).map(e => ({
        id: String(e.API || '').toLowerCase().replace(/\s+/g, '-'),
        name: String(e.API || ''),
        description: String(e.Description || ''),
        auth: String(e.Auth || 'none'),
        https: Boolean(e.HTTPS),
        url: String(e.Link || ''),
      }));
    } catch {
      return [];
    }
  }
}
