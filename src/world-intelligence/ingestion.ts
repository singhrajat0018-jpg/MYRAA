// ============================================================================
// MYRAA World Ingestion Engine
// ============================================================================

import {
  WorldEntity, TemporalFact, WorldEvent, EventSource,
  IngestionSource, IngestionResult, RawWorldData, RawWorldItem,
  WorldIntelligenceConfig, DEFAULT_WORLD_CONFIG,
  SourceClass, ImportanceLevel, FreshnessClass,
  ObservationStatus, KnowledgeLevel, FactProvenance,
  generateWorldId, nowISO,
} from './contracts';
import { WorldStateEngine } from './world_state_engine';
import { EntityResolver, ResolutionMatch } from './entity_resolution';
import { DeduplicationEngine, DeduplicationResult } from './deduplication';

export interface IngestionProvider {
  readonly id: string;
  readonly name: string;
  readonly category: string;
  readonly sourceClass: SourceClass;
  readonly enabled: boolean;
  fetch(): Promise<RawWorldData>;
}

export interface IngestionPipeline {
  normalize(item: RawWorldItem): NormalizedItem[];
  extractEntities(item: NormalizedItem): EntityCandidate[];
  extractFacts(item: NormalizedItem, entityIds: string[]): FactCandidate[];
  extractEvents(item: NormalizedItem, entityIds: string[]): EventCandidate[];
}

export interface NormalizedItem {
  readonly type: 'entity' | 'fact' | 'event';
  readonly raw: Record<string, unknown>;
  readonly normalizedTitle?: string;
  readonly normalizedSummary?: string;
  readonly entities: string[];
  readonly topics: string[];
  readonly publishedAt?: string;
  readonly sourceUrl?: string;
  readonly providerId: string;
}

export interface EntityCandidate {
  readonly name: string;
  readonly entityType: WorldEntity['identity']['entityType'];
  readonly aliases?: { name: string; type: string }[];
  readonly tags?: string[];
  readonly importance?: ImportanceLevel;
}

export interface FactCandidate {
  readonly subjectName: string;
  readonly predicate: string;
  readonly objectName?: string;
  readonly objectValue?: string | number | boolean;
  readonly confidence: number;
  readonly observationStatus: ObservationStatus;
  readonly knowledgeLevel: KnowledgeLevel;
  readonly publishedAt?: string;
}

export interface EventCandidate {
  readonly type: WorldEvent['type'];
  readonly title: string;
  readonly summary: string;
  readonly entityNames: string[];
  readonly timestamp: string;
  readonly importance: ImportanceLevel;
  readonly confidence: number;
  readonly topics: string[];
  readonly location?: WorldEvent['location'];
  readonly freshnessClass: FreshnessClass;
  readonly observationStatus: ObservationStatus;
}

export class WorldIngestionEngine {
  private stateEngine: WorldStateEngine;
  private resolver: EntityResolver;
  private dedup: DeduplicationEngine;
  private providers: Map<string, IngestionProvider> = new Map();
  private ingestionHistory: IngestionResult[] = [];
  private config: WorldIntelligenceConfig;

  constructor(
    stateEngine: WorldStateEngine,
    resolver: EntityResolver,
    dedup: DeduplicationEngine,
    config?: Partial<WorldIntelligenceConfig>
  ) {
    this.stateEngine = stateEngine;
    this.resolver = resolver;
    this.dedup = dedup;
    this.config = { ...DEFAULT_WORLD_CONFIG, ...config };
  }

  registerProvider(provider: IngestionProvider): void {
    this.providers.set(provider.id, provider);
  }

  unregisterProvider(providerId: string): void {
    this.providers.delete(providerId);
  }

