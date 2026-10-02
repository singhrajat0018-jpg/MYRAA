// ============================================================================
// MYRAA World Query Engine
// ============================================================================

import {
  WorldEntity, TemporalFact, WorldEvent,
  GraphNode, GraphEdge,
  WorldQuery, WorldQueryResult, WorldQueryType,
  EntityType, WorldEventType, FreshnessClass, ImportanceLevel,
  nowISO,
} from './contracts';
import { WorldStateEngine } from './world_state_engine';
import { EntityResolver } from './entity_resolution';
import { KnowledgeGraphEngine } from './knowledge_graph';

export class WorldQueryEngine {
  private stateEngine: WorldStateEngine;
  private resolver: EntityResolver;
  private graphEngine: KnowledgeGraphEngine;

  constructor(
    stateEngine: WorldStateEngine,
    resolver: EntityResolver,
    graphEngine: KnowledgeGraphEngine
  ) {
    this.stateEngine = stateEngine;
    this.resolver = resolver;
    this.graphEngine = graphEngine;
  }

  query(query: WorldQuery): WorldQueryResult {
    const start = Date.now();
    switch (query.type) {
      case 'ENTITY_LOOKUP': return this.queryEntity(query, start);
      case 'EVENT_LOOKUP': return this.queryEvents(query, start);
      case 'FACT_LOOKUP': return this.queryFacts(query, start);
      case 'TEMPORAL_QUERY': return this.queryTemporal(query, start);
      case 'COMPARISON': return this.queryComparison(query, start);
      case 'CHANGE_DETECTION': return this.queryChanges(query, start);
      case 'TOPIC_SEARCH': return this.queryTopic(query, start);
      case 'NATURAL_LANGUAGE': return this.queryNaturalLanguage(query, start);
      case 'SOURCE_FILTER':
      case 'FRESHNESS_FILTER':
      default: return this.queryGeneric(query, start);
    }
  }

