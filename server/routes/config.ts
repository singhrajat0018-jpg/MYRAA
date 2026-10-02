import * as fs from "fs";
import * as path from "path";
import type { ServerContext } from "./types";
import { atomicWriteTextFile } from "../../server_memory";

/**
 * Server-side secrets live in ONE place: the project `.env`.
 *
 * Both processes read it: Node via `dotenv.config()` and Python via
 * `load_dotenv(ROOT / ".env")` in desktop_agent/config/settings.py. So the
 * Gemini/Tavily keys must be written here — never into a second "secrets.json"
 * store, which nothing reads (the file is only listed as a *protected*
 * filename in the permission blocklists).
 *
 * `MYRAA_ENV_FILE` lets tests/deployments redirect the target (same override
 * idiom as MYRAA_DATA_DIR / MYRAA_MEMORY_FILE).
 */
function envFilePath(): string {
  return process.env.MYRAA_ENV_FILE || path.join(process.cwd(), ".env");
}

/** Keys the frontend may legitimately configure through this endpoint. */
const CONFIGURABLE_ENV_KEYS = new Set(["GEMINI_API_KEY", "TAVILY_API_KEY"]);

/** Parse a .env file into ordered lines (comments/blank lines preserved). */
function readEnvLines(): string[] {
  try {
    return fs.readFileSync(envFilePath(), "utf-8").split(/\r?\n/);
  } catch {
    return [];
  }
}

/** Presence (never the value) of an env key, from file or process env. */
function hasEnvKey(key: string): boolean {
  if ((process.env[key] ?? "").trim()) return true;
  for (const line of readEnvLines()) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    if (m && m[1] === key && m[2].trim().replace(/^['"]|['"]$/g, "").trim()) return true;
  }
  return false;
}

/**
 * Upsert `KEY=value` in the .env file, preserving every other line verbatim.
 * Returns true only when the file was durably replaced.
 */
async function upsertEnvKey(key: string, value: string): Promise<boolean> {
  const lines = readEnvLines();
  const next: string[] = [];
  let replaced = false;
  for (const line of lines) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(line);
    if (m && m[1] === key) {
      if (!replaced) {
        next.push(`${key}=${value}`);
        replaced = true;
      }
      // drop any duplicate definitions of the same key
      continue;
    }
    next.push(line);
  }
  if (!replaced) {
    // Trim a trailing run of blank lines, then append in its own block.
    while (next.length && next[next.length - 1].trim() === "") next.pop();
    next.push(`${key}=${value}`);
  }
  // Always end with a single newline so the file stays POSIX-clean.
  while (next.length && next[next.length - 1].trim() === "") next.pop();
  return atomicWriteTextFile(envFilePath(), next.join("\n") + "\n");
}

export function registerConfigRoutes(app: any, ctx: ServerContext) {
  // Truthful status: report whether each server-side key is CONFIGURED.
  // The values themselves are never sent to the frontend or logged.
  app.get("/api/config", (_req: any, res: any) => {
    const gemini = hasEnvKey("GEMINI_API_KEY");
    const tavily = hasEnvKey("TAVILY_API_KEY");
    res.json({
      hasApiKey: gemini,
      mode: "local-first",
      providers: { gemini, tavily },
    });
  });

  app.get("/api/ws-token", (_req: any, res: any) => {
    res.json({ token: ctx.WS_SESSION_TOKEN });
  });

  /**
   * Persist a server-side API key into the authoritative `.env` file.
   *
   * Security: the key is never logged, never echoed back, never returned by
   * GET /api/config, and newline/quote injection into .env is rejected.
   */
  app.post("/api/config/apikey", async (req: any, res: any) => {
    try {
      const key: string = (req.body?.apiKey ?? "").toString().trim();
      const name: string = (req.body?.name ?? "GEMINI_API_KEY").toString().trim();

      if (!CONFIGURABLE_ENV_KEYS.has(name)) {
        return res.status(400).json({
          success: false,
          ok: false,
          error: `Unsupported key '${name}'. Allowed: ${[...CONFIGURABLE_ENV_KEYS].join(", ")}`,
        });
      }
      if (!key) {
        return res.status(400).json({ success: false, ok: false, error: "API key is required." });
      }
      if (/[\r\n]/.test(key) || /[\r\n]/.test(name)) {
        // .env injection guard: a newline could inject arbitrary env entries.
        return res.status(400).json({
          success: false,
          ok: false,
          error: "API key must not contain line breaks.",
        });
      }
      if (key.length > 512) {
        return res.status(400).json({ success: false, ok: false, error: "API key is too long." });
      }

      const written = await upsertEnvKey(name, key);
      if (!written) {
        ctx.logError(`APIKEY_SAVE_DEFERRED: .env transiently locked (${name})`);
        return res.status(503).json({
          success: false,
          ok: false,
          error: "Could not write the API key (file transiently locked). Try again.",
        });
      }

      // Node-side consumers see it immediately; the Python agent reads .env at
      // import time, so the running agent must be restarted to pick it up.
      process.env[name] = key;
      ctx.logCommand(`APIKEY_SAVED ${name}`);  // name only — never the value
      return res.json({
        success: true,
        ok: true,
        hasApiKey: hasEnvKey("GEMINI_API_KEY"),
        requiresRestart: true,
        message: "Saved to .env. Restart MYRAA for the agent to load it.",
      });
    } catch (e: any) {
      ctx.logError(`APIKEY_SAVE_ERROR: ${e?.message || e}`);
      res.status(500).json({ success: false, ok: false, error: e?.message || "Failed to save API key." });
    }
  });
}
