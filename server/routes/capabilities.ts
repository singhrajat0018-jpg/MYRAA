// MYRAA Capability Routes — Node-side API for capability resolution
// Provides HTTP endpoints for Python brain to resolve and execute capabilities

import type { ServerContext } from "./types";
import { getCapabilityRuntime, initializeCapabilityRuntime } from "../../src/capabilities/runtime";
import type {
  CapabilityRequest,
  CapabilityResponse,
  Capability,
  Provider,
} from "../../src/capabilities/contracts";

// Lazy-initialized runtime
let runtimeReady: Promise<void> | null = null;

async function ensureRuntime() {
  if (!runtimeReady) {
    runtimeReady = initializeCapabilityRuntime().then(() => {});
  }
  return runtimeReady;
}

// ── Request validation ─────────────────────────────────────
const MAX_BODY_BYTES = 64 * 1024; // 64KB max request body

function validateRequestBody(req: any, res: any): boolean {
  const contentLength = parseInt(req.headers["content-length"] || "0", 10);
  if (contentLength > MAX_BODY_BYTES) {
    res.status(413).json({ error: "Request body too large" });
    return false;
  }
  return true;
}

function generateRequestId(): string {
  return `cap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function registerCapabilityRoutes(app: any, ctx: ServerContext) {
  const { logCommand, logError } = ctx;

  // ── Resolve: Given a capability request, return execution plan ──
  app.post("/api/capabilities/resolve", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const { capabilityId, input, priority, source } = req.body;

      if (!capabilityId) {
        return res.status(400).json({ error: "capabilityId required" });
      }

      const request: CapabilityRequest = {
        id: generateRequestId(),
        capabilityId,
        input: input || {},
        source: source || "SYSTEM",
        priority: priority || 5,
        fallbackAllowed: true,
        cachePolicy: "MEDIUM",
        timestamp: Date.now(),
      };

      const response = await runtime.execute(request);
      res.json(response);
    } catch (err) {
      logError(`[Capability Routes] resolve error: ${err}`);
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Execute: Resolve and execute in one call ──────────────────
  app.post("/api/capabilities/execute", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const { capabilityId, input, priority, source, cachePolicy } = req.body;

      if (!capabilityId) {
        return res.status(400).json({ error: "capabilityId required" });
      }

      const request: CapabilityRequest = {
        id: generateRequestId(),
        capabilityId,
        input: input || {},
        source: source || "SYSTEM",
        priority: priority || 5,
        fallbackAllowed: true,
        cachePolicy: cachePolicy || "MEDIUM",
        timestamp: Date.now(),
      };

      const response = await runtime.execute(request);
      logCommand(`[Capability] ${capabilityId} → ${response.providerId} (${response.success ? "ok" : "fail"}) ${response.latencyMs}ms`);
      res.json(response);
    } catch (err) {
      logError(`[Capability Routes] execute error: ${err}`);
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Plan: Multi-capability execution plan ─────────────────────
  app.post("/api/capabilities/plan", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const { intents } = req.body;

      if (!Array.isArray(intents) || intents.length === 0) {
        return res.status(400).json({ error: "intents array required" });
      }

      if (intents.length > 10) {
        return res.status(400).json({ error: "Maximum 10 intents per plan" });
      }

      const requestId = generateRequestId();
      const plan = runtime.planner.plan(requestId, intents);
      const executionPlan = runtime.planner.toExecutionPlan(plan);
      res.json({ plan, executionPlan });
    } catch (err) {
      logError(`[Capability Routes] plan error: ${err}`);
      res.status(500).json({ error: String(err) });
    }
  });

  // ── List capabilities ──────────────────────────────────────
  app.get("/api/capabilities", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const capabilities = runtime.registry.getCapabilities();
      res.json({ capabilities, count: capabilities.length });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── List providers ─────────────────────────────────────────
  app.get("/api/capabilities/providers", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const providers = runtime.registry.getProviders();
      res.json({ providers, count: providers.length });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Get providers for a capability ─────────────────────────
  app.get("/api/capabilities/:capabilityId/providers", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const providers = runtime.registry.findProvidersForCapability(req.params.capabilityId);
      res.json({ providers, count: providers.length });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Health check for a provider ────────────────────────────
  app.get("/api/capabilities/providers/:providerId/health", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const provider = runtime.registry.getProvider(req.params.providerId);
      if (!provider) {
        return res.status(404).json({ error: "Provider not found" });
      }
      const result = await runtime.verifier.healthCheck(provider);
      res.json(result);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Diagnostics ────────────────────────────────────────────
  app.get("/api/capabilities/diagnostics", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.getDiagnostics());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Metrics for a provider ─────────────────────────────────
  app.get("/api/capabilities/providers/:providerId/metrics", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const metrics = runtime.metrics.getProviderMetrics(req.params.providerId);
      res.json(metrics);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Circuit breaker states ─────────────────────────────────
  app.get("/api/capabilities/circuits", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.circuitBreaker.getAllStates());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Cache stats ────────────────────────────────────────────
  app.get("/api/capabilities/cache", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.cache.getStats());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Clear cache ────────────────────────────────────────────
  app.post("/api/capabilities/cache/clear", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      runtime.cache.clear();
      res.json({ ok: true });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Register a new provider (for dynamic registration) ─────
  app.post("/api/capabilities/providers", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const provider = req.body as Provider;
      if (!provider.id || !provider.name) {
        return res.status(400).json({ error: "id and name required" });
      }
      runtime.registry.registerProvider(provider);
      logCommand(`[Capability] Registered provider: ${provider.id}`);
      res.json({ ok: true, providerId: provider.id });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Register a new capability ──────────────────────────────
  app.post("/api/capabilities", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const cap = req.body as Capability;
      if (!cap.id || !cap.name) {
        return res.status(400).json({ error: "id and name required" });
      }
      runtime.registry.registerCapability(cap);
      logCommand(`[Capability] Registered capability: ${cap.id}`);
      res.json({ ok: true, capabilityId: cap.id });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Refresh provider health ────────────────────────────────
  app.post("/api/capabilities/health/refresh", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const providers = runtime.registry.getProviders({ enabled: true });
      const results = [];
      for (const provider of providers) {
        if (provider.baseUrl) {
          const result = await runtime.verifier.healthCheck(provider);
          runtime.registry.updateProviderHealth(provider.id, result.status);
          results.push(result);
        }
      }
      res.json({ checked: results.length, results });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Promote provider trust level ───────────────────────────
  app.post("/api/capabilities/providers/:providerId/trust", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const { trustLevel, trustScore } = req.body;
      runtime.registry.updateProviderTrust(req.params.providerId, trustLevel, trustScore);
      res.json({ ok: true });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Force persist ──────────────────────────────────────────
  app.post("/api/capabilities/persist", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      runtime.flush();
      res.json({ ok: true });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ══════════════════════════════════════════════════════════════
  // Phase 19C — Marketplace, Lifecycle, Reputation, Audit
  // ══════════════════════════════════════════════════════════════

  // ── Marketplace: search capabilities ────────────────────────
  app.get("/api/capabilities/marketplace/search", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const filter = {
        query: req.query.q as string,
        category: req.query.category as string,
        minTrust: req.query.minTrust ? parseInt(req.query.minTrust as string, 10) : undefined,
        limit: req.query.limit ? parseInt(req.query.limit as string, 10) : 50,
        offset: req.query.offset ? parseInt(req.query.offset as string, 10) : 0,
      };
      const results = runtime.marketplace.search(filter);
      res.json({ listings: results, count: results.length });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Marketplace: get listing ────────────────────────────────
  app.get("/api/capabilities/marketplace/:capabilityId", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const listing = runtime.marketplace.getListing(req.params.capabilityId);
      if (!listing) return res.status(404).json({ error: "Listing not found" });
      res.json(listing);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Marketplace: stats ─────────────────────────────────────
  app.get("/api/capabilities/marketplace/stats", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.marketplace.getStats());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Marketplace: categories ─────────────────────────────────
  app.get("/api/capabilities/marketplace/categories", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.marketplace.getCategories());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Marketplace: needs attention ────────────────────────────
  app.get("/api/capabilities/marketplace/attention", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.marketplace.getCapabilitiesNeedingAttention());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Lifecycle: get provider state ───────────────────────────
  app.get("/api/capabilities/lifecycle/:providerId", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const state = runtime.lifecycle.getState(req.params.providerId);
      const history = runtime.lifecycle.getHistory(req.params.providerId, 20);
      res.json({ state, history });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Lifecycle: transition provider ──────────────────────────
  app.post("/api/capabilities/lifecycle/:providerId/transition", async (req: any, res: any) => {
    try {
      if (!validateRequestBody(req, res)) return;
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const { to, reason, actor } = req.body;
      if (!to || !reason) return res.status(400).json({ error: "to and reason required" });

      const can = runtime.lifecycle.canTransition(req.params.providerId, to);
      if (!can) return res.status(400).json({ error: `Cannot transition to ${to}` });

      const event = runtime.lifecycle.transition(req.params.providerId, to, reason, actor || "ADMIN");
      runtime.audit.record({
        providerId: req.params.providerId,
        operation: "LIFECYCLE_TRANSITION",
        oldState: { state: event.from },
        newState: { state: event.to },
        reason,
        actor: actor || "ADMIN",
      });
      res.json({ ok: true, event });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Lifecycle: stats ────────────────────────────────────────
  app.get("/api/capabilities/lifecycle/stats", async (_req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      res.json(runtime.lifecycle.getStats());
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Reputation: get provider score ──────────────────────────
  app.get("/api/capabilities/reputation/:providerId", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const score = runtime.reputation.getScore(req.params.providerId);
      const explanation = runtime.reputation.getExplanation(req.params.providerId);
      res.json({ score, explanation });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Reputation: top providers ───────────────────────────────
  app.get("/api/capabilities/reputation/top", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 10;
      res.json(runtime.reputation.getTopProviders(limit));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Audit: recent events ───────────────────────────────────
  app.get("/api/capabilities/audit", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 50;
      res.json(runtime.audit.getRecent(limit));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Audit: events for provider ──────────────────────────────
  app.get("/api/capabilities/audit/:providerId", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : 50;
      res.json(runtime.audit.getByProvider(req.params.providerId, limit));
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  // ── Capability health ──────────────────────────────────────
  app.get("/api/capabilities/:capabilityId/health", async (req: any, res: any) => {
    try {
      await ensureRuntime();
      const runtime = getCapabilityRuntime();
      const health = runtime.marketplace.getCapabilityHealth(req.params.capabilityId);
      res.json(health);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });
}
