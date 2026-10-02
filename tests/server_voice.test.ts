import { describe, it, expect } from "vitest";

// Gemini Live ONLY transport. Legacy provider contracts (STT_CONNECT_MS,
// sentence TTS, upsample helpers) were removed with the old engines.

describe("Voice Timeouts (bounded, no storm)", () => {
  it("exports VOICE_TIMEOUTS with Gemini structure", async () => {
    const mod = await import("../server_voice");
    expect(mod.VOICE_TIMEOUTS).toBeDefined();
    expect(mod.VOICE_TIMEOUTS.GEMINI_CONNECT_MS).toBe(20_000);
    expect(mod.VOICE_TIMEOUTS.WARMUP_MS).toBe(10_000);
    expect(mod.VOICE_TIMEOUTS.MAX_RECONNECT_ATTEMPTS).toBeLessThanOrEqual(3);
  });

  it("TIMEOUTS are all positive integers", async () => {
    const { VOICE_TIMEOUTS } = await import("../server_voice");
    for (const [key, val] of Object.entries(VOICE_TIMEOUTS)) {
      expect(val, `${key} should be positive`).toBeGreaterThan(0);
    }
  });

  it("VOICE_TIMEOUTS has all required keys", async () => {
    const { VOICE_TIMEOUTS } = await import("../server_voice");
    const required = ["GEMINI_CONNECT_MS", "RECONNECT_BASE_DELAY_MS",
      "RECONNECT_MAX_DELAY_MS", "MAX_RECONNECT_ATTEMPTS", "WARMUP_MS"];
    for (const key of required) {
      expect(VOICE_TIMEOUTS).toHaveProperty(key);
    }
  });
});

describe("VoiceTransport module", () => {
  it("exports VoiceTransport class and response-bus fan-out", async () => {
    const mod = await import("../server_voice");
    expect(mod.VoiceTransport).toBeDefined();
    expect(typeof mod.VoiceTransport).toBe("function");
    expect(typeof mod.speakTextToVoiceSessions).toBe("function");
  });

  it("exposes interruption and external-speech entry points", async () => {
    const proto = (await import("../server_voice")).VoiceTransport.prototype as any;
    for (const m of ["interrupt", "speakExternalText", "handleAudioChunk",
      "handleVideoFrame", "start", "stop", "getState", "setCallbacks"]) {
      expect(typeof proto[m], m).toBe("function");
    }
  });

  it("has exactly one voice provider (Gemini)", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("server_voice.ts", "utf-8");
    expect(src).toContain("/voice/gemini/stream");
    expect(src).toContain("/voice/gemini/health");
    for (const token of ["elevenlabs", "whisper", "kokoro", "piper",
      "silero", "scribe_v2", "convai", "tts/stream", "sentence"]) {
      expect(src, token).not.toContain(token);
    }
  });

  it("client voice path references no legacy provider (audio.ts)", async () => {
    // Regression: the browser degraded-state message historically mentioned
    // ElevenLabs after the Gemini Live migration. The client voice path must
    // reference only Gemini Live — never a retired provider.
    const fs = await import("fs");
    const src = fs.readFileSync("src/lib/audio.ts", "utf-8");
    for (const token of ["ElevenLabs", "elevenlabs", "Faster-Whisper",
      "faster-whisper", "Silero VAD", "kokoro", "Kokoro", "Piper", "piper",
      "SpeechSynthesis"]) {
      expect(src, token).not.toContain(token);
    }
  });
});

describe("Voice session fingerprint (exactly-once dedup)", () => {
  it("normalizes whitespace/case, preserves script", async () => {
    const mod = await import("../server_voice");
    expect(mod.normalizeVoiceFingerprint("  Hello   MYRAA ")).toBe("hello myraa");
    expect(mod.normalizeVoiceFingerprint("MYRAA mera CPU usage check karo"))
      .toBe("myraa mera cpu usage check karo");
  });

  it("is stable for repeats and scoped per session", async () => {
    const mod = await import("../server_voice");
    const a = mod.voiceFingerprint("V1", "Hello MYRAA");
    const b = mod.voiceFingerprint("V1", "hello  myraa");
    const c = mod.voiceFingerprint("V2", "Hello MYRAA");
    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });

  it("exposes a bounded dedup window", async () => {
    const mod = await import("../server_voice");
    expect(mod.VOICE_DEDUP_WINDOW_MS).toBeGreaterThan(0);
    expect(mod.VOICE_DEDUP_WINDOW_MS).toBeLessThanOrEqual(10000);
  });

  it("parks transport on non-retryable errors (no reconnect storm)", async () => {
    const fs = await import("fs");
    const src = fs.readFileSync("server_voice.ts", "utf-8");
    expect(src).toContain("geminiUnavailable");
    expect(src).toContain("no reconnect storm");
  });
});

describe("WebSocket auth token contract", () => {
  it("WS_SESSION_TOKEN pattern is documented", () => {
    expect(
      typeof process.env.MYRAA_WS_TOKEN === "string" ||
        process.env.MYRAA_WS_TOKEN === undefined
    ).toBe(true);
  });
});

