// ============================================================================
// MYRAA World Intelligence Engine — Main Integration + API
// ============================================================================

import {
  WorldIntelligenceConfig, DEFAULT_WORLD_CONFIG,
  WorldEntity, TemporalFact, WorldEvent, EventSource,
  WorldQuery, WorldQueryResult,
  WorldWatcher, WatcherPolicy, WatcherAlert,
  WorldStateSnapshot, WorldStateDiff,
  DataQualityMetrics, WorldEngineEvent, WorldEngineEventType,
  EntityType, WorldEventType, ImportanceLevel, FactProvenance,
  generateWorldId, nowISO,
} from './contracts';
import { WorldStateEngine } from './world_state_engine';
import { EntityResolver } from './entity_resolution';
import { WorldIngestionEngine, IngestionProvider } from './ingestion';
import { DeduplicationEngine } from './deduplication';
import { KnowledgeGraphEngine } from './knowledge_graph';
import { WorldQueryEngine } from './query_engine';
import { WorldWatcherEngine } from './watcher';
import { WorldPersistenceEngine } from './persistence';
import { LiveIngestionEngine } from './live_ingestion';
import { HybridSearchEngine } from './semantic_search';
import { LlmExtractionEngine } from './llm_extraction';
import { EvidencePackBuilder, buildBrainContext } from './evidence';
import type { BrainWorldContext, EvidencePack } from './evidence';
import { createDefaultProviders, createNewsProviders } from './providers/real_providers';

// ============================================================================
// WorldIntelligence — Main API Surface
// ============================================================================

export class WorldIntelligence {
  readonly state: WorldStateEngine;
  readonly resolver: EntityResolver;
  readonly ingestion: WorldIngestionEngine;
  readonly dedup: DeduplicationEngine;
  readonly graph: KnowledgeGraphEngine;
  readonly query: WorldQueryEngine;
  readonly watcher: WorldWatcherEngine;
  readonly persistence: WorldPersistenceEngine;
  readonly liveIngestion: LiveIngestionEngine;
  readonly semanticSearch: HybridSearchEngine;
  readonly llmExtraction: LlmExtractionEngine;
  private config: WorldIntelligenceConfig;
  private refreshTimers: Map<string, ReturnType<typeof setInterval>> = new Map();
  private eventHandlers: ((event: WorldEngineEvent) => void)[] = [];

  constructor(config?: Partial<WorldIntelligenceConfig>) {
    this.config = { ...DEFAULT_WORLD_CONFIG, ...config };
    this.state = new WorldStateEngine(this.config);
    this.resolver = new EntityResolver();
    this.dedup = new DeduplicationEngine();
    this.graph = new KnowledgeGraphEngine();
    this.ingestion = new WorldIngestionEngine(this.state, this.resolver, this.dedup, this.config);
    this.query = new WorldQueryEngine(this.state, this.resolver, this.graph);
    this.watcher = new WorldWatcherEngine(this.state);
    this.persistence = new WorldPersistenceEngine(this.config);
    this.liveIngestion = new LiveIngestionEngine(this.config);
    this.semanticSearch = new HybridSearchEngine();
    this.llmExtraction = new LlmExtractionEngine();
    this.wireEvents();
  }

  // ==========================================================================
  // Initialization
  // ==========================================================================

  async initialize(): Promise<void> {
    this.persistence.ensureDataDir();
    // Load persisted state
    const entities = await this.persistence.loadEntities();
    const facts = await this.persistence.loadFacts();
    const events = await this.persistence.loadEvents();
    // Populate state engine
    for (const e of entities) {
      (this.state as any).entities.set(e.id, e);
      this.resolver.indexEntity(e);
    }
    for (const f of facts) {
      (this.state as any).facts.set(f.id, f);
    }
    for (const e of events) {
      (this.state as any).events.set(e.id, e);
      this.dedup.registerEvent(e);
    }
    // Rebuild indexes
    (this.state as any).rebuildIndexes();
    // Populate semantic index
    const entityMap = (this.state as any).entities as Map<string, WorldEntity>;
    const eventMap = (this.state as any).events as Map<string, WorldEvent>;
    for (const e of entityMap.values()) {
      this.semanticSearch.indexEntity(e);
    }
    for (const e of eventMap.values()) {
      this.semanticSearch.indexEvent(e);
    }
    // Register built-in providers
    this.registerBuiltinProviders();
    // Wire live ingestion handler
    this.liveIngestion.setItemHandler(async (providerId, data) => {
      return this.processIngestedData(providerId, data);
    });
  }

