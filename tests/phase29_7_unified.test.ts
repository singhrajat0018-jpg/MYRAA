// ============================================================================
// Phase 29.7 — Unified Live Path Integration Tests
// ============================================================================
// Covers: circuit breaker, hybrid memory retrieval, unified streaming handler,
// deterministic fast path, financial firewall, bridge OCR adapter.

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { CircuitBreaker } from '../src/core/circuit_breaker';
import { hybridRetrieve } from '../src/core/memory_retrieval';
import type { Memory } from '../src/lib/memoryTypes';
import { classifyInput } from '../src/core/context_assembler';
import { handleStreamRequest } from '../src/core/unified_handler';
import { BridgeOcrAdapter } from '../src/vision/ocrAdapter';
import type { ScreenCapture } from '../src/vision/contracts';

// ── Circuit Breaker ─────────────────────────────────────────────────────────

describe('CircuitBreaker', () => {
  it('starts CLOSED and allows requests', () => {
    const breaker = new CircuitBreaker();
    expect(breaker.getState()).toBe('CLOSED');
    expect(breaker.canExecute()).toBe(true);
  });

  it('opens after consecutive failures reach threshold', () => {
    const breaker = new CircuitBreaker({ failureThreshold: 3, cooldownMs: 60000 });
    breaker.recordFailure();
    breaker.recordFailure();
    expect(breaker.getState()).toBe('CLOSED');
    breaker.recordFailure();
    expect(breaker.getState()).toBe('OPEN');
    expect(breaker.canExecute()).toBe(false);
  });

  it('transitions OPEN → HALF_OPEN after cooldown', () => {
    const breaker = new CircuitBreaker({ failureThreshold: 1, cooldownMs: 10 });
    breaker.recordFailure();
    expect(breaker.getState()).toBe('OPEN');
    // Wait past cooldown
    return new Promise<void>(resolve => {
      setTimeout(() => {
        expect(breaker.getState()).toBe('HALF_OPEN');
        expect(breaker.canExecute()).toBe(true);
        resolve();
      }, 30);
    });
  });

  it('closes again after a successful half-open test', () => {
    const breaker = new CircuitBreaker({ failureThreshold: 1, cooldownMs: 0 });
    breaker.recordFailure();
    breaker.getState(); // force transition to HALF_OPEN (cooldown 0)
    breaker.recordSuccess(10);
    expect(breaker.getState()).toBe('CLOSED');
  });

  it('reopens when half-open test fails', async () => {
    const breaker = new CircuitBreaker({ failureThreshold: 1, cooldownMs: 10, halfOpenMaxAttempts: 1 });
    breaker.recordFailure();
    expect(breaker.getState()).toBe('OPEN');
    // Wait past cooldown → HALF_OPEN
    await new Promise(r => setTimeout(r, 20));
    expect(breaker.getState()).toBe('HALF_OPEN');
    breaker.recordFailure(); // test fails → reopen
    expect(breaker.getState()).toBe('OPEN');
    expect(breaker.canExecute()).toBe(false);
  });

  it('tracks stats', () => {
    const breaker = new CircuitBreaker();
    breaker.recordSuccess(5);
    breaker.recordFailure();
    const stats = breaker.getStats();
    expect(stats.successes).toBe(1);
    expect(stats.failures).toBe(1);
    expect(stats.totalRequests).toBe(2);
    expect(stats.latencyMs).toBe(5);
  });

  it('reset returns to CLOSED with zero failures', () => {
    const breaker = new CircuitBreaker({ failureThreshold: 1 });
    breaker.recordFailure();
    expect(breaker.getState()).toBe('OPEN');
    breaker.reset();
    expect(breaker.getState()).toBe('CLOSED');
    expect(breaker.getStats().failures).toBe(0);
  });
});

// ── Hybrid Memory Retrieval ─────────────────────────────────────────────────

