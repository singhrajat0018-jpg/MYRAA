// MYRAA Capability Engine — Tests
import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  CapabilityRegistry,
  CapabilityDiscovery,
  ProviderVerifier,
  ProviderRanker,
  ExecutionEngine,
  CapabilityRouter,
  CapabilityPlanner,
  SecurityGuard,
  AuthManager,
  CircuitBreaker,
  ResponseCache,
  FallbackManager,
  ResponseNormalizer,
  normalizeWeather,
  normalizeSearch,
  normalizeFinance,
  ResponseMerger,
  ProvenanceTracker,
  MetricsCollector,
  CapabilitySerializer,
  createCapabilityEngine,
} from "../src/capabilities/index";
import type {
  Capability,
  Provider,
  CapabilityRequest,
  CapabilityResponse,
} from "../src/capabilities/contracts";

// ── Helpers ──────────────────────────────────────────────────

function makeCapability(overrides?: Partial<Capability>): Capability {
  return {
    id: "test-cap",
    name: "Test Capability",
    description: "A test capability",
    category: "UTILITY",
    source: "EXTERNAL_API",
    tags: ["test"],
    examples: ["test example"],
    deprecated: false,
    addedAt: Date.now(),
    updatedAt: Date.now(),
    ...overrides,
  };
}

function makeProvider(overrides?: Partial<Provider>): Provider {
  return {
    id: "test-provider",
    name: "Test Provider",
    description: "A test provider",
    source: "EXTERNAL_API",
    capabilities: ["test-cap"],
    authType: "NONE",
    httpsRequired: false,
    cors: "OPEN",
    reliability: {
      successRate: 1.0,
      totalRequests: 100,
      totalFailures: 0,
      consecutiveFailures: 0,
    },
    latency: {
      avgMs: 100,
      p50Ms: 80,
      p95Ms: 200,
      p99Ms: 300,
      sampleCount: 100,
    },
    trustScore: 80,
    trustLevel: "VERIFIED",
    enabled: true,
    tags: ["test"],
    addedAt: Date.now(),
    metadata: {},
    ...overrides,
  };
}

function makeRequest(overrides?: Partial<CapabilityRequest>): CapabilityRequest {
  return {
    id: "req-1",
    capabilityId: "test-cap",
    input: { query: "test" },
    source: "CHAT",
    priority: 5,
    fallbackAllowed: true,
    cachePolicy: "NONE",
    timestamp: Date.now(),
    ...overrides,
  };
}

// ══════════════════════════════════════════════════════════════
// CONTRACTS
// ══════════════════════════════════════════════════════════════

describe("Capability Engine — Contracts", () => {
  it("exports CAPABILITY_VERSION", async () => {
    const { CAPABILITY_VERSION } = await import("../src/capabilities/contracts");
    expect(CAPABILITY_VERSION).toBe("1.0.0");
  });
});

// ══════════════════════════════════════════════════════════════
// REGISTRY
// ══════════════════════════════════════════════════════════════

