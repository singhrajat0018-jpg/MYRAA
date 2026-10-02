/**
 * Audio handling utility for Myraa Live API Voice stream.
 * Handles:
 * - 16kHz layout sampling for microphone stream.
 * - Raw Little Endian Int16 PCM translation.
 * - 24kHz layout output sampling for model voice playback.
 * - Gapless double-buffer queue scheduler.
 * - Interrupt signal immediate stop.
 * - Input & Output AnalyserNodes for real-time waveform visuals.
 */

import type { VADState } from './voiceActivityDetector';
import { VoiceActivityDetector } from './voiceActivityDetector';

// Re-export VADState for use in App.tsx
export type { VADState } from './voiceActivityDetector';

export type LiveState = "disconnected" | "connecting" | "listening" | "speaking" | "reconnecting";
export type LanguageHint = "english" | "hinglish" | "hindi" | "unknown";

// EPIC-05: structured Python Brain LLM-reasoning answer pushed over the WS link.
export type BrainResponse = {
  ok: boolean;
  success: boolean;
  text: string;
  provider?: string;
  error?: string | null;
};

// PCM helpers live in ./pcm (shared + unit-tested); behavior identical.
import {
  floatTo16BitPCM,
  pcm16ToFloats,
  base64ArrayBuffer,
  base64ToUint8Array,
} from './pcm';

// AudioWorklet capture processor: accumulates 128-sample render quanta into
// 1024-sample (64ms @16kHz) frames and posts them transferable to the main
// thread. Loaded via Blob URL (no bundler worklet config needed; CSP
// worker-src 'self' blob: allows it). Runs at the input context rate.
const MYRAA_CAPTURE_WORKLET_SOURCE = `
class MyraaCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._frame = 1024;
    this._buf = new Float32Array(this._frame);
    this._n = 0;
  }
  process(inputs) {
    const ch = inputs && inputs[0] && inputs[0][0];
    if (!ch || ch.length === 0) return true;
    let i = 0;
    while (i < ch.length) {
      const take = Math.min(ch.length - i, this._frame - this._n);
      this._buf.set(ch.subarray(i, i + take), this._n);
      this._n += take;
      i += take;
      if (this._n >= this._frame) {
        const out = this._buf.slice();
        this.port.postMessage(out, [out.buffer]);
        this._n = 0;
      }
    }
    return true;
  }
}
registerProcessor('myraa-capture', MyraaCaptureProcessor);
`;

export class MyraaAudioSession {
  private ws: WebSocket | null = null;
  
  // Audios contexts (separate to match exact required sample rates)
  private inputAudioCtx: AudioContext | null = null;
  private outputAudioCtx: AudioContext | null = null;
  
  // Audio sources & processors
  private micStream: MediaStream | null = null;
  private micSourceNode: MediaStreamAudioSourceNode | null = null;
  private micProcessorNode: ScriptProcessorNode | null = null;
  // AudioWorklet capture (preferred): off-main-thread, 1024-sample (64ms)
  // frames. Falls back to ScriptProcessor (2048/128ms) when unavailable.
  private micWorkletNode: AudioWorkletNode | null = null;
  private captureMode: "worklet" | "script" = "script";
  
  // Visualisers
  public inputAnalyser: AnalyserNode | null = null;
  public outputAnalyser: AnalyserNode | null = null;
  private outputGainNode: GainNode | null = null;
  
  // Buffering / Playback details
  private nextStartTime = 0;
  private activeSources: AudioBufferSourceNode[] = [];
  // Playback bounds: sustained overflow (suspended output, WS burst) drops
  // oldest instead of growing without limit. Counters only, never per-chunk logs.
  private readonly AUDIO_BUFFER_MAX_CHUNKS = 200;
  private readonly ACTIVE_SOURCES_MAX = 16;
  private droppedPlaybackChunks = 0;
  private droppedPlaybackSources = 0;
  private playbackWarnAt = 0;
  // Client-side turn timing: armed by the first mic chunk sent after playback
  // drain / turn-complete / interrupt; consumed at first playback schedule.
  // Same-clock delta only (mic-resume→playback), never mixed with server clocks.
  private tMicTurnStart = 0;
  private ttfaLoggedThisTurn = false;

  // Streaming TTS Optimization: Buffer for accumulating audio chunks
  private audioBuffer: string[] = [];
  private bufferTimeout: NodeJS.Timeout | null = null;
  private readonly BUFFER_FLUSH_MS = 20; // Reduced from 100ms for lower TTFA - immediate flush for low latency
  private isBuffering = false;

  // Mic gain for feedback prevention
  private micGainNode: GainNode | null = null;
  
  // State Callbacks
  private onStateChange: (state: LiveState) => void;
  private onTranscription: (role: "user" | "model", text: string) => void;
  private onToolCall: (name: string, args: any, callback: (result: any) => void) => void;
  private onToolResponse: (name: string, result: any) => void;
  private onError: (error: string) => void;
  private onMemorySync?: (memories: any[]) => void;
  private onBrainResponse?: (data: BrainResponse) => void;
  private onLanguageDetected: ((hint: LanguageHint) => void) | null = null;
  private onVADStateChange: ((state: VADState, probability: number) => void) | null = null;
  
