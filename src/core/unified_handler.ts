// ============================================================================
// MYRAA Unified Request Handler — The ONE canonical entry point
// ============================================================================

import type { MyraaRequestContext, ModelDecision } from './contracts';
import { classifyInput } from './context_assembler';
import { assembleRequestContext } from './context_assembler';
import { routeRequest, MODEL_ROUTES, type RoutingDecision } from './request_router';
import { loadMemories, formatSystemInstructionsWithMemories } from '../../server_memory';
import { generateRequestId, generateTraceId } from './contracts';

const DESKTOP_AGENT_URL = process.env.DESKTOP_AGENT_URL || 'http://127.0.0.1:8765';

// ── Event Types for Streaming ───────────────────────────────────────────────

export type UnifiedEventType =
  | 'metadata'
  | 'chunk'
  | 'done'
  | 'error'
  | 'tool_call'
  | 'verification'
  | 'learning';

export interface UnifiedEvent {
  readonly type: UnifiedEventType;
  readonly text?: string;
  readonly requestId?: string;
  readonly traceId?: string;
  readonly route?: string;
  readonly model?: string;
  readonly intent?: string;
  readonly latencyMs?: number;
  readonly message?: string;
  readonly tool?: string;
  readonly result?: unknown;
  readonly aborted?: boolean;
}

// ── Request Handler Options ─────────────────────────────────────────────────

export interface HandleRequestOptions {
  readonly text: string;
  readonly inputType: 'voice' | 'text' | 'image';
  readonly conversationId?: string;
  readonly conversationHistory?: readonly { role: string; text: string }[];
  readonly model?: string;
  readonly abortSignal?: AbortSignal;
}

export interface HandleRequestResult {
  readonly requestId: string;
  readonly traceId: string;
  readonly response: string;
  readonly route: string;
  readonly model?: string;
  readonly latencyMs: number;
  readonly classification: string;
}

// ── The Unified Handler ─────────────────────────────────────────────────────

// Lazy singleton — initialized on first request
let reasoningEngine: any = null;
let visionEngine: any = null;

export function setReasoningEngine(engine: any) { reasoningEngine = engine; }
export function setVisionEngineRef(engine: any) { visionEngine = engine; }

// ── Memory Assembly ─────────────────────────────────────────────────────────

async function assembleMemoryContext(input: string): Promise<string | undefined> {
  try {
    const memories = await loadMemories();
    if (!memories || memories.length === 0) return undefined;
    return formatSystemInstructionsWithMemories('', memories) || undefined;
  } catch {
    return undefined;
  }
}

// ── Model Decision (Phase 29.7: canonical — from RequestRouter) ─────────────
// The unified handler no longer has its own model selection. ModelDecision
// comes exclusively from routeRequest() so there is ONE routing system.

function resolveModelDecision(ctx: MyraaRequestContext): ModelDecision | undefined {
  const decision = routeRequest(ctx);
  return decision.modelDecision;
}

// ── Deterministic Fast Path ─────────────────────────────────────────────────

function getDeterministicResponse(input: string): string | null {
  const lower = input.toLowerCase().trim();
  if (/^(what time|current time|time kya|samay|clock)/i.test(lower)) {
    return `Current time: ${new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}`;
  }
  if (/^(what date|current date|date kya|aaj ki date)/i.test(lower)) {
    return `Today's date: ${new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}`;
  }
  if (/^(system info|system information|system details)/i.test(lower)) {
    return `System: ${process.platform} ${process.arch}, Node ${process.version}, uptime ${Math.floor(process.uptime())}s`;
  }
  return null;
}

// ── Agent Path (Complex Tasks) ──────────────────────────────────────────────

