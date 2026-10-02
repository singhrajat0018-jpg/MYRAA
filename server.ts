import express from "express";
import http from "http";
import path from "path";
import { spawn as spawnProcess } from "node:child_process";
import { WebSocketServer, WebSocket as WsWebSocket } from "ws";
import dotenv from "dotenv";
import * as fs from "fs";
import {
  loadMemories,
  saveMemories,
  formatSystemInstructionsWithMemories,
  processConversationSlice,
  loadConversationHistory,
  saveConversationHistory,
  normalizeNewMemory,
  updateMemories,
  isSensitiveMemoryText,
} from "./server_memory";
import {
  createConversation,
  getConversation,
  pruneConversations,
  generateTitle,
} from "./server_conversations";
import { DESKTOP_AGENT_URL } from "./services/desktop/desktop_agent";
import {
  DATA_DIR,
} from "./server_paths";
import { ConversationBus } from "./backend/speech/conversation_bus";
import {
    ensureDesktopAgent,
} from "./services/desktop/desktop_agent";
import { nodeTelemetryRelay } from "./services/telemetry/telemetry_relay";
import { VoiceTransport } from "./server_voice";

import { registerMemoryRoutes } from "./server/routes/memories";
import { registerSettingsRoutes } from "./server/routes/settings";
import { registerConfigRoutes } from "./server/routes/config";
import { registerWeatherRoutes } from "./server/routes/weather";
import { registerSystemRoutes } from "./server/routes/system";
import { registerTradingRoutes } from "./server/routes/trading";
import { registerFinanceRoutes } from "./server/routes/finance";
import { registerLogsRoutes } from "./server/routes/logs";
import { registerProxyRoutes, isUnsafeUrl } from "./server/routes/proxy";
import { registerConversationRoutes, registerChatRoutes } from "./server/routes/chat";
import { registerCapabilityRoutes } from "./server/routes/capabilities";
import { registerLearningRoutes } from "./server/routes/learning";
import { registerAgentRoutes } from "./server/routes/agent";
import { registerWorldRoutes } from "./server/routes/world";
import computerRouter from "./server/routes/computer";
import reliabilityRouter from "./server/routes/reliability";
import researchRouter from "./server/routes/research";
import { registerVisionRoutes } from "./server/routes/vision";

const conversationBus = new ConversationBus();
dotenv.config();

// ── WebSocket session token ────────────────────────────────
import crypto from "crypto";
const WS_SESSION_TOKEN = process.env.MYRAA_WS_TOKEN || crypto.randomBytes(16).toString("hex");
const WS_TOKEN_PARAM = "token";

// ── Logging ────────────────────────────────────────────────
const LOGS_DIR = path.join(DATA_DIR, "logs");
try { fs.mkdirSync(LOGS_DIR, { recursive: true }); } catch { /* already exists */ }

function appendLog(fileName: string, message: string): void {
  try {
    const line = `[${new Date().toISOString()}] ${message}\n`;
    fs.appendFile(path.join(LOGS_DIR, fileName), line, () => {});
  } catch {
    /* logging is best-effort */
  }
}
const logCommand = (m: string) => appendLog("commands.log", m);
const logStartup = (m: string) => appendLog("startup.log", m);
const logError = (m: string) => appendLog("errors.log", m);

// ── Desktop tool registry ──────────────────────────────────
const DESKTOP_TOOLS: ReadonlySet<string> = new Set([
  "openApplication", "closeApplication", "openWebsite",
  "searchWeb", "searchYouTube", "searchGoogle", "searchGitHub",
  "createFile", "readFile", "renameFile", "deleteFile", "moveFile",
  "copyFile", "openFile", "writeFile",
  "openFolder", "listFiles", "searchFiles",
  "volumeUp", "volumeDown", "muteToggle", "setVolume",
  "requestPowerAction", "executePowerAction",
  "minimizeWindow", "maximizeWindow", "closeWindow", "switchApplication",
  "activateWindow", "restoreWindow",
  "copySelected", "pasteClipboard", "getClipboard", "clearClipboard",
  "takeScreenshot", "saveScreenshot", "analyzeScreenshot", "readScreen",
  "takeRegionScreenshot",
  "desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
  "desktopBrowserCloseTab", "desktopBrowserSearch", "desktopBrowserClick",
  "desktopBrowserType", "desktopBrowserFillForm", "desktopBrowserGoBack",
  "desktopBrowserGoForward", "desktopBrowserScroll",
  "createPythonFile", "runPythonScript", "createProjectFolder", "writeCodeFile",
  "runShellCommand", "runCommand",
  "gitStatus", "gitDiff", "gitLog", "gitAdd", "gitCommit", "gitPush", "gitPull", "gitBranch", "gitCheckout",
  "systemInfo", "gpuInfo", "temperatureInfo",
  "brightnessUp", "brightnessDown", "setBrightness",
  "enableAutoStart", "disableAutoStart", "getAutoStartStatus",
  "typeText", "pressKey", "keyDown", "keyUp", "hotkey",
  "moveMouse", "leftClick", "rightClick", "doubleClick", "middleClick",
  "dragMouse", "scrollMouse", "mousePosition",
  "currentDateTime",
]);

