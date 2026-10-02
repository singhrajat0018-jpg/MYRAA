/**
 * MYRAA Voice Transport — Gemini Live API ONLY.
 *
 * Architecture (locked):
 *   Browser mic (PCM16 mono 16kHz, existing audio.ts)
 *     -> Node VoiceTransport (/live — transport only, no intelligence)
 *     -> Python GeminiLiveSessionManager (/voice/gemini/stream)
 *     -> Gemini Live API (VAD + STT + response + native 24kHz audio + barge-in)
 *     -> MYRAA Tool Bus (Python allowlist + authorization + finance firewall)
 *     -> browser playback (existing queue, generation guards)
 *
 * There is exactly ONE voice provider: Gemini Live. No legacy-provider code
 * paths exist in this file. No fallback chains. Gemini failure surfaces as
 * a structured error, never a silent provider switch.
 */

import WebSocket from "ws";

const DESKTOP_AGENT_URL = process.env.DESKTOP_AGENT_URL || "http://127.0.0.1:8765";

// ── Timeout / retry policy (§28: bounded, no storm) ──────────────
export const VOICE_TIMEOUTS = {
  /** Max time to wait for the Gemini bridge WebSocket connection */
  GEMINI_CONNECT_MS: 20_000,
  /** Base delay for bounded reconnect backoff */
  RECONNECT_BASE_DELAY_MS: 2000,
  /** Max delay for bounded reconnect backoff */
  RECONNECT_MAX_DELAY_MS: 16000,
  /** Maximum automatic reconnect attempts before parking */
  MAX_RECONNECT_ATTEMPTS: 3,
  /** Max time for model warm-up request */
  WARMUP_MS: 10_000,
} as const;

export type VoiceTransportState =
  | "idle"
  | "connecting"
  | "listening"
  | "speaking"
  | "interrupted"
  | "reconnecting"
  | "degraded"
  | "error"
  | "disconnected";

export interface VoiceTransportConfig {
  maxReconnectAttempts: number;
  reconnectBaseDelayMs: number;
  reconnectMaxDelayMs: number;
}

const DEFAULT_CONFIG: VoiceTransportConfig = {
  maxReconnectAttempts: VOICE_TIMEOUTS.MAX_RECONNECT_ATTEMPTS,
  reconnectBaseDelayMs: VOICE_TIMEOUTS.RECONNECT_BASE_DELAY_MS,
  reconnectMaxDelayMs: VOICE_TIMEOUTS.RECONNECT_MAX_DELAY_MS,
};

