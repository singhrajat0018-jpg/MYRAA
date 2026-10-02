# Phase 29.8 — Live Runtime Verification, Hardware Validation & Real-World QA Report

> **Generated:** 2026-09-05 (IST)
> **Method:** REAL runtime exercised — no mocked services for verification
> **Services:** Node :3000 (tsx server.ts) + Python agent :8765 (uvicorn) + Ollama :11434

---

## 1. Executive Summary

Phase 29.8 ran the real MYRAA stack on the actual Windows machine. Verified **REAL**: deterministic fast path (12ms, no LLM), streaming brain chat (252ms correct answer), 41-chunk streamed LLM conversation, real screen capture (162ms), real OCR via Tesseract (4.8s / 1501 chars from live screen), memory persistence/store, conversation persistence (conv JSON written), ModelDecision consumed (qwen3:4b confirmed on agent route), financial firewall holds (no trade tools exist in Python registry), unified full path (Node→Python→Ollama). Found **5 confirmed real defects** (2 fixed, 3 documented). **Production readiness: LEVEL 3 (Integrated) — fails Phase 30 gate** due to Python `/brain` empty-message defect and TS agent file-task mapping failure.

## 2. Environment
- Windows 11, CMD/PowerShell, VS Code visible
- Node v24.18.0, Python 3.13.14, tsx runner

## 3. Hardware
- NVIDIA GeForce RTX 3050 A Laptop GPU, **4094 MiB VRAM** (612 MiB used idle, 53°C, 8% util)
- RAM 15.6 GB total / **4.1 GB free** (75% used)

## 4. Runtime Services
| Service | Status at probe |
|---|---|
| Ollama :11434 | **UP** — models: qwen3:4b, llama3.2:3b, qwen3.5:4b, gemma3:4b, minimax-m3:cloud |
| Python agent :8765 | **UP** — 89 tools, vision/target/browser/finance subsystems HEALTHY |
| Node server :3000 | **UP** — ReasoningEngine initialized WITH Python bridge |

## 5. Startup Validation
Node log confirms: Agent Routes, World Routes, VisionEngine (BridgeScreenCaptureAdapter — REAL capture), Telemetry Relay started. **Defect 4 found:** `spawnDesktopAgent` logs "require is not defined" (ESM dirname issue) — auto-start fails; agent must be started externally (as spec allows).

## 6. Health Validation (`GET /api/health`)
Honest states verified: server/py/brain/memory/computer/quant/learning/voice/providers **UP**; **vision DEGRADED** ("Using mock adapter" — production gap); world **UNAVAILABLE**; finance **DEGRADED** ("No live market data"); bridge **UP** ("Circuit breaker: CLOSED", 4ms).

## 8. Text E2E
- `/api/chat/stream` "what is 2 plus 2" → **REAL**: 252ms, conversation_id created, route `local_small`, correct "4". Conversation persisted (`conv_1788597347594_i2a7jz.json`).
- `/api/chat` conversational → routed Python brain (`FAST_ANSWER`); **empty message** (Defect 3 — see Failures).

## 9. Fast Path Validation
"what time is it" → `/api/chat` → **route: deterministic, latency 12ms**, "Current time: 2:02:02 pm". **REAL VERIFIED** (no LLM call — classifier short-circuits).

## 10-12. Model Routing
- Agent-path request returned `model: qwen3:4b` — ModelDecision flows to response.
- **Defect 1 (FIXED):** router configured `qwen3:8b` (not installed) → now `qwen3:4b` (FAST) / `qwen3.5:4b` (STRONG+fallback) matching installed models.
- **Defect: vision.** Installed `gemma3:4b` reports NO vision capability; `qwen3.5:4b` has ["vision","completion","tools","thinking"] → **VISION_MODEL fixed to qwen3.5:4b**.

## 13. Real Ollama / 14. GPU
Cold-start streamed conversation: **63.7s to first full response (41 chunks)** — model spawn + VRAM load. Post-warm simple math: **252ms**. GPU at 612 MiB used during idle; no OOM observed. **P1 bottleneck: cold start.**

## 16-18. Real Screen Capture / OCR
- takeScreenshot: **REAL** 162ms ok=true (image returned under `result`).
- readScreen: **REAL OCR VERIFIED** 4820ms ok=true, 1501 chars of live screen text (`"File Edit Selection View Go Cline..."` — actual VS Code window). Tesseract backend works in-process.

## 20-22. Vision→Agent
VISION classification path routes through agent; **full VisionContext→Agent live click not exercised** (safe-click E2E needs controlled fixture; deferred).

## 26. Real Verification / 28. Python Bridge
Bridge calls succeed (screenshot/OCR/systemInfo) with request/result round-trips. writeFile/createFile **REAL-VERIFIED** (121ms/115ms) when given `path` arg.

## 29-31. Circuit Breaker / Liveness
Tested in Phase 29.7 unit suite (state machine + TTL). Real bridge failure-injection NOT performed (agent stayed up).

## 32. Memory REAL E2E
Stored preference `"My favorite editor is VS Code"` via `/api/memories` → persisted (id mto4ta04d57at4). Retrieval chat returned Python FAST_ANSWER wrapper (empty message — Defect 3).

## 36. Finance
`/api/health` reports **DEGRADED "No live market data"** — honest. No price fabricated.

## 38. Learning
Not consumed by router (deferred — matches Phase 29.7 finding).

## 43-44. UI / Avatar / Resources
UI/avatar NOT exercised this session (requires Electron/browser interaction; backend-only validation here). Avatar states still timer-driven (unverified).

## 49-50. Prompt Injection / Financial Firewall
- Python `/execute` for `buy_stock/place_order/execute_trade` → **ALL BLOCKED**: "Unknown tool" — no trade tools exist in registry; firewall holds at Python layer.
- TS bridge also blocks blocked-tools list (unit-verified).
- Prompt-injection test (hostile webpage) NOT run — needs live browser fixture; deferred.

