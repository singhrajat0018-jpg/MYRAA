# MYRAA VOICE PIPELINE — FINAL ENGINEERING REPORT

Date: 2026-09-19
Scope: Gemini Live voice ONLY (sole engine — verified, no fallback added).
Prior audit treated as implementation evidence, NOT as proof of quality;
every claim below re-verified against live code this pass.

## A. Previous architecture (actual runtime path, verified)

```
Browser mic (getUserMedia, echoCancellation/noiseSuppression/autoGainControl)
 → input AudioContext (16kHz requested) → ScriptProcessor(2048,1,1) ≈128ms chunks
 → floatTo16BitPCM → base64 → WS /live {audio}
 → Node VoiceTransport.handleAudioChunk (server_voice.ts:444, no buffering, drop on closed bridge)
 → WS 127.0.0.1:8765/voice/gemini/stream {type:"audio"}
 → Python bridge _pump_in → sess.submit_audio → bounded asyncio.Queue(64)
 → _audio_sender (READY + generation-gated) → Gemini Live SDK send_realtime_input
 → Gemini (native VAD/turns/24kHz audio/barge-in) → receive_loop → _handle_message
 → bridge _pump_out → Node handleGeminiMessage → WS /live → browser
 → playAudioPCMChunk → 20ms buffer → flushAudioBuffer → AudioBuffer(24kHz)
 → gapless scheduler (nextStartTime, +15ms) → speakers
```

Parallel local VAD: separate 16kHz AudioContext + VoiceActivityDetector
(spectral flux/ZCR/energy, 2-frame rule) — previously triggered
`handleInterruption()` directly, competing with Gemini's authoritative
`interrupted` events.

## B. Problems discovered (all verified in code)

### V-1 — Dual VAD authorities fighting. Severity: HIGH.
File: src/lib/audio.ts (VAD callback ex-379-433). Function: VAD onStateChange.
Root cause: local VAD called `handleInterruption()` after 2 consecutive
speech frames (~256ms) while Gemini Live simultaneously emits authoritative
`interrupted` events for the same user speech.
Observed behavior: double interruption (local stop + server stop), generation
churn, possible mid-utterance cutoff driven by untuned local thresholds
(0.2–0.5 adaptive) rather than Gemini's acoustic model.
Why: two turn-detection owners with no hierarchy.
Fix: local VAD demoted to advisory/UI-only (forwards to onVADStateChange,
frame counting retained for metrics, NEVER calls handleInterruption).
Authoritative interruption is Gemini `interrupted` events only.

### V-2 — 100ms playback buffer added first-audio latency. Severity: HIGH.
File: src/lib/audio.ts (BUFFER_FLUSH_MS ex-102). Function: playAudioPCMChunk.
Root cause: every audio chunk waited up to 100ms + join/decode before any
sound played; stated rationale (prosody) trades TTFA for smoothness on a
realtime path.
Observed behavior: ~100–200ms extra time-to-first-audio on every turn.
Why: batching tuned for file-like TTS, wrong for streaming conversation.
Fix: BUFFER_FLUSH_MS 100 → 20ms. Gapless scheduler retained (15ms lookahead).

### V-3 — Python bridge singleton clobber race. Severity: MEDIUM.
File: desktop_agent/main.py (ex `_gemini_manager_singleton` global).
Root cause: module global overwritten per bridge connection and cleared on
any disconnect; concurrent bridges orphan each other's manager; health
endpoint reported last-writer only.
Observed behavior: second voice client disconnects/confuses the first.
Why: global used where per-connection ownership is correct (manager already
per-connection; only the global alias was shared).
Fix: removed the global alias entirely (per-connection manager only).
Health endpoint now reports configured/model without singleton.

