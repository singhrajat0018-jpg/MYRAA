# MYRAA VOICE PIPELINE — 0→100 AUDIT & UPGRADE

Date: 2026-09-19. Engine: Gemini Live ONLY (no fallback added, none present).
Prior reports used as implementation evidence only — every finding below was
independently re-verified against live code this pass. No live microphone /
Gemini round-trip was executed from this harness: anything requiring hardware
or network inference is marked NOT LIVE VERIFIED, never claimed.

## A. Existing architecture

Browser `MyraaAudioSession` (src/lib/audio.ts:78) owns mic + playback.
Mic: getUserMedia (EC/NS/AGC, optional deviceId) → 16kHz AudioContext →
capture processor → Float32→Int16LE→base64 → WS `/live`. Node `VoiceTransport`
(server_voice.ts:114, one per /live connection) forwards straight to Python
(no buffering; drop-if-closed). Python bridge (`voice_gemini_stream_ws`,
main.py:2046) owns one `GeminiLiveSessionManager` → one `GeminiLiveSession`
→ Google GenAI SDK realtime session (model gemini-3.1-flash-live-preview,
voice Aoede). Mic bytes flow through a bounded asyncio.Queue(64) via a
single generation-gated sender; one receiver loop pumps events; tool calls
run off-loop (cap 8) through allowlist→finance-block→validate→authorize→
sanitize→respond. 24kHz PCM returns over the same path into a browser jitter
buffer → generation-checked decode → gapless AudioBufferSource scheduling.

## B. Complete runtime flow

SPEAK → mic track → input ctx (ScriptProcessor 2048/128ms BEFORE this pass;
AudioWorklet 1024/64ms AFTER) → `handleMicFrame` (PCM16LE+base64, mic
diagnostics, 2s language hint) → `/live` → `handleAudioChunk` (state gate,
circuit-breaker write) → Python `submit_audio` (READY gate, drop-oldest) →
sender (`gen == _conn_gen` check) → Gemini realtime input → Gemini native
VAD/turns → `receive_loop` → `_handle_message` (transcripts/audio/interrupt/
tool_call/turn_complete/resumption/GoAway) → bridge `_pump_out` →
`handleGeminiMessage` (TTFA timers, dedup, state) → `/live` client →
`playAudioPCMChunk` (20ms jitter buffer) → `flushAudioBuffer`
(generation triple-check, decode, schedule +15ms) → speakers. Interrupt path:
Gemini `interrupted` → Python `generation_seq++` → Node `generationId++` +
client `interrupted` → browser `generationId++` + source stop + buffer clear
+ `interrupt` upstream.

## C. Dependency map (owner → file:function/class)

1. mic capture: `MyraaAudioSession.connect` (audio.ts:316), frames via
   AudioWorklet `myraa-capture` else ScriptProcessor fallback.
2. audio contexts: same (`inputAudioCtx` 16k, `outputAudioCtx` 24k).
3. VAD: Gemini native (authority); local `VoiceActivityDetector`
   (voiceActivityDetector.ts:25) advisory/UI only.
4. turn detection: Gemini (`turn_complete`, transcriptions).
5. interruption: Gemini `interrupted` → `interrupt()` chain (§B).
6. Node transport: `VoiceTransport` per connection (server_voice.ts:114).
7. Python transport: per-bridge `_pump_in/_pump_out` (main.py:2105-2116).
8. Gemini session: `GeminiLiveSession` (gemini_live.py:375), one per bridge.
9. audio sender: `_audio_sender` (gemini_live.py:694), exactly one.
10. audio receiver: `receive_loop` (gemini_live.py:890), exactly one.
11. playback: `MyraaAudioSession` (`playAudioPCMChunk`/`flushAudioBuffer`).
12. reconnect: layered budgets — browser 5, Node 3, session 3 + manager.
13. generation/epoch: browser `generationId`, Node `generationId`, Python
    `_conn_gen` + `_failed_gens`.
14. transcripts: Gemini transcriptions → Node fingerprint dedup (5s).
15. tool calls: `GeminiToolRouter` (gemini_live.py:211) + `_handle_tool_call`.
16. session lifecycle: `GeminiLiveSessionManager` per bridge (gemini_live.py).
17. error state: `ConnState` machine (gemini_live.py:349) + Node transport
    state + `_fail_once` convergence.

## D. All latency sources (budget; UNKNOWN where unmeasurable here)

- Frame quantization: 128ms BEFORE → 64ms AFTER (worklet 1024-frame).
- VAD tap: parallel, +0 path latency.
- PCM+base64+JSON encode: sub-ms +33% bytes (measured in unit test: 2048B →
  2732 chars).
- Node forward: ~0–2ms, no buffer (structurally bounded; NOT MEASURED live).
- Python queue/sender wakeup: ~ms when drained (NOT MEASURED live).
- Network + Gemini inference: UNKNOWN (dominant by construction).
- Browser jitter buffer: 100ms BEFORE → 20ms AFTER.
- Decode + schedule lookahead: ~1–3ms + 15ms (structural).
- Controllable client-side budget: ≈163ms BEFORE → ≈100ms AFTER, plus
  UNKNOWN network/inference. TTFA instrumentation exists at Node
  (FIRST_AUDIO_RECEIVED breakdown) and Python (per-turn input→audio) for
  on-host measurement.

## E–H. Bugs found (ID/SEVERITY/FILE/FUNCTION/SYMPTOM/ROOT CAUSE/FIX/VERIFICATION/STATUS)

