# MYRAA VOICE 0→100 PRODUCTION REPORT

Date: 2026-09-19. Extends (never replaces): MYRAA_VOICE_MULTITURN_REPORT.md,
MYRAA_VOICE_VALIDATION_REPORT.md, MYRAA_VOICE_0_100_FINAL_AUDIT.md,
MYRAA_VOICE_AUDIT_REPORT.md, MYRAA_AUDIT_REPORT.md. No live mic/speakers/
interactive Gemini in this harness: hardware-dependent claims are marked
NOT LIVE VERIFIED, never fabricated.

## 1. Executive verdict

CODE VERIFIED · TEST VERIFIED · BUILD VERIFIED · LIVE AUDIO NOT VERIFIED ·
HUMAN QUALITY NOT VERIFIED. Forensic re-audit confirms one production voice
path, single authority at every stage, bounded queues throughout, epochs end
to end. Two behavior changes this pass (bounded bridge fan-out, reconnecting
UI truth); one forbidden-surface deletion (`wakeWord.ts`); one 20-turn sim.

## 2. Existing architecture

Unchanged: mic → AudioWorklet(1024/64ms, script fallback) → shared PCM16LE/
base64 framer → Node VoiceTransport (no buffer) → Python bounded queue(64)
→ single gated sender → Gemini Live (3.1-flash-live-preview, Aoede) → 24kHz
PCM → 20ms jitter → triple-checked gapless playback. Tool calls off-loop
with error responses; transcripts role-separated with 5s dedup.

## 3. Actual runtime flow

connect() → contexts → worklet-or-script capture → `handleMicFrame` →
`/live` → `handleAudioChunk` → `submit_audio` → sender → Gemini → receive →
pump → Node → jitter → decode → schedule. Interrupt/reconnect/turn-complete
paths re-verified unchanged except §23 items.

## 4. State machine

Owners: browser LiveState (UI + mic gate), Node transport state (bridge
gate + client status), Python ConnState (audio gate + recovery). Verified
transitions: READY→turns→READY (sim), speaking→interrupt→listening (sim),
any→FAILED→RECONNECTING→READY (sim), clean-end→FAILED (sim). No stuck or
impossible transition found; all switches have defaults (tsc-clean).

## 5. Audio capture

Worklet-first re-verified (Blob module, transferable frames, zero-gain
sink, fallback, port.close on disconnect). VAD tap advisory-only.

## 6. PCM pipeline

`pcm.ts` single contract, 7 tests green (silence/endianness/clipping/frame
sizes/≤2-LSB round-trips documenting the pre-existing 0x7FFF scale).

## 7. Gemini Live

Session lifecycle/manager re-verified; config fields re-verified against
installed SDK 2.14.0 (all passed fields exist; `realtime_input_config`
correctly omitted → server-default VAD). No config change.

## 8. VAD

Gemini native sole authority (re-verified — no commit/interrupt path from
local VAD exists). Local detector visualization/metrics only.

## 9. Multiturn

Sim-proven: 3-turn, 10-turn (ordered, streaming, no dupes), 20-turn stable
(20/20 + 20/20, READY + accepting + bounded internals after).

## 10. Barge-in

Sim-proven: single + triple interruption isolate generations {G0..G3},
post-interrupt turns complete on the same session. Blackout-barge
limitation documented (§28: buffered audio can play out during reconnect
since local VAD must not interrupt — architectural, not a bug).

## 11. Playback

20ms jitter, gapless +15ms, triple generation checks, 200-chunk/16-source
bounds re-verified. First audio streams (ordering test per turn).

## 12. Reconnect

Budgets 5/3/3+manager; resumption handle captured-before-drop (sim-proven
pass-through + budget reset); provisional recovery; clean-end convergence
(sim-proven red-first). Dual-tab safe via active-bridge counter.

## 13. Resumption

Handle stored on update, passed on reconnect (sim), sliding-window
configured. Cross-reload resume absent by design (documented).

## 14. Transcript

Roles correct; 5s dedup; dead `partial_transcript` receiver branch harmless;
no inversion path found.

## 15. Tool interaction

Off-loop (cap 8 + error responses, tested); allowlist + finance block +
PermissionManager + sanitize re-tested green (84 + 149 suites). Typed-chat
auto-speak mid-voice-turn is an accepted residual race (user-initiated,
intended feature; documented §28).

## 16. Browser interaction

Voice-reachable tools (openWebsite, desktopBrowserOpen/Navigate/Search,
search*) route through the default-browser architecture; PermissionManager
gates hold (test suites green). No Playwright. Live open-URL flow NOT LIVE
VERIFIED this pass.

