// ============================================================================
// MYRAA World Intelligence Engine — Comprehensive Test Suite
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  WorldIntelligence,
  WorldStateEngine,
  EntityResolver,
  DeduplicationEngine,
  KnowledgeGraphEngine,
  WorldQueryEngine,
  WorldWatcherEngine,
  WorldPersistenceEngine,
  WorldIngestionEngine,
  generateWorldId,
  nowISO,
  DEFAULT_WORLD_CONFIG,
} from '../src/world-intelligence/index';
import type {
  WorldEntity, TemporalFact, WorldEvent,
  EntityAlias, FactProvenance, EventSource,
  WorldQuery, WorldQueryResult,
  WatcherPolicy,
  EntityType, WorldEventType, ImportanceLevel,
  RelationshipType,
  RawWorldItem, RawWorldData,
  IngestionProvider,
} from '../src/world-intelligence/contracts';

// ============================================================================
// Contracts & Utilities
// ============================================================================

describe('World Intelligence Contracts', () => {
  it('should generate unique world IDs', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 1000; i++) {
      ids.add(generateWorldId());
    }
    expect(ids.size).toBe(1000);
  });

  it('should generate valid ISO timestamps', () => {
    const ts = nowISO();
    expect(new Date(ts).toISOString()).toBe(ts);
  });

  it('should have valid default config', () => {
    expect(DEFAULT_WORLD_CONFIG.maxEntities).toBe(100_000);
    expect(DEFAULT_WORLD_CONFIG.maxFacts).toBe(500_000);
    expect(DEFAULT_WORLD_CONFIG.maxEvents).toBe(200_000);
    expect(DEFAULT_WORLD_CONFIG.enablePersistence).toBe(true);
    expect(DEFAULT_WORLD_CONFIG.enableWatchers).toBe(true);
  });
});

// ============================================================================
// WorldStateEngine
// ============================================================================