// ── Transcript fingerprint (UI duplicate protection, §26) ────────
// Fingerprint-only normalization; original text always preserved.
export function normalizeVoiceFingerprint(text: string): string {
  return text.normalize("NFKC").split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

export function voiceFingerprint(sessionId: string, text: string): string {
  const norm = normalizeVoiceFingerprint(text);
  let h = 0x811c9dc5;
  const s = sessionId + "" + norm;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}

export const VOICE_DEDUP_WINDOW_MS = 5000;

// ── Active voice transports: typed chat auto-speaks through these ──
// Same canonical response fans out to UI text + voice (§15 response bus).
const activeVoiceTransports = new Set<VoiceTransport>();

export function speakTextToVoiceSessions(text: string): void {
  for (const t of activeVoiceTransports) {
    try {
      void t.speakExternalText(text);
    } catch {
      /* one bad session must not break the others */
    }
  }
}

/**
 * §18: module-level Node-side voice health snapshot (read-only).
 * Aggregates all live /live transports; merge with Python
 * /voice/gemini/health at the /api/voice/health route.
 */
export function getVoiceHealthSnapshot(): Record<string, any> {
  const sessions = Array.from(activeVoiceTransports).map((t) => {
    try {
      return t.getHealth();
    } catch {
      return { transport_state: "unknown", error: "snapshot failed" };
    }
  });
  const primary = sessions[0] ?? null;
  return {
    provider: "gemini_live",
    client_connected: sessions.length > 0,
    transport_state: primary ? primary.transport_state : "no_session",
    session: primary,
    sessions,
  };
}

export class VoiceTransport {
  private clientWs: WebSocket;
  private state: VoiceTransportState = "idle";
  private config: VoiceTransportConfig;
  private reconnectAttempts = 0;
  private intentionalDisconnect = false;
  private geminiUnavailable = false;

  // Session identity (§7): one per /live connection.
  private readonly voiceSessionId: string =
    `V${Date.now().toString(36).toUpperCase()}`;

  // UI duplicate protection for re-emitted transcripts.
  private lastUserFp = "";
  private lastUserAt = 0;

  // Conversation state (role-tagged; user turns feed memory via callback).
  private dialogueHistory: { role: string; text: string }[] = [];

  // Generation guard: stale audio after interruption is discarded (§7/27).
  private generationId = 0;

  // Monotonic voice-TTFA telemetry (§61 metrics): mic -> transcript -> audio.
  private t0Mic = 0;
  private tFirstTranscript = 0;
  private tFirstAudio = 0;
  private turnCount = 0;

  // Gemini bridge connection to Python.
  private geminiWs: WebSocket | null = null;
  private geminiReady = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // Bridge-write circuit breaker counters (storm-proofing: drops are counted,
  // never logged per chunk, never retried, never replayed after reconnect).
  private bridgeWrites = 0;
  private droppedBridgeChunks = 0;

  // ── Voice health diagnostics (§2/3/16/17/18) ──────────────────────
  // Aggregate counters only — never per-chunk logging.
  private chunksFromClient = 0;      // mic chunks received from the browser
  private chunksForwarded = 0;       // mic chunks written to the Python bridge
  private chunksDropped = 0;         // mic chunks dropped (state/bridge gates)
  private bytesFromClient = 0;
  private bytesForwarded = 0;
  private lastClientChunkAt = 0;     // Date.now() of last client mic chunk
  private lastBridgeAudioAt = 0;     // Date.now() of last output audio (Gemini)
  private lastGeminiEventAt = 0;     // Date.now() of last bridge message
  private lastSecondMark = Date.now();
  private winChunksFromClient = 0;
  private winChunksForwarded = 0;
  private winChunksDropped = 0;
  private reconnectCount = 0;
  private lastError: string | null = null;
  // §16: recovery is "provisional" until the first post-reconnect output
  // audio actually flows — never claim full recovery earlier.
  private recoveryPending = false;
  private recoveryVerifiedAt = 0;

  // Phase 7.4: periodic warmup interval (kept; now a Gemini health check).
  private _warmupInterval: ReturnType<typeof setInterval> | null = null;

  // Callbacks (same shape as before; server.ts untouched).
  private onStateChange?: (state: VoiceTransportState) => void;
  private onTranscription?: (role: "user" | "model", text: string) => void;
  private onAudio?: (base64Audio: string) => void;
  private onToolCall?: (name: string, args: any, respond: (result: any) => void) => void;
  private onMemorySync?: (memories: any[]) => void;
  private onTurnComplete?: () => void;

  constructor(clientWs: WebSocket, config?: Partial<VoiceTransportConfig>) {
    this.clientWs = clientWs;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Initialize voice transport — Gemini Live ONLY.
   * Missing key / unconfigured backend -> structured degraded error.
   * Never falls back to another provider.
   */
  async start(): Promise<void> {
    this.setState("connecting");

    try {
      const resp = await fetch(`${DESKTOP_AGENT_URL}/voice/gemini/health`);
      const health = await resp.json();
      if (!health?.voice?.configured) {
        this.sendError("GEMINI_API_KEY is not configured. Voice unavailable; text chat remains available.");
        this.setState("degraded");
        return;
      }
      console.log(`[VoiceTransport] Gemini Live model=${health.voice.model} voice=${health.voice.voice}`);
    } catch (err: any) {
      this.sendError(`Python backend unavailable: ${err.message}`);
      this.setState("error");
      return;
    }

    await this.connectGemini();

    activeVoiceTransports.add(this);
    this.setState("listening");
    console.log("[VoiceTransport] Started — Gemini Live voice mode");

    this.warmUpModel();
    this._warmupInterval = setInterval(() => this.warmUpModel(), 10 * 60 * 1000);
  }

  // ─── Gemini bridge ────────────────────────────────────────────

  private async connectGemini(): Promise<void> {
    if ((this.geminiWs && (this.geminiReady)) || this.geminiUnavailable) return;

    const wsUrl = `${DESKTOP_AGENT_URL.replace(/^http/, "ws")}/voice/gemini/stream`;

    try {
      this.geminiWs = new WebSocket(wsUrl);

      this.geminiWs.on("open", () => {
        console.log("[VoiceTransport] Gemini bridge TCP connected, waiting for session_started");
      });

      this.geminiWs.on("message", (raw: Buffer) => {
        try {
          const data = JSON.parse(raw.toString());
          this.handleGeminiMessage(data);
        } catch {
          // ignore parse errors
        }
      });

      this.geminiWs.on("close", (code: number, reason: Buffer) => {
        console.log(`[VoiceTransport] Gemini bridge closed code=${code} reason=${reason?.toString() || "-"}`);
        this.geminiReady = false;
        this.geminiWs = null;
        this.scheduleReconnect();
      });

      this.geminiWs.on("error", (err) => {
        console.error("[VoiceTransport] Gemini bridge error:", (err as Error).message);
        this.geminiReady = false;
      });
    } catch (err: any) {
      console.error("[VoiceTransport] Gemini connect failed:", err.message);
      this.geminiReady = false;
      this.scheduleReconnect();
    }
  }

  /** Bounded reconnect (§28: 3 attempts max, then parked degraded). */
  private scheduleReconnect(): void {
    if (this.intentionalDisconnect || this.geminiUnavailable) {
      if (this.geminiUnavailable) {
        console.log("[VoiceTransport] Gemini unavailable (non-retryable) — no reconnect storm");
      }
      return;
    }
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.log("[VoiceTransport] Gemini reconnect budget exhausted — voice degraded, text chat alive");
      this.setState("degraded");
      return;
    }
    if (this.reconnectTimer) return;

    const delay = Math.min(
      this.config.reconnectBaseDelayMs * Math.pow(2, this.reconnectAttempts),
      this.config.reconnectMaxDelayMs,
    );
    this.reconnectAttempts++;

    this.setState("reconnecting");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.intentionalDisconnect && !this.geminiUnavailable) {
        console.log(`[VoiceTransport] Gemini reconnect attempt ${this.reconnectAttempts}`);
        this.connectGemini();
      }
    }, delay);
  }

  /**
   * Handle messages from the Python Gemini bridge.
   * Gemini is the authority for VAD/turn detection — no local commit logic.
   */
  private handleGeminiMessage(data: any): void {
    const type = data.type;
    this.lastGeminiEventAt = Date.now();

    if (type === "connected") {
      return;
    }

    if (type === "session_started") {
      console.log(`[VoiceTransport] Gemini session started session=${data.session_id} model=${data.model}`);
      this.geminiReady = true;
      this.reconnectAttempts = 0;
      if (this.state === "reconnecting" || this.state === "connecting") {
        this.setState("listening");
      }
      return;
    }

    if (type === "partial_transcript") {
      const text = data.text?.trim();
      if (!text) return;
      if (data.role === "user") {
        // Duplicate protection: same turn re-emitted after reconnect.
        const fp = voiceFingerprint(this.voiceSessionId, text);
        const nowMs = performance.now();
        if (fp === this.lastUserFp && (nowMs - this.lastUserAt) < VOICE_DEDUP_WINDOW_MS) {
          return;
        }
        this.lastUserFp = fp;
        this.lastUserAt = nowMs;
        if (!this.tFirstTranscript) this.tFirstTranscript = performance.now();
        this.sendToClient({ type: "transcription", role: "user", text });
        this.onTranscription?.("user", text);
        this.dialogueHistory.push({ role: "user", text });
      } else {
        this.sendToClient({ type: "transcription", role: "model", text });
        this.onTranscription?.("model", text);
      }
      return;
    }

    if (type === "audio" && data.audio) {
      if (this.recoveryPending) {
        // §16: recovery is only PROVEN once output audio actually flows again.
        this.recoveryPending = false;
        this.recoveryVerifiedAt = Date.now();
        console.log("[VoiceTransport] RECOVERY_VERIFIED first post-reconnect audio flows");
      }
      this.lastBridgeAudioAt = Date.now();
      if (!this.tFirstAudio) {
        this.tFirstAudio = performance.now();
        const ttfa = this.t0Mic ? Math.round(this.tFirstAudio - this.t0Mic) : -1;
        const capToTranscript = (this.t0Mic && this.tFirstTranscript)
          ? Math.round(this.tFirstTranscript - this.t0Mic) : -1;
        const transcriptToAudio = (this.tFirstTranscript && this.tFirstAudio)
          ? Math.round(this.tFirstAudio - this.tFirstTranscript) : -1;
        console.log(`[VoiceTransport] FIRST_AUDIO_RECEIVED turn=${this.turnCount + 1} ttfa_ms=${ttfa} capture_to_transcript_ms=${capToTranscript} transcript_to_audio_ms=${transcriptToAudio}`);
      }
      this.setState("speaking", "gemini audio");
      this.sendToClient({ type: "audio", audio: data.audio });
      this.onAudio?.(data.audio);
      return;
    }

    if (type === "interrupted") {
      // Gemini detected user speech during playback: first-class barge-in.
      this.interrupt();
      return;
    }

    if (type === "turnComplete") {
      this.turnCount++;
      this.t0Mic = 0;
      this.tFirstTranscript = 0;
      this.tFirstAudio = 0;
      console.log(`[VoiceTransport] TURN_COMPLETE turn=${this.turnCount} — listening for next turn`);
      this.sendToClient({ type: "turnComplete" });
      this.onTurnComplete?.();
      if (this.dialogueHistory.length > 30) {
        this.dialogueHistory = this.dialogueHistory.slice(-30);
      }
      this.setState("listening", "turn complete");
      return;
    }

    if (type === "tool_result") {
      console.log(`[VoiceTransport] tool result name=${data.name} ok=${data.ok}`);
      return;
    }

    if (type === "reconnecting") {
      console.log(`[VoiceTransport] Gemini session reconnecting (${data.reason || data.attempt || "unknown"})`);
      this.setState("reconnecting");
      return;
    }

    if (type === "connection_failed") {
      console.log(`[VoiceTransport] CONNECTION_FAILED (${data.reason || "unknown"}) generation=${data.generation ?? "-"} — entering RECONNECTING, turn timers reset`);
      // §17: a turn interrupted by a dead connection must NOT poison the next
      // turn's TTFA — reset all turn timers now.
      this.lastError = String(data.reason || "connection failed");
      this.t0Mic = 0;
      this.tFirstTranscript = 0;
      this.tFirstAudio = 0;
      this.recoveryPending = true;
      this.recoveryVerifiedAt = 0;
      this.setState("reconnecting", "connection failed");
      return;
    }

    if (type === "reconnected") {
      // §16: NOT full recovery yet — only a provisionally READY session.
      this.reconnectCount++;
      this.recoveryPending = true;
      this.recoveryVerifiedAt = 0;
      // §17: never measure the next turn from pre-outage timestamps.
      this.t0Mic = 0;
      this.tFirstTranscript = 0;
      this.tFirstAudio = 0;
      console.log(`[VoiceTransport] RECONNECTED_READY (provisional) generation=${data.generation ?? "-"} — awaiting first post-reconnect turn to verify recovery`);
      this.reconnectAttempts = 0;
      this.setState("listening", "reconnected");
      return;
    }

    if (type === "error") {
      console.error("[VoiceTransport] Gemini error:", data.code, data.message);
      this.lastError = String(data.message || data.code || "gemini error");
      if (data.retryable === false) {
        this.geminiUnavailable = true;
        this.sendToClient({ type: "stt_error", code: data.code, message: data.message, retryable: false });
        this.setState("degraded");
      } else {
        this.sendToClient({ type: "stt_error", code: data.code, message: data.message, retryable: true });
        this.scheduleReconnect();
      }
      return;
    }
  }

  // ─── Audio handling ───────────────────────────────────────────

  /**
   * Handle incoming 16kHz PCM audio chunk from the browser client.
   * Forwarded straight to Gemini; no buffering, no local STT, no HTTP fallback.
   */
  handleAudioChunk(base64Audio: string): void {
    const now = Date.now();
    this.lastClientChunkAt = now;
    this.chunksFromClient++;
    this.winChunksFromClient++;
    this.bytesFromClient += base64Audio.length;

    if (this.state !== "listening" && this.state !== "speaking" && this.state !== "reconnecting") {
      this.chunksDropped++;
      this.noteAudioChunk(false);
      return;
    }

    if (!this.t0Mic) {
      this.t0Mic = performance.now();
    }

    // Circuit breaker: write ONLY to a verified-open bridge socket. A dead
    // bridge must never throw per chunk (ws.send on a closed socket throws
    // "WebSocket is not open") and chunks are dropped, never queued.
    if (this.geminiReady && this.geminiWs && this.geminiWs.readyState === WebSocket.OPEN) {
      try {
        this.geminiWs.send(JSON.stringify({ type: "audio", audio: base64Audio }));
        this.bridgeWrites++;
        this.chunksForwarded++;
        this.bytesForwarded += base64Audio.length;
        this.noteAudioChunk(true);
      } catch {
        this.geminiReady = false;
        this.droppedBridgeChunks++;
        this.chunksDropped++;
        this.noteAudioChunk(false);
      }
    } else {
      // If the bridge is down the chunk is dropped (never buffered/replayed).
      this.droppedBridgeChunks++;
      this.chunksDropped++;
      this.noteAudioChunk(false);
    }
  }

  /**
   * Speak canonical assistant text (typed chat auto-speak, §15 response bus).
   * Voice-rendering turn through the ACTIVE Gemini session — same audio path.
   */
  async speakExternalText(text: string): Promise<void> {
    if (!text?.trim()) return;
    if (this.state === "disconnected" || this.state === "error" || this.state === "degraded") return;
    if (!this.geminiReady || !this.geminiWs || this.geminiWs.readyState !== WebSocket.OPEN) return;
    const genId = ++this.generationId;
    this.setState("speaking");
    try {
      this.geminiWs.send(JSON.stringify({ type: "speak", text }));
      this.bridgeWrites++;
    } catch {
      this.geminiReady = false;
      this.droppedBridgeChunks++;
    }
    // Completion/cancellation tracked via turnComplete/interrupted events.
    if (genId !== this.generationId) return;
  }

  // ─── Interruption (first-class barge-in) ──────────────────────

  /**
   * Barge-in: invalidate current generation, clear stale audio, listen.
   * Called on Gemini interruption events and browser interrupt messages.
   */
  interrupt(): void {
    if (this.state === "speaking" || this.state === "listening") {
      const staleGen = this.generationId;
      this.generationId++;
      console.log("[Voice] interruption detected");
      console.log(`[Playback] generation G${staleGen} invalidated; queue clearing`);

      this.setState("interrupted");
      this.sendToClient({ type: "interrupted" });

      if (this.geminiWs && this.geminiWs.readyState === WebSocket.OPEN) {
        try {
          this.geminiWs.send(JSON.stringify({ type: "interrupt" }));
        } catch {
          // best-effort forward
        }
      }

      this.t0Mic = 0;
      this.tFirstTranscript = 0;
      this.tFirstAudio = 0;

      setTimeout(() => {
        if (this.state === "interrupted") {
          this.setState("listening");
        }
      }, 100);
    }
  }

  // ─── Video / Screen sharing (preserved; vision path, not voice STT) ──

  handleVideoFrame(base64Data: string): void {
    fetch(`${DESKTOP_AGENT_URL}/voice/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transcript: "[Screen frame received]",
        image: base64Data,
        request_id: `vf-${Date.now()}`,
      }),
    }).catch(() => {});
  }

  // ─── Lifecycle ────────────────────────────────────────────────

  private async warmUpModel(): Promise<void> {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), VOICE_TIMEOUTS.WARMUP_MS);
      const resp = await fetch(`${DESKTOP_AGENT_URL}/voice/warmup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const result = await resp.json();
      if (result.ok) {
        console.log("[VoiceTransport] warm-up:", JSON.stringify(result.voice || result.model || result));
      }
    } catch {
      // Non-fatal
    }
  }

  stop(): void {
    console.log(`[VoiceTransport] stopped session=${this.voiceSessionId}`);
    activeVoiceTransports.delete(this);
    this.intentionalDisconnect = true;

    if (this._warmupInterval) {
      clearInterval(this._warmupInterval);
      this._warmupInterval = null;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.geminiWs) {
      try { this.geminiWs.send(JSON.stringify({ type: "stop" })); } catch {}
      try { this.geminiWs.close(); } catch {}
      this.geminiWs = null;
      this.geminiReady = false;
    }

    this.setState("disconnected");

    fetch(`${DESKTOP_AGENT_URL}/voice/disconnect`, {
      method: "POST",
    }).catch(() => {});
  }

  // ─── Internal helpers ─────────────────────────────────────────

  private setState(state: VoiceTransportState, reason?: string): void {
    if (this.state !== state) {
      console.log(`[VoiceTransport] state ${this.state} -> ${state}${reason ? ` (${reason})` : ""}`);
    }
    this.state = state;
    this.onStateChange?.(state);
  }

  /** Rolling 1-second window roll-up (rate summaries, not per-chunk logs). */
  private noteAudioChunk(forwarded: boolean): void {
    if (forwarded) {
      this.winChunksForwarded++;
    } else {
      this.winChunksDropped++;
    }
    const now = Date.now();
    if (now - this.lastSecondMark >= 1000) {
      if (this.winChunksFromClient > 0 || this.winChunksDropped > 0) {
        console.log(`[VoiceTransport] audio_1s received=${this.winChunksFromClient} forwarded=${this.winChunksForwarded} dropped=${this.winChunksDropped}`);
      }
      this.lastSecondMark = now;
      this.winChunksFromClient = 0;
      this.winChunksForwarded = 0;
      this.winChunksDropped = 0;
    }
  }

  private sendToClient(data: any): void {
    if (this.clientWs.readyState === WebSocket.OPEN) {
      this.clientWs.send(JSON.stringify(data));
    }
  }

  private sendError(message: string): void {
    this.sendToClient({ type: "error", error: message });
  }

  // ─── Public API ───────────────────────────────────────────────

  getState(): VoiceTransportState {
    return this.state;
  }

  /** Bridge circuit-breaker stats (writes vs dropped chunks). */
  getBridgeStats(): { writes: number; dropped: number; ready: boolean } {
    return { writes: this.bridgeWrites, dropped: this.droppedBridgeChunks, ready: this.geminiReady };
  }

  /** §18 Node-side voice health snapshot for this transport (read-only). */
  getHealth(): Record<string, any> {
    const now = Date.now();
    const age = (ts: number) => (ts > 0 ? now - ts : null);
    return {
      provider: "gemini_live",
      transport_state: this.state,
      voice_session_id: this.voiceSessionId,
      bridge_connected: Boolean(this.geminiWs && this.geminiWs.readyState === WebSocket.OPEN),
      gemini_ready: this.geminiReady,
      client_connected: this.clientWs.readyState === WebSocket.OPEN,
      mic_active: this.lastClientChunkAt > 0 && (now - this.lastClientChunkAt) < 3000,
      last_input_audio_ms_ago: age(this.lastClientChunkAt),
      last_gemini_event_ms_ago: age(this.lastGeminiEventAt),
      last_output_audio_ms_ago: age(this.lastBridgeAudioAt),
      audio_input: {
        chunks_from_client_total: this.chunksFromClient,
        chunks_forwarded_total: this.chunksForwarded,
        chunks_dropped_total: this.chunksDropped,
        bytes_from_client_total: this.bytesFromClient,
        bytes_forwarded_total: this.bytesForwarded,
        dropped_by_breaker: this.droppedBridgeChunks,
      },
      recovery: {
        pending: this.recoveryPending,
        verified_at: this.recoveryVerifiedAt > 0 ? this.recoveryVerifiedAt : null,
        reconnect_count: this.reconnectCount,
      },
      turns: this.turnCount,
      last_error: this.lastError,
    };
  }

  setCallbacks(callbacks: {
    onStateChange?: (state: VoiceTransportState) => void;
    onTranscription?: (role: "user" | "model", text: string) => void;
    onAudio?: (base64Audio: string) => void;
    onToolCall?: (name: string, args: any, respond: (result: any) => void) => void;
    onMemorySync?: (memories: any[]) => void;
    onTurnComplete?: () => void;
  }): void {
    this.onStateChange = callbacks.onStateChange;
    this.onTranscription = callbacks.onTranscription;
    this.onAudio = callbacks.onAudio;
    this.onToolCall = callbacks.onToolCall;
    this.onMemorySync = callbacks.onMemorySync;
    this.onTurnComplete = callbacks.onTurnComplete;
  }
}
