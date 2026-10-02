// ============================================================================
// MYRAA World State Engine — Core State Management
// ============================================================================

import {
  WorldEntity, EntityIdentity, EntityAlias, EntityType,
  TemporalFact, FactProvenance, FactStatus, ObservationStatus,
  WorldEvent, EventSource, WorldEventType, EventStatus,
  ImportanceLevel, FreshnessClass, StalenessStatus,
  KnowledgeLevel, SourceClass, VerificationStatus,
  KnowledgeGraph, GraphNode, GraphEdge, RelationshipType,
  WorldStateSnapshot, WorldStateDiff,
  WorldEngineEvent, WorldEngineEventType,
  WorldIntelligenceConfig, DEFAULT_WORLD_CONFIG,
  DataQualityMetrics,
  generateWorldId, nowISO, computeChecksum,
} from './contracts';

// ============================================================================
// WorldStateEngine
// ============================================================================

export class WorldStateEngine {
  private entities: Map<string, WorldEntity> = new Map();
  private facts: Map<string, TemporalFact> = new Map();
  private events: Map<string, WorldEvent> = new Map();
  private graph: KnowledgeGraph = { nodes: new Map(), edges: new Map(), adjacency: new Map() };
  private snapshots: WorldStateSnapshot[] = [];
  private eventLog: WorldEngineEvent[] = [];
  private config: WorldIntelligenceConfig;
  private aliasIndex: Map<string, Set<string>> = new Map(); // alias lowercase -> entity IDs
  private entityNameIndex: Map<string, Set<string>> = new Map(); // name lowercase -> entity IDs
  private eventTypeIndex: Map<string, Set<string>> = new Map(); // event type -> event IDs
  private eventTimeIndex: string[] = []; // sorted event IDs by timestamp
  private factSubjectIndex: Map<string, Set<string>> = new Map(); // subject ID -> fact IDs
  private topicIndex: Map<string, Set<string>> = new Map(); // topic -> event IDs
  private entityEventIndex: Map<string, Set<string>> = new Map(); // entity ID -> event IDs
  private graphEdgeBySource: Map<string, Set<string>> = new Map();
  private graphEdgeByTarget: Map<string, Set<string>> = new Map();
  private eventHandlers: Map<string, ((event: WorldEngineEvent) => void)[]> = new Map();

  constructor(config?: Partial<WorldIntelligenceConfig>) {
    this.config = { ...DEFAULT_WORLD_CONFIG, ...config };
  }

  // ==========================================================================
  // Entity Operations
  // ==========================================================================

  createEntity(
    entityType: EntityType,
    canonicalName: string,
    aliases?: EntityAlias[],
    options?: {
      importance?: ImportanceLevel;
      tags?: string[];
      metadata?: Record<string, unknown>;
      subType?: string;
    }
  ): WorldEntity {
    const id = generateWorldId();
    const now = nowISO();
    const allAliases: EntityAlias[] = [
      { name: canonicalName, type: 'canonical' },
      ...(aliases || []),
    ];
    const identity: EntityIdentity = {
      canonicalId: id,
      canonicalName,
      aliases: allAliases,
      entityType,
      subType: options?.subType,
    };
    const entity: WorldEntity = {
      id,
      identity,
      createdAt: now,
      updatedAt: now,
      importance: options?.importance || 'MEDIUM',
      tags: options?.tags || [],
      metadata: options?.metadata || {},
      knownFacts: [],
      knownEvents: [],
      knowledgeLevel: 'CURRENT',
    };
    this.entities.set(id, entity);
    this.updateEntityIndex(entity);
    this.emitEvent({ type: 'entity_created', timestamp: now, data: { entityId: id, entityType, canonicalName } });
    return entity;
  }

  updateEntity(id: string, updates: Partial<Omit<WorldEntity, 'id' | 'createdAt'>>): WorldEntity | null {
    const existing = this.entities.get(id);
    if (!existing) return null;
    const now = nowISO();
    const updated: WorldEntity = {
      ...existing,
      ...updates,
      updatedAt: now,
    };
    this.entities.set(id, updated);
    this.updateEntityIndex(updated);
    this.emitEvent({ type: 'entity_updated', timestamp: now, data: { entityId: id } });
    return updated;
  }