## 54-55. Real vs Mock / Config
- **Vision state DEGRADED: "Using mock adapter"** — production gap: TS VisionEngine uses MockOcrAdapter; real OCR exists only on Python side. **KNOWN defect.**
- `spawnDesktopAgent` fails in tsx/ESM (`require is not defined`). Agent must be started externally.

## 57. Performance Baseline (REAL measured)
| Pipeline | Cold | Warm | Notes |
|---|---|---|---|
| Deterministic fast path | — |12 ms | no LLM |
|Streaming chat (2+2)| — |252 ms | correct "4" |
|Streaming LLM conversation|63.7 s |— |41 chunks, cold model load |
| Real screenshot |— |162 ms | ok |
| Real OCR (Tesseract)|— |4.8 s |1501 chars live screen |
| writeFile via bridge |— |121 ms | path arg |
| createFile via bridge |— |115 ms | path arg |
| Health endpoint |— |~5 ms | bridge 4 ms |

## 67 . ENGINEERING DECISION (spec §78)
1. Can MYRAA run on real Windows? **YES (partial)** — core services + tools work.
2. Can it hear? **UNVERIFIED** (no mic test this session).
3. Can it speak? **UNVERIFIED** (TTS service reachable; no audio device loop).
4. Can it see real screen? **YES** — real capture verified.
5. Can it OCR real screen? **YES** — real Tesseract verified.
6. Understand visual context? **PARTIAL** — VisionContext pipeline exists, mock adapter gap.
7. Safely click/type? **UNVERIFIED** (fixture E2E not run; tools exist and are safe-gated).
8. Verify actions? **PARTIAL** — tool success returned; task-level verification deferred.
9. Recover? **PARTIAL** — breaker + liveness in place; failure-injection not run.
10. Agent execution real tasks? **NO** — TS agent file task returned "task failed" (Defect 5).
11. Memory persists? **YES** — store verified persisted.
12. Model routing works? **YES (fixed)** — qwen3:4b consumed; vision routed to capable model.
13. Bridge recovery? **PARTIAL** — TTL+breaker built; crash recovery not injected.
14. Financial firewall unbypassable? **YES** — no trade tools exist in registry; blocked at both layers.
15. Remaining unverified: mic STT, TTS playback, avatar UI, browser E2E, computer control click, prompt-injection, soak >30min, GPU VRAM during active LLM.
16. Largest bottleneck: **Python `/brain` returns empty message for knowledge questions** (P0 — user sees blank) + **TS agent file-task mapping failure** (P1).
17. Ready for Phase 30? **NO** — Phase 30 gate fails critical items (agent real-task execution, stable user-visible replies). Recommend hardening pass.

## 78. Confirmed Defects
| # | Defect | Severity | Status |
|---|---|---|---|
|1| `qwen3:8b` not installed (router) | P1 | **FIXED** → qwen3:4b / qwen3.5:4b |
|2| `gemma3:4b` lacks vision cap | P1 | **FIXED** → vision=qwen3.5:4b |
|3| Python `/brain` returns success with empty message (FAST_ANSWER) | P0 | **OPEN** — user-facing blank reply |
|4| `spawnDesktopAgent` "require is not defined" in ESM | P3 | **OPEN** — agent starts externally as spec allows |
|5| TS agent path file-task → "task failed" (mapping/extraction gap: Python rejects `filename` arg, TS may send it) | P1 | **OPEN** — Python writeFile/createFile WORK with `path`; TS mapping unreliable |

## 79. Scorecard (0-10, evidence-based)
Real Voice 0 (unverified) · Real Text 8 (252ms stream verified) · Real Agent 2 (task failed) · Real Vision 7 (capture ✓) · Real OCR 9 (1501ch ✓) · Real Computer Control 2 (tools exist, arg-bug) · Verification 3 · Recovery 4 · Memory 8 · Model Routing 8 · Bridge 8 · Security 9 (firewall verified) · UI 0 (unverified) · Avatar 0 · Performance 5 (cold 63s) · Soak 0 (not run)
**Overall practical production-readiness: 4.4 / 10 — LEVEL 3 (Integrated), NOT production.**

## 80. Phase 30 Recommendation
**Do NOT start Phase 30.** Critical gates fail: (a) agent cannot execute real safe task, (b) `/brain` empty-message makes normal replies blank. Recommend Phase 29.9 hardening: fix Python `/brain` response mapping (empty→fallback to stream), fix TS bridge `path` extraction, wire VisionEngine → BridgeOcrAdapter, then re-run ALL real E2E (Tests A-L) including mic/TTS/click fixture.

## Evidence Table (selected)
| System | Test | Env | Result | Latency | Status |
|---|---|---|---|---|---|
| Fast path | "what time" | live Node | Current time | 12ms | REAL VERIFIED |
| Streaming chat | "2+2" | live Node→Python | "4" persisted | 252ms | REAL VERIFIED |
| LLM stream | intro | live Python→Ollama | 41ch real text | 63.7s cold | REAL VERIFIED |
| Screenshot | takeScreenshot | live Python | ok=true img | 162ms | REAL VERIFIED |
| OCR | readScreen | live Python/Tesseract | 1501ch live text | 4.8s | REAL VERIFIED |
| Memory | /api/memories | live Node | stored | — | REAL VERIFIED|
| Firewall | buy_stock et al | live Python | "Unknown tool" | — | REAL VERIFIED (blocked) |
| Agent file task | create file… | live Node→bridge | "task failed" | 2.9s | FAILED |
| Agent task reply | brain chat | live Node→Python | empty message | 44ms | FAILED |