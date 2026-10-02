# Phase 29.6 — Core Unification & System Hardening Report

> **Generated:** 2026-09-05  
> **Status:** COMPLETE  
> **Tests:** 1813/1813 pass (34 new)  
> **TS:** 0 errors  
> **Build:** 4.06s clean

---

## Executive Summary

Phase 29.6 transformed MYRAA from 12+ isolated engines into ONE integrated system. A canonical request lifecycle was implemented: classify → assemble context → route → execute → respond. The TS Agent now bridges to the Python Desktop Agent for real execution (not fake success). All subsystems are health-monitored. Deterministic shortcuts bypass LLM for simple commands.

---

## What Was Built

### 1. Canonical Contracts (`src/core/contracts.ts`)
- `MyraaRequestContext` — unified request envelope with requestId, traceId, classification, memory, vision, tools, policy
- `ExecutionRequest` / `ExecutionResult` — typed execution lifecycle
- `SystemHealth` — 14-subsystem health snapshot
- `ModelDecision` / `LearningSignals` — model selection and learning data types

### 2. Context Assembler (`src/core/context_assembler.ts`)
- `classifyInput()` — regex-based classification into 8 categories: VISION, COMPUTER_ACTION, FILE_OPERATION, RESEARCH, FINANCE, QUANT, AGENT_TASK, CONVERSATION
- `assembleRequestContext()` — builds full `MyraaRequestContext` with selective assembly (only fetches memory for relevant inputs, only checks vision for vision/computer tasks)
- Memory retrieval with keyword-relevance scoring

### 3. Request Router (`src/core/request_router.ts`)
- `routeRequest()` — maps classification to routing decision with specialist engine assignment
- Deterministic shortcuts: volume/system/screenshot/app-open bypass LLM entirely
- Model selection: `qwen3:8b` for conversation, `gemma3:4b` for vision, strong model for complex tasks

### 4. Execution Bridge (`src/core/execution_bridge.ts`)
- `executeViaPython()` — real TS Agent → Python `POST /execute` bridge
- Policy enforcement: financial firewall blocks trade execution
- Tool mapping: PlanTask description → Python tool (readFile, createFile, searchWeb, openApplication, etc.)
- Health tracking: latency, failure rate, bridge state
- Retryable error detection (timeout, ECONNREFUSED, etc.)

### 5. System Health (`src/core/health.ts`)
- `getSystemHealth()` — pings Python agent, Ollama, checks all engine states
- `healthToHttpStatus()` — 200/207/503 based on subsystem health distribution
- `/api/health` endpoint registered in server.ts

### 6. Server Integration (`server.ts`)
- ReasoningEngine now has `taskExecutor` wired to Python bridge (was fake-succeed before)
- `spawnDesktopAgent()` called at startup (was dead code)
- `ComputerControlEngine` still not instantiated (deferred — not blocking core flow)

---

## Integration Points Verified

| Path | Before | After |
|------|--------|-------|
| TS Agent task execution | Fake success (no-op) | Real Python POST /execute |
| `spawnDesktopAgent()` | Dead code | Called at startup |
| Memory context to brain | Wired but not surfaced | Surfaced in MyraaRequestContext |
| Vision engine availability | Hardcoded | Dynamic from engine state |
| Health monitoring | Per-endpoint only | Unified `/api/health` |
| Request classification | None (direct brain dispatch) | 8-category classifier |
| Deterministic shortcuts | None | Volume/screenshot/system bypass LLM |

---

## Test Coverage (34 new tests)

| Module | Tests | Coverage |
|--------|-------|----------|
| Canonical Contracts | 3 | ID generation uniqueness |
| Input Classification | 6 | Vision, computer, file, research, finance, conversation |
| Context Assembly | 4 | Voice, vision availability, conversation history |
| Request Router | 7 | All classification paths, deterministic shortcuts |
| Health Checks | 4 | Status mapping, HTTP codes |
| Execution Bridge | 2 | Contract validation |
| Full Lifecycle | 6 | End-to-end classify→assemble→route chains |

---

## Known Limitations (Deferred)

1. **ComputerControlEngine not instantiated** — requires pyautogui bridge, deferred to Phase 29.7
2. **ReasoningEngine not wired into chat/voice routes** — voice pipeline still calls Python `/brain/stream` directly (functional, just not using the unified router)
3. **MockOcrAdapter only** — no real OCR adapter for vision (uses Python `readScreen` tool)
4. **`ensureDesktopAgent()` caches liveness forever** — no invalidation/retry logic
5. **Context assembler uses simple keyword overlap** — no embedding-based retrieval
6. **Model decision not actually consumed** — router produces `ModelDecision` but brain/voice still use their own model selection

---

## Next Steps (Phase 29.7 candidates)

- Wire ReasoningEngine into chat route and voice pipeline processTranscriptStream
- Instantiate ComputerControlEngine with Python bridge adapter
- Add liveness re-check to `ensureDesktopAgent()`
- Wire model decision into brain/voice model selection
- Embed-based memory retrieval (replace keyword overlap)
- Circuit breaker for Python bridge (track failures, auto-recover)
