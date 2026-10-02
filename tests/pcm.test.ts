import { describe, it, expect } from "vitest";
import {
  float32ToInt16,
  int16ToFloat32,
  pcm16ToBase64,
  base64ToPcm16,
} from "../src/lib/pcm";

describe("PCM Conversion Utilities", () => {
  it("converts silence (0.0) float32 to 0 int16", () => {
    const input = new Float32Array([0, 0, 0, 0]);
    const pcm = float32ToInt16(input);
    expect(pcm).toEqual(new Int16Array([0, 0, 0, 0]));

    const back = int16ToFloat32(pcm);
    expect(back).toEqual(new Float32Array([0, 0, 0, 0]));
  });

  it("converts positive and negative extremes with asymmetric scale", () => {
    const input = new Float32Array([1.0, -1.0, 0.5, -0.5]);
    const pcm = float32ToInt16(input);
    expect(pcm[0]).toBe(32767); // 0x7FFF
    expect(pcm[1]).toBe(-32768); // 0x8000
    expect(pcm[2]).toBe(16384);
    expect(pcm[3]).toBe(-16384);
  });

  it("clamps values exceeding [-1, 1]", () => {
    const input = new Float32Array([1.5, -2.0]);
    const pcm = float32ToInt16(input);
    expect(pcm[0]).toBe(32767);
    expect(pcm[1]).toBe(-32768);
  });

  it("preserves PCM precision within ≤ 2 LSB roundtrip", () => {
    const input = new Float32Array(1024);
    for (let i = 0; i < input.length; i++) {
      input[i] = Math.sin((i / 1024) * 2 * Math.PI);
    }
    const pcm = float32ToInt16(input);
    const floatBack = int16ToFloat32(pcm);
    const pcmBack = float32ToInt16(floatBack);

    for (let i = 0; i < pcm.length; i++) {
      expect(Math.abs(pcm[i] - pcmBack[i])).toBeLessThanOrEqual(2);
    }
  });

  it("correctly encodes and decodes base64 without corruption", () => {
    const original = new Int16Array([0, 100, -100, 32767, -32768, 42, -999]);
    const b64 = pcm16ToBase64(original);
    expect(typeof b64).toBe("string");
    expect(b64.length).toBeGreaterThan(0);

    const decoded = base64ToPcm16(b64);
    expect(decoded.length).toBe(original.length);
    for (let i = 0; i < original.length; i++) {
      expect(decoded[i]).toBe(original[i]);
    }
  });

  it("handles empty buffers safely", () => {
    const emptyFloat = new Float32Array(0);
    const emptyPcm = float32ToInt16(emptyFloat);
    expect(emptyPcm.length).toBe(0);

    const b64 = pcm16ToBase64(emptyPcm);
    expect(b64).toBe("");

    const decoded = base64ToPcm16("");
    expect(decoded.length).toBe(0);
  });
});