describe("Capability Registry", () => {
  let registry: CapabilityRegistry;

  beforeEach(() => {
    registry = new CapabilityRegistry({ maxCapabilities: 10, maxProviders: 10 });
  });

  it("registers and retrieves a capability", () => {
    const cap = makeCapability();
    registry.registerCapability(cap);
    expect(registry.getCapability("test-cap")).toBeDefined();
    expect(registry.getCapability("test-cap")!.name).toBe("Test Capability");
  });

  it("unregisters a capability", () => {
    registry.registerCapability(makeCapability());
    expect(registry.unregisterCapability("test-cap")).toBe(true);
    expect(registry.getCapability("test-cap")).toBeUndefined();
  });

  it("returns false when unregistering non-existent capability", () => {
    expect(registry.unregisterCapability("nonexistent")).toBe(false);
  });

  it("queries capabilities by category", () => {
    registry.registerCapability(makeCapability({ id: "cap1", category: "WEATHER" }));
    registry.registerCapability(makeCapability({ id: "cap2", category: "NEWS" }));
    registry.registerCapability(makeCapability({ id: "cap3", category: "WEATHER" }));
    expect(registry.getCapabilities({ category: "WEATHER" }).length).toBe(2);
    expect(registry.getCapabilities({ category: "NEWS" }).length).toBe(1);
  });

  it("registers and retrieves a provider", () => {
    const prov = makeProvider();
    registry.registerProvider(prov);
    expect(registry.getProvider("test-provider")).toBeDefined();
  });

  it("unregisters a provider", () => {
    registry.registerProvider(makeProvider());
    expect(registry.unregisterProvider("test-provider")).toBe(true);
    expect(registry.getProvider("test-provider")).toBeUndefined();
  });

  it("gets providers for a capability", () => {
    registry.registerCapability(makeCapability());
    registry.registerProvider(makeProvider());
    const providers = registry.getProvidersForCapability("test-cap");
    expect(providers.length).toBe(1);
    expect(providers[0].id).toBe("test-provider");
  });

  it("does not return disabled providers", () => {
    registry.registerCapability(makeCapability());
    registry.registerProvider(makeProvider({ enabled: false }));
    expect(registry.getProvidersForCapability("test-cap").length).toBe(0);
  });

  it("updates provider trust", () => {
    registry.registerProvider(makeProvider());
    registry.updateProviderTrust("test-provider", "TRUSTED", 95);
    const prov = registry.getProvider("test-provider")!;
    expect(prov.trustLevel).toBe("TRUSTED");
    expect(prov.trustScore).toBe(95);
  });

  it("clamps trust score to 0-100", () => {
    registry.registerProvider(makeProvider());
    registry.updateProviderTrust("test-provider", "TRUSTED", 150);
    expect(registry.getProvider("test-provider")!.trustScore).toBe(100);
    registry.updateProviderTrust("test-provider", "BLOCKED", -10);
    expect(registry.getProvider("test-provider")!.trustScore).toBe(0);
  });

  it("auto-disables provider after consecutive failures", () => {
    registry.registerProvider(makeProvider());
    for (let i = 0; i < 10; i++) {
      registry.updateProviderHealth("test-provider", "UNHEALTHY");
    }
    expect(registry.getProvider("test-provider")!.enabled).toBe(false);
  });

  it("resets failure count on healthy status", () => {
    registry.registerProvider(makeProvider());
    registry.updateProviderHealth("test-provider", "UNHEALTHY");
    registry.updateProviderHealth("test-provider", "UNHEALTHY");
    registry.updateProviderHealth("test-provider", "HEALTHY");
    expect(registry.getProvider("test-provider")!.reliability.consecutiveFailures).toBe(0);
  });

  it("emits events on capability registration", () => {
    const events: string[] = [];
    registry.on("CAPABILITY_REGISTERED", (e) => events.push(e.type));
    registry.registerCapability(makeCapability());
    expect(events).toContain("CAPABILITY_REGISTERED");
  });

  it("emits events on provider registration", () => {
    const events: string[] = [];
    registry.on("PROVIDER_REGISTERED", (e) => events.push(e.type));
    registry.registerProvider(makeProvider());
    expect(events).toContain("PROVIDER_REGISTERED");
  });

  it("returns stats", () => {
    registry.registerCapability(makeCapability());
    registry.registerProvider(makeProvider());
    const stats = registry.getStats();
    expect(stats.capabilities).toBe(1);
    expect(stats.providers).toBe(1);
    expect(stats.enabledProviders).toBe(1);
  });

  it("exports and imports snapshot", () => {
    registry.registerCapability(makeCapability());
    registry.registerProvider(makeProvider());
    const snapshot = registry.exportSnapshot();
    expect(snapshot.capabilities.length).toBe(1);
    expect(snapshot.providers.length).toBe(1);

    const registry2 = new CapabilityRegistry();
    registry2.importSnapshot(snapshot);
    expect(registry2.getCapability("test-cap")).toBeDefined();
    expect(registry2.getProvider("test-provider")).toBeDefined();
  });

  it("finds providers with trust filter", () => {
    registry.registerCapability(makeCapability());
    registry.registerProvider(makeProvider({ id: "p1", trustLevel: "VERIFIED", trustScore: 60 }));
    registry.registerProvider(makeProvider({ id: "p2", trustLevel: "TRUSTED", trustScore: 90 }));
    const found = registry.findProvidersForCapability("test-cap", { minTrustLevel: "TRUSTED" });
    expect(found.length).toBe(1);
    expect(found[0].id).toBe("p2");
  });
});

// ══════════════════════════════════════════════════════════════
// SECURITY
// ══════════════════════════════════════════════════════════════

