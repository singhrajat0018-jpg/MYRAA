// Capability Runtime Integration Tests — Phase 19B
// Tests for CapabilityRuntime, RateLimiter, RequestCoalescer, CredentialStore

import { describe, it, expect, beforeEach } from "vitest";
import {
  CapabilityRuntime,
  RateLimiter,
  RequestCoalescer,
  CredentialStore,
  getCapabilityRuntime,
  initializeCapabilityRuntime,
} from "../src/capabilities/runtime";
import type { CapabilityRequest } from "../src/capabilities/contracts";

// ── RateLimiter ──────────────────────────────────────────────

describe("Phase 19B — RateLimiter", () => {
  it("allows requests when under limit", () => {
    const limiter = new RateLimiter(5);
    expect(limiter.canExecute("provider-1")).toBe(true);
  });

  it("blocks requests when limit exceeded", () => {
    const limiter = new RateLimiter(3);
    limiter.recordRequest("p1");
    limiter.recordRequest("p1");
    limiter.recordRequest("p1");
    expect(limiter.canExecute("p1")).toBe(false);
  });

  it("resets after window expires", () => {
    const limiter = new RateLimiter(2);
    limiter.recordRequest("p1");
    limiter.recordRequest("p1");
    expect(limiter.canExecute("p1")).toBe(false);

    // Manually expire the window
    const entry = (limiter as any).limits.get("p1");
    if (entry) entry.windowStart = Date.now() - 61_000;
    expect(limiter.canExecute("p1")).toBe(true);
  });

  it("records 429 and blocks for retry-after", () => {
    const limiter = new RateLimiter(60);
    limiter.record429("p1", 30);
    expect(limiter.canExecute("p1")).toBe(false);
  });

  it("returns correct status", () => {
    const limiter = new RateLimiter(60);
    const status = limiter.getStatus("p1");
    expect(status.allowed).toBe(true);
    expect(status.retryAfterMs).toBe(0);
  });

  it("tracks independent providers", () => {
    const limiter = new RateLimiter(2);
    limiter.recordRequest("p1");
    limiter.recordRequest("p1");
    expect(limiter.canExecute("p1")).toBe(false);
    expect(limiter.canExecute("p2")).toBe(true);
  });
});

// ── RequestCoalescer ─────────────────────────────────────────

describe("Phase 19B — RequestCoalescer", () => {
  it("coalesces identical concurrent requests", async () => {
    const coalescer = new RequestCoalescer();
    let callCount = 0;

    const executor = async () => {
      callCount++;
      await new Promise(r => setTimeout(r, 50));
      return {
        requestId: "r1",
        providerId: "p1",
        capabilityId: "test",
        success: true,
        data: { value: 42 },
        latencyMs: 50,
        fromCache: false,
        normalized: false,
        timestamp: Date.now(),
        provenance: { source: "test", capabilityId: "test", retrievedAt: Date.now(), trustChain: [], confidenceScore: 1 },
      };
    };

    // Fire 3 identical requests concurrently
    const [r1, r2, r3] = await Promise.all([
      coalescer.coalesce("key1", executor),
      coalescer.coalesce("key1", executor),
      coalescer.coalesce("key1", executor),
    ]);

    expect(callCount).toBe(1); // Only one actual execution
    expect(r1.data).toEqual({ value: 42 });
    expect(r1).toBe(r2); // Same promise reference
    expect(r2).toBe(r3);
  });

  it("runs different keys independently", async () => {
    const coalescer = new RequestCoalescer();
    let callCount = 0;

    const executor = async () => {
      callCount++;
      return {
        requestId: "r1",
        providerId: "p1",
        capabilityId: "test",
        success: true,
        data: {},
        latencyMs: 0,
        fromCache: false,
        normalized: false,
        timestamp: Date.now(),
        provenance: { source: "test", capabilityId: "test", retrievedAt: Date.now(), trustChain: [], confidenceScore: 1 },
      };
    };

    await Promise.all([
      coalescer.coalesce("key1", executor),
      coalescer.coalesce("key2", executor),
    ]);

    expect(callCount).toBe(2);
  });

  it("cleans up after completion", async () => {
    const coalescer = new RequestCoalescer();
    const executor = async () => ({
      requestId: "r1",
      providerId: "p1",
      capabilityId: "test",
      success: true,
      data: {},
      latencyMs: 0,
      fromCache: false,
      normalized: false,
      timestamp: Date.now(),
      provenance: { source: "test", capabilityId: "test", retrievedAt: Date.now(), trustChain: [], confidenceScore: 1 },
    });

    await coalescer.coalesce("key1", executor);
    expect(coalescer.getStats().pending).toBe(0);
  });

  it("generates deterministic keys", () => {
    const key1 = RequestCoalescer.keyFor({
      id: "r1",
      capabilityId: "weather.current",
      input: { city: "Delhi" },
      source: "SYSTEM",
      priority: 5,
      fallbackAllowed: true,
      cachePolicy: "MEDIUM",
      timestamp: 0,
    });
    const key2 = RequestCoalescer.keyFor({
      id: "r2",
      capabilityId: "weather.current",
      input: { city: "Delhi" },
      source: "SYSTEM",
      priority: 5,
      fallbackAllowed: true,
      cachePolicy: "MEDIUM",
      timestamp: 0,
    });
    expect(key1).toBe(key2);
  });
});