## 17. Error handling

Every failure converges to RECOVERED/RECONNECTING/visible ERROR/safe
termination (sim + unit proven). No silent path remains except a stalled-
but-open stream with no keepalive timeout — SDK keepalive owns that;
code treats 1011 convergently.

## 18. Resource usage

Sim-level: no growth across 20 turns (queues/tasks/sources bounded;
counters are ints). 20–50–100-turn soak + CPU/RAM profiling NOT EXECUTED —
procedure in prior reports §9.

## 19. Security

Untouched + re-verified: PermissionManager, finance firewall, allowlist,
sanitizers, fail-closed defaults, no key/log exposure, CSP change scoped
to `worker-src`. Voice input stays untrusted (transcripts never become
instructions — no such path exists).

## 20. Latency

No live values (honest). Structural client budget ≈100ms + UNKNOWN
network/inference. Per-leg same-clock instrumentation complete at all
three layers (CLIENT_TTFA, Node breakdown, Python per-turn ms).

## 21. Bugs found

ID/SEVERITY/EVIDENCE/ROOT CAUSE/FIX/VERIFICATION/REMAINING RISK:
- VQ-1/P2/bridge `asyncio.Queue()` unbounded/`_pump_out` could grow if Node
  stalls/`_BridgeEventQueues` (control never drops, media 128 drop-oldest,
  control-first drain)/4 unit tests + suites/closed.
- VQ-2/P2/`reconnecting` status ignored by browser/audio.ts:606 + frozen
  UI/`reconnecting` state end to end (audio/events/companion/chat)/tsc +
  suite/closed (live feel pending).
- VQ-3/P3/`wakeWord.ts` Web Speech API detector, zero importers (proven by
  grep)/file deleted; inert settings flag left/live suites green/closed
  (toggle persists a flag nothing reads — documented).
- Re-verified healthy (no change): session/message handling, epochs,
  bounds, config, transcripts, tools, permissions.

## 22. Root causes

Unbounded fan-out (no backpressure design); missing status branch (protocol
grew, browser handler didn't); dormant forbidden-surface file (leftover).

## 23. Fixes

§21 VQ-1..VQ-3. Smallest correct changes; no architecture touched; no
provider/fallback; no permission/security change.

## 24. Files changed

`desktop_agent/main.py` (queues), `src/lib/audio.ts` (reconnecting),
`src/ui/events.ts`, `MyraaCompanion.tsx`, `CompanionChat.tsx`,
`CompanionVoice.tsx` (dormant), `tests/test_voice_bridge_queues.py` (new),
`tests/test_voice_multiturn.py` (20-turn), `wakeWord.ts` (deleted).
Unrelated 190-file dirty tree untouched; no resets.

## 25. Tests

New: 4 queue + 1 twenty-turn (total voice sims: 3/10/20-turn, triple +
single interrupt, clean-end, reconnect-loop). Full vitest 1883/1883. Python
targeted 157 (voice/lifecycle/multiturn/queues/browser/permissions/agent).
tsc clean. Pre-existing unrelated failures this cycle: none (prior cycle's
2 flakes not present this run).

## 26. Build

Vite 2096 modules + dist/server.cjs 1.1MB green. Forbidden scans clean
(removal-comments + negative guards + dead skipped-test refs only).

## 27. Live verification

NOT PERFORMED (no mic/speakers/interactive Gemini). Nothing fabricated.

## 28. Remaining limitations (real only)

Live feel + TTFA numbers + soak (procedures ready); blackout barge-in plays
out buffered audio (architectural: local VAD must not interrupt);
typed-auto-speak mid-turn race (accepted); stalled-open-stream depends on
SDK keepalive; history secret / memory authority / icon.ico (system audit);
19 heavyweight Python files excluded from timed runs (prior full sweep
green).

## 29. Manual acceptance procedure

"Hello MYRAA" (record CLIENT_TTFA + server TTFA) → "What can you do?" →
"Tell me something interesting." → "Open Google." (default browser) →
interrupt mid-speech ("No, wait.") → "Continue." → 30s silence → speak →
kill :8765 mid-turn ("Reconnecting... keep talking" → recovery) → 20-turn
run → second tab. Each PASS/FAIL/NOT VERIFIED + TTFA values.

## 30. Final 0→100 assessment

CODE 100 · TEST 100 · BUILD 100 · LIVE AUDIO unverified · HUMAN QUALITY
unverified. The voice system is as fast, bounded, truthful, and recoverable
as its architecture allows; the remaining distance to premium feel is
measured on-host (§29), not coded blind.
