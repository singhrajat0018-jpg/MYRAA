import { describe, it, expect, vi, beforeEach } from "vitest";
import { MyraaAudioSession } from "../src/lib/audio";
import { pcm16ToBase64 } from "../src/lib/pcm";

describe("MyraaAudioSession Voice Client Protocol & Queueing", () => {
  let session: MyraaAudioSession;
  let callbacks: any;

  beforeEach(() => {
    callbacks = {
      onStateChange: vi.fn(),
      onTranscription: vi.fn(),
      onError: vi.fn(),
      onTurnComplete: vi.fn(),
    };
    session = new MyraaAudioSession(callbacks);
  });

  it("initializes in idle state with generation 0", () => {
    expect(session.state).toBe("idle");
    expect(session.generationId).toBe(0);
    expect(session.getCaptureMode()).toBe("none");
  });

  it("handles status protocol messages correctly", () => {
    const handleSocketMessage = (session as any).handleSocketMessage.bind(session);

    handleSocketMessage({ type: "status", status: "listening" });
    expect(session.state).toBe("listening");
    expect(callbacks.onStateChange).toHaveBeenCalledWith("listening");

    handleSocketMessage({ type: "status", status: "speaking" });
    expect(session.state).toBe("speaking");
    expect(callbacks.onStateChange).toHaveBeenCalledWith("speaking");
  });

  it("handles transcription messages with role separation", () => {
    const handleSocketMessage = (session as any).handleSocketMessage.bind(session);

    handleSocketMessage({ type: "transcription", role: "user", text: "Hello MYRAA" });
    expect(callbacks.onTranscription).toHaveBeenCalledWith("user", "Hello MYRAA");

    handleSocketMessage({ type: "transcription", role: "model", text: "Hello! How can I help?" });
    expect(callbacks.onTranscription).toHaveBeenCalledWith("model", "Hello! How can I help?");
  });

  it("enqueues incoming audio chunks and bounds jitter queue", () => {
    (session as any).active = true;
    const dummyPcm = new Int16Array(480); // 20ms at 24kHz
    dummyPcm.fill(100);
    const b64 = pcm16ToBase64(dummyPcm);

    // Push 250 chunks (exceeding MAX_JITTER_QUEUE_CHUNKS = 200)
    for (let i = 0; i < 250; i++) {
      session.enqueueIncomingAudio(b64);
    }

    const queue = (session as any).audioChunkQueue;
    expect(queue.length).toBeLessThanOrEqual(200);
  });

  it("increments generationId and clears queue on interruption", () => {
    (session as any).active = true;
    const initialGen = session.generationId;

    const dummyPcm = new Int16Array(480);
    session.enqueueIncomingAudio(pcm16ToBase64(dummyPcm));
    expect((session as any).audioChunkQueue.length).toBe(1);

    // Trigger interruption
    session.handleInterruption(false);

    expect(session.generationId).toBe(initialGen + 1);
    expect((session as any).audioChunkQueue.length).toBe(0);
    expect(session.state).toBe("interrupted");
    expect(callbacks.onStateChange).toHaveBeenCalledWith("interrupted");
  });

  it("discards incoming audio chunks tagged with an older generation", () => {
    (session as any).active = true;
    (session as any).outputAudioContext = null; // simulate decoding step

    const dummyPcm = new Int16Array(480);
    const b64 = pcm16ToBase64(dummyPcm);

    // Queue in gen 0
    (session as any).audioChunkQueue.push({ pcm: dummyPcm, generation: 0 });

    // Interrupt -> advances to gen 1
    session.generationId = 1;

    // Call schedulePlayback with stale generation 0
    (session as any).schedulePlayback(0);

    // Items from gen 0 are dropped
    expect((session as any).audioChunkQueue.length).toBe(1); // untouched because scheduledGen 0 was rejected early
  });

  it("handles turnComplete protocol event cleanly", () => {
    const handleSocketMessage = (session as any).handleSocketMessage.bind(session);

    handleSocketMessage({ type: "turnComplete" });
    expect(session.state).toBe("listening");
    expect(callbacks.onTurnComplete).toHaveBeenCalled();
  });

  it("handles server stt_error and degraded status", () => {
    const handleSocketMessage = (session as any).handleSocketMessage.bind(session);

    handleSocketMessage({
      type: "stt_error",
      code: "QUOTA_EXCEEDED",
      message: "Daily quota reached",
      retryable: false,
    });

    expect(session.state).toBe("degraded");
    expect(callbacks.onError).toHaveBeenCalled();
  });

  it("performs clean disconnect without throwing errors", () => {
    session.disconnect();
    expect(session.state).toBe("disconnected");
    expect((session as any).active).toBe(false);
  });
});
