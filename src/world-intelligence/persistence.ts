// ============================================================================
// MYRAA World State Persistence Engine
// ============================================================================

import {
  WorldIntelligenceConfig,
  WorldEntity, TemporalFact, WorldEvent,
  WorldStateSnapshot, nowISO, computeChecksum,
} from './contracts';
import * as fs from 'fs';
import * as path from 'path';

export interface PersistenceEntry {
  readonly type: 'entity' | 'fact' | 'event' | 'snapshot' | 'watcher' | 'config';
  readonly id: string;
  readonly data: unknown;
  readonly checksum: string;
  readonly persistedAt: string;
}

export class WorldPersistenceEngine {
  private config: WorldIntelligenceConfig;
  private dataDir: string;
  private dirty = false;
  private saveTimer: ReturnType<typeof setTimeout> | null = null;
  private mutex = false;
  private writeQueue: PersistenceEntry[] = [];

  constructor(config: WorldIntelligenceConfig) {
    this.config = config;
    this.dataDir = config.persistencePath || path.join(process.cwd(), '.myrra', 'world-intelligence');
  }

  ensureDataDir(): void {
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
    }
  }

  // --- Entity Persistence ---

  async persistEntity(entity: WorldEntity): Promise<void> {
    const entry: PersistenceEntry = {
      type: 'entity',
      id: entity.id,
      data: entity,
      checksum: computeChecksum(JSON.stringify(entity)),
      persistedAt: nowISO(),
    };
    this.writeQueue.push(entry);
    this.scheduleSave();
  }

  async persistEntities(entities: WorldEntity[]): Promise<void> {
    for (const entity of entities) {
      await this.persistEntity(entity);
    }
  }

  // --- Fact Persistence ---

  async persistFact(fact: TemporalFact): Promise<void> {
    const entry: PersistenceEntry = {
      type: 'fact',
      id: fact.id,
      data: fact,
      checksum: computeChecksum(JSON.stringify(fact)),
      persistedAt: nowISO(),
    };
    this.writeQueue.push(entry);
    this.scheduleSave();
  }

  async persistFacts(facts: TemporalFact[]): Promise<void> {
    for (const fact of facts) {
      await this.persistFact(fact);
    }
  }

  // --- Event Persistence ---

  async persistEvent(event: WorldEvent): Promise<void> {
    const entry: PersistenceEntry = {
      type: 'event',
      id: event.id,
      data: event,
      checksum: computeChecksum(JSON.stringify(event)),
      persistedAt: nowISO(),
    };
    this.writeQueue.push(entry);
    this.scheduleSave();
  }

  async persistEvents(events: WorldEvent[]): Promise<void> {
    for (const event of events) {
      await this.persistEvent(event);
    }
  }

  // --- Snapshot Persistence ---

  async persistSnapshot(snapshot: WorldStateSnapshot): Promise<void> {
    const snapshotData = {
      timestamp: snapshot.timestamp,
      checksum: snapshot.checksum,
      entityCount: snapshot.entities.size,
      factCount: snapshot.facts.size,
      eventCount: snapshot.events.size,
      entities: Array.from(snapshot.entities.entries()),
      facts: Array.from(snapshot.facts.entries()),
      events: Array.from(snapshot.events.entries()),
    };
    const entry: PersistenceEntry = {
      type: 'snapshot',
      id: snapshot.timestamp,
      data: snapshotData,
      checksum: snapshot.checksum,
      persistedAt: nowISO(),
    };
    const filePath = this.getFilePath('snapshot', snapshot.timestamp);
    await this.writeFileAtomic(filePath, JSON.stringify(entry, null, 2));
  }

  // --- Bulk Persistence ---

  async persistAll(
    entities: WorldEntity[],
    facts: TemporalFact[],
    events: WorldEvent[]
  ): Promise<void> {
    this.ensureDataDir();
    // Write entities
    const entityData = entities.map(e => ({
      id: e.id,
      data: e,
      checksum: computeChecksum(JSON.stringify(e)),
    }));
    await this.writeFileAtomic(
      this.getFilePath('entities', 'all'),
      JSON.stringify(entityData, null, 2)
    );
    // Write facts
    const factData = facts.map(f => ({
      id: f.id,
      data: f,
      checksum: computeChecksum(JSON.stringify(f)),
    }));
    await this.writeFileAtomic(
      this.getFilePath('facts', 'all'),
      JSON.stringify(factData, null, 2)
    );
    // Write events
    const eventData = events.map(e => ({
      id: e.id,
      data: e,
      checksum: computeChecksum(JSON.stringify(e)),
    }));
    await this.writeFileAtomic(
      this.getFilePath('events', 'all'),
      JSON.stringify(eventData, null, 2)
    );
  }

  // --- Load ---

  async loadEntities(): Promise<WorldEntity[]> {
    return this.loadArray<WorldEntity>('entities', 'all');
  }

  async loadFacts(): Promise<TemporalFact[]> {
    return this.loadArray<TemporalFact>('facts', 'all');
  }

  async loadEvents(): Promise<WorldEvent[]> {
    return this.loadArray<WorldEvent>('events', 'all');
  }

  async loadLatestSnapshot(): Promise<WorldStateSnapshot | null> {
    try {
      this.ensureDataDir();
      const snapshotDir = path.join(this.dataDir, 'snapshot');
      if (!fs.existsSync(snapshotDir)) return null;
      const files = fs.readdirSync(snapshotDir)
        .filter(f => f.endsWith('.json'))
        .sort()
        .reverse();
      if (files.length === 0) return null;
      const content = fs.readFileSync(path.join(snapshotDir, files[0]), 'utf-8');
      const entry: PersistenceEntry = JSON.parse(content);
      if (entry.checksum !== computeChecksum(JSON.stringify(entry.data))) {
        console.warn('[WorldPersistence] Snapshot checksum mismatch, attempting recovery');
        return this.recoverSnapshot();
      }
      const data = entry.data as any;
      return {
        timestamp: data.timestamp,
        checksum: data.checksum,
        entities: new Map(data.entities),
        facts: new Map(data.facts),
        events: new Map(data.events),
        graph: { nodes: new Map(), edges: new Map(), adjacency: new Map() },
      };
    } catch {
      return this.recoverSnapshot();
    }
  }

  // --- Recovery ---

  private async recoverSnapshot(): Promise<WorldStateSnapshot | null> {
    try {
      this.ensureDataDir();
      const snapshotDir = path.join(this.dataDir, 'snapshot');
      if (!fs.existsSync(snapshotDir)) return null;
      const files = fs.readdirSync(snapshotDir)
        .filter(f => f.endsWith('.json.bak'))
        .sort()
        .reverse();
      if (files.length === 0) return null;
      const content = fs.readFileSync(path.join(snapshotDir, files[0]), 'utf-8');
      const entry: PersistenceEntry = JSON.parse(content);
      const data = entry.data as any;
      // Restore .bak as main
      const mainFile = files[0].replace('.bak', '');
      fs.copyFileSync(path.join(snapshotDir, files[0]), path.join(snapshotDir, mainFile));
      return {
        timestamp: data.timestamp,
        checksum: data.checksum,
        entities: new Map(data.entities),
        facts: new Map(data.facts),
        events: new Map(data.events),
        graph: { nodes: new Map(), edges: new Map(), adjacency: new Map() },
      };
    } catch {
      return null;
    }
  }

  // --- Validation ---

  async validateData(): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = [];
    try {
      const entities = await this.loadEntities();
      for (const e of entities) {
        if (!e.id || !e.identity?.canonicalName) {
          errors.push(`Invalid entity: missing id or name`);
        }
      }
    } catch (err) {
      errors.push(`Entity validation failed: ${err}`);
    }
    try {
      const facts = await this.loadFacts();
      for (const f of facts) {
        if (!f.id || !f.subjectId || !f.predicate) {
          errors.push(`Invalid fact: missing id, subjectId, or predicate`);
        }
      }
    } catch (err) {
      errors.push(`Fact validation failed: ${err}`);
    }
    try {
      const events = await this.loadEvents();
      for (const e of events) {
        if (!e.id || !e.title || !e.type) {
          errors.push(`Invalid event: missing id, title, or type`);
        }
      }
    } catch (err) {
      errors.push(`Event validation failed: ${err}`);
    }
    return { valid: errors.length === 0, errors };
  }

  // --- Cleanup ---

  async cleanupOldSnapshots(keepCount = 10): Promise<number> {
    this.ensureDataDir();
    const snapshotDir = path.join(this.dataDir, 'snapshot');
    if (!fs.existsSync(snapshotDir)) return 0;
    const files = fs.readdirSync(snapshotDir)
      .filter(f => f.endsWith('.json'))
      .sort()
      .reverse();
    let removed = 0;
    for (let i = keepCount; i < files.length; i++) {
      try {
        fs.unlinkSync(path.join(snapshotDir, files[i]));
        removed++;
      } catch { /* ignore */ }
    }
    return removed;
  }

  // --- Internals ---

  private scheduleSave(): void {
    this.dirty = true;
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      this.flushQueue();
    }, 1000);
  }

  private async flushQueue(): Promise<void> {
    if (this.mutex) return;
    this.mutex = true;
    try {
      this.ensureDataDir();
      const batch = this.writeQueue.splice(0);
      // Group by type
      const groups: Record<string, PersistenceEntry[]> = {};
      for (const entry of batch) {
        if (!groups[entry.type]) groups[entry.type] = [];
        groups[entry.type].push(entry);
      }
      for (const [type, entries] of Object.entries(groups)) {
        const filePath = this.getFilePath(type, 'batch');
        const existing = await this.loadArrayRaw(filePath);
        const map = new Map(existing.map((e: any) => [e.id, e]));
        for (const entry of entries) {
          map.set(entry.id, entry);
        }
        await this.writeFileAtomic(filePath, JSON.stringify(Array.from(map.values()), null, 2));
      }
      this.dirty = false;
    } finally {
      this.mutex = false;
    }
  }

  private async loadArray<T>(type: string, key: string): Promise<T[]> {
    const raw = await this.loadArrayRaw(this.getFilePath(type, key));
    return raw.map((e: any) => e.data as T);
  }

  private async loadArrayRaw(filePath: string): Promise<any[]> {
    try {
      this.ensureDataDir();
      if (!fs.existsSync(filePath)) return [];
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch {
      return [];
    }
  }

  private getFilePath(type: string, key: string): string {
    const dir = path.join(this.dataDir, type);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    return path.join(dir, `${key}.json`);
  }

  private async writeFileAtomic(filePath: string, content: string): Promise<void> {
    const tmpPath = `${filePath}.tmp`;
    const bakPath = `${filePath}.bak`;
    try {
      // Backup existing
      if (fs.existsSync(filePath)) {
        fs.copyFileSync(filePath, bakPath);
      }
      // Write temp
      fs.writeFileSync(tmpPath, content, 'utf-8');
      // Atomic rename
      fs.renameSync(tmpPath, filePath);
    } catch (err) {
      // Try to recover from backup
      if (fs.existsSync(bakPath)) {
        try { fs.copyFileSync(bakPath, filePath); } catch { /* ignore */ }
      }
      throw err;
    }
  }

  getDataDir(): string {
    return this.dataDir;
  }
}
