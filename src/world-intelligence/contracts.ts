// ============================================================================
// MYRAA World Intelligence Engine — Typed Contracts
// ============================================================================

// --- Entity Types ---

export type EntityType =
  | 'PERSON'
  | 'COMPANY'
  | 'COUNTRY'
  | 'CITY'
  | 'PLACE'
  | 'PRODUCT'
  | 'ORGANIZATION'
  | 'EVENT'
  | 'MARKET'
  | 'ASSET'
  | 'CURRENCY'
  | 'SPORTS_TEAM'
  | 'SPORTS_EVENT'
  | 'SCIENTIFIC_OBJECT'
  | 'SPACE_OBJECT'
  | 'TECHNOLOGY'
  | 'PUBLICATION'
  | 'REGULATION'
  | 'WEATHER_SYSTEM'
  | 'OTHER';

// --- Knowledge Levels ---

export type KnowledgeLevel =
  | 'STATIC'
  | 'CURRENT'
  | 'HISTORICAL'
  | 'PREDICTED'
  | 'INFERRED'
  | 'USER_MEMORY';

// --- Observation Status ---

export type ObservationStatus =
  | 'OBSERVED'
  | 'DERIVED'
  | 'INFERRED'
  | 'UNKNOWN';

// --- Freshness Classes ---

export type FreshnessClass =
  | 'REALTIME'
  | 'MINUTES'
  | 'HOURLY'
  | 'DAILY'
  | 'STATIC'
  | 'HISTORICAL'
  | 'UNKNOWN';

// --- Staleness ---

export type StalenessStatus = 'CURRENT' | 'STALE' | 'EXPIRED' | 'UNKNOWN';

// --- Event Types ---

export type WorldEventType =
  | 'NEWS'
  | 'MARKET_MOVE'
  | 'EARNINGS'
  | 'POLICY_CHANGE'
  | 'PRODUCT_RELEASE'
  | 'SCIENTIFIC_DISCOVERY'
  | 'WEATHER_EVENT'
  | 'NATURAL_EVENT'
  | 'SPORTS_RESULT'
  | 'POLITICAL_EVENT'
  | 'COMPANY_EVENT'
  | 'TECH_EVENT'
  | 'FINANCIAL_DATA'
  | 'ECONOMIC_RELEASE'
  | 'CENTRAL_BANK'
  | 'GEOPOLITICAL'
  | 'ENVIRONMENT'
  | 'TRANSPORTATION'
  | 'OTHER';

// --- Event Status ---

export type EventStatus = 'EMERGING' | 'ACTIVE' | 'DEVELOPING' | 'STABLE' | 'RESOLVED' | 'STALE' | 'RETRACTED';

// --- Importance ---

export type ImportanceLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

// --- Source Classes ---

export type SourceClass = 'PRIMARY' | 'SECONDARY' | 'AGGREGATOR' | 'DISCOVERY' | 'USER_PROVIDED' | 'INFERRED';

// --- Fact Status ---

export type FactStatus = 'ACTIVE' | 'SUPERSEDED' | 'RETRACTED' | 'CORRECTED' | 'EXPIRED' | 'CONFLICTED' | 'UNKNOWN';

// --- Verification Status ---

export type VerificationStatus = 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'CONFLICTING' | 'UNVERIFIED' | 'RETRACTED';

// --- Memory Namespaces ---

export type MemoryNamespace = 'USER_MEMORY' | 'WORLD_MEMORY' | 'TASK_MEMORY' | 'CAPABILITY_MEMORY';

// --- Query Types ---

export type WorldQueryType =
  | 'ENTITY_LOOKUP'
  | 'EVENT_LOOKUP'
  | 'FACT_LOOKUP'
  | 'TEMPORAL_QUERY'
  | 'COMPARISON'
  | 'CHANGE_DETECTION'
  | 'SOURCE_FILTER'
  | 'FRESHNESS_FILTER'
  | 'TOPIC_SEARCH'
  | 'NATURAL_LANGUAGE';

// --- Trend Confidence ---

export type TrendConfidence = 'STRONG' | 'MODERATE' | 'WEAK' | 'UNKNOWN';

// --- Relationship Types (Knowledge Graph) ---