  queryEntity(query: WorldQuery, start: number): WorldQueryResult {
    const entities: WorldEntity[] = [];
    if (query.entityIds) {
      for (const id of query.entityIds) {
        const e = this.stateEngine.getEntity(id);
        if (e) entities.push(e);
      }
    }
    if (query.entityType) {
      entities.push(...this.stateEngine.findEntitiesByType(query.entityType));
    }
    if (query.naturalLanguageQuery) {
      entities.push(...this.stateEngine.searchEntities(query.naturalLanguageQuery, query.maxResults || 20));
    }
    const deduped = this.deduplicateEntities(entities);
    const limited = deduped.slice(0, query.maxResults || 50);
    return {
      query,
      entities: limited,
      facts: [],
      events: [],
      graphNodes: [],
      graphEdges: [],
      totalResults: deduped.length,
      confidence: this.computeAverageConfidence(limited.map(e => e.importance)),
      freshness: this.computeFreshness(limited.map(e => e.lastIngestedAt)),
      sourcesUsed: [],
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryEvents(query: WorldQuery, start: number): WorldQueryResult {
    const events: WorldEvent[] = [];
    if (query.entityIds) {
      for (const eid of query.entityIds) {
        events.push(...this.stateEngine.getEventsByEntity(eid, query.maxResults || 50));
      }
    }
    if (query.eventTypes) {
      for (const type of query.eventTypes) {
        events.push(...this.stateEngine.getEventsByType(type, query.maxResults || 50));
      }
    }
    if (query.topics) {
      for (const topic of query.topics) {
        events.push(...this.stateEngine.getEventsByTopic(topic, query.maxResults || 50));
      }
    }
    if (query.timeRange) {
      return this.filterByTimeRange(events, query, start);
    }
    const deduped = this.deduplicateEvents(events);
    const filtered = this.applyEventFilters(deduped, query);
    const limited = filtered.slice(0, query.maxResults || 50);
    return {
      query,
      entities: [],
      facts: [],
      events: limited,
      graphNodes: [],
      graphEdges: [],
      totalResults: filtered.length,
      confidence: this.computeAverageConfidence(limited.map(e => e.importance)),
      freshness: this.computeFreshness(limited.map(e => e.retrievedAt)),
      sourcesUsed: this.extractSources(limited),
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryFacts(query: WorldQuery, start: number): WorldQueryResult {
    const facts: TemporalFact[] = [];
    if (query.entityIds) {
      for (const eid of query.entityIds) {
        facts.push(...this.stateEngine.getFactsBySubject(eid));
      }
    }
    const filtered = facts.filter(f => {
      if (query.timeRange) {
        if (query.timeRange.from && f.validFrom < query.timeRange.from) return false;
        if (query.timeRange.to && f.validTo && f.validTo > query.timeRange.to) return false;
      }
      return f.status === 'ACTIVE';
    });
    const limited = filtered.slice(0, query.maxResults || 100);
    return {
      query,
      entities: [],
      facts: limited,
      events: [],
      graphNodes: [],
      graphEdges: [],
      totalResults: filtered.length,
      confidence: limited.reduce((sum, f) => sum + f.confidence, 0) / Math.max(1, limited.length),
      freshness: 'UNKNOWN',
      sourcesUsed: [],
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryTemporal(query: WorldQuery, start: number): WorldQueryResult {
    const facts: TemporalFact[] = [];
    if (query.entityIds && query.timeRange) {
      const atTime = query.timeRange.to || nowISO();
      for (const eid of query.entityIds) {
        const subjectFacts = this.stateEngine.getFactsBySubject(eid);
        for (const f of subjectFacts) {
          if (f.validFrom <= atTime && (!f.validTo || f.validTo >= atTime)) {
            facts.push(f);
          }
        }
      }
    }
    return {
      query,
      entities: [],
      facts: facts.slice(0, query.maxResults || 50),
      events: [],
      graphNodes: [],
      graphEdges: [],
      totalResults: facts.length,
      confidence: 0.8,
      freshness: 'UNKNOWN',
      sourcesUsed: [],
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryComparison(query: WorldQuery, start: number): WorldQueryResult {
    // Compare entities side by side
    const entities: WorldEntity[] = [];
    const facts: TemporalFact[] = [];
    if (query.entityIds) {
      for (const eid of query.entityIds) {
        const e = this.stateEngine.getEntity(eid);
        if (e) entities.push(e);
        facts.push(...this.stateEngine.getFactsBySubject(eid));
      }
    }
    return {
      query,
      entities,
      facts,
      events: [],
      graphNodes: [],
      graphEdges: [],
      totalResults: entities.length + facts.length,
      confidence: 0.7,
      freshness: 'UNKNOWN',
      sourcesUsed: [],
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryChanges(query: WorldQuery, start: number): WorldQueryResult {
    const from = query.timeRange?.from || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const to = query.timeRange?.to || nowISO();
    const diff = this.stateEngine.getDiff(from, to);
    const events: WorldEvent[] = [...diff.addedEvents];
    return {
      query,
      entities: diff.addedEntities,
      facts: diff.addedFacts,
      events,
      graphNodes: [],
      graphEdges: [],
      totalResults: diff.addedEntities.length + diff.addedFacts.length + diff.addedEvents.length,
      confidence: 0.8,
      freshness: 'HOURLY',
      sourcesUsed: [],
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryTopic(query: WorldQuery, start: number): WorldQueryResult {
    const events: WorldEvent[] = [];
    if (query.topics) {
      for (const topic of query.topics) {
        events.push(...this.stateEngine.getEventsByTopic(topic, query.maxResults || 50));
      }
    }
    if (query.naturalLanguageQuery) {
      // Search events by title/summary
      const lower = query.naturalLanguageQuery.toLowerCase();
      const allEvents = this.stateEngine.getRecentEvents(168, 500); // 1 week
      for (const e of allEvents) {
        if (e.title.toLowerCase().includes(lower) || e.summary.toLowerCase().includes(lower)) {
          events.push(e);
        }
      }
    }
    const deduped = this.deduplicateEvents(events);
    const limited = deduped.slice(0, query.maxResults || 50);
    return {
      query,
      entities: [],
      facts: [],
      events: limited,
      graphNodes: [],
      graphEdges: [],
      totalResults: deduped.length,
      confidence: 0.7,
      freshness: this.computeFreshness(limited.map(e => e.retrievedAt)),
      sourcesUsed: this.extractSources(limited),
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  queryNaturalLanguage(query: WorldQuery, start: number): WorldQueryResult {
    // Decompose natural language into structured queries
    const text = (query.naturalLanguageQuery || '').toLowerCase();
    // Detect entity names
    const entityMatches = this.resolver.resolve(query.naturalLanguageQuery || '');
    const entityIds = entityMatches.slice(0, 5).map(m => m.entityId);
    // Detect time references
    const timeRange = this.parseTimeReference(text);
    // Detect event type hints
    const eventTypes = this.inferEventTypes(text);
    // Detect topic hints
    const topics = this.extractTopics(text);

    // Combine results from multiple sub-queries
    const allEntities: WorldEntity[] = [];
    const allEvents: WorldEvent[] = [];
    const allFacts: TemporalFact[] = [];

    // Entity lookup
    for (const eid of entityIds) {
      const e = this.stateEngine.getEntity(eid);
      if (e) allEntities.push(e);
    }
    // Event lookup
    if (eventTypes.length > 0) {
      for (const type of eventTypes) {
        allEvents.push(...this.stateEngine.getEventsByType(type, 20));
      }
    }
    if (topics.length > 0) {
      for (const topic of topics) {
        allEvents.push(...this.stateEngine.getEventsByTopic(topic, 20));
      }
    }
    // Entity events
    for (const eid of entityIds) {
      allEvents.push(...this.stateEngine.getEventsByEntity(eid, 20));
    }
    // Facts
    for (const eid of entityIds) {
      allFacts.push(...this.stateEngine.getFactsBySubject(eid));
    }

    const dedupedEvents = this.deduplicateEvents(allEvents);
    const limited = dedupedEvents.slice(0, query.maxResults || 30);

    return {
      query,
      entities: allEntities.slice(0, 10),
      facts: allFacts.slice(0, 20),
      events: limited,
      graphNodes: [],
      graphEdges: [],
      totalResults: allEntities.length + limited.length + allFacts.length,
      confidence: 0.6,
      freshness: this.computeFreshness(limited.map(e => e.retrievedAt)),
      sourcesUsed: this.extractSources(limited),
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  private queryGeneric(query: WorldQuery, start: number): WorldQueryResult {
    return {
      query,
      entities: [],
      facts: [],
      events: [],
      graphNodes: [],
      graphEdges: [],
      totalResults: 0,
      confidence: 0,
      freshness: 'UNKNOWN',
      sourcesUsed: [],
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  // --- Helpers ---

  private filterByTimeRange(events: WorldEvent[], query: WorldQuery, start: number): WorldQueryResult {
    const from = query.timeRange?.from || '';
    const to = query.timeRange?.to || nowISO();
    const filtered = events.filter(e => {
      if (from && e.timestamp < from) return false;
      if (to && e.timestamp > to) return false;
      return true;
    });
    const limited = filtered.slice(0, query.maxResults || 50);
    return {
      query,
      entities: [],
      facts: [],
      events: limited,
      graphNodes: [],
      graphEdges: [],
      totalResults: filtered.length,
      confidence: 0.8,
      freshness: this.computeFreshness(limited.map(e => e.retrievedAt)),
      sourcesUsed: this.extractSources(limited),
      queriedAt: nowISO(),
      processingTimeMs: Date.now() - start,
    };
  }

  private applyEventFilters(events: WorldEvent[], query: WorldQuery): WorldEvent[] {
    let filtered = events;
    if (query.freshness) {
      filtered = filtered.filter(e => e.freshnessClass === query.freshness);
    }
    if (query.sourceFilter && query.sourceFilter.length > 0) {
      filtered = filtered.filter(e =>
        e.sources.some(s => query.sourceFilter!.includes(s.providerId))
      );
    }
    return filtered;
  }

  private deduplicateEntities(entities: WorldEntity[]): WorldEntity[] {
    const seen = new Set<string>();
    return entities.filter(e => {
      if (seen.has(e.id)) return false;
      seen.add(e.id);
      return true;
    });
  }

  private deduplicateEvents(events: WorldEvent[]): WorldEvent[] {
    const seen = new Set<string>();
    return events
      .filter(e => {
        if (seen.has(e.id)) return false;
        seen.add(e.id);
        return true;
      })
      .sort((a, b) => {
        // Sort by importance then timestamp
        const impOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
        const impDiff = (impOrder[a.importance] || 5) - (impOrder[b.importance] || 5);
        if (impDiff !== 0) return impDiff;
        return b.timestamp.localeCompare(a.timestamp);
      });
  }

  private computeAverageConfidence(levels: ImportanceLevel[]): number {
    const scores: Record<string, number> = { CRITICAL: 0.95, HIGH: 0.85, MEDIUM: 0.7, LOW: 0.5, INFO: 0.3 };
    if (levels.length === 0) return 0.5;
    return levels.reduce((sum, l) => sum + (scores[l] || 0.5), 0) / levels.length;
  }

  private computeFreshness(timestamps: (string | undefined)[]): FreshnessClass {
    const now = Date.now();
    let minAge = Infinity;
    for (const ts of timestamps) {
      if (!ts) continue;
      const age = now - new Date(ts).getTime();
      if (age < minAge) minAge = age;
    }
    if (minAge < 5 * 60 * 1000) return 'REALTIME';
    if (minAge < 60 * 60 * 1000) return 'MINUTES';
    if (minAge < 24 * 60 * 60 * 1000) return 'HOURLY';
    if (minAge < 7 * 24 * 60 * 60 * 1000) return 'DAILY';
    return 'HISTORICAL';
  }

  private extractSources(events: WorldEvent[]): string[] {
    const sources = new Set<string>();
    for (const e of events) {
      for (const s of e.sources) sources.add(s.providerId);
    }
    return Array.from(sources);
  }

  private parseTimeReference(text: string): { from?: string; to?: string } | undefined {
    const now = new Date();
    if (text.includes('today') || text.includes('aaj')) {
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      return { from: today.toISOString() };
    }
    if (text.includes('yesterday') || text.includes('kal')) {
      const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      return { from: yesterday.toISOString(), to: today.toISOString() };
    }
    if (text.includes('this week') || text.includes('is hafte')) {
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      return { from: weekAgo.toISOString() };
    }
    if (text.includes('this month') || text.includes('is mahine')) {
      const monthAgo = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
      return { from: monthAgo.toISOString() };
    }
    return undefined;
  }

  private inferEventTypes(text: string): WorldEventType[] {
    const types: WorldEventType[] = [];
    if (text.includes('market') || text.includes('stock') || text.includes('nifty') || text.includes('sensex')) types.push('MARKET_MOVE');
    if (text.includes('earning') || text.includes('revenue') || text.includes('profit')) types.push('EARNINGS');
    if (text.includes('tech') || text.includes('ai') || text.includes('openai') || text.includes('nvidia') || text.includes('google')) types.push('TECH_EVENT');
    if (text.includes('weather') || text.includes('rain') || text.includes('cyclone')) types.push('WEATHER_EVENT');
    if (text.includes('politic') || text.includes('election') || text.includes('parliament')) types.push('POLITICAL_EVENT');
    if (text.includes('science') || text.includes('space') || text.includes('nasa')) types.push('SCIENTIFIC_DISCOVERY');
    if (text.includes('economic') || text.includes('gdp') || text.includes('inflation')) types.push('ECONOMIC_RELEASE');
    if (types.length === 0) types.push('NEWS');
    return types;
  }

  private extractTopics(text: string): string[] {
    const topics: string[] = [];
    const topicPatterns: [RegExp, string][] = [
      [/artificial intelligence|ai\b|machine learning|ml\b/i, 'artificial intelligence'],
      [/climate change|global warming|carbon/i, 'climate'],
      [/crypto|bitcoin|ethereum|blockchain/i, 'cryptocurrency'],
      [/trade war|tariff|sanction/i, 'trade'],
      [/pandemic|covid|virus|health/i, 'health'],
      [/space|nasa|spacex|rocket/i, 'space'],
      [/energy|oil|solar|renewable/i, 'energy'],
      [/election|vote|democracy/i, 'politics'],
    ];
    for (const [pattern, topic] of topicPatterns) {
      if (pattern.test(text)) topics.push(topic);
    }
    return topics;
  }
}
