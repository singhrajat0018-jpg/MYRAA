import { describe, it, expect, vi } from "vitest";
import { VoiceTransport, normalizeVoiceFingerprint, voiceFingerprint } from "../server_voice";
import { pcm16ToBase64 } from "../src/lib/pcm";

describe("Voice Transport Simulation & Protocol Verification", () => {
  it("normalizes and fingerprints user transcripts correctly", () => {
    const text1 = "Hello MYRAA, kya haal hai?";
    const text2 = "  hello   myraa,  kya haal hai?  ";
    expect(normalizeVoiceFingerprint(text1)).toBe(normalizeVoiceFingerprint(text2));

    const fp1 = voiceFingerprint("session-1", text1);
    const fp2 = voiceFingerprint("session-1", text2);
    expect(fp1).toBe(fp2);

    const fpDifferentSession = voiceFingerprint("session-2", text1);
    expect(fp1).not.toBe(fpDifferentSession);
  });

  it("TEST A: simulates 20 multi-turn conversation cycles cleanly", () => {
    const sentMessages: any[] = [];
    const mockClientWs: any = {
      readyState: 1, // OPEN
      send: (str: string) => {
        sentMessages.push(JSON.parse(str));
      },
    };

    const transport = new VoiceTransport(mockClientWs);
    const dummyAudioB64 = pcm16ToBase64(new Int16Array(480));

    // Simulate 20 conversational turns
    for (let turn = 1; turn <= 20; turn++) {
      // 1. User speaks
      (transport as any).handleGeminiMessage({
        type: "partial_transcript",
        role: "user",
        text: `User query ${turn}`,
      });

      // 2. Model outputs audio
      (transport as any).handleGeminiMessage({
        type: "audio",
        audio: dummyAudioB64,
      });

      // 3. Model transcript
      (transport as any).handleGeminiMessage({
        type: "partial_transcript",
        role: "model",
        text: `Model response for turn ${turn}`,
      });

      // 4. Turn complete
      (transport as any).handleGeminiMessage({
        type: "turnComplete",
      });

      expect(transport.getState()).toBe("listening");
    }

    // Verify sent messages include transcriptions, audio, and turnComplete
    const transcriptions = sentMessages.filter((m) => m.type === "transcription");
    const audioChunks = sentMessages.filter((m) => m.type === "audio");
    const completions = sentMessages.filter((m) => m.type === "turnComplete");

    expect(transcriptions.length).toBe(40); // 20 user + 20 model
    expect(audioChunks.length).toBe(20);
    expect(completions.length).toBe(20);
  });

  it("TEST B: simulates interruption (barge-in) and generation invalidation", () => {
    const sentMessages: any[] = [];
    const mockClientWs: any = {
      readyState: 1,
      send: (str: string) => sentMessages.push(JSON.parse(str)),
    };

    const transport = new VoiceTransport(mockClientWs);
    const dummyAudioB64 = pcm16ToBase64(new Int16Array(480));

    // Model starts speaking
    (transport as any).handleGeminiMessage({
      type: "audio",
      audio: dummyAudioB64,
    });
    expect(transport.getState()).toBe("speaking");

    const genBefore = (transport as any).generationId;

    // Interruption occurs (Gemini detects user speech)
    (transport as any).handleGeminiMessage({
      type: "interrupted",
    });

    const genAfter = (transport as any).generationId;
    expect(genAfter).toBe(genBefore + 1);
    expect(transport.getState()).toBe("interrupted");

    // Client received interrupted event
    const interruptEvents = sentMessages.filter((m) => m.type === "interrupted");
    expect(interruptEvents.length).toBe(1);
  });

  it("TEST C: handles reconnecting and reconnected_ready transitions", () => {
    const sentMessages: any[] = [];
    const mockClientWs: any = {
      readyState: 1,
      send: (str: string) => sentMessages.push(JSON.parse(str)),
    };

    const transport = new VoiceTransport(mockClientWs);

    // Connection failure event
    (transport as any).handleGeminiMessage({
      type: "connection_failed",
      reason: "Stream closed by peer",
    });
    expect(transport.getState()).toBe("reconnecting");

    // Reconnected event
    (transport as any).handleGeminiMessage({
      type: "reconnected",
      generation: 1,
    });
    expect(transport.getState()).toBe("listening");
  });

  it("TEST D: tracks bridge write counters and drops safely when closed", () => {
    const mockClientWs: any = { readyState: 1, send: () => {} };
    const transport = new VoiceTransport(mockClientWs);
    (transport as any).setState("listening");

    // geminiWs is null (bridge closed)
    transport.handleAudioChunk("dummy-audio-base64");
    const stats = transport.getBridgeStats();
    expect(stats.ready).toBe(false);
    expect(stats.dropped).toBeGreaterThan(0);
  });

  it("TEST E: Desktop Agent offline produces honest degraded error without crashing", async () => {
    const sentMessages: any[] = [];
    const mockClientWs: any = {
      readyState: 1,
      send: (str: string) => sentMessages.push(JSON.parse(str)),
    };

    // Point to unreachable port
    process.env.DESKTOP_AGENT_URL = "http://127.0.0.1:59999";
    const transport = new VoiceTransport(mockClientWs);

    await transport.start();

    // Transport should transition to error without crashing the process
    expect(["error", "degraded"]).toContain(transport.getState());
    const errors = sentMessages.filter((m) => m.type === "error");
    expect(errors.length).toBeGreaterThan(0);

    // Clean up
    delete process.env.DESKTOP_AGENT_URL;
  });
});
