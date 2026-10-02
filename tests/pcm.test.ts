/**
 * PCM contract tests (voice capture path).
 *
 * src/lib/pcm.ts is shared by BOTH capture paths (AudioWorklet 64ms frames
 * and ScriptProcessor 128ms frames) and the playback decoder. These tests
 * lock the wire contract: Float32 mono [-1,1] <-> Int16LE PCM <-> base64.
 */
import { describe, it, expect, beforeAll } from "vitest";
import {
  floatTo16BitPCM,
  pcm16ToFloats,
  base64ArrayBuffer,
  base64ToUint8Array,
} from "../src/lib/pcm";

beforeAll(() => {
  // pcm.ts uses window.btoa/atob like the browser code; provide them in node.
  (globalThis as any).window = {
    btoa: (bin: string) => Buffer.from(bin, "binary").toString("base64"),
    atob: (b64: string) => Buffer.from(b64, "base64").toString("binary"),
  };
});

describe("floatTo16BitPCM", () => {
  it("encodes silence as zero bytes", () => {
    const out = new Uint8Array(floatTo16BitPCM(new Float32Array([0, 0])));
    expect(Array.from(out)).toEqual([0, 0, 0, 0]);
  });

  it("is little-endian (+1.0 -> [0xFF, 0x7F], -1.0 -> [0x00, 0x80])", () => {
    const out = new Uint8Array(floatTo16BitPCM(new Float32Array([1.0, -1.0])));
    expect(Array.from(out)).toEqual([0xff, 0x7f, 0x00, 0x80]);
  });

  it("clips above +1.0 to 0x7FFF and below -1.0 to -0x8000", () => {
    const view = new DataView(floatTo16BitPCM(new Float32Array([2.5, -9])));
    expect(view.getInt16(0, true)).toBe(0x7fff);
    expect(view.getInt16(2, true)).toBe(-0x8000);
  });

  it("produces 2 bytes per sample", () => {
    expect(floatTo16BitPCM(new Float32Array(1024)).byteLength).toBe(2048);
    expect(floatTo16BitPCM(new Float32Array(2048)).byteLength).toBe(4096);
  });
});

describe("pcm16ToFloats", () => {
  it("round-trips through floatTo16BitPCM within 2 LSB", () => {
    // NOTE: encode scales positives by 0x7FFF but decode divides by 32768
    // (pre-existing wire behavior, preserved verbatim) — worst-case error is
    // just under 2 LSB. The bound below locks that behavior, not 1 LSB.
    const src = new Float32Array([0, 0.5, -0.5, 0.9999, -0.9999, 0.123456]);
    const bytes = new Uint8Array(floatTo16BitPCM(src));
    const back = pcm16ToFloats(bytes);
    for (let i = 0; i < src.length; i++) {
      expect(Math.abs(back[i] - src[i])).toBeLessThan(2 / 32768 + 1e-9);
    }
  });
});

describe("base64 PCM framing", () => {
  it("round-trips a full 1024-sample worklet frame", () => {
    const frame = new Float32Array(1024);
    for (let i = 0; i < frame.length; i++) frame[i] = Math.sin(i / 10) * 0.8;
    const b64 = base64ArrayBuffer(floatTo16BitPCM(frame));
    // 2048 bytes -> ceil(2048/3)*4 base64 chars
    expect(b64.length).toBe(Math.ceil(2048 / 3) * 4);
    const back = pcm16ToFloats(base64ToUint8Array(b64));
    expect(back.length).toBe(1024);
    for (let i = 0; i < frame.length; i++) {
      expect(Math.abs(back[i] - frame[i])).toBeLessThan(2 / 32768 + 1e-9);
    }
  });

  it("round-trips a 2048-sample script-processor frame", () => {
    const frame = new Float32Array(2048).fill(0.25);
    const back = pcm16ToFloats(base64ToUint8Array(base64ArrayBuffer(floatTo16BitPCM(frame))));
    expect(back.length).toBe(2048);
    expect(Math.abs(back[0] - 0.25)).toBeLessThan(1 / 32768 + 1e-9);
  });
});
