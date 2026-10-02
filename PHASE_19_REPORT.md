# Phase 19 — Universal Intelligence & Capability Expansion Layer

## Summary

Built the complete capability engine for MYRAA — a discovery-to-execution infrastructure
that discovers, verifies, ranks, and executes across broad external information/service
providers. Public-apis directory serves as the discovery source. The engine is domain-agnostic,
provider-agnostic, and safety-first with SSRF protection, circuit breakers, and trust scoring.

## Verification

- **TypeScript:** `tsc --noEmit` — clean
- **Tests:** 826/826 pass (731 existing + 95 new capability engine tests)
- **Build:** 6.33s, successful

---

## Architecture

```
User Intent
  ↓
CapabilityRouter
  ├── CapabilityPlanner (multi-capability decomposition)
  ├── FallbackManager (provider failover chain)
  │     ├── ProviderRanker (trust × reliability × latency scoring)
  │     ├── ExecutionEngine (secure HTTP with retry/timeout)
  │     │     ├── SecurityGuard (SSRF protection)
  │     │     ├── AuthManager (API key/bearer/query auth)
  │     │     └── CircuitBreaker (failure detection + recovery)
  │     ├── ResponseCache (LRU with TTL per cache policy)
  │     ├── ResponseNormalizer (unified shape normalization)
  │     └── ProvenanceTracker (data lineage + trust chain)
  ├── ResponseMerger (multi-provider result merging)
  └── MetricsCollector (per-provider/capability metrics)
```

## Files Created (16 new files)

| File | Lines | Purpose |
|------|-------|---------|
| `src/capabilities/contracts.ts` | ~340 | Typed contracts: Capability, Provider, Request, Response, Errors, Events, etc. |
| `src/capabilities/registry.ts` | ~310 | Universal capability + provider registry with event emission |
| `src/capabilities/discovery.ts` | ~220 | public-apis directory API adapter with category mapping |
| `src/capabilities/verification.ts` | ~230 | Provider endpoint verification + health monitoring |
| `src/capabilities/ranking.ts` | ~140 | Composite scoring: trust × reliability × latency × freshness |
| `src/capabilities/execution.ts` | ~300 | Secure generic HTTP execution with retry, timeout, circuit breaker |
| `src/capabilities/security.ts` | ~290 | SSRF protection, auth management, circuit breaker |
| `src/capabilities/cache.ts` | ~170 | LRU cache with TTL and size limits |
| `src/capabilities/fallback.ts` | ~130 | Health-aware provider fallback chains |
| `src/capabilities/normalization.ts` | ~200 | Response normalization for weather, search, finance formats |
| `src/capabilities/provenance.ts` | ~100 | Data lineage tracking |
| `src/capabilities/router.ts` | ~160 | Capability request routing |
| `src/capabilities/planner.ts` | ~170 | Multi-capability execution planning with dependency resolution |
| `src/capabilities/merge.ts` | ~160 | Multi-provider response merging (best/merge/consensus) |
| `src/capabilities/metrics.ts` | ~130 | Request/latency/cache metrics collection |
| `src/capabilities/serialization.ts` | ~90 | Snapshot persistence with checksum verification |
| `src/capabilities/index.ts` | ~160 | Public API + `createCapabilityEngine()` factory |

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/capability_engine.test.ts` | 95 | Registry, Security, Circuit Breaker, Cache, Auth, Ranking, Normalization, Merge, Provenance, Metrics, Serialization, Planner, Discovery, Verifier, Engine Factory |

## Key Design Decisions

1. **public-apis as discovery source, not execution authority.** CATALOG ENTRY ≠ TRUSTED PROVIDER.
   Every discovered provider goes through verification → trust scoring → enabled/disabled lifecycle.

2. **SSRF protection is mandatory.** All external URLs validated against private IPs, metadata
   endpoints, non-standard ports, and URL credentials before any fetch.

3. **Circuit breaker per provider.** Opens after 5 consecutive failures, recovers after 60s
   into half-open state. Prevents cascading failures.

4. **Native capability first.** Existing 87+ tools are LOCAL_TOOL category. New external APIs
   are discovered and added through the registry, not replacing native tools.

5. **Response normalization is extensible.** Register rules per capability+provider. Built-in
   normalizers for weather (Open-Meteo), search (Tavily), and finance formats.

6. **Consensus merging for multi-provider queries.** When 3+ providers return results, only
   values appearing in majority are included — prevents outlier contamination.

7. **Fully-wired factory.** `createCapabilityEngine()` returns all 15 sub-components wired
   together with default configs. Single entry point, no manual wiring needed.

## Compatibility

- All 731 existing tests continue passing
- No modifications to any existing module
- New `src/capabilities/` directory is self-contained
- Engine is independent of DesignCore, Geometry, Assembly, Brain
- Can be wired into Node server, Python agent, or React frontend independently

## What's NOT Done (Future Work)

- **Wiring into server.py / Node server** — Engine exists as standalone TypeScript module
- **Browser-based provider discovery** — Only HTTP API discovery implemented
- **OAuth2 flow** — AuthManager handles API keys but not OAuth2 token refresh
- **Rate limiter enforcement** — RateLimit metadata is tracked but not enforced client-side
- **Persistent storage** — All metrics/cache/provenance are in-memory only
- **Real provider verification runs** — Tests use mock/stub providers
- **Integration with existing Python tools** — The 87 desktop tools are not yet wrapped as providers