describe("Security Guard — SSRF Protection", () => {
  it("allows valid HTTPS URLs", () => {
    expect(SecurityGuard.checkUrl("https://api.example.com/data").allowed).toBe(true);
  });

  it("allows valid HTTP URLs", () => {
    expect(SecurityGuard.checkUrl("http://api.example.com/data").allowed).toBe(true);
  });

  it("blocks localhost", () => {
    expect(SecurityGuard.checkUrl("http://localhost/api").allowed).toBe(false);
  });

  it("blocks 127.0.0.1", () => {
    expect(SecurityGuard.checkUrl("http://127.0.0.1/api").allowed).toBe(false);
  });

  it("blocks private IP 10.x.x.x", () => {
    expect(SecurityGuard.checkUrl("http://10.0.0.1/api").allowed).toBe(false);
  });

  it("blocks private IP 192.168.x.x", () => {
    expect(SecurityGuard.checkUrl("http://192.168.1.1/api").allowed).toBe(false);
  });

  it("blocks private IP 172.16.x.x", () => {
    expect(SecurityGuard.checkUrl("http://172.16.0.1/api").allowed).toBe(false);
  });

  it("blocks AWS metadata endpoint", () => {
    expect(SecurityGuard.checkUrl("http://169.254.169.254/latest/meta-data/").allowed).toBe(false);
  });

  it("blocks non-standard ports", () => {
    expect(SecurityGuard.checkUrl("https://api.example.com:9999/data").allowed).toBe(false);
  });

  it("allows standard ports", () => {
    expect(SecurityGuard.checkUrl("https://api.example.com:443/data").allowed).toBe(true);
    expect(SecurityGuard.checkUrl("http://api.example.com:80/data").allowed).toBe(true);
  });

  it("blocks FTP protocol", () => {
    expect(SecurityGuard.checkUrl("ftp://example.com/file").allowed).toBe(false);
  });

  it("blocks URL with credentials", () => {
    expect(SecurityGuard.checkUrl("https://user:pass@example.com/").allowed).toBe(false);
  });

  it("blocks invalid URLs", () => {
    expect(SecurityGuard.checkUrl("not-a-url").allowed).toBe(false);
  });

  it("sanitizes input", () => {
    expect(SecurityGuard.sanitizeInput("<script>alert(1)</script>")).toBe("scriptalert(1)/script");
    expect(SecurityGuard.sanitizeInput("javascript:alert(1)")).toBe("alert(1)");
    expect(SecurityGuard.sanitizeInput("data:text/html,<h1>Hi</h1>")).toBe("text/html,h1Hi/h1");
  });

  it("validates headers", () => {
    const result = SecurityGuard.validateHeaders({ "Content-Type": "application/json" });
    expect(result.valid).toBe(true);
  });

  it("detects suspicious headers", () => {
    const result = SecurityGuard.validateHeaders({ "Cookie": "session=abc" });
    expect(result.valid).toBe(false);
    expect(result.issues.length).toBeGreaterThan(0);
  });
});

// ══════════════════════════════════════════════════════════════
// CIRCUIT BREAKER
// ══════════════════════════════════════════════════════════════

describe("Circuit Breaker", () => {
  let cb: CircuitBreaker;

  beforeEach(() => {
    cb = new CircuitBreaker({ failureThreshold: 3, recoveryTimeMs: 100 });
  });

  it("starts closed", () => {
    expect(cb.canExecute("prov")).toBe(true);
    expect(cb.getState("prov")).toBe("CLOSED");
  });

  it("opens after threshold failures", () => {
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    expect(cb.canExecute("prov")).toBe(false);
    expect(cb.getState("prov")).toBe("OPEN");
  });

  it("transitions to half-open after recovery time", async () => {
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    expect(cb.canExecute("prov")).toBe(false);
    await new Promise(r => setTimeout(r, 150));
    expect(cb.canExecute("prov")).toBe(true);
    expect(cb.getState("prov")).toBe("HALF_OPEN");
  });

  it("closes on success in half-open", () => {
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    // Force to half-open
    (cb as any).circuits.get("prov").state = "HALF_OPEN";
    cb.recordSuccess("prov");
    expect(cb.getState("prov")).toBe("CLOSED");
  });

  it("re-opens on failure in half-open", () => {
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    (cb as any).circuits.get("prov").state = "HALF_OPEN";
    cb.recordFailure("prov");
    expect(cb.getState("prov")).toBe("OPEN");
  });

  it("resets circuit", () => {
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    cb.recordFailure("prov");
    cb.reset("prov");
    expect(cb.canExecute("prov")).toBe(true);
    expect(cb.getState("prov")).toBe("CLOSED");
  });
});

// ══════════════════════════════════════════════════════════════
// CACHE
// ══════════════════════════════════════════════════════════════