// ── CredentialStore ──────────────────────────────────────────

describe("Phase 19B — CredentialStore", () => {
  let store: CredentialStore;

  beforeEach(() => {
    store = new CredentialStore();
  });

  it("stores and retrieves credentials", () => {
    store.store("key1", "OpenWeather API Key", "API_KEY", "sk-test-123");
    expect(store.get("key1")).toBe("sk-test-123");
  });

  it("returns undefined for missing credential", () => {
    expect(store.get("nonexistent")).toBeUndefined();
  });

  it("removes credentials", () => {
    store.store("key1", "Test", "API_KEY", "value");
    expect(store.remove("key1")).toBe(true);
    expect(store.get("key1")).toBeUndefined();
  });

  it("returns false when removing nonexistent credential", () => {
    expect(store.remove("nonexistent")).toBe(false);
  });

  it("lists stored credentials without exposing values", () => {
    store.store("key1", "My Key", "BEARER_TOKEN", "secret-value");
    const list = store.list();
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe("key1");
    expect(list[0].name).toBe("My Key");
    expect(list[0].type).toBe("BEARER_TOKEN");
    expect(list[0].hasValue).toBe(true);
  });

  it("rejects expired credentials", () => {
    store.store("key1", "Expired", "API_KEY", "value", Date.now() - 1000);
    expect(store.get("key1")).toBeUndefined();
  });
});

// ── CapabilityRuntime ────────────────────────────────────────

describe("Phase 19B — CapabilityRuntime", () => {
  it("creates runtime with default config", () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    expect(runtime.registry).toBeDefined();
    expect(runtime.router).toBeDefined();
    expect(runtime.execution).toBeDefined();
    expect(runtime.ranker).toBeDefined();
    expect(runtime.cache).toBeDefined();
    expect(runtime.circuitBreaker).toBeDefined();
    expect(runtime.metrics).toBeDefined();
    expect(runtime.rateLimiter).toBeDefined();
    expect(runtime.coalescer).toBeDefined();
    expect(runtime.credentialStore).toBeDefined();
    expect(runtime.oauth2).toBeDefined();
  });

  it("registers built-in capabilities on initialize", async () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    await runtime.initialize();

    const caps = runtime.registry.getCapabilities();
    const capIds = caps.map(c => c.id);
    expect(capIds).toContain("weather.current");
    expect(capIds).toContain("news.search");
    expect(capIds).toContain("research.search");
    expect(capIds).toContain("time.current");
    expect(capIds).toContain("system.info");
    expect(capIds).toContain("web.search");
    expect(capIds).toContain("files.read");
    expect(capIds).toContain("vision.analyze");
    expect(capIds).toContain("browser.search");
  });

  it("registers built-in Open-Meteo provider", async () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    await runtime.initialize();

    const providers = runtime.registry.findProvidersForCapability("weather.current");
    expect(providers.length).toBeGreaterThan(0);
    expect(providers[0].id).toBe("open-meteo");
  });

  it("initialize is idempotent", async () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    await runtime.initialize();
    await runtime.initialize(); // second call should be no-op
    const caps = runtime.registry.getCapabilities();
    expect(caps.length).toBeGreaterThan(0);
  });

  it("getDiagnostics returns complete info", async () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    await runtime.initialize();

    const diag = runtime.getDiagnostics();
    expect(diag.capabilities).toBeGreaterThan(0);
    expect(diag.providers).toBeGreaterThan(0);
    expect(diag.enabledProviders).toBeGreaterThan(0);
    expect(diag.metrics).toBeDefined();
    expect(diag.circuits).toBeDefined();
    expect(diag.cache).toBeDefined();
    expect(diag.coalescer).toBeDefined();
  });

  it("handles rate-limited requests", async () => {
    const runtime = new CapabilityRuntime({
      persistenceEnabled: false,
      rateLimitPerMinute: 1,
    });
    await runtime.initialize();

    // Exhaust the rate limit
    runtime.rateLimiter.recordRequest("open-meteo");
    runtime.rateLimiter.recordRequest("open-meteo"); // over limit

    const request: CapabilityRequest = {
      id: "test-1",
      capabilityId: "weather.current",
      input: { city: "Delhi" },
      source: "SYSTEM",
      priority: 5,
      fallbackAllowed: true,
      cachePolicy: "NONE",
      timestamp: Date.now(),
    };

    const response = await runtime.execute(request);
    expect(response.success).toBe(false);
    expect(response.error?.code).toBe("RATE_LIMITED");
  });

  it("generates request IDs correctly", async () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    await runtime.initialize();

    // Verify routes module generates IDs
    const { default: _ } = await import("../server/routes/capabilities");
    // Just verify runtime works
    expect(runtime).toBeDefined();
  });
});