  // ==========================================================================
  // Entity API
  // ==========================================================================

  createEntity(
    entityType: EntityType,
    canonicalName: string,
    aliases?: { name: string; type: string }[],
    options?: { importance?: ImportanceLevel; tags?: string[]; metadata?: Record<string, unknown> }
  ): WorldEntity {
    const entity = this.state.createEntity(entityType, canonicalName, aliases as any, options);
    this.resolver.indexEntity(entity);
    this.dedup.registerEntity(entity);
    this.graph.addEntityNode(entity);
    this.persistence.persistEntity(entity);
    return entity;
  }

  getEntity(id: string): WorldEntity | undefined {
    return this.state.getEntity(id);
  }

  searchEntities(query: string, limit?: number): WorldEntity[] {
    return this.state.searchEntities(query, limit);
  }

  findEntitiesByName(name: string): WorldEntity[] {
    return this.state.findEntitiesByName(name);
  }

  mergeEntities(sourceId: string, targetId: string): WorldEntity | null {
    return this.state.mergeEntities(sourceId, targetId);
  }

  // ==========================================================================
  // Fact API
  // ==========================================================================

  createFact(
    subjectId: string,
    predicate: string,
    options?: {
      objectId?: string;
      objectValue?: string | number | boolean;
      validFrom?: string;
      validTo?: string;
      confidence?: number;
      provenance?: FactProvenance[];
    }
  ): TemporalFact {
    const fact = this.state.createFact(subjectId, predicate, options);
    this.dedup.registerFact(fact);
    this.persistence.persistFact(fact);
    return fact;
  }

  getFact(id: string): TemporalFact | undefined {
    return this.state.getFact(id);
  }

  getCurrentFact(subjectId: string, predicate: string): TemporalFact | undefined {
    return this.state.getCurrentFact(subjectId, predicate);
  }

  getHistoricalFacts(subjectId: string, predicate: string, atTime: string): TemporalFact[] {
    return this.state.getHistoricalFacts(subjectId, predicate, atTime);
  }

  retractFact(id: string, reason: string): TemporalFact | null {
    return this.state.retractFact(id, reason);
  }

  // ==========================================================================
  // Event API
  // ==========================================================================

  createEvent(
    type: WorldEventType,
    title: string,
    summary: string,
    entityIds: string[],
    timestamp: string,
    options?: {
      publishedAt?: string;
      location?: { country?: string; region?: string; city?: string; coordinates?: { lat: number; lng: number } };
      importance?: ImportanceLevel;
      confidence?: number;
      sources?: EventSource[];
      topicIds?: string[];
      relatedEventIds?: string[];
      tags?: string[];
      metadata?: Record<string, unknown>;
      freshnessClass?: import('./contracts').FreshnessClass;
      observationStatus?: import('./contracts').ObservationStatus;
    }
  ): WorldEvent {
    const event = this.state.createEvent(type, title, summary, entityIds, timestamp, options as any);
    this.dedup.registerEvent(event);
    this.graph.addEventNode(event);
    this.graph.linkEventToEntities(event, 'world-intelligence');
    this.persistence.persistEvent(event);
    // Evaluate watchers
    const alerts = this.watcher.evaluate(event);
    if (alerts.length > 0) {
      for (const handler of this.eventHandlers) {
        handler({ type: 'watcher_triggered', timestamp: nowISO(), data: { alerts, eventId: event.id } });
      }
    }
    return event;
  }

  getEvent(id: string): WorldEvent | undefined {
    return this.state.getEvent(id);
  }

  getRecentEvents(hours?: number, limit?: number): WorldEvent[] {
    return this.state.getRecentEvents(hours, limit);
  }

  // ==========================================================================
  // Query API
  // ==========================================================================

  queryWorld(query: WorldQuery): WorldQueryResult {
    return this.query.query(query);
  }

  queryEntity(entityId: string): WorldQueryResult {
    return this.query.query({ type: 'ENTITY_LOOKUP', entityIds: [entityId], includeProvenance: true });
  }