### VW-1 / P1 / audio.ts:475-523 / connect-capture / 128ms main-thread framing + deprecated API
SYMPTOM: capture quantized at 128ms on the UI thread; deprecation warnings;
jank risk stalls capture (the MIC_CAPTURE_STALL diagnostic exists for this).
ROOT CAUSE: ScriptProcessor-only capture. FIX: AudioWorklet
`myraa-capture` (1024-sample/64ms, transferable frames) first,
ScriptProcessor fallback preserved; both funnel into shared `handleMicFrame`
(identical wire bytes); Blob-URL module + `worker-src 'self' blob:` CSP
(server.ts:205-216). VERIFICATION: tsc + 7 new pcm.test.ts + full vitest
1883/1883 + build. STATUS: implemented; live frame timing NOT LIVE VERIFIED
(see manual test 1).
### VW-2 / P1 / main.py:2029-2088 / voice_gemini_stream_ws / second tab disturbs first
SYMPTOM: `_gemini_manager_singleton` overwritten per bridge; closer cleared
it; health reported last-writer. ROOT CAUSE: process-global alias for
per-connection state. FIX: alias deleted; `_gemini_bridges_active` counter;
health reports count (no fake per-session snapshot). VERIFICATION: grep zero
refs + 70 voice/agent pytest pass. STATUS: implemented.
### VW-3 / P2 / audio.ts playback / unbounded jitter structures
SYMPTOM: `audioBuffer` and `activeSources` grew without bound under stall.
ROOT CAUSE: no caps. FIX: 200-chunk drop-oldest + 16-source cap with
rate-limited counters. VERIFICATION: tsc + suite. STATUS: implemented.
### VW-4 / P3 / failure_containment.py:510, action_validator.py:829 / stale "Playwright" comments
SYMPTOM: misleading engine references. ROOT CAUSE: leftover wording. FIX:
reworded (zero behavior). VERIFICATION: grep + suite. STATUS: implemented.
### Prior-pass (re-verified present, not re-done)
VAD authority demotion, 100→20ms flush, client generationId triple-check,
singleton-assignment removal (completed by VW-2), backlog error response,
_completed 500-cap, transcript role routing — all confirmed in current tree.

## I. Fixes performed (why each was necessary)

VW-1: frame quantization + main-thread capture is the largest controllable
client latency/jank source; worklet halves it with fallback safety. VW-2:
concurrent-connection corruption of voice state. VW-3: memory-growth DoS
shape in a realtime loop. VW-4: architecture-truth in docs/comments.
PCM extraction (pcm.ts): single tested contract for both capture paths.

## J. Tests

New: tests/pcm.test.ts (7: silence/endianness/clipping/frame sizes/
round-trips ≤2 LSB — bound documents the pre-existing 0x7FFF/32768
asymmetry, preserved verbatim). Full vitest: 21 files, 1883 passed (was
1876). Python voice+agent targeted: 70 passed. tsc clean. (Full 1666-test
Python sweep ran green in the prior pass; this pass re-ran all voice/agent
touchpoints plus full vitest/build.)

## K. Performance instrumentation

Pre-existing + kept: Node TTFA breakdown + 1s audio roll-ups + health
snapshot; Python per-turn input→audio ms, queue depth, drop/dead-write
counters, loop-lag probe; browser 5s MIC_OK + stall/drop warnings (+
capture-mode tag added). No raw audio/key/secret logging anywhere on the
path (verified by inspection).

## L. Live verification status

NOT LIVE VERIFIED (no mic/speakers/interactive Gemini in this harness).
Automated + static verification complete (§J + tsc + build + scans).
Manual Windows acceptance procedure (§P) is the remaining gate.

## M. Remaining limitations

ScriptProcessor fallback retained (by design); advisory VAD still uses a
second AudioContext + deprecated processor (P3 follow-up: worklet-ize or
remove); bridge event queue unbounded (main.py:2081 — drops nothing today;
watch item); video-frame POST throttle unverified; ` - Copy.env` history +
memory-authority + icon.ico from the system audit are untouched here.

## N. Final architecture

§28 target holds: ONE engine, ONE turn authority (Gemini VAD), ONE session
owner per bridge, ONE sender, ONE receiver, ONE playback owner, end-to-end
epochs, bounded queues (except noted bridge event queue), no fallback
provider, no Playwright, finance/permission boundaries intact.

## O. Manual Windows acceptance procedure

1. Mic HearCheck: connect → MIC_CAPTURE_START shows ctx 16k +
   CAPTURE_MODE=worklet (fallback `script` acceptable if logged) → speak →
   MIC_OK chunks ≈78/5s (64ms) or ≈39/5s (128ms fallback).
2. "Hello MYRAA" → spoken reply; record Node FIRST_AUDIO_RECEIVED TTFA.
3. 3-turn conversation → no duplicate bubbles.
4. Interrupt mid-response ("No, wait") → immediate stop, no stale tail;
   repeat 3×.
5. 30s silence → no phantom turns; fan/keyboard noise → no false barge-in
   storms.
6. Kill :8765 mid-turn → degraded → restart → recovery verified on first
   audio only.
7. Two tabs connect → independent sessions; first unaffected (VW-2).
8. 10 connect/disconnect cycles → no context/socket/task growth (health +
   DevTools).
9. Each: PASS/FAIL/NOT VERIFIED. No step may be skipped for a production
   claim.

## P. Before/after measurements

No live numbers exist (prior or current) — both honest states are
"structural deltas, NOT MEASURED": frame 128→64ms, jitter 100→20ms,
client controllable budget ≈163→≈100ms + UNKNOWN network/inference.