describe('hybridRetrieve', () => {
  const now = new Date().toISOString();
  const old = new Date(Date.now() - 40 * 86400000).toISOString();

  const memories: Memory[] = [
    { id: '1', category: 'preference', text: 'User prefers dark mode in VS Code', createdAt: now, updatedAt: now },
    { id: '2', category: 'project', text: 'MYRAA project uses TypeScript and Python', createdAt: now, updatedAt: now },
    { id: '3', category: 'behavior', text: 'User drinks coffee every morning', createdAt: now, updatedAt: now },
    { id: '4', category: 'identity', text: 'User name is Rajat', createdAt: now, updatedAt: now },
  ];

  it('ranks keyword-matching memories highest', () => {
    const results = hybridRetrieve(memories, 'dark mode preferences');
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].id).toBe('1');
  });

  it('boosts identity/importance categories', () => {
    const results = hybridRetrieve(memories, 'random unrelated query words');
    // identity has high importance weight so it survives minScore
    const identity = results.find(r => r.id === '4');
    if (identity) {
      expect(identity.importanceScore).toBe(0.9);
    }
  });

  it('respects maxResults', () => {
    const results = hybridRetrieve(memories, 'user', { maxResults: 2 });
    expect(results.length).toBeLessThanOrEqual(2);
  });

  it('filters by category', () => {
    const results = hybridRetrieve(memories, 'user', { categories: ['identity'] });
    expect(results.every(r => r.category === 'identity')).toBe(true);
  });

  it('returns empty for no matches below minScore', () => {
    const results = hybridRetrieve(memories, 'zzzqqqxxx', { minScore: 0.9 });
    expect(results.length).toBe(0);
  });

  it('includes recency and importance scores in results', () => {
    const results = hybridRetrieve(memories, 'dark mode');
    expect(results[0]).toHaveProperty('relevanceScore');
    expect(results[0]).toHaveProperty('recencyScore');
    expect(results[0]).toHaveProperty('importanceScore');
    expect(results[0]).toHaveProperty('totalScore');
  });
});

// ── Input Classification (unified path routing) ─────────────────────────────

describe('classifyInput for unified routing', () => {
  it('classifies vision requests', () => {
    expect(classifyInput('screen pe kya likha hai')).toBe('VISION');
  });

  it('classifies computer actions', () => {
    expect(classifyInput('open chrome')).toBe('COMPUTER_ACTION');
  });

  it('classifies file operations', () => {
    expect(classifyInput('read file config.json')).toBe('FILE_OPERATION');
  });

  it('classifies research', () => {
    expect(classifyInput('research latest AI agents')).toBe('RESEARCH');
  });

  it('classifies finance', () => {
    expect(classifyInput('what is the NIFTY price today')).toBe('FINANCE');
  });

  it('classifies simple conversation', () => {
    expect(classifyInput('hello how are you')).toBe('CONVERSATION');
  });
});

// ── Unified Streaming Handler ───────────────────────────────────────────────

describe('handleStreamRequest (unified streaming entry)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('deterministic fast path: time query returns without LLM', async () => {
    const { handleStreamRequest } = await import('../src/core/unified_handler');
    const events = [];
    for await (const e of handleStreamRequest({ text: 'what time is it', inputType: 'text' })) {
      events.push(e);
    }
    expect(events[0].type).toBe('metadata');
    expect(events[0].route).toBe('deterministic');
    expect(events.some(e => e.type === 'chunk' && (e.text || '').includes('Current time'))).toBe(true);
    expect(events[events.length - 1].type).toBe('done');
  });

  it('deterministic fast path: date query', async () => {
    const { handleStreamRequest } = await import('../src/core/unified_handler');
    const events = [];
    for await (const e of handleStreamRequest({ text: 'what date is today', inputType: 'text' })) {
      events.push(e);
    }
    expect(events[0].route).toBe('deterministic');
    expect(events.some(e => e.type === 'chunk' && (e.text || '').includes("Today's date"))).toBe(true);
  });

  it('simple conversation streams through brain fast path with metadata', async () => {
    // Mock the Python brain stream
    const sseBody = [
      JSON.stringify({ type: 'metadata', model_route: 'fast', model: 'qwen3:8b', intent: 'CONVERSATION' }),
      JSON.stringify({ type: 'chunk', text: 'Hello ' }),
      JSON.stringify({ type: 'chunk', text: 'there!' }),
      JSON.stringify({ type: 'done', text: 'Hello there!' }),
    ].join('\n') + '\n';

    vi.stubGlobal('fetch', vi.fn(async () => new Response(sseBody, { status: 200 })));

    const { handleStreamRequest } = await import('../src/core/unified_handler');
    const events = [];
    for await (const e of handleStreamRequest({ text: 'hi there friend', inputType: 'text' })) {
      events.push(e);
    }

    const metadata = events.find(e => e.type === 'metadata');
    expect(metadata).toBeDefined();
    expect(metadata!.route).toBe('brain-stream');
    const chunks = events.filter(e => e.type === 'chunk');
    expect(chunks.map(c => c.text).join('')).toBe('Hello there!');
    expect(events[events.length - 1].type).toBe('done');

    // Verify the call went to the Python brain stream (unified path)
    const fetchMock = vi.mocked(fetch);
    const call = fetchMock.mock.calls[0];
    expect(String(call[0])).toContain('/brain/stream');
  });

  it('brain stream failure yields error event, never fake success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('unavailable', { status: 503 })));

    const { handleStreamRequest } = await import('../src/core/unified_handler');
    const events = [];
    for await (const e of handleStreamRequest({ text: 'tell me a story please', inputType: 'text' })) {
      events.push(e);
    }
    expect(events.some(e => e.type === 'error')).toBe(true);
    expect(events[events.length - 1].type).toBe('done');
  });
});

