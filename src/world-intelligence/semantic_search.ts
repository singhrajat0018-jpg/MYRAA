// ============================================================================
// MYRAA Semantic Search Engine — Lightweight TF-IDF (No External Dependencies)
// ============================================================================

import type { WorldEntity, TemporalFact, WorldEvent } from './contracts';

export interface SemanticDocument {
  readonly id: string;
  readonly type: 'entity' | 'fact' | 'event';
  readonly text: string;
  readonly tokens: string[];
  readonly tf: Map<string, number>;
  readonly metadata: Record<string, unknown>;
}

export interface SemanticResult {
  readonly id: string;
  readonly type: string;
  readonly score: number;
  readonly text: string;
  readonly metadata: Record<string, unknown>;
}

export interface SearchResult {
  readonly query: string;
  readonly results: readonly SemanticResult[];
  readonly totalIndexed: number;
  readonly processingTimeMs: number;
}

// ============================================================================
// Stop words (compact set for English)
// ============================================================================

const STOP_WORDS = new Set([
  'a', 'an', 'the', 'is', 'it', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
  'by', 'from', 'as', 'or', 'and', 'but', 'not', 'are', 'was', 'were', 'be',
  'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
  'could', 'should', 'may', 'might', 'shall', 'can', 'this', 'that', 'these',
  'those', 'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her', 'us',
  'them', 'my', 'your', 'his', 'its', 'our', 'their', 'what', 'which', 'who',
  'whom', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
  'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'only', 'own', 'same',
  'so', 'than', 'too', 'very', 'just', 'because', 'if', 'then', 'else', 'up',
  'out', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
  'between', 'under', 'again', 'further', 'once', 'here', 'there', 'also',
]);

// ============================================================================
// Tokenizer
// ============================================================================

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 1 && !STOP_WORDS.has(t));
}

// ============================================================================
// Semantic Index (TF-IDF)
// ============================================================================

export class SemanticIndex {
  private documents: Map<string, SemanticDocument> = new Map();
  private df: Map<string, number> = new Map(); // document frequency per term
  private totalDocs = 0;
  private idfCache: Map<string, number> = new Map();
  private idfDirty = true;

  addDocument(id: string, type: SemanticDocument['type'], text: string, metadata: Record<string, unknown> = {}): void {
    const tokens = tokenize(text);
    const tf = new Map<string, number>();
    for (const token of tokens) {
      tf.set(token, (tf.get(token) || 0) + 1);
    }
    // Normalize TF
    const maxTf = Math.max(1, ...Array.from(tf.values()));
    for (const [k, v] of tf) {
      tf.set(k, v / maxTf);
    }
    // Update DF
    const uniqueTokens = new Set(tokens);
    for (const token of uniqueTokens) {
      this.df.set(token, (this.df.get(token) || 0) + 1);
    }
    this.totalDocs++;
    this.idfDirty = true;
    this.documents.set(id, { id, type, text, tokens, tf, metadata });
  }

  removeDocument(id: string): void {
    const doc = this.documents.get(id);
    if (!doc) return;
    const uniqueTokens = new Set(doc.tokens);
    for (const token of uniqueTokens) {
      const count = this.df.get(token) || 0;
      if (count <= 1) this.df.delete(token);
      else this.df.set(token, count - 1);
    }
    this.totalDocs--;
    this.idfDirty = true;
    this.documents.delete(id);
  }

  search(query: string, limit = 20, typeFilter?: string): SemanticResult[] {
    const queryTokens = tokenize(query);
    if (queryTokens.length === 0) return [];
    this.recomputeIdf();
    const queryTf = new Map<string, number>();
    for (const t of queryTokens) {
      queryTf.set(t, (queryTf.get(t) || 0) + 1);
    }
    const maxQtf = Math.max(1, ...Array.from(queryTf.values()));
    for (const [k, v] of queryTf) {
      queryTf.set(k, v / maxQtf);
    }
    // Compute query IDF vector
    const queryIdf = new Map<string, number>();
    for (const t of queryTokens) {
      queryIdf.set(t, this.idfCache.get(t) || 0);
    }
    // Score each document
    const results: { id: string; type: string; score: number; text: string; metadata: Record<string, unknown> }[] = [];
    for (const [docId, doc] of this.documents) {
      if (typeFilter && doc.type !== typeFilter) continue;
      let score = 0;
      for (const [token, qTf] of queryTf) {
        const docTf = doc.tf.get(token) || 0;
        const idf = this.idfCache.get(token) || 0;
        score += qTf * docTf * idf * idf; // TF-IDF cosine similarity approximation
      }
      if (score > 0) {
        results.push({ id: docId, type: doc.type, score, text: doc.text, metadata: doc.metadata });
      }
    }
    return results
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(r => ({ id: r.id, type: r.type, score: r.score, text: r.text, metadata: r.metadata }));
  }

