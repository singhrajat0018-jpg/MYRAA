/**
 * Web Audio & Gemini Live client bridge for MYRAA.
 *
 * Implements a world-class conversational voice client:
 * - AudioWorklet-first 1024-sample (64ms @ 16kHz) continuous microphone capture
 *   with ScriptProcessorNode compatibility fallback.
 * - Streaming 24kHz Gemini native PCM playback with ~20ms bounded jitter buffer.
 * - True full-duplex conversational audio with continuous microphone streaming.
 * - Epoch/generation-based interruption protection (barge-in): immediately cancels
 *   playing sources, clears queued frames, and drops in-flight stale responses.
 * - Bounded memory queues (max 200 chunks, max 16 active sources).
 * - Full lifecycle management with clean teardown.
 */

import { float32ToInt16, pcm16ToBase64, base64ToPcm16, pcm16ToAudioBuffer } from "./pcm";

export type LiveState =
  | "idle"
  | "connecting"
  | "connected"
  | "listening"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "reconnecting"
  | "degraded"
  | "error"
  | "disconnected"
  | "closed";

export interface AudioSessionCallbacks {
  onStateChange?: (state: LiveState) => void;
  onTranscription?: (role: "user" | "model", text: string) => void;
  onError?: (err: Error) => void;
  onTurnComplete?: () => void;
}

// Inline AudioWorklet processor code for 1024-sample / 64ms frame capture
const WORKLET_PROCESSOR_CODE = `
class MyraaCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(1024);
    this.offset = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const channelData = input[0];
    let i = 0;
    while (i < channelData.length) {
      const remaining = 1024 - this.offset;
      const toCopy = Math.min(remaining, channelData.length - i);
      this.buffer.set(channelData.subarray(i, i + toCopy), this.offset);
      this.offset += toCopy;
      i += toCopy;
      if (this.offset === 1024) {
        const frame = new Float32Array(this.buffer);
        this.port.postMessage({ frame }, [frame.buffer]);
        this.offset = 0;
      }
    }
    return true;
  }
}
registerProcessor('myraa-capture', MyraaCaptureProcessor);
`;

const MAX_JITTER_QUEUE_CHUNKS = 200;
const MAX_ACTIVE_SOURCES = 16;
const JITTER_LOOKAHEAD_SECONDS = 0.02; // ~20ms lookahead
const OUTPUT_SAMPLE_RATE = 24000;

export class MyraaAudioSession {
  public state: LiveState = "idle";
  public inputAnalyser: AnalyserNode | null = null;
  public outputAnalyser: AnalyserNode | null = null;

  // Session identity & generation guard
  public generationId = 0;

  private ws: WebSocket | null = null;
  private inputAudioContext: AudioContext | null = null;
  private outputAudioContext: AudioContext | null = null;
  private outputGainNode: GainNode | null = null;

  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private scriptProcessorNode: ScriptProcessorNode | null = null;

  // Playback scheduler state
  private nextStartTime = 0;
  private activeSources: Set<AudioBufferSourceNode> = new Set();
  private audioChunkQueue: Array<{ pcm: Int16Array; generation: number }> = [];

  private callbacks: AudioSessionCallbacks = {};
  private active = false;
  private captureMode: "worklet" | "script" | "none" = "none";

  constructor(callbacks: AudioSessionCallbacks = {}) {
    this.callbacks = callbacks;
  }

  private setState(next: LiveState) {
    if (this.state === next) return;
    this.state = next;
    this.callbacks.onStateChange?.(next);
  }

  public getCaptureMode(): "worklet" | "script" | "none" {
    return this.captureMode;
  }

