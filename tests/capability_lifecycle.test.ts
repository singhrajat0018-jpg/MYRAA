/**
 * Phase 19C — Provider Lifecycle, Reputation, Versioning, Marketplace, Diff,
 *             Manifest, Audit, Policy tests
 *
 * Covers all 8 new modules from Phase 19C.
 * Run: npx vitest run tests/capability_lifecycle.test.ts
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  ProviderLifecycleManager,
  VALID_TRANSITION_MAP,
  isTerminalState,
  type ProviderLifecycleState,
} from "../src/capabilities/lifecycle";

import {
  ProviderReputationEngine,
  type ReputationDimension,
} from "../src/capabilities/reputation";

import {
  VersionManager,
  VERSION_MODULE,
} from "../src/capabilities/versions";

import {
  CapabilityMarketplace,
  type MarketplaceListing,
  type ProviderRef,
} from "../src/capabilities/marketplace";

import {
  DiscoveryDiffEngine,
  type DiscoveryDiffResult,
} from "../src/capabilities/diff";

import {
  ManifestValidator,
  type ProviderManifest,
} from "../src/capabilities/manifest";

import {
  AuditLog,
  type AuditOperation,
  type AuditActor,
} from "../src/capabilities/audit";

import {
  ProviderPolicyEngine,
  type Provider,
  type TrustLevel,
  type CapabilitySource,
  type AuthType,
  type CorsSupport,
  type ReliabilityMetrics,
  type LatencyMetrics,
  type ProviderMetadata,
} from "../src/capabilities/policy";

// ── Helpers ──────────────────────────────────────────────────────

function makeProvider(overrides: Partial<Provider> = {}): Provider {
  return {
    id: `prov-${Math.random().toString(36).slice(2, 8)}`,
    name: "Test Provider",
    description: "A test provider",
    source: "DISCOVERED" as CapabilitySource,
    capabilities: ["test.cap"],
    baseUrl: "https://api.example.com",
    authType: "NONE" as AuthType,
    httpsRequired: true,
    cors: "UNKNOWN" as CorsSupport,
    reliability: { successRate: 1, totalRequests: 0, totalFailures: 0, consecutiveFailures: 0 } as ReliabilityMetrics,
    latency: { avgMs: 100, p50Ms: 100, p95Ms: 200, p99Ms: 300, sampleCount: 1 } as LatencyMetrics,
    trustScore: 75,
    trustLevel: "VERIFIED" as TrustLevel,
    enabled: true,
    version: "1.0.0",
    tags: ["test"],
    addedAt: Date.now(),
    metadata: {} as ProviderMetadata,
    ...overrides,
  };
}

function makeListing(overrides: Partial<MarketplaceListing> = {}): MarketplaceListing {
  return {
    capabilityId: `cap-${Math.random().toString(36).slice(2, 8)}`,
    name: "Test Capability",
    description: "A test capability",
    category: "test",
    providers: [
      { providerId: "prov-1", name: "Provider 1", status: "active", trust: 80, health: 90, version: "1.0.0", latency: 100, reliability: 95 },
    ],
    status: "active",
    quality: 85,
    availability: 90,
    auth: "none",
    freshness: 95,
    cost: "free",
    trust: 80,
    version: "1.0.0",
    tags: ["test", "free"],
    addedAt: Date.now(),
    updatedAt: Date.now(),
    ...overrides,
  };
}

// ══════════════════════════════════════════════════════════════════
// 1. Provider Lifecycle Manager
// ══════════════════════════════════════════════════════════════════

describe("ProviderLifecycleManager", () => {
  let lm: ProviderLifecycleManager;

  beforeEach(() => {
    lm = new ProviderLifecycleManager();
  });

  it("defaults unknown provider to DISCOVERED", () => {
    expect(lm.getState("unknown")).toBe("DISCOVERED");
  });

  it("validates the happy-path transition chain", () => {
    const steps: ProviderLifecycleState[] = [
      "DISCOVERED", "CANDIDATE", "PENDING_VERIFICATION", "VERIFIED", "TRUSTED", "ENABLED",
    ];
    for (let i = 1; i < steps.length; i++) {
      const t = lm.transition("prov-1", steps[i], "step", "ADMIN");
      expect(t).not.toBeNull();
      expect(t!.from).toBe(steps[i - 1]);
      expect(t!.to).toBe(steps[i]);
    }
    expect(lm.getState("prov-1")).toBe("ENABLED");
  });

  it("allows ENABLED → DEGRADED → QUARANTINED → ENABLED cycle", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p", "VERIFIED", "r", "ADMIN");
    lm.transition("p", "TRUSTED", "r", "ADMIN");
    lm.transition("p", "ENABLED", "r", "ADMIN");

    lm.transition("p", "DEGRADED", "perf", "SYSTEM_VERIFIER");
    expect(lm.getState("p")).toBe("DEGRADED");

    lm.transition("p", "QUARANTINED", "bad", "SYSTEM_VERIFIER");
    expect(lm.getState("p")).toBe("QUARANTINED");

    lm.transition("p", "ENABLED", "recovered", "ADMIN");
    expect(lm.getState("p")).toBe("ENABLED");
  });

  it("rejects invalid transitions (DISCOVERED → ENABLED)", () => {
    const t = lm.transition("p", "ENABLED", "skip", "ADMIN");
    expect(t).toBeNull();
    expect(lm.getState("p")).toBe("DISCOVERED");
  });

  it("rejects transitions from terminal states", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "REJECTED", "bad", "ADMIN");
    expect(lm.getState("p")).toBe("REJECTED");
    expect(isTerminalState("REJECTED")).toBe(true);

    const t = lm.transition("p", "ENABLED", "try", "ADMIN");
    expect(t).toBeNull();
  });

  it("rejects transitions from REMOVED", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p", "VERIFIED", "r", "ADMIN");
    lm.transition("p", "TRUSTED", "r", "ADMIN");
    lm.transition("p", "ENABLED", "r", "ADMIN");
    lm.transition("p", "DISABLED", "r", "ADMIN");
    lm.transition("p", "REMOVED", "r", "ADMIN");
    expect(lm.getState("p")).toBe("REMOVED");
    expect(isTerminalState("REMOVED")).toBe(true);

    expect(lm.transition("p", "ENABLED", "back", "ADMIN")).toBeNull();
  });

  it("tracks transition history most-recent-first", () => {
    lm.transition("p", "CANDIDATE", "r1", "A");
    lm.transition("p", "PENDING_VERIFICATION", "r2", "B");
    lm.transition("p", "VERIFIED", "r3", "C");

    const h = lm.getHistory("p");
    expect(h.length).toBe(3);
    expect(h[0].to).toBe("VERIFIED");
    expect(h[0].actor).toBe("C");
    expect(h[1].to).toBe("PENDING_VERIFICATION");
    expect(h[2].to).toBe("CANDIDATE");
  });

  it("limits history with limit param", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p", "VERIFIED", "r", "ADMIN");

    const h = lm.getHistory("p", 1);
    expect(h.length).toBe(1);
    expect(h[0].to).toBe("VERIFIED");
  });

  it("canTransition returns true/false correctly", () => {
    expect(lm.canTransition("p", "CANDIDATE")).toBe(true); // DISCOVERED → CANDIDATE
    expect(lm.canTransition("p", "ENABLED")).toBe(false); // DISCOVERED → ENABLED invalid
  });

  it("increments version on each transition", () => {
    const t1 = lm.transition("p", "CANDIDATE", "r", "ADMIN");
    const t2 = lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");
    expect(t1!.version).toBe(1);
    expect(t2!.version).toBe(2);
  });

  it("emits TRANSITION events to listeners", () => {
    const events: unknown[] = [];
    lm.on((e) => events.push(e));

    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    expect(events.length).toBe(1);
    expect((events[0] as { type: string }).type).toBe("TRANSITION");
  });

  it("emits INVALID_TRANSITION events", () => {
    const events: unknown[] = [];
    lm.on((e) => events.push(e));

    lm.transition("p", "ENABLED", "skip", "ADMIN");
    expect(events.length).toBe(1);
    expect((events[0] as { type: string }).type).toBe("INVALID_TRANSITION");
  });

  it("unsubscribes listener", () => {
    const events: unknown[] = [];
    const unsub = lm.on((e) => events.push(e));

    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    expect(events.length).toBe(1);

    unsub();
    lm.transition("p2", "CANDIDATE", "r", "ADMIN");
    expect(events.length).toBe(1);
  });

  it("getStats counts providers in each state", () => {
    lm.transition("p1", "CANDIDATE", "r", "ADMIN");
    lm.transition("p2", "CANDIDATE", "r", "ADMIN");
    lm.transition("p2", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p3", "CANDIDATE", "r", "ADMIN");
    lm.transition("p3", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p3", "VERIFIED", "r", "ADMIN");

    const stats = lm.getStats();
    expect(stats["DISCOVERED"]).toBe(0);
    expect(stats["CANDIDATE"]).toBe(1); // p1
    expect(stats["PENDING_VERIFICATION"]).toBe(1); // p2
    expect(stats["VERIFIED"]).toBe(1); // p3
  });

  it("getDeprecatedProviders lists deprecated IDs", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p", "VERIFIED", "r", "ADMIN");
    lm.transition("p", "TRUSTED", "r", "ADMIN");
    lm.transition("p", "ENABLED", "r", "ADMIN");
    lm.transition("p", "DEPRECATED", "old", "ADMIN");

    expect(lm.getDeprecatedProviders()).toEqual(["p"]);
    expect(lm.getQuarantinedProviders()).toEqual([]);
  });

  it("getQuarantinedProviders lists quarantined IDs", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");
    lm.transition("p", "VERIFIED", "r", "ADMIN");
    lm.transition("p", "TRUSTED", "r", "ADMIN");
    lm.transition("p", "ENABLED", "r", "ADMIN");
    lm.transition("p", "DEGRADED", "r", "ADMIN");
    lm.transition("p", "QUARANTINED", "r", "ADMIN");

    expect(lm.getQuarantinedProviders()).toEqual(["p"]);
  });

  it("exportSnapshot and importSnapshot round-trip", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.transition("p", "PENDING_VERIFICATION", "r", "ADMIN");

    const snap = lm.exportSnapshot();
    const lm2 = new ProviderLifecycleManager();
    lm2.importSnapshot(snap);

    expect(lm2.getState("p")).toBe("PENDING_VERIFICATION");
    expect(lm2.getHistory("p").length).toBe(2);
  });

  it("reset clears all state", () => {
    lm.transition("p", "CANDIDATE", "r", "ADMIN");
    lm.reset();
    expect(lm.getState("p")).toBe("DISCOVERED");
    expect(lm.getHistory("p").length).toBe(0);
  });

  it("VALID_TRANSITION_MAP has all 12 states", () => {
    expect(VALID_TRANSITION_MAP.size).toBe(12);
  });
});

// ══════════════════════════════════════════════════════════════════
// 2. Provider Reputation Engine
// ══════════════════════════════════════════════════════════════════

describe("ProviderReputationEngine", () => {
  let re: ProviderReputationEngine;

  beforeEach(() => {
    re = new ProviderReputationEngine();
  });

  it("cold start returns coldStartScore (50) for all dimensions", () => {
    const score = re.getScore("new-provider");
    expect(score.overall).toBe(50);
    expect(score.dimensions.reliability).toBe(50);
    expect(score.evidenceCount).toBe(0);
  });

  it("recordSuccess increases reliability", () => {
    const events = re.recordSuccess("p1");
    expect(events.length).toBeGreaterThanOrEqual(1);
    expect(events[0].dimension).toBe("reliability");
    expect(events[0].delta).toBeGreaterThan(0);

    const score = re.getScore("p1");
    expect(score.dimensions.reliability).toBeGreaterThan(50);
    expect(score.evidenceCount).toBe(1);
  });

  it("recordSuccess with latency updates latency dimension", () => {
    re.recordSuccess("p1", 50);
    const score = re.getScore("p1");
    expect(score.dimensions.latency).toBeGreaterThan(50);
  });

  it("recordFailure decreases reliability and availability", () => {
    re.recordFailure("p1", "timeout");
    const score = re.getScore("p1");
    expect(score.dimensions.reliability).toBeLessThan(50);
    expect(score.dimensions.availability).toBeLessThan(50);
    expect(score.evidenceCount).toBe(1);
  });

  it("recordLatency updates latency dimension", () => {
    re.recordLatency("fast", 50);
    const fast = re.getScore("fast");

    re.recordLatency("slow", 5000);
    const slow = re.getScore("slow");

    expect(fast.dimensions.latency).toBeGreaterThan(slow.dimensions.latency);
  });

  it("recordSchemaChange compatible boosts schema_stability", () => {
    re.recordSchemaChange("p", true);
    const score = re.getScore("p");
    expect(score.dimensions.schema_stability).toBeGreaterThan(50);
  });

  it("recordSchemaChange breaking decreases schema_stability", () => {
    re.recordSchemaChange("p", false);
    const score = re.getScore("p");
    expect(score.dimensions.schema_stability).toBeLessThan(50);
  });

  it("recordFreshness fresh boosts freshness", () => {
    re.recordFreshness("p", true);
    const score = re.getScore("p");
    expect(score.dimensions.freshness).toBeGreaterThan(50);
  });

  it("recordFreshness stale decreases freshness", () => {
    re.recordFreshness("p", false);
    const score = re.getScore("p");
    expect(score.dimensions.freshness).toBeLessThan(50);
  });

  it("scores are bounded 0–100", () => {
    for (let i = 0; i < 100; i++) re.recordSuccess("p");
    const score = re.getScore("p");
    expect(score.overall).toBeGreaterThanOrEqual(0);
    expect(score.overall).toBeLessThanOrEqual(100);
    for (const v of Object.values(score.dimensions)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    }
  });

  it("compare returns winner and margin", () => {
    re.recordSuccess("good");
    re.recordSuccess("good");
    re.recordSuccess("good");
    re.recordFailure("bad");

    const cmp = re.compare("good", "bad");
    expect(cmp.winner).toBe("good");
    expect(cmp.margin).toBeGreaterThan(0);
    expect(cmp.breakdown.reliability.a).toBeGreaterThan(cmp.breakdown.reliability.b);
  });

  it("getTopProviders returns sorted by overall", () => {
    re.recordSuccess("a");
    re.recordSuccess("a");
    re.recordFailure("b");

    const top = re.getTopProviders(5);
    expect(top.length).toBe(2);
    expect(top[0].providerId).toBe("a");
  });

  it("getExplanation returns strengths/weaknesses", () => {
    for (let i = 0; i < 20; i++) re.recordSuccess("good");
    const exp = re.getExplanation("good");
    expect(exp.overall).toBeGreaterThan(50);
    expect(exp.strengths.length).toBeGreaterThan(0);
    expect(exp.summary).toBeTruthy();
  });

  it("getExplanation with low score has weaknesses", () => {
    for (let i = 0; i < 20; i++) re.recordFailure("bad");
    const exp = re.getExplanation("bad");
    expect(exp.weaknesses.length).toBeGreaterThan(0);
  });

  it("getHistory returns event history", () => {
    re.recordSuccess("p");
    re.recordFailure("p");
    const h = re.getHistory("p");
    // recordSuccess emits 1 event (reliability), recordFailure emits 2 (reliability + availability)
    expect(h.length).toBe(3);
  });

  it("getHistory respects limit", () => {
    for (let i = 0; i < 10; i++) re.recordSuccess("p");
    const h = re.getHistory("p", 3);
    expect(h.length).toBe(3);
  });

  it("getStats returns aggregate info", () => {
    re.recordSuccess("a");
    re.recordSuccess("b");
    const stats = re.getStats();
    expect(stats.providerCount).toBe(2);
    expect(stats.averageOverall).toBeGreaterThan(0);
    expect(stats.topProvider).toBeTruthy();
  });

  it("getStats returns empty stats for no providers", () => {
    const stats = re.getStats();
    expect(stats.providerCount).toBe(0);
    expect(stats.averageOverall).toBe(0);
  });

  it("exportSnapshot and importSnapshot round-trip", () => {
    re.recordSuccess("p1");
    re.recordFailure("p2");

    const snap = re.exportSnapshot();
    const re2 = new ProviderReputationEngine();
    re2.importSnapshot(snap);

    const s1 = re2.getScore("p1");
    expect(s1.evidenceCount).toBe(1);
  });
});

// ══════════════════════════════════════════════════════════════════
// 3. Version Manager
// ══════════════════════════════════════════════════════════════════

describe("VersionManager", () => {
  let vm: VersionManager;

  beforeEach(() => {
    vm = new VersionManager();
  });

  it("exports VERSION_MODULE constant", () => {
    expect(VERSION_MODULE).toBe("1.0.0");
  });

  it("setProviderVersion stores and retrieves", () => {
    vm.setProviderVersion("p1", "1.0.0", { capabilities: ["a"] });
    const rec = vm.getProviderVersion("p1");
    expect(rec).toBeDefined();
    expect(rec!.version).toBe("1.0.0");
    expect(rec!.providerId).toBe("p1");
    expect(rec!.capabilities).toEqual(["a"]);
  });

  it("setProviderVersion tracks previousVersion", () => {
    vm.setProviderVersion("p1", "1.0.0");
    vm.setProviderVersion("p1", "1.1.0");
    const rec = vm.getProviderVersion("p1");
    expect(rec!.previousVersion).toBe("1.0.0");
    expect(rec!.version).toBe("1.1.0");
  });

  it("getProviderHistory tracks all versions", () => {
    vm.setProviderVersion("p1", "1.0.0");
    vm.setProviderVersion("p1", "1.1.0");
    vm.setProviderVersion("p1", "2.0.0");
    const h = vm.getProviderHistory("p1");
    expect(h.length).toBe(3);
    expect(h[0].version).toBe("1.0.0");
    expect(h[2].version).toBe("2.0.0");
  });

  it("setCapabilityVersion stores and retrieves", () => {
    vm.setCapabilityVersion("c1", "1.0.0");
    const rec = vm.getCapabilityVersion("c1");
    expect(rec).toBeDefined();
    expect(rec!.version).toBe("1.0.0");
  });

  it("compareSchemas returns FULLY_COMPATIBLE for identical schemas", () => {
    const schema = { type: "object" as const, properties: { a: { type: "string" as const } }, required: ["a"] };
    const result = vm.compareSchemas(schema, schema);
    expect(result.result).toBe("FULLY_COMPATIBLE");
    expect(result.diffs.length).toBe(0);
  });

  it("compareSchemas detects ADDED_REQUIRED (BREAKING)", () => {
    const old = { type: "object" as const, properties: { a: { type: "string" as const } }, required: ["a"] };
    const nw = { type: "object" as const, properties: { a: { type: "string" as const }, b: { type: "number" as const } }, required: ["a", "b"] };
    const result = vm.compareSchemas(old, nw);
    expect(result.result).toBe("BREAKING");
    expect(result.diffs.some((d) => d.type === "ADDED_REQUIRED")).toBe(true);
  });

  it("compareSchemas detects REMOVED field (BREAKING)", () => {
    const old = { type: "object" as const, properties: { a: { type: "string" as const }, b: { type: "number" as const } }, required: ["a"] };
    const nw = { type: "object" as const, properties: { a: { type: "string" as const } }, required: ["a"] };
    const result = vm.compareSchemas(old, nw);
    expect(result.result).toBe("BREAKING");
    expect(result.diffs.some((d) => d.type === "REMOVED")).toBe(true);
  });

  it("compareSchemas detects TYPE_CHANGED (BREAKING)", () => {
    const old = { type: "object" as const, properties: { a: { type: "string" as const } }, required: [] };
    const nw = { type: "object" as const, properties: { a: { type: "number" as const } }, required: [] };
    const result = vm.compareSchemas(old, nw);
    expect(result.result).toBe("BREAKING");
    expect(result.diffs.some((d) => d.type === "TYPE_CHANGED")).toBe(true);
  });

  it("compareSchemas detects ADDED_OPTIONAL (BACKWARD_COMPATIBLE)", () => {
    const old = { type: "object" as const, properties: { a: { type: "string" as const } }, required: [] };
    const nw = { type: "object" as const, properties: { a: { type: "string" as const }, b: { type: "number" as const } }, required: [] };
    const result = vm.compareSchemas(old, nw);
    expect(result.result).toBe("BACKWARD_COMPATIBLE");
    expect(result.diffs.some((d) => d.type === "ADDED_OPTIONAL")).toBe(true);
  });

  it("canMigrate returns true for adjacent versions", () => {
    vm.setProviderVersion("p", "1.0.0");
    vm.setProviderVersion("p", "1.1.0");
    expect(vm.canMigrate("p", "1.0.0", "1.1.0")).toBe(true);
  });

  it("canMigrate returns false for non-adjacent versions", () => {
    vm.setProviderVersion("p", "1.0.0");
    vm.setProviderVersion("p", "1.1.0");
    vm.setProviderVersion("p", "1.2.0");
    expect(vm.canMigrate("p", "1.0.0", "1.2.0")).toBe(false);
  });

  it("canMigrate returns false for unknown versions", () => {
    expect(vm.canMigrate("p", "1.0.0", "1.1.0")).toBe(false);
  });

  it("rollbackProvider reverts to previous version", () => {
    vm.setProviderVersion("p", "1.0.0");
    vm.setProviderVersion("p", "1.1.0");
    vm.setProviderVersion("p", "2.0.0");

    const rolled = vm.rollbackProvider("p");
    expect(rolled).toBeDefined();
    expect(rolled!.version).toBe("1.1.0");

    const current = vm.getProviderVersion("p");
    expect(current!.version).toBe("1.1.0");
  });

  it("rollbackProvider returns undefined with <2 versions", () => {
    vm.setProviderVersion("p", "1.0.0");
    expect(vm.rollbackProvider("p")).toBeUndefined();
  });

  it("getRollbackTarget returns previous version info", () => {
    vm.setProviderVersion("p", "1.0.0");
    vm.setProviderVersion("p", "2.0.0");
    const target = vm.getRollbackTarget("p");
    expect(target).toBeDefined();
    expect(target!.version).toBe("1.0.0");
  });

  it("isVersionStale returns true for mismatched versions", () => {
    vm.setProviderVersion("p", "1.0.0");
    expect(vm.isVersionStale("p", "1.1.0")).toBe(true);
    expect(vm.isVersionStale("p", "1.0.0")).toBe(false);
  });

  it("isVersionStale returns true for unknown provider", () => {
    expect(vm.isVersionStale("unknown", "1.0.0")).toBe(true);
  });

  it("exportSnapshot and importSnapshot round-trip", () => {
    vm.setProviderVersion("p1", "1.0.0");
    vm.setCapabilityVersion("c1", "2.0.0");

    const snap = vm.exportSnapshot();
    const vm2 = new VersionManager();
    vm2.importSnapshot(snap);

    expect(vm2.getProviderVersion("p1")!.version).toBe("1.0.0");
    expect(vm2.getCapabilityVersion("c1")!.version).toBe("2.0.0");
  });
});

// ══════════════════════════════════════════════════════════════════
// 4. Capability Marketplace
// ══════════════════════════════════════════════════════════════════

describe("CapabilityMarketplace", () => {
  let mp: CapabilityMarketplace;

  beforeEach(() => {
    mp = new CapabilityMarketplace();
  });

  it("addListing and getListing", () => {
    const l = makeListing({ capabilityId: "weather" });
    mp.addListing(l);
    expect(mp.getListing("weather")).toBeDefined();
    expect(mp.getListing("weather")!.name).toBe("Test Capability");
  });

  it("removeListing removes a listing", () => {
    mp.addListing(makeListing({ capabilityId: "c1" }));
    expect(mp.removeListing("c1")).toBe(true);
    expect(mp.getListing("c1")).toBeUndefined();
  });

  it("removeListing returns false for non-existent", () => {
    expect(mp.removeListing("nope")).toBe(false);
  });

  it("updateProvider adds new provider to listing", () => {
    mp.addListing(makeListing({ capabilityId: "c1" }));
    const newProv: ProviderRef = { providerId: "prov-2", name: "P2", status: "active", trust: 90, health: 95, version: "2.0.0", latency: 50, reliability: 98 };
    const ok = mp.updateProvider("c1", newProv);
    expect(ok).toBe(true);
    expect(mp.getProvidersForCapability("c1").length).toBe(2);
  });

  it("updateProvider updates existing provider", () => {
    mp.addListing(makeListing({ capabilityId: "c1" }));
    const updated: ProviderRef = { providerId: "prov-1", name: "P1-v2", status: "degraded", trust: 60, health: 70, version: "1.1.0", latency: 200, reliability: 80 };
    mp.updateProvider("c1", updated);
    const providers = mp.getProvidersForCapability("c1");
    expect(providers[0].status).toBe("degraded");
    expect(providers[0].name).toBe("P1-v2");
  });

  it("updateProvider returns false for unknown capability", () => {
    expect(mp.updateProvider("nope", { providerId: "p", name: "p", status: "active", trust: 50, health: 50, version: "1.0.0", latency: 100, reliability: 50 })).toBe(false);
  });

  it("search with no filters returns all", () => {
    mp.addListing(makeListing({ capabilityId: "a" }));
    mp.addListing(makeListing({ capabilityId: "b" }));
    expect(mp.search({}).length).toBe(2);
  });

  it("search filters by query", () => {
    mp.addListing(makeListing({ capabilityId: "weather-api", name: "Weather API", tags: ["weather"] }));
    mp.addListing(makeListing({ capabilityId: "news-api", name: "News API", tags: ["news"] }));
    const results = mp.search({ query: "weather" });
    expect(results.length).toBe(1);
    expect(results[0].capabilityId).toBe("weather-api");
  });

  it("search filters by category", () => {
    mp.addListing(makeListing({ capabilityId: "a", category: "data" }));
    mp.addListing(makeListing({ capabilityId: "b", category: "search" }));
    expect(mp.search({ category: "data" }).length).toBe(1);
  });

  it("search filters by status", () => {
    mp.addListing(makeListing({ capabilityId: "a", status: "active" }));
    mp.addListing(makeListing({ capabilityId: "b", status: "deprecated" }));
    expect(mp.search({ status: "deprecated" }).length).toBe(1);
  });

  it("search filters by minTrust", () => {
    mp.addListing(makeListing({ capabilityId: "a", trust: 90 }));
    mp.addListing(makeListing({ capabilityId: "b", trust: 40 }));
    expect(mp.search({ minTrust: 70 }).length).toBe(1);
  });

  it("search filters by maxCost", () => {
    mp.addListing(makeListing({ capabilityId: "a", cost: "free" }));
    mp.addListing(makeListing({ capabilityId: "b", cost: "high" }));
    expect(mp.search({ maxCost: "free" }).length).toBe(1);
  });

  it("search filters by provider", () => {
    mp.addListing(makeListing({ capabilityId: "a", providers: [{ providerId: "p1", name: "P1", status: "active", trust: 80, health: 90, version: "1.0.0", latency: 100, reliability: 95 }] }));
    mp.addListing(makeListing({ capabilityId: "b", providers: [{ providerId: "p2", name: "P2", status: "active", trust: 80, health: 90, version: "1.0.0", latency: 100, reliability: 95 }] }));
    expect(mp.search({ provider: "p1" }).length).toBe(1);
  });

  it("search filters by tags", () => {
    mp.addListing(makeListing({ capabilityId: "a", tags: ["weather", "free"] }));
    mp.addListing(makeListing({ capabilityId: "b", tags: ["news", "paid"] }));
    expect(mp.search({ tags: ["weather"] }).length).toBe(1);
  });

  it("search respects limit and offset", () => {
    for (let i = 0; i < 10; i++) mp.addListing(makeListing({ capabilityId: `c${i}` }));
    const page1 = mp.search({ limit: 3, offset: 0 });
    const page2 = mp.search({ limit: 3, offset: 3 });
    expect(page1.length).toBe(3);
    expect(page2.length).toBe(3);
    expect(page1[0].capabilityId).not.toBe(page2[0].capabilityId);
  });

  it("getByCategory returns correct listings", () => {
    mp.addListing(makeListing({ capabilityId: "a", category: "weather" }));
    mp.addListing(makeListing({ capabilityId: "b", category: "weather" }));
    mp.addListing(makeListing({ capabilityId: "c", category: "news" }));
    expect(mp.getByCategory("weather").length).toBe(2);
  });

  it("getProvidersForCapability returns empty for unknown", () => {
    expect(mp.getProvidersForCapability("nope")).toEqual([]);
  });

  it("getCapabilityHealth computes counts", () => {
    mp.addListing(makeListing({
      capabilityId: "c1",
      providers: [
        { providerId: "p1", name: "P1", status: "active", trust: 80, health: 90, version: "1.0.0", latency: 100, reliability: 95 },
        { providerId: "p2", name: "P2", status: "degraded", trust: 50, health: 60, version: "1.0.0", latency: 200, reliability: 70 },
      ],
    }));
    const h = mp.getCapabilityHealth("c1");
    expect(h).toBeDefined();
    expect(h!.healthyCount).toBe(1);
    expect(h!.degradedCount).toBe(1);
    expect(h!.totalProviders).toBe(2);
    expect(h!.singleProviderRisk).toBe(false);
  });

  it("getCapabilityHealth detects single provider risk", () => {
    mp.addListing(makeListing({ capabilityId: "c1", providers: [{ providerId: "p1", name: "P1", status: "active", trust: 80, health: 90, version: "1.0.0", latency: 100, reliability: 95 }] }));
    const h = mp.getCapabilityHealth("c1");
    expect(h!.singleProviderRisk).toBe(true);
  });

  it("getStats returns aggregate info", () => {
    mp.addListing(makeListing({ capabilityId: "a", status: "deprecated" }));
    mp.addListing(makeListing({ capabilityId: "b", status: "active" }));
    const stats = mp.getStats();
    expect(stats.totalCapabilities).toBe(2);
    expect(stats.deprecatedCapabilities).toBe(1);
    expect(stats.totalProviders).toBe(2);
  });

  it("getCategories returns sorted by count", () => {
    mp.addListing(makeListing({ capabilityId: "a", category: "data" }));
    mp.addListing(makeListing({ capabilityId: "b", category: "data" }));
    mp.addListing(makeListing({ capabilityId: "c", category: "search" }));
    const cats = mp.getCategories();
    expect(cats[0].category).toBe("data");
    expect(cats[0].count).toBe(2);
  });

  it("getCapabilitiesNeedingAttention finds single-provider and deprecated", () => {
    mp.addListing(makeListing({ capabilityId: "a", status: "deprecated" }));
    mp.addListing(makeListing({ capabilityId: "b", providers: [{ providerId: "p1", name: "P1", status: "active", trust: 80, health: 90, version: "1.0.0", latency: 100, reliability: 95 }] }));
    const attn = mp.getCapabilitiesNeedingAttention();
    expect(attn.length).toBe(2);
  });

  it("exportSnapshot and importSnapshot round-trip", () => {
    mp.addListing(makeListing({ capabilityId: "a" }));
    mp.addListing(makeListing({ capabilityId: "b" }));
    const snap = mp.exportSnapshot();
    const mp2 = new CapabilityMarketplace();
    const count = mp2.importSnapshot(snap);
    expect(count).toBe(2);
    expect(mp2.getListing("a")).toBeDefined();
  });
});

// ══════════════════════════════════════════════════════════════════
// 5. Discovery Diff Engine
// ══════════════════════════════════════════════════════════════════

describe("DiscoveryDiffEngine", () => {
  let diff: DiscoveryDiffEngine;

  beforeEach(() => {
    diff = new DiscoveryDiffEngine();
  });

  function makeProv(id: string, overrides: Partial<Provider> = {}): Provider {
    return makeProvider({ id, name: `Provider ${id}`, ...overrides });
  }

  it("detects added providers", () => {
    const prev = [makeProv("a")];
    const curr = [makeProv("a"), makeProv("b")];
    const result = diff.diff(prev, curr);
    expect(result.added).toEqual(["b"]);
    expect(result.removed).toEqual([]);
    expect(result.stats.added).toBe(1);
  });

  it("detects removed providers", () => {
    const prev = [makeProv("a"), makeProv("b")];
    const curr = [makeProv("a")];
    const result = diff.diff(prev, curr);
    expect(result.removed).toEqual(["b"]);
    expect(result.stats.removed).toBe(1);
  });

  it("detects changed providers", () => {
    const prev = [makeProv("a", { version: "1.0.0" })];
    const curr = [makeProv("a", { version: "2.0.0" })];
    const result = diff.diff(prev, curr);
    expect(result.changed.length).toBe(1);
    expect(result.changed[0].providerId).toBe("a");
    expect(result.changed[0].changes!.some((c) => c.field === "version")).toBe(true);
  });

  it("detects unchanged providers", () => {
    const p = makeProv("a");
    const result = diff.diff([p], [p]);
    expect(result.unchanged).toEqual(["a"]);
    expect(result.stats.unchanged).toBe(1);
  });

  it("handles empty previous (all added)", () => {
    const result = diff.diff([], [makeProv("a"), makeProv("b")]);
    expect(result.added).toEqual(["a", "b"]);
    expect(result.stats.totalPrevious).toBe(0);
    expect(result.stats.totalCurrent).toBe(2);
  });

  it("handles empty current (all removed)", () => {
    const result = diff.diff([makeProv("a"), makeProv("b")], []);
    expect(result.removed).toEqual(["a", "b"]);
    expect(result.stats.totalCurrent).toBe(0);
  });

  it("handles both empty", () => {
    const result = diff.diff([], []);
    expect(result.added.length).toBe(0);
    expect(result.removed.length).toBe(0);
    expect(result.changed.length).toBe(0);
  });

  it("hasBreakingChanges detects baseUrl change", () => {
    const prev = [makeProv("a", { baseUrl: "https://old.example.com" })];
    const curr = [makeProv("a", { baseUrl: "https://new.example.com" })];
    const result = diff.diff(prev, curr);
    expect(diff.hasBreakingChanges(result)).toBe(true);
  });

  it("hasBreakingChanges detects authType change", () => {
    const prev = [makeProv("a", { authType: "NONE" as AuthType })];
    const curr = [makeProv("a", { authType: "API_KEY" as AuthType })];
    const result = diff.diff(prev, curr);
    expect(diff.hasBreakingChanges(result)).toBe(true);
  });

  it("hasBreakingChanges returns false for non-breaking changes", () => {
    const prev = [makeProv("a", { version: "1.0.0" })];
    const curr = [makeProv("a", { version: "2.0.0" })];
    const result = diff.diff(prev, curr);
    expect(diff.hasBreakingChanges(result)).toBe(false);
  });

  it("summarize returns human-readable string", () => {
    const prev = [makeProv("a")];
    const curr = [makeProv("a"), makeProv("b")];
    const result = diff.diff(prev, curr, "test");
    const summary = diff.summarize(result);
    expect(summary).toContain("Added 1");
    expect(summary).toContain("test");
  });

  it("summarize reports no changes", () => {
    const p = makeProv("a");
    const result = diff.diff([p], [p]);
    const summary = diff.summarize(result);
    expect(summary).toContain("No changes detected");
  });

  it("computeChange detects capabilities change", () => {
    const old = makeProv("a", { capabilities: ["a", "b"] });
    const curr = makeProv("a", { capabilities: ["a", "c"] });
    const changes = DiscoveryDiffEngine.computeChange(old, curr);
    expect(changes.some((c) => c.field === "capabilities")).toBe(true);
  });
});

// ══════════════════════════════════════════════════════════════════
// 6. Manifest Validator
// ══════════════════════════════════════════════════════════════════

describe("ManifestValidator", () => {
  let mv: ManifestValidator;

  beforeEach(() => {
    mv = new ManifestValidator();
  });

  function makeManifest(overrides: Partial<ProviderManifest> = {}): ProviderManifest {
    return {
      providerId: "test-provider",
      name: "Test Provider",
      version: "1.0.0",
      description: "A test",
      capabilities: ["test.cap"],
      auth: "NONE",
      source: "DISCOVERED",
      ...overrides,
    };
  }

  it("validates a complete valid manifest", () => {
    const result = mv.validate(makeManifest());
    expect(result.valid).toBe(true);
    expect(result.errors.length).toBe(0);
  });

  it("requires providerId", () => {
    const result = mv.validate(makeManifest({ providerId: "" }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("providerId"))).toBe(true);
  });

  it("requires name", () => {
    const result = mv.validate(makeManifest({ name: "" }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("name"))).toBe(true);
  });

  it("requires valid semver version", () => {
    const result = mv.validate(makeManifest({ version: "not-a-version" }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("semver"))).toBe(true);
  });

  it("requires description", () => {
    const result = mv.validate(makeManifest({ description: "" }));
    expect(result.valid).toBe(false);
  });

  it("requires at least one capability", () => {
    const result = mv.validate(makeManifest({ capabilities: [] }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("capability"))).toBe(true);
  });

  it("requires valid auth type", () => {
    const result = mv.validate(makeManifest({ auth: "INVALID" as AuthType }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("auth"))).toBe(true);
  });

  it("requires source", () => {
    const result = mv.validate(makeManifest({ source: undefined as unknown as CapabilitySource }));
    expect(result.valid).toBe(false);
  });

  it("warns when baseUrl is missing", () => {
    const result = mv.validate(makeManifest({ baseUrl: undefined }));
    expect(result.valid).toBe(true);
    expect(result.warnings.some((w) => w.includes("baseUrl"))).toBe(true);
  });

  it("rejects non-HTTPS baseUrl", () => {
    const result = mv.validate(makeManifest({ baseUrl: "http://api.example.com" }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("HTTPS"))).toBe(true);
  });

  it("rejects private IP baseUrl", () => {
    const result = mv.validate(makeManifest({ baseUrl: "https://192.168.1.1/api" }));
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("private"))).toBe(true);
  });

  it("rejects localhost baseUrl", () => {
    const result = mv.validate(makeManifest({ baseUrl: "https://localhost/api" }));
    expect(result.valid).toBe(false);
  });

  it("validates semver with pre-release tags", () => {
    expect(ManifestValidator.validateVersion("1.0.0-beta.1")).toBe(true);
    expect(ManifestValidator.validateVersion("1.0.0+build.123")).toBe(true);
  });

  it("rejects invalid semver", () => {
    expect(ManifestValidator.validateVersion("1.0")).toBe(false);
    expect(ManifestValidator.validateVersion("v1.0.0")).toBe(false);
    expect(ManifestValidator.validateVersion("abc")).toBe(false);
  });

  it("toProvider converts manifest to Provider", () => {
    const manifest = makeManifest({ baseUrl: "https://api.example.com" });
    const provider = mv.toProvider(manifest);
    expect(provider.id).toBe("test-provider");
    expect(provider.name).toBe("Test Provider");
    expect(provider.httpsRequired).toBe(true);
    expect(provider.trustScore).toBe(0);
    expect(provider.enabled).toBe(false);
  });

  it("toProvider sets httpsRequired false for non-https", () => {
    const provider = mv.toProvider(makeManifest({ baseUrl: undefined }));
    expect(provider.httpsRequired).toBe(false);
  });

  it("fromPublicApisEntry converts entry to manifest", () => {
    const entry = { API: "OpenWeatherMap", Description: "Weather data", Auth: "apiKey", Link: "https://openweathermap.org/api", HTTPS: true, Cors: "yes", Category: "Weather" };
    const manifest = mv.fromPublicApisEntry(entry);
    expect(manifest.providerId).toBe("public-apis-openweathermap");
    expect(manifest.name).toBe("OpenWeatherMap");
    expect(manifest.auth).toBe("API_KEY");
    expect(manifest.source).toBe("DISCOVERED");
  });

  it("validateUrl accepts valid HTTPS URL", () => {
    expect(ManifestValidator.validateUrl("https://api.example.com").valid).toBe(true);
  });

  it("validateUrl rejects HTTP", () => {
    expect(ManifestValidator.validateUrl("http://api.example.com").valid).toBe(false);
  });

  it("validateUrl rejects invalid format", () => {
    expect(ManifestValidator.validateUrl("not-a-url").valid).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════
// 7. Audit Log
// ══════════════════════════════════════════════════════════════════

describe("AuditLog", () => {
  let audit: AuditLog;

  beforeEach(() => {
    audit = new AuditLog();
  });

  it("record creates event with auto-generated id and timestamp", () => {
    const event = audit.record({
      providerId: "p1",
      operation: "REGISTERED",
      reason: "test",
      actor: "ADMIN",
    });
    expect(event.id).toBeTruthy();
    expect(event.timestamp).toBeGreaterThan(0);
    expect(event.providerId).toBe("p1");
    expect(event.operation).toBe("REGISTERED");
  });

  it("getByProvider returns events for specific provider", () => {
    audit.record({ providerId: "p1", operation: "ENABLED", reason: "r", actor: "ADMIN" });
    audit.record({ providerId: "p2", operation: "ENABLED", reason: "r", actor: "ADMIN" });
    audit.record({ providerId: "p1", operation: "DISABLED", reason: "r", actor: "ADMIN" });

    const events = audit.getByProvider("p1");
    expect(events.length).toBe(2);
  });

  it("getByActor returns events for specific actor", () => {
    audit.record({ providerId: "p1", operation: "ENABLED", reason: "r", actor: "ADMIN" });
    audit.record({ providerId: "p2", operation: "ENABLED", reason: "r", actor: "SYSTEM_VERIFIER" });

    expect(audit.getByActor("ADMIN").length).toBe(1);
    expect(audit.getByActor("SYSTEM_VERIFIER").length).toBe(1);
  });

  it("getRecent returns most recent events", () => {
    for (let i = 0; i < 10; i++) {
      audit.record({ providerId: `p${i}`, operation: "HEALTH_CHECK", reason: "r", actor: "SYSTEM_VERIFIER" });
    }
    expect(audit.getRecent(5).length).toBe(5);
    expect(audit.getRecent().length).toBe(10);
  });

  it("getStats returns aggregate info", () => {
    audit.record({ providerId: "p1", operation: "ENABLED", reason: "r", actor: "ADMIN" });
    audit.record({ providerId: "p1", operation: "DISABLED", reason: "r", actor: "ADMIN" });
    audit.record({ providerId: "p2", operation: "ENABLED", reason: "r", actor: "SYSTEM_VERIFIER" });

    const stats = audit.getStats();
    expect(stats.total).toBe(3);
    expect(stats.byOperation["ENABLED"]).toBe(2);
    expect(stats.byActor["ADMIN"]).toBe(2);
    expect(stats.byProvider["p1"]).toBe(2);
  });

  it("respects maxHistory limit", () => {
    const smallAudit = new AuditLog({ maxHistory: 5 });
    for (let i = 0; i < 10; i++) {
      smallAudit.record({ providerId: `p${i}`, operation: "HEALTH_CHECK", reason: "r", actor: "SYSTEM_VERIFIER" });
    }
    expect(smallAudit.getRecent().length).toBe(5);
  });

  it("exportSnapshot and importSnapshot round-trip", () => {
    audit.record({ providerId: "p1", operation: "ENABLED", reason: "r", actor: "ADMIN" });
    audit.record({ providerId: "p2", operation: "DISABLED", reason: "r", actor: "ADMIN" });

    const snap = audit.exportSnapshot();
    expect(snap.version).toBe("1.0.0");
    expect(snap.events.length).toBe(2);

    const audit2 = new AuditLog();
    const imported = audit2.importSnapshot(snap);
    expect(imported).toBe(2);
    expect(audit2.getRecent().length).toBe(2);
  });

  it("importSnapshot deduplicates by id", () => {
    audit.record({ providerId: "p1", operation: "ENABLED", reason: "r", actor: "ADMIN" });
    const snap = audit.exportSnapshot();

    const imported = audit.importSnapshot(snap);
    expect(imported).toBe(0); // all already exist
  });

  it("importSnapshot returns 0 for invalid data", () => {
    expect(audit.importSnapshot({})).toBe(0);
    expect(audit.importSnapshot({ events: "not-array" as unknown })).toBe(0);
  });

  it("supports all AuditOperation types", () => {
    const ops: AuditOperation[] = [
      "REGISTERED", "UNREGISTERED", "ENABLED", "DISABLED", "VERIFIED",
      "BLOCKED", "TRUST_CHANGED", "UPDATED", "HEALTH_CHECK",
      "LIFECYCLE_TRANSITION", "AUTO_DEGRADE", "QUARANTINED", "DEPRECATED",
      "REPLACED", "ROLLBACK", "REPUTATION_UPDATE", "MANIFEST_IMPORTED",
    ];
    for (const op of ops) {
      audit.record({ providerId: "p", operation: op, reason: "test", actor: "ADMIN" });
    }
    expect(audit.getRecent().length).toBe(ops.length);
  });

  it("supports all AuditActor types", () => {
    const actors: AuditActor[] = ["SYSTEM_DISCOVERY", "SYSTEM_VERIFIER", "ADMIN", "USER", "MIGRATION"];
    for (const a of actors) {
      audit.record({ providerId: "p", operation: "HEALTH_CHECK", reason: "test", actor: a });
    }
    expect(audit.getRecent().length).toBe(5);
  });
});

// ══════════════════════════════════════════════════════════════════
// 8. Provider Policy Engine
// ══════════════════════════════════════════════════════════════════

describe("ProviderPolicyEngine", () => {
  let pe: ProviderPolicyEngine;

  beforeEach(() => {
    pe = new ProviderPolicyEngine();
  });

  it("allows verified provider with good trust", () => {
    const p = makeProvider({ trustLevel: "VERIFIED", trustScore: 80, capabilities: ["weather.get"] });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("ALLOW");
  });

  it("denies blocked source", () => {
    pe.updatePolicy({ blockedSources: ["CUSTOM"] });
    const p = makeProvider({ source: "CUSTOM" as CapabilitySource });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("DENY");
    expect(result.reason).toContain("blocked");
  });

  it("denies private IP URL", () => {
    const p = makeProvider({ baseUrl: "https://192.168.1.1/api" });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("DENY");
    expect(result.reason).toContain("private");
  });

  it("denies localhost URL", () => {
    const p = makeProvider({ baseUrl: "https://localhost/api" });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("DENY");
  });

  it("denies explicitly blocked trust level", () => {
    const p = makeProvider({ trustLevel: "BLOCKED" as TrustLevel });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("DENY");
    expect(result.reason).toContain("blocked");
  });

  it("requires approval for sensitive capabilities", () => {
    const p = makeProvider({ capabilities: ["COMMUNICATION"], trustLevel: "VERIFIED", trustScore: 80 });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("REQUIRE_APPROVAL");
  });

  it("requires verification for unknown trust level", () => {
    const p = makeProvider({ trustLevel: "UNKNOWN" as TrustLevel, trustScore: 50, capabilities: ["weather.get"] });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("REQUIRE_VERIFICATION");
  });

  it("requires verification for low trust score", () => {
    const p = makeProvider({ trustLevel: "VERIFIED", trustScore: 10, capabilities: ["weather.get"] });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("REQUIRE_VERIFICATION");
    expect(result.reason).toContain("below minimum");
  });

  it("canAutoEnable returns true for ALLOW", () => {
    const p = makeProvider({ trustLevel: "VERIFIED", trustScore: 80, capabilities: ["weather.get"] });
    expect(pe.canAutoEnable(p)).toBe(true);
  });

  it("canAutoEnable returns false for DENY", () => {
    const p = makeProvider({ trustLevel: "BLOCKED" as TrustLevel });
    expect(pe.canAutoEnable(p)).toBe(false);
  });

  it("requiresVerification returns true for REQUIRE_VERIFICATION", () => {
    const p = makeProvider({ trustLevel: "UNKNOWN" as TrustLevel, trustScore: 50, capabilities: ["weather.get"] });
    expect(pe.requiresVerification(p)).toBe(true);
  });

  it("isSensitiveCapability checks list", () => {
    expect(pe.isSensitiveCapability("COMMUNICATION")).toBe(true);
    expect(pe.isSensitiveCapability("IOT")).toBe(true);
    expect(pe.isSensitiveCapability("WEATHER")).toBe(false);
  });

  it("isBlockedSource checks list", () => {
    pe.updatePolicy({ blockedSources: ["CUSTOM"] });
    expect(pe.isBlockedSource("CUSTOM")).toBe(true);
    expect(pe.isBlockedSource("DISCOVERED")).toBe(false);
  });

  it("getPolicy returns current policy", () => {
    const policy = pe.getPolicy();
    expect(policy.autoEnableReadOnly).toBe(true);
    expect(policy.sensitiveCapabilities).toContain("COMMUNICATION");
  });

  it("updatePolicy merges with defaults", () => {
    pe.updatePolicy({ minTrustScore: 50 });
    expect(pe.getPolicy().minTrustScore).toBe(50);
    expect(pe.getPolicy().denyPrivateIps).toBe(true); // default preserved
  });

  it("denies paid providers when maxPaidProviders is 0", () => {
    pe.updatePolicy({ maxPaidProviders: 0 });
    const p = makeProvider({
      trustLevel: "VERIFIED",
      trustScore: 80,
      capabilities: ["weather.get"],
      pricing: { free: false },
    });
    const result = pe.evaluate(p);
    expect(result.decision).toBe("DENY");
    expect(result.reason).toContain("Paid");
  });

  it("allows free providers even with maxPaidProviders 0", () => {
    pe.updatePolicy({ maxPaidProviders: 0 });
    const p = makeProvider({
      trustLevel: "VERIFIED",
      trustScore: 80,
      capabilities: ["weather.get"],
      pricing: { free: true },
    });
    expect(pe.evaluate(p).decision).toBe("ALLOW");
  });

  it("requires approval when requireManualApproval is true", () => {
    pe.updatePolicy({ requireManualApproval: true });
    const p = makeProvider({ trustLevel: "VERIFIED", trustScore: 80, capabilities: ["weather.get"] });
    expect(pe.evaluate(p).decision).toBe("REQUIRE_APPROVAL");
  });

  it("allows trusted provider with requireManualApproval", () => {
    pe.updatePolicy({ requireManualApproval: true, maxTrustForAutoEnable: "TRUSTED" });
    const p = makeProvider({ trustLevel: "TRUSTED" as TrustLevel, trustScore: 90, capabilities: ["weather.get"] });
    expect(pe.evaluate(p).decision).toBe("ALLOW");
  });
});
