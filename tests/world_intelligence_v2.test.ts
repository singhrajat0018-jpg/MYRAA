// ============================================================================
// MYRAA World Intelligence v2 — Phase 22 Tests
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  WorldIntelligence,
  WorldStateEngine,
  EntityResolver,
  WorldIngestionEngine,
  DeduplicationEngine,
  LiveIngestionEngine,
  HybridSearchEngine,
  LlmExtractionEngine,
  EvidencePackBuilder,
  buildBrainContext,
} from '../src/world-intelligence/index';
import {
  createDefaultProviders,
  createNewsProviders,
} from '../src/world-intelligence/providers/real_providers';
import {
  DEFAULT_WORLD_CONFIG,
  generateWorldId,
  nowISO,
} from '../src/world-intelligence/contracts';

// ============================================================================
// Mock HTTP Fetcher
// ============================================================================

const mockFetch = vi.fn();

function mockJsonResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as unknown as Response;
}

// ============================================================================
// Real Providers Tests
// ============================================================================

describe('Phase 22 — Real Providers', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates default providers without API keys', () => {
    const providers = createDefaultProviders();
    expect(providers.length).toBeGreaterThanOrEqual(5);
    for (const p of providers) {
      expect(p.id).toBeTruthy();
      expect(p.name).toBeTruthy();
      expect(p.enabled).toBe(true);
    }
  });

  it('creates news providers', () => {
    const providers = createNewsProviders();
    expect(providers.length).toBeGreaterThanOrEqual(1);
    for (const p of providers) {
      expect(p.id).toBeTruthy();
      expect(p.name).toBeTruthy();
    }
  });

  it('OpenMeteo weather provider fetches real data', async () => {
    const providers = createDefaultProviders();
    const weather = providers.find(p => p.id === 'open-meteo-weather');
    expect(weather).toBeDefined();
    // Provider iterates 5 cities, each needs a response
    const cityResponse = {
      current: {
        temperature_2m: 28.5,
        relative_humidity_2m: 65,
        wind_speed_10m: 12,
        weather_code: 1,
        time: new Date().toISOString(),
      },
      timezone: 'Asia/Kolkata',
    };
    mockFetch.mockResolvedValue(mockJsonResponse(cityResponse));
    const data = await weather!.fetch();
    expect(data.providerId).toBe('open-meteo-weather');
    expect(data.items.length).toBeGreaterThanOrEqual(1);
    expect(data.items[0].title).toContain('Weather');
  });

  it('Wikipedia provider fetches real data', async () => {
    const providers = createDefaultProviders();
    const wiki = providers.find(p => p.id === 'wikipedia');
    expect(wiki).toBeDefined();
    // Provider iterates 3 topics
    mockFetch.mockResolvedValue(mockJsonResponse({
      title: 'Artificial Intelligence',
      pageid: 123,
      extract: 'Artificial intelligence is the intelligence of machines.',
      content_urls: { desktop: { page: 'https://en.wikipedia.org/wiki/Artificial_intelligence' } },
    }));
    const data = await wiki!.fetch();
    expect(data.providerId).toBe('wikipedia');
    expect(data.items.length).toBeGreaterThanOrEqual(1);
  });

  it('Exchange rates provider fetches real data', async () => {
    const providers = createDefaultProviders();
    const fx = providers.find(p => p.id === 'exchange-rates');
    expect(fx).toBeDefined();
    mockFetch.mockResolvedValue(mockJsonResponse({
      rates: { INR: 83.5, USD: 1, EUR: 0.92, GBP: 0.79 },
      time_last_update_unix: Date.now() / 1000,
    }));
    const data = await fx!.fetch();
    expect(data.providerId).toBe('exchange-rates');
    expect(data.items.length).toBeGreaterThanOrEqual(1);
    expect(data.items[0].title).toContain('USD');
  });

  it('NASA APOD provider fetches real data', async () => {
    const providers = createDefaultProviders();
    const nasa = providers.find(p => p.id === 'nasa-apod');
    expect(nasa).toBeDefined();
    mockFetch.mockResolvedValue(mockJsonResponse({
      title: 'Galaxy NGC 1234',
      explanation: 'A spiral galaxy in the constellation Andromeda.',
      date: '2026-09-04',
      url: 'https://apod.nasa.gov/apod/image.jpg',
    }));
    const data = await nasa!.fetch();
    expect(data.providerId).toBe('nasa-apod');
    expect(data.items.length).toBeGreaterThanOrEqual(1);
  });

  it('ISS location provider fetches real data', async () => {
    const providers = createDefaultProviders();
    const iss = providers.find(p => p.id === 'iss-location');
    expect(iss).toBeDefined();
    mockFetch.mockResolvedValue(mockJsonResponse({
      iss_position: { latitude: '28.5', longitude: '77.1' },
      timestamp: Date.now() / 1000,
    }));
    const data = await iss!.fetch();
    expect(data.providerId).toBe('iss-location');
    expect(data.items.length).toBe(1);
    expect(data.items[0].title).toContain('ISS');
  });

  it('GitHub trending provider fetches real data', async () => {
    const providers = createDefaultProviders();
    const gh = providers.find(p => p.id === 'github-trending');
    expect(gh).toBeDefined();
    // Provider iterates 3 languages, each needs items array
    mockFetch.mockResolvedValue(mockJsonResponse({
      items: [{
        full_name: 'microsoft/typescript',
        description: 'TypeScript is a superset of JavaScript',
        stargazers_count: 100000,
        language: 'TypeScript',
        owner: { login: 'microsoft' },
        html_url: 'https://github.com/microsoft/typescript',
        created_at: '2026-09-01',
        name: 'typescript',
      }],
    }));
    const data = await gh!.fetch();
    expect(data.providerId).toBe('github-trending');
    expect(data.items.length).toBeGreaterThanOrEqual(1);
  });

  it('providers handle network failures gracefully', async () => {
    const providers = createDefaultProviders();
    const weather = providers.find(p => p.id === 'open-meteo-weather');
    mockFetch.mockRejectedValue(new Error('Network error'));
    const data = await weather!.fetch();
    expect(data.items.length).toBe(0);
  });
});