export type RelationshipType =
  | 'RELATES_TO'
  | 'PART_OF'
  | 'LOCATED_IN'
  | 'OWNED_BY'
  | 'WORKS_FOR'
  | 'AFFECTS'
  | 'CAUSES'
  | 'MENTIONS'
  | 'CONTRADICTS'
  | 'REPORTED_BY'
  | 'SUBSIDIARY_OF'
  | 'HEADQUARTERED_IN'
  | 'FOUNDED_BY'
  | 'CEO_OF'
  | 'COMPETES_WITH'
  | 'PARTNER_OF'
  | 'REGULATED_BY'
  | 'TRIGGERS'
  | 'FOLLOWS'
  | 'PRECEDES';

// ============================================================================
// Core Entity
// ============================================================================

export interface EntityAlias {
  readonly name: string;
  readonly type: 'canonical' | 'alias' | 'abbreviation' | 'ticker' | 'external_id' | 'localized' | 'provider_id';
  readonly source?: string;
}

export interface EntityIdentity {
  readonly canonicalId: string;
  readonly canonicalName: string;
  readonly aliases: readonly EntityAlias[];
  readonly entityType: EntityType;
  readonly subType?: string;
}

export interface WorldEntity {
  readonly id: string;
  readonly identity: EntityIdentity;
  readonly createdAt: string; // ISO 8601
  readonly updatedAt: string;
  readonly lastIngestedAt?: string;
  readonly importance: ImportanceLevel;
  readonly tags: readonly string[];
  readonly metadata: Record<string, unknown>;
  readonly knownFacts: readonly string[]; // fact IDs
  readonly knownEvents: readonly string[]; // event IDs
  readonly knowledgeLevel: KnowledgeLevel;
}

// ============================================================================
// Fact Model
// ============================================================================

export interface FactProvenance {
  readonly sourceId: string;
  readonly sourceClass: SourceClass;
  readonly providerId: string;
  readonly retrievedAt: string;
  readonly publishedAt?: string;
  readonly eventAt?: string;
  readonly confidence: number; // 0-1
  readonly verificationStatus: VerificationStatus;
}

export interface TemporalFact {
  readonly id: string;
  readonly subjectId: string; // entity ID
  readonly predicate: string;
  readonly objectId?: string; // entity ID or null for literal
  readonly objectValue?: string | number | boolean; // literal value
  readonly status: FactStatus;
  readonly observationStatus: ObservationStatus;
  readonly validFrom: string;
  readonly validTo?: string; // null = still valid
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly provenance: readonly FactProvenance[];
  readonly confidence: number;
  readonly knowledgeLevel: KnowledgeLevel;
  readonly metadata: Record<string, unknown>;
}

// ============================================================================
// Event Model
// ============================================================================

export interface EventSource {
  readonly sourceId: string;
  readonly providerId: string;
  readonly sourceClass: SourceClass;
  readonly url?: string;
  readonly title?: string;
  readonly retrievedAt: string;
  readonly publishedAt?: string;
}

export interface WorldEvent {
  readonly id: string;
  readonly type: WorldEventType;
  readonly title: string;
  readonly summary: string;
  readonly entityIds: readonly string[];
  readonly timestamp: string; // event time
  readonly publishedAt?: string;
  readonly retrievedAt: string;
  readonly location?: {
    readonly country?: string;
    readonly region?: string;
    readonly city?: string;
    readonly coordinates?: { lat: number; lng: number };
  };
  readonly importance: ImportanceLevel;
  readonly status: EventStatus;
  readonly confidence: number;
  readonly sources: readonly EventSource[];
  readonly topicIds: readonly string[];
  readonly relatedEventIds: readonly string[];
  readonly tags: readonly string[];
  readonly metadata: Record<string, unknown>;
  readonly freshnessClass: FreshnessClass;
  readonly staleness: StalenessStatus;
  readonly observationStatus: ObservationStatus;
}

// ============================================================================
// Knowledge Graph
// ============================================================================