  getEntity(id: string): WorldEntity | undefined {
    return this.entities.get(id);
  }

  findEntitiesByName(name: string): WorldEntity[] {
    const lower = name.toLowerCase();
    const ids = this.entityNameIndex.get(lower) || new Set();
    return Array.from(ids).map(id => this.entities.get(id)!).filter(Boolean);
  }

  findEntitiesByAlias(alias: string): WorldEntity[] {
    const lower = alias.toLowerCase();
    const ids = this.aliasIndex.get(lower) || new Set();
    return Array.from(ids).map(id => this.entities.get(id)!).filter(Boolean);
  }

  findEntitiesByType(entityType: EntityType): WorldEntity[] {
    return Array.from(this.entities.values()).filter(e => e.identity.entityType === entityType);
  }

  searchEntities(query: string, limit = 20): WorldEntity[] {
    const lower = query.toLowerCase();
    const results: { entity: WorldEntity; score: number }[] = [];
    for (const entity of this.entities.values()) {
      let score = 0;
      const name = entity.identity.canonicalName.toLowerCase();
      if (name === lower) score = 100;
      else if (name.startsWith(lower)) score = 80;
      else if (name.includes(lower)) score = 60;
      else {
        for (const alias of entity.identity.aliases) {
          const an = alias.name.toLowerCase();
          if (an === lower) { score = 70; break; }
          if (an.includes(lower)) { score = Math.max(score, 40); }
        }
      }
      if (score > 0) results.push({ entity, score });
    }
    return results.sort((a, b) => b.score - a.score).slice(0, limit).map(r => r.entity);
  }

  mergeEntities(sourceId: string, targetId: string): WorldEntity | null {
    const source = this.entities.get(sourceId);
    const target = this.entities.get(targetId);
    if (!source || !target) return null;
    const now = nowISO();
    const mergedAliases: EntityAlias[] = [
      ...target.identity.aliases,
      ...source.identity.aliases.filter(sa =>
        !target.identity.aliases.some(ta => ta.name.toLowerCase() === sa.name.toLowerCase())
      ),
    ];
    const merged: WorldEntity = {
      ...target,
      identity: {
        ...target.identity,
        aliases: mergedAliases,
      },
      knownFacts: [...new Set([...target.knownFacts, ...source.knownFacts])],
      knownEvents: [...new Set([...target.knownEvents, ...source.knownEvents])],
      tags: [...new Set([...target.tags, ...source.tags])],
      metadata: { ...source.metadata, ...target.metadata, mergedFrom: [sourceId] },
      updatedAt: now,
    };
    this.entities.set(targetId, merged);
    this.entities.delete(sourceId);
    this.updateEntityIndex(merged);
    // Update graph edges pointing to source
    this.redirectGraphEdges(sourceId, targetId);
    this.emitEvent({ type: 'entity_merged', timestamp: now, data: { sourceId, targetId } });
    return merged;
  }

  splitEntity(entityId: string, splits: { id: string; canonicalName: string; facts: string[]; events: string[] }[]): WorldEntity[] {
    const original = this.entities.get(entityId);
    if (!original) return [];
    const now = nowISO();
    const results: WorldEntity[] = [];
    for (const split of splits) {
      const splitEntity = this.createEntity(original.identity.entityType, split.canonicalName, [], {
        importance: original.importance,
        tags: [...original.tags],
        metadata: { ...original.metadata, splitFrom: entityId },
      });
      // Re-assign facts and events
      for (const factId of split.facts) {
        const fact = this.facts.get(factId);
        if (fact && fact.subjectId === entityId) {
          this.facts.set(factId, { ...fact, subjectId: splitEntity.id, updatedAt: now });
        }
      }
      for (const eventId of split.events) {
        const event = this.events.get(eventId);
        if (event) {
          const newEntityIds = [...event.entityIds].map(eid => eid === entityId ? splitEntity.id : eid);
          this.events.set(eventId, { ...event, entityIds: newEntityIds, retrievedAt: now });
        }
      }
      results.push(splitEntity);
    }
    this.emitEvent({ type: 'entity_split', timestamp: now, data: { entityId, splitCount: splits.length } });
    return results;
  }

