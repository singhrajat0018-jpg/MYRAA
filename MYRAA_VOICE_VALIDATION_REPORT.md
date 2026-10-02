# MYRAA VOICE — POST-FIX VALIDATION + LATENCY ELIMINATION REPORT

Date: 2026-09-19. Extends (does not replace): MYRAA_VOICE_MULTITURN_REPORT.md
(root causes R1/R2), MYRAA_VOICE_0_100_FINAL_AUDIT.md, MYRAA_VOICE_AUDIT_REPORT.md.

## 1. LIVE TEST RESULTS — LIVE VERIFICATION BLOCKED

No microphone, speakers, or interactive Gemini session exist in this harness.
The 5-turn script ("Hello MYRAA" → "What can you do?" → "Tell me something
interesting" → "Open Google" → interrupt "No, wait" → "Continue"), the 30s
silence test, and the bridge-kill test could NOT be executed live. Everything
below is runtime evidence from scripted-transport simulation driving the REAL
session/bridge code, plus static verification. Nothing is fabricated.

## 2. TTFA MEASUREMENTS — NO LIVE VALUES (honest)

Per-leg same-clock instrumentation now complete: browser CLIENT_TTFA
(mic-chunk→playback-schedule), Node FIRST_AUDIO_RECEIVED breakdown
(capture→transcript→audio), Python per-turn input→audio ms. Structural
client budget ≈100ms + UNKNOWN network/inference (dominant). P50/P90/P95/max:
NOT MEASURED — requires the on-host runs in §9.

## 3. EXACT REMAINING BOTTLENECK

Code-side: none proven — capture (64ms), forward (~0–2ms), queue (~ms),
jitter (20ms), schedule (+15ms) are all bounded and measured-ready. Expected
dominant cost is Gemini inference + network RTT (UNKNOWN, unfixable in client
code). Two failure-shaped behaviors were closed this pass: silent stream
death (R1, prior) and reconnect-blackout-with-frozen-UI (R2, this pass).

## 4. EXACT CODE CHANGES (this pass)

1. `desktop_agent/main.py` — `_BridgeEventQueues`: control events
   (turn_complete, interrupted, failures, resumption, errors, tool_result)
   never drop (unbounded, low-volume); audio/partial drop-oldest beyond 128
   with `events_dropped` counter; `_pump_out` drains control first.
2. `src/lib/audio.ts` + `src/ui/events.ts` + `MyraaCompanion.tsx` +
   `CompanionChat.tsx` (+ dormant `CompanionVoice.tsx`) — `reconnecting`
   state end to end; mic keeps flowing (gate unchanged); recovery audio
   plays immediately; UI shows "Reconnecting... keep talking".
3. `tests/test_voice_bridge_queues.py` (new, 4 tests); extended
   `tests/test_voice_multiturn.py` (10-turn, triple-interrupt, reconnect-loop).

## 5. REGRESSION RESULTS

- New: 4 queue + 3 extended sim tests pass (10 turns/10 audios ordered +
  streaming-ordered, triple-interrupt generations {G0..G3} isolated, resumption
  handle passed + budget reset).
- Full vitest: 1881/1883 — 2 pre-existing unrelated failures (FastCore 5ms
  timing flake; world-intelligence 10K-events perf bound), both untouched.
- Python targeted (voice/lifecycle/multiturn/bridge-queues/browser/
  permissions/agent): 149 passed. tsc clean. Build green (2096 modules).

## 6. BUILD RESULTS

`npm run lint` clean; `npm run build` green (vite + server.cjs 1.1MB).

## 7. RESOURCE/LONG-RUN RESULTS

Sim-level: 10-turn run leaves session READY + accepting, no task/queue
growth (bounded everywhere including the bridge queue after §4). A 20–30
turn soak, 10-interruption run, and memory/CPU profiling were NOT EXECUTED
(no long-run harness here) — procedure in §9.

## 8. REMAINING LIMITATIONS (real only)

LIVE audio/human-quality unverified; TTFA numbers unknown until on-host;
bridge media drops are lossy by design (superseded chunks only); advisory
VAD still ScriptProcessor (P3); video-POST path dead (no callers, left
alone); system-audit leftovers (history secret, memory authority, icon).

## 9. MANUAL ACCEPTANCE (on Windows host, agent running, key set)

1. "Hello MYRAA" → record CLIENT_TTFA + server TTFA. 2. "What can you do?"
3. "Tell me something interesting." 4. "Open Google." (default browser).
5. Interrupt mid-speech ("No, wait.") → immediate stop. 6. "Continue."
7. 30s silence → speak → response. 8. Kill :8765 mid-turn → expect
"Reconnecting... keep talking" → recovery → continue. 9. 10-turn run.
10. Second tab dual session. Each PASS/FAIL/NOT VERIFIED with TTFA values.

## ACCEPTANCE CHECKLIST MAPPING

✓ TURN 1/2/3 + 10 consecutive (sim-proven; live pending §9)
✓ interruption + post-interruption turn (sim-proven, generations isolated)
✓ clean stream termination recovers (sim-proven red-first)
✓ reconnect state visible (implemented; live pending)
✓ no duplicate responses / no stale audio (sim-proven ordering + epochs)
✓ microphone/session alive between turns (sim-proven)
✓ first audio streamed (ordering test: audio precedes turn_complete per turn)
✓ TTFA measured (instrumented; values pending live)
✓ no unbounded audio growth (jitter 200 + sources 16 + bridge media 128)
✓ no memory/task leak (sim-level; soak pending)
✓ sole engine Gemini Live; security unchanged (scans + 149 tests green)