  queryEvents(options: { entityIds?: string[]; eventTypes?: WorldEventType[]; topics?: string[]; timeRange?: { from?: string; to?: string }; maxResults?: number }): WorldQueryResult {
    return this.query.query({ type: 'EVENT_LOOKUP', ...options });
  }

  queryFacts(entityId: string, timeRange?: { from?: string; to?: string }): WorldQueryResult {
    return this.query.query({ type: 'FACT_LOOKUP', entityIds: [entityId], timeRange });
  }

  queryHistory(entityId: string, predicate: string, atTime: string): TemporalFact[] {
    return this.state.getHistoricalFacts(entityId, predicate, atTime);
  }

  compareEntities(entityIds: string[]): WorldQueryResult {
    return this.query.query({ type: 'COMPARISON', entityIds });
  }

  getChanges(from: string, to?: string): WorldStateDiff {
    return this.state.getDiff(from, to);
  }

  // ==========================================================================
  // Watcher API
  // ==========================================================================

  watch(options: {
    entityType?: EntityType;
    entityIds?: string[];
    topics?: string[];
    eventTypes?: WorldEventType[];
    policy: WatcherPolicy;
  }): WorldWatcher {
    return this.watcher.watch(options);
  }

  pauseWatcher(watcherId: string): boolean {
    return this.watcher.pause(watcherId);
  }

  resumeWatcher(watcherId: string): boolean {
    return this.watcher.resume(watcherId);
  }

  stopWatcher(watcherId: string): boolean {
    return this.watcher.stop(watcherId);
  }

  unwatch(watcherId: string): boolean {
    return this.watcher.unwatch(watcherId);
  }

  getAlerts(watcherId?: string): WatcherAlert[] {
    return this.watcher.getAlerts(watcherId, true);
  }

  acknowledgeAlert(alertId: string): boolean {
    return this.watcher.acknowledgeAlert(alertId);
  }

  // ==========================================================================
  // Ingestion API
  // ==========================================================================

  registerProvider(provider: IngestionProvider): void {
    this.ingestion.registerProvider(provider);
  }

  async ingestFromProvider(providerId: string): Promise<import('./contracts').IngestionResult> {
    return this.ingestion.ingestFromProvider(providerId);
  }

  async ingestAll(): Promise<import('./contracts').IngestionResult[]> {
    return this.ingestion.ingestFromAll();
  }

  // ==========================================================================
  // Refresh / Scheduling
  // ==========================================================================

  startAutoRefresh(intervalMs = 300_000): void {
    this.stopAutoRefresh();
    const timer = setInterval(async () => {
      try {
        await this.ingestAll();
        this.persistence.persistAll(
          Array.from((this.state as any).entities.values()),
          Array.from((this.state as any).facts.values()),
          Array.from((this.state as any).events.values()),
        );
      } catch (err) {
        console.error('[WorldIntelligence] Auto-refresh error:', err);
      }
    }, intervalMs);
    this.refreshTimers.set('main', timer);
  }

  stopAutoRefresh(): void {
    for (const [key, timer] of this.refreshTimers) {
      clearInterval(timer);
      this.refreshTimers.delete(key);
    }
  }

  async refresh(): Promise<void> {
    await this.ingestAll();
  }

  // ==========================================================================
  // Persistence API
  // ==========================================================================

  async save(): Promise<void> {
    await this.persistence.persistAll(
      Array.from((this.state as any).entities.values()),
      Array.from((this.state as any).facts.values()),
      Array.from((this.state as any).events.values()),
    );
  }

  async createSnapshot(): Promise<WorldStateSnapshot> {
    const snapshot = this.state.createSnapshot();
    await this.persistence.persistSnapshot(snapshot);
    return snapshot;
  }

  async restoreSnapshot(timestamp: string): Promise<boolean> {
    const snapshot = await this.persistence.loadLatestSnapshot();
    if (!snapshot || snapshot.timestamp !== timestamp) return false;
    return this.state.restoreSnapshot(timestamp);
  }

  // ==========================================================================
  // Diagnostics
  // ==========================================================================

  getDataQuality(): DataQualityMetrics {
    return this.state.getDataQuality();
  }