  // ==========================================================================
  // Fact Operations
  // ==========================================================================

  createFact(
    subjectId: string,
    predicate: string,
    options: {
      objectId?: string;
      objectValue?: string | number | boolean;
      validFrom?: string;
      validTo?: string;
      observationStatus?: ObservationStatus;
      knowledgeLevel?: KnowledgeLevel;
      provenance?: FactProvenance[];
      confidence?: number;
      metadata?: Record<string, unknown>;
    } = {}
  ): TemporalFact {
    const id = generateWorldId();
    const now = nowISO();
    const fact: TemporalFact = {
      id,
      subjectId,
      predicate,
      objectId: options.objectId,
      objectValue: options.objectValue,
      status: 'ACTIVE',
      observationStatus: options.observationStatus || 'UNKNOWN',
      validFrom: options.validFrom || now,
      validTo: options.validTo,
      createdAt: now,
      updatedAt: now,
      provenance: options.provenance || [],
      confidence: options.confidence ?? 0.5,
      knowledgeLevel: options.knowledgeLevel || 'CURRENT',
      metadata: options.metadata || {},
    };
    this.facts.set(id, fact);
    this.updateFactIndex(fact);
    this.emitEvent({ type: 'fact_created', timestamp: now, data: { factId: id, subjectId, predicate } });
    return fact;
  }

  updateFact(id: string, updates: Partial<Omit<TemporalFact, 'id' | 'createdAt'>>): TemporalFact | null {
    const existing = this.facts.get(id);
    if (!existing) return null;
    const now = nowISO();
    const updated: TemporalFact = { ...existing, ...updates, updatedAt: now };
    this.facts.set(id, updated);
    this.updateFactIndex(updated);
    this.emitEvent({ type: 'fact_updated', timestamp: now, data: { factId: id } });
    return updated;
  }

  retractFact(id: string, reason: string): TemporalFact | null {
    const existing = this.facts.get(id);
    if (!existing) return null;
    const now = nowISO();
    const retracted: TemporalFact = {
      ...existing,
      status: 'RETRACTED',
      validTo: now,
      updatedAt: now,
      metadata: { ...existing.metadata, retractionReason: reason },
    };
    this.facts.set(id, retracted);
    this.emitEvent({ type: 'fact_retracted', timestamp: now, data: { factId: id, reason } });
    return retracted;
  }

  supersedeFact(oldFactId: string, newFact: Omit<TemporalFact, 'id' | 'createdAt' | 'updatedAt'>): TemporalFact {
    const old = this.facts.get(oldFactId);
    if (old) {
      this.updateFact(oldFactId, { status: 'SUPERSEDED', validTo: nowISO() });
    }
    const id = generateWorldId();
    const now = nowISO();
    const fact: TemporalFact = { ...newFact, id, createdAt: now, updatedAt: now };
    this.facts.set(id, fact);
    this.updateFactIndex(fact);
    return fact;
  }

  getFact(id: string): TemporalFact | undefined {
    return this.facts.get(id);
  }

  getFactsBySubject(subjectId: string): TemporalFact[] {
    const ids = this.factSubjectIndex.get(subjectId) || new Set();
    return Array.from(ids).map(id => this.facts.get(id)!).filter(Boolean);
  }

  getCurrentFact(subjectId: string, predicate: string): TemporalFact | undefined {
    const now = nowISO();
    const factIds = this.factSubjectIndex.get(subjectId) || new Set();
    let best: TemporalFact | undefined;
    for (const fid of factIds) {
      const fact = this.facts.get(fid);
      if (!fact || fact.predicate !== predicate || fact.status !== 'ACTIVE') continue;
      if (fact.validTo && fact.validTo < now) continue;
      if (!best || fact.validFrom > best.validFrom) best = fact;
    }
    return best;
  }