  size(): number {
    return this.documents.size;
  }

  clear(): void {
    this.documents.clear();
    this.df.clear();
    this.idfCache.clear();
    this.totalDocs = 0;
    this.idfDirty = true;
  }

  getDocument(id: string): SemanticDocument | undefined {
    return this.documents.get(id);
  }

  private recomputeIdf(): void {
    if (!this.idfDirty) return;
    this.idfCache.clear();
    for (const [term, freq] of this.df) {
      this.idfCache.set(term, Math.log((this.totalDocs + 1) / (freq + 1)) + 1);
    }
    this.idfDirty = false;
  }
}

// ============================================================================
// Hybrid Search Engine
// ============================================================================

export interface HybridSearchConfig {
  readonly keywordWeight: number;
  readonly semanticWeight: number;
  readonly freshnessWeight: number;
  readonly entityWeight: number;
  readonly importanceWeight: number;
}

const DEFAULT_HYBRID_CONFIG: HybridSearchConfig = {
  keywordWeight: 0.3,
  semanticWeight: 0.3,
  freshnessWeight: 0.15,
  entityWeight: 0.15,
  importanceWeight: 0.1,
};

export class HybridSearchEngine {
  private semanticIndex = new SemanticIndex();
  private config: HybridSearchConfig;
  private entityIndex: Map<string, Set<string>> = new Map(); // entity name (lower) -> doc IDs
  private topicIndex: Map<string, Set<string>> = new Map(); // topic (lower) -> doc IDs

  constructor(config?: Partial<HybridSearchConfig>) {
    this.config = { ...DEFAULT_HYBRID_CONFIG, ...config };
  }

  // --- Indexing ---

  indexEntity(entity: WorldEntity): void {
    const text = [
      entity.identity.canonicalName,
      ...entity.identity.aliases.map(a => a.name),
      entity.identity.entityType,
      ...entity.tags,
    ].join(' ');
    this.semanticIndex.addDocument(entity.id, 'entity', text, {
      entityType: entity.identity.entityType,
      importance: entity.importance,
      name: entity.identity.canonicalName,
    });
    // Update entity index
    const nameLower = entity.identity.canonicalName.toLowerCase();
    const set = this.entityIndex.get(nameLower) || new Set();
    set.add(entity.id);
    this.entityIndex.set(nameLower, set);
    for (const alias of entity.identity.aliases) {
      const aSet = this.entityIndex.get(alias.name.toLowerCase()) || new Set();
      aSet.add(entity.id);
      this.entityIndex.set(alias.name.toLowerCase(), aSet);
    }
  }

  indexEvent(event: WorldEvent): void {
    const text = [event.title, event.summary, ...event.topicIds, ...event.tags].join(' ');
    this.semanticIndex.addDocument(event.id, 'event', text, {
      eventType: event.type,
      importance: event.importance,
      timestamp: event.timestamp,
      entityIds: event.entityIds,
      topics: event.topicIds,
      freshnessClass: event.freshnessClass,
    });
    for (const topic of event.topicIds) {
      const set = this.topicIndex.get(topic.toLowerCase()) || new Set();
      set.add(event.id);
      this.topicIndex.set(topic.toLowerCase(), set);
    }
  }

  indexFact(fact: TemporalFact): void {
    const text = [fact.predicate, String(fact.objectValue || ''), fact.subjectId].join(' ');
    this.semanticIndex.addDocument(fact.id, 'fact', text, {
      subjectId: fact.subjectId,
      predicate: fact.predicate,
      confidence: fact.confidence,
      status: fact.status,
    });
  }

  removeDocument(id: string): void {
    this.semanticIndex.removeDocument(id);
  }

  // --- Hybrid Search ---