describe("Response Cache", () => {
  let cache: ResponseCache;

  beforeEach(() => {
    cache = new ResponseCache({ maxSizeEntries: 5, maxSizeBytes: 10000 });
  });

  it("stores and retrieves data", () => {
    cache.set("key1", { temp: 25 }, "prov1", "cap1", "MEDIUM");
    const entry = cache.get("key1");
    expect(entry).not.toBeNull();
    expect(entry!.data).toEqual({ temp: 25 });
  });

  it("returns null for missing key", () => {
    expect(cache.get("nonexistent")).toBeNull();
  });

  it("returns null for expired entry", () => {
    cache.set("key1", { temp: 25 }, "prov1", "cap1", "SHORT");
    // Manually expire
    const entry = (cache as any).entries.get("key1");
    entry.expiresAt = Date.now() - 1000;
    expect(cache.get("key1")).toBeNull();
  });

  it("deletes entry", () => {
    cache.set("key1", { temp: 25 }, "prov1", "cap1", "MEDIUM");
    expect(cache.delete("key1")).toBe(true);
    expect(cache.get("key1")).toBeNull();
  });

  it("clears all entries", () => {
    cache.set("key1", { a: 1 }, "prov1", "cap1", "MEDIUM");
    cache.set("key2", { b: 2 }, "prov2", "cap2", "MEDIUM");
    cache.clear();
    expect(cache.getStats().entries).toBe(0);
  });

  it("clears entries by provider", () => {
    cache.set("key1", { a: 1 }, "prov1", "cap1", "MEDIUM");
    cache.set("key2", { b: 2 }, "prov1", "cap2", "MEDIUM");
    cache.set("key3", { c: 3 }, "prov2", "cap1", "MEDIUM");
    const cleared = cache.clearProvider("prov1");
    expect(cleared).toBe(2);
    expect(cache.get("key3")).not.toBeNull();
  });

  it("purges expired entries", () => {
    cache.set("key1", { a: 1 }, "prov1", "cap1", "SHORT");
    const entry = (cache as any).entries.get("key1");
    entry.expiresAt = Date.now() - 1000;
    const purged = cache.purgeExpired();
    expect(purged).toBe(1);
  });

  it("generates deterministic keys", () => {
    const k1 = ResponseCache.keyFor("cap", { b: 2, a: 1 });
    const k2 = ResponseCache.keyFor("cap", { a: 1, b: 2 });
    expect(k1).toBe(k2);
  });

  it("skips NONE policy", () => {
    cache.set("key1", { a: 1 }, "prov1", "cap1", "NONE");
    expect(cache.get("key1")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════
// AUTH MANAGER
// ══════════════════════════════════════════════════════════════

describe("Auth Manager", () => {
  it("stores and retrieves keys", () => {
    const am = new AuthManager();
    am.setKey("MY_KEY", "secret123");
    expect(am.getKey("MY_KEY")).toBe("secret123");
  });

  it("removes keys", () => {
    const am = new AuthManager();
    am.setKey("MY_KEY", "secret123");
    expect(am.removeKey("MY_KEY")).toBe(true);
    expect(am.getKey("MY_KEY")).toBeUndefined();
  });

  it("applies API key header auth", () => {
    const am = new AuthManager();
    am.setKey("API_KEY", "my-key-123");
    const provider = makeProvider({
      authType: "API_KEY_HEADER",
      authConfig: { keyHeader: "X-API-Key", keyEnvVar: "API_KEY" },
    });
    const result = am.applyAuth(provider, {}, {});
    expect(result.headers["X-API-Key"]).toBe("my-key-123");
  });

  it("applies bearer token auth", () => {
    const am = new AuthManager();
    am.setKey("TOKEN", "bearer-token");
    const provider = makeProvider({
      authType: "BEARER_TOKEN",
      authConfig: { keyEnvVar: "TOKEN" },
    });
    const result = am.applyAuth(provider, {}, {});
    expect(result.headers["Authorization"]).toBe("Bearer bearer-token");
  });

  it("applies query param auth", () => {
    const am = new AuthManager();
    am.setKey("API_KEY", "key123");
    const provider = makeProvider({
      authType: "API_KEY_QUERY",
      authConfig: { keyQuery: "api_key", keyEnvVar: "API_KEY" },
    });
    const result = am.applyAuth(provider, {}, {});
    expect(result.params["api_key"]).toBe("key123");
  });

  it("passes through for NONE auth", () => {
    const am = new AuthManager();
    const provider = makeProvider({ authType: "NONE" });
    const result = am.applyAuth(provider, { "X-Custom": "val" }, { p: "v" });
    expect(result.headers["X-Custom"]).toBe("val");
    expect(result.params["p"]).toBe("v");
  });
});

// ══════════════════════════════════════════════════════════════
// RANKING
// ══════════════════════════════════════════════════════════════

describe("Provider Ranking", () => {
  it("ranks providers by trust score", () => {
    const ranker = new ProviderRanker();
    const p1 = makeProvider({ id: "p1", trustScore: 50, trustLevel: "VERIFIED" });
    const p2 = makeProvider({ id: "p2", trustScore: 90, trustLevel: "TRUSTED" });
    const ranked = ranker.rank([p1, p2]);
    expect(ranked[0].provider.id).toBe("p2");
    expect(ranked[1].provider.id).toBe("p1");
  });

  it("picks best provider", () => {
    const ranker = new ProviderRanker();
    const p1 = makeProvider({ id: "p1", trustScore: 50, trustLevel: "VERIFIED" });
    const p2 = makeProvider({ id: "p2", trustScore: 90, trustLevel: "TRUSTED" });
    const best = ranker.pickBest([p1, p2]);
    expect(best).not.toBeNull();
    expect(best!.id).toBe("p2");
  });

  it("returns null for empty list", () => {
    expect(new ProviderRanker().pickBest([])).toBeNull();
  });

  it("scores free providers higher", () => {
    const ranker = new ProviderRanker();
    const p1 = makeProvider({ id: "p1", trustScore: 80, pricing: { free: false } });
    const p2 = makeProvider({ id: "p2", trustScore: 80, pricing: { free: true } });
    const ranked = ranker.rank([p1, p2]);
    expect(ranked[0].provider.id).toBe("p2");
  });

  it("scores HTTPS providers higher", () => {
    const ranker = new ProviderRanker();
    const p1 = makeProvider({ id: "p1", trustScore: 80, httpsRequired: false });
    const p2 = makeProvider({ id: "p2", trustScore: 80, httpsRequired: true });
    const ranked = ranker.rank([p1, p2]);
    expect(ranked[0].provider.id).toBe("p2");
  });
});

// ══════════════════════════════════════════════════════════════
// NORMALIZATION
// ══════════════════════════════════════════════════════════════

describe("Response Normalizer", () => {
  it("normalizes Open-Meteo weather format", () => {
    const result = normalizeWeather({
      current: {
        temperature_2m: 25,
        relative_humidity_2m: 60,
        weather_code: 1,
        wind_speed_10m: 10,
      },
    });
    expect(result.temperature).toBe(25);
    expect(result.humidity).toBe(60);
    expect(result.description).toBe("Mainly clear");
  });

  it("normalizes generic weather format", () => {
    const result = normalizeWeather({ temperature: 30, humidity: 70, description: "Sunny" });
    expect(result.temperature).toBe(30);
    expect(result.description).toBe("Sunny");
  });

  it("normalizes Tavily search format", () => {
    const result = normalizeSearch({
      results: [
        { title: "Test", url: "https://example.com", content: "Snippet" },
      ],
    });
    expect(result.results!.length).toBe(1);
    expect(result.results![0].title).toBe("Test");
    expect(result.results![0].url).toBe("https://example.com");
    expect(result.results![0].snippet).toBe("Snippet");
  });

  it("normalizes generic search array", () => {
    const result = normalizeSearch([
      { title: "A", link: "https://a.com", description: "Desc A" },
    ]);
    expect(result.results!.length).toBe(1);
    expect(result.results![0].title).toBe("A");
  });

  it("normalizes finance data", () => {
    const result = normalizeFinance({
      symbol: "AAPL",
      price: 150.25,
      change: 2.5,
      volume: 1000000,
    });
    expect(result.symbol).toBe("AAPL");
    expect(result.price).toBe(150.25);
    expect(result.change).toBe(2.5);
  });

  it("returns empty object for non-object input", () => {
    expect(normalizeWeather(null)).toEqual({});
    expect(normalizeSearch(null)).toEqual({});
    expect(normalizeFinance(null)).toEqual({});
  });
});

// ══════════════════════════════════════════════════════════════
// MERGE
// ══════════════════════════════════════════════════════════════

describe("Response Merger", () => {
  const makeResp = (providerId: string, data: unknown, score = 0.8): CapabilityResponse => ({
    requestId: "req-1",
    providerId,
    capabilityId: "test-cap",
    success: true,
    data,
    provenance: {
      source: providerId,
      capabilityId: "test-cap",
      retrievedAt: Date.now(),
      trustChain: [providerId],
      confidenceScore: score,
    },
    latencyMs: 100,
    fromCache: false,
    normalized: false,
    timestamp: Date.now(),
  });

  it("picks best response by confidence", () => {
    const merger = new ResponseMerger({ strategy: "best" });
    const r1 = makeResp("p1", { temp: 25 }, 0.5);
    const r2 = makeResp("p2", { temp: 30 }, 0.9);
    const merged = merger.merge([r1, r2]);
    expect(merged!.providerId).toBe("p2");
  });

  it("merges all responses", () => {
    const merger = new ResponseMerger({ strategy: "merge" });
    const r1 = makeResp("p1", { temp: 25, humidity: 60 });
    const r2 = makeResp("p2", { temp: 30, wind: 5 });
    const merged = merger.merge([r1, r2]);
    expect(merged!.data).toHaveProperty("temp");
    expect(merged!.data).toHaveProperty("humidity");
    expect(merged!.data).toHaveProperty("wind");
  });

  it("returns null for no successful responses", () => {
    const merger = new ResponseMerger();
    const r1: CapabilityResponse = {
      requestId: "req-1",
      providerId: "p1",
      capabilityId: "test-cap",
      success: false,
      error: { code: "TIMEOUT", message: "timeout", severity: "TRANSIENT", retryable: true },
      provenance: { source: "p1", capabilityId: "test-cap", retrievedAt: Date.now(), trustChain: [], confidenceScore: 0 },
      latencyMs: 100,
      fromCache: false,
      normalized: false,
      timestamp: Date.now(),
    };
    expect(merger.merge([r1])).toBeNull();
  });

  it("returns single response as-is", () => {
    const merger = new ResponseMerger({ strategy: "merge" });
    const r = makeResp("p1", { a: 1 });
    expect(merger.merge([r])!.data).toEqual({ a: 1 });
  });
});

// ══════════════════════════════════════════════════════════════
// PROVENANCE
// ══════════════════════════════════════════════════════════════

describe("Provenance Tracker", () => {
  it("records provenance from response", () => {
    const tracker = new ProvenanceTracker();
    const resp: CapabilityResponse = {
      requestId: "req-1",
      providerId: "prov1",
      capabilityId: "cap1",
      success: true,
      data: { result: 42 },
      provenance: {
        source: "prov1",
        capabilityId: "cap1",
        retrievedAt: Date.now(),
        trustChain: [],
        confidenceScore: 0.8,
      },
      latencyMs: 100,
      fromCache: false,
      normalized: false,
      timestamp: Date.now(),
    };
    const record = tracker.record(resp);
    expect(record.source).toBe("prov1");
    expect(record.confidenceScore).toBe(0.8);
  });

  it("gets chain for request", () => {
    const tracker = new ProvenanceTracker();
    const resp: CapabilityResponse = {
      requestId: "req-1",
      providerId: "prov1",
      capabilityId: "cap1",
      success: true,
      data: {},
      provenance: { source: "prov1", capabilityId: "cap1", retrievedAt: Date.now(), trustChain: [], confidenceScore: 0.8 },
      latencyMs: 100,
      fromCache: false,
      normalized: false,
      timestamp: Date.now(),
    };
    tracker.record(resp);
    expect(tracker.getChain("req-1").length).toBe(1);
    expect(tracker.getChain("nonexistent").length).toBe(0);
  });

  it("checks trust threshold", () => {
    const tracker = new ProvenanceTracker();
    const resp: CapabilityResponse = {
      requestId: "req-1",
      providerId: "prov1",
      capabilityId: "cap1",
      success: true,
      data: {},
      provenance: { source: "prov1", capabilityId: "cap1", retrievedAt: Date.now(), trustChain: [], confidenceScore: 0.3 },
      latencyMs: 100,
      fromCache: false,
      normalized: false,
      timestamp: Date.now(),
    };
    tracker.record(resp);
    expect(tracker.isTrusted("req-1", 0.5)).toBe(false);
    expect(tracker.isTrusted("req-1", 0.2)).toBe(true);
  });
});

// ══════════════════════════════════════════════════════════════
// METRICS
// ══════════════════════════════════════════════════════════════

describe("Metrics Collector", () => {
  it("records requests", () => {
    const mc = new MetricsCollector();
    mc.record({ providerId: "p1", capabilityId: "c1", success: true, latencyMs: 100, fromCache: false });
    mc.record({ providerId: "p1", capabilityId: "c1", success: false, latencyMs: 200, fromCache: false });
    const m = mc.getProviderMetrics("p1");
    expect(m.requests).toBe(2);
    expect(m.successes).toBe(1);
    expect(m.failures).toBe(1);
  });

  it("tracks cache hits", () => {
    const mc = new MetricsCollector();
    mc.record({ providerId: "p1", capabilityId: "c1", success: true, latencyMs: 10, fromCache: true });
    mc.record({ providerId: "p1", capabilityId: "c1", success: true, latencyMs: 100, fromCache: false });
    const m = mc.getProviderMetrics("p1");
    expect(m.cacheHits).toBe(1);
    expect(m.cacheMisses).toBe(1);
  });

  it("computes system metrics", () => {
    const mc = new MetricsCollector();
    mc.record({ providerId: "p1", capabilityId: "c1", success: true, latencyMs: 50, fromCache: false });
    mc.record({ providerId: "p2", capabilityId: "c2", success: true, latencyMs: 100, fromCache: false });
    const sys = mc.getSystemMetrics();
    expect(sys.totalRequests24h).toBe(2);
    expect(sys.uniqueProviders).toBe(2);
    expect(sys.uniqueCapabilities).toBe(2);
  });

  it("clears metrics", () => {
    const mc = new MetricsCollector();
    mc.record({ providerId: "p1", capabilityId: "c1", success: true, latencyMs: 50, fromCache: false });
    mc.clear();
    expect(mc.getSystemMetrics().totalRequests24h).toBe(0);
  });
});

// ══════════════════════════════════════════════════════════════
// SERIALIZATION
// ══════════════════════════════════════════════════════════════

describe("Capability Serialization", () => {
  it("exports and imports snapshot", () => {
    const registry = new CapabilityRegistry();
    registry.registerCapability(makeCapability());
    registry.registerProvider(makeProvider());

    const snapshot = CapabilitySerializer.exportSnapshot(registry);
    expect(snapshot.capabilities.length).toBe(1);
    expect(snapshot.providers.length).toBe(1);
    expect(snapshot.checksum).toBeTruthy();

    const json = CapabilitySerializer.toJson(snapshot);
    const parsed = CapabilitySerializer.fromJson(json);
    expect(parsed).not.toBeNull();
    expect(parsed!.capabilities.length).toBe(1);
  });

  it("rejects corrupted snapshot", () => {
    const registry = new CapabilityRegistry();
    registry.registerCapability(makeCapability());
    const snapshot = CapabilitySerializer.exportSnapshot(registry);
    // Corrupt the checksum
    const corrupted = { ...snapshot, checksum: "bad" };
    const result = CapabilitySerializer.importSnapshot(new CapabilityRegistry(), corrupted);
    expect(result.success).toBe(false);
  });

  it("fromJson returns null for invalid JSON", () => {
    expect(CapabilitySerializer.fromJson("not json")).toBeNull();
  });

  it("fromJson returns null for incomplete data", () => {
    expect(CapabilitySerializer.fromJson('{"version":"1.0.0"}')).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════
// PLANNER
// ══════════════════════════════════════════════════════════════

describe("Capability Planner", () => {
  let registry: CapabilityRegistry;
  let planner: CapabilityPlanner;

  beforeEach(() => {
    registry = new CapabilityRegistry();
    registry.registerCapability(makeCapability({ id: "weather", category: "WEATHER" }));
    registry.registerCapability(makeCapability({ id: "news", category: "NEWS" }));
    registry.registerProvider(makeProvider({ id: "wp1", capabilities: ["weather"] }));
    registry.registerProvider(makeProvider({ id: "np1", capabilities: ["news"] }));
    planner = new CapabilityPlanner(registry);
  });

  it("plans single capability", () => {
    const plan = planner.plan("req-1", [
      { capabilityId: "weather", input: { city: "Delhi" } },
    ]);
    expect(plan.steps.length).toBe(1);
    expect(plan.capabilities).toContain("weather");
  });

  it("plans multiple capabilities", () => {
    const plan = planner.plan("req-1", [
      { capabilityId: "weather", input: { city: "Delhi" } },
      { capabilityId: "news", input: { query: "tech" } },
    ]);
    expect(plan.steps.length).toBe(2);
    expect(plan.capabilities.length).toBe(2);
  });

  it("skips unknown capabilities", () => {
    const plan = planner.plan("req-1", [
      { capabilityId: "weather", input: {} },
      { capabilityId: "unknown", input: {} },
    ]);
    expect(plan.steps.length).toBe(1);
  });

  it("groups into batches", () => {
    const steps = [
      { capabilityId: "a", input: {}, priority: 1, dependsOn: [] as string[] },
      { capabilityId: "b", input: {}, priority: 2, dependsOn: ["a"] },
      { capabilityId: "c", input: {}, priority: 3, dependsOn: [] as string[] },
    ];
    const batches = planner.groupIntoBatches(steps);
    expect(batches.length).toBe(2);
    expect(batches[0].length).toBe(2); // a and c can run in parallel
    expect(batches[1].length).toBe(1); // b depends on a
  });

  it("checks parallelizability", () => {
    const stepA = { capabilityId: "a", input: {}, priority: 1, dependsOn: [] as string[] };
    const stepB = { capabilityId: "b", input: {}, priority: 2, dependsOn: ["a"] };
    expect(planner.canRunParallel(stepA, stepB)).toBe(false);
    expect(planner.canRunParallel(stepA, { capabilityId: "c", input: {}, priority: 3, dependsOn: [] })).toBe(true);
  });
});

// ══════════════════════════════════════════════════════════════
// DISCOVERY
// ══════════════════════════════════════════════════════════════

describe("Capability Discovery", () => {
  it("creates manual entry", () => {
    const disc = new CapabilityDiscovery();
    const entry = disc.createManualEntry({
      name: "My API",
      description: "A test API",
      category: "Data",
      baseUrl: "https://api.myservice.com",
    });
    expect(entry.id).toBe("my-api");
    expect(entry.name).toBe("My API");
    expect(entry.authType).toBe("NONE");
    expect(entry.https).toBe(true);
  });

  it("clears cache", () => {
    const disc = new CapabilityDiscovery();
    disc.clearCache();
    // No error means success
  });
});

// ══════════════════════════════════════════════════════════════
// VERIFIER
// ══════════════════════════════════════════════════════════════

describe("Provider Verifier", () => {
  it("verifies provider without URL", async () => {
    const verifier = new ProviderVerifier();
    const prov = makeProvider({ baseUrl: undefined });
    const result = await verifier.verify(prov);
    expect(result.valid).toBe(true);
  });

  it("blocks verification of SSRF URLs", async () => {
    const verifier = new ProviderVerifier();
    const prov = makeProvider({ baseUrl: "http://169.254.169.254/" });
    const result = await verifier.verify(prov);
    expect(result.valid).toBe(false);
    expect(result.trustLevel).toBe("BLOCKED");
  });

  it("returns health history", async () => {
    const verifier = new ProviderVerifier();
    const prov = makeProvider({ baseUrl: undefined });
    await verifier.healthCheck(prov);
    const history = verifier.getHealthHistory("test-provider");
    expect(history.length).toBe(1);
    expect(history[0].status).toBe("HEALTHY");
  });

  it("reports overall health", async () => {
    const verifier = new ProviderVerifier();
    const prov = makeProvider({ baseUrl: undefined });
    await verifier.healthCheck(prov);
    const health = verifier.getOverallHealth("test-provider");
    expect(health.status).toBe("HEALTHY");
    expect(health.successRate).toBe(1);
  });
});

// ══════════════════════════════════════════════════════════════
// ENGINE FACTORY
// ══════════════════════════════════════════════════════════════

describe("createCapabilityEngine", () => {
  it("creates fully-wired engine", () => {
    const engine = createCapabilityEngine();
    expect(engine.registry).toBeDefined();
    expect(engine.execution).toBeDefined();
    expect(engine.ranker).toBeDefined();
    expect(engine.normalizer).toBeDefined();
    expect(engine.provenance).toBeDefined();
    expect(engine.fallback).toBeDefined();
    expect(engine.router).toBeDefined();
    expect(engine.planner).toBeDefined();
    expect(engine.verifier).toBeDefined();
    expect(engine.discovery).toBeDefined();
    expect(engine.cache).toBeDefined();
    expect(engine.circuitBreaker).toBeDefined();
    expect(engine.authManager).toBeDefined();
    expect(engine.metrics).toBeDefined();
    expect(engine.merger).toBeDefined();
  });

  it("engine registry works end-to-end", () => {
    const engine = createCapabilityEngine();
    engine.registry.registerCapability(makeCapability());
    engine.registry.registerProvider(makeProvider());
    expect(engine.registry.getCapability("test-cap")).toBeDefined();
    expect(engine.registry.getProvider("test-provider")).toBeDefined();
  });

  it("engine router can find providers", () => {
    const engine = createCapabilityEngine();
    engine.registry.registerCapability(makeCapability());
    engine.registry.registerProvider(makeProvider());
    const best = engine.router.findBestProvider("test-cap");
    expect(best).not.toBeNull();
    expect(best!.id).toBe("test-provider");
  });
});