// Startup race guard: probe the agent before spawning. When start-myraa.bat
// (or an earlier Node run) already started uvicorn, Node must NOT spawn a
// doomed duplicate that will lose the 8765 port race. The bounded double
// probe also survives the window where the agent is still booting.
function isDesktopAgentAlive(): Promise<boolean> {
  return fetch(`${DESKTOP_AGENT_URL}/health/live`, {
    signal: AbortSignal.timeout(2000),
  })
    .then((r) => r.ok)
    .catch(() => false);
}

const settleMs = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function spawnDesktopAgent(): Promise<void> {
  if (await isDesktopAgentAlive()) {
    logStartup("[Desktop Agent] Already running — skipping auto-start.");
    console.log("[Desktop Agent] Already running — skipping auto-start.");
    return;
  }
  // The agent may be mid-boot (just launched in parallel); settle briefly and
  // probe once more before deciding to spawn.
  await settleMs(1200);
  if (await isDesktopAgentAlive()) {
    logStartup("[Desktop Agent] Detected during settle period — skipping auto-start.");
    console.log("[Desktop Agent] Detected during settle period — skipping auto-start.");
    return;
  }
  const agentExe = process.env.MYRAA_AGENT_EXE;
  if (agentExe && fs.existsSync(agentExe)) {
      logStartup(`[Desktop Agent] Spawning frozen agent: ${agentExe}`);
      console.log(`[Desktop Agent] Spawning frozen agent: ${agentExe}`);
      const child = spawnProcess(agentExe, [], {
          detached: true, stdio: "ignore", windowsHide: true,
      });
      child.unref();
      return;
  }
  const pythonCmd = process.env.PYTHON_PATH || "python";
  logStartup(`[Desktop Agent] Spawning via ${pythonCmd} uvicorn...`);
  console.log(`[Desktop Agent] Spawning via ${pythonCmd} uvicorn...`);
  try {
      const child = spawnProcess(pythonCmd, ["-m", "uvicorn", "desktop_agent.main:app", "--host", "127.0.0.1", "--port", "8765"], {
          detached: true, stdio: "ignore",
          cwd: process.env.MYRAA_APP_ROOT || process.cwd(),
          windowsHide: true,
      });
      child.unref();
  } catch (e: any) {
      logStartup(`[Desktop Agent] Auto-start failed: ${e.message}`);
      console.log(`[Desktop Agent] Could not auto-start: ${e.message}`);
  }
}

const BRAIN_CONTEXT_TURNS = 8;

