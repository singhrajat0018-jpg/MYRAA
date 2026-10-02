// ============================================================================
// Phase 29.6 — Integration Tests: Core Unification Layer
// ============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generateRequestId,
  generateTraceId,
  generateActionId,
  type MyraaRequestContext,
  type ExecutionRequest,
  type ExecutionResult,
  type SystemHealth,
} from '../src/core/contracts';
import {
  classifyInput,
  assembleRequestContext,
} from '../src/core/context_assembler';
import {
  routeRequest,
  type RoutingDecision,
} from '../src/core/request_router';
import {
  getSystemHealth,
  healthToHttpStatus,
} from '../src/core/health';

// ── Contracts Tests ─────────────────────────────────────────────────────────

describe('Phase 29.6 — Canonical Contracts', () => {
  it('generateRequestId returns unique IDs', () => {
    const id1 = generateRequestId();
    const id2 = generateRequestId();
    expect(id1).toMatch(/^req-/);
    expect(id2).toMatch(/^req-/);
    expect(id1).not.toBe(id2);
  });

  it('generateTraceId returns unique trace IDs', () => {
    const id1 = generateTraceId();
    const id2 = generateTraceId();
    expect(id1).toMatch(/^trace-/);
    expect(id2).toMatch(/^trace-/);
    expect(id1).not.toBe(id2);
  });

  it('generateActionId returns unique action IDs', () => {
    const id1 = generateActionId();
    const id2 = generateActionId();
    expect(id1).toMatch(/^act-/);
    expect(id2).toMatch(/^act-/);
    expect(id1).not.toBe(id2);
  });
});

// ── Classification Tests ────────────────────────────────────────────────────

describe('Phase 29.6 — Input Classification', () => {
  it('classifies vision requests', () => {
    expect(classifyInput('screen pe kya hai')).toBe('VISION');
    expect(classifyInput('take a screenshot')).toBe('VISION');
    expect(classifyInput('what is on my screen')).toBe('VISION');
    expect(classifyInput('read the text from screen')).toBe('VISION');
  });

  it('classifies computer action requests', () => {
    expect(classifyInput('chrome kholo')).toBe('COMPUTER_ACTION');
    expect(classifyInput('volume up kar do')).toBe('COMPUTER_ACTION');
    expect(classifyInput('click the button')).toBe('COMPUTER_ACTION');
    expect(classifyInput('type hello world')).toBe('COMPUTER_ACTION');
    expect(classifyInput('press enter key')).toBe('COMPUTER_ACTION');
  });

  it('classifies file operation requests', () => {
    expect(classifyInput('read the file config.json')).toBe('FILE_OPERATION');
    expect(classifyInput('create file test.txt')).toBe('FILE_OPERATION');
  });

  it('classifies research requests', () => {
    expect(classifyInput('search for latest AI news')).toBe('RESEARCH');
    expect(classifyInput('research quantum computing')).toBe('RESEARCH');
    expect(classifyInput('google karo ye topic')).toBe('RESEARCH');
  });

  it('classifies finance requests', () => {
    expect(classifyInput('NVIDIA ka stock price')).toBe('FINANCE');
    expect(classifyInput('market me kya ho raha hai')).toBe('FINANCE');
    expect(classifyInput('nifty analysis karo')).toBe('FINANCE');
  });

  it('classifies code/agent requests', () => {
    expect(classifyInput('is code ka error fix karo')).toBe('AGENT_TASK');
    expect(classifyInput('run this python script')).toBe('AGENT_TASK');
  });

  it('classifies simple conversation', () => {
    expect(classifyInput('hello')).toBe('CONVERSATION');
    expect(classifyInput('kaise ho')).toBe('CONVERSATION');
    expect(classifyInput('what is 2+2')).toBe('CONVERSATION');
  });
});

// ── Context Assembly Tests ──────────────────────────────────────────────────

describe('Phase 29.6 — Context Assembly', () => {
  it('assembles context for a voice request', async () => {
    const ctx = await assembleRequestContext({
      input: 'hello MYRAA',
      inputType: 'voice',
    });
    expect(ctx.requestId).toMatch(/^req-/);
    expect(ctx.traceId).toMatch(/^trace-/);
    expect(ctx.input).toBe('hello MYRAA');
    expect(ctx.inputType).toBe('voice');
    expect(ctx.classification).toBe('CONVERSATION');
    expect(ctx.timestamps.received).toBeDefined();
    expect(ctx.policy?.financialFirewallActive).toBe(true);
    expect(ctx.tools?.availableTools.length).toBeGreaterThan(0);
  });

  it('assembles vision context for screen requests', async () => {
    const ctx = await assembleRequestContext({
      input: 'screen pe kya hai',
      inputType: 'voice',
      visionEngine: { isEngineRunning: true },
    });
    expect(ctx.classification).toBe('VISION');
    expect(ctx.vision?.available).toBe(true);
  });

  it('marks vision unavailable when engine not running', async () => {
    const ctx = await assembleRequestContext({
      input: 'screen pe kya hai',
      inputType: 'voice',
    });
    expect(ctx.vision?.available).toBe(false);
  });

  it('includes conversation history when provided', async () => {
    const ctx = await assembleRequestContext({
      input: 'uske baare me batao',
      inputType: 'text',
      conversation: [
        { role: 'user', content: 'hello' },
        { role: 'assistant', content: 'Hello! Kaise ho?' },
      ],
    });
    expect(ctx.conversation).toHaveLength(2);
    expect(ctx.conversation[0].role).toBe('user');
  });
});