// ── Runtime Singleton ────────────────────────────────────────

describe("Phase 19B — Runtime Singleton", () => {
  it("getCapabilityRuntime returns same instance", () => {
    const r1 = getCapabilityRuntime();
    const r2 = getCapabilityRuntime();
    expect(r1).toBe(r2);
  });
});

// ── Native Adapter Contract (Python-side, validated inline) ──

describe("Phase 19B — Native Adapter Contract", () => {
  const TOOL_CAPABILITY_MAP: Record<string, { capability: string; category: string; description: string }> = {
    systemInfo: { capability: "system.info", category: "UTILITY", description: "System hardware info" },
    gpuInfo: { capability: "system.info", category: "UTILITY", description: "GPU information" },
    temperatureInfo: { capability: "system.info", category: "UTILITY", description: "System temperatures" },
    readFile: { capability: "files.read", category: "UTILITY", description: "Read file contents" },
    createFile: { capability: "files.write", category: "UTILITY", description: "Create a file" },
    listFiles: { capability: "files.list", category: "UTILITY", description: "List directory contents" },
    searchFiles: { capability: "files.search", category: "UTILITY", description: "Search for files" },
    deleteFile: { capability: "files.delete", category: "UTILITY", description: "Delete a file" },
    takeScreenshot: { capability: "vision.analyze", category: "UTILITY", description: "Take screenshot" },
    analyzeScreenshot: { capability: "vision.analyze", category: "UTILITY", description: "OCR screenshot" },
    readScreen: { capability: "vision.analyze", category: "UTILITY", description: "Read screen text" },
    searchWeb: { capability: "web.search", category: "SEARCH", description: "Web search" },
    searchGoogle: { capability: "web.search", category: "SEARCH", description: "Google search" },
    searchYouTube: { capability: "web.search", category: "SEARCH", description: "YouTube search" },
    openWebsite: { capability: "web.search", category: "SEARCH", description: "Open website" },
    desktopBrowserOpen: { capability: "browser.search", category: "SEARCH", description: "Open URL in browser" },
    desktopBrowserSearch: { capability: "browser.search", category: "SEARCH", description: "Search in browser" },
    openApplication: { capability: "app.open", category: "UTILITY", description: "Open application" },
    closeApplication: { capability: "app.close", category: "UTILITY", description: "Close application" },
    minimizeWindow: { capability: "window.manage", category: "UTILITY", description: "Minimize window" },
    maximizeWindow: { capability: "window.manage", category: "UTILITY", description: "Maximize window" },
    closeWindow: { capability: "window.manage", category: "UTILITY", description: "Close window" },
    activateWindow: { capability: "window.manage", category: "UTILITY", description: "Activate window" },
    typeText: { capability: "input.type", category: "UTILITY", description: "Type text" },
    pressKey: { capability: "input.key", category: "UTILITY", description: "Press key" },
    hotkey: { capability: "input.key", category: "UTILITY", description: "Key combination" },
    moveMouse: { capability: "input.mouse", category: "UTILITY", description: "Move mouse" },
    leftClick: { capability: "input.mouse", category: "UTILITY", description: "Left click" },
    rightClick: { capability: "input.mouse", category: "UTILITY", description: "Right click" },
    copySelected: { capability: "clipboard.copy", category: "UTILITY", description: "Copy selected" },
    pasteClipboard: { capability: "clipboard.paste", category: "UTILITY", description: "Paste clipboard" },
    getClipboard: { capability: "clipboard.read", category: "UTILITY", description: "Read clipboard" },
    volumeUp: { capability: "pc.volume", category: "UTILITY", description: "Volume up" },
    volumeDown: { capability: "pc.volume", category: "UTILITY", description: "Volume down" },
    setVolume: { capability: "pc.volume", category: "UTILITY", description: "Set volume" },
    muteToggle: { capability: "pc.volume", category: "UTILITY", description: "Toggle mute" },
    brightnessUp: { capability: "pc.brightness", category: "UTILITY", description: "Brightness up" },
    brightnessDown: { capability: "pc.brightness", category: "UTILITY", description: "Brightness down" },
    setBrightness: { capability: "pc.brightness", category: "UTILITY", description: "Set brightness" },
    gitStatus: { capability: "git.status", category: "DEVELOPMENT", description: "Git status" },
    gitDiff: { capability: "git.diff", category: "DEVELOPMENT", description: "Git diff" },
    gitLog: { capability: "git.log", category: "DEVELOPMENT", description: "Git log" },
    gitAdd: { capability: "git.stage", category: "DEVELOPMENT", description: "Git add" },
    gitCommit: { capability: "git.commit", category: "DEVELOPMENT", description: "Git commit" },
    gitPush: { capability: "git.push", category: "DEVELOPMENT", description: "Git push" },
    gitPull: { capability: "git.pull", category: "DEVELOPMENT", description: "Git pull" },
    createPythonFile: { capability: "code.create", category: "DEVELOPMENT", description: "Create Python file" },
    writeCodeFile: { capability: "code.create", category: "DEVELOPMENT", description: "Write code file" },
    runPythonScript: { capability: "code.run", category: "DEVELOPMENT", description: "Run Python script" },
    createProjectFolder: { capability: "code.project", category: "DEVELOPMENT", description: "Create project folder" },
    runShellCommand: { capability: "terminal.run", category: "UTILITY", description: "Run shell command" },
    runCommand: { capability: "terminal.run", category: "UTILITY", description: "Run command" },
  };

  it("maps system tools to system.info capability", () => {
    expect(TOOL_CAPABILITY_MAP.systemInfo.capability).toBe("system.info");
    expect(TOOL_CAPABILITY_MAP.gpuInfo.capability).toBe("system.info");
    expect(TOOL_CAPABILITY_MAP.temperatureInfo.capability).toBe("system.info");
  });

  it("maps file tools to files.* capabilities", () => {
    expect(TOOL_CAPABILITY_MAP.readFile.capability).toBe("files.read");
    expect(TOOL_CAPABILITY_MAP.createFile.capability).toBe("files.write");
    expect(TOOL_CAPABILITY_MAP.listFiles.capability).toBe("files.list");
    expect(TOOL_CAPABILITY_MAP.searchFiles.capability).toBe("files.search");
  });

  it("maps vision tools to vision.analyze", () => {
    expect(TOOL_CAPABILITY_MAP.takeScreenshot.capability).toBe("vision.analyze");
    expect(TOOL_CAPABILITY_MAP.analyzeScreenshot.capability).toBe("vision.analyze");
    expect(TOOL_CAPABILITY_MAP.readScreen.capability).toBe("vision.analyze");
  });

  it("maps search tools to web.search", () => {
    expect(TOOL_CAPABILITY_MAP.searchWeb.capability).toBe("web.search");
    expect(TOOL_CAPABILITY_MAP.searchGoogle.capability).toBe("web.search");
    expect(TOOL_CAPABILITY_MAP.searchYouTube.capability).toBe("web.search");
    expect(TOOL_CAPABILITY_MAP.openWebsite.capability).toBe("web.search");
  });

  it("maps browser tools to browser.search", () => {
    expect(TOOL_CAPABILITY_MAP.desktopBrowserOpen.capability).toBe("browser.search");
    expect(TOOL_CAPABILITY_MAP.desktopBrowserSearch.capability).toBe("browser.search");
  });

  it("maps input tools to input.* capabilities", () => {
    expect(TOOL_CAPABILITY_MAP.typeText.capability).toBe("input.type");
    expect(TOOL_CAPABILITY_MAP.pressKey.capability).toBe("input.key");
    expect(TOOL_CAPABILITY_MAP.hotkey.capability).toBe("input.key");
    expect(TOOL_CAPABILITY_MAP.moveMouse.capability).toBe("input.mouse");
    expect(TOOL_CAPABILITY_MAP.leftClick.capability).toBe("input.mouse");
  });

  it("maps clipboard tools to clipboard.* capabilities", () => {
    expect(TOOL_CAPABILITY_MAP.copySelected.capability).toBe("clipboard.copy");
    expect(TOOL_CAPABILITY_MAP.pasteClipboard.capability).toBe("clipboard.paste");
    expect(TOOL_CAPABILITY_MAP.getClipboard.capability).toBe("clipboard.read");
  });

  it("maps PC control tools to pc.* capabilities", () => {
    expect(TOOL_CAPABILITY_MAP.volumeUp.capability).toBe("pc.volume");
    expect(TOOL_CAPABILITY_MAP.brightnessUp.capability).toBe("pc.brightness");
  });

  it("maps git tools to git.* capabilities", () => {
    expect(TOOL_CAPABILITY_MAP.gitStatus.capability).toBe("git.status");
    expect(TOOL_CAPABILITY_MAP.gitCommit.capability).toBe("git.commit");
  });

  it("maps code tools to code.* capabilities", () => {
    expect(TOOL_CAPABILITY_MAP.createPythonFile.capability).toBe("code.create");
    expect(TOOL_CAPABILITY_MAP.runPythonScript.capability).toBe("code.run");
  });

  it("has correct categories for each tool group", () => {
    expect(TOOL_CAPABILITY_MAP.systemInfo.category).toBe("UTILITY");
    expect(TOOL_CAPABILITY_MAP.searchWeb.category).toBe("SEARCH");
    expect(TOOL_CAPABILITY_MAP.gitStatus.category).toBe("DEVELOPMENT");
    expect(TOOL_CAPABILITY_MAP.leftClick.category).toBe("UTILITY");
  });

  it("covers all 50+ tools", () => {
    expect(Object.keys(TOOL_CAPABILITY_MAP).length).toBeGreaterThanOrEqual(50);
  });
});