  search(query: string, options: {
    limit?: number;
    type?: 'entity' | 'fact' | 'event';
    entityFilter?: string[];
    topicFilter?: string[];
    timeRange?: { from?: string; to?: string };
    freshnessBoost?: boolean;
  } = {}): { results: SemanticResult[]; totalIndexed: number } {
    const limit = options.limit || 20;
    const start = Date.now();

    // 1. Semantic search
    const semanticResults = this.semanticIndex.search(query, limit * 3, options.type);

    // 2. Entity search
    const queryLower = query.toLowerCase();
    const entityMatches = new Set<string>();
    for (const [name, ids] of this.entityIndex) {
      if (name.includes(queryLower) || queryLower.includes(name)) {
        for (const id of ids) entityMatches.add(id);
      }
    }

    // 3. Topic search
    const topicMatches = new Set<string>();
    for (const [topic, ids] of this.topicIndex) {
      if (topic.includes(queryLower) || queryLower.includes(topic)) {
        for (const id of ids) topicMatches.add(id);
      }
    }

    // 4. Combine scores
    const scoreMap = new Map<string, { result: SemanticResult; combinedScore: number }>();
    for (const r of semanticResults) {
      const meta = r.metadata as Record<string, unknown>;
      let score = r.score * this.config.semanticWeight;
      // Keyword bonus
      if (r.text.toLowerCase().includes(queryLower)) {
        score += this.config.keywordWeight;
      }
      // Entity match bonus
      if (entityMatches.has(r.id)) {
        score += this.config.entityWeight;
      }
      // Topic match bonus
      if (topicMatches.has(r.id)) {
        score += this.config.entityWeight;
      }
      // Freshness bonus
      if (options.freshnessBoost && meta.freshnessClass) {
        const freshnessScore: Record<string, number> = {
          REALTIME: 1.0, MINUTES: 0.9, HOURLY: 0.7, DAILY: 0.5, STATIC: 0.2, HISTORICAL: 0.1, UNKNOWN: 0.3,
        };
        score += (freshnessScore[String(meta.freshnessClass)] || 0.3) * this.config.freshnessWeight;
      }
      // Importance bonus
      if (meta.importance) {
        const impScore: Record<string, number> = {
          CRITICAL: 1.0, HIGH: 0.8, MEDIUM: 0.5, LOW: 0.3, INFO: 0.1,
        };
        score += (impScore[String(meta.importance)] || 0.5) * this.config.importanceWeight;
      }
      // Apply filters
      if (options.entityFilter && options.entityFilter.length > 0) {
        const metaEntityIds = (meta.entityIds as string[]) || [];
        if (!options.entityFilter.some(eid => metaEntityIds.includes(eid))) {
          if (r.type !== 'entity') continue; // entities pass through
        }
      }
      if (options.topicFilter && options.topicFilter.length > 0) {
        const metaTopics = (meta.topics as string[]) || [];
        if (!options.topicFilter.some(t => metaTopics.includes(t))) {
          continue;
        }
      }
      if (options.timeRange) {
        const ts = String(meta.timestamp || meta.validFrom || '');
        if (options.timeRange.from && ts < options.timeRange.from) continue;
        if (options.timeRange.to && ts > options.timeRange.to) continue;
      }
      scoreMap.set(r.id, { result: r, combinedScore: score });
    }

    // 5. Boost entity matches not already in semantic results
    for (const id of entityMatches) {
      if (!scoreMap.has(id)) {
        const doc = this.semanticIndex.getDocument(id);
        if (doc) {
          scoreMap.set(id, {
            result: { id, type: doc.type, score: 0, text: doc.text, metadata: doc.metadata },
            combinedScore: this.config.entityWeight + 0.1,
          });
        }
      }
    }

    // 6. Sort and limit
    const sorted = Array.from(scoreMap.values())
      .sort((a, b) => b.combinedScore - a.combinedScore)
      .slice(0, limit)
      .map(e => ({ ...e.result, score: e.combinedScore }));

    return { results: sorted, totalIndexed: this.semanticIndex.size() };
  }

  size(): number {
    return this.semanticIndex.size();
  }

  clear(): void {
    this.semanticIndex.clear();
    this.entityIndex.clear();
    this.topicIndex.clear();
  }
}