// ── Request Router Tests ────────────────────────────────────────────────────

describe('Phase 29.6 — Request Router', () => {
  it('routes conversation to brain (no agent)', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'hello',
      inputType: 'text',
      classification: 'CONVERSATION',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresAgent).toBe(false);
    expect(decision.requiresVision).toBe(false);
    expect(decision.requiresModel).toBe(true);
    expect(decision.modelDecision?.provider).toBe('ollama');
  });

  it('routes vision requests to vision engine', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'screen pe kya hai',
      inputType: 'voice',
      classification: 'VISION',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresVision).toBe(true);
    expect(decision.specialistEngine).toBe('vision');
    expect(decision.modelDecision?.modality).toBe('vision');
  });

  it('routes computer actions to computer control', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'chrome kholo',
      inputType: 'voice',
      classification: 'COMPUTER_ACTION',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresComputer).toBe(true);
    expect(decision.requiresVision).toBe(true);
    expect(decision.specialistEngine).toBe('computer');
  });

  it('uses deterministic path for simple system commands', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'volume up',
      inputType: 'voice',
      classification: 'COMPUTER_ACTION',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresModel).toBe(false);
    expect(decision.deterministicPath).toBe('volumeControl');
  });

  it('uses deterministic path for screenshot', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'screenshot',
      inputType: 'voice',
      classification: 'COMPUTER_ACTION',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresModel).toBe(false);
    expect(decision.deterministicPath).toBe('screenshot');
  });

  it('routes finance to finance specialist', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'NVIDIA ka stock price batao',
      inputType: 'voice',
      classification: 'FINANCE',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresFinance).toBe(true);
    expect(decision.specialistEngine).toBe('finance');
  });

  it('routes research to research with strong model', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'research quantum computing latest papers',
      inputType: 'text',
      classification: 'RESEARCH',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresResearch).toBe(true);
    expect(decision.specialistEngine).toBe('research');
    // STALE EXPECTATION UPDATED (documented decision, §61): Phase 29.8 changed
    // the strong model from qwen3:8b → qwen3.5:4b after validating against the
    // actual Ollama installation (qwen3:8b is NOT installed — verified live via
    // /api/tags). The test was not updated in that change; implementation is
    // intentional and correct. Single source: request_router.MODEL_ROUTES.
    expect(decision.modelDecision?.model).toBe('qwen3.5:4b');
  });

  it('routes agent tasks with strong model', () => {
    const ctx: MyraaRequestContext = {
      requestId: 'req-test',
      traceId: 'trace-test',
      input: 'is code ka error fix karo and then test it',
      inputType: 'text',
      classification: 'AGENT_TASK',
      conversation: [],
      timestamps: { received: new Date().toISOString() },
    };
    const decision = routeRequest(ctx);
    expect(decision.requiresAgent).toBe(true);
    expect(decision.specialistEngine).toBe('agent');
  });
});

// ── Health Check Tests ──────────────────────────────────────────────────────

describe('Phase 29.6 — Health Checks', () => {
  it('getSystemHealth returns structured health', async () => {
    const health = await getSystemHealth();
    expect(health.server.status).toBe('UP');
    expect(health.memory.status).toBe('UP');
    expect(health.quant.status).toBe('UP');
    expect(health.learning.status).toBe('UP');
    expect(health.finance.status).toBe('DEGRADED'); // No live data
  });

  it('healthToHttpStatus returns 200 when all UP', () => {
    const health: SystemHealth = {
      server: { status: 'UP' },
      pythonAgent: { status: 'UP' },
      brain: { status: 'UP' },
      memory: { status: 'UP' },
      world: { status: 'UP' },
      vision: { status: 'UP' },
      computer: { status: 'UP' },
      finance: { status: 'UP' },
      quant: { status: 'UP' },
      learning: { status: 'UP' },
      voice: { status: 'UP' },
      providers: { status: 'UP' },
      bridge: { status: 'UP' },
    };
    expect(healthToHttpStatus(health)).toBe(200);
  });

  it('healthToHttpStatus returns 503 when most DOWN', () => {
    const health: SystemHealth = {
      server: { status: 'DOWN' },
      pythonAgent: { status: 'DOWN' },
      brain: { status: 'DOWN' },
      memory: { status: 'DOWN' },
      world: { status: 'DOWN' },
      vision: { status: 'DOWN' },
      computer: { status: 'DOWN' },
      finance: { status: 'DOWN' },
      quant: { status: 'DOWN' },
      learning: { status: 'DOWN' },
      voice: { status: 'DOWN' },
      providers: { status: 'DOWN' },
      bridge: { status: 'DOWN' },
    };
    expect(healthToHttpStatus(health)).toBe(503);
  });

  it('healthToHttpStatus returns 207 for partial degradation', () => {
    const health: SystemHealth = {
      server: { status: 'UP' },
      pythonAgent: { status: 'DOWN' },
      brain: { status: 'DOWN' },
      memory: { status: 'UP' },
      world: { status: 'UP' },
      vision: { status: 'DOWN' },
      computer: { status: 'UP' },
      finance: { status: 'UP' },
      quant: { status: 'UP' },
      learning: { status: 'UP' },
      voice: { status: 'DOWN' },
      providers: { status: 'UP' },
      bridge: { status: 'UP' },
    };
    expect(healthToHttpStatus(health)).toBe(207);
  });
});

