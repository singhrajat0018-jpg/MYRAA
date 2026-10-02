// ============================================================================
// MYRAA Avatar Lip Sync Engine — Audio-Driven Mouth Animation
// ============================================================================

import type {
  LipSyncFrame,
  SpeakingState,
  AvatarConfig,
} from './contracts';
import { DEFAULT_AVATAR_CONFIG } from './contracts';

// ============================================================================
// Phoneme-to-Viseme Mapping
// ============================================================================

const PHONEME_VISEME_MAP: Record<string, number> = {
  // Open vowels
  'AA': 0.9, 'AE': 0.85, 'AH': 0.7, 'AO': 0.75, 'AW': 0.8, 'AY': 0.8,
  // Closed vowels
  'IY': 0.4, 'IH': 0.35, 'EY': 0.5, 'EH': 0.55, 'ER': 0.5,
  // Rounded
  'UH': 0.45, 'UW': 0.5, 'OW': 0.6, 'OY': 0.65,
  // Consonants (lips nearly closed)
  'B': 0.05, 'P': 0.05, 'M': 0.05,
  'F': 0.15, 'V': 0.15,
  'TH': 0.2, 'DH': 0.2,
  'S': 0.25, 'Z': 0.25, 'SH': 0.3, 'ZH': 0.3,
  'T': 0.2, 'D': 0.2, 'N': 0.2, 'L': 0.25, 'R': 0.3,
  'K': 0.15, 'G': 0.15, 'NG': 0.15, 'HH': 0.4,
  'W': 0.5, 'Y': 0.4, 'JH': 0.3, 'CH': 0.25,
};

// ============================================================================
// Volume-to-Openness Smoothing
// ============================================================================

interface SmoothingState {
  lastOpenness: number;
  lastVolume: number;
  velocity: number;
}

// ============================================================================
// LipSyncEngine
// ============================================================================

export class LipSyncEngine {
  private config: AvatarConfig;
  private enabled: boolean;
  private pendingFrames: LipSyncFrame[] = [];
  private smoothing: SmoothingState;
  private frameInterval: number;
  private lastFrameTime: number = 0;
  private smoothingFactor: number = 0.3;
  private maxFrameBuffer: number = 10;

  constructor(config: Partial<AvatarConfig> = {}) {
    this.config = { ...DEFAULT_AVATAR_CONFIG, ...config };
    this.enabled = this.config.lipSyncEnabled;
    this.frameInterval = 1000 / this.config.speakingFrameRate;
    this.smoothing = { lastOpenness: 0, lastVolume: 0, velocity: 0 };
  }

  // --- Core API ---

