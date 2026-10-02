/**
 * Voice Activity Detector using Web Audio API
 * Provides real-time speech detection for more responsive interruption handling
 */

export type VADState = "silence" | "speech" | "transition";

export interface VADOptions {
  /** Sample rate of the audio input */
  sampleRate: number;
  /** FFT size for analysis */
  fftSize?: number;
  /** Smoothing time constant (0-1) */
  smoothingTimeConstant?: number;
  /** Speech threshold (0-1) */
  speechThreshold?: number;
  /** Hangover time (ms) to prevent choppy detection */
  hangoverTime?: number;
  /** Minimum speech duration (ms) to consider valid */
  minSpeechDuration?: number;
  /** Minimum silence duration (ms) to consider end of speech */
  minSilenceDuration?: number;
}

export class VoiceActivityDetector {
  private analyser: AnalyserNode | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private gainNode: GainNode | null = null;
  private audioContext: AudioContext | null = null;

  private sampleRate: number;
  private fftSize: number;
  private smoothingTimeConstant: number;
  private speechThreshold: number;
  private hangoverTime: number;
  private minSpeechDuration: number;
  private minSilenceDuration: number;

  // State tracking
  private state: VADState = "silence";
  private speechProbability: number = 0;
  private lastSpeechTime: number = 0;
  private lastSilenceTime: number = 0;
  private speechStartTime: number = 0;
  private silenceStartTime: number = 0;

  // Callbacks
  private _onStateChange: ((state: VADState, probability: number) => void) | null = null;

  constructor(options: VADOptions) {
    this.sampleRate = options.sampleRate;
    this.fftSize = options.fftSize || 512;
    this.smoothingTimeConstant = options.smoothingTimeConstant || 0.8;
    this.speechThreshold = options.speechThreshold || 0.3;
    this.hangoverTime = options.hangoverTime || 150;
    this.minSpeechDuration = options.minSpeechDuration || 100;
    this.minSilenceDuration = options.minSilenceDuration || 200;
  }

  /**
   * Initialize the VAD with an audio context
   */
  init(audioContext: AudioContext): void {
    this.audioContext = audioContext;
    // Create analyser node for frequency analysis
    this.analyser = audioContext.createAnalyser();
    this.analyser.fftSize = this.fftSize;
    this.analyser.smoothingTimeConstant = this.smoothingTimeConstant;

    // Create script processor for real-time analysis
    this.scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);
    // Create gain node to mute VAD output (we only need it for processing, not playback)
    this.gainNode = audioContext.createGain();
    this.gainNode.gain.value = 0; // Mute

