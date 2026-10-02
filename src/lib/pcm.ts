/**
 * MYRAA PCM & Audio Conversion Utilities
 *
 * Provides bit-exact Float32 <-> Int16 conversions, base64 encoding/decoding,
 * and AudioBuffer creation. Preserves the 0x7FFF / 0x8000 asymmetric scale
 * required for standard PCM16 LE audio transmission.
 */

/**
 * Convert Float32Array [-1.0, 1.0] to signed 16-bit PCM Int16Array [-32768, 32767].
 */
export function float32ToInt16(input: Float32Array): Int16Array {
  const len = input.length;
  const pcm = new Int16Array(len);
  for (let i = 0; i < len; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    pcm[i] = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff);
  }
  return pcm;
}

/**
 * Convert signed 16-bit PCM Int16Array to Float32Array [-1.0, 1.0].
 */
export function int16ToFloat32(input: Int16Array): Float32Array {
  const len = input.length;
  const out = new Float32Array(len);
  for (let i = 0; i < len; i++) {
    const s = input[i];
    out[i] = s < 0 ? s / 0x8000 : s / 0x7fff;
  }
  return out;
}

/**
 * Safe base64 encoding of Int16Array byte buffer (chunked to avoid call stack limits).
 */
export function pcm16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  const CHUNK_SIZE = 4096;
  const chunks: string[] = [];
  for (let i = 0; i < bytes.length; i += CHUNK_SIZE) {
    const slice = bytes.subarray(i, i + CHUNK_SIZE);
    chunks.push(String.fromCharCode(...slice));
  }
  return btoa(chunks.join(""));
}

/**
 * Safe base64 decoding to Int16Array.
 */
export function base64ToPcm16(base64: string): Int16Array {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(len / 2));
}

/**
 * Creates an AudioBuffer from Int16 PCM data.
 */
export function pcm16ToAudioBuffer(
  pcm: Int16Array,
  ctx: AudioContext,
  sampleRate = 24000
): AudioBuffer {
  const float32 = int16ToFloat32(pcm);
  const buffer = ctx.createBuffer(1, float32.length, sampleRate);
  buffer.getChannelData(0).set(float32);
  return buffer;
}
