import type { ServerContext } from "./types";

const TRADING_ENDPOINTS = [
  { path: "/api/trading/health", python: "/trading/health" },
  { path: "/api/trading/alerts", python: "/trading/alerts" },
  { path: "/api/groww/portfolio", python: "/groww/portfolio" },
  { path: "/api/groww/analyze", python: "/groww/analyze" },
];

export function registerTradingRoutes(app: any, ctx: ServerContext) {
  for (const ep of TRADING_ENDPOINTS) {
    app.get(ep.path, async (_req: any, res: any) => {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 10000);
        const r = await fetch(`${ctx.DESKTOP_AGENT_URL}${ep.python}`, { signal: ctrl.signal });
        clearTimeout(timer);
        if (r.ok) {
          res.json(await r.json());
        } else {
          res.json({ status: "UNAVAILABLE", error: `Python returned ${r.status}` });
        }
      } catch {
        res.json({ status: "UNAVAILABLE", error: "Python agent unreachable" });
      }
    });
  }

  app.get("/api/groww/stock/:symbol", async (req: any, res: any) => {
    try {
      const symbol = req.params.symbol;
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 10000);
      const r = await fetch(`${ctx.DESKTOP_AGENT_URL}/groww/stock/${encodeURIComponent(symbol)}`, { signal: ctrl.signal });
      clearTimeout(timer);
      if (r.ok) {
        res.json(await r.json());
      } else {
        res.json({ status: "UNAVAILABLE", error: `Python returned ${r.status}` });
      }
    } catch {
      res.json({ status: "UNAVAILABLE", error: "Python agent unreachable" });
    }
  });
}
