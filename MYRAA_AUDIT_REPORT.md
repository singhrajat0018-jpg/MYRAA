# MYRAA 0→100 AUDIT REPORT

Date: 2026-09-19. Method: read-only inspection first (plus 3 parallel research
subagents for voice/memory-UI), then evidence-backed fixes only. Nothing was
assumed from prior reports; every load-bearing claim below was re-verified
against live code. Items marked NOT LIVE VERIFIED were not executed against
running hardware/APIs.

Prior browser pass (separate): `BROWSER_ARCHITECTURE_AUDIT.md` (audit) +
`MYRAA_BROWSER_FINAL_REPORT.md` (fixes: validation OR-args, 172.16/12 SSRF
parity, model strings, stale Playwright refs, dormant-iframe sandbox).

## 1. Executive summary

MYRAA is a real, substantial system: Gemini Live voice (sole engine, verified),
Python desktop agent with 89 permission-gated tools, rule-based brain pipeline,
continuous vision, dual-but-diverged memory, Electron shell, and a live
MyraaCompanion UI. This pass found 2 P0s (one live fake-success endpoint, one
historical secret leak), fixed the fake-success endpoint plus 4 more genuine
defects, untracked PII-bearing data files from git, and catalogued the rest
with severity and manual tests. No subsystem was rewritten; no forbidden
dependency introduced; protected systems untouched.

## 2. Actual architecture

