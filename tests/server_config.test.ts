import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import fs from "fs";
import path from "path";
import os from "os";

/**
 * Regression tests for the config + settings routes:
 *
 *  - GET /api/config must report TRUTHFUL provider status (never hardcoded
 *    hasApiKey: true).
 *  - POST /api/config/apikey must actually PERSIST the key to the
 *    authoritative .env file (the historical no-op silently accepted keys and
 *    stored nothing). The value is never echoed back and .env injection is
 *    rejected.
 *  - POST /api/settings must persist atomically (same Windows-safe writer as
 *    the memory/conversation stores) and must NOT report success when the
 *    write did not land.
 */

const TEST_DIR = path.join(os.tmpdir(), `myraa-cfg-test-${Date.now()}`);
const ENV_FILE = path.join(TEST_DIR, ".env");

vi.mock("../server_paths", () => ({
  DATA_DIR: TEST_DIR,
  dataFile: (name: string) => path.join(TEST_DIR, name),
}));

// Avoid any real network call from the settings route.
vi.mock("../services/desktop/desktop_agent", () => ({
  callDesktopAgent: vi.fn(async () => ({})),
}));

type Handler = (req: any, res: any) => any;

/** Minimal express capture: records handlers so tests can invoke them. */
function makeApp() {
  const routes = new Map<string, Handler>();
  return {
    routes,
    get(r: string, h: Handler) { routes.set(`GET ${r}`, h); },
    post(r: string, h: Handler) { routes.set(`POST ${r}`, h); },
  };
}

function makeRes() {
  const res: any = {
    statusCode: 200,
    body: undefined as any,
    status(code: number) { res.statusCode = code; return res; },
    json(payload: any) { res.body = payload; return res; },
  };
  return res;
}

let configMod: typeof import("../server/routes/config");
let settingsMod: typeof import("../server/routes/settings");
let memoryMod: typeof import("../server_memory");

const ctx = {
  WS_SESSION_TOKEN: "test-token",
  logError: (m: string) => { void m; },
  logCommand: (m: string) => { void m; },
} as any;

beforeEach(async () => {
  fs.mkdirSync(TEST_DIR, { recursive: true });
  // Start each test with a known .env containing unrelated lines.
  fs.writeFileSync(
    ENV_FILE,
    "# myraa env\nDESKTOP_AGENT_URL=http://127.0.0.1:8765\nOTHER_KEY=keep_me\n",
    "utf-8",
  );
  process.env.MYRAA_ENV_FILE = ENV_FILE;
  delete process.env.GEMINI_API_KEY;
  delete process.env.TAVILY_API_KEY;
  // Dynamic import AFTER mocks + env are in place.
  configMod = await import("../server/routes/config");
  settingsMod = await import("../server/routes/settings");
  memoryMod = await import("../server_memory");
});

afterEach(() => {
  delete process.env.MYRAA_ENV_FILE;
  delete process.env.GEMINI_API_KEY;
  delete process.env.TAVILY_API_KEY;
  fs.rmSync(TEST_DIR, { recursive: true, force: true });
  vi.resetModules();
});

describe("GET /api/config — truthful status", () => {
  it("reports both providers unconfigured when no keys exist", () => {
    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res = makeRes();
    app.routes.get("GET /api/config")!({} as any, res);
    expect(res.body.hasApiKey).toBe(false);
    expect(res.body.providers).toEqual({ gemini: false, tavily: false });
  });

  it("reports gemini configured when the .env contains a key", () => {
    fs.appendFileSync(ENV_FILE, "GEMINI_API_KEY=test-key-value\n", "utf-8");
    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res = makeRes();
    app.routes.get("GET /api/config")!({} as any, res);
    expect(res.body.hasApiKey).toBe(true);
    expect(res.body.providers.gemini).toBe(true);
    expect(res.body.providers.tavily).toBe(false);
    // The value must NEVER appear in the status response.
    expect(JSON.stringify(res.body)).not.toContain("test-key-value");
  });
});