export interface GraphNode {
  readonly id: string;
  readonly type: 'entity' | 'event' | 'fact' | 'source' | 'document' | 'topic';
  readonly label: string;
  readonly metadata: Record<string, unknown>;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface GraphEdge {
  readonly id: string;
  readonly sourceId: string;
  readonly targetId: string;
  readonly relationship: RelationshipType;
  readonly observationStatus: ObservationStatus;
  readonly confidence: number;
  readonly validFrom: string;
  readonly validTo?: string;
  readonly sourceRef: string; // provenance source
  readonly metadata: Record<string, unknown>;
}

export interface KnowledgeGraph {
  readonly nodes: Map<string, GraphNode>;
  readonly edges: Map<string, GraphEdge>;
  readonly adjacency: Map<string, Set<string>>; // node ID -> edge IDs
}

// ============================================================================
// World State
// ============================================================================

export interface WorldStateSnapshot {
  readonly timestamp: string;
  readonly entities: Map<string, WorldEntity>;
  readonly facts: Map<string, TemporalFact>;
  readonly events: Map<string, WorldEvent>;
  readonly graph: KnowledgeGraph;
  readonly checksum: string;
}

export interface WorldStateDiff {
  readonly fromTimestamp: string;
  readonly toTimestamp: string;
  readonly addedEntities: readonly WorldEntity[];
  readonly removedEntities: readonly string[];
  readonly changedEntities: readonly { entity: WorldEntity; changes: string[] }[];
  readonly addedFacts: readonly TemporalFact[];
  readonly removedFacts: readonly string[];
  readonly changedFacts: readonly { fact: TemporalFact; changes: string[] }[];
  readonly addedEvents: readonly WorldEvent[];
  readonly removedEvents: readonly string[];
  readonly newTopicIds: readonly string[];
}

// ============================================================================
// Query Engine
// ============================================================================

export interface WorldQuery {
  readonly type: WorldQueryType;
  readonly entityIds?: readonly string[];
  readonly entityType?: EntityType;
  readonly eventTypes?: readonly WorldEventType[];
  readonly topics?: readonly string[];
  readonly timeRange?: { from?: string; to?: string };
  readonly freshness?: FreshnessClass;
  readonly sourceFilter?: readonly string[];
  readonly maxResults?: number;
  readonly includeProvenance?: boolean;
  readonly includeGraph?: boolean;
  readonly naturalLanguageQuery?: string;
}

export interface WorldQueryResult {
  readonly query: WorldQuery;
  readonly entities: readonly WorldEntity[];
  readonly facts: readonly TemporalFact[];
  readonly events: readonly WorldEvent[];
  readonly graphNodes: readonly GraphNode[];
  readonly graphEdges: readonly GraphEdge[];
  readonly totalResults: number;
  readonly confidence: number;
  readonly freshness: FreshnessClass;
  readonly sourcesUsed: readonly string[];
  readonly queriedAt: string;
  readonly processingTimeMs: number;
}

// ============================================================================
// Ingestion
// ============================================================================

export interface IngestionSource {
  readonly providerId: string;
  readonly sourceClass: SourceClass;
  readonly category: string;
  readonly lastIngestedAt?: string;
  readonly enabled: boolean;
  readonly priority: number; // 1=highest
  readonly refreshIntervalMs: number;
}

export interface IngestionResult {
  readonly sourceId: string;
  readonly success: boolean;
  readonly entitiesFound: number;
  readonly factsFound: number;
  readonly eventsFound: number;
  readonly duplicatesSkipped: number;
  readonly conflictsDetected: number;
  readonly errors: readonly string[];
  readonly ingestedAt: string;
  readonly durationMs: number;
}

export interface RawWorldData {
  readonly providerId: string;
  readonly retrievedAt: string;
  readonly items: readonly RawWorldItem[];
}

export interface RawWorldItem {
  readonly type: 'entity' | 'fact' | 'event';
  readonly raw: Record<string, unknown>;
  readonly sourceUrl?: string;
  readonly publishedAt?: string;
  readonly title?: string;
  readonly summary?: string;
  readonly entities?: readonly string[];
}

// ============================================================================
// Watchers
// ============================================================================

export type WatcherStatus = 'ACTIVE' | 'PAUSED' | 'STOPPED' | 'EXPIRED';

export interface WatcherPolicy {
  readonly importance: ImportanceLevel;
  readonly cooldownMs: number;
  readonly maxAlertsPerHour: number;
  readonly expirationMs?: number;
  readonly channels: readonly ('notification' | 'voice' | 'text')[];
}

export interface WorldWatcher {
  readonly id: string;
  readonly entityType?: EntityType;
  readonly entityIds?: readonly string[];
  readonly topics?: readonly string[];
  readonly eventTypes?: readonly WorldEventType[];
  readonly policy: WatcherPolicy;
  readonly status: WatcherStatus;
  readonly createdAt: string;
  readonly lastTriggeredAt?: string;
  readonly triggerCount: number;
  readonly metadata: Record<string, unknown>;
}

export interface WatcherAlert {
  readonly id: string;
  readonly watcherId: string;
  readonly eventIds: readonly string[];
  readonly entityIds: readonly string[];
  readonly title: string;
  readonly summary: string;
  readonly importance: ImportanceLevel;
  readonly createdAt: string;
  readonly acknowledged: boolean;
}

// ============================================================================
// Data Quality
// ============================================================================

export interface DataQualityMetrics {
  readonly totalEntities: number;
  readonly totalFacts: number;
  readonly totalEvents: number;
  readonly activeFacts: number;
  readonly expiredFacts: number;
  readonly retractedFacts: number;
  readonly conflictingFacts: number;
  readonly avgFactConfidence: number;
  readonly avgEntityAliases: number;
  readonly sourceDistribution: Record<string, number>;
  readonly freshnessDistribution: Record<FreshnessClass, number>;
  readonly eventStatusDistribution: Record<EventStatus, number>;
  readonly lastIngestionAt?: string;
  readonly ingestionCount24h: number;
  readonly deduplicationRate: number;
}

// ============================================================================
// Engine Options
// ============================================================================

export interface WorldIntelligenceConfig {
  readonly maxEntities: number;
  readonly maxFacts: number;
  readonly maxEvents: number;
  readonly maxGraphNodes: number;
  readonly maxGraphEdges: number;
  readonly defaultRetentionMs: number;
  readonly snapshotIntervalMs: number;
  readonly ingestionConcurrency: number;
  readonly queryTimeoutMs: number;
  readonly enablePersistence: boolean;
  readonly persistencePath?: string;
  readonly enableWatchers: boolean;
  readonly memoryNamespace: MemoryNamespace;
}

export const DEFAULT_WORLD_CONFIG: WorldIntelligenceConfig = {
  maxEntities: 100_000,
  maxFacts: 500_000,
  maxEvents: 200_000,
  maxGraphNodes: 200_000,
  maxGraphEdges: 500_000,
  defaultRetentionMs: 90 * 24 * 60 * 60 * 1000, // 90 days
  snapshotIntervalMs: 60 * 60 * 1000, // 1 hour
  ingestionConcurrency: 5,
  queryTimeoutMs: 10_000,
  enablePersistence: true,
  enableWatchers: true,
  memoryNamespace: 'WORLD_MEMORY',
};

// ============================================================================
// Engine Events
// ============================================================================

export type WorldEngineEventType =
  | 'entity_created'
  | 'entity_updated'
  | 'entity_merged'
  | 'entity_split'
  | 'fact_created'
  | 'fact_updated'
  | 'fact_retracted'
  | 'fact_conflict'
  | 'event_ingested'
  | 'event_deduplicated'
  | 'event_correlated'
  | 'event_status_changed'
  | 'graph_updated'
  | 'snapshot_created'
  | 'snapshot_restored'
  | 'watcher_triggered'
  | 'ingestion_started'
  | 'ingestion_completed'
  | 'ingestion_failed'
  | 'source_health_changed'
  | 'staleness_detected'
  | 'conflict_detected'
  | 'retraction_processed';

export interface WorldEngineEvent {
  readonly type: WorldEngineEventType;
  readonly timestamp: string;
  readonly data: Record<string, unknown>;
}

// ============================================================================
// Utility
// ============================================================================

export function generateWorldId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `w_${timestamp}_${random}`;
}

export function nowISO(): string {
  return new Date().toISOString();
}

export function computeChecksum(data: string): string {
  let hash = 0;
  for (let i = 0; i < data.length; i++) {
    const char = data.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}
