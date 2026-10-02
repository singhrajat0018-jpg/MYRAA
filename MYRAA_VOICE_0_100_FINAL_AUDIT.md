# MYRAA VOICE 0→100 FINAL AUDIT

Date: 2026-09-19. Engine: Gemini Live ONLY — verified, no fallback added.
Method: full forensic re-inspection (reports treated as evidence, not proof),
root-cause fixes, regression tests, full verification. No live microphone /
Gemini round-trip exists in this harness: anything needing hardware or
inference is marked NOT LIVE VERIFIED, never claimed.

## A. Executive Verdict

CODE VERIFIED · TEST VERIFIED · BUILD VERIFIED · LIVE AUDIO: NOT VERIFIED ·
HUMAN CONVERSATIONAL QUALITY: NOT VERIFIED. The pipeline is single-authority
at every stage with bounded queues, end-to-end epochs, and fresh client-side
TTFA instrumentation awaiting on-host runs. Prior passes' fixes re-verified
present; this pass added worklet capture, singleton cleanup, playback bounds,
and regression coverage.

## B. Existing Architecture

`MyraaAudioSession` (src/lib/audio.ts:78) owns mic+playback. Capture:
getUserMedia (EC/NS/AGC, optional deviceId) → 16kHz ctx → AudioWorklet
`myraa-capture` (1024-sample/64ms, transferable) with ScriptProcessor
(2048/128ms) fallback → shared `handleMicFrame` (PCM16LE+base64, mic
diagnostics) → WS `/live` → Node `VoiceTransport` (no buffer,
drop-if-closed) → Python bridge (bounded queue 64, drop-oldest) → single
generation-gated sender → Gemini Live SDK (gemini-3.1-flash-live-preview,
Aoede) → 24kHz PCM → 20ms jitter buffer → generation triple-checked decode
→ gapless schedule (+15ms) → speakers.

## C. Actual Runtime Flow

connect() → WS + token → 16k/24k contexts + analysers → advisory VAD tap →
mic (+deviceId) → worklet-or-script capture → per-frame send → Gemini
realtime input → native VAD/turns → receive_loop → _handle_message →
_pump_out → handleGeminiMessage (TTFA timers, 5s transcript dedup) →
playAudioPCMChunk → flushAudioBuffer → source.start. Interrupt: Gemini
`interrupted` → Python generation_seq++ → Node generationId++ → browser
generationId++ + stop + clear + upstream interrupt. Tool calls off-loop
(cap 8, error response on overflow) via allowlist→finance→validate→
authorize→sanitize.

## D. Root Causes Found

1. 128ms main-thread capture quantization (+deprecation/jank risk).
2. Cross-connection singleton alias corrupting bridge state/health.
3. Unbounded playback jitter structures (memory-growth shape under stall).
4. No client-side turn-timing signal (TTFA only server-side).
5. Stale "Playwright" wording in two brain comments.

## E. Bugs Found (ID/SEVERITY/FILE/FUNCTION/SYMPTOM/ROOT CAUSE/FIX/TEST/STATUS)

- VW-1/P1/audio.ts connect-capture/128ms main-thread framing/deprecated API/
  shared handleMicFrame + worklet-first (1024/64ms) + script fallback +
  pcm.ts contract/tests/pcm.test.ts (7 pass)/IMPLEMENTED.
- VW-2/P1/main.py voice_gemini_stream_ws+health/second tab disturbs first
  via `_gemini_manager_singleton`/alias deleted, `_gemini_bridges_active`
  counter, honest health/zero grep refs + 70 pytest/IMPLEMENTED.
- VW-3/P2/audio.ts playback/stall growth/audioBuffer 200 drop-oldest +
  activeSources 16 cap + counters/tsc+suite/IMPLEMENTED.
- VW-4/P3/comments only/reworded, zero behavior/suite/IMPLEMENTED.
- VW-5/P2/audio.ts turn timing/no client TTFA/`tMicTurnStart` arming +
  CLIENT_TTFA log + resets (drain/turnComplete/interrupt/disconnect)/tsc;
  live values NOT LIVE VERIFIED/IMPLEMENTED (instrumentation).
- VW-6/P3/audio.ts disconnect/MessagePort leak on repeated cycles/
  `port.close()` added/tsc/IMPLEMENTED.

## F. Fixes Implemented

Above six. Prior-pass fixes re-verified present (VAD advisory, 20ms flush,
client generation triple-check, backlog error response, _completed 500-cap,
transcript roles, CSP worker-src). No provider, engine, or permission change.

## G. Latency Before/After (measured vs UNKNOWN)

