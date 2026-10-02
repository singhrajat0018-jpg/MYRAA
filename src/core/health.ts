// ============================================================================
// MYRAA System Health — Unified Health Snapshot for All Subsystems
// ============================================================================

import type { SystemHealth, SubsystemHealth, SubsystemStatus } from './contracts';
import { getPythonBreaker } from './execution_bridge';

const DESKTOP_AGENT_URL = process.env.DESKTOP_AGENT_URL || 'http://127.0.0.1:8765';

async function checkUrl(url: string, timeoutMs = 3000): Promise<SubsystemHealth> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);
    return {
      status: resp.ok ? 'UP' : 'DEGRADED',
      latencyMs: Date.now() - start,
      lastCheck: new Date().toISOString(),
    };
  } catch {
    return {
      status: 'DOWN',
      latencyMs: Date.now() - start,
      lastCheck: new Date().toISOString(),
      message: 'Connection failed',
    };
  }
}

function checkOllama(): Promise<SubsystemHealth> {
  return checkUrl('http://127.0.0.1:11434/api/tags', 5000);
}

function checkPythonAgent(): Promise<SubsystemHealth> {
  return checkUrl(`${DESKTOP_AGENT_URL}/health/live`, 5000);
}

export async function getSystemHealth(engines: {
  visionEngine?: { isEngineRunning: boolean } | null;
  reasoningEngine?: unknown | null;
  worldIntelligence?: unknown | null;
} = {}): Promise<SystemHealth> {
  const [pythonAgent, ollama] = await Promise.all([
    checkPythonAgent(),
    checkOllama(),
  ]);

  return {
    server: { status: 'UP', lastCheck: new Date().toISOString() },
    pythonAgent,
    brain: {
      status: pythonAgent.status === 'UP' ? (ollama.status === 'UP' ? 'UP' : 'DEGRADED') : 'DOWN',
      message: ollama.status !== 'UP' ? 'Ollama unavailable' : undefined,
      lastCheck: new Date().toISOString(),
    },
    memory: { status: 'UP', lastCheck: new Date().toISOString() },
    world: {
      status: engines.worldIntelligence ? 'UP' : 'UNAVAILABLE',
      lastCheck: new Date().toISOString(),
    },
    vision: {
      status: engines.visionEngine?.isEngineRunning ? 'UP' : 'DEGRADED',
      // Honest state: adapters are REAL (BridgeScreenCapture/BridgeOcr); the
      // engine simply has not been started. Continuous screen capture is
      // opt-in via POST /api/vision/control {action:"start"}.
      message: engines.visionEngine?.isEngineRunning ? undefined : 'Engine not started (screen capture is opt-in via /api/vision/control)',
      lastCheck: new Date().toISOString(),
    },
    computer: {
      status: pythonAgent.status === 'UP' ? 'UP' : 'DOWN',
      lastCheck: new Date().toISOString(),
    },
    finance: { status: 'DEGRADED', message: 'No live market data', lastCheck: new Date().toISOString() },
    quant: { status: 'UP', lastCheck: new Date().toISOString() },
    learning: { status: 'UP', lastCheck: new Date().toISOString() },
    voice: {
      status: pythonAgent.status === 'UP' ? 'UP' : 'DOWN',
      lastCheck: new Date().toISOString(),
    },
    providers: {
      status: ollama.status,
      message: ollama.status !== 'UP' ? 'Ollama unavailable' : undefined,
      lastCheck: new Date().toISOString(),
    },
    bridge: {
      status: pythonAgent.status,
      latencyMs: pythonAgent.latencyMs,
      lastCheck: new Date().toISOString(),
      message: `Circuit breaker: ${getPythonBreaker().getStats().state}`,
    },
  };
}

export function healthToHttpStatus(health: SystemHealth): number {
  const statuses = Object.values(health);
  const downs = statuses.filter(s => s.status === 'DOWN').length;
  if (downs === 0) return 200;
  if (downs < statuses.length / 2) return 207; // Multi-Status
  return 503; // Service Unavailable
}
