// ============================================================================
// MYRAA Execution Bridge — Connects TS Agent to Python CommandDispatcher
// ============================================================================

import type { PlanTask, TaskResult } from '../agent/contracts';
import type { ExecutionRequest, ExecutionResult, PolicyContext } from './contracts';
import { generateActionId } from './contracts';
import { CircuitBreaker } from './circuit_breaker';

const DESKTOP_AGENT_URL = process.env.DESKTOP_AGENT_URL || 'http://127.0.0.1:8765';
const DEFAULT_TIMEOUT_MS = 25_000;

// ── Circuit Breaker ─────────────────────────────────────────────────────────

const pythonBreaker = new CircuitBreaker({ failureThreshold: 5, cooldownMs: 30000 });
export function getPythonBreaker() { return pythonBreaker; }

// ── Bridge Health State ─────────────────────────────────────────────────────

interface BridgeState {
  lastHeartbeat: number;
  activeRequests: number;
  totalRequests: number;
  failedRequests: number;
  avgLatencyMs: number;
  healthy: boolean;
}

const bridgeState: BridgeState = {
  lastHeartbeat: 0,
  activeRequests: 0,
  totalRequests: 0,
  failedRequests: 0,
  avgLatencyMs: 0,
  healthy: false,
};

// ── Policy Enforcement ──────────────────────────────────────────────────────

const BLOCKED_TOOLS = new Set([
  'execute_trade', 'place_order', 'buy_stock', 'sell_stock',
  'short_stock', 'open_position', 'close_position', 'transfer_funds',
]);

function validatePolicy(task: PlanTask, policy?: PolicyContext): string | null {
  if (policy?.financialFirewallActive) {
    const taskText = `${task.type} ${task.description}`.toLowerCase();
    for (const blocked of BLOCKED_TOOLS) {
      if (taskText.includes(blocked)) {
        return `Blocked by financial firewall: ${blocked}`;
      }
    }
  }
  if (task.sideEffects.some(se => se.type === 'SHELL_EXECUTION')) {
    if (!task.description.toLowerCase().includes('approved')) {
      // Shell commands require explicit approval through the agent pipeline
    }
  }
  return null;
}

// ── Core Bridge ─────────────────────────────────────────────────────────────