  async ingestFromProvider(providerId: string): Promise<IngestionResult> {
    const provider = this.providers.get(providerId);
    if (!provider || !provider.enabled) {
      return this.makeResult(providerId, false, 0, 0, 0, 0, 0, ['Provider not found or disabled']);
    }
    const start = Date.now();
    try {
      const data = await provider.fetch();
      let entitiesFound = 0, factsFound = 0, eventsFound = 0, duplicatesSkipped = 0, conflictsDetected = 0;
      for (const item of data.items) {
        const normalized = this.normalizeItem(item, providerId);
        // Entity extraction
        const entityCandidates = this.extractEntityCandidates(normalized);
        const entityIds: string[] = [];
        for (const candidate of entityCandidates) {
          const resolved = this.resolver.resolve(candidate.name, candidate.entityType);
          if (resolved.length > 0 && resolved[0].score >= 0.85) {
            entityIds.push(resolved[0].entityId);
          } else {
            const created = this.stateEngine.createEntity(
              candidate.entityType,
              candidate.name,
              (candidate.aliases || []).map(a => ({ name: a.name, type: a.type as any })),
              { importance: candidate.importance || 'MEDIUM', tags: candidate.tags || [] }
            );
            this.resolver.indexEntity(created);
            entityIds.push(created.id);
            entitiesFound++;
          }
        }
        // Fact extraction
        const factCandidates = this.extractFactCandidates(normalized, entityIds);
        for (const fc of factCandidates) {
          const subjectEntity = this.findEntityByName(fc.subjectName, entityIds);
          if (!subjectEntity) continue;
          const objectEntity = fc.objectName ? this.findEntityByName(fc.objectName, entityIds) : undefined;
          // Dedup check
          const existingFacts = this.stateEngine.getFactsBySubject(subjectEntity.id);
          const isDupe = existingFacts.some(f =>
            f.predicate === fc.predicate &&
            (f.objectId === objectEntity?.id || f.objectValue === fc.objectValue) &&
            f.status === 'ACTIVE'
          );
          if (isDupe) { duplicatesSkipped++; continue; }
          const provenance: FactProvenance = {
            sourceId: providerId,
            sourceClass: provider.sourceClass,
            providerId,
            retrievedAt: data.retrievedAt,
            publishedAt: fc.publishedAt,
            confidence: fc.confidence,
            verificationStatus: 'UNVERIFIED',
          };
          this.stateEngine.createFact(subjectEntity.id, fc.predicate, {
            objectId: objectEntity?.id,
            objectValue: fc.objectValue,
            observationStatus: fc.observationStatus,
            knowledgeLevel: fc.knowledgeLevel,
            provenance: [provenance],
            confidence: fc.confidence,
          });
          factsFound++;
        }
        // Event extraction
        const eventCandidates = this.extractEventCandidates(normalized, entityIds);
        for (const ec of eventCandidates) {
          const resolvedEntityIds = ec.entityNames
            .map(name => this.findEntityByName(name, entityIds)?.id)
            .filter(Boolean) as string[];
          // Dedup check
          const existingEvents = this.stateEngine.getRecentEvents(24);
          const isDupe = existingEvents.some(e =>
            e.type === ec.type &&
            this.dedup.computeTitleSimilarity(e.title, ec.title) > 0.85
          );
          if (isDupe) { duplicatesSkipped++; continue; }
          const eventSources: EventSource[] = [{
            sourceId: providerId,
            providerId,
            sourceClass: provider.sourceClass,
            url: normalized.sourceUrl,
            title: normalized.normalizedTitle,
            retrievedAt: data.retrievedAt,
            publishedAt: ec.timestamp,
          }];
          this.stateEngine.createEvent(ec.type, ec.title, ec.summary, resolvedEntityIds, ec.timestamp, {
            importance: ec.importance,
            confidence: ec.confidence,
            sources: eventSources,
            topicIds: ec.topics,
            location: ec.location,
            freshnessClass: ec.freshnessClass,
            observationStatus: ec.observationStatus,
          });
          eventsFound++;
        }
      }
      const result = this.makeResult(providerId, true, entitiesFound, factsFound, eventsFound, duplicatesSkipped, conflictsDetected);
      this.ingestionHistory.push(result);
      return result;
    } catch (err) {
      const result = this.makeResult(providerId, false, 0, 0, 0, 0, 0, [String(err)]);
      this.ingestionHistory.push(result);
      return result;
    }
  }

  async ingestFromAll(): Promise<IngestionResult[]> {
    const results: IngestionResult[] = [];
    const enabled = Array.from(this.providers.values()).filter(p => p.enabled);
    // Process in batches respecting concurrency
    for (let i = 0; i < enabled.length; i += this.config.ingestionConcurrency) {
      const batch = enabled.slice(i, i + this.config.ingestionConcurrency);
      const batchResults = await Promise.allSettled(batch.map(p => this.ingestFromProvider(p.id)));
      for (const r of batchResults) {
        if (r.status === 'fulfilled') results.push(r.value);
        else results.push(this.makeResult('unknown', false, 0, 0, 0, 0, 0, [String(r.reason)]));
      }
    }
    return results;
  }

  getIngestionHistory(limit = 50): IngestionResult[] {
    return this.ingestionHistory.slice(-limit);
  }