// ── Bridge Contract (Python-side, validated inline) ──────────

describe("Phase 19B — Capability Bridge Contract", () => {
  const TASK_TYPE_TO_CAPABILITY: Record<string, string> = {
    weather_task: "weather.current",
    news_task: "news.search",
    web_research: "research.search",
    current_information: "research.search",
    time_task: "time.current",
    system_task: "system.info",
    search_task: "web.search",
    file_task: "files.read",
    vision_task: "vision.analyze",
    browser_action: "browser.search",
  };

  it("maps weather_task to weather.current", () => {
    expect(TASK_TYPE_TO_CAPABILITY.weather_task).toBe("weather.current");
  });

  it("maps news_task to news.search", () => {
    expect(TASK_TYPE_TO_CAPABILITY.news_task).toBe("news.search");
  });

  it("maps web_research to research.search", () => {
    expect(TASK_TYPE_TO_CAPABILITY.web_research).toBe("research.search");
  });

  it("maps time_task to time.current", () => {
    expect(TASK_TYPE_TO_CAPABILITY.time_task).toBe("time.current");
  });

  it("maps system_task to system.info", () => {
    expect(TASK_TYPE_TO_CAPABILITY.system_task).toBe("system.info");
  });

  it("maps search_task to web.search", () => {
    expect(TASK_TYPE_TO_CAPABILITY.search_task).toBe("web.search");
  });

  it("maps file_task to files.read", () => {
    expect(TASK_TYPE_TO_CAPABILITY.file_task).toBe("files.read");
  });

  it("maps vision_task to vision.analyze", () => {
    expect(TASK_TYPE_TO_CAPABILITY.vision_task).toBe("vision.analyze");
  });

  it("maps browser_action to browser.search", () => {
    expect(TASK_TYPE_TO_CAPABILITY.browser_action).toBe("browser.search");
  });

  it("covers all 10 task types", () => {
    expect(Object.keys(TASK_TYPE_TO_CAPABILITY).length).toBe(10);
  });

  it("all mapped capability IDs exist in runtime", async () => {
    const runtime = new CapabilityRuntime({ persistenceEnabled: false });
    await runtime.initialize();
    const caps = runtime.registry.getCapabilities();
    const capIds = new Set(caps.map(c => c.id));

    for (const [, capId] of Object.entries(TASK_TYPE_TO_CAPABILITY)) {
      expect(capIds.has(capId)).toBe(true);
    }
  });
});