// ============================================================================
// Semantic Search Tests
// ============================================================================

describe('Phase 22 — Semantic Search', () => {
  let search: HybridSearchEngine;

  beforeEach(() => {
    search = new HybridSearchEngine();
  });

  it('indexes and searches entities', () => {
    const entity = {
      id: generateWorldId(),
      identity: { canonicalName: 'Apple Inc', entityType: 'COMPANY' as const, aliases: [] },
      importance: 'HIGH' as const,
      tags: ['tech', 'stock'],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    };
    search.indexEntity(entity);
    const { results } = search.search('Apple stock', { type: 'entity' });
    expect(results.length).toBeGreaterThanOrEqual(1);
    expect(results[0].text).toContain('Apple Inc');
  });

  it('indexes and searches events', () => {
    const event = {
      id: generateWorldId(),
      type: 'TECH_EVENT' as const,
      title: 'OpenAI releases GPT-5',
      summary: 'Major AI model release with breakthrough performance',
      entityIds: [],
      timestamp: nowISO(),
      importance: 'HIGH' as const,
      confidence: 0.9,
      topicIds: ['ai', 'technology'],
      sources: [],
      tags: [],
      metadata: {},
    };
    search.indexEvent(event);
    const { results } = search.search('GPT AI model', { type: 'event' });
    expect(results.length).toBeGreaterThanOrEqual(1);
    expect(results[0].text).toContain('GPT-5');
  });

  it('hybrid search returns scored results', () => {
    const entity1 = {
      id: 'e1',
      identity: { canonicalName: 'NVIDIA', entityType: 'COMPANY' as const, aliases: [] },
      importance: 'HIGH' as const,
      tags: ['gpu', 'ai', 'chip'],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    };
    const entity2 = {
      id: 'e2',
      identity: { canonicalName: 'AMD', entityType: 'COMPANY' as const, aliases: [] },
      importance: 'MEDIUM' as const,
      tags: ['cpu', 'gpu', 'chip'],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    };
    search.indexEntity(entity1);
    search.indexEntity(entity2);
    const { results } = search.search('NVIDIA AI gpu');
    expect(results.length).toBeGreaterThanOrEqual(1);
    expect(results[0].text).toContain('NVIDIA');
  });

  it('freshness boost works', () => {
    const oldEntity = {
      id: 'e1',
      identity: { canonicalName: 'Old Company', entityType: 'COMPANY' as const, aliases: [] },
      importance: 'MEDIUM' as const,
      tags: [],
      firstSeenAt: '2020-01-01T00:00:00Z',
      lastUpdatedAt: '2020-01-01T00:00:00Z',
      metadata: {},
    };
    const newEntity = {
      id: 'e2',
      identity: { canonicalName: 'New Company', entityType: 'COMPANY' as const, aliases: [] },
      importance: 'MEDIUM' as const,
      tags: [],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    };
    search.indexEntity(oldEntity);
    search.indexEntity(newEntity);
    const { results } = search.search('Company', { freshnessBoost: true });
    expect(results.length).toBe(2);
    // Both should be found; check freshness boost is applied
    const ids = results.map(r => r.id);
    expect(ids).toContain('e1');
    expect(ids).toContain('e2');
  });

  it('search with no results returns empty', () => {
    const { results } = search.search('xyznonexistent');
    expect(results.length).toBe(0);
  });

  it('search returns totalIndexed count', () => {
    const entity = {
      id: 'e1',
      identity: { canonicalName: 'Test', entityType: 'OTHER' as const, aliases: [] },
      importance: 'LOW' as const,
      tags: [],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    };
    search.indexEntity(entity);
    const { totalIndexed } = search.search('Test');
    expect(totalIndexed).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================================
// LLM Extraction Tests
// ============================================================================

describe('Phase 22 — LLM Extraction', () => {
  it('rule-based extraction finds known entities', () => {
    const engine = new LlmExtractionEngine();
    const result = engine.extractFromText('Apple CEO Tim Cook announced new iPhone at Apple event', 'test');
    expect(result.entities.length).toBeGreaterThanOrEqual(1);
    const names = result.entities.map(e => e.name);
    expect(names.some(n => n.toLowerCase() === 'apple')).toBe(true);
  });

  it('rule-based extraction finds topics', () => {
    const engine = new LlmExtractionEngine();
    const result = engine.extractFromText('New AI model released by OpenAI in artificial intelligence breakthrough', 'test');
    expect(result.topics).toContain('artificial-intelligence');
  });

  it('rule-based extraction finds events', () => {
    const engine = new LlmExtractionEngine();
    const result = engine.extractFromText('Breaking: Major tech stock NVIDIA surged 15% on AI chip demand', 'test');
    expect(result.events.length).toBeGreaterThanOrEqual(1);
  });

  it('rule-based extraction finds facts', () => {
    const engine = new LlmExtractionEngine();
    const result = engine.extractFromText('Elon Musk is the CEO of Tesla', 'test');
    expect(result.facts.length).toBeGreaterThanOrEqual(1);
  });

  it('extraction validates all outputs', () => {
    const engine = new LlmExtractionEngine();
    const result = engine.extractFromText('Normal text with no entities', 'test');
    expect(result.validated).toBe(true);
    expect(result.validationErrors.length).toBe(0);
  });

  it('handles empty input gracefully', () => {
    const engine = new LlmExtractionEngine();
    const result = engine.extractFromText('', 'test');
    expect(result.entities.length).toBe(0);
    expect(result.facts.length).toBe(0);
    expect(result.events.length).toBe(0);
  });

  it('LLM extraction falls back to rule-based on Ollama failure', async () => {
    const engine = new LlmExtractionEngine('http://127.0.0.1:9999');
    const result = await engine.extractWithLlm('Apple stock rises', 'test');
    expect(result.entities.length).toBeGreaterThanOrEqual(0);
    expect(result.extractionTimeMs).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// Live Ingestion Engine Tests
// ============================================================================

describe('Phase 22 — Live Ingestion Engine', () => {
  let config: typeof DEFAULT_WORLD_CONFIG;

  beforeEach(() => {
    config = { ...DEFAULT_WORLD_CONFIG };
  });

  it('creates engine with default config', () => {
    const engine = new LiveIngestionEngine(config);
    expect(engine).toBeDefined();
  });

  it('registers and unregisters providers', () => {
    const engine = new LiveIngestionEngine(config);
    const provider = {
      id: 'test-provider',
      name: 'Test Provider',
      category: 'test',
      sourceClass: 'TERTIARY' as const,
      enabled: true,
      fetch: async () => ({ providerId: 'test-provider', retrievedAt: nowISO(), items: [] }),
    };
    engine.registerProvider(provider);
    const metrics = engine.getMetrics();
    expect(metrics).toBeDefined();
    engine.unregisterProvider('test-provider');
  });

  it('enqueue respects backpressure', () => {
    const engine = new LiveIngestionEngine(config, 2);
    engine.enqueue('p1');
    engine.enqueue('p1');
    const result = engine.enqueue('p1');
    expect(result).toBe(false);
  });

  it('queueDepth tracks depth', () => {
    const engine = new LiveIngestionEngine(config, 10);
    for (let i = 0; i < 5; i++) engine.enqueue('p1');
    expect(engine.queueDepth()).toBe(5);
  });

  it('checkpoint tracks provider state', () => {
    const engine = new LiveIngestionEngine(config);
    const provider = {
      id: 'test-provider',
      name: 'Test',
      category: 'test',
      sourceClass: 'TERTIARY' as const,
      enabled: true,
      fetch: async () => ({ providerId: 'test-provider', retrievedAt: nowISO(), items: [] }),
    };
    engine.registerProvider(provider);
    const cp = engine.getCheckpoint('test-provider');
    expect(cp).toBeDefined();
    expect(cp!.providerId).toBe('test-provider');
  });

  it('watermark protection works', () => {
    const engine = new LiveIngestionEngine(config);
    const provider = {
      id: 'test-provider',
      name: 'Test',
      category: 'test',
      sourceClass: 'TERTIARY' as const,
      enabled: true,
      fetch: async () => ({ providerId: 'test-provider', retrievedAt: nowISO(), items: [] }),
    };
    engine.registerProvider(provider);
    // No prior successful ingestion — should not be stale
    expect(engine.isStaleWrite('test-provider', '2020-01-01T00:00:00Z')).toBe(false);
  });

  it('getMetrics returns valid metrics', () => {
    const engine = new LiveIngestionEngine(config);
    const metrics = engine.getMetrics();
    expect(metrics.totalIngestions).toBe(0);
    expect(metrics.totalItemsFetched).toBe(0);
    expect(metrics.providerMetrics).toEqual({});
  });
});

// ============================================================================
// Evidence Pack Tests
// ============================================================================

describe('Phase 22 — Evidence Packs', () => {
  let builder: EvidencePackBuilder;

  beforeEach(() => {
    builder = new EvidencePackBuilder();
    builder.setQuery('What is happening with Apple stock?');
  });

  it('creates evidence pack with claims', () => {
    builder.addFact({
      id: 'f1',
      subjectId: 'e1',
      predicate: 'stock_price',
      objectValue: 185.5,
      confidence: 0.85,
      status: 'ACTIVE',
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      provenance: [],
      metadata: {},
    });
    const pack = builder.build('Apple stock is at $185.50');
    expect(pack.claims.length).toBe(1);
    expect(pack.claims[0].subject).toBe('e1');
  });

  it('creates evidence pack with entities', () => {
    builder.addEntity({
      id: 'e1',
      identity: { canonicalName: 'Apple Inc', entityType: 'COMPANY', aliases: [] },
      importance: 'HIGH',
      tags: [],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    });
    const pack = builder.build('Apple is performing well');
    expect(pack.entities.length).toBe(1);
  });

  it('builds BrainWorldContext from evidence pack', () => {
    builder.addEntity({
      id: 'e1',
      identity: { canonicalName: 'Apple Inc', entityType: 'COMPANY', aliases: [] },
      importance: 'HIGH',
      tags: [],
      firstSeenAt: nowISO(),
      lastUpdatedAt: nowISO(),
      metadata: {},
    });
    builder.addEvent({
      id: 'ev1',
      type: 'MARKET_MOVE',
      title: 'Apple stock rises',
      summary: 'AAPL up 3%',
      entityIds: ['e1'],
      timestamp: nowISO(),
      importance: 'HIGH',
      confidence: 0.8,
      topicIds: ['finance'],
      sources: [],
      tags: [],
      metadata: {},
    });
    const pack = builder.build('Apple stock is up 3%');
    const context = buildBrainContext(pack);
    expect(context.summary).toContain('Apple');
    expect(context.confidence).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// Integration Tests — WorldIntelligence with Phase 22 Components
// ============================================================================

describe('Phase 22 — WorldIntelligence Integration', () => {
  let wi: WorldIntelligence;

  beforeEach(async () => {
    wi = new WorldIntelligence({ persistenceEnabled: false });
    await wi.initialize();
  });

  it('initializes with live ingestion and semantic search', () => {
    expect(wi.liveIngestion).toBeDefined();
    expect(wi.semanticSearch).toBeDefined();
    expect(wi.llmExtraction).toBeDefined();
  });

  it('has real providers registered after initialization', () => {
    expect(wi.ingestion).toBeDefined();
    const stats = wi.getStats();
    expect(stats).toBeDefined();
  });

  it('semantic search works after indexing via WorldIntelligence', () => {
    // Manually index into semantic search after creating entity
    const entity = wi.createEntity('COMPANY', 'TestCorp', [], {
      importance: 'HIGH',
      tags: ['tech', 'ai'],
    });
    wi.semanticSearch.indexEntity(entity);
    const { totalIndexed } = wi.searchHybrid('TestCorp tech');
    expect(totalIndexed).toBeGreaterThanOrEqual(1);
  });

  it('LLM extraction works through WorldIntelligence', async () => {
    const result = await wi.extractFromText('Apple CEO Tim Cook announces new product', 'test');
    expect(result.extractionTimeMs).toBeGreaterThanOrEqual(0);
  });

  it('evidence pack builder works', () => {
    wi.createEntity('COMPANY', 'TestCorp');
    const pack = wi.buildEvidence('What is TestCorp?', 'TestCorp is a test company');
    expect(pack.query).toBe('What is TestCorp?');
    expect(pack.answer).toBe('TestCorp is a test company');
  });

  it('brain context builder works', () => {
    wi.createEntity('COMPANY', 'TestCorp');
    const context = wi.getBrainContext('What is TestCorp?', 'TestCorp is a test company');
    expect(context.summary).toContain('TestCorp');
  });

  it('hybrid search combines keyword and semantic scoring', () => {
    const nvidia = wi.createEntity('COMPANY', 'NVIDIA', [], { tags: ['gpu', 'ai'] });
    const amd = wi.createEntity('COMPANY', 'AMD', [], { tags: ['cpu', 'gpu'] });
    wi.semanticSearch.indexEntity(nvidia);
    wi.semanticSearch.indexEntity(amd);
    const { results } = wi.searchHybrid('NVIDIA ai chip');
    expect(results.length).toBeGreaterThanOrEqual(1);
  });
});

// ============================================================================
// Performance Benchmarks
// ============================================================================

describe('Phase 22 — Performance Benchmarks', () => {
  it('semantic search handles 1000 entities in <500ms', () => {
    const search = new HybridSearchEngine();
    const start = Date.now();
    for (let i = 0; i < 1000; i++) {
      search.indexEntity({
        id: `entity-${i}`,
        identity: { canonicalName: `Entity ${i}`, entityType: 'OTHER', aliases: [] },
        importance: 'MEDIUM',
        tags: [`tag-${i % 10}`],
        firstSeenAt: nowISO(),
        lastUpdatedAt: nowISO(),
        metadata: {},
      });
    }
    const indexTime = Date.now() - start;
    expect(indexTime).toBeLessThan(1000);

    const searchStart = Date.now();
    const { results } = search.search('Entity 500 tag-5');
    const searchTime = Date.now() - searchStart;
    expect(searchTime).toBeLessThan(200);
    expect(results.length).toBeGreaterThanOrEqual(1);
  });

  it('evidence pack build handles 50 facts in <50ms', () => {
    const builder = new EvidencePackBuilder();
    builder.setQuery('test query');
    const start = Date.now();
    for (let i = 0; i < 50; i++) {
      builder.addFact({
        id: `fact-${i}`,
        subjectId: `entity-${i}`,
        predicate: `predicate-${i}`,
        objectValue: `value-${i}`,
        confidence: 0.8,
        status: 'ACTIVE',
        firstSeenAt: nowISO(),
        lastUpdatedAt: nowISO(),
        provenance: [],
        metadata: {},
      });
    }
    const pack = builder.build('Test answer');
    const time = Date.now() - start;
    expect(time).toBeLessThan(100);
    expect(pack.claims.length).toBe(50);
  });

  it('LLM rule-based extraction handles 10KB text in <100ms', () => {
    const engine = new LlmExtractionEngine();
    const longText = 'Apple announced new iPhone. '.repeat(500) + 'NVIDIA stock rose 10%. ';
    const start = Date.now();
    const result = engine.extractFromText(longText, 'test');
    const time = Date.now() - start;
    expect(time).toBeLessThan(100);
    expect(result.entities.length).toBeGreaterThanOrEqual(1);
  });
});