async function handleViaAgent(
  text: string,
  ctx: MyraaRequestContext,
  abortSignal?: AbortSignal,
): Promise<string> {
  if (!reasoningEngine) {
    // Fallback: go directly to Python brain
    return handleViaBrain(text, ctx, abortSignal);
  }

  try {
    const result = await reasoningEngine.processRequest(text, {
      conversationId: ctx.conversationId,
      conversationHistory: ctx.conversation as any[],
    });
    return result?.summary || result?.response || 'Agent processed the request.';
  } catch (err) {
    console.error('[UnifiedHandler] Agent processing failed, falling back to brain:', err);
    return handleViaBrain(text, ctx, abortSignal);
  }
}

// ── Brain Path (Simple Conversational) ──────────────────────────────────────

async function handleViaBrain(
  text: string,
  ctx: MyraaRequestContext,
  abortSignal?: AbortSignal,
): Promise<string> {
  const memoryContext = await assembleMemoryContext(text);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);

  // Link external abort signal
  if (abortSignal) {
    abortSignal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(`${DESKTOP_AGENT_URL}/brain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        context: {
          conversation_history: (ctx.conversation || []).slice(-10),
          memory_context: memoryContext,
        },
        request_id: ctx.requestId,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      return `Brain service returned ${response.status}`;
    }

    const data = await response.json() as { ok: boolean; result?: any; error?: string };
    if (data.ok && data.result) {
      return typeof data.result === 'string' ? data.result : JSON.stringify(data.result);
    }
    return data.error || 'No response from brain.';
  } catch (err: any) {
    clearTimeout(timeout);
    if (err.name === 'AbortError') return 'Request cancelled.';
    return `Brain error: ${err.message}`;
  }
}

// ── Brain Streaming Path ────────────────────────────────────────────────────

export async function* handleStreamViaBrain(
  text: string,
  ctx: MyraaRequestContext,
  abortSignal?: AbortSignal,
): AsyncGenerator<UnifiedEvent> {
  const memoryContext = await assembleMemoryContext(text);

  yield { type: 'metadata', requestId: ctx.requestId, traceId: ctx.traceId, route: 'brain-stream', model: MODEL_ROUTES.FAST, intent: ctx.classification };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);
  if (abortSignal) abortSignal.addEventListener('abort', () => controller.abort());

  try {
    const response = await fetch(`${DESKTOP_AGENT_URL}/brain/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        context: {
          conversation_history: (ctx.conversation || []).slice(-10),
          memory_context: memoryContext,
        },
        request_id: ctx.requestId,
      }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      yield { type: 'error', message: `Brain returned ${response.status}` };
      yield { type: 'done', text: '' };
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      yield { type: 'error', message: 'No response body' };
      yield { type: 'done', text: '' };
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let fullResponse = '';

    while (true) {
      if (controller.signal.aborted) {
        yield { type: 'done', text: fullResponse, aborted: true };
        return;
      }

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const event = JSON.parse(line);
          if (event.type === 'chunk' && event.text) {
            fullResponse += event.text;
            yield { type: 'chunk', text: event.text };
          } else if (event.type === 'done') {
            fullResponse = event.text || fullResponse;
          } else if (event.type === 'metadata') {
            yield { type: 'metadata', route: event.model_route, model: event.model, intent: event.intent };
          } else if (event.type === 'error') {
            yield { type: 'error', message: event.message };
          }
        } catch { /* skip malformed lines */ }
      }
    }

    yield { type: 'done', text: fullResponse };
  } catch (err: any) {
    clearTimeout(timeout);
    if (err.name === 'AbortError') {
      yield { type: 'done', text: '', aborted: true };
    } else {
      yield { type: 'error', message: err.message };
      yield { type: 'done', text: '' };
    }
  }
}

// ── Main Entry Point ────────────────────────────────────────────────────────

