import { dataFile } from "../../server_paths";
import * as fs from "fs";
import type { ServerContext } from "./types";
import { callDesktopAgent } from "../../services/desktop/desktop_agent";
import { atomicWriteJsonFile } from "../../server_memory";

const SETTINGS_FILE = dataFile("settings.json");

function loadSettingsFile(): Record<string, unknown> {
  try {
    if (fs.existsSync(SETTINGS_FILE)) {
      return JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf-8"));
    }
  } catch { /* corrupt file — return defaults */ }
  return {};
}

/**
 * Persist settings via the same Windows-safe atomic writer used by the memory
 * and conversation stores (unique temp + fsync + bounded rename retry, `.bak`
 * of the previous good copy).
 *
 * A plain `fs.writeFileSync` here could leave a truncated settings.json if the
 * process died mid-write, and it could not survive a transient OneDrive/AV lock.
 *
 * Returns true only when the write actually landed — callers must NOT report
 * success otherwise.
 */
async function saveSettingsFile(data: Record<string, unknown>): Promise<boolean> {
  return atomicWriteJsonFile(SETTINGS_FILE, data);
}

export function registerSettingsRoutes(
  app: any,
  ctx: ServerContext,
) {
  app.get("/api/settings", async (_req: any, res: any) => {
    try {
      res.json(loadSettingsFile());
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  });

  app.post("/api/settings", async (req: any, res: any) => {
    try {
      const patch = req.body;
      if (!patch || typeof patch !== "object") {
        return res.status(400).json({ error: "Request body must be a JSON object." });
      }
      const current = loadSettingsFile();
      const next = { ...current, ...patch };
      const persisted = await saveSettingsFile(next);
      if (!persisted) {
        // Disk transiently locked (OneDrive/AV) — do NOT report a save that
        // did not happen; the previous settings.json is intact.
        ctx.logError("SETTINGS_SAVE_DEFERRED: settings.json transiently locked");
        return res.status(503).json({
          error: "Settings could not be written (file transiently locked). Try again.",
        });
      }

      if ("autoStart" in patch) {
        callDesktopAgent(patch.autoStart ? "enableAutoStart" : "disableAutoStart", {})
          .catch(() => {});
      }

      ctx.logCommand(`SETTINGS_UPDATED keys=${Object.keys(patch).join(",")}`);
      res.json(next);
    } catch (e: any) {
      ctx.logError(`SETTINGS_SAVE_ERROR: ${e.message}`);
      res.status(500).json({ error: e.message });
    }
  });
}