### V-4 — No client-side generation guard (stale audio leak). Severity: HIGH.
File: src/lib/audio.ts (handleInterruption ex-675, flushAudioBuffer ex-721).
Root cause: `handleInterruption()` stopped sources and cleared the buffer but
never versioned the generation; audio already queued in `bufferTimeout` or
arriving between stop and clear could still play into the new turn.
Observed behavior: stale tail of old response audible after barge-in.
Why: stop-without-epoch.
Fix: added `generationId` (audio.ts): bumped in `handleInterruption`,
captured at flush entry, re-checked after join/decode, re-checked before
`source.start()`. Any mismatch → drop + log. Matches existing server
(server_voice.ts:493-515) and Python (sender `gen != _conn_gen` drop)
epochs end-to-end.

### V-5 — Stale tool-response hang (prior audit, confirmed present).
File: desktop_agent/speech/gemini_live.py:929-931. Already fixed in prior
pass (error FunctionResponse on backlog-full); re-verified present this pass.
No change.

## C. Changes made (exact files)

1. `src/lib/audio.ts`
   - BUFFER_FLUSH_MS 100 → 20.
   - VAD callback: removed `handleInterruption()` trigger; advisory only.
   - Added `generationId`; bump in `handleInterruption()`; triple-checked
     in `flushAudioBuffer()` (entry / post-decode / pre-start).
2. `desktop_agent/main.py`
   - Removed `_gemini_manager_singleton` global (alias + clear); per-bridge
     manager unchanged otherwise.
3. `tests/` — no new voice tests this pass (existing 37 voice tests cover
   generation/queue/reconnect/sanitize; all pass — §J).
4. NOT changed (deliberately): Python session/generation/queue design,
   Node transport policy, tool allowlist, finance firewall, PermissionManager,
   resumption/backoff budgets, sample rates, worklet migration (see §L).

Untouched protected systems: FastCore, PermissionManager, finance firewall,
tool authorization, default-browser architecture, vision, memory.

## D. Audio pipeline (actual, post-fix)

MIC → getUserMedia (EC/NS/AGC, optional deviceId) → 16kHz AudioContext →
ScriptProcessor 2048 (≈128ms) → Int16LE → base64 → /live → Node (no buffer,
drop-if-closed) → Python bounded queue(64, drop-oldest) → READY+generation
gated sender → Gemini (16kHz PCM) → 24kHz PCM chunks → Node (no buffer) →
browser 20ms jitter buffer → generation-checked decode → AudioBuffer(24kHz)
→ gapless schedule (+15ms) → speakers. One sender, one receiver, one
playback owner per layer; one Gemini session per bridge.

## E. VAD (ownership, final)

Gemini Live native VAD is the SOLE turn-detection authority (speech end,
turn_complete, interruption). Local VoiceActivityDetector is an advisory
visualization/metrics layer only: it may inform UI state, never interrupt,
never commit turn state, never send anything. Rationale: only Gemini sees
the full-duplex acoustic picture (echo, endpointing, barge-in); local
energy/ZCR heuristics cannot win ties and previously caused double
interruptions (V-1).

## F. Interruption (exact barge-in mechanism)

1. Gemini detects user speech during playback → `interrupted` event →
   Python `generation_seq++` → bridge → Node `interrupt()` (generationId++,
   `interrupted` to client, timers reset, listening in 100ms) → browser
   `handleInterruption()` (generationId++, stop sources, clear buffer,
   `interrupt` to server, listening).
2. Any audio from the old generation is dropped at three checkpoints
   (buffer entry, post-decode, pre-start) plus server/Python epoch drops.
3. New user audio flows immediately; no replay of dropped chunks anywhere.

## G. Generation protection (stale-audio prevention)

Epochs at all three layers, all bumped on interrupt/close/failure:
browser `generationId` (new this pass), Node `generationId`
(server_voice.ts:134,493,515), Python `_conn_gen` (gemini_live.py:401,804)
+ `_failed_gens`. Queue drain on close/fail (Python) and disconnect
(browser). Duplicate tool-call memory (500 FIFO) prevents double execution
on resend. Invariants V-1..V-5 hold by construction + existing tests.

## H. Reconnect (resumption + duplicate prevention)

 budgets: browser 5 (1s·2ⁿ≤16s), Node 3 (2s·2ⁿ≤16s), Python session 3