  public async connect(): Promise<void> {
    if (this.active) return;
    this.active = true;
    this.setState("connecting");

    try {
      // 1. Fetch WS token
      let token = "";
      try {
        const res = await fetch("/api/ws-token");
        if (res.ok) {
          const data = await res.json();
          token = data.token || "";
        }
      } catch (err) {
        console.warn("[Voice] Could not fetch WS token:", err);
      }

      // 2. Establish WebSocket
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/live?token=${encodeURIComponent(token)}`;

      this.ws = new WebSocket(wsUrl);
      this.ws.binaryType = "arraybuffer";

      this.ws.onopen = async () => {
        this.setState("connected");
        await this.initAudio();
      };

      this.ws.onmessage = (event) => {
        try {
          if (typeof event.data === "string") {
            const msg = JSON.parse(event.data);
            this.handleSocketMessage(msg);
          }
        } catch {
          // ignore malformed lines
        }
      };

      this.ws.onerror = (e) => {
        console.warn("[Voice] WebSocket error:", e);
        this.setState("error");
      };

      this.ws.onclose = () => {
        this.setState("disconnected");
        this.active = false;
      };
    } catch (err: any) {
      this.setState("error");
      this.callbacks.onError?.(err);
      this.active = false;
    }
  }

  private handleSocketMessage(msg: any): void {
    if (!msg || typeof msg !== "object") return;

    switch (msg.type) {
      case "status":
        if (msg.status) {
          this.setState(msg.status);
        }
        break;

      case "transcription":
        if (msg.text) {
          this.callbacks.onTranscription?.(msg.role || "user", msg.text);
        }
        break;

      case "audio":
        if (msg.audio) {
          this.enqueueIncomingAudio(msg.audio);
        }
        break;

      case "interrupted":
        this.handleInterruption(false);
        break;

      case "turnComplete":
        this.setState("listening");
        this.callbacks.onTurnComplete?.();
        break;

      case "stt_error":
      case "error":
        console.warn("[Voice] Server error:", msg.code, msg.message || msg.error);
        if (msg.retryable === false) {
          this.setState("degraded");
        }
        this.callbacks.onError?.(new Error(msg.message || msg.error || "Voice error"));
        break;

      default:
        break;
    }
  }

  private async initAudio(): Promise<void> {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) {
        console.warn("[Voice] Web Audio API is not supported in this browser.");
        this.setState("error");
        return;
      }

      // Input context for mic capture (16kHz standard for Gemini speech input)
      this.inputAudioContext = new AudioCtx({ sampleRate: 16000 });
      this.inputAnalyser = this.inputAudioContext.createAnalyser();
      this.inputAnalyser.fftSize = 128;

      // Output context for model audio playback
      this.outputAudioContext = new AudioCtx();
      this.outputAnalyser = this.outputAudioContext.createAnalyser();
      this.outputAnalyser.fftSize = 128;
      this.outputGainNode = this.outputAudioContext.createGain();
      this.outputGainNode.gain.setValueAtTime(1.0, this.outputAudioContext.currentTime);
      this.outputGainNode.connect(this.outputAnalyser);
      this.outputAnalyser.connect(this.outputAudioContext.destination);

      // Resume output context if suspended by browser autoplay policy
      if (this.outputAudioContext.state === "suspended") {
        await this.outputAudioContext.resume();
      }

      // Initialize microphone capture with platform AEC / NS / AGC
      if (navigator.mediaDevices?.getUserMedia) {
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        this.sourceNode = this.inputAudioContext.createMediaStreamSource(this.mediaStream);
        this.sourceNode.connect(this.inputAnalyser);

        // Attempt AudioWorklet first
        let workletLoaded = false;
        if (this.inputAudioContext.audioWorklet) {
          try {
            const blob = new Blob([WORKLET_PROCESSOR_CODE], { type: "application/javascript" });
            const blobUrl = URL.createObjectURL(blob);
            await this.inputAudioContext.audioWorklet.addModule(blobUrl);
            URL.revokeObjectURL(blobUrl);

            this.workletNode = new AudioWorkletNode(this.inputAudioContext, "myraa-capture");
            this.workletNode.port.onmessage = (e) => {
              if (e.data?.frame) {
                this.handleMicFrame(e.data.frame);
              }
            };

            this.sourceNode.connect(this.workletNode);
            // Connect to zero-gain sink to keep processing alive without feedback
            const sink = this.inputAudioContext.createGain();
            sink.gain.value = 0;
            this.workletNode.connect(sink);
            sink.connect(this.inputAudioContext.destination);

            this.captureMode = "worklet";
            workletLoaded = true;
            console.log("[Voice] AudioWorklet capture initialized (1024-frame / 64ms)");
          } catch (err: any) {
            console.warn("[Voice] AudioWorklet failed, falling back to ScriptProcessor:", err.message);
          }
        }

        // ScriptProcessor fallback if AudioWorklet was unavailable or failed
        if (!workletLoaded) {
          const processor = this.inputAudioContext.createScriptProcessor(1024, 1, 1);
          processor.onaudioprocess = (e) => {
            const input = e.inputBuffer.getChannelData(0);
            this.handleMicFrame(input);
          };

          this.sourceNode.connect(processor);
          processor.connect(this.inputAudioContext.destination);
          this.scriptProcessorNode = processor;
          this.captureMode = "script";
          console.log("[Voice] ScriptProcessor capture initialized (fallback)");
        }

        this.setState("listening");
      }
    } catch (err: any) {
      console.warn("[Voice] Microphone capture unavailable:", err.message);
      this.setState("degraded");
      this.callbacks.onError?.(err);
    }
  }

  /**
   * Process a float32 audio frame from the microphone and send PCM16 LE base64 to WebSocket.
   */
  public handleMicFrame(float32Data: Float32Array): void {
    if (!this.active || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    try {
      const pcm16 = float32ToInt16(float32Data);
      const base64Audio = pcm16ToBase64(pcm16);
      this.ws.send(JSON.stringify({ audio: base64Audio }));
    } catch (err: any) {
      console.warn("[Voice] Failed to encode/send mic frame:", err.message);
    }
  }

  /**
   * Enqueue incoming 24kHz PCM16 audio chunk from Gemini Live and schedule continuous playback.
   */
  public enqueueIncomingAudio(base64Audio: string): void {
    if (!this.active || !base64Audio) return;

    const currentGen = this.generationId;

    try {
      const pcm = base64ToPcm16(base64Audio);
      if (pcm.length === 0) return;

      // Jitter queue bounded insertion
      if (this.audioChunkQueue.length >= MAX_JITTER_QUEUE_CHUNKS) {
        this.audioChunkQueue.shift(); // drop oldest under heavy backlog
      }
      this.audioChunkQueue.push({ pcm, generation: currentGen });

      // Schedule playback
      this.schedulePlayback(currentGen);
    } catch (err: any) {
      console.warn("[Voice] Error decoding incoming audio chunk:", err.message);
    }
  }

  /**
   * Schedule queued audio buffers into the AudioContext timeline with jitter protection.
   */
  private schedulePlayback(scheduledGen: number): void {
    if (!this.outputAudioContext || !this.outputGainNode) return;
    if (scheduledGen !== this.generationId) return;

    // Drain queue items matching current generation
    while (this.audioChunkQueue.length > 0) {
      const item = this.audioChunkQueue.shift();
      if (!item || item.generation !== this.generationId) continue;

      const audioBuffer = pcm16ToAudioBuffer(item.pcm, this.outputAudioContext, OUTPUT_SAMPLE_RATE);

      // Determine schedule time: lookahead jitter buffer
      const now = this.outputAudioContext.currentTime;
      if (this.nextStartTime < now) {
        // Underflow or start of new utterance: schedule slightly ahead of now
        this.nextStartTime = now + JITTER_LOOKAHEAD_SECONDS;
      }

      // Create and configure source node
      const source = this.outputAudioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.outputGainNode);

      // Source tracking and bounding
      if (this.activeSources.size >= MAX_ACTIVE_SOURCES) {
        const oldest = this.activeSources.values().next().value;
        if (oldest) {
          try {
            oldest.stop(0);
            oldest.disconnect();
          } catch (_) {}
          this.activeSources.delete(oldest);
        }
      }

      this.activeSources.add(source);
      source.onended = () => {
        this.activeSources.delete(source);
        if (this.activeSources.size === 0 && this.state === "speaking") {
          // If no sources are playing and we were speaking, return to listening
          this.setState("listening");
        }
      };

      try {
        source.start(this.nextStartTime);
        this.nextStartTime += audioBuffer.duration;
        this.setState("speaking");
      } catch (err: any) {
        this.activeSources.delete(source);
        console.warn("[Voice] Failed to start buffer source:", err.message);
      }
    }
  }

  /**
   * Full-duplex barge-in / interruption handling.
   * Cancels all current and pending audio playback, increments generation, and cleans queues.
   */
  public handleInterruption(notifyServer = true): void {
    this.generationId++;
    const staleGen = this.generationId - 1;

    // 1. Immediately silence all active and scheduled audio sources
    for (const source of this.activeSources) {
      try {
        source.stop(0);
        source.disconnect();
      } catch (_) {}
    }
    this.activeSources.clear();

    // 2. Clear playback queues
    this.audioChunkQueue = [];
    this.nextStartTime = 0;

    // 3. Update state
    this.setState("interrupted");

    // 4. Send interrupt signal to server if user-initiated
    if (notifyServer && this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: "interrupt", generation: `G${staleGen}` }));
      } catch (_) {}
    }

    // 5. Quickly settle back to listening
    setTimeout(() => {
      if (this.state === "interrupted" && this.active) {
        this.setState("listening");
      }
    }, 80);
  }

  public interrupt(): void {
    this.handleInterruption(true);
  }

  public disconnect(): void {
    this.active = false;
    this.generationId++;

    // Stop active audio sources
    for (const source of this.activeSources) {
      try {
        source.stop(0);
        source.disconnect();
      } catch (_) {}
    }
    this.activeSources.clear();
    this.audioChunkQueue = [];

    // Stop media stream tracks
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }

    // Teardown audio nodes
    if (this.workletNode) {
      try {
        this.workletNode.disconnect();
      } catch (_) {}
      this.workletNode = null;
    }

    if (this.scriptProcessorNode) {
      try {
        this.scriptProcessorNode.disconnect();
      } catch (_) {}
      this.scriptProcessorNode = null;
    }

    if (this.sourceNode) {
      try {
        this.sourceNode.disconnect();
      } catch (_) {}
      this.sourceNode = null;
    }

    // Close AudioContexts
    if (this.inputAudioContext && this.inputAudioContext.state !== "closed") {
      this.inputAudioContext.close().catch(() => {});
      this.inputAudioContext = null;
    }

    if (this.outputAudioContext && this.outputAudioContext.state !== "closed") {
      this.outputAudioContext.close().catch(() => {});
      this.outputAudioContext = null;
    }

    // Close WebSocket
    if (this.ws) {
      try {
        this.ws.close();
      } catch (_) {}
      this.ws = null;
    }

    this.captureMode = "none";
    this.setState("disconnected");
  }
}