export async function handleRequest(
  options: HandleRequestOptions,
): Promise<HandleRequestResult> {
  const start = Date.now();
  const requestId = generateRequestId();
  const traceId = generateTraceId();

  const { text, inputType, conversationHistory = [], conversationId } = options;

  // 1. Classify
  const classification = classifyInput(text);

  // 2. Check deterministic fast path
  const deterministicResponse = getDeterministicResponse(text);
  if (deterministicResponse) {
    return {
      requestId,
      traceId,
      response: deterministicResponse,
      route: 'deterministic',
      latencyMs: Date.now() - start,
      classification,
    };
  }

  // 3. Build context
  const ctx: MyraaRequestContext = {
    requestId,
    traceId,
    input: text,
    inputType,
    classification,
    conversationId,
    conversation: conversationHistory.map(t => ({ role: t.role as 'user' | 'assistant' | 'system', content: t.text })),
    timestamps: { received: new Date().toISOString() },
  };

  // 4. Route — ModelDecision is canonical from RequestRouter (Phase 29.7)
  const modelDecision = resolveModelDecision(ctx);

  // 5. Execute
  let route: string;
  let response: string;

  switch (classification) {
    case 'VISION':
    case 'COMPUTER_ACTION':
    case 'AGENT_TASK':
    case 'FILE_OPERATION':
      // Complex tasks → Agent path
      route = 'agent';
      response = await handleViaAgent(text, ctx, options.abortSignal);
      break;

    case 'RESEARCH':
    case 'FINANCE':
    case 'QUANT':
      // Specialist tasks → Agent with specialist routing
      route = 'agent-specialist';
      response = await handleViaAgent(text, ctx, options.abortSignal);
      break;

    default:
      // Simple conversation → Brain fast path
      route = 'brain-fast';
      response = await handleViaBrain(text, ctx, options.abortSignal);
      break;
  }

  return {
    requestId,
    traceId,
    response,
    route,
    model: modelDecision?.model,
    latencyMs: Date.now() - start,
    classification,
  };
}

// ── Unified Streaming Entry Point (Phase 29.7) ──────────────────────────────
// ONE canonical streaming path for chat AND voice. Simple conversation streams
// through the brain fast path; complex tasks use the agent path. No caller
// should fetch /brain/stream directly anymore.

export async function* handleStreamRequest(
  options: HandleRequestOptions,
): AsyncGenerator<UnifiedEvent> {
  const start = Date.now();
  const requestId = generateRequestId();
  const traceId = generateTraceId();
  const { text, inputType, conversationHistory = [], conversationId } = options;

  // 1. Classify
  const classification = classifyInput(text);

  // 2. Deterministic fast path — no LLM
  const deterministicResponse = getDeterministicResponse(text);
  if (deterministicResponse) {
    yield { type: 'metadata', requestId, traceId, route: 'deterministic', intent: classification };
    yield { type: 'chunk', text: deterministicResponse };
    yield { type: 'done', text: deterministicResponse };
    return;
  }

  // 3. Build context
  const ctx: MyraaRequestContext = {
    requestId,
    traceId,
    input: text,
    inputType,
    classification,
    conversationId,
    conversation: conversationHistory.map(t => ({ role: t.role as 'user' | 'assistant' | 'system', content: t.text })),
    timestamps: { received: new Date().toISOString() },
  };

  // 4. Route — canonical ModelDecision
  const routing = routeRequest(ctx);
  const modelDecision = routing.modelDecision;

  const isComplexTask = ['VISION', 'COMPUTER_ACTION', 'AGENT_TASK', 'FILE_OPERATION', 'RESEARCH', 'FINANCE', 'QUANT'].includes(classification);

  if (isComplexTask) {
    // Complex: agent path (non-streaming result, emitted as one chunk)
    yield { type: 'metadata', requestId, traceId, route: 'agent', model: modelDecision?.model, intent: classification };
    const result = await handleViaAgent(text, ctx, options.abortSignal);
    yield { type: 'chunk', text: result };
    yield { type: 'done', text: result };
    return;
  }

  // Simple conversation: stream through brain fast path (unified)
  yield* handleStreamViaBrain(text, ctx, options.abortSignal);
}
