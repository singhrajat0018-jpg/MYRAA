import { DESKTOP_AGENT_URL } from "../../services/desktop/desktop_agent";
import { nodeTelemetryRelay } from "../../services/telemetry/telemetry_relay";
import { getVoiceHealthSnapshot } from "../../server_voice";
import { getConversationPersistenceHealth } from "../../server_conversations";
import { getMemoryPersistenceHealth } from "../../server_memory";
import type { ServerContext } from "./types";

export function registerSystemRoutes(app: any, _ctx: ServerContext) {
  // §18: read-only voice health snapshot — Node transport + Python session.
  app.get("/api/voice/health", async (_req: any, res: any) => {
    const node = getVoiceHealthSnapshot();
    let python: any = null;
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3000);
      const r = await fetch(`${DESKTOP_AGENT_URL}/voice/gemini/health`, { signal: ctrl.signal });
      clearTimeout(timer);
      if (r.ok) python = await r.json();
    } catch (e: any) {
      python = { error: e?.message || "python unreachable" };
    }
    res.json({
      provider: "gemini_live",
      node,
      python: python?.voice ?? python,
      read_only: true,
    });
  });

  app.get("/api/agent-health", async (_req: any, res: any) => {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3000);
      const r = await fetch(`${DESKTOP_AGENT_URL}/health/live`, { signal: ctrl.signal });
      clearTimeout(timer);
      if (!r.ok) {
        res.json({ online: false });
        return;
      }
      let tool_count: number | undefined;
      try {
        const ctrl2 = new AbortController();
        const timer2 = setTimeout(() => ctrl2.abort(), 3000);
        const d = await fetch(`${DESKTOP_AGENT_URL}/health`, { signal: ctrl2.signal });
        clearTimeout(timer2);
        if (d.ok) tool_count = (await d.json()).tool_count;
      } catch { /* detail report optional */ }
      res.json({ online: true, tool_count });
    } catch {
      res.json({ online: false });
    }
  });

  app.get("/api/telemetry/stream", async (req: any, res: any) => {
    try {
      const count = Math.min(parseInt(req.query.count as string) || 50, 200);
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 3000);
      const r = await fetch(`${DESKTOP_AGENT_URL}/telemetry/stream?count=${count}`, { signal: ctrl.signal });
      clearTimeout(timer);
      if (r.ok) {
        res.json(await r.json());
      } else {
        res.json({ events: [], count: 0 });
      }
    } catch {
      res.json({ events: [], count: 0 });
    }
  });

  app.get("/api/telemetry/status", async (_req: any, res: any) => {
    res.json(nodeTelemetryRelay.status());
  });

  // Truthful persistence health: HEALTHY / DEGRADED / RECOVERING.
  // Read-only; never exposes file contents. Covers the Windows/OneDrive
  // atomic-write layer for conversations + Node memory stores.
  app.get("/api/persistence/health", (_req: any, res: any) => {
    try {
      const conversations = getConversationPersistenceHealth();
      const memory = getMemoryPersistenceHealth();
      const degraded = conversations.status === "DEGRADED" || memory.status === "DEGRADED";
      const recovering =
        degraded &&
        (conversations.pendingWrites > 0 || memory.pendingWrites > 0);
      res.json({
        status: degraded ? (recovering ? "RECOVERING" : "PERSISTENCE_DEGRADED") : "HEALTHY",
        conversations,
        memory,
      });
    } catch (e: any) {
      res.status(500).json({ error: e?.message ?? "health unavailable" });
    }
  });
}
