# Phase 29.7 — Unified Live Brain, Model Routing & Closed-Loop Execution Report

> **Generated:** 2026-09-05
> **Status:** COMPLETE (core integration goals)
> **Tests:** 1843/1843 pass (30 new Phase 29.7 tests)
> **TypeScript:** 0 errors
> **Build:** Vite 3.01s clean, server bundle 1.1mb

---

## 1. Executive Summary

Phase 29.7 converted the Phase 29.6 Core from an "architectural option" into the **actual canonical live execution path** for MYRAA. The two remaining direct-to-Python bypasses (chat simple-path and voice simple-path) were eliminated. `ModelDecision` is now consumed exclusively from `RequestRouter` — no duplicate model selection exists. The Python bridge gained real liveness (TTL + failure invalidation) and a full circuit breaker (CLOSED/OPEN/HALF_OPEN). Production OCR now has a real bridge path (`BridgeOcrAdapter` → Python `readScreen`/Tesseract). Memory retrieval upgraded from keyword-overlap to hybrid scoring (keyword + recency + importance).

No duplicate engines were created. FastCore untouched. Financial firewall intact and test-verified. All prior functionality preserved (full regression pass).

---

## 2. Before → After

| Path | Before (29.6) | After (29.7) |
|---|---|---|
| Chat simple conversation | Direct `fetch /brain/stream` in route | `handleStreamRequest()` (unified) |
| Chat complex task | `handleRequest()` (unified) | `handleStreamRequest()` / `handleRequest()` (unified) |
| Voice simple conversation | Direct `fetch /brain/stream` in `server_voice.ts` | `handleStreamRequest()` (unified, sentence-TTS preserved) |
| Voice complex task | `handleRequest()` (unified) | unchanged (unified) |
| ModelDecision | `unified_handler` private `selectModel` duplicate | Canonical from `routeRequest()` only |
| `ensureDesktopAgent()` | Cached liveness forever | 30s TTL + failure invalidation + `invalidateDesktopAgentLiveness()` |
| Python bridge failures | Unbounded hammering | `CircuitBreaker` CLOSED→OPEN→HALF_OPEN, fail-fast |
| OCR | `MockOcrAdapter` only | `BridgeOcrAdapter` (real, Python Tesseract) + mock for tests |
| Memory retrieval | Keyword-overlap only | `hybridRetrieve`: keyword × recency × importance |
| Deterministic fast path | Non-streaming only | Both `handleRequest` and `handleStreamRequest` |

---

## 3. Live Request Paths (verified)

```
VOICE (browser mic → WS STT → transcript)
TEXT  (/api/chat, /api/chat/stream)
  ↓
handleStreamRequest / handleRequest        ← ONE canonical entry
  ↓ classifyInput → deterministic fast path?
  │   YES → response (no LLM)              ← TESTED
  ↓ routeRequest (canonical ModelDecision) ← TESTED
  ├── CONVERSATION → /brain/stream (streaming, brain fast path)
  └── VISION/COMPUTER/FILE/RESEARCH/FINANCE/QUANT/AGENT_TASK
        → ReasoningEngine → executeViaPython (circuit-breaker gated)
          → POST :8765/execute (request_id, task_id)
```

## 4. Model Routing

- `ModelDecision` (model/provider/reason/latencyBudget/contextBudget/modality/fallback/temperature/maxTokens) produced **only** by `src/core/request_router.ts`.
- `unified_handler.resolveModelDecision()` consumes it; the old private `selectModel()` was deleted.
- Stream metadata surfaces the routed model to UI/TTS paths.

## 5. Bridge Health & Resilience

- **`src/core/circuit_breaker.ts`** — state machine with failureThreshold(5), cooldownMs(30s), halfOpenMaxAttempts(2), stats (successes/failures/consecutive/latency/lastSuccess/lastFailure). Wired into `executeViaPython`: fail-fast returns structured retryable error while OPEN; success in HALF_OPEN closes; failure reopens.
- **`services/desktop/desktop_agent.ts`** — `LIVENESS_TTL_MS=30s`; failure paths (`ensureDesktopAgent` check failure, connection-level fetch errors) call `invalidateDesktopAgentLiveness()` so the next call re-verifies.