function recentBrainContext(
    history: { role: string; text: string }[],
): { metadata: { conversation_history: { role: string; text: string }[] } } {
    const recent = history
        .slice(-BRAIN_CONTEXT_TURNS)
        .map((t) => ({ role: t.role, text: t.text }));
    return { metadata: { conversation_history: recent } };
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // CORS middleware — restrict to known local origins
  const ALLOWED_ORIGINS = new Set([
    "http://localhost:3000",
    "http://127.0.0.1:3000",
  ]);
  app.use((req, res, next) => {
    const origin = req.headers.origin || "";
    if (ALLOWED_ORIGINS.has(origin)) {
      res.header("Access-Control-Allow-Origin", origin);
    }
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID");
    res.header("Access-Control-Allow-Credentials", "true");
    if (req.method === "OPTIONS") {
      return res.sendStatus(204);
    }
    next();
  });

  // Correlation ID — every HTTP request gets a unique ID for end-to-end tracing
  app.use((req, _res, next) => {
    (req as any).requestId = (req.headers["x-request-id"] as string) || crypto.randomUUID();
    next();
  });

  // Content Security Policy — prevent XSS and code injection.
  // Development (Vite dev middleware active) requires relaxed rules so the
  // @vitejs/plugin-react preamble (inline script) and the Vite HMR WebSocket
  // (ws://localhost:24678) can operate. Production keeps a strict CSP.
  // worker-src 'self' blob: allows the Blob-URL AudioWorklet capture
  // processor (src/lib/audio.ts); script-src is unchanged.
  const isDev = process.env.NODE_ENV !== 'production';
  app.use((_req, res, next) => {
    const csp = isDev
      ? "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; connect-src 'self' ws://localhost:3000 ws://localhost:24678 http://127.0.0.1:8765 http://127.0.0.1:11434; img-src 'self' data: blob:; font-src 'self'; frame-ancestors 'none'"
      : "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; connect-src 'self' ws://localhost:3000 http://127.0.0.1:8765 http://127.0.0.1:11434; img-src 'self' data: blob:; font-src 'self'; frame-ancestors 'none'";
    res.header("Content-Security-Policy", csp);
    next();
  });

  // Server context for route modules
  const ctx = { DESKTOP_AGENT_URL, LOGS_DIR, WS_SESSION_TOKEN, logCommand, logError };

  // Register all route modules
  registerSettingsRoutes(app, ctx);
  registerConfigRoutes(app, ctx);
  registerMemoryRoutes(app, ctx);
  registerWeatherRoutes(app, ctx);
  registerSystemRoutes(app, ctx);
  registerTradingRoutes(app, ctx);
  registerFinanceRoutes(app, ctx);
  registerLogsRoutes(app, ctx);
  registerProxyRoutes(app, ctx);
  registerConversationRoutes(app, ctx);
  registerChatRoutes(app, ctx);
  registerCapabilityRoutes(app, ctx);
  registerLearningRoutes(app, ctx);
  registerAgentRoutes(app);
  registerWorldRoutes(app);
  app.use('/api/computer', computerRouter);
  app.use('/api/reliability', reliabilityRouter);
  app.use('/api/research', researchRouter);
  registerVisionRoutes(app, ctx);

  // ── Initialize engines (P0 fix — routes return 503 without these) ──
  let reasoningEngine: any = null;
  let visionEngine: any = null;

  try {
    const { ReasoningEngine } = await import("./src/agent/index");
    const { setReasoningEngine } = await import("./server/routes/agent");
    const { executeViaPython } = await import("./src/core/execution_bridge");
    const re = new ReasoningEngine();
    // Wire the task executor to Python bridge — REAL execution, not fake
    re.executionEngine.setTaskExecutor(async (task: any) => {
      return executeViaPython(task, { financialFirewallActive: true, autonomyLevel: 'SUPERVISED', blockedActions: [] });
    });
    setReasoningEngine(re);
    reasoningEngine = re;
    console.log("[Startup] ReasoningEngine initialized WITH Python execution bridge");
  } catch (err: any) {
    console.warn("[Startup] ReasoningEngine init failed:", err.message);
  }

  try {
    const { WorldIntelligence } = await import("./src/world-intelligence/index");
    const { setWorldIntelligence } = await import("./server/routes/world");
    const wi = new WorldIntelligence();
    setWorldIntelligence(wi);
    console.log("[Startup] WorldIntelligence initialized");
  } catch (err: any) {
    console.warn("[Startup] WorldIntelligence init failed:", err.message);
  }

  try {
    const { VisionEngine } = await import("./src/vision/index");
    const { BridgeScreenCaptureAdapter } = await import("./src/vision/screenCapture");
    const { BridgeOcrAdapter } = await import("./src/vision/ocrAdapter");
    const { setVisionEngine } = await import("./server/routes/vision");
    const ve = new VisionEngine({
      captureAdapter: new BridgeScreenCaptureAdapter({ agentUrl: DESKTOP_AGENT_URL }),
      ocrAdapter: new BridgeOcrAdapter({ agentUrl: DESKTOP_AGENT_URL }),
    });
    setVisionEngine(ve);
    visionEngine = ve;
    console.log("[Startup] VisionEngine initialized (BridgeScreenCaptureAdapter + BridgeOcrAdapter — REAL OCR)");
  } catch (err: any) {
    console.warn("[Startup] VisionEngine init failed:", err.message);
  }

  // ── Unified Health Endpoint ──────────────────────────────
  app.get("/api/health", async (_req, res) => {
    try {
      const { getSystemHealth, healthToHttpStatus } = await import("./src/core/health");
      const health = await getSystemHealth({ visionEngine, reasoningEngine });
      res.status(healthToHttpStatus(health)).json(health);
    } catch {
      res.status(500).json({ error: "Health check failed" });
    }
  });

  // ── HTTP server + WebSocket ──────────────────────────────
  const server = http.createServer(app);
  const wss = new WebSocketServer({ noServer: true });
  const wssTelemetry = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    const url = new URL(request.url || '', `http://${request.headers.host}`);
    const pathname = url.pathname;

    if (pathname === "/live") {
      const clientToken = url.searchParams.get(WS_TOKEN_PARAM);
      if (clientToken !== WS_SESSION_TOKEN) {
        console.warn("[WS] Rejected connection — invalid or missing session token");
        socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
        socket.destroy();
        return;
      }
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit("connection", ws, request);
      });
    } else if (pathname === "/telemetry") {
      wssTelemetry.handleUpgrade(request, socket, head, (ws) => {
        nodeTelemetryRelay.addClient(ws);
      });
    } else {
      socket.destroy();
    }
  });

  wss.on("connection", async (clientWs) => {
    console.log("[Voice] Client WebSocket connected to /live (Gemini Live voice)");

    const transport = new VoiceTransport(clientWs);

    transport.setCallbacks({
      onStateChange: (state) => {
        if (clientWs.readyState === WsWebSocket.OPEN) {
          clientWs.send(JSON.stringify({ type: "status", status: state }));
        }
      },
      onTranscription: (role, text) => {
        if (role === "model") conversationBus.addAssistant(text);
        else conversationBus.addUser(text);
      },
    });

    await transport.start();

    clientWs.on("message", async (raw) => {
      try {
        const data = JSON.parse(raw.toString());
        if (data.audio) {
          transport.handleAudioChunk(data.audio);
          return;
        }
        if (data.type === "video" && data.video) {
          transport.handleVideoFrame(data.video);
          return;
        }
        if (data.type === "interrupt") {
          transport.interrupt();
          return;
        }
      } catch (err: any) {
        console.error("[Voice] Message parse error:", err.message);
      }
    });

    clientWs.on("close", () => {
      console.log("[Voice] Client disconnected");
      transport.stop();
    });

    clientWs.on("error", (err) => {
      console.error("[Voice] WebSocket error:", err.message);
      transport.stop();
    });
  });

  // Static assets
  app.use("/assets", express.static(path.join(process.cwd(), "assets")));

  if (process.env.NODE_ENV !== "production") {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  server.listen(PORT, "127.0.0.1", () => {
    logStartup(`MYRAA V2 server started on http://localhost:${PORT}`);
    console.log(`[Server] Running on http://localhost:${PORT}`);
    // Try to auto-start Python agent if not running (skips if already healthy)
    spawnDesktopAgent().catch((e) =>
      console.warn(`[Desktop Agent] Auto-start failed: ${e?.message || e}`)
    );
    ensureDesktopAgent().catch((e) =>
      console.warn(`[Desktop Agent] Boot probe failed: ${e?.message || e}`)
    );
    nodeTelemetryRelay.start();
    console.log("[Telemetry Relay] Started polling Python agent.");
  });

  let shuttingDown = false;
  const shutdown = (signal: string) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`[Server] ${signal} received, shutting down gracefully...`);
    try { nodeTelemetryRelay.stop(); } catch { /* ignore */ }
    try { wss.clients.forEach((ws) => ws.close()); } catch { /* ignore */ }
    try { wssTelemetry.clients.forEach((ws) => ws.close()); } catch { /* ignore */ }
    // Flush pending persistence (conversations index + memory retry state)
    // so a shutdown during a transient OneDrive lock never drops the merge.
    try {
      const conv = require("./server_conversations") as typeof import("./server_conversations");
      conv.flushConversationPersistence();
    } catch { /* best-effort */ }
    try {
      const mem = require("./server_memory") as typeof import("./server_memory");
      (mem.flushMemoryPersistence() as Promise<void>).catch(() => undefined);
    } catch { /* best-effort */ }
    try {
      const staleDirs = ["conversations", "capabilities"];
      const fss = require("fs") as typeof import("fs");
      const pathm = require("path") as typeof import("path");
      const { DATA_DIR: _dd } = require("./server_paths") as typeof import("./server_paths");
      for (const d of staleDirs) {
        try {
          const dir = pathm.join(_dd, d);
          if (!fss.existsSync(dir)) continue;
          for (const name of fss.readdirSync(dir)) {
            if (!name.includes(".tmp.")) continue;
            try { fss.unlinkSync(pathm.join(dir, name)); } catch { /* ignore */ }
          }
        } catch { /* ignore */ }
      }
    } catch { /* ignore */ }
    server.close(() => {
      console.log("[Server] HTTP server closed.");
      process.exit(0);
    });
    setTimeout(() => {
      console.warn("[Server] Forced shutdown after close timeout.");
      process.exit(0);
    }, 5000).unref();
  };
  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  // Persistence failure must be a DEGRADED condition, never a process crash.
  process.on("unhandledRejection", (reason: unknown) => {
    console.error("[Server] unhandledRejection (contained, server alive):", reason);
  });
  process.on("uncaughtException", (err: unknown) => {
    console.error("[Server] uncaughtException (contained, server alive):", err);
  });
}

startServer().catch((error) => {
  console.error("Failed to start server startup sequence:", error);
});