Electron (main.cjs: splash → backend dist/server.cjs → window localhost:3000;
external links → shell.openExternal) → Node :3000 (Express, /api/*, WS /live
voice bridge, WS /telemetry relay) → Python :8765 (FastAPI: /execute,
/brain, /voice/*, /health/*, /telemetry/*; CommandDispatcher →
ValidationLayer → PermissionManager → TOOLS → F7 recovery). Brain:
BrainEngine/SuperBrain/ExecutionBrain + Planner/Orchestrator/Blackboard.
Voice: mic → audio.ts → VoiceTransport → Python bridge → Gemini Live API →
audio back. Vision: ScreenShareEngine → ContinuousVisionController →
UC/vision tools. Memory: Node memories.json + conversations/ AND Python
myraa_brain_memory.json (diverged, §13). Models: Gemini Live (voice),
Ollama (MODEL_ROUTES / settings.py) for consolidation/research paths.

## 3. Actual runtime flow

TEXT: CompanionChat → POST /api/chat/stream → conversations/ → buildContext(10)
→ unified_handler → (complex: agent path; simple: brain-stream) → persist →
speakTextToVoiceSessions (voice fan-out) → SSE. VOICE: mic PCM16 mono 16kHz →
/live → VoiceTransport → Python bridge → Gemini (VAD/turns/audio 24kHz) →
tool calls via GeminiToolRouter (allowlist→finance block→validate→authorize→
sanitize→respond) → transcripts/audio to client. Voice input does NOT enter
conversations/ or memory (M3 gap). VISION: auto-start observers →
process_event → working memory + Python consolidation. BROWSER: default-browser
open + UC vision interaction (see browser reports).

## 4. Subsystem inventory

LIVE: Electron shell, Node server+17 route modules, /live voice bridge,
Python agent (tools, brain, vision, observers, finance-advisory, telemetry),
MyraaCompanion UI (character+chat+voice), memories.json, conversations/,
UnifiedMemoryManager. DORMANT: MyraaShell+11 workspaces, all dashboards,
BrowserAgent, DesignLab, ContinuousVoiceLoop (never started), SpeechManager,
AudioQueue, BaseRecognizer, wake-word detector, services/voice+ai,
backend/speech 0-byte, MemoryDashboard UI, TradingDashboard. DEAD: local-agent,
Playwright paths, secrets.json store, conversation_history.json writer-less
functions, ConversationBus readers. Details §§5–16.

## 5. Critical bugs

### V1 — Gemini bridge singleton clobber race. Severity P1. Subsystem voice.
Root cause: module-global `_gemini_manager_singleton` overwritten per bridge
connection without a lock; closer clears it unconditionally. Evidence:
desktop_agent/main.py:2029-2033, 2086-2087, 2160-2165; health reports last
only (2018-2025). Impact: concurrent bridges orphan each other. Fix: NOT
APPLIED (needs single-vs-multi session product decision). Files: main.py.
Verification: code inspection only. Manual test: open two /voice/gemini/stream
bridges, confirm first degrades; decide enforce-single (409 busy) vs per-conn
scope.
### D1 — /api/computer reported OS success without acting. Severity P0.
Root cause: TS engine leaves simulate (mouse_engine.ts:69-110 returns
success:true on coordinate math; keyboard_engine.ts:63,92 "Simulate…";
window/scroll same) while POST /api/computer/execute+transaction returned
those as success. Evidence: files above + routes/computer.ts:33-63; zero
callers in src (grep). Impact: any caller believes the desktop moved.
Fix: APPLIED — both endpoints return 501 directing to Python POST /execute.
Files: server/routes/computer.ts. Verification: tsc + vitest 1876/1876;
unit tests call engine directly (unaffected). Manual: curl POST →
expect 501 JSON.
### V4 — model transcripts stored as user. Severity P2.
Root cause: role ignored in server.ts:339-341. Impact: (low — bus is orphan)
mislabelled transcript history. Fix: APPLIED — model→addAssistant
(server.ts). Verification: tsc + build.
### V3 — voice tool backlog silent drop. Severity P2.
Root cause: gemini_live.py:929-931 `continue` without FunctionResponse —
Gemini hangs. Fix: APPLIED — error FunctionResponse + tool_result emit.
Files: gemini_live.py. Verification: targeted pytest 127 pass. Manual:
flood >8 concurrent tool calls, confirm error responses, no stall.

## 6. Security vulnerabilities

### S1 — API key committed to git history. Severity P0 (historical).
Root cause: tracked file ` - Copy.env` (initial commit 121bc7f) contains
GEMINI_API_KEY. Evidence: `git show HEAD:" - Copy.env"` (values redacted in
audit; hash-compare proves committed key DIFFERS from live `.env` key —
rotation likely, revocation NOT LIVE VERIFIED). `.env` itself never tracked;
no hardcoded prod keys anywhere. Fix: NOT APPLIED (history rewrite is
destructive — owner approval required). Remediation: confirm old-key
revocation in Google Cloud console; before ever sharing/pushing the repo run
`git filter-repo --path " - Copy.env" --invert-paths` (plus existing
` - Copy.*` deletions); rotate again if revocation uncertain. Files: git
history. Manual: console check + `git log -p -- " - Copy.env"` (redacted).
### S2 — PII-bearing data tracked in git. Severity P1. FIXED.
Root cause: `memories.json` (user phone, name, paths — verified redacted
scan) and `settings.json` tracked. Fix: APPLIED — `git rm --cached` both
(files kept on disk) + `.gitignore` entries (memories/settings/conversation
history/conversations/capabilities/runtime/*.corrupt). Verification: `git
status` shows `D memories.json` (index-only); fresh `git status` clean of
data files.
### VI2 — untrusted screen/OCR/market content promotable to LTM. Severity P1.
Root cause: `process_event` writes every observer event twice with no trust
filter (brain_engine.py:1580 working_memory.remember_event — no check at
all; :1588 remember_working_event — secret-regex only); WORKING→EPISODIC→
SEMANTIC promotion (unified_manager.py:660,702,759,863) honors provenance
tag SYSTEM_OBSERVED but has no never-promote-untrusted rule. Secret regexes
are good (server_memory.ts:393-406, persistence.py:55-98) but cover secrets,
not injection. Fix: NOT APPLIED (promotion policy = product decision).
Mitigation: secret filters hold; no evidence of active exploitation.
Manual: display hostile-instruction text on screen, confirm no tool executes
and (currently) it may still be remembered — verify after policy lands.
### S4 — settings dual authority, no lock/schema. Severity P2.
Evidence: settings.json (Node route, no withWriteLock/serializeWrite,
load→merge→save lost-update window, any-JSON accepted: routes/settings.ts)
vs localStorage myraa.settings.v2 (best-effort POST sync:
settingsStore.ts:62-91). No dual disk writers; divergence possible offline.
Fix: not applied (needs schema + lock design). Manual: concurrent POSTs.

## 7. Integration failures

- M3 [P1]: voice→conversation/memory unification missing (responses fan out
  via speakTextToVoiceSessions, inputs never persist). Voice and text are one
  assistant on output, two on input history.
- M1 [P1]: Node/Python long-term memories diverged, no sync (schemas,
  retention, IDs all differ; one-way transient read only).
- V5 [P3]: ContinuousVoiceLoop never started (only callback set:
  application_container.py:295; no start call anywhere) — dormant parallel
  voice pipeline; REST endpoints exist but nothing live calls them.
- D2 [P3]: frontend onToolCall posts directly to 127.0.0.1:8765, bypassing
  Node (works: localhost-only design — server binds 127.0.0.1 — so no fix).
- U3 [P2]: no global error surface; MyraaCompanion onError noop; failures
  degrade to dot-color changes.

## 8. UX/UI issues

Live chain is ONLY MyraaCompanion (verified import graph); ~70% of frontend
(shell, 12-nav workspaces, dashboards, DesignLab, cards) is dormant.
Dormant fake-status: Sidebar STATUS Online (always green), TopBar NEURAL
CORE from WS state, hooks fastcore "READY" hardcoded, TradingDashboard glow
vs DISCONNECTED, ActiveModules collapsing 5/8 modules to pythonOnline,
BrowserAgent "Connection Established" hardcoded. Live honest bits: empty
chat state, in-bubble errors, voice-status text, TabPlaceholders.
FIXED: hardcoded PII name in dormant Sidebar → "User" (Sidebar.tsx:128).
NOT fixed (needs owner direction): dormant removal pass, global toast/error
system, memory/tools/vision tabs (honest placeholders today).

## 9. Voice issues

Gemini Live is the ONLY active engine (ElevenLabs/Whisper/Piper/Kokoro/
Silero/SpeechSynthesis all dead — retired guards + tests confirm). Formats
verified: 16kHz mono in, 24kHz mono out, 128ms chunks, gapless scheduler,
single playback owner (MyraaAudioSession). Reconnect budgets bounded at all
three layers (browser 5, Node 3, Python 3) with provisional-recovery semantics
and duplicate-call protection. FIXED: V3, V4 (+prior: _completed cap
counted here as V3b). Remaining: V1 singleton race, V5 orphan loop, V7
hardening backlog (dialogueHistory trim path server_voice.ts:131/376-378;
mic drop undercount audio.ts:495 vs 522-530; dead genId guard
server_voice.ts:493-503; barge-in state gate 512-513; video→/voice/execute
post rate unverified). Voice allowlist stays read/open-only (deliberate).

## 10. Vision issues

Healthy: auto-starts in lifespan, single capture authority (ScreenShareEngine),
stale/degraded detection, UC consumes state + verify_action, no duplicate
loops. OCR throttled (5s interval). Boundary gap is VI2 (§6):
screen text is DATA but promotable to memory. No change to pipeline.

## 11. Browser issues

See BROWSER_ARCHITECTURE_AUDIT.md + MYRAA_BROWSER_FINAL_REPORT.md. Re-scan
this pass: clean (remaining hits are legitimate removal-comments, behavioral
no-playwright tests, audit docs, lockfile/model-vocab false positives).
No regressions from this pass's edits (targeted browser suites re-run: pass).

## 12. Desktop Agent issues

89 tools load; CommandDispatcher + GeminiToolRouter + unified_handler all
share ValidationLayer→PermissionManager→F7 (verified). D1 fixed. No
Playwright. Finance advisory blocked-actions verified (TradingAdvisorPolicy
+ FINANCE_BLOCK_SUBSTRINGS + LIVE_TRADE_EXECUTION FALSE). Fail-closed authorization verified: unmapped tools (e.g. runShellCommand,
runCommand — absent from TOOL_CATEGORIES) default to HIGH_RISK → "confirm"
(registry.py check + DEFAULT_POLICIES); FINANCIAL → "deny". No arbitrary
model-generated shell, file, or power action executes without passing
PermissionManager category policy + arg-aware rules + (where confirm-gated)
single-use token handshake.

## 13. Memory issues

Authorities: Node memories.json (UI-facing, atomic, 500-cap) + conversations/
(live text) vs Python myraa_brain_memory.json (brain-authoritative, governed
remember, coalesced persist) — diverged (M1). Dead: conversation_history.json
functions (zero callers), ConversationBus readers (write-only), legacy
MemoryManager, one of two WorkingMemory classes. Python consolidation live;
Node processConversationSlice dead (Ollama-based, never invoked). Voice input
never lands anywhere durable (M3). Write paths secret-filtered; injection
not filtered (VI2).

## 14. Brain/reasoning issues

Pipeline real (BrainEngine→Planner→Executive→Orchestrator→metacognition);
ExecutionBrain + SuperBrain + AssistantRuntime convergence (voice callback →
AssistantRuntime) present. LLM providers exist but BrainEngine.process is
rule/heuristic (per existing docs; not re-litigated — behavior preserved).
3 Python event buses live (blackboard, planner-execution, orchestrator) —
flagged for review, no harm proven, no merge attempted (rule: no speculative
rewrites).

## 15. Tool-system issues

Single registry (TOOLS + DESKTOP_TOOL_NAMES + TOOL_REQUIRED_ARGS) shared by
all three dispatch paths — no second registry created. Gemini voice allowlist
narrow (~22 read/open tools) + finance substring block + sanitize (40
keys/items, 4k chars, depth 4). FIXED: _completed cap, backlog response.
Node DESKTOP_TOOLS set dead (sync holds by inspection). Per-tool
timeout/retry: F7 central, no unbounded retries found.

## 16. Startup/shutdown issues

start-myraa.bat sound: stale-port kill → agent boot → /health/live gate
(correct: liveness, not detail health) → Node → UI. Electron: single
instance, backend tree kill via taskkill, external links to OS browser.
"require is not defined": NOT PRESENT (zero require( in src). Shutdown:
Node closes WS + flushes persistence; Python lifespan stops vision/runtime/
observers; Node-alone shutdown leaves Python running (covered by launcher
cleanup paths — documented, acceptable).

## 17. Performance issues

NOT LIVE VERIFIED (no measurements taken; no numbers invented). Bounded-ness
post-fix: audio 64 (~8s, drop-oldest), tool tasks 8 (+fast rejections),
_completed 500 FIFO, histories capped (30/100/200/20/500), bridge event
queue UNBOUNDED (main.py:2081 — watch item), frontend audioBuffer flushed
per 100ms (fine). Polling: 15s agent-health (live), dormant hooks 3–15s
(unmounted — zero cost). Manual:cold-start timing, mic→audio TTFA (telemetry
exists server_voice.ts:347-355 + gemini_live.py:988-992 — read during manual
voice test).

## 18. Testing gaps

- HTTP-layer tests absent (no supertest): F1's 501 + all /api/* routes
  verified by tsc/build + manual curl only. Recommend adding supertest.
- Bool-returning "tests" (test_phase10_*, test_phase_v_*, test_screen_share,
  test_phase_3_4, test_phase_4_5) return bool instead of asserting —
  PytestReturnNotNoneWarnings: they PASS while verifying nothing. P2 gap.
- 19 heavyweight files (soak/start-stop/perf/benchmark/indexers/healing
  smokes) excluded from timed runs; unfiltered attempt hit ~93% with zero
  failures pre-timeout — remainder NOT VERIFIED this pass.
- Live-hardware paths (mic, speakers, Tesseract, Ollama models, GPU) need
  on-host runs.

## 19. Packaging gaps

- build/icon.ico MISSING while electron-builder.yml points win/nsis/
  uninstaller icons at it → broken/missing installer icons. P1, NOT FIXED
  (no asset fabrication per rules — supply a real .ico).
- agent_dist/ absent in dev (expected; PyInstaller prerequisite — documented).
- asar:false rationale present; extraResources agent mapping present;
  per-user DATA_DIR wiring present (MYRAA_DATA_DIR → userData).
- `npm run build` green (vite 2095 modules + server.cjs 1.1MB).

## 20. Capability gaps

P0: none open (fake-success closed; secret-rotated-likely). P1: memory
authority unification; voice-input persistence; untrusted-promotion policy;
installer icon; singleton-bridge decision. P2: settings lock/schema; global
error UX; bool-test cleanup; supertest HTTP coverage; dormant-code removal
pass (~70% frontend + voice stubs). P3: telemetry aggregation (parallel
health never merged), model-string hygiene (qwen3:8b test fixture),
wake-word dead toggle, video-post throttle confirmation.

## 21. Dead/legacy code (do not wire anything to these)

local-agent history; ContinuousVoiceLoop (constructed, never started);
SpeechManager/AudioQueue/BaseRecognizer; services/voice + services/ai +
backend/speech 0-byte scaffolds; conversation_history.json functions;
ConversationBus (write-only); legacy MemoryManager + spare WorkingMemory;
wakeWord detector (unimported); DESKTOP_TOOLS unused set;secrets.json store;
` - Copy.*` tracked deletions (cleanup in progress by owner).

## 22. Duplicate systems

Voice: live Gemini bridge vs dormant CVL (do NOT merge without design).
Memory: Node vs Python LTM (acknowledged gap). Event buses: 3 live Python
buses (review-only). Settings: file vs localStorage (best-effort sync).
Mirror risk avoided: no new registries/routers/buses/engines added this pass.

## 23. Configuration problems

Fixed: secrets.json doc claims (AGENTS.md x2, CLAUDE.md x2 → .env truth).
Healthy: .env single file authority, dual readers, upsert preserving
comments, 512-char + newline-injection guards, never echoed/logged.
MODEL_ROUTES (+settings.py) centralized; single DEFAULT_LIVE_MODEL.
AGENTS.md still describes phantom src/design-core+geometry+assembly (also
flagged by PHASE_29_5_REPORT) — left to owner (context file, beyond verified
security scope).

## 24. Recommended architecture (deltas only, no rewrites)

Keep everything; add: (a) single-vs-multi bridge decision (V1); (b) memory
authority + promotion policy (M1/VI2/M3); (c) settings lock+schema (S4);
(d) dormant-code removal pass (U1/V5); (e) supertest HTTP suite + bool-test
cleanup (T-gaps); (f) icon asset (PKG). Nothing else.

## 25. Changes actually implemented

1. server/routes/computer.ts — /execute + /transaction → honest 501 (D1).
2. server.ts — role-aware transcript routing (V4).
3. desktop_agent/speech/gemini_live.py — _COMPLETED_MAX 500 FIFO (V3b) +
   backlog error FunctionResponse (V3).
4. git rm --cached memories.json settings.json; .gitignore data entries (S2).
5. AGENTS.md + CLAUDE.md secrets.json → .env (4 lines).
6. src/ui/Sidebar.tsx hardcoded name → "User" (U5).
7. tests/test_gemini_live.py — bounded-memory regression test.
Prior pass: permissions OR-args, 172.16/12 block, Gemini decl strings, stale
Playwright wording (8 files), BrowserAgent sandbox+origin guard, 8 browser
regression tests. Protected systems untouched throughout.

## 26. Files changed

server/routes/computer.ts, server.ts, desktop_agent/speech/gemini_live.py,
tests/test_gemini_live.py, .gitignore, AGENTS.md, CLAUDE.md,
src/ui/Sidebar.tsx (+ prior pass: permissions.py, tools_websites.py,
tools_search.py, gemini_live.py decls, desktop_agent.spec,
EPIC-14F-SUMMARY.md, BrowserAgent.tsx, test_browser_security.py).
Untracked from git index (kept on disk): memories.json, settings.json.
Working tree also contains pre-existing owner modifications untouched
(ai_manager.py, settings.py, READMEs, Copy-file deletions, etc.).

## 27. Tests executed

- New regression: completed-call bound (pass); prior: 8 browser guards.
- Targeted: gemini_live+lifecycle+browser+permissions+f2 = 127 pass;
  prod_e+phase8+groww = 54 pass 1 skip (pre-existing).
- Full Python (19 heavyweight files excluded): 1666 passed, 15 skipped,
  0 failed (~9 min). Unfiltered attempt: ~93% zero failures pre-timeout.
- production_readiness + security_scan + launcher_readiness: 10 pass.
- npm test (vitest): 1876/1876 pass. tsc --noEmit: clean. npm run build:
  green (vite 9–13s + server.cjs).
- NOT LIVE VERIFIED: real mic/speaker/Gemini round-trip,Homestead... (no —
  strictly): real voice round-trip, browser-window opens, UC live clicks,
  Tesseract OCR, Ollama models, installer run, multi-bridge race.

## 28. Build results

tsc clean; vite 2095 modules; dist/server.cjs 1.1MB; test files 20/20 vitest.

## 29. Remaining risks

S1 history secret (verify revocation; purge before sharing); V1 race; M1/M3
unification; VI2 promotion policy; icon.ico missing; 19 heavy test files
unverified; bool-tests verifying nothing; unbounded bridge queue;
settings races; no HTTP tests; dormant ~70% UI + voice stubs awaiting removal
pass; latency unmeasured.

## 30. Next development phases

A: decisions (bridge sessions, memory authority/promotion, settings).
B: dormant removal + bool-test + supertest + icon asset.
C: error-UX + memory/tools/vision tabs wired or removed.
D: manual acceptance runs (voice E2E, browser E2E, installer E2E) then production call.

Manual acceptance tests: (1) start-myraa.bat → READY both URLs, no console
errors; (2) voice "open YouTube and search Minecraft" → default browser
opens, results, spoken summary, chat updated; (3) hostile screen text →
no tool executes; (4) close tab focused/unfocused; (5) kill :8765 →
degraded UI → restart → recovery verified audio; (6) curl POST
/api/computer/execute → 501; (7) second Gemini bridge → observe/document
behavior per V1 decision.