  private normalizeItem(item: RawWorldItem, providerId: string): NormalizedItem {
    return {
      type: item.type,
      raw: item.raw,
      normalizedTitle: item.title || String(item.raw.title || item.raw.headline || ''),
      normalizedSummary: item.summary || String(item.raw.summary || item.raw.description || item.raw.snippet || ''),
      entities: [...(item.entities || [])],
      topics: [...((item.raw.topics || item.raw.keywords || []) as string[])],
      publishedAt: item.publishedAt || String(item.raw.publishedAt || item.raw.date || item.raw.published_date || ''),
      sourceUrl: item.sourceUrl || String(item.raw.url || item.raw.link || ''),
      providerId,
    };
  }

  private extractEntityCandidates(item: NormalizedItem): EntityCandidate[] {
    const candidates: EntityCandidate[] = [];
    // From explicit entities
    for (const name of item.entities) {
      candidates.push({
        name,
        entityType: 'OTHER',
        importance: 'MEDIUM',
      });
    }
    // From raw data entity fields
    const raw = item.raw;
    if (raw.entity_name && raw.entity_type) {
      candidates.push({
        name: String(raw.entity_name),
        entityType: this.mapEntityType(String(raw.entity_type)),
        importance: (raw.importance as ImportanceLevel) || 'MEDIUM',
      });
    }
    if (Array.isArray(raw.entities)) {
      for (const e of raw.entities) {
        if (typeof e === 'string') {
          candidates.push({ name: e, entityType: 'OTHER' });
        } else if (e && typeof e === 'object') {
          candidates.push({
            name: String(e.name || e.title || ''),
            entityType: this.mapEntityType(e.type),
            importance: e.importance || 'MEDIUM',
          });
        }
      }
    }
    return candidates.filter(c => c.name.length > 0);
  }

  private extractFactCandidates(item: NormalizedItem, entityIds: string[]): FactCandidate[] {
    const candidates: FactCandidate[] = [];
    const raw = item.raw;
    // Generic fact extraction from structured fields
    if (raw.predicate && (raw.object_value || raw.object_entity)) {
      candidates.push({
        subjectName: item.entities[0] || '',
        predicate: String(raw.predicate),
        objectName: raw.object_entity ? String(raw.object_entity) : undefined,
        objectValue: raw.object_value as string | number | boolean,
        confidence: (raw.confidence as number) || 0.7,
        observationStatus: 'OBSERVED',
        knowledgeLevel: 'CURRENT',
        publishedAt: item.publishedAt,
      });
    }
    // Market data facts
    if (raw.price !== undefined) {
      candidates.push({
        subjectName: item.entities[0] || '',
        predicate: 'price',
        objectValue: Number(raw.price),
        confidence: 0.9,
        observationStatus: 'OBSERVED',
        knowledgeLevel: 'CURRENT',
        publishedAt: item.publishedAt,
      });
    }
    // CEO facts
    if (raw.ceo || raw.chief_executive) {
      candidates.push({
        subjectName: item.entities[0] || '',
        predicate: 'CEO',
        objectName: String(raw.ceo || raw.chief_executive),
        confidence: 0.85,
        observationStatus: 'OBSERVED',
        knowledgeLevel: 'CURRENT',
        publishedAt: item.publishedAt,
      });
    }
    // Revenue facts
    if (raw.revenue !== undefined) {
      candidates.push({
        subjectName: item.entities[0] || '',
        predicate: 'revenue',
        objectValue: Number(raw.revenue),
        confidence: 0.8,
        observationStatus: 'OBSERVED',
        knowledgeLevel: 'CURRENT',
        publishedAt: item.publishedAt,
      });
    }
    // Weather facts
    if (raw.temperature !== undefined) {
      candidates.push({
        subjectName: item.entities[0] || '',
        predicate: 'temperature',
        objectValue: Number(raw.temperature),
        confidence: 0.9,
        observationStatus: 'OBSERVED',
        knowledgeLevel: 'CURRENT',
        publishedAt: item.publishedAt,
      });
    }
    return candidates.filter(c => c.subjectName.length > 0);
  }

  private extractEventCandidates(item: NormalizedItem, entityIds: string[]): EventCandidate[] {
    const candidates: EventCandidate[] = [];
    const raw = item.raw;
    const eventType = this.inferEventType(raw, item);
    const importance = this.inferImportance(raw, item);
    const freshness = this.inferFreshness(item.publishedAt);
    candidates.push({
      type: eventType,
      title: item.normalizedTitle || 'Untitled Event',
      summary: item.normalizedSummary || '',
      entityNames: [...item.entities],
      timestamp: item.publishedAt || nowISO(),
      importance,
      confidence: (raw.confidence as number) || 0.6,
      topics: [...item.topics],
      location: raw.location ? {
        country: String(raw.country || raw.location_country || ''),
        city: String(raw.city || raw.location_city || ''),
      } : undefined,
      freshnessClass: freshness,
      observationStatus: 'OBSERVED',
    });
    return candidates;
  }