Frame 128→64ms / jitter 100→20ms (structural, verified in code+tests).
Client controllable ≈163→≈100ms + UNKNOWN network/inference. No live
numbers exist; CLIENT_TTFA + server TTFA breakdown + Python per-turn ms now
all emit for on-host measurement.

## H. Capture Pipeline

Worklet-first with identical wire bytes; Blob-URL module (CSP-covered);
zero-gain sink; fallback logged via CAPTURE_MODE; port closed on disconnect;
mic diagnostics tag capture mode.

## I. Gemini Live Pipeline

Single session/sender/receiver per bridge; config fields verified against
installed SDK 2.14.0 (all 8 passed fields exist; `realtime_input_config`
correctly omitted → server-default VAD on; no change warranted).

## J. Playback Pipeline

20ms jitter, gapless +15ms scheduler, generation triple-check, 200/16
bounds, CLIENT_TTFA instrumentation.

## K. Interruption/Barge-in

Epoch chain intact (browser+Node+Python), advisory-only local VAD,
drain-on-close/fail, backlog error responses. Triple-interrupt safe by
construction; live feel NOT LIVE VERIFIED.

## L. Reconnect/Recovery

Budgets 5/3/3+manager; resumption handle captured-before-drop; provisional
recovery; timer resets; dedup; VW-2 removes cross-tab corruption.

## M. Transcript System

Roles correct end to end (user/model); dead `partial_transcript` branch in
browser is receiver-only with no sender — harmless; no inversion found.

## N. Tool Interaction

Off-loop execution, backlog error response (newly tested), dedup memory
bounded, permission+finance gates re-tested (84 browser/permission pass).

## O. Resource/Memory Safety

Worklet node+port teardown verified in code; contexts closed; tasks
cancelled; queues/histories capped (bridge event queue unbounded — watch
item, drops nothing).

## P. Security

No auth/key/tool path touched. `worker-src blob:` scoped (script-src
unchanged). Fail-closed defaults re-verified (unmapped → HIGH_RISK confirm).

## Q. Files Changed

src/lib/audio.ts, src/lib/pcm.ts (new), tests/pcm.test.ts (new),
desktop_agent/main.py, server.ts (CSP, prior), brain comments ×2,
tests/test_gemini_lifecycle.py (backlog test). No unrelated-tree changes.

## R. Tests Added

tests/pcm.test.ts (7); test_tool_backlog_full_rejects_with_error_response
(prior item in this cycle: test_completed_call_memory_is_bounded).

## S. Test Results

vitest 1882/1883 (1 unrelated pre-existing world-intelligence 10K-events
perf flake: 41.8s vs 30s budget — untouched per Phase 25, documented);
Python voice/agent/permission/browser targeted 142+70+13 pass; tsc clean.

## T. Build Results

vite 2096 modules + dist/server.cjs 1.1MB green (twice, pre/post).

## U. Live Verification

NOT PERFORMED (no mic/speakers/interactive Gemini in harness). Nothing
fabricated.

## V. Performance Measurements

None live. Structural deltas only (§G). Instrumentation ready (§K prior).

## W. Remaining Limitations

ScriptProcessor fallback by design; advisory VAD still deprecated-processor
(P3); unbounded bridge event queue (watch); video-POST throttle unverified;
system-audit leftovers (history secret, memory authority, icon.ico).

## X. Manual Acceptance Procedure

1. CAPTURE_MODE=worklet + MIC_OK ≈78 chunks/5s. 2. "Hello MYRAA" → record
CLIENT_TTFA + server TTFA. 3. 3-turn, no dupes. 4. Interrupt ×3, no stale
tail. 5. 30s silence + noise, no phantom/false turns. 6. Kill :8765 →
degraded → restart → recovery-on-first-audio. 7. Dual-tab independence.
8. 10 connect/disconnect cycles, no growth. Each PASS/FAIL/NOT VERIFIED.

## Y. Regression Risks

Worklet path is new code on a realtime path — mitigated by byte-identical
fallback-tested contract + automatic fallback + mode logging. CSP change is
additive (worker-src only). Bridge counter is single-loop-safe. All covered
by suite + build.

## Z. Final Architecture

§28 target as-built: ONE engine, ONE turn authority, ONE session/sender/
receiver/playback owner per connection, ONE epoch chain, BOUNDED queues,
NO stale/duplicate audio, NO fallback, NO ElevenLabs, NO Playwright, NO
fake success, NO security bypass.

## AA. Final Verdict

CODE VERIFIED · TEST VERIFIED · BUILD VERIFIED · LIVE AUDIO NOT VERIFIED ·
HUMAN QUALITY NOT VERIFIED. Ship to on-host acceptance (§X); do not claim
production voice quality before it.