  getStats() {
    return {
      state: this.state.getStats(),
      graph: this.graph.getStats(),
      dedup: this.dedup.getStats(),
      watcher: this.watcher.getStats(),
      resolver: this.resolver.getStats(),
      ingestionHistory: this.ingestion.getIngestionHistory(10),
    };
  }

  async getHealth(): Promise<{ status: string; stats: ReturnType<typeof this.getStats>; persistenceValid: boolean }> {
    const stats = this.getStats();
    const validation = await this.persistence.validateData();
    return {
      status: 'healthy',
      stats,
      persistenceValid: validation.valid,
    };
  }

  // ==========================================================================
  // Event System
  // ==========================================================================

  on(eventType: WorldEngineEventType, handler: (event: WorldEngineEvent) => void): () => void {
    this.eventHandlers.push(handler);
    return () => {
      this.eventHandlers = this.eventHandlers.filter(h => h !== handler);
    };
  }

  // ==========================================================================
  // Cleanup
  // ==========================================================================

  async shutdown(): Promise<void> {
    this.stopAutoRefresh();
    await this.save();
  }

  // ==========================================================================
  // Private
  // ==========================================================================

  private wireEvents(): void {
    this.state.on('entity_created', (e) => this.emit(e));
    this.state.on('entity_updated', (e) => this.emit(e));
    this.state.on('fact_created', (e) => this.emit(e));
    this.state.on('fact_retracted', (e) => this.emit(e));
    this.state.on('event_ingested', (e) => this.emit(e));
    this.state.on('snapshot_created', (e) => this.emit(e));
  }

  private emit(event: WorldEngineEvent): void {
    for (const handler of this.eventHandlers) {
      try { handler(event); } catch { /* ignore */ }
    }
  }

  private registerBuiltinProviders(): void {
    // Register real free providers for live world data ingestion
    const defaultProviders = createDefaultProviders();
    for (const provider of defaultProviders) {
      this.ingestion.registerProvider(provider);
      this.liveIngestion.registerProvider(provider);
    }
    // Register news providers (no API keys needed for basic operation)
    const newsProviders = createNewsProviders();
    for (const provider of newsProviders) {
      this.ingestion.registerProvider(provider);
      this.liveIngestion.registerProvider(provider);
    }
  }

  // ==========================================================================
  // Phase 22 — Live Ingestion Processing
  // ==========================================================================

  private async processIngestedData(providerId: string, data: import('./contracts').RawWorldData): Promise<import('./contracts').IngestionResult> {
    let entitiesFound = 0, factsFound = 0, eventsFound = 0, duplicatesSkipped = 0;
    for (const item of data.items) {
      // LLM-enhanced extraction for substantial text
      const text = [item.title || '', item.summary || ''].join(' ');
      const extraction = text.length > 50
        ? await this.llmExtraction.extractFromText(text, providerId)
        : this.llmExtraction.extractFromText(text, providerId);
      // Process extracted entities
      const entityIds: string[] = [];
      for (const ext of extraction.entities) {
        const resolved = this.resolver.resolve(ext.name, ext.entityType);
        if (resolved.length > 0 && resolved[0].score >= 0.8) {
          entityIds.push(resolved[0].entityId);
        } else {
          const created = this.state.createEntity(ext.entityType, ext.name, [], {
            importance: ext.confidence > 0.7 ? 'HIGH' : 'MEDIUM',
          });
          this.resolver.indexEntity(created);
          this.semanticSearch.indexEntity(created);
          entityIds.push(created.id);
          entitiesFound++;
        }
      }
      // Process extracted events
      for (const ext of extraction.events) {
        const resolvedEntityIds = ext.entityNames
          .map(name => this.resolver.resolve(name)[0]?.entityId)
          .filter(Boolean) as string[];
        // Dedup check
        const recent = this.state.getRecentEvents(24);
        const isDupe = recent.some(e =>
          e.type === ext.type &&
          this.dedup.computeTitleSimilarity(e.title, ext.title) > 0.85
        );
        if (isDupe) { duplicatesSkipped++; continue; }
        const event = this.state.createEvent(ext.type, ext.title, ext.summary, resolvedEntityIds, item.publishedAt || nowISO(), {
          importance: ext.importance,
          confidence: ext.confidence,
          topicIds: [...ext.topics],
          sources: [{
            sourceId: providerId,
            providerId,
            sourceClass: 'SECONDARY',
            url: item.sourceUrl,
            title: item.title,
            retrievedAt: data.retrievedAt,
            publishedAt: item.publishedAt,
          }],
        });
        this.dedup.registerEvent(event);
        this.semanticSearch.indexEvent(event);
        // Evaluate watchers
        const alerts = this.watcher.evaluate(event);
        if (alerts.length > 0) {
          for (const handler of this.eventHandlers) {
            handler({ type: 'watcher_triggered', timestamp: nowISO(), data: { alerts, eventId: event.id } });
          }
        }
        eventsFound++;
      }
      // Process extracted facts
      for (const ext of extraction.facts) {
        const subjectEntity = this.resolver.resolve(ext.subjectName)[0];
        if (!subjectEntity) continue;
        const existingFacts = this.state.getFactsBySubject(subjectEntity.entityId);
        const isDupe = existingFacts.some(f =>
          f.predicate === ext.predicate && f.status === 'ACTIVE'
        );
        if (isDupe) { duplicatesSkipped++; continue; }
        this.state.createFact(subjectEntity.entityId, ext.predicate, {
          objectValue: ext.objectValue,
          observationStatus: ext.observationStatus,
          knowledgeLevel: ext.knowledgeLevel,
          confidence: ext.confidence,
          provenance: [{
            sourceId: providerId,
            sourceClass: 'SECONDARY',
            providerId,
            retrievedAt: data.retrievedAt,
            publishedAt: item.publishedAt,
            confidence: ext.confidence,
            verificationStatus: 'UNVERIFIED',
          }],
        });
        factsFound++;
      }
    }
    return {
      sourceId: providerId,
      success: true,
      entitiesFound,
      factsFound,
      eventsFound,
      duplicatesSkipped,
      conflictsDetected: 0,
      errors: [],
      ingestedAt: nowISO(),
      durationMs: 0,
    };
  }