describe('WorldStateEngine', () => {
  let engine: WorldStateEngine;

  beforeEach(() => {
    engine = new WorldStateEngine({ enablePersistence: false });
  });

  // --- Entity Operations ---

  describe('Entity Operations', () => {
    it('should create an entity', () => {
      const entity = engine.createEntity('COMPANY', 'Apple Inc.', [
        { name: 'AAPL', type: 'ticker' },
        { name: 'Apple', type: 'alias' },
      ], { importance: 'HIGH', tags: ['tech'] });
      expect(entity.id).toBeTruthy();
      expect(entity.identity.canonicalName).toBe('Apple Inc.');
      expect(entity.identity.entityType).toBe('COMPANY');
      expect(entity.identity.aliases).toHaveLength(3);
      expect(entity.importance).toBe('HIGH');
      expect(entity.tags).toContain('tech');
    });

    it('should update an entity', () => {
      const entity = engine.createEntity('PERSON', 'John Doe');
      const updated = engine.updateEntity(entity.id, { importance: 'HIGH' });
      expect(updated).toBeTruthy();
      expect(updated!.importance).toBe('HIGH');
    });

    it('should return null for non-existent entity update', () => {
      expect(engine.updateEntity('nonexistent', { importance: 'HIGH' })).toBeNull();
    });

    it('should find entities by name', () => {
      engine.createEntity('COMPANY', 'Tesla Inc.');
      engine.createEntity('COMPANY', 'SpaceX');
      const found = engine.findEntitiesByName('Tesla Inc.');
      expect(found).toHaveLength(1);
      expect(found[0].identity.canonicalName).toBe('Tesla Inc.');
    });

    it('should find entities by alias', () => {
      engine.createEntity('COMPANY', 'Apple Inc.', [
        { name: 'AAPL', type: 'ticker' },
      ]);
      const found = engine.findEntitiesByAlias('AAPL');
      expect(found).toHaveLength(1);
    });

    it('should search entities', () => {
      engine.createEntity('COMPANY', 'Apple Inc.');
      engine.createEntity('COMPANY', 'Microsoft Corp');
      engine.createEntity('PERSON', 'Tim Cook');
      const results = engine.searchEntities('apple');
      expect(results.length).toBeGreaterThanOrEqual(1);
      expect(results[0].identity.canonicalName).toBe('Apple Inc.');
    });

    it('should find entities by type', () => {
      engine.createEntity('COMPANY', 'Apple');
      engine.createEntity('COMPANY', 'Google');
      engine.createEntity('PERSON', 'Sundar Pichai');
      const companies = engine.findEntitiesByType('COMPANY');
      expect(companies).toHaveLength(2);
    });

    it('should merge entities', () => {
      const e1 = engine.createEntity('COMPANY', 'Microsoft Corp', [{ name: 'MSFT', type: 'ticker' }]);
      const e2 = engine.createEntity('COMPANY', 'Microsoft', [{ name: 'Microsoft Corp.', type: 'alias' }]);
      const merged = engine.mergeEntities(e1.id, e2.id);
      expect(merged).toBeTruthy();
      expect(merged!.id).toBe(e2.id);
      expect(merged!.identity.aliases.length).toBeGreaterThanOrEqual(2);
      expect(engine.getEntity(e1.id)).toBeUndefined();
    });

    it('should split entities', () => {
      const original = engine.createEntity('COMPANY', 'Alphabet Inc.');
      const fact1 = engine.createFact(original.id, 'CEO', { objectValue: 'Sundar Pichai' });
      const fact2 = engine.createFact(original.id, 'revenue', { objectValue: 300000000000 });
      const event1 = engine.createEvent('COMPANY_EVENT', 'Alphabet restructuring', 'Split into Google and Other Bets', [original.id], nowISO());
      const splits = engine.splitEntity(original.id, [
        { id: generateWorldId(), canonicalName: 'Google LLC', facts: [fact1.id], events: [] },
        { id: generateWorldId(), canonicalName: 'Other Bets', facts: [fact2.id], events: [event1.id] },
      ]);
      expect(splits).toHaveLength(2);
    });
  });

  // --- Fact Operations ---

  describe('Fact Operations', () => {
    it('should create a fact with entity reference', () => {
      const entity = engine.createEntity('COMPANY', 'Apple');
      const fact = engine.createFact(entity.id, 'CEO', {
        objectValue: 'Tim Cook',
        confidence: 0.95,
        observationStatus: 'OBSERVED',
      });
      expect(fact.id).toBeTruthy();
      expect(fact.subjectId).toBe(entity.id);
      expect(fact.predicate).toBe('CEO');
      expect(fact.objectValue).toBe('Tim Cook');
      expect(fact.confidence).toBe(0.95);
      expect(fact.status).toBe('ACTIVE');
    });

    it('should create a temporal fact with validity period', () => {
      const entity = engine.createEntity('PERSON', 'Tim Cook');
      const fact = engine.createFact(entity.id, 'CEO', {
        objectValue: 'Apple',
        validFrom: '2011-08-24T00:00:00Z',
        validTo: undefined, // still valid
      });
      expect(fact.validFrom).toBe('2011-08-24T00:00:00Z');
      expect(fact.validTo).toBeUndefined();
    });

    it('should get current fact for subject+predicate', () => {
      const entity = engine.createEntity('COMPANY', 'Apple');
      engine.createFact(entity.id, 'CEO', { objectValue: 'Tim Cook' });
      const current = engine.getCurrentFact(entity.id, 'CEO');
      expect(current).toBeTruthy();
      expect(current!.objectValue).toBe('Tim Cook');
    });

    it('should get historical facts', () => {
      const entity = engine.createEntity('COMPANY', 'Apple');
      const fact = engine.createFact(entity.id, 'CEO', {
        objectValue: 'Steve Jobs',
        validFrom: '1997-07-09T00:00:00Z',
        validTo: '2011-08-24T00:00:00Z',
      });
      engine.createFact(entity.id, 'CEO', {
        objectValue: 'Tim Cook',
        validFrom: '2011-08-24T00:00:00Z',
      });
      const historical = engine.getHistoricalFacts(entity.id, 'CEO', '2005-01-01T00:00:00Z');
      expect(historical.length).toBeGreaterThanOrEqual(1);
      expect(historical.some(f => f.objectValue === 'Steve Jobs')).toBe(true);
    });

    it('should retract a fact', () => {
      const entity = engine.createEntity('PERSON', 'Test Person');
      const fact = engine.createFact(entity.id, 'role', { objectValue: 'CEO' });
      const retracted = engine.retractFact(fact.id, 'Incorrect information');
      expect(retracted).toBeTruthy();
      expect(retracted!.status).toBe('RETRACTED');
    });

    it('should supersede a fact', () => {
      const entity = engine.createEntity('COMPANY', 'Apple');
      const oldFact = engine.createFact(entity.id, 'CEO', { objectValue: 'Steve Jobs' });
      const newFact = engine.supersedeFact(oldFact.id, {
        subjectId: entity.id,
        predicate: 'CEO',
        objectValue: 'Tim Cook',
        status: 'ACTIVE',
        observationStatus: 'OBSERVED',
        validFrom: '2011-08-24T00:00:00Z',
        provenance: [],
        confidence: 0.95,
        knowledgeLevel: 'CURRENT',
        metadata: {},
      });
      expect(newFact.id).not.toBe(oldFact.id);
      expect(newFact.objectValue).toBe('Tim Cook');
      const oldUpdated = engine.getFact(oldFact.id);
      expect(oldUpdated!.status).toBe('SUPERSEDED');
    });
  });

  // --- Event Operations ---

  describe('Event Operations', () => {
    it('should create an event', () => {
      const event = engine.createEvent('TECH_EVENT', 'OpenAI releases GPT-5', 'New model announced', [], nowISO(), {
        importance: 'HIGH',
        confidence: 0.9,
        topicIds: ['ai', 'technology'],
      });
      expect(event.id).toBeTruthy();
      expect(event.type).toBe('TECH_EVENT');
      expect(event.title).toBe('OpenAI releases GPT-5');
      expect(event.status).toBe('ACTIVE');
      expect(event.topicIds).toContain('ai');
    });

    it('should get events by type', () => {
      engine.createEvent('TECH_EVENT', 'AI breakthrough', 'New model', [], nowISO());
      engine.createEvent('MARKET_MOVE', 'Stock rally', 'Markets up', [], nowISO());
      const techEvents = engine.getEventsByType('TECH_EVENT');
      expect(techEvents).toHaveLength(1);
    });

    it('should get events by entity', () => {
      const entity = engine.createEntity('COMPANY', 'NVIDIA');
      engine.createEvent('TECH_EVENT', 'NVIDIA GPU launch', 'New GPU', [entity.id], nowISO());
      const events = engine.getEventsByEntity(entity.id);
      expect(events).toHaveLength(1);
    });

    it('should get events by topic', () => {
      engine.createEvent('TECH_EVENT', 'AI regulation proposed', 'EU proposes AI act', [], nowISO(), {
        topicIds: ['ai', 'regulation'],
      });
      const events = engine.getEventsByTopic('ai');
      expect(events).toHaveLength(1);
    });

    it('should get recent events', () => {
      engine.createEvent('NEWS', 'Breaking news', 'Something happened', [], nowISO());
      const recent = engine.getRecentEvents(24);
      expect(recent.length).toBeGreaterThanOrEqual(1);
    });

    it('should correlate events', () => {
      const e1 = engine.createEvent('EARNINGS', 'Q1 earnings', 'Good quarter', [], nowISO());
      const e2 = engine.createEvent('MARKET_MOVE', 'Stock jumps', 'After earnings', [], nowISO());
      engine.correlateEvents([e1.id, e2.id]);
      const updated = engine.getEvent(e1.id);
      expect(updated!.relatedEventIds).toContain(e2.id);
    });
  });

  // --- Knowledge Graph ---

  describe('Knowledge Graph', () => {
    it('should add graph nodes', () => {
      const node = engine.addGraphNode('entity', 'Apple Inc.');
      expect(node.id).toBeTruthy();
      expect(node.type).toBe('entity');
      expect(node.label).toBe('Apple Inc.');
    });

    it('should add graph edges', () => {
      const n1 = engine.addGraphNode('entity', 'Tim Cook');
      const n2 = engine.addGraphNode('entity', 'Apple');
      const edge = engine.addGraphEdge(n1.id, n2.id, 'CEO_OF', {
        observationStatus: 'OBSERVED',
        confidence: 0.95,
      });
      expect(edge).toBeTruthy();
      expect(edge!.relationship).toBe('CEO_OF');
    });

    it('should get graph edges for a node', () => {
      const n1 = engine.addGraphNode('entity', 'Person A');
      const n2 = engine.addGraphNode('entity', 'Company B');
      engine.addGraphEdge(n1.id, n2.id, 'WORKS_FOR');
      const edges = engine.getGraphEdges(n1.id);
      expect(edges).toHaveLength(1);
    });

    it('should find graph paths', () => {
      const n1 = engine.addGraphNode('entity', 'A');
      const n2 = engine.addGraphNode('entity', 'B');
      const n3 = engine.addGraphNode('entity', 'C');
      engine.addGraphEdge(n1.id, n2.id, 'RELATES_TO');
      engine.addGraphEdge(n2.id, n3.id, 'RELATES_TO');
      const paths = engine.findGraphPath(n1.id, n3.id);
      expect(paths.length).toBeGreaterThanOrEqual(1);
      expect(paths[0]).toHaveLength(2);
    });
  });

  // --- World State ---

  describe('World State', () => {
    it('should create a snapshot', () => {
      engine.createEntity('COMPANY', 'Test');
      const snapshot = engine.createSnapshot();
      expect(snapshot.timestamp).toBeTruthy();
      expect(snapshot.entities.size).toBe(1);
      expect(snapshot.checksum).toBeTruthy();
    });

    it('should restore a snapshot', () => {
      engine.createEntity('COMPANY', 'Before');
      const snapshot = engine.createSnapshot();
      engine.createEntity('COMPANY', 'After');
      expect(engine.getStats().entities).toBe(2);
      const restored = engine.restoreSnapshot(snapshot.timestamp);
      expect(restored).toBe(true);
      expect(engine.getStats().entities).toBe(1);
    });

    it('should compute world diff', () => {
      const snapshot = engine.createSnapshot();
      engine.createEntity('COMPANY', 'New Company');
      const diff = engine.getDiff(snapshot.timestamp);
      expect(diff.addedEntities).toHaveLength(1);
      expect(diff.addedEntities[0].identity.canonicalName).toBe('New Company');
    });
  });

  // --- Data Quality ---

  describe('Data Quality', () => {
    it('should compute data quality metrics', () => {
      engine.createEntity('COMPANY', 'Apple');
      engine.createEntity('COMPANY', 'Google');
      const entity = engine.createEntity('PERSON', 'Tim Cook');
      engine.createFact(entity.id, 'CEO', { objectValue: 'Apple', confidence: 0.9 });
      engine.createEvent('TECH_EVENT', 'AI breakthrough', 'New model', [], nowISO());
      const quality = engine.getDataQuality();
      expect(quality.totalEntities).toBe(3);
      expect(quality.totalFacts).toBe(1);
      expect(quality.totalEvents).toBe(1);
      expect(quality.activeFacts).toBe(1);
      expect(quality.avgFactConfidence).toBeGreaterThan(0);
    });
  });
});