  isEnabled(): boolean {
    return this.enabled;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.pendingFrames = [];
    }
  }

  getFrameBuffer(): readonly LipSyncFrame[] {
    return this.pendingFrames;
  }

  getFrameInterval(): number {
    return this.frameInterval;
  }

  // --- Generate Frame from Volume ---

  generateFrameFromVolume(volume: number, currentTime: number): LipSyncFrame | null {
    if (!this.enabled) return null;
    if (currentTime - this.lastFrameTime < this.frameInterval) return null;

    this.lastFrameTime = currentTime;

    const smoothedOpenness = this.smoothVolumeToOpenness(volume);
    const frame: LipSyncFrame = {
      timestamp: new Date(currentTime).toISOString(),
      openness: smoothedOpenness,
      phoneme: null,
      volume,
    };

    this.pushFrame(frame);
    return frame;
  }

  // --- Generate Frame from Phoneme ---

  generateFrameFromPhoneme(phoneme: string, volume: number, currentTime: number): LipSyncFrame | null {
    if (!this.enabled) return null;
    if (currentTime - this.lastFrameTime < this.frameInterval) return null;

    this.lastFrameTime = currentTime;

    const visemeOpenness = PHONEME_VISEME_MAP[phoneme.toUpperCase()] ?? 0.3;
    const volumeFactor = Math.min(1, volume * 1.5);
    const rawOpenness = visemeOpenness * volumeFactor;
    const smoothedOpenness = this.smoothVolumeToOpenness(rawOpenness);

    const frame: LipSyncFrame = {
      timestamp: new Date(currentTime).toISOString(),
      openness: smoothedOpenness,
      phoneme: phoneme.toUpperCase(),
      volume,
    };

    this.pushFrame(frame);
    return frame;
  }

  // --- Generate Silent Frame ---

  generateSilentFrame(currentTime: number): LipSyncFrame | null {
    if (!this.enabled) return null;
    if (currentTime - this.lastFrameTime < this.frameInterval) return null;

    this.lastFrameTime = currentTime;

    const smoothedOpenness = this.smoothVolumeToOpenness(0);
    const frame: LipSyncFrame = {
      timestamp: new Date(currentTime).toISOString(),
      openness: smoothedOpenness,
      phoneme: null,
      volume: 0,
    };

    this.pushFrame(frame);
    return frame;
  }

  // --- Batch Process Frames ---

  processBatch(volumes: readonly number[], startTime: number): readonly LipSyncFrame[] {
    const frames: LipSyncFrame[] = [];
    let currentTime = startTime;

    for (const volume of volumes) {
      const frame = this.generateFrameFromVolume(volume, currentTime);
      if (frame) {
        frames.push(frame);
      }
      currentTime += this.frameInterval;
    }

    return frames;
  }

  // --- State Transition ---

  onSpeakingStateChanged(state: SpeakingState): void {
    switch (state) {
      case 'SILENT':
      case 'SPEAKING_PAUSED':
        // Generate closing frames
        this.generateClosingFrames();
        break;
      case 'SPEAKING_ACTIVE':
        // Ready for new frames
        break;
      case 'SPEAKING_EMPHASIS':
        // Will receive louder volumes
        break;
    }
  }

  // --- Interruption (clears immediately) ---

  interrupt(): void {
    this.pendingFrames = [];
    this.smoothing = { lastOpenness: 0, lastVolume: 0, velocity: 0 };
  }

  // --- Smooth Interpolation ---

  private smoothVolumeToOpenness(volume: number): number {
    const clampedVolume = Math.max(0, Math.min(1, volume));

    // Apply non-linear curve (lips don't open linearly with volume)
    const curvedVolume = Math.pow(clampedVolume, 0.7);

    // Smooth with velocity-based easing
    const targetOpenness = curvedVolume;
    const diff = targetOpenness - this.smoothing.lastOpenness;

    // Faster opening, slower closing (natural speech pattern)
    const rate = diff > 0 ? this.smoothingFactor * 1.2 : this.smoothingFactor * 0.8;
    this.smoothing.velocity = diff * rate;

    const newOpenness = Math.max(0, Math.min(1,
      this.smoothing.lastOpenness + this.smoothing.velocity
    ));

    this.smoothing.lastOpenness = newOpenness;
    this.smoothing.lastVolume = clampedVolume;

    return Math.round(newOpenness * 100) / 100;
  }

  private generateClosingFrames(): void {
    const steps = 5;
    const startOpenness = this.smoothing.lastOpenness;
    const currentTime = Date.now();

    for (let i = 0; i < steps; i++) {
      const progress = (i + 1) / steps;
      const openness = startOpenness * (1 - progress);
      const frame: LipSyncFrame = {
        timestamp: new Date(currentTime + i * this.frameInterval).toISOString(),
        openness: Math.round(openness * 100) / 100,
        phoneme: null,
        volume: 0,
      };
      this.pushFrame(frame);
    }
  }

  private pushFrame(frame: LipSyncFrame): void {
    this.pendingFrames.push(frame);

    // Trim buffer
    if (this.pendingFrames.length > this.maxFrameBuffer) {
      this.pendingFrames = this.pendingFrames.slice(-this.maxFrameBuffer);
    }
  }

  // --- Reset ---

  reset(): void {
    this.pendingFrames = [];
    this.smoothing = { lastOpenness: 0, lastVolume: 0, velocity: 0 };
    this.lastFrameTime = 0;
  }

  // --- Destroy ---

  destroy(): void {
    this.reset();
  }
}

// ============================================================================
// PhonemeProvider Helper (for external TTS integration)
// ============================================================================

export function createPhonemeMapper(provider: { getPhoneme(): Promise<string | null> }): {
  mapToViseme: (phoneme: string) => number;
  getCurrentViseme: () => Promise<number>;
} {
  return {
    mapToViseme: (phoneme: string): number => {
      return PHONEME_VISEME_MAP[phoneme.toUpperCase()] ?? 0.3;
    },
    getCurrentViseme: async (): Promise<number> => {
      const phoneme = await provider.getPhoneme();
      if (phoneme === null) return 0;
      return PHONEME_VISEME_MAP[phoneme.toUpperCase()] ?? 0.3;
    },
  };
}