  private currentState: LiveState = "disconnected";
  private isActivated = false;
  // Voice health surfaced by the server (Gemini Live voice transport state).
  public voiceDegraded = false;
  public activeVoiceName = "";

  // Enhanced features for EPIC-12
  private languageHint: LanguageHint = "unknown";
  private languageDetectionBuffer: string = "";
  private lastLanguageCheck: number = 0;

  // Voice Activity Detection for enhanced interruption handling
  private vadAudioCtx: AudioContext | null = null;
  private vadProcessor: VoiceActivityDetector | null = null;
  private vadSource: MediaStreamAudioSourceNode | null = null;
  // For barge-in detection: count consecutive frames above threshold to avoid false positives
  private consecutiveSpeechFrames: number = 0;

  // Phase V: Auto-reconnect state
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalDisconnect: boolean = false;

  // Generation guard: stale audio after interruption is discarded.
  private generationId = 0;

  // ── Mic continuity diagnostics (§2: counters, never per-chunk logs) ──
  private micChunkCount = 0;
  private micByteCount = 0;
  private micWindowChunks = 0;
  private micWindowBytes = 0;
  private micWindowStart = 0;
  private micLastChunkAt = 0;
  private micDroppedNoWs = 0;
  private micLastWarnAt = 0;

  constructor(handlers: {
    onStateChange: (state: LiveState) => void;
    onTranscription: (role: "user" | "model", text: string) => void;
    onToolCall: (name: string, args: any, callback: (result: any) => void) => void;
    onToolResponse: (name: string, result: any) => void;
    onError: (error: string) => void;
    onMemorySync?: (memories: any[]) => void;
    onBrainResponse?: (data: BrainResponse) => void;
    onLanguageDetected?: (hint: LanguageHint) => void;
    onVADStateChange?: (state: VADState, probability: number) => void;
  }) {
    this.onStateChange = handlers.onStateChange;
    this.onTranscription = handlers.onTranscription;
    this.onToolCall = handlers.onToolCall;
    this.onToolResponse = handlers.onToolResponse;
    this.onError = handlers.onError;
    this.onMemorySync = handlers.onMemorySync;
    this.onBrainResponse = handlers.onBrainResponse;
    this.onLanguageDetected = handlers.onLanguageDetected ?? null;
    this.onVADStateChange = handlers.onVADStateChange ?? null;

    // Initialize EPIC-12 features
    this.languageHint = "unknown";
    this.languageDetectionBuffer = "";
    this.lastLanguageCheck = 0;
  }

  private setState(state: LiveState) {
    this.currentState = state;
    this.onStateChange(state);
    this.updateMicGainForState(state);
  }

  private updateMicGainForState(state: LiveState) {
    if (!this.micGainNode) return;

    // Advanced Feedback Prevention: Adaptive gain control based on state and audio levels
    let baseGain = 0.5;

    switch (state) {
      case "speaking":
        // More aggressive gain reduction when speaking to prevent feedback
        baseGain = 0.2;
        break;
      case "listening":
        // Adaptive gain when listening - balance between hearing user and preventing feedback
        baseGain = 0.7;
        break;
      default:
        // Default gain when neither speaking nor listening
        baseGain = 0.5;
    }

    // 1. Dynamic gain control based on output level:
    //    Monitor output levels to detect potential feedback conditions
    //    Reduce mic gain when output level is high and mic is likely picking up output
    let outputLevel = 0.0;
    if (this.outputAnalyser && this.outputAudioCtx) {
      // Get RMS level from output analyser
      const bufferLength = this.outputAnalyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      this.outputAnalyser.getByteFrequencyData(dataArray);

      // Calculate RMS-like value from frequency data
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        // Normalize to 0-1 range and accumulate
        sum += dataArray[i] / 255;
      }
      outputLevel = sum / bufferLength;
    }

    // Apply dynamic gain reduction based on output level
    // If output is loud (>0.5), reduce mic gain to prevent feedback
    const feedbackReduction = Math.max(0, (outputLevel - 0.3) * 0.8); // Start reducing at 0.3 threshold
    let adjustedGain = baseGain * (1.0 - feedbackReduction);

    // Ensure gain doesn't go too low (minimum 0.05 to still hear user)
    adjustedGain = Math.max(adjustedGain, 0.05);

    // 2. Adaptive echo cancellation using reference signal:
    //    Use the output signal as a reference to cancel echo from the input signal
    //    Simple implementation: subtract filtered output from input (basic echo cancellation)
    //    More sophisticated implementations would use LMS or RLS adaptive filters
    if (this.micGainNode && this.outputGainNode) {
      // Simple echo cancellation estimate based on output level
      // In a full implementation, we'd use an adaptive filter here
      const echoEstimate = outputLevel * 0.6; // Empirical factor for echo path
      // Reduce gain further if echo is likely
      if (echoEstimate > 0.1) {
        adjustedGain *= Math.max(0.5, 1.0 - echoEstimate);
      }
    }