  private inferEventType(raw: Record<string, unknown>, item: NormalizedItem): WorldEvent['type'] {
    const category = String(raw.category || raw.type || '').toLowerCase();
    if (category.includes('market') || category.includes('stock') || category.includes('trading')) return 'MARKET_MOVE';
    if (category.includes('earning') || category.includes('financial')) return 'EARNINGS';
    if (category.includes('policy') || category.includes('regulation')) return 'POLICY_CHANGE';
    if (category.includes('product') || category.includes('launch')) return 'PRODUCT_RELEASE';
    if (category.includes('science') || category.includes('research')) return 'SCIENTIFIC_DISCOVERY';
    if (category.includes('weather') || category.includes('climate')) return 'WEATHER_EVENT';
    if (category.includes('sport')) return 'SPORTS_RESULT';
    if (category.includes('politic')) return 'POLITICAL_EVENT';
    if (category.includes('tech') || category.includes('ai')) return 'TECH_EVENT';
    if (category.includes('economic') || category.includes('gdp') || category.includes('inflation')) return 'ECONOMIC_RELEASE';
    if (category.includes('central bank') || category.includes('fed') || category.includes('rbi')) return 'CENTRAL_BANK';
    // Default: check title/summary for hints
    const text = `${item.normalizedTitle} ${item.normalizedSummary}`.toLowerCase();
    if (text.includes('earthquake') || text.includes('hurricane') || text.includes('flood')) return 'NATURAL_EVENT';
    if (text.includes('ai ') || text.includes('artificial intelligence') || text.includes('openai') || text.includes('nvidia')) return 'TECH_EVENT';
    return 'NEWS';
  }

  private inferImportance(raw: Record<string, unknown>, item: NormalizedItem): ImportanceLevel {
    if (raw.importance) return raw.importance as ImportanceLevel;
    const text = `${item.normalizedTitle} ${item.normalizedSummary}`.toLowerCase();
    if (text.includes('breaking') || text.includes('urgent') || text.includes('critical')) return 'CRITICAL';
    if (text.includes('major') || text.includes('significant') || text.includes('important')) return 'HIGH';
    if (text.includes('minor') || text.includes('trivial')) return 'LOW';
    return 'MEDIUM';
  }

  private inferFreshness(publishedAt?: string): FreshnessClass {
    if (!publishedAt) return 'UNKNOWN';
    const age = Date.now() - new Date(publishedAt).getTime();
    if (age < 5 * 60 * 1000) return 'REALTIME';
    if (age < 60 * 60 * 1000) return 'MINUTES';
    if (age < 24 * 60 * 60 * 1000) return 'HOURLY';
    if (age < 7 * 24 * 60 * 60 * 1000) return 'DAILY';
    return 'HISTORICAL';
  }

  private findEntityByName(name: string, knownIds: string[]): WorldEntity | undefined {
    const matches = this.resolver.resolve(name);
    if (matches.length > 0) {
      return this.stateEngine.getEntity(matches[0].entityId);
    }
    return undefined;
  }

  private mapEntityType(rawType: string): WorldEntity['identity']['entityType'] {
    const lower = (rawType || '').toLowerCase();
    if (lower.includes('person') || lower.includes('human')) return 'PERSON';
    if (lower.includes('company') || lower.includes('corporation')) return 'COMPANY';
    if (lower.includes('country') || lower.includes('nation')) return 'COUNTRY';
    if (lower.includes('city')) return 'CITY';
    if (lower.includes('product')) return 'PRODUCT';
    if (lower.includes('organization') || lower.includes('org')) return 'ORGANIZATION';
    if (lower.includes('market')) return 'MARKET';
    if (lower.includes('currency')) return 'CURRENCY';
    if (lower.includes('technology') || lower.includes('tech')) return 'TECHNOLOGY';
    return 'OTHER';
  }

  private makeResult(
    providerId: string, success: boolean,
    entities: number, facts: number, events: number,
    duplicates: number, conflicts: number, errors: string[] = []
  ): IngestionResult {
    return {
      sourceId: providerId,
      success,
      entitiesFound: entities,
      factsFound: facts,
      eventsFound: events,
      duplicatesSkipped: duplicates,
      conflictsDetected: conflicts,
      errors,
      ingestedAt: nowISO(),
      durationMs: 0,
    };
  }
}
