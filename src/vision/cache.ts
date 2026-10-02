// ============================================================================
// MYRAA Vision Core — LRU Cache with TTL Support
// ============================================================================

import type { CacheEntry } from './contracts';

// ============================================================================
// LRU Cache
// ============================================================================

export class LruCache<K, V> {
  private entries: Map<K, CacheEntry<V>> = new Map();
  private readonly maxSize: number;
  private readonly ttlMs: number;
  private hitCount = 0;
  private missCount = 0;

  constructor(maxSize: number, ttlMs: number) {
    this.maxSize = maxSize;
    this.ttlMs = ttlMs;
  }

  get(key: K): V | undefined {
    const entry = this.entries.get(key);
    if (!entry) {
      this.missCount++;
      return undefined;
    }

    if (this.isExpired(entry)) {
      this.entries.delete(key);
      this.missCount++;
      return undefined;
    }

    this.hitCount++;
    const refreshed: CacheEntry<V> = {
      ...entry,
      accessCount: entry.accessCount + 1,
      lastAccessedAt: Date.now(),
    };
    this.entries.set(key, refreshed);

    this.moveToEnd(key);
    return entry.value;
  }

  set(key: K, value: V): void {
    if (this.entries.has(key)) {
      this.entries.delete(key);
    } else if (this.entries.size >= this.maxSize) {
      this.evictOldest();
    }

    const now = Date.now();
    this.entries.set(key, {
      value,
      createdAt: now,
      accessCount: 1,
      lastAccessedAt: now,
    });
  }

  has(key: K): boolean {
    const entry = this.entries.get(key);
    if (!entry) return false;

    if (this.isExpired(entry)) {
      this.entries.delete(key);
      return false;
    }
    return true;
  }

  delete(key: K): boolean {
    return this.entries.delete(key);
  }

  clear(): void {
    this.entries.clear();
    this.hitCount = 0;
    this.missCount = 0;
  }

  get size(): number {
    return this.entries.size;
  }

  get hits(): number {
    return this.hitCount;
  }

  get misses(): number {
    return this.missCount;
  }

  get hitRate(): number {
    const total = this.hitCount + this.missCount;
    return total > 0 ? this.hitCount / total : 0;
  }

  keys(): readonly K[] {
    return [...this.entries.keys()];
  }

  values(): readonly V[] {
    return [...this.entries.values()].map(e => e.value);
  }

  entriesList(): ReadonlyArray<{ key: K; value: V; age: number }> {
    const now = Date.now();
    return [...this.entries.entries()].map(([key, entry]) => ({
      key,
      value: entry.value,
      age: now - entry.createdAt,
    }));
  }

  evictExpired(): number {
    let evicted = 0;
    for (const [key, entry] of this.entries) {
      if (this.isExpired(entry)) {
        this.entries.delete(key);
        evicted++;
      }
    }
    return evicted;
  }

  getStats(): {
    size: number;
    maxSize: number;
    hits: number;
    misses: number;
    hitRate: number;
    oldestEntryAge: number | null;
    newestEntryAge: number | null;
  } {
    const now = Date.now();
    let oldestAge: number | null = null;
    let newestAge: number | null = null;

    for (const entry of this.entries.values()) {
      const age = now - entry.createdAt;
      if (oldestAge === null || age > oldestAge) oldestAge = age;
      if (newestAge === null || age < newestAge) newestAge = age;
    }

    return {
      size: this.entries.size,
      maxSize: this.maxSize,
      hits: this.hitCount,
      misses: this.missCount,
      hitRate: this.hitRate,
      oldestEntryAge: oldestAge,
      newestEntryAge: newestAge,
    };
  }

  private isExpired(entry: CacheEntry<V>): boolean {
    if (this.ttlMs <= 0) return false;
    return Date.now() - entry.createdAt > this.ttlMs;
  }

  private evictOldest(): void {
    const firstKey = this.entries.keys().next().value;
    if (firstKey !== undefined) {
      this.entries.delete(firstKey);
    }
  }

  private moveToEnd(key: K): void {
    const value = this.entries.get(key);
    if (value === undefined) return;
    this.entries.delete(key);
    this.entries.set(key, value);
  }
}

// ============================================================================
// Scene Cache — Specialized LRU for VisualScene objects
// ============================================================================

export class SceneCache {
  private cache: LruCache<string, import('./contracts').VisualScene>;

  constructor(maxSize: number, ttlMs: number) {
    this.cache = new LruCache(maxSize, ttlMs);
  }

  get(sceneId: string): import('./contracts').VisualScene | undefined {
    return this.cache.get(sceneId);
  }

  set(scene: import('./contracts').VisualScene): void {
    this.cache.set(scene.sceneId as string, scene);
  }

  has(sceneId: string): boolean {
    return this.cache.has(sceneId);
  }

  getLatest(): import('./contracts').VisualScene | null {
    const values = this.cache.values();
    if (values.length === 0) return null;
    return values[values.length - 1];
  }

  getByIndex(index: number): import('./contracts').VisualScene | null {
    const values = this.cache.values();
    if (index < 0 || index >= values.length) return null;
    return values[index];
  }

  getStats() {
    return this.cache.getStats();
  }

  get size(): number {
    return this.cache.size;
  }

  clear(): void {
    this.cache.clear();
  }

  evictExpired(): number {
    return this.cache.evictExpired();
  }
}