export async function executeViaPython(
  task: PlanTask,
  policy?: PolicyContext,
): Promise<TaskResult> {
  const start = Date.now();
  const actionId = generateActionId();

  // Policy check
  const policyViolation = validatePolicy(task, policy);
  if (policyViolation) {
    return {
      success: false,
      data: null,
      error: policyViolation,
      timestamp: new Date().toISOString(),
      latencyMs: Date.now() - start,
      provenance: [{ sourceId: 'execution-bridge', sourceType: 'NATIVE_TOOL' as const, retrievedAt: new Date().toISOString(), confidence: 1 }],
      confidence: 1,
      retryable: false,
    };
  }

  // Map PlanTask → Python tool invocation
  const toolInvocation = mapTaskToTool(task);
  if (!toolInvocation) {
    return {
      success: false,
      data: null,
      error: `No tool mapping for task type: ${task.type}`,
      timestamp: new Date().toISOString(),
      latencyMs: Date.now() - start,
      provenance: [{ sourceId: 'execution-bridge', sourceType: 'NATIVE_TOOL' as const, retrievedAt: new Date().toISOString(), confidence: 1 }],
      confidence: 1,
      retryable: false,
    };
  }

  // Circuit breaker check
  if (!pythonBreaker.canExecute()) {
    const stats = pythonBreaker.getStats();
    return {
      success: false,
      data: null,
      error: `Python bridge circuit breaker OPEN (failures: ${stats.failures}, last failure: ${new Date(stats.lastFailure).toISOString()})`,
      timestamp: new Date().toISOString(),
      latencyMs: Date.now() - start,
      provenance: [{ sourceId: 'execution-bridge', sourceType: 'NATIVE_TOOL' as const, retrievedAt: new Date().toISOString(), confidence: 0 }],
      confidence: 0,
      retryable: true,
    };
  }

  // Execute via Python
  bridgeState.activeRequests++;
  bridgeState.totalRequests++;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    const response = await fetch(`${DESKTOP_AGENT_URL}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool: toolInvocation.tool,
        args: toolInvocation.args,
        request_id: task.taskId,
        task_id: task.taskId,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      throw new Error(`Python agent returned ${response.status}`);
    }

    const data = await response.json() as {
      ok: boolean;
      result?: unknown;
      error?: string;
      meta?: { duration_ms?: number };
    };

    const duration = Date.now() - start;
    bridgeState.avgLatencyMs = (bridgeState.avgLatencyMs + duration) / 2;
    bridgeState.lastHeartbeat = Date.now();
    bridgeState.healthy = true;
    pythonBreaker.recordSuccess(duration);

    return {
      success: data.ok,
      data: data.ok ? data.result : null,
      error: data.ok ? undefined : data.error,
      provider: 'python-desktop-agent',
      timestamp: new Date().toISOString(),
      latencyMs: duration,
      provenance: [{
        sourceId: 'execution-bridge',
        sourceType: 'NATIVE_TOOL' as const,
        retrievedAt: new Date().toISOString(),
        confidence: data.ok ? 0.9 : 0,
      }],
      confidence: data.ok ? 0.9 : 0,
      retryable: !data.ok && isRetryableError(data.error),
    };
  } catch (err) {
    bridgeState.failedRequests++;
    bridgeState.healthy = false;
    pythonBreaker.recordFailure();
    const duration = Date.now() - start;

    return {
      success: false,
      data: null,
      error: err instanceof Error ? err.message : String(err),
      provider: 'python-desktop-agent',
      timestamp: new Date().toISOString(),
      latencyMs: duration,
      provenance: [{
        sourceId: 'execution-bridge',
        sourceType: 'NATIVE_TOOL' as const,
        retrievedAt: new Date().toISOString(),
        confidence: 0,
      }],
      confidence: 0,
      retryable: true,
    };
  } finally {
    bridgeState.activeRequests--;
  }
}

// ── Tool Mapping ────────────────────────────────────────────────────────────

interface ToolInvocation {
  tool: string;
  args: Record<string, unknown>;
}

function mapTaskToTool(task: PlanTask): ToolInvocation | null {
  const desc = task.description.toLowerCase();

  // File operations
  if (desc.includes('read file') || desc.includes('read the file')) {
    const path = extractPath(task);
    return path ? { tool: 'readFile', args: { path } } : null;
  }
  if (desc.includes('write file') || desc.includes('create file')) {
    const path = extractPath(task);
    const content = extractContent(task);
    return path ? { tool: 'createFile', args: { path, content: content || '' } } : null;
  }

  // Web operations
  if (desc.includes('search') || desc.includes('research')) {
    const query = extractQuery(task);
    return query ? { tool: 'searchWeb', args: { query } } : null;
  }
  if (desc.includes('open website') || desc.includes('open url')) {
    const url = extractUrl(task);
    return url ? { tool: 'openWebsite', args: { url } } : null;
  }

  // Application operations
  if (desc.includes('open app') || desc.includes('open chrome') || desc.includes('open notepad')) {
    const app = extractAppName(task);
    return app ? { tool: 'openApplication', args: { name: app } } : null;
  }
  if (desc.includes('close app')) {
    const app = extractAppName(task);
    return app ? { tool: 'closeApplication', args: { name: app } } : null;
  }

  // Screenshot / Vision
  if (desc.includes('screenshot') || desc.includes('screen capture')) {
    return { tool: 'takeScreenshot', args: {} };
  }

  // System info
  if (desc.includes('system info') || desc.includes('system information')) {
    return { tool: 'systemInfo', args: {} };
  }

  // Code execution
  if (desc.includes('run python') || desc.includes('execute code')) {
    const code = extractContent(task);
    return code ? { tool: 'runPythonScript', args: { script: code } } : null;
  }

  // Clipboard
  if (desc.includes('copy') && desc.includes('clipboard')) {
    return { tool: 'getClipboard', args: {} };
  }

  // Volume
  if (desc.includes('volume up') || desc.includes('increase volume')) {
    return { tool: 'volumeUp', args: {} };
  }
  if (desc.includes('volume down') || desc.includes('decrease volume')) {
    return { tool: 'volumeDown', args: {} };
  }

  // Default: try to use the task description as a generic search
  if (task.description) {
    return { tool: 'searchWeb', args: { query: task.description } };
  }

  return null;
}

// ── Extraction Helpers ──────────────────────────────────────────────────────

function extractPath(task: PlanTask): string | null {
  const desc = task.description;
  // Try to find a file path in the description
  const pathMatch = desc.match(/(?:file|path|read|write|create)\s+[:=]?\s*["`']?([^\s"`']+\.\w+)/i);
  if (pathMatch) return pathMatch[1];
  // Check metadata
  const metaPath = task.metadata?.filePath || task.metadata?.path || task.metadata?.filename;
  if (typeof metaPath === 'string') return metaPath;
  return null;
}

function extractContent(task: PlanTask): string | null {
  const metaContent = task.metadata?.content || task.metadata?.script || task.metadata?.code;
  if (typeof metaContent === 'string') return metaContent;
  return null;
}

function extractQuery(task: PlanTask): string | null {
  const metaQuery = task.metadata?.query;
  if (typeof metaQuery === 'string') return metaQuery;
  // Use description as query
  return task.description || null;
}

function extractUrl(task: PlanTask): string | null {
  const metaUrl = task.metadata?.url;
  if (typeof metaUrl === 'string') return metaUrl;
  const urlMatch = task.description.match(/(https?:\/\/[^\s]+)/i);
  return urlMatch ? urlMatch[1] : null;
}

function extractAppName(task: PlanTask): string | null {
  const metaName = task.metadata?.appName || task.metadata?.name;
  if (typeof metaName === 'string') return metaName;
  // Try to extract app name from common patterns
  const appMatch = task.description.match(/(?:open|launch|start|close)\s+(chrome|notepad|vscode|code|explorer|firefox|edge|spotify|discord)/i);
  return appMatch ? appMatch[1] : null;
}

function isRetryableError(error?: string): boolean {
  if (!error) return false;
  const retryablePatterns = ['timeout', 'ECONNREFUSED', 'ECONNRESET', 'network', 'temporary', 'rate limit'];
  return retryablePatterns.some(p => error.toLowerCase().includes(p));
}

// ── Health Check ────────────────────────────────────────────────────────────

export async function checkBridgeHealth(): Promise<{
  healthy: boolean;
  state: BridgeState;
  pythonReachable: boolean;
}> {
  let pythonReachable = false;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const resp = await fetch(`${DESKTOP_AGENT_URL}/health/live`, { signal: controller.signal });
    clearTimeout(timeout);
    pythonReachable = resp.ok;
  } catch {
    pythonReachable = false;
  }

  return {
    healthy: pythonReachable && bridgeState.healthy,
    state: { ...bridgeState },
    pythonReachable,
  };
}

export function getBridgeState(): Readonly<BridgeState> {
  return { ...bridgeState };
}