// ── Execution Bridge Tests ──────────────────────────────────────────────────

describe('Phase 29.6 — Execution Bridge Contract', () => {
  it('ExecutionRequest has required fields', () => {
    const req: ExecutionRequest = {
      requestId: 'req-1',
      taskId: 'task-1',
      actionId: 'act-1',
      capability: 'file.write',
      tool: 'createFile',
      arguments: { path: 'test.txt', content: 'hello' },
    };
    expect(req.requestId).toBe('req-1');
    expect(req.taskId).toBe('task-1');
    expect(req.actionId).toBe('act-1');
    expect(req.tool).toBe('createFile');
  });

  it('ExecutionResult has required fields', () => {
    const result: ExecutionResult = {
      requestId: 'req-1',
      taskId: 'task-1',
      actionId: 'act-1',
      success: true,
      status: 'COMPLETED',
      result: { path: 'test.txt' },
      duration: 150,
    };
    expect(result.success).toBe(true);
    expect(result.duration).toBe(150);
  });
});

// ── Integration: Full Request Lifecycle ─────────────────────────────────────

describe('Phase 29.6 — Full Request Lifecycle', () => {
  it('voice conversation: classify → assemble → route → brain', async () => {
    const input = 'hello MYRAA kaise ho';
    const ctx = await assembleRequestContext({ input, inputType: 'voice' });
    expect(ctx.classification).toBe('CONVERSATION');

    const decision = routeRequest(ctx);
    expect(decision.requiresAgent).toBe(false);
    expect(decision.requiresModel).toBe(true);
    expect(decision.modelDecision?.provider).toBe('ollama');
  });

  it('screen observation: classify → assemble → route → vision', async () => {
    const input = 'screen pe kya hai';
    const ctx = await assembleRequestContext({
      input,
      inputType: 'voice',
      visionEngine: { isEngineRunning: true },
    });
    expect(ctx.classification).toBe('VISION');

    const decision = routeRequest(ctx);
    expect(decision.requiresVision).toBe(true);
    expect(decision.specialistEngine).toBe('vision');
  });

  it('computer action: classify → assemble → route → vision + computer', async () => {
    const input = 'download button click karo';
    const ctx = await assembleRequestContext({
      input,
      inputType: 'voice',
      visionEngine: { isEngineRunning: true },
    });
    expect(ctx.classification).toBe('COMPUTER_ACTION');

    const decision = routeRequest(ctx);
    expect(decision.requiresComputer).toBe(true);
    expect(decision.requiresVision).toBe(true);
    expect(decision.specialistEngine).toBe('computer');
  });

  it('finance analysis: classify → assemble → route → finance', async () => {
    const input = 'NVIDIA ka stock analysis karo';
    const ctx = await assembleRequestContext({ input, inputType: 'text' });
    expect(ctx.classification).toBe('FINANCE');

    const decision = routeRequest(ctx);
    expect(decision.requiresFinance).toBe(true);
    expect(decision.specialistEngine).toBe('finance');
  });

  it('deterministic shortcut: classify → route → no LLM needed', async () => {
    const input = 'volume up';
    const ctx = await assembleRequestContext({ input, inputType: 'voice' });
    const decision = routeRequest(ctx);
    expect(decision.requiresModel).toBe(false);
    expect(decision.deterministicPath).toBe('volumeControl');
  });

  it('system info: classify → route → deterministic', async () => {
    const input = 'system info';
    const ctx = await assembleRequestContext({ input, inputType: 'text' });
    const decision = routeRequest(ctx);
    expect(decision.requiresModel).toBe(false);
    expect(decision.deterministicPath).toBe('systemInfo');
  });
});