describe("POST /api/config/apikey — real persistence", () => {
  it("persists the key into .env, preserving unrelated lines", async () => {
    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res = makeRes();
    await app.routes.get("POST /api/config/apikey")!(
      { body: { apiKey: "sk-gemini-123" } },
      res,
    );
    expect(res.statusCode).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.requiresRestart).toBe(true);

    const envText = fs.readFileSync(ENV_FILE, "utf-8");
    expect(envText).toContain("GEMINI_API_KEY=sk-gemini-123");
    expect(envText).toContain("OTHER_KEY=keep_me"); // untouched
    expect(envText).toContain("DESKTOP_AGENT_URL=http://127.0.0.1:8765");
    // Atomic write leaves no temp residue.
    expect(fs.readdirSync(TEST_DIR).filter((f) => f.includes(".tmp"))).toEqual([]);
  });

  it("replaces an existing key and collapses duplicates", async () => {
    fs.appendFileSync(ENV_FILE, "GEMINI_API_KEY=old-key\nGEMINI_API_KEY=older-key\n", "utf-8");
    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res = makeRes();
    await app.routes.get("POST /api/config/apikey")!(
      { body: { apiKey: "new-key" } },
      res,
    );
    expect(res.statusCode).toBe(200);
    const envText = fs.readFileSync(ENV_FILE, "utf-8");
    expect(envText).toContain("GEMINI_API_KEY=new-key");
    expect(envText).not.toContain("old-key");
    expect(envText.match(/GEMINI_API_KEY=/g)!.length).toBe(1);
  });

  it("rejects .env injection via newline", async () => {
    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res = makeRes();
    await app.routes.get("POST /api/config/apikey")!(
      { body: { apiKey: "abc\nEVIL_KEY=1" } },
      res,
    );
    expect(res.statusCode).toBe(400);
    expect(fs.readFileSync(ENV_FILE, "utf-8")).not.toContain("EVIL_KEY");
  });

  it("rejects unsupported key names and empty keys", async () => {
    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res1 = makeRes();
    await app.routes.get("POST /api/config/apikey")!(
      { body: { apiKey: "x", name: "ARBITRARY_KEY" } },
      res1,
    );
    expect(res1.statusCode).toBe(400);

    const res2 = makeRes();
    await app.routes.get("POST /api/config/apikey")!(
      { body: { apiKey: "   " } },
      res2,
    );
    expect(res2.statusCode).toBe(400);
  });

  it("does not claim success when the write did not land", async () => {
    // Force the atomic writer to fail by pointing the .env path at a directory.
    const badDir = path.join(TEST_DIR, "not-a-file");
    fs.mkdirSync(badDir, { recursive: true });
    process.env.MYRAA_ENV_FILE = badDir;

    const app = makeApp();
    configMod.registerConfigRoutes(app as any, ctx);
    const res = makeRes();
    await app.routes.get("POST /api/config/apikey")!(
      { body: { apiKey: "sk-x" } },
      res,
    );
    expect([500, 503]).toContain(res.statusCode);
    expect(res.body.success).toBe(false);
  });
});

describe("POST /api/settings — atomic persistence", () => {
  it("merges the patch, persists it, and returns the merged object", async () => {
    const app = makeApp();
    settingsMod.registerSettingsRoutes(app as any, ctx);
    const res = makeRes();
    await app.routes.get("POST /api/settings")!(
      { body: { theme: "dark", voiceEnabled: true } },
      res,
    );
    expect(res.statusCode).toBe(200);
    expect(res.body).toMatchObject({ theme: "dark", voiceEnabled: true });

    // A second request must see the persisted value (merge-on-read).
    const res2 = makeRes();
    await app.routes.get("POST /api/settings")!({ body: { volume: 42 } }, res2);
    expect(res2.body.theme).toBe("dark");
    expect(res2.body.volume).toBe(42);

    expect(JSON.parse(fs.readFileSync(path.join(TEST_DIR, "settings.json"), "utf-8")))
      .toMatchObject({ theme: "dark", voiceEnabled: true, volume: 42 });
  });

  it("rejects non-object bodies", async () => {
    const app = makeApp();
    settingsMod.registerSettingsRoutes(app as any, ctx);
    const res = makeRes();
    await app.routes.get("POST /api/settings")!({ body: "nope" }, res);
    expect(res.statusCode).toBe(400);
  });

  it("reports 503/500 — not success — when settings.json cannot be written", async () => {
    const app = makeApp();
    settingsMod.registerSettingsRoutes(app as any, ctx);
    // Corrupt the target into a directory so atomicWriteJsonFile fails.
    fs.mkdirSync(path.join(TEST_DIR, "settings.json"), { recursive: true });
    const res = makeRes();
    await app.routes.get("POST /api/settings")!({ body: { theme: "dark" } }, res);
    expect([500, 503]).toContain(res.statusCode);
    expect(res.body.error).toBeTruthy();
  });
});

describe("atomic write helpers", () => {
  it("atomicWriteTextFile lands content and returns true", async () => {
    const target = path.join(TEST_DIR, "helper.txt");
    const ok = await memoryMod.atomicWriteTextFile(target, "hello");
    expect(ok).toBe(true);
    expect(fs.readFileSync(target, "utf-8")).toBe("hello");
  });

  it("atomicWriteJsonFile serializes and returns true", async () => {
    const target = path.join(TEST_DIR, "helper.json");
    const ok = await memoryMod.atomicWriteJsonFile(target, { a: 1 });
    expect(ok).toBe(true);
    expect(JSON.parse(fs.readFileSync(target, "utf-8"))).toEqual({ a: 1 });
  });
});