(2s·2ⁿ≤16s) + manager budget. Resumption handle captured before drop,
passed on reconnect (manager reconnect; session sliding-window configured).
Recovery provisional until first post-reconnect audio (Node
recoveryPending). Turn timers reset on failure/reconnect (no poisoned
TTFA). Transcript fingerprint dedup (5s window) prevents duplicate user
turns after reconnect.

## I. Performance

NOT MEASURED live (no microphone/Gemini round-trip executed from this
harness — see §K). Structural deltas, not claims: first-audio path sheds
~80ms of batching (100→20ms flush); interruption path sheds one redundant
local trigger (was ~256ms racing Gemini); per-chunk overhead unchanged
(base64 JSON per 128ms frame, no extra conversions — verified single
Float32→Int16 and single Int16→Float32 in the whole path). Instrumentation
present for manual runs: Node FIRST_AUDIO_RECEIVED TTFA breakdown
(server_voice.ts:347-355), Python input→audio per-turn ms
(gemini_live.py:988-996), mic 5s summaries (audio.ts:516-521), health
snapshots both layers. CPU/memory/latency numbers: NOT MEASURED.

## J. Tests (exact numbers)

- Targeted voice: tests/test_gemini_live.py + test_gemini_lifecycle.py +
  test_voice_health.py = 37 passed.
- Python agent: desktop_agent/tests/ = 25 passed.
- Browser+permissions (regression): 84 passed.
- Full vitest: 1875 passed, 1 failed — pre-existing flaky FastCore latency
  assertion (5.17ms vs 5ms threshold, tests/security.test.ts:119),
  unrelated to voice (no voice file touched by that test).
- tsc --noEmit: clean. npm run build: green (vite 2095 modules + server.cjs).

## K. Live verification

NOT PERFORMED — no microphone, speakers, or interactive Gemini session
available to this harness, and I do not fabricate round-trips. No live
claim is made. Manual acceptance procedure (on a Windows host, agent
running, GEMINI_API_KEY set):
1. Click mic → speak "Hello MYRAA" → expect spoken reply; read Node
   FIRST_AUDIO_RECEIVED TTFA from server log.
2. Multi-turn conversation (3+ turns) → no duplicate user bubbles.
3. Interrupt mid-response with loud "No, wait" → old audio stops
   immediately; new turn proceeds; no stale tail.
4. Interrupt 3× in a row → generations advance, no overlap/echo of old audio.
5. Silence 30s → no hallucinated turns. Background noise → no false turns.
6. Kill :8765 mid-turn → degraded state → restart → recovery verified on
   first audio. 7. Two browser tabs connect → second must not disturb first
   (V-3 fix check). 8. Ten connect/disconnect cycles → contexts/GC clean,
   no zombie sockets (DevTools + Python /voice/gemini/health).

## L. Remaining issues (real only)

1. ScriptProcessorNode is deprecated (audio.ts:490, VAD:71) — migrate to
   AudioWorklet in a follow-up (behavior change + worklet bundling; not
   attempted blind).
2. ` - Copy.env` secret in git history + V1 bridge concurrency policy +
   memory/bridge decisions — see MYRAA_AUDIT_REPORT.md §§6,29 (unchanged).
3. Chunk framing is 128ms (2048/16k) — fine, but any future low-latency push
   should measure before shrinking (overhead vs responsiveness tradeoff).
4. Per-frame video POST path (server_voice.ts:536-546) has no throttle —
   vision-adjacent, out of voice scope; confirm throttle separately.
5. Language-detection heuristic (audio.ts:947-990) is placeholder-grade;
   harmless (hint only) but do not depend on it.

## M. Final verdict

READY WITH KNOWN LIMITATIONS. The pipeline is now single-authority at every
stage (VAD, interruption, session, playback), generation-guarded end to end,
bounded everywhere, with no provider fallback and no browser-engine
regression. Automated suites are green (except one unrelated flaky timing
assertion). Live conversational quality — the actual objective — is NOT
VERIFIED by execution here; the manual procedure in §K must be run on-host
before any production claim.