    // Connect nodes
    this.scriptProcessor.onaudioprocess = (e) => this._processAudio(e);
  }

  /**
   * Connect audio source to the VAD
   */
  connect(source: AudioNode): void {
    if (this.analyser && this.scriptProcessor && this.audioContext && this.gainNode) {
      source.connect(this.analyser);
      this.analyser.connect(this.scriptProcessor);
      this.scriptProcessor.connect(this.gainNode);
      this.gainNode.connect(this.audioContext.destination);
    }
  }

  /**
   * Disconnect the VAD
   */
  disconnect(): void {
    if (this.scriptProcessor) {
      this.scriptProcessor.onaudioprocess = null;
      this.scriptProcessor.disconnect();
    }
    if (this.analyser) {
      this.analyser.disconnect();
    }
    if (this.gainNode) {
      this.gainNode.disconnect();
      this.gainNode = null;
    }
    this.audioContext = null;
  }

  /**
   * Set callback for VAD state changes
   */
  onStateChange(callback: (state: VADState, probability: number) => void): void {
    this._onStateChange = callback;
  }

  /**
   * Get current VAD state
   */
  getState(): VADState {
    return this.state;
  }

  /**
   * Get current speech probability (0-1)
   */
  getSpeechProbability(): number {
    return this.speechProbability;
  }

  /**
   * Process audio buffer for voice activity detection
   */
  private _processAudio(e: AudioProcessingEvent): void {
    if (!this.analyser) return;

    // Get frequency domain data
    const freqData = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(freqData);

    // Calculate spectral flux (change in frequency spectrum)
    const spectralFlux = this._calculateSpectralFlux(freqData);

    // Calculate zero crossing rate
    const zeroCrossingRate = this._calculateZeroCrossingRate(e.inputBuffer);

    // Calculate energy (RMS)
    const energy = this._calculateEnergy(e.inputBuffer);

    // Combine features for speech probability
    const speechProb = this._combineFeatures(spectralFlux, zeroCrossingRate, energy);

    // Apply smoothing
    this.speechProbability =
      this.smoothingTimeConstant * this.speechProbability +
      (1 - this.smoothingTimeConstant) * speechProb;

    // Update state with hysteresis
    this._updateState();
  }

  /**
   * Calculate spectral flux (measure of spectral change)
   */
  private _calculateSpectralFlux(freqData: Uint8Array): number {
    // Simple implementation - in practice would compare with previous frame
    // For now, use high-frequency energy as proxy
    const highFreqStart = Math.floor(this.fftSize * 0.3); // Focus on frequencies above 30%
    let sum = 0;
    for (let i = highFreqStart; i < freqData.length; i++) {
      sum += freqData[i];
    }
    return sum / (freqData.length - highFreqStart) / 255; // Normalize to 0-1
  }

  /**
   * Calculate zero crossing rate
   */
  private _calculateZeroCrossingRate(buffer: AudioBuffer): number {
    const channelData = buffer.getChannelData(0);
    let zeroCrossings = 0;

    for (let i = 1; i < channelData.length; i++) {
      if ((channelData[i - 1] >= 0 && channelData[i] < 0) ||
          (channelData[i - 1] < 0 && channelData[i] >= 0)) {
        zeroCrossings++;
      }
    }

    return zeroCrossings / channelData.length;
  }

  /**
   * Calculate energy (RMS)
   */
  private _calculateEnergy(buffer: AudioBuffer): number {
    const channelData = buffer.getChannelData(0);
    let sum = 0;

    for (let i = 0; i < channelData.length; i++) {
      sum += channelData[i] * channelData[i];
    }

    return Math.sqrt(sum / channelData.length);
  }

  /**
   * Combine features into speech probability
   */
  private _combineFeatures(spectralFlux: number, zcr: number, energy: number): number {
    // Weighted combination of features
    // These weights would need tuning based on empirical data
    const fluxWeight = 0.4;
    const zcrWeight = 0.3;
    const energyWeight = 0.3;

    // Normalize features to 0-1 range (approximate)
    const normFlux = Math.min(1, spectralFlux * 2); // Spectral flux typically < 0.5
    const normZCR = Math.min(1, zcr * 50); // ZCR for speech typically 0.02-0.1
    const normEnergy = Math.min(1, energy * 3); // Energy for speech varies widely

    return (fluxWeight * normFlux +
            zcrWeight * normZCR +
            energyWeight * normEnergy);
  }

  /**
   * Update VAD state with hysteresis to prevent chattering
   */
  private _updateState(): void {
    const now = Date.now();
    const speechThreshold = this.speechThreshold;
    const silenceThreshold = this.speechThreshold * 0.5; // Lower threshold for silence

    let newState = this.state;

    if (this.state === "silence") {
      if (this.speechProbability > speechThreshold) {
        // Potential speech start
        if (this.speechStartTime === 0) {
          this.speechStartTime = now;
        } else if (now - this.speechStartTime >= this.minSpeechDuration) {
          // Confirmed speech start
          newState = "speech";
          this.lastSpeechTime = now;
          this.silenceStartTime = 0;
        }
      } else {
        this.speechStartTime = 0;
      }
    } else if (this.state === "speech") {
      if (this.speechProbability < silenceThreshold) {
        // Potential silence start
        if (this.silenceStartTime === 0) {
          this.silenceStartTime = now;
        } else if (now - this.silenceStartTime >= this.hangoverTime) {
          // Confirmed silence start (with hangover)
          newState = "silence";
          this.lastSilenceTime = now;
          this.speechStartTime = 0;
        }
      } else {
        this.silenceStartTime = 0;
        this.lastSpeechTime = now;
      }
    }

    // State changed
    if (newState !== this.state) {
      this.state = newState;
      if (this._onStateChange) {
        this._onStateChange(this.state, this.speechProbability);
      }
    }
  }

  /**
   * Destroy the VAD and release resources
   */
  destroy(): void {
    this.disconnect();
    this.analyser = null;
    this.scriptProcessor = null;
    this.onStateChange = null;
  }
}