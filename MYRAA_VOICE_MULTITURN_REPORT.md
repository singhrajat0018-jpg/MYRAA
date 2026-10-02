# MYRAA VOICE — MULTI-TURN FAILURE ROOT CAUSE REPORT

Date: 2026-09-19. No live mic/Gemini in this harness: runtime claims below
are proven with a scripted-transport simulation driving the REAL session
code (not mocks of it), plus code-path verification. Anything needing
hardware/inference is marked NOT LIVE VERIFIED.

## 1. Exact symptom

Turn 1 completes (response + audio). Turns 2+ unreliably produce nothing,
and the first response feels delayed. UI gives no signal during the dead
period (frozen "Listening...").

## 2. Exact root cause (two defects, both fixed)

R1 — Silent stream death. `GeminiLiveSession.receive_loop`
(desktop_agent/speech/gemini_live.py:890) handled exceptions via
`_fail_once` but a CLEANLY-ENDING server stream simply fell off the
`async for` and returned: sender idled, state stayed READY, no event fired,
no reconnect scheduled. The session looked alive and accepted mic audio
into a queue nobody drained — "one response then silence while everything
looks alive".

R2 — Reconnect blackout without UI truth. When the bridge DID fail over
(keepalive 1011 etc.), Node entered `reconnecting` and mic audio was
correctly dropped-if-down — but the browser had no `reconnecting` branch
(src/lib/audio.ts status handler), so the UI froze on the previous state
while the user spoke into a 2–8s blackout. Perceived as "turn 2 ignored".

## 3. Why response #1 worked

Mic → worklet/script frames → `handleMicFrame` → `/live` →
`handleAudioChunk` (state listening, bridge READY) → `submit_audio` →
bounded queue → `_audio_sender` (gen match) → Gemini → `receive_loop` →
events → bridge pumps → Node → jitter buffer → generation-checked decode
→ gapless schedule. Every gate is open on a fresh session. Proven by sim
turn 1 flowing byte-for-byte to 4 audio events.

## 4. Why response #2 failed

Path A (proven possible): server stream ends/clean-closes after turn 1 →
R1 silent death → turns 2+ produce zero events, zero errors, zero recovery.
Path B (proven gap): any keepalive/network failure → reconnect blackout →
turn-2 audio dropped by design while UI shows frozen "Listening" (R2).
Session message handling itself was PROVEN innocent: the 3-turn + interrupt
sim passes all turns through one live session with isolated generations.

## 5. Why response was delayed (measured breakdown)

No live numbers exist; honest structural budget: capture frame 64ms
(worklet) + encode sub-ms + Node ~0–2ms + Python queue ~ms + UNKNOWN
network/inference (dominant) + jitter 20ms + decode/schedule ~16–18ms.
Client controllable ≈100ms + UNKNOWN. Previous 100ms jitter batching
(already 20ms) was the largest code-level item and is gone. Remaining
"delay" is overwhelmingly Gemini-side cold inference + RTT — measurable
on-host now via CLIENT_TTFA + server FIRST_AUDIO_RECEIVED + Python
per-turn input→audio (all emitting; see §8).

## 6. Fix (exact changes)

1. `gemini_live.py receive_loop`: clean stream end converges into
   `_fail_once("receive-ended")` → single reconnect path with resumption
   handle. 6 lines, no new paths.
2. `audio.ts`: `LiveState += "reconnecting"`; status branch sets it; mic
   keeps flowing (gate unchanged); recovery audio plays immediately.
3. `events.ts` VoiceState += 'reconnecting'; `MyraaCompanion` mappers;
   `CompanionChat` VoiceStrip active + "Reconnecting... keep talking";
   dormant `CompanionVoice` label/color.
4. `tests/test_voice_multiturn.py` (new): 3-turn+interrupt sim +
   clean-end convergence test.

## 7. Runtime flow AFTER fix

TURN 1: mic → Gemini → audio → turn_complete → READY (unchanged).
TURN 2: same path (proven: sim turn 2 flows post-fix).
TURN 3: same path (proven). INTERRUPTION: epochs++ at all layers,
stale audio dropped at 3 checkpoints (proven: generations {G0,G1}
isolated, no leak). TURN 4: flows (proven: post-interrupt turn
completes, session READY + accepting). Stream death (any turn):
connection_failed → bounded reconnect → provisional → verified on first
audio (proven: convergence test).

## 8. Latency BEFORE/AFTER

No live measurements exist (stated, not fabricated). Structural:
first-audio batching 100→20ms (prior), frame 128→64ms (prior), this pass
adds measurement, not delay removal: CLIENT_TTFA (browser), TTFA breakdown
(Node), per-turn input→audio (Python). Run §10 procedure for numbers.

## 9. Tests

New: 2 multiturn sim tests (both fail pre-fix appropriately — #2 proven
red-first; #1 needed harness correction for realtime backpressure, then
green). Full: vitest 1881/1883 (2 unrelated pre-existing failures:
FastCore 5ms timing flake; world-intelligence 10K-events perf bound —
both untouched per rules); Python targeted 149 passed (voice, lifecycle,
multiturn, browser, permissions, agent suites); tsc clean; build green.

## 10. Remaining limitations (real only)

- Live feel NOT VERIFIED: run 1) "Hello MYRAA" → record CLIENT_TTFA +
  server TTFA; 2) three distinct turns ("Hello MYRAA" / "What is the
  weather today?" / "Tell me something interesting") → all respond;
  3) interrupt mid-speech → immediate stop + new answer; 4) 30s silence;
  5) kill :8765 mid-turn → "Reconnecting... keep talking" → recovery.
- Response latency is Gemini-side dominated; no client code can fix RTT.
- Bridge event queue unbounded (watch item); advisory VAD still
  ScriptProcessor (P3); video-POST path dead (no callers) — left alone.