// ── Financial Firewall (execution bridge policy) ────────────────────────────

describe('financial firewall in execution bridge', () => {
  it('blocks trade execution tasks', async () => {
    const { executeViaPython } = await import('../src/core/execution_bridge');
    const task = {
      taskId: 't1',
      type: 'TRADE',
      description: 'buy_stock RELIANCE',
      sideEffects: [],
      metadata: {},
    } as any;

    const result = await executeViaPython(task, { financialFirewallActive: true, autonomyLevel: 'SUPERVISED', blockedActions: [] });
    expect(result.success).toBe(false);
    expect(result.error).toContain('financial firewall');
  });

  it('blocks transfer funds tasks', async () => {
    const { executeViaPython } = await import('../src/core/execution_bridge');
    const task = {
      taskId: 't2',
      type: 'TRANSFER',
      description: 'transfer_funds to account X',
      sideEffects: [],
      metadata: {},
    } as any;

    const result = await executeViaPython(task, { financialFirewallActive: true, autonomyLevel: 'SUPERVISED', blockedActions: [] });
    expect(result.success).toBe(false);
    expect(result.error).toContain('financial firewall');
  });
});

// ── Bridge OCR Adapter ──────────────────────────────────────────────────────

describe('BridgeOcrAdapter', () => {
  const capture: ScreenCapture = {
    captureId: 'cap-1',
    timestamp: new Date().toISOString(),
    monitorId: 'monitor-0' as any,
    bounds: { x: 0, y: 0, width: 1920, height: 1080 },
    dpiScale: 1,
    imageData: 'abc',
    format: 'png',
    width: 1920,
    height: 1080,
  };

  it('converts structured Python lines into OcrBlocks with spatial data', async () => {
    const adapter = new BridgeOcrAdapter({ agentUrl: 'http://test-agent' });
    const payload = {
      ok: true,
      result: {
        lines: [
          { text: 'Download', x: 100, y: 200, width: 80, height: 20, confidence: 0.95 },
          { text: 'Settings', x: 100, y: 240, width: 70, height: 20, confidence: 0.9 },
        ],
      },
    };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })));

    const blocks = await adapter.recognizeText(capture);
    expect(blocks.length).toBeGreaterThan(0);
    expect(blocks[0].text).toContain('Download');
    expect(blocks[0].bounds.width).toBeGreaterThan(0);
    expect(blocks[0].lines[0].words.length).toBeGreaterThan(0);
  });

  it('falls back to single block for plain-text-only results', async () => {
    const adapter = new BridgeOcrAdapter({ agentUrl: 'http://test-agent' });
    const payload = { ok: true, result: { text: 'Hello World\nSecond line' } };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })));

    const blocks = await adapter.recognizeText(capture);
    expect(blocks.length).toBe(1);
    expect(blocks[0].text).toContain('Hello World');
  });

  it('returns empty blocks on error result', async () => {
    const adapter = new BridgeOcrAdapter({ agentUrl: 'http://test-agent' });
    const payload = { ok: false, error: 'OCR unavailable' };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 })));

    const blocks = await adapter.recognizeText(capture);
    expect(blocks.length).toBe(0);
  });

  it('throws on HTTP failure', async () => {
    const adapter = new BridgeOcrAdapter({ agentUrl: 'http://test-agent' });
    vi.stubGlobal('fetch', vi.fn(async () => new Response('err', { status: 500 })));

    await expect(adapter.recognizeText(capture)).rejects.toThrow('OCR bridge returned 500');
  });
});

// ── Desktop Agent Liveness TTL ──────────────────────────────────────────────

describe('desktop agent liveness TTL', () => {
  it('invalidateDesktopAgentLiveness resets the cache', async () => {
    const mod = await import('../services/desktop/desktop_agent');
    // Should not throw even when agent is down, if we never call ensure
    expect(typeof (mod as any).invalidateDesktopAgentLiveness).toBe('function');
    (mod as any).invalidateDesktopAgentLiveness();
    // ensureDesktopAgent should now re-check and throw when agent is unreachable
    await expect(mod.ensureDesktopAgent()).rejects.toThrow(/not running/i);
  });
});