## 6. Vision / OCR

- `BridgeOcrAdapter` (`src/vision/ocrAdapter.ts`): canonical production OCR contract → Python `/execute {tool: readScreen}` → OcrBlocks with preserved spatial bounds/words/confidence; graceful plain-text fallback; error transparency (throws on HTTP failure, empty on tool error). `MockOcrAdapter` retained **for tests only**.
- `BridgeScreenCaptureAdapter` (existing, real mss capture) unchanged.

## 7. Memory

- `hybridRetrieve` (`src/core/memory_retrieval.ts`): keyword relevance (exact + partial) × recency (<1d=1.0 … >30d=0.2) × importance (identity 0.9 → behavior 0.4). Wired into `assembleRequestContext` via `context_assembler.ts`. Keyword fallback preserved by design (hybrid scoring degrades gracefully). Embedding provider left as swappable extension point (no heavy model added — 4GB VRAM constraint respected).

## 8. Cancellation / Barge-in

- Voice: `generationId` bump on `interrupt()` is now polled (100ms) and mapped to `AbortController.abort()` on the unified stream; done/aborted propagation preserves no-stale-TTS guarantee. Sentence-level TTS unchanged.
- Chat: `/api/chat/cancel` abort controller now flows through `handleStreamRequest` options.

## 9. Security & Firewall

- Financial firewall (`BLOCKED_TOOLS` + `PolicyContext.financialFirewallActive`) unchanged and **tested** (buy_stock, transfer_funds blocked).
- All tool execution still flows Python PermissionManager + CommandDispatcher.

## 10. Verification Matrix (honest classification)

| Item | Status |
|---|---|
| Chat unified path | IMPLEMENTED + UNIT TESTED (mocked brain) |
| Voice unified path | IMPLEMENTED (compile-verified; E2E needs live agent) |
| ModelDecision consumed | IMPLEMENTED + UNIT TESTED |
| Circuit breaker | IMPLEMENTED + UNIT TESTED (state machine) |
| Liveness TTL | IMPLEMENTED + UNIT TESTED |
| Hybrid memory | IMPLEMENTED + UNIT TESTED |
| Bridge OCR | IMPLEMENTED + UNIT TESTED (mocked HTTP) |
| Deterministic fast path | IMPLEMENTED + UNIT TESTED |
| REAL Windows execution / OCR / vision | **UNVERIFIED** (requires live Python agent run) |
| REAL GPU/model routing | UNVERIFIED (requires live Ollama) |

## 11. Remaining / Deferred (documented, not hidden)

1. **E2E with live Python agent + Ollama not run** in this session (Tests 1–12 of spec need live services; unit/integration coverage is mocked-HTTP level).
2. **ComputerControlEngine** still not instantiated in the server path (was deferred in 29.6; not blocking the core chat/voice/execution flow).
3. **Embedding-based retrieval** — provider interface reserved; not implemented (deferred per hardware budget).
4. **Learning-signal consumption by router** — LearningSignals contract exists in context; router does not yet bias ModelDecision from validated learning signals.
5. **Idempotency keys** — bridge sends `request_id`/`task_id`; full idempotency-key dedup on Python side is future work.

## 12. Exact Results

- **Test count:** 1843 passed / 0 failed (18 files), up from 1813 (+30 new)
- **TypeScript:** `tsc --noEmit` → 0 errors
- **Build:** `npm run build` → Vite 3.01s, dist 407.74 kB (gzip 124.68 kB), server.cjs 1.1mb
- **Files changed:** `services/desktop/desktop_agent.ts`, `src/core/unified_handler.ts`, `src/core/context_assembler.ts`, `src/core/memory_retrieval.ts` (new integration), `src/core/execution_bridge.ts` (breaker wiring), `src/core/circuit_breaker.ts`, `server/routes/chat.ts`, `server_voice.ts`, `src/vision/ocrAdapter.ts`, `tests/phase29_7_unified.test.ts` (new)

## 13. Phase 30 Readiness

Primitives now in place for Long-Horizon Autonomy: durable requestId/traceId/taskId/actionId flow, circuit-breaker-guarded bridge, cancellation propagation, structured typed errors, unified streaming events, hybrid memory, canonical health endpoints.