  getHistoricalFacts(subjectId: string, predicate: string, atTime: string): TemporalFact[] {
    const factIds = this.factSubjectIndex.get(subjectId) || new Set();
    const results: TemporalFact[] = [];
    for (const fid of factIds) {
      const fact = this.facts.get(fid);
      if (!fact || fact.predicate !== predicate) continue;
      if (fact.validFrom <= atTime && (!fact.validTo || fact.validTo >= atTime)) {
        results.push(fact);
      }
    }
    return results;
  }

  // ==========================================================================
  // Event Operations
  // ==========================================================================

  createEvent(
    type: WorldEventType,
    title: string,
    summary: string,
    entityIds: string[],
    timestamp: string,
    options: {
      publishedAt?: string;
      location?: WorldEvent['location'];
      importance?: ImportanceLevel;
      confidence?: number;
      sources?: EventSource[];
      topicIds?: string[];
      relatedEventIds?: string[];
      tags?: string[];
      metadata?: Record<string, unknown>;
      freshnessClass?: FreshnessClass;
      observationStatus?: ObservationStatus;
    } = {}
  ): WorldEvent {
    const id = generateWorldId();
    const now = nowISO();
    const event: WorldEvent = {
      id,
      type,
      title,
      summary,
      entityIds,
      timestamp,
      publishedAt: options.publishedAt,
      retrievedAt: now,
      location: options.location,
      importance: options.importance || 'MEDIUM',
      status: 'ACTIVE',
      confidence: options.confidence ?? 0.5,
      sources: options.sources || [],
      topicIds: options.topicIds || [],
      relatedEventIds: options.relatedEventIds || [],
      tags: options.tags || [],
      metadata: options.metadata || {},
      freshnessClass: options.freshnessClass || 'UNKNOWN',
      staleness: 'CURRENT',
      observationStatus: options.observationStatus || 'UNKNOWN',
    };
    this.events.set(id, event);
    this.updateEventIndex(event);
    this.emitEvent({ type: 'event_ingested', timestamp: now, data: { eventId: id, eventType: type, title } });
    return event;
  }

  updateEvent(id: string, updates: Partial<Omit<WorldEvent, 'id' | 'createdAt'>>): WorldEvent | null {
    const existing = this.events.get(id);
    if (!existing) return null;
    const now = nowISO();
    const updated: WorldEvent = { ...existing, ...updates, retrievedAt: now };
    this.events.set(id, updated);
    this.updateEventIndex(updated);
    this.emitEvent({ type: 'event_status_changed', timestamp: now, data: { eventId: id } });
    return updated;
  }

  getEvent(id: string): WorldEvent | undefined {
    return this.events.get(id);
  }

  getEventsByType(type: WorldEventType, limit = 50): WorldEvent[] {
    const ids = this.eventTypeIndex.get(type) || new Set();
    return Array.from(ids)
      .map(id => this.events.get(id)!)
      .filter(Boolean)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
      .slice(0, limit);
  }

  getEventsByEntity(entityId: string, limit = 50): WorldEvent[] {
    const ids = this.entityEventIndex.get(entityId) || new Set();
    return Array.from(ids)
      .map(id => this.events.get(id)!)
      .filter(Boolean)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
      .slice(0, limit);
  }

  getEventsByTopic(topic: string, limit = 50): WorldEvent[] {
    const ids = this.topicIndex.get(topic.toLowerCase()) || new Set();
    return Array.from(ids)
      .map(id => this.events.get(id)!)
      .filter(Boolean)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
      .slice(0, limit);
  }

  getRecentEvents(hours = 24, limit = 100): WorldEvent[] {
    const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
    return Array.from(this.events.values())
      .filter(e => e.timestamp >= cutoff || (e.publishedAt && e.publishedAt >= cutoff))
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
      .slice(0, limit);
  }

  correlateEvents(eventIds: string[]): void {
    for (let i = 0; i < eventIds.length; i++) {
      const event = this.events.get(eventIds[i]);
      if (!event) continue;
      const related = eventIds.filter((_, j) => j !== i);
      const updatedRelated = [...new Set([...event.relatedEventIds, ...related])];
      this.events.set(eventIds[i], { ...event, relatedEventIds: updatedRelated });
    }
    this.emitEvent({ type: 'event_correlated', timestamp: nowISO(), data: { eventIds } });
  }

  // ==========================================================================
  // Knowledge Graph Operations
  // ==========================================================================

  addGraphNode(type: GraphNode['type'], label: string, metadata: Record<string, unknown> = {}): GraphNode {
    const id = generateWorldId();
    const now = nowISO();
    const node: GraphNode = { id, type, label, metadata, createdAt: now, updatedAt: now };
    this.graph.nodes.set(id, node);
    this.graph.adjacency.set(id, new Set());
    this.emitEvent({ type: 'graph_updated', timestamp: now, data: { nodeId: id, nodeType: type } });
    return node;
  }

  addGraphEdge(
    sourceId: string,
    targetId: string,
    relationship: RelationshipType,
    options: {
      observationStatus?: ObservationStatus;
      confidence?: number;
      validFrom?: string;
      validTo?: string;
      sourceRef?: string;
      metadata?: Record<string, unknown>;
    } = {}
  ): GraphEdge | null {
    if (!this.graph.nodes.has(sourceId) || !this.graph.nodes.has(targetId)) return null;
    const id = generateWorldId();
    const now = nowISO();
    const edge: GraphEdge = {
      id,
      sourceId,
      targetId,
      relationship,
      observationStatus: options.observationStatus || 'UNKNOWN',
      confidence: options.confidence ?? 0.5,
      validFrom: options.validFrom || now,
      validTo: options.validTo,
      sourceRef: options.sourceRef || '',
      metadata: options.metadata || {},
    };
    this.graph.edges.set(id, edge);
    // Update adjacency
    const srcAdj = this.graph.adjacency.get(sourceId) || new Set();
    srcAdj.add(id);
    this.graph.adjacency.set(sourceId, srcAdj);
    const tgtAdj = this.graph.adjacency.get(targetId) || new Set();
    tgtAdj.add(id);
    this.graph.adjacency.set(targetId, tgtAdj);
    // Update edge indexes
    const bySrc = this.graphEdgeBySource.get(sourceId) || new Set();
    bySrc.add(id);
    this.graphEdgeBySource.set(sourceId, bySrc);
    const byTgt = this.graphEdgeByTarget.get(targetId) || new Set();
    byTgt.add(id);
    this.graphEdgeByTarget.set(targetId, byTgt);
    this.emitEvent({ type: 'graph_updated', timestamp: now, data: { edgeId: id, relationship } });
    return edge;
  }

  getGraphNode(id: string): GraphNode | undefined {
    return this.graph.nodes.get(id);
  }

  getGraphEdges(nodeId: string): GraphEdge[] {
    const edgeIds = this.graph.adjacency.get(nodeId) || new Set();
    return Array.from(edgeIds).map(id => this.graph.edges.get(id)!).filter(Boolean);
  }

  getGraphEdgesByType(relationship: RelationshipType): GraphEdge[] {
    return Array.from(this.graph.edges.values()).filter(e => e.relationship === relationship);
  }

  findGraphPath(sourceId: string, targetId: string, maxDepth = 5): GraphEdge[][] {
    const paths: GraphEdge[][] = [];
    const queue: { nodeId: string; path: GraphEdge[] }[] = [{ nodeId: sourceId, path: [] }];
    const visited = new Set<string>();
    while (queue.length > 0 && paths.length < 10) {
      const { nodeId, path } = queue.shift()!;
      if (nodeId === targetId && path.length > 0) {
        paths.push(path);
        continue;
      }
      if (path.length >= maxDepth) continue;
      visited.add(nodeId);
      const edgeIds = this.graph.adjacency.get(nodeId) || new Set();
      for (const edgeId of edgeIds) {
        const edge = this.graph.edges.get(edgeId);
        if (!edge) continue;
        const nextId = edge.sourceId === nodeId ? edge.targetId : edge.sourceId;
        if (!visited.has(nextId)) {
          queue.push({ nodeId: nextId, path: [...path, edge] });
        }
      }
    }
    return paths;
  }

  // ==========================================================================
  // World State Operations
  // ==========================================================================

  createSnapshot(): WorldStateSnapshot {
    const now = nowISO();
    const checksum = computeChecksum(JSON.stringify({
      entityCount: this.entities.size,
      factCount: this.facts.size,
      eventCount: this.events.size,
      timestamp: now,
    }));
    const snapshot: WorldStateSnapshot = {
      timestamp: now,
      entities: new Map(this.entities),
      facts: new Map(this.facts),
      events: new Map(this.events),
      graph: {
        nodes: new Map(this.graph.nodes),
        edges: new Map(this.graph.edges),
        adjacency: new Map(this.graph.adjacency),
      },
      checksum,
    };
    this.snapshots.push(snapshot);
    // Keep only last 24 snapshots
    if (this.snapshots.length > 24) {
      this.snapshots = this.snapshots.slice(-24);
    }
    this.emitEvent({ type: 'snapshot_created', timestamp: now, data: { checksum } });
    return snapshot;
  }

  restoreSnapshot(snapshotTimestamp: string): boolean {
    const snapshot = this.snapshots.find(s => s.timestamp === snapshotTimestamp);
    if (!snapshot) return false;
    this.entities = new Map(snapshot.entities);
    this.facts = new Map(snapshot.facts);
    this.events = new Map(snapshot.events);
    this.graph = {
      nodes: new Map(snapshot.graph.nodes),
      edges: new Map(snapshot.graph.edges),
      adjacency: new Map(snapshot.graph.adjacency),
    };
    this.rebuildIndexes();
    this.emitEvent({ type: 'snapshot_restored', timestamp: nowISO(), data: { snapshotTimestamp } });
    return true;
  }

  getDiff(fromTimestamp: string, toTimestamp?: string): WorldStateDiff {
    const to = toTimestamp || nowISO();
    const fromSnap = this.snapshots.find(s => s.timestamp >= fromTimestamp);
    const fromEntities = fromSnap?.entities || new Map();
    const fromFacts = fromSnap?.facts || new Map();
    const fromEvents = fromSnap?.events || new Map();

    const addedEntities = Array.from(this.entities.values()).filter(e => !fromEntities.has(e.id));
    const removedEntities = Array.from(fromEntities.keys()).filter(id => !this.entities.has(id));
    const changedEntities: { entity: WorldEntity; changes: string[] }[] = [];
    for (const [id, entity] of this.entities) {
      const from = fromEntities.get(id);
      if (from && JSON.stringify(from) !== JSON.stringify(entity)) {
        changedEntities.push({ entity, changes: this.detectChanges(from, entity) });
      }
    }

    const addedFacts = Array.from(this.facts.values()).filter(f => !fromFacts.has(f.id));
    const removedFacts = Array.from(fromFacts.keys()).filter(id => !this.facts.has(id));
    const changedFacts: { fact: TemporalFact; changes: string[] }[] = [];
    for (const [id, fact] of this.facts) {
      const from = fromFacts.get(id);
      if (from && JSON.stringify(from) !== JSON.stringify(fact)) {
        changedFacts.push({ fact, changes: this.detectChanges(from, fact) });
      }
    }

    const addedEvents = Array.from(this.events.values()).filter(e => !fromEvents.has(e.id));
    const removedEvents = Array.from(fromEvents.keys()).filter(id => !this.events.has(id));

    return {
      fromTimestamp,
      toTimestamp: to,
      addedEntities,
      removedEntities,
      changedEntities,
      addedFacts,
      removedFacts,
      changedFacts,
      addedEvents,
      removedEvents,
      newTopicIds: [],
    };
  }

  // ==========================================================================
  // Data Quality
  // ==========================================================================

  getDataQuality(): DataQualityMetrics {
    const now = nowISO();
    const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    let activeFacts = 0, expiredFacts = 0, retractedFacts = 0, conflictingFacts = 0;
    let totalConfidence = 0;
    const sourceDistribution: Record<string, number> = {};
    const freshnessDistribution: Record<FreshnessClass, number> = {
      REALTIME: 0, MINUTES: 0, HOURLY: 0, DAILY: 0, STATIC: 0, HISTORICAL: 0, UNKNOWN: 0,
    };
    const eventStatusDistribution: Record<EventStatus, number> = {
      EMERGING: 0, ACTIVE: 0, DEVELOPING: 0, STABLE: 0, RESOLVED: 0, STALE: 0, RETRACTED: 0,
    };

    for (const fact of this.facts.values()) {
      if (fact.status === 'ACTIVE') activeFacts++;
      else if (fact.status === 'SUPERSEDED') expiredFacts++;
      else if (fact.status === 'RETRACTED') retractedFacts++;
      else if (fact.status === 'CONFLICTED') conflictingFacts++;
      totalConfidence += fact.confidence;
      for (const p of fact.provenance) {
        sourceDistribution[p.providerId] = (sourceDistribution[p.providerId] || 0) + 1;
      }
    }

    for (const event of this.events.values()) {
      eventStatusDistribution[event.status]++;
      freshnessDistribution[event.freshnessClass]++;
    }

    let totalAliases = 0;
    for (const entity of this.entities.values()) {
      totalAliases += entity.identity.aliases.length;
    }

    let ingestionCount = 0;
    for (const event of this.events.values()) {
      if (event.retrievedAt >= dayAgo) ingestionCount++;
    }

    const deduplicationRate = this.events.size > 0
      ? 1 - (this.events.size / Math.max(1, this.events.size * 1.2)) // rough estimate
      : 0;

    return {
      totalEntities: this.entities.size,
      totalFacts: this.facts.size,
      totalEvents: this.events.size,
      activeFacts,
      expiredFacts,
      retractedFacts,
      conflictingFacts,
      avgFactConfidence: this.facts.size > 0 ? totalConfidence / this.facts.size : 0,
      avgEntityAliases: this.entities.size > 0 ? totalAliases / this.entities.size : 0,
      sourceDistribution,
      freshnessDistribution,
      eventStatusDistribution,
      lastIngestionAt: this.eventLog.filter(e => e.type === 'ingestion_completed').pop()?.timestamp,
      ingestionCount24h: ingestionCount,
      deduplicationRate,
    };
  }

  // ==========================================================================
  // Statistics
  // ==========================================================================

  getStats() {
    return {
      entities: this.entities.size,
      facts: this.facts.size,
      events: this.events.size,
      graphNodes: this.graph.nodes.size,
      graphEdges: this.graph.edges.size,
      snapshots: this.snapshots.length,
      eventLogSize: this.eventLog.length,
    };
  }

  // ==========================================================================
  // Event Emitter
  // ==========================================================================

  on(eventType: WorldEngineEventType, handler: (event: WorldEngineEvent) => void): () => void {
    const handlers = this.eventHandlers.get(eventType) || [];
    handlers.push(handler);
    this.eventHandlers.set(eventType, handlers);
    return () => {
      const h = this.eventHandlers.get(eventType) || [];
      this.eventHandlers.set(eventType, h.filter(fn => fn !== handler));
    };
  }

  private emitEvent(event: WorldEngineEvent): void {
    this.eventLog.push(event);
    if (this.eventLog.length > 10_000) {
      this.eventLog = this.eventLog.slice(-5_000);
    }
    const handlers = this.eventHandlers.get(event.type) || [];
    for (const handler of handlers) {
      try { handler(event); } catch { /* ignore handler errors */ }
    }
  }

  // ==========================================================================
  // Private Helpers
  // ==========================================================================

  private updateEntityIndex(entity: WorldEntity): void {
    // Name index
    const nameKey = entity.identity.canonicalName.toLowerCase();
    const nameSet = this.entityNameIndex.get(nameKey) || new Set();
    nameSet.add(entity.id);
    this.entityNameIndex.set(nameKey, nameSet);
    // Alias index
    for (const alias of entity.identity.aliases) {
      const key = alias.name.toLowerCase();
      const set = this.aliasIndex.get(key) || new Set();
      set.add(entity.id);
      this.aliasIndex.set(key, set);
    }
  }

  private updateFactIndex(fact: TemporalFact): void {
    const set = this.factSubjectIndex.get(fact.subjectId) || new Set();
    set.add(fact.id);
    this.factSubjectIndex.set(fact.subjectId, set);
  }

  private updateEventIndex(event: WorldEvent): void {
    // Type index
    const typeSet = this.eventTypeIndex.get(event.type) || new Set();
    typeSet.add(event.id);
    this.eventTypeIndex.set(event.type, typeSet);
    // Entity index
    for (const eid of event.entityIds) {
      const set = this.entityEventIndex.get(eid) || new Set();
      set.add(event.id);
      this.entityEventIndex.set(eid, set);
    }
    // Topic index
    for (const topic of event.topicIds) {
      const key = topic.toLowerCase();
      const set = this.topicIndex.get(key) || new Set();
      set.add(event.id);
      this.topicIndex.set(key, set);
    }
    // Time index (maintain sorted order)
    const idx = this.eventTimeIndex.indexOf(event.id);
    if (idx === -1) {
      this.eventTimeIndex.push(event.id);
      this.eventTimeIndex.sort((a, b) => {
        const ea = this.events.get(a);
        const eb = this.events.get(b);
        return (ea?.timestamp || '').localeCompare(eb?.timestamp || '');
      });
    }
  }

  private redirectGraphEdges(fromId: string, toId: string): void {
    for (const [edgeId, edge] of this.graph.edges) {
      if (edge.sourceId === fromId || edge.targetId === fromId) {
        const updated = {
          ...edge,
          sourceId: edge.sourceId === fromId ? toId : edge.sourceId,
          targetId: edge.targetId === fromId ? toId : edge.targetId,
        };
        this.graph.edges.set(edgeId, updated);
      }
    }
  }

  private rebuildIndexes(): void {
    this.aliasIndex.clear();
    this.entityNameIndex.clear();
    this.eventTypeIndex.clear();
    this.eventTimeIndex = [];
    this.factSubjectIndex.clear();
    this.topicIndex.clear();
    this.entityEventIndex.clear();
    this.graphEdgeBySource.clear();
    this.graphEdgeByTarget.clear();
    for (const entity of this.entities.values()) this.updateEntityIndex(entity);
    for (const fact of this.facts.values()) this.updateFactIndex(fact);
    for (const event of this.events.values()) this.updateEventIndex(event);
    for (const [edgeId, edge] of this.graph.edges) {
      const bySrc = this.graphEdgeBySource.get(edge.sourceId) || new Set();
      bySrc.add(edgeId);
      this.graphEdgeBySource.set(edge.sourceId, bySrc);
      const byTgt = this.graphEdgeByTarget.get(edge.targetId) || new Set();
      byTgt.add(edgeId);
      this.graphEdgeByTarget.set(edge.targetId, byTgt);
    }
  }

  private detectChanges(a: unknown, b: unknown): string[] {
    const changes: string[] = [];
    const aObj = a as Record<string, unknown>;
    const bObj = b as Record<string, unknown>;
    const allKeys = new Set([...Object.keys(aObj), ...Object.keys(bObj)]);
    for (const key of allKeys) {
      if (JSON.stringify(aObj[key]) !== JSON.stringify(bObj[key])) {
        changes.push(key);
      }
    }
    return changes;
  }
}