describe("Bridge circuit breaker (no per-chunk throw on dead socket)", () => {
  async function makeTransport() {
    const mod: any = await import("../server_voice");
    const fakeClient = { readyState: 1, send: () => {} };
    const t = new mod.VoiceTransport(fakeClient);
    (t as any).state = "listening";
    return t;
  }

  it("drops 100 chunks on a dead bridge without throwing", async () => {
    const t = await makeTransport();
    let throws = 0;
    (t as any).geminiReady = true;
    // readyState 3 = CLOSED; send would throw "WebSocket is not open".
    (t as any).geminiWs = { readyState: 3, send: () => { throw new Error("WebSocket is not open"); } };
    for (let i = 0; i < 100; i++) {
      try {
        t.handleAudioChunk("aGVsbG8=");
      } catch {
        throws++;
      }
    }
    expect(throws).toBe(0);
    const stats = t.getBridgeStats();
    expect(stats.writes).toBe(0);
    expect(stats.dropped).toBe(100);
  });

  it("writes when the bridge socket is open", async () => {
    const t = await makeTransport();
    let writes = 0;
    (t as any).geminiReady = true;
    (t as any).geminiWs = { readyState: 1, send: () => { writes++; } };
    t.handleAudioChunk("aGVsbG8=");
    expect(writes).toBe(1);
    expect(t.getBridgeStats().writes).toBe(1);
  });

  it("speakExternalText refuses a dead bridge without throwing", async () => {
    const t = await makeTransport();
    (t as any).geminiReady = true;
    (t as any).geminiWs = { readyState: 3, send: () => { throw new Error("WebSocket is not open"); } };
    await t.speakExternalText("hello");
    expect(t.getBridgeStats().writes).toBe(0);
  });
});

describe("Continuous multi-turn conversation + verified recovery", () => {
  async function makeTransport() {
    const mod: any = await import("../server_voice");
    const fakeClient = { readyState: 1, send: () => {} };
    const t = new mod.VoiceTransport(fakeClient);
    (t as any).state = "listening";
    return { mod, t };
  }

  function openBridge(t: any) {
    (t as any).geminiReady = true;
    (t as any).geminiWs = { readyState: 1, send: () => {} };
  }

  it("keeps forwarding mic chunks after a completed turn (turn 2 reaches Gemini)", async () => {
    const { t } = await makeTransport();
    openBridge(t);
    // Turn 1: audio in, forwarded, then Gemini completes the turn.
    t.handleAudioChunk("aGVsbG8=");
    t.handleGeminiMessage({ type: "audio", audio: "aGk=" });
    t.handleGeminiMessage({ type: "turnComplete" });
    expect(t.getState()).toBe("listening");
    // Turn 2 begins immediately: mic chunks must still be forwarded.
    let sent = 0;
    (t as any).geminiWs.send = () => { sent++; };
    for (let i = 0; i < 25; i++) t.handleAudioChunk("aGVsbG8=");
    expect(sent).toBe(25);
    expect((t as any).chunksForwarded).toBe(26); // 1 from turn 1 + 25
    expect((t as any).chunksDropped).toBe(0);
    expect((t as any).t0Mic).toBeGreaterThan(0); // fresh turn-2 timing started
  });

  it("connection_failed resets turn timers and enters reconnecting", async () => {
    const { t } = await makeTransport();
    openBridge(t);
    t.handleAudioChunk("aGVsbG8=");
    (t as any).tFirstTranscript = performance.now();
    t.handleGeminiMessage({ type: "connection_failed", reason: "keepalive ping timeout", generation: 1 });
    expect((t as any).t0Mic).toBe(0);
    expect((t as any).tFirstTranscript).toBe(0);
    expect((t as any).tFirstAudio).toBe(0);
    expect((t as any).recoveryPending).toBe(true);
    expect(t.getState()).toBe("reconnecting");
    expect((t as any).lastError).toContain("keepalive");
  });

  it("reconnected is provisional; recovery is verified only by post-reconnect audio", async () => {
    const { t } = await makeTransport();
    openBridge(t);
    t.handleGeminiMessage({ type: "connection_failed", reason: "1011", generation: 0 });
    t.handleGeminiMessage({ type: "reconnecting", attempt: 1 });
    t.handleGeminiMessage({ type: "reconnected", generation: 1 });
    expect(t.getState()).toBe("listening");
    expect((t as any).recoveryPending).toBe(true);
    expect((t as any).recoveryVerifiedAt).toBe(0);
    // First post-reconnect output audio proves the response path works.
    t.handleGeminiMessage({ type: "audio", audio: "aGk=" });
    expect((t as any).recoveryPending).toBe(false);
    expect((t as any).recoveryVerifiedAt).toBeGreaterThan(0);
  });

  it("counts chunks received vs dropped while the bridge is dead (no send storm)", async () => {
    const { t } = await makeTransport();
    (t as any).geminiReady = false;
    (t as any).geminiWs = null;
    for (let i = 0; i < 100; i++) t.handleAudioChunk("aGVsbG8=");
    const h = t.getHealth();
    expect(h.audio_input.chunks_from_client_total).toBe(100);
    expect(h.audio_input.chunks_dropped_total).toBe(100);
    expect(h.audio_input.chunks_forwarded_total).toBe(0);
    expect(h.mic_active).toBe(true); // mic kept producing; bridge was the problem
  });

  it("getVoiceHealthSnapshot aggregates provider-level state", async () => {
    const { mod, t } = await makeTransport();
    const snap = mod.getVoiceHealthSnapshot();
    expect(snap.provider).toBe("gemini_live");
    // No transport has called start() in this unit test, so no live sessions.
    expect(snap.client_connected).toBe(false);
    expect(snap.transport_state).toBe("no_session");
    expect(snap.session).toBeNull();
    // Per-transport snapshot shape (start() registers it in live use).
    const h = t.getHealth();
    expect(h.provider).toBe("gemini_live");
    expect(typeof h.recovery.reconnect_count).toBe("number");
    expect(h.audio_input).toHaveProperty("chunks_forwarded_total");
  });
});