  // ==========================================================================
  // Phase 22 — Semantic/Hybrid Search
  // ==========================================================================

  searchHybrid(query: string, options: {
    limit?: number;
    type?: 'entity' | 'fact' | 'event';
    freshnessBoost?: boolean;
    timeRange?: { from?: string; to?: string };
  } = {}): { results: import('./semantic_search').SemanticResult[]; totalIndexed: number } {
    return this.semanticSearch.search(query, options);
  }

  // ==========================================================================
  // Phase 22 — Evidence Packaging
  // ==========================================================================

  buildEvidence(query: string, answer: string): EvidencePack {
    const builder = new EvidencePackBuilder();
    builder.setQuery(query);
    // Add relevant entities
    const entities = this.searchEntities(query, 5);
    for (const e of entities) builder.addEntity(e);
    // Add relevant events
    const events = this.state.getRecentEvents(48, 10);
    for (const e of events) builder.addEvent(e);
    // Add relevant facts
    for (const e of entities) {
      const facts = this.state.getFactsBySubject(e.id);
      for (const f of facts) builder.addFact(f);
    }
    return builder.build(answer);
  }

  getBrainContext(query: string, answer: string): BrainWorldContext {
    const pack = this.buildEvidence(query, answer);
    return buildBrainContext(pack);
  }

  // ==========================================================================
  // Phase 22 — LLM Extraction
  // ==========================================================================

  async extractFromText(text: string, sourceId: string): Promise<import('./llm_extraction').ExtractionResult> {
    return this.llmExtraction.extractWithLlm(text, sourceId);
  }
}

// ============================================================================
// Re-exports
// ============================================================================

export { WorldStateEngine } from './world_state_engine';
export { EntityResolver } from './entity_resolution';
export { WorldIngestionEngine } from './ingestion';
export { DeduplicationEngine } from './deduplication';
export { KnowledgeGraphEngine } from './knowledge_graph';
export { WorldQueryEngine } from './query_engine';
export { WorldWatcherEngine } from './watcher';
export { WorldPersistenceEngine } from './persistence';
export { LiveIngestionEngine } from './live_ingestion';
export { HybridSearchEngine, SemanticIndex } from './semantic_search';
export { LlmExtractionEngine } from './llm_extraction';
export { EvidencePackBuilder, buildBrainContext } from './evidence';
export type { BrainWorldContext, EvidencePack } from './evidence';
export * from './contracts';