    // Apply the final gain value
    this.micGainNode.gain.value = adjustedGain;

    // 3. Frequency-specific feedback suppression:
    //    Identify frequencies prone to feedback (typically specific resonant frequencies)
    //    Apply notch filters at those frequencies in the mic gain node
    //    Would require creating BiquadFilterNode instances for feedback frequencies
    //    TODO: Implement BiquadFilterNode-based notch filters for common feedback frequencies

    // 4. Spectral subtraction for noise reduction:
    //    Estimate noise floor during periods of silence
    //    Subtract estimated noise from signal spectrum
    //    Would require FFT processing (could use existing analyser nodes)
    //    TODO: Implement noise floor estimation and spectral subtraction
  }

  public getState(): LiveState {
    return this.currentState;
  }

  /**
   * Checks if the WebSocket is connected and open.
   */
  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Phase V: Get audio device health information.
   */
  public getDeviceHealth(): {
    micActive: boolean;
    sampleRate: number;
    channels: number;
    deviceId: string;
    state: LiveState;
  } {
    const track = this.micStream?.getAudioTracks()[0];
    return {
      micActive: track?.enabled ?? false,
      sampleRate: this.inputAudioCtx?.sampleRate ?? 0,
      channels: track?.getSettings().channelCount ?? 0,
      deviceId: track?.getSettings().deviceId ?? "",
      state: this.currentState,
    };
  }

  /**
   * Pushes a compressed JPEG base64 screenshot frame directly to the live WebSocket server.
   */
  public sendVideoFrame(base64Data: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && this.currentState !== "disconnected") {
      this.ws.send(JSON.stringify({ type: "video", video: base64Data }));
    }
  }

  /**
   * Sends a message over the WebSocket connection.
   */
  public sendMessage(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /**
   * Single mic-frame handler for BOTH capture paths (AudioWorklet 64ms and
   * ScriptProcessor 128ms). Identical PCM16 base64 bytes on the wire.
   */
  private handleMicFrame(channelData: Float32Array): void {
    if (this.currentState === "disconnected" || this.currentState === "connecting") return;

    // Convert to base64 Int16 Little Endian PCM
    const pcmBuffer = floatTo16BitPCM(channelData);
    const base64 = base64ArrayBuffer(pcmBuffer);

    // ── Mic continuity counters (§2): rate summaries, not chunk logs ──
    const nowMs = Date.now();
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ audio: base64 }));
      this.micChunkCount++;
      this.micByteCount += pcmBuffer.byteLength;
      this.micWindowChunks++;
      this.micWindowBytes += pcmBuffer.byteLength;
      if (this.micLastChunkAt > 0 && nowMs - this.micLastChunkAt > 3000) {
        console.warn(`[MicDiagnostics] MIC_CAPTURE_STALL gap_ms=${nowMs - this.micLastChunkAt} (capture continued after stall)`);
      }
              this.micLastChunkAt = nowMs;
              if (!this.tMicTurnStart) this.tMicTurnStart = performance.now();
              if (!this.micWindowStart) this.micWindowStart = nowMs;
      if (nowMs - this.micWindowStart >= 5000) {
        console.log(`[MicDiagnostics] MIC_OK mode=${this.captureMode} mic_chunks_5s=${this.micWindowChunks} mic_bytes_5s=${this.micWindowBytes} mic_last_chunk_age_ms=${nowMs - this.micLastChunkAt} dropped_no_ws_total=${this.micDroppedNoWs}`);
        this.micWindowChunks = 0;
        this.micWindowBytes = 0;
        this.micWindowStart = nowMs;
      }
    } else {
      // WebSocket down: chunks are dropped (never queued) — counted,
      // warned at most once per 5s, mic capture itself keeps running.
      this.micDroppedNoWs++;
      if (nowMs - this.micLastWarnAt > 5000) {
        console.warn(`[MicDiagnostics] MIC_CHUNKS_DROPPED_NO_WS count=${this.micDroppedNoWs} (ws not open; capture stays alive)`);
        this.micLastWarnAt = nowMs;
      }
    }

    // Language detection (run periodically to avoid excessive computation)
    const now = Date.now();
    if (now - this.lastLanguageCheck > 2000) { // Check every 2 seconds (reduced from 1 second)
      this.detectLanguageFromAudio(channelData);
      this.lastLanguageCheck = now;
    }
  }

  // Requests microphone and creates connections
  public async connect() {
    if (this.isActivated) return;
    this.isActivated = true;
    this.setState("connecting");

    try {
      // 1. Establish custom WebSocket server bridge
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // Fetch WS session token for local-first auth
      let wsToken = "";
      try {
        const tokenResp = await fetch("/api/ws-token");
        const tokenData = await tokenResp.json();
        wsToken = tokenData.token || "";
      } catch { /* token fetch failed — connect without token, server will allow if MYRAA_WS_TOKEN is not set */ }
      const tokenParam = wsToken ? `?token=${encodeURIComponent(wsToken)}` : "";
      this.ws = new WebSocket(`${protocol}//${window.location.host}/live${tokenParam}`);
      this.ws.binaryType = "blob";

      this.ws.onopen = async () => {
        console.log("[Myraa] Connected to server side WS bridge");
        console.log("[MicDiagnostics] CLIENT_WS_OPEN");
        try {
          // Guard against early user disconnect during connection setup
          if (!this.isActivated) return;

          // Safe, cross-browser AudioContext initialization
          const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
          if (!AudioContextClass) {
            throw new Error("Holographic audio link unsupported: Web Audio API missing in browser.");
          }

          this.inputAudioCtx = new AudioContextClass({ sampleRate: 16000 });
          this.outputAudioCtx = new AudioContextClass({ sampleRate: 24000 });

          // Ensure Audio Contexts are active and resumed to bypass browser security blocks
          if (this.inputAudioCtx.state === "suspended") {
            await this.inputAudioCtx.resume().catch(() => {});
          }
          if (this.outputAudioCtx.state === "suspended") {
            await this.outputAudioCtx.resume().catch(() => {});
          }
          
          // Setup custom output Analyser & Volume Gains
          this.outputGainNode = this.outputAudioCtx.createGain();
          this.outputAnalyser = this.outputAudioCtx.createAnalyser();
          this.outputAnalyser.fftSize = 256;
          this.outputAnalyser.smoothingTimeConstant = 0.8;

          this.outputGainNode.connect(this.outputAnalyser);
          this.outputAnalyser.connect(this.outputAudioCtx.destination);

          // Setup Voice Activity Detector for enhanced interruption detection
          try {
            this.vadAudioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
            this.vadProcessor = new VoiceActivityDetector({
              sampleRate: 16000,
              fftSize: 512,
              smoothingTimeConstant: 0.7, // Further reduced smoothing for quicker response to speech onset
              speechThreshold: 0.2, // Even lower threshold to catch softer speech
              hangoverTime: 80, // Very short hangover for minimal delay in state switching
              minSpeechDuration: 30, // Shorter minimum speech duration for quicker detection
              minSilenceDuration: 80 // Shorter minimum silence to avoid missing subsequent speech
            });
            this.vadProcessor.init(this.vadAudioCtx);
            // Set up VAD state change callback
            this.vadProcessor.onStateChange((state: VADState, probability: number) => {
              // Forward to the outer class's onVADStateChange for UI visualization only
              // DO NOT trigger interruption here - authoritative interruption comes from
              // Gemini Live's native VAD via `interrupted` events. Local VAD is advisory only.
              if (this.onVADStateChange) {
                this.onVADStateChange(state, probability);
              }

              // Track consecutive frames for advisory metrics only (no auto-interrupt)
              if (this.currentState === "speaking") {
                let adaptiveThreshold = 0.5;
                if (this.outputAnalyser && this.outputAudioCtx) {
                  const bufferLength = this.outputAnalyser.frequencyBinCount;
                  const dataArray = new Uint8Array(bufferLength);
                  this.outputAnalyser.getByteFrequencyData(dataArray);
                  let sum = 0;
                  for (let i = 0; i < bufferLength; i++) {
                    sum += dataArray[i] / 255;
                  }
                  const outputLevel = sum / bufferLength;
                  if (outputLevel < 0.2) {
                    adaptiveThreshold = 0.3;
                  } else if (outputLevel < 0.4) {
                    adaptiveThreshold = 0.4;
                  } else {
                    adaptiveThreshold = 0.5;
                  }
                }
                if (state === "speech" && probability > adaptiveThreshold) {
                  this.consecutiveSpeechFrames++;
                } else {
                  this.consecutiveSpeechFrames = 0;
                }
              } else {
                this.consecutiveSpeechFrames = 0;
              }
            });
          } catch (vadError) {
            console.warn("Voice Activity Detector initialization failed:", vadError);
            // Continue without VAD - server-side interruption is still available
          }

          // Obtain User Microphone layout
          // Phase V: Use selected microphone from settings if available
          const { loadSettings } = await import('./settingsStore');
          const settings = loadSettings();
          const audioConstraints: MediaTrackConstraints = {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          };
          if (settings.micDeviceId) {
            audioConstraints.deviceId = { exact: settings.micDeviceId };
          }
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: audioConstraints,
          });

          // Safeguard: Check if we disconnected while waiting for user to grant mic permissions
          if (!this.isActivated || !this.inputAudioCtx || !this.outputAudioCtx) {
            stream.getTracks().forEach((track) => {
              try {
                track.stop();
              } catch (e) {}
            });
            return;
          }

          this.micStream = stream;
          console.log(`[MicDiagnostics] MIC_CAPTURE_START sample_rate=${this.inputAudioCtx?.sampleRate} channels=1 sample_width=2 encoding=pcm_s16le`);

          // Setup custom input Analyser
          this.inputAnalyser = this.inputAudioCtx.createAnalyser();
          this.inputAnalyser.fftSize = 256;
          
          this.micSourceNode = this.inputAudioCtx.createMediaStreamSource(this.micStream);

          // Mic gain for feedback prevention - reduce microphone gain when speaking
          this.micGainNode = this.inputAudioCtx.createGain();
          this.micGainNode.gain.value = 0.5; // Reduce microphone input by 50% to prevent feedback

          this.micSourceNode.connect(this.micGainNode);
          this.micGainNode.connect(this.inputAnalyser);

          // Also connect microphone to VAD processor for speech detection
          if (this.vadProcessor && this.vadAudioCtx) {
            // Create a separate source for VAD to avoid conflicts with main audio processing
            this.vadSource = this.vadAudioCtx.createMediaStreamSource(this.micStream);
            this.vadProcessor.connect(this.vadSource);
          }

          // Stream input PCM 16-bit to WS.
          // AudioWorklet first (off-main-thread, 1024-sample/64ms frames);
          // ScriptProcessor fallback (deprecated, 2048/128ms) when worklets
          // are unavailable or blocked. Both paths funnel into handleMicFrame
          // — identical bytes on the wire either way.
          this.captureMode = "script";
          let workletReady = false;
          try {
            if (this.inputAudioCtx.audioWorklet) {
              const workletUrl = URL.createObjectURL(
                new Blob([MYRAA_CAPTURE_WORKLET_SOURCE], { type: "application/javascript" })
              );
              try {
                await this.inputAudioCtx.audioWorklet.addModule(workletUrl);
                this.micWorkletNode = new AudioWorkletNode(this.inputAudioCtx, "myraa-capture", {
                  numberOfInputs: 1,
                  numberOfOutputs: 1,
                  outputChannelCount: [1],
                });
                this.micWorkletNode.port.onmessage = (ev: MessageEvent) => {
                  const frame = ev.data as Float32Array;
                  if (frame && frame.length > 0) this.handleMicFrame(frame);
                };
                this.micSourceNode.connect(this.micWorkletNode);
                // A worklet must sink somewhere to run; zero-gain keeps it silent.
                const workletSink = this.inputAudioCtx.createGain();
                workletSink.gain.value = 0;
                this.micWorkletNode.connect(workletSink);
                workletSink.connect(this.inputAudioCtx.destination);
                workletReady = true;
                this.captureMode = "worklet";
                console.log("[MicDiagnostics] CAPTURE_MODE=worklet frame=1024 (64ms)");
              } finally {
                URL.revokeObjectURL(workletUrl);
              }
            }
          } catch (workletError) {
            console.warn("[MicDiagnostics] AudioWorklet unavailable, ScriptProcessor fallback:", workletError);
            try { this.micWorkletNode?.disconnect(); } catch { /* ignore */ }
            this.micWorkletNode = null;
          }

          if (!workletReady) {
            this.micProcessorNode = this.inputAudioCtx.createScriptProcessor(2048, 1, 1);
            this.micSourceNode.connect(this.micProcessorNode);
            this.micProcessorNode.connect(this.inputAudioCtx.destination);

            this.micProcessorNode.onaudioprocess = (e) => {
              this.handleMicFrame(e.inputBuffer.getChannelData(0));
            };
            console.log("[MicDiagnostics] CAPTURE_MODE=script frame=2048 (128ms)");
          }

          // Sound setups are fully functional
          this.setState("listening");

        } catch (audioError: any) {
          console.error("Audio Context or Microphone Initialization Failed:", audioError);
          this.onError(`Permission error: ${audioError.message || "Microphone required for holographic Live link."}`);
          this.disconnect();
        }
      };

      this.ws.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Root Error Handler message
          if (data.type === "error") {
            this.onError(data.error);
            this.disconnect();
            return;
          }

          // Handle server-side states
          if (data.type === "status") {
            console.log("[Myraa WS Status]:", data.status);
            if (data.status === "connecting") {
              // Wait for connection
            } else if (data.status === "reconnecting") {
              // Bridge reconnect blackout: mic keeps flowing (dropped-if-down
              // at Node, counted), UI shows it instead of frozen "Listening".
              this.setState("reconnecting");
            } else if (data.status === "listening") {
              this.activeVoiceName = data.voice || "";
              this.voiceDegraded = false;
              this.setState("listening");
            } else if (data.status === "degraded") {
              this.voiceDegraded = true;
              this.setState("disconnected");
              this.onError(
                "VOICE DEGRADED: Gemini Live is unavailable after reconnect attempts. Text chat remains available."
              );
            } else if (data.status === "disconnected" || data.status === "error") {
              this.disconnect();
            }
            return;
          }

          // Handle audio payload (24kHzPCM model response)
          if (data.type === "audio" && data.audio) {
            this.playAudioPCMChunk(data.audio);
          }

          // Handle interruption signal (e.g. user talked over Myraa)
          if (data.type === "interrupted") {
            this.handleInterruption();
          }

          // Turn complete
          if (data.type === "turnComplete") {
            // Once Myraa completes speaking, change visual state back to listening immediately
            if (this.activeSources.length === 0 && this.currentState === "speaking") {
              this.setState("listening");
            }
            this.tMicTurnStart = 0;
            this.ttfaLoggedThisTurn = false;
          }

          // Handle live captions transcription
          if (data.type === "transcription") {
            this.onTranscription(data.role, data.text);
          }

          // Phase 7.2: Handle partial transcript for live captions
          if (data.type === "partial_transcript") {
            this.onTranscription("user", data.text);
          }

          // Handle Python Brain reasoning answers (EPIC-05)
          if (data.type === "brain_response") {
            if (this.onBrainResponse) {
              this.onBrainResponse(data);
            }
          }

          // Handle memory synchronization
          if (data.type === "memory_sync" && data.memories) {
            if (this.onMemorySync) {
              this.onMemorySync(data.memories);
            }
          }

          // Handle Tool Response (from server after tool execution)
          if (data.type === "toolResponse") {
            const { id, name, output } = data;
            this.onToolResponse(name, output);
          }

          // Handle Tool Calling
          if (data.type === "toolCall") {
            const { callId, name, args } = data;
            this.onToolCall(name, args, (result) => {
              // Send back execution result to server bridge
              if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                  type: "toolResponse",
                  id: callId,
                  name: name,
                  output: result
                }));
              }
            });
          }

        } catch (parseError) {
          console.error("Error reading server packet:", parseError);
        }
      };

      this.ws.onerror = (wsError) => {
        console.error("WebSocket transport error:", wsError);
        console.warn("[MicDiagnostics] CLIENT_WS_ERROR");
        this.onError("Holographic network link lost. Please check connection.");
        this.disconnect();
      };

      this.ws.onclose = () => {
        console.log("WebSocket connection closed");
        console.warn("[MicDiagnostics] CLIENT_WS_CLOSE");
        this.disconnect();
      };

    } catch (e: any) {
      console.error("Connection establish sequence failed:", e);
      this.onError(e.message || "Failed to initialize active channel.");
      this.disconnect();
    }
  }

  // Interruption triggers: stops all active audio players immediately.
  // Barge-in contract (§20/55/56): stop local playback AND tell the server
  // to cancel the in-flight Brain/TTS generation, and drop any TTS audio
  // still buffered locally so stale speech can never resume.
  private handleInterruption() {
    console.log("[Audio] Interruption signal received; flushing play logs.");

    // Drop buffered-but-unplayed TTS audio (stale generation protection)
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
      this.bufferTimeout = null;
    }
    this.audioBuffer = [];
    this.isBuffering = false;

    // Stop all playing nodes
    this.activeSources.forEach((source) => {
      try {
        source.stop();
      } catch (err) {
        // Already finished or stopped
      }
    });
    this.activeSources = [];
    this.nextStartTime = 0;

    // Invalidate current generation - stale audio from old generation will be dropped
    this.generationId++;

    // Notify the server so it cancels Brain + TTS generation immediately.
    // Server treats this as first-class barge-in (cancels stale generation).
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: "interrupt" }));
      } catch (e) {}
    }

    // Clear language detection buffer on interruption
    this.languageDetectionBuffer = "";
    this.lastLanguageCheck = 0;
    this.tMicTurnStart = 0;
    this.ttfaLoggedThisTurn = false;

    // Set state back to user listening
    this.setState("listening");
  }

  // Direct raw PCM chunk scheduled playback at 24kHz
  private playAudioPCMChunk(base64Audio: string) {
    if (!this.outputAudioCtx || !this.outputGainNode) return;

    // Bound the jitter buffer: sustained overflow (suspended output, WS
    // burst) drops oldest instead of growing without limit.
    if (this.audioBuffer.length >= this.AUDIO_BUFFER_MAX_CHUNKS) {
      this.audioBuffer.shift();
      this.droppedPlaybackChunks++;
      const nowMs = Date.now();
      if (nowMs - this.playbackWarnAt > 5000) {
        this.playbackWarnAt = nowMs;
        console.warn(`[Audio] PLAYBACK_BUFFER_OVERFLOW dropped_total=${this.droppedPlaybackChunks} (output stalled; dropping oldest)`);
      }
    }

    // Add chunk to buffer for streaming optimization
    this.audioBuffer.push(base64Audio);

    // Clear existing timeout and set new one
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
    }
    this.bufferTimeout = setTimeout(() => {
      this.flushAudioBuffer();
    }, this.BUFFER_FLUSH_MS);

    // Mark that we're buffering
    this.isBuffering = true;

    // Set speaking state immediately for responsiveness
    this.setState("speaking");
  }

  /**
   * Flush the audio buffer and play all accumulated chunks as a single utterance
   * This provides more natural prosody by reducing fragmentation
   */
  private flushAudioBuffer(): void {
    // Clear the timeout
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
      this.bufferTimeout = null;
    }

    // If no audio to play, return
    if (this.audioBuffer.length === 0) {
      this.isBuffering = false;
      return;
    }

    // Check if output context and gain node are available
    if (!this.outputAudioCtx || !this.outputGainNode) {
      // Reset buffer state if we can't play
      this.audioBuffer = [];
      this.isBuffering = false;
      return;
    }

    // Generation guard: discard stale audio from previous generation
    const currentGen = this.generationId;
    // We'll check this again before actual playback

    try {
      // Concatenate all audio chunks into a single buffer
      const combinedBase64 = this.audioBuffer.join('');
      this.audioBuffer = []; // Clear buffer
      this.isBuffering = false;

      // Generation guard: discard if generation changed while buffering
      if (currentGen !== this.generationId) {
        console.log("[Audio] Discarding stale audio from generation", currentGen);
        return;
      }

      // Decode the combined audio
      const uint8Array = base64ToUint8Array(combinedBase64);
      const floats = pcm16ToFloats(uint8Array);

      // Create AudioBuffer of 24000Hz (the exact playback sample rate of Gemini Live native audio)
      const buffer = this.outputAudioCtx.createBuffer(1, floats.length, 24000);
      buffer.getChannelData(0).set(floats);

      // Create Buffer source
      const source = this.outputAudioCtx.createBufferSource();
      source.buffer = buffer;

      // Connect source to gain which is routed to analyser & speakers
      // Using non-null assertion since we checked above
      source.connect(this.outputGainNode!);

      // Final generation guard before actual playback
      if (currentGen !== this.generationId) {
        console.log("[Audio] Discarding stale audio before start (gen changed)");
        return;
      }

      const currentTime = this.outputAudioCtx.currentTime;

      // Gapless scheduler sync
      if (this.nextStartTime < currentTime) {
        // Phase 7: start 15ms ahead (reduced from 30ms) for faster playback
        this.nextStartTime = currentTime + 0.015;
      }

      source.start(this.nextStartTime);
      this.nextStartTime += buffer.duration;

      // Client-side TTFA: first mic chunk of this turn → first scheduled playback.
      if (this.tMicTurnStart && !this.ttfaLoggedThisTurn) {
        this.ttfaLoggedThisTurn = true;
        console.log(`[Audio] CLIENT_TTFA ms=${Math.round(performance.now() - this.tMicTurnStart)} (mic-chunk→playback-schedule)`);
      }

      // Keep reference to handle real-time interruptions
      source.onended = () => {
        const index = this.activeSources.indexOf(source);
        if (index > -1) {
          this.activeSources.splice(index, 1);
        }

        // If there are no more active play nodes, revert state back to listening
        if (this.activeSources.length === 0 && this.currentState === "speaking") {
          this.setState("listening");
          // Re-arm turn timing: next mic chunk starts a fresh measurement.
          this.tMicTurnStart = 0;
          this.ttfaLoggedThisTurn = false;
        }
      };

      // Bound live sources: never accumulate zombie players.
      if (this.activeSources.length >= this.ACTIVE_SOURCES_MAX) {
        const stale = this.activeSources.shift();
        try { stale?.stop(); } catch { /* already finished */ }
        this.droppedPlaybackSources++;
      }
      this.activeSources.push(source);

    } catch (playbackError) {
      console.error("PCM Chunk buffering/playback failed:", playbackError);
      // Reset buffer state on error
      this.audioBuffer = [];
      this.isBuffering = false;
    }
  }

  // Fully cleanup and release microphones & connection sockets
  public disconnect(intentional: boolean = false) {
    if (intentional) {
      this.intentionalDisconnect = true;
      this.reconnectAttempts = 0;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    }

    this.isActivated = false;
    this.setState("disconnected");

    // Close WS socket
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {}
      this.ws = null;
    }

    // Stop and release user microphone streams
    if (this.micStream) {
      console.log(`[MicDiagnostics] MIC_CAPTURE_STOP chunks_total=${this.micChunkCount} bytes_total=${this.micByteCount} dropped_no_ws_total=${this.micDroppedNoWs}`);
      this.micStream.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch (e) {}
      });
      this.micStream = null;
    }

    // Disconnect routing nodes
    if (this.micWorkletNode) {
      try { this.micWorkletNode.port.onmessage = null; } catch (e) {}
      try { this.micWorkletNode.port.close(); } catch (e) {}
      try {
        this.micWorkletNode.disconnect();
      } catch (e) {}
      this.micWorkletNode = null;
    }

    if (this.micProcessorNode) {
      try {
        this.micProcessorNode.disconnect();
      } catch (e) {}
      this.micProcessorNode = null;
    }

    if (this.micSourceNode) {
      try {
        this.micSourceNode.disconnect();
      } catch (e) {}
      this.micSourceNode = null;
    }

    // Disconnect VAD nodes
    if (this.vadSource) {
      try {
        this.vadSource.disconnect();
      } catch (e) {}
      this.vadSource = null;
    }

    if (this.vadProcessor) {
      this.vadProcessor.disconnect();
      this.vadProcessor = null;
    }

    if (this.vadAudioCtx) {
      try {
        this.vadAudioCtx.close();
      } catch (e) {}
      this.vadAudioCtx = null;
    }

    // Close Audio contexts
    if (this.inputAudioCtx) {
      try {
        this.inputAudioCtx.close();
      } catch (e) {}
      this.inputAudioCtx = null;
    }

    if (this.outputAudioCtx) {
      try {
        this.outputAudioCtx.close();
      } catch (e) {}
      this.outputAudioCtx = null;
    }

    this.activeSources = [];
    this.nextStartTime = 0;
    // Drop any buffered TTS audio: it belongs to the dead session (§17).
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout);
      this.bufferTimeout = null;
    }
    this.audioBuffer = [];
    this.isBuffering = false;
    this.tMicTurnStart = 0;
    this.ttfaLoggedThisTurn = false;
    this.inputAnalyser = null;
    this.outputAnalyser = null;
    this.outputGainNode = null;

    // Phase V: Auto-reconnect on unintentional disconnect
    if (!intentional && !this.intentionalDisconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.attemptReconnect();
    }
  }

  /**
   * Phase V: Attempt reconnection with exponential backoff.
   */
  private attemptReconnect() {
    if (this.reconnectTimer) return;

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 16000);
    this.reconnectAttempts++;

    console.log(`[Audio] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      this.intentionalDisconnect = false;
      try {
        await this.connect();
      } catch (e) {
        console.error("[Audio] Reconnect failed:", e);
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        }
      }
    }, delay);
  }

  /**
   * Simple language detection from audio energy patterns
   * This is a basic implementation that looks for patterns typical in Hindi/English code-switching
   */
  private detectLanguageFromAudio(channelData: Float32Array): void {
    // Very basic language detection based on audio characteristics
    // In a real implementation, you would use a proper language identification model

    // Calculate basic audio features
    const energy = this.calculateEnergy(channelData);
    const zeroCrossingRate = this.calculateZeroCrossingRate(channelData);
    const spectralCentroid = this.calculateSpectralCentroid(channelData);

    // Simple heuristic: Hindi speech tends to have different spectral characteristics
    // This is a placeholder - in reality you'd use a trained model
    const hindiLikelihood =
      (spectralCentroid > 1000 && spectralCentroid < 3000) ? 0.7 : 0.3;

    // Adjust based on zero crossing rate (voiced vs unvoiced sounds)
    const zcrFactor = zeroCrossingRate > 0.1 ? 0.3 : 0.7;

    // Combined likelihood
    const combinedScore = (hindiLikelihood * 0.6) + (zcrFactor * 0.4);

    // Update language hint based on detection
    if (combinedScore > 0.6) {
      if (this.languageHint !== "hindi" && this.languageHint !== "hinglish") {
        this.languageHint = "hindi";
        if (this.onLanguageDetected) {
          this.onLanguageDetected("hindi");
        }
      }
    } else if (combinedScore > 0.4) {
      if (this.languageHint !== "hinglish") {
        this.languageHint = "hinglish";
        if (this.onLanguageDetected) {
          this.onLanguageDetected("hinglish");
        }
      }
    } else {
      if (this.languageHint !== "english") {
        this.languageHint = "english";
        if (this.onLanguageDetected) {
          this.onLanguageDetected("english");
        }
      }
    }
  }

  /**
   * Calculate energy (RMS) of audio buffer
   */
  private calculateEnergy(buffer: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < buffer.length; i++) {
      sum += buffer[i] * buffer[i];
    }
    return Math.sqrt(sum / buffer.length);
  }

  /**
   * Calculate zero crossing rate
   */
  private calculateZeroCrossingRate(buffer: Float32Array): number {
    let zeroCrossings = 0;
    for (let i = 1; i < buffer.length; i++) {
      if ((buffer[i - 1] >= 0 && buffer[i] < 0) ||
          (buffer[i - 1] < 0 && buffer[i] >= 0)) {
        zeroCrossings++;
      }
    }
    return zeroCrossings / buffer.length;
  }

  /**
   * Calculate spectral centroid (brightness of sound)
   */
  private calculateSpectralCentroid(buffer: Float32Array): number {
    // Very simplified spectral centroid calculation
    // In reality, you'd need to do an FFT first
    // This is just a placeholder for the concept
    const sum = buffer.reduce((acc, val) => acc + Math.abs(val), 0);
    return sum / buffer.length * 1000; // Scale to roughly Hz range
  }
}