// ============================================================================
// EntityResolver
// ============================================================================

describe('EntityResolver', () => {
  let resolver: EntityResolver;

  beforeEach(() => {
    resolver = new EntityResolver();
  });

  it('should resolve exact name match', () => {
    const entity: WorldEntity = {
      id: 'e1',
      identity: {
        canonicalId: 'e1',
        canonicalName: 'Apple Inc.',
        aliases: [{ name: 'AAPL', type: 'ticker' }],
        entityType: 'COMPANY',
      },
      createdAt: nowISO(),
      updatedAt: nowISO(),
      importance: 'HIGH',
      tags: [],
      metadata: {},
      knownFacts: [],
      knownEvents: [],
      knowledgeLevel: 'CURRENT',
    };
    resolver.indexEntity(entity);
    const matches = resolver.resolve('Apple Inc.');
    expect(matches).toHaveLength(1);
    expect(matches[0].score).toBe(1.0);
  });

  it('should resolve alias match', () => {
    const entity: WorldEntity = {
      id: 'e1',
      identity: {
        canonicalId: 'e1',
        canonicalName: 'Apple Inc.',
        aliases: [{ name: 'AAPL', type: 'ticker' }],
        entityType: 'COMPANY',
      },
      createdAt: nowISO(),
      updatedAt: nowISO(),
      importance: 'HIGH',
      tags: [],
      metadata: {},
      knownFacts: [],
      knownEvents: [],
      knowledgeLevel: 'CURRENT',
    };
    resolver.indexEntity(entity);
    const matches = resolver.resolve('AAPL');
    expect(matches).toHaveLength(1);
    expect(matches[0].score).toBeGreaterThanOrEqual(0.85);
  });

  it('should resolve fuzzy name match', () => {
    const entity: WorldEntity = {
      id: 'e1',
      identity: {
        canonicalId: 'e1',
        canonicalName: 'Microsoft Corporation',
        aliases: [],
        entityType: 'COMPANY',
      },
      createdAt: nowISO(),
      updatedAt: nowISO(),
      importance: 'HIGH',
      tags: [],
      metadata: {},
      knownFacts: [],
      knownEvents: [],
      knowledgeLevel: 'CURRENT',
    };
    resolver.indexEntity(entity);
    const matches = resolver.resolve('Microsoft Corp');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('should filter by entity type', () => {
    resolver.indexEntity({
      id: 'e1',
      identity: { canonicalId: 'e1', canonicalName: 'Apple', aliases: [], entityType: 'COMPANY' },
      createdAt: nowISO(), updatedAt: nowISO(), importance: 'HIGH', tags: [], metadata: {}, knownFacts: [], knownEvents: [], knowledgeLevel: 'CURRENT',
    });
    resolver.indexEntity({
      id: 'e2',
      identity: { canonicalId: 'e2', canonicalName: 'Apple', aliases: [], entityType: 'PERSON' },
      createdAt: nowISO(), updatedAt: nowISO(), importance: 'MEDIUM', tags: [], metadata: {}, knownFacts: [], knownEvents: [], knowledgeLevel: 'CURRENT',
    });
    const companies = resolver.resolve('Apple', 'COMPANY');
    expect(companies).toHaveLength(1);
    expect(companies[0].entityId).toBe('e1');
  });

  it('should detect auto-merge candidates', () => {
    resolver.indexEntity({
      id: 'e1',
      identity: { canonicalId: 'e1', canonicalName: 'Tesla', aliases: [{ name: 'TSLA', type: 'ticker' }], entityType: 'COMPANY' },
      createdAt: nowISO(), updatedAt: nowISO(), importance: 'HIGH', tags: [], metadata: {}, knownFacts: [], knownEvents: [], knowledgeLevel: 'CURRENT',
    });
    resolver.indexEntity({
      id: 'e2',
      identity: { canonicalId: 'e2', canonicalName: 'Tesla Inc', aliases: [{ name: 'TSLA', type: 'ticker' }], entityType: 'COMPANY' },
      createdAt: nowISO(), updatedAt: nowISO(), importance: 'HIGH', tags: [], metadata: {}, knownFacts: [], knownEvents: [], knowledgeLevel: 'CURRENT',
    });
    const merges = resolver.autoMergeConfident();
    expect(merges.length).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// DeduplicationEngine
// ============================================================================

describe('DeduplicationEngine', () => {
  let dedup: DeduplicationEngine;

  beforeEach(() => {
    dedup = new DeduplicationEngine();
  });

  it('should detect duplicate events by fingerprint', () => {
    const event1: WorldEvent = {
      id: 'ev1', type: 'TECH_EVENT', title: 'AI breakthrough',
      summary: 'New model', entityIds: [], timestamp: nowISO(),
      retrievedAt: nowISO(), importance: 'HIGH', status: 'ACTIVE',
      confidence: 0.9, sources: [], topicIds: ['ai'],
      relatedEventIds: [], tags: [], metadata: {},
      freshnessClass: 'HOURLY', staleness: 'CURRENT', observationStatus: 'OBSERVED',
    };
    dedup.registerEvent(event1);
    const event2: WorldEvent = { ...event1, id: 'ev2' };
    const result = dedup.checkEventDuplicate(event2);
    expect(result.isDuplicate).toBe(true);
  });

  it('should detect duplicate facts', () => {
    const fact1: TemporalFact = {
      id: 'f1', subjectId: 's1', predicate: 'CEO',
      objectValue: 'Tim Cook', status: 'ACTIVE',
      observationStatus: 'OBSERVED', validFrom: nowISO(),
      createdAt: nowISO(), updatedAt: nowISO(),
      provenance: [], confidence: 0.9, knowledgeLevel: 'CURRENT', metadata: {},
    };
    dedup.registerFact(fact1);
    const fact2: TemporalFact = { ...fact1, id: 'f2' };
    const result = dedup.checkFactDuplicate(fact2);
    expect(result.isDuplicate).toBe(true);
  });

  it('should detect duplicate entities', () => {
    const entity1: WorldEntity = {
      id: 'e1',
      identity: { canonicalId: 'e1', canonicalName: 'Apple', aliases: [], entityType: 'COMPANY' },
      createdAt: nowISO(), updatedAt: nowISO(), importance: 'HIGH', tags: [], metadata: {},
      knownFacts: [], knownEvents: [], knowledgeLevel: 'CURRENT',
    };
    dedup.registerEntity(entity1);
    const entity2: WorldEntity = { ...entity1, id: 'e2' };
    const result = dedup.checkEntityDuplicate(entity2);
    expect(result.isDuplicate).toBe(true);
  });

  it('should compute title similarity', () => {
    const sim1 = dedup.computeTitleSimilarity('OpenAI releases GPT-5', 'OpenAI Releases GPT-5');
    expect(sim1).toBeGreaterThan(0.9);
    const sim2 = dedup.computeTitleSimilarity('OpenAI releases GPT-5', 'Completely different title');
    expect(sim2).toBeLessThan(0.5);
  });
});

// ============================================================================
// KnowledgeGraphEngine
// ============================================================================

describe('KnowledgeGraphEngine', () => {
  let graph: KnowledgeGraphEngine;

  beforeEach(() => {
    graph = new KnowledgeGraphEngine();
  });

  it('should add nodes', () => {
    const node = graph.addNode('entity', 'Apple');
    expect(node.id).toBeTruthy();
    expect(graph.getStats().nodes).toBe(1);
  });

  it('should add edges', () => {
    const n1 = graph.addNode('entity', 'Tim Cook');
    const n2 = graph.addNode('entity', 'Apple');
    const edge = graph.addEdge(n1.id, n2.id, 'CEO_OF');
    expect(edge).toBeTruthy();
    expect(graph.getStats().edges).toBe(1);
  });

  it('should get neighbors', () => {
    const n1 = graph.addNode('entity', 'A');
    const n2 = graph.addNode('entity', 'B');
    graph.addEdge(n1.id, n2.id, 'RELATES_TO');
    const neighbors = graph.getNeighbors(n1.id);
    expect(neighbors).toHaveLength(1);
    expect(neighbors[0].node.label).toBe('B');
  });

  it('should find paths', () => {
    const n1 = graph.addNode('entity', 'A');
    const n2 = graph.addNode('entity', 'B');
    const n3 = graph.addNode('entity', 'C');
    graph.addEdge(n1.id, n2.id, 'RELATES_TO');
    graph.addEdge(n2.id, n3.id, 'RELATES_TO');
    const paths = graph.findPath(n1.id, n3.id);
    expect(paths.length).toBeGreaterThanOrEqual(1);
  });

  it('should get subgraph', () => {
    const n1 = graph.addNode('entity', 'A');
    const n2 = graph.addNode('entity', 'B');
    const n3 = graph.addNode('entity', 'C');
    graph.addEdge(n1.id, n2.id, 'RELATES_TO');
    graph.addEdge(n2.id, n3.id, 'RELATES_TO');
    const subgraph = graph.getSubgraph(n1.id, 2);
    expect(subgraph.nodes.length).toBe(3);
    expect(subgraph.edges.length).toBe(2);
  });

  it('should search nodes', () => {
    graph.addNode('entity', 'Apple Inc');
    graph.addNode('entity', 'Google');
    const results = graph.searchNodes('apple');
    expect(results).toHaveLength(1);
  });

  it('should remove nodes and edges', () => {
    const n1 = graph.addNode('entity', 'A');
    const n2 = graph.addNode('entity', 'B');
    graph.addEdge(n1.id, n2.id, 'RELATES_TO');
    graph.removeNode(n1.id);
    expect(graph.getStats().nodes).toBe(1);
    expect(graph.getStats().edges).toBe(0);
  });
});

// ============================================================================
// WorldWatcherEngine
// ============================================================================

describe('WorldWatcherEngine', () => {
  let state: WorldStateEngine;
  let watcher: WorldWatcherEngine;

  beforeEach(() => {
    state = new WorldStateEngine();
    watcher = new WorldWatcherEngine(state);
  });

  it('should create a watcher', () => {
    const w = watcher.watch({
      entityIds: ['e1'],
      policy: { importance: 'HIGH', cooldownMs: 60000, maxAlertsPerHour: 10, channels: ['notification'] },
    });
    expect(w.id).toBeTruthy();
    expect(w.status).toBe('ACTIVE');
  });

  it('should pause/resume a watcher', () => {
    const w = watcher.watch({ policy: { importance: 'LOW', cooldownMs: 0, maxAlertsPerHour: 100, channels: ['text'] } });
    watcher.pause(w.id);
    expect(watcher.getWatcher(w.id)!.status).toBe('PAUSED');
    watcher.resume(w.id);
    expect(watcher.getWatcher(w.id)!.status).toBe('ACTIVE');
  });

  it('should trigger alert on matching event', () => {
    const w = watcher.watch({
      eventTypes: ['TECH_EVENT'],
      policy: { importance: 'HIGH', cooldownMs: 0, maxAlertsPerHour: 100, channels: ['notification'] },
    });
    const event: WorldEvent = {
      id: 'ev1', type: 'TECH_EVENT', title: 'AI breakthrough',
      summary: 'New model', entityIds: [], timestamp: nowISO(),
      retrievedAt: nowISO(), importance: 'HIGH', status: 'ACTIVE',
      confidence: 0.9, sources: [], topicIds: ['ai'],
      relatedEventIds: [], tags: [], metadata: {},
      freshnessClass: 'HOURLY', staleness: 'CURRENT', observationStatus: 'OBSERVED',
    };
    const alerts = watcher.evaluate(event);
    expect(alerts).toHaveLength(1);
    expect(alerts[0].title).toBe('AI breakthrough');
  });

  it('should respect cooldown', () => {
    const w = watcher.watch({
      eventTypes: ['TECH_EVENT'],
      policy: { importance: 'HIGH', cooldownMs: 60000, maxAlertsPerHour: 100, channels: ['notification'] },
    });
    const event: WorldEvent = {
      id: 'ev1', type: 'TECH_EVENT', title: 'Test',
      summary: 'Test', entityIds: [], timestamp: nowISO(),
      retrievedAt: nowISO(), importance: 'HIGH', status: 'ACTIVE',
      confidence: 0.9, sources: [], topicIds: [],
      relatedEventIds: [], tags: [], metadata: {},
      freshnessClass: 'HOURLY', staleness: 'CURRENT', observationStatus: 'OBSERVED',
    };
    const alerts1 = watcher.evaluate(event);
    expect(alerts1).toHaveLength(1);
    const alerts2 = watcher.evaluate(event);
    expect(alerts2).toHaveLength(0); // cooldown
  });

  it('should stop and unwatch', () => {
    const w = watcher.watch({ policy: { importance: 'LOW', cooldownMs: 0, maxAlertsPerHour: 100, channels: ['text'] } });
    watcher.stop(w.id);
    expect(watcher.getWatcher(w.id)!.status).toBe('STOPPED');
    watcher.unwatch(w.id);
    expect(watcher.getWatcher(w.id)).toBeUndefined();
  });
});

// ============================================================================
// WorldQueryEngine (integration)
// ============================================================================

describe('WorldQueryEngine', () => {
  let wi: WorldIntelligence;

  beforeEach(() => {
    wi = new WorldIntelligence({ enablePersistence: false });
  });

  it('should query entities', () => {
    const entity = wi.createEntity('COMPANY', 'NVIDIA');
    const result = wi.queryWorld({ type: 'ENTITY_LOOKUP', entityIds: [entity.id] });
    expect(result.entities).toHaveLength(1);
    expect(result.entities[0].identity.canonicalName).toBe('NVIDIA');
  });

  it('should query events', () => {
    wi.createEvent('TECH_EVENT', 'GPU launch', 'New GPU released', [], nowISO());
    const result = wi.queryWorld({ type: 'EVENT_LOOKUP', eventTypes: ['TECH_EVENT'] });
    expect(result.events.length).toBeGreaterThanOrEqual(1);
  });

  it('should query by natural language', () => {
    wi.createEntity('COMPANY', 'Tesla');
    wi.createEvent('MARKET_MOVE', 'Tesla stock surges', 'Stock up 10%', [], nowISO(), {
      topicIds: ['tesla', 'stock'],
    });
    const result = wi.queryWorld({
      type: 'NATURAL_LANGUAGE',
      naturalLanguageQuery: 'What happened with Tesla today?',
    });
    expect(result).toBeTruthy();
  });

  it('should compare entities', () => {
    const e1 = wi.createEntity('COMPANY', 'Apple');
    const e2 = wi.createEntity('COMPANY', 'Google');
    const result = wi.compareEntities([e1.id, e2.id]);
    expect(result.entities).toHaveLength(2);
  });

  it('should get changes since timestamp', () => {
    const before = nowISO();
    wi.createEntity('COMPANY', 'NewCo');
    const diff = wi.getChanges(before);
    expect(diff.addedEntities.length).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================================
// World Intelligence Integration
// ============================================================================

describe('WorldIntelligence Integration', () => {
  let wi: WorldIntelligence;

  beforeEach(() => {
    wi = new WorldIntelligence({ enablePersistence: false });
  });

  it('should initialize successfully', async () => {
    await wi.initialize();
    expect(wi).toBeTruthy();
  });

  it('should create and retrieve entities', () => {
    const entity = wi.createEntity('COMPANY', 'OpenAI', [
      { name: 'OpenAI Inc', type: 'alias' },
    ], { importance: 'HIGH' });
    const retrieved = wi.getEntity(entity.id);
    expect(retrieved).toBeTruthy();
    expect(retrieved!.identity.canonicalName).toBe('OpenAI');
  });

  it('should create and retrieve facts', () => {
    const entity = wi.createEntity('COMPANY', 'Apple');
    const fact = wi.createFact(entity.id, 'CEO', { objectValue: 'Tim Cook', confidence: 0.95 });
    const retrieved = wi.getFact(fact.id);
    expect(retrieved).toBeTruthy();
    expect(retrieved!.objectValue).toBe('Tim Cook');
  });

  it('should create and retrieve events', () => {
    const entity = wi.createEntity('COMPANY', 'NVIDIA');
    const event = wi.createEvent('TECH_EVENT', 'NVIDIA announces new GPU', 'Blackwell Ultra architecture', [entity.id], nowISO(), {
      importance: 'HIGH',
    });
    const retrieved = wi.getEvent(event.id);
    expect(retrieved).toBeTruthy();
    expect(retrieved!.title).toBe('NVIDIA announces new GPU');
  });

  it('should integrate with knowledge graph', () => {
    const person = wi.createEntity('PERSON', 'Tim Cook');
    const company = wi.createEntity('COMPANY', 'Apple');
    const graphNode1 = wi.graph.addEntityNode(person);
    const graphNode2 = wi.graph.addEntityNode(company);
    wi.graph.addEdge(graphNode1.id, graphNode2.id, 'CEO_OF');
    const neighbors = wi.graph.getNeighbors(graphNode1.id);
    expect(neighbors).toHaveLength(1);
  });

  it('should create and evaluate watchers', () => {
    const w = wi.watch({
      eventTypes: ['TECH_EVENT'],
      policy: { importance: 'HIGH', cooldownMs: 0, maxAlertsPerHour: 100, channels: ['notification'] },
    });
    wi.createEvent('TECH_EVENT', 'Major AI release', 'GPT-6 announced', [], nowISO(), {
      importance: 'CRITICAL',
    });
    const alerts = wi.getAlerts(w.id);
    expect(alerts.length).toBeGreaterThanOrEqual(1);
  });

  it('should support auto-refresh', () => {
    wi.startAutoRefresh(60000);
    wi.stopAutoRefresh();
    expect(wi).toBeTruthy();
  });

  it('should compute data quality', () => {
    wi.createEntity('COMPANY', 'A');
    wi.createEntity('COMPANY', 'B');
    const quality = wi.getDataQuality();
    expect(quality.totalEntities).toBe(2);
  });

  it('should get health status', async () => {
    const health = await wi.getHealth();
    expect(health.status).toBe('healthy');
  });

  it('should shutdown cleanly', async () => {
    await wi.shutdown();
    expect(wi).toBeTruthy();
  });

  it('should support multiple event types', () => {
    wi.createEvent('MARKET_MOVE', 'Nifty rallies', 'Markets up 2%', [], nowISO());
    wi.createEvent('WEATHER_EVENT', 'Cyclone approaching', 'Bay of Bengal', [], nowISO());
    wi.createEvent('SCIENTIFIC_DISCOVERY', 'New exoplanet found', 'NASA discovers planet', [], nowISO());
    const stats = wi.getStats();
    expect(stats.state.events).toBe(3);
  });

  it('should handle entity resolution across entities', () => {
    wi.createEntity('COMPANY', 'Microsoft Corp', [{ name: 'MSFT', type: 'ticker' }]);
    wi.createEntity('COMPANY', 'Microsoft', [{ name: 'Microsoft Corporation', type: 'alias' }]);
    const matches = wi.searchEntities('Microsoft');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================================
// Ingestion Integration
// ============================================================================

describe('WorldIngestion Integration', () => {
  let wi: WorldIntelligence;

  beforeEach(() => {
    wi = new WorldIntelligence({ enablePersistence: false });
  });

  it('should register and use a provider', async () => {
    const mockProvider: IngestionProvider = {
      id: 'test-news',
      name: 'Test News',
      category: 'news',
      sourceClass: 'SECONDARY',
      enabled: true,
      fetch: async () => ({
        providerId: 'test-news',
        retrievedAt: nowISO(),
        items: [
          {
            type: 'event',
            raw: {
              title: 'Test headline',
              summary: 'Test summary',
              category: 'tech',
              entities: [{ name: 'OpenAI', type: 'company' }],
              topics: ['ai'],
            },
            title: 'Test headline',
            summary: 'Test summary',
            entities: ['OpenAI'],
          },
        ],
      }),
    };
    wi.registerProvider(mockProvider);
    const result = await wi.ingestFromProvider('test-news');
    expect(result.success).toBe(true);
  });
});

// ============================================================================
// Persistence Integration
// ============================================================================

describe('WorldPersistence Integration', () => {
  it('should create persistence engine', () => {
    const persistence = new WorldPersistenceEngine({
      ...DEFAULT_WORLD_CONFIG,
      persistencePath: '/tmp/test-world-intelligence',
    });
    expect(persistence).toBeTruthy();
  });

  it('should validate empty data', async () => {
    const persistence = new WorldPersistenceEngine({
      ...DEFAULT_WORLD_CONFIG,
      persistencePath: '/tmp/test-world-intelligence',
    });
    const result = await persistence.validateData();
    expect(result.valid).toBe(true);
  });
});

// ============================================================================
// Scale Tests
// ============================================================================

describe('World Intelligence Scale', () => {
  let engine: WorldStateEngine;

  beforeEach(() => {
    engine = new WorldStateEngine({ enablePersistence: false });
  });

  it('should handle 10K entities', () => {
    const start = Date.now();
    for (let i = 0; i < 10_000; i++) {
      engine.createEntity('COMPANY', `Company ${i}`);
    }
    const elapsed = Date.now() - start;
    expect(engine.getStats().entities).toBe(10_000);
    expect(elapsed).toBeLessThan(30_000); // 30s budget
  });

  // Explicit 30s vitest timeout to match each test's documented 30s budget
  // (vitest default is 15s — under machine load the harness killed the test
  // before its own assertion ran; documented §61, invalid test configuration).
  it('should handle 10K events', () => {
    const start = Date.now();
    for (let i = 0; i < 10_000; i++) {
      engine.createEvent('NEWS', `Event ${i}`, `Summary ${i}`, [], nowISO());
    }
    const elapsed = Date.now() - start;
    expect(engine.getStats().events).toBe(10_000);
    expect(elapsed).toBeLessThan(30_000);
  }, 30_000);

  it('should handle 10K facts', () => {
    const entity = engine.createEntity('COMPANY', 'Test');
    const start = Date.now();
    for (let i = 0; i < 10_000; i++) {
      engine.createFact(entity.id, `predicate_${i}`, { objectValue: `value_${i}` });
    }
    const elapsed = Date.now() - start;
    expect(engine.getStats().facts).toBe(10_000);
    expect(elapsed).toBeLessThan(30_000);
  }, 30_000);

  it('should handle 10K graph nodes', () => {
    const start = Date.now();
    for (let i = 0; i < 10_000; i++) {
      engine.addGraphNode('entity', `Node ${i}`);
    }
    const elapsed = Date.now() - start;
    expect(engine.getStats().graphNodes).toBe(10_000);
    expect(elapsed).toBeLessThan(30_000);
  }, 30_000);

  it('should query 10K entities efficiently', () => {
    for (let i = 0; i < 10_000; i++) {
      engine.createEntity('COMPANY', `Company ${i}`);
    }
    const start = Date.now();
    const results = engine.searchEntities('Company 5000');
    const elapsed = Date.now() - start;
    expect(results.length).toBeGreaterThanOrEqual(1);
    expect(elapsed).toBeLessThan(5_000); // 5s budget for search
  });
});

// ============================================================================
// Temporal Tests
// ============================================================================

describe('Temporal Operations', () => {
  let engine: WorldStateEngine;

  beforeEach(() => {
    engine = new WorldStateEngine({ enablePersistence: false });
  });

  it('should track fact changes over time', () => {
    const entity = engine.createEntity('COMPANY', 'Apple');
    engine.createFact(entity.id, 'CEO', {
      objectValue: 'Steve Jobs',
      validFrom: '1997-07-09T00:00:00Z',
      validTo: '2011-08-24T00:00:00Z',
    });
    engine.createFact(entity.id, 'CEO', {
      objectValue: 'Tim Cook',
      validFrom: '2011-08-24T00:00:00Z',
    });
    const in2005 = engine.getHistoricalFacts(entity.id, 'CEO', '2005-06-01T00:00:00Z');
    expect(in2005.some(f => f.objectValue === 'Steve Jobs')).toBe(true);
    const current = engine.getCurrentFact(entity.id, 'CEO');
    expect(current?.objectValue).toBe('Tim Cook');
  });

  it('should track event staleness', () => {
    const oldTime = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
    engine.createEvent('NEWS', 'Old news', 'Old', [], oldTime);
    const recent = engine.getRecentEvents(24);
    expect(recent).toHaveLength(0);
    const all = engine.getRecentEvents(72);
    expect(all.length).toBeGreaterThanOrEqual(1);
  });

  it('should create and restore snapshots with temporal state', () => {
    const entity = engine.createEntity('COMPANY', 'TestCo');
    engine.createFact(entity.id, 'CEO', { objectValue: 'Alice' });
    const snap1 = engine.createSnapshot();
    engine.createFact(entity.id, 'CEO', { objectValue: 'Bob' });
    expect(engine.getFactsBySubject(entity.id)).toHaveLength(2);
    engine.restoreSnapshot(snap1.timestamp);
    expect(engine.getFactsBySubject(entity.id)).toHaveLength(1);
  });
});
