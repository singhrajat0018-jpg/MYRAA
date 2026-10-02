// ============================================================================
// MYRAA Avatar Micro-Animation Engine — Natural, Periodic Animations
// ============================================================================

import type {
  MicroAnimation,
  AvatarMainState,
  AvatarConfig,
  Point,
} from './contracts';
import { DEFAULT_AVATAR_CONFIG } from './contracts';

// ============================================================================
// Micro-Animation State
// ============================================================================

interface MicroAnimEntry {
  readonly type: MicroAnimation;
  readonly startTime: number;
  readonly duration: number;
  readonly intensity: number;
}

// ============================================================================
// Blink Schedule
// ============================================================================

interface BlinkSchedule {
  nextBlinkTime: number;
  blinkCount: number;
  isDoubleBlink: boolean;
}

// ============================================================================
// Gaze State
// ============================================================================

interface GazeState {
  target: Point | null;
  nextShiftTime: number;
  driftAngle: number;
}

// ============================================================================
// MicroAnimationEngine
// ============================================================================

export class MicroAnimationEngine {
  private config: AvatarConfig;
  private activeAnimations: MicroAnimEntry[] = [];
  private lastUpdateTime: number = Date.now();
  private blinkSchedule: BlinkSchedule;
  private gazeState: GazeState;
  private breathPhase: number = 0;
  private bodySwayPhase: number = 0;
  private headTiltPhase: number = 0;
  private enabled: boolean;

  constructor(config: Partial<AvatarConfig> = {}) {
    this.config = { ...DEFAULT_AVATAR_CONFIG, ...config };
    this.enabled = this.config.microAnimationEnabled;
    this.blinkSchedule = {
      nextBlinkTime: Date.now() + this.config.blinkInterval + this.randomJitter(),
      blinkCount: 0,
      isDoubleBlink: false,
    };
    this.gazeState = {
      target: null,
      nextShiftTime: Date.now() + this.config.gazeShiftInterval + this.randomJitter(),
      driftAngle: 0,
    };
  }

  // --- Core API ---

  isEnabled(): boolean {
    return this.enabled;
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.activeAnimations = [];
    }
  }

  getActiveAnimations(): readonly MicroAnimation[] {
    return this.activeAnimations.map(a => a.type);
  }

  getActiveAnimationDetails(): readonly MicroAnimEntry[] {
    return this.activeAnimations;
  }

  getBlinkSchedule(): BlinkSchedule {
    return { ...this.blinkSchedule };
  }

  getGazeTarget(): Point | null {
    return this.gazeState.target;
  }

  getBreathPhase(): number {
    return this.breathPhase;
  }

  getBodySway(): number {
    return Math.sin(this.bodySwayPhase) * 0.5;
  }

  getHeadTilt(): number {
    return Math.sin(this.headTiltPhase) * 0.3;
  }

  // --- Update (called per frame) ---

  update(currentTime: number, mainState: AvatarMainState, eyeTarget: Point | null): MicroAnimation[] {
    if (!this.enabled) return [];

    const dt = Math.min(currentTime - this.lastUpdateTime, 100);
    this.lastUpdateTime = currentTime;

    // Update phases
    this.breathPhase = (this.breathPhase + (dt / this.config.breathCycle) * Math.PI * 2) % (Math.PI * 2);
    this.bodySwayPhase = (this.bodySwayPhase + (dt / (this.config.breathCycle * 1.5)) * Math.PI * 2) % (Math.PI * 2);
    this.headTiltPhase = (this.headTiltPhase + (dt / (this.config.breathCycle * 2)) * Math.PI * 2) % (Math.PI * 2);

    // Clean expired animations
    this.activeAnimations = this.activeAnimations.filter(a => currentTime - a.startTime < a.duration);

    const triggered: MicroAnimation[] = [];

    // Always: BREATHE
    if (!this.hasAnimation('BREATHE')) {
      this.activeAnimations.push({
        type: 'BREATHE',
        startTime: currentTime,
        duration: this.config.breathCycle,
        intensity: this.getBreathIntensity(mainState),
      });
      triggered.push('BREATHE');
    }

    // State-specific scheduling
    switch (mainState) {
      case 'IDLE':
        this.scheduleIdleAnimations(currentTime, mainState, triggered);
        break;
      case 'LISTENING':
        this.scheduleListeningAnimations(currentTime, mainState, triggered);
        break;
      case 'THINKING':
        this.scheduleThinkingAnimations(currentTime, mainState, triggered);
        break;
      case 'WORKING':
        this.scheduleWorkingAnimations(currentTime, mainState, triggered);
        break;
      case 'SPEAKING':
        this.scheduleSpeakingAnimations(currentTime, mainState, triggered);
        break;
      case 'RELAXED':
        this.scheduleRelaxedAnimations(currentTime, mainState, triggered);
        break;
      case 'SLEEPING':
        this.scheduleSleepingAnimations(currentTime, mainState, triggered);
        break;
      default:
        this.scheduleIdleAnimations(currentTime, mainState, triggered);
        break;
    }

    // Update gaze based on state
    this.updateGaze(currentTime, mainState, eyeTarget);

    return triggered;
  }

  // --- Interrupt (clear all pending, trigger immediate blink) ---

  interrupt(currentTime: number): void {
    this.activeAnimations = [];
    this.blinkSchedule.nextBlinkTime = currentTime + 100;
    this.gazeState.target = null;
  }

  // --- Reset ---

  reset(): void {
    this.activeAnimations = [];
    this.breathPhase = 0;
    this.bodySwayPhase = 0;
    this.headTiltPhase = 0;
    this.blinkSchedule = {
      nextBlinkTime: Date.now() + this.config.blinkInterval + this.randomJitter(),
      blinkCount: 0,
      isDoubleBlink: false,
    };
    this.gazeState = {
      target: null,
      nextShiftTime: Date.now() + this.config.gazeShiftInterval + this.randomJitter(),
      driftAngle: 0,
    };
  }

  // --- Private: Scheduling ---

  private scheduleIdleAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Blink
    if (this.shouldBlink(currentTime)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Gaze shift
    if (this.shouldShiftGaze(currentTime)) {
      this.triggerGazeShift(currentTime, triggered);
    }

    // Occasional head tilt
    if (this.randomChance(0.003)) {
      this.addAnimation('HEAD_TILT', currentTime, 1200, 0.3, triggered);
    }

    // Very subtle body sway
    if (!this.hasAnimation('BODY_SWAY') && this.randomChance(0.005)) {
      this.addAnimation('BODY_SWAY', currentTime, 2000, 0.2, triggered);
    }
  }

  private scheduleListeningAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Blink (slightly more frequent when attentive)
    if (this.shouldBlink(currentTime, 0.8)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Attentive gaze (keep looking at user)
    if (this.gazeState.target === null) {
      this.gazeState.target = { x: 0, y: 0.3 };
    }

    // Occasional nod
    if (this.randomChance(0.008)) {
      this.addAnimation('HEAD_NOD', currentTime, 600, 0.4, triggered);
    }

    // Head tilt when really listening
    if (this.randomChance(0.005)) {
      this.addAnimation('HEAD_TILT', currentTime, 1000, 0.25, triggered);
    }
  }

  private scheduleThinkingAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Blink
    if (this.shouldBlink(currentTime)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Look up/away (thinking pose)
    if (!this.hasAnimation('LOOK_UP') && !this.hasAnimation('LOOK_LEFT') && this.randomChance(0.004)) {
      const dir = this.randomChoice(['LOOK_UP', 'LOOK_LEFT'] as const);
      this.addAnimation(dir, currentTime, 1500, 0.5, triggered);
    }

    // Head tilt (pondering)
    if (!this.hasAnimation('HEAD_TILT') && this.randomChance(0.006)) {
      this.addAnimation('HEAD_TILT', currentTime, 1800, 0.35, triggered);
    }

    // Gaze shift (looking around while thinking)
    if (this.shouldShiftGaze(currentTime, 0.6)) {
      this.gazeState.target = {
        x: this.gazeState.driftAngle > 0 ? 0.15 : -0.15,
        y: 0.4,
      };
      this.gazeState.nextShiftTime = currentTime + 2000 + this.randomJitter();
      this.addAnimation('GAZE_SHIFT', currentTime, 800, 0.4, triggered);
    }
  }

  private scheduleWorkingAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Blink (less frequent when focused)
    if (this.shouldBlink(currentTime, 1.2)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Focused gaze (looking down at work)
    if (!this.hasAnimation('GAZE_SHIFT') && this.randomChance(0.002)) {
      this.gazeState.target = { x: 0, y: -0.2 };
      this.addAnimation('GAZE_SHIFT', currentTime, 1000, 0.6, triggered);
    }

    // Minimal head movement (focus)
    if (this.randomChance(0.002)) {
      this.addAnimation('HEAD_TILT', currentTime, 800, 0.15, triggered);
    }
  }

  private scheduleSpeakingAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Blink (natural while speaking)
    if (this.shouldBlink(currentTime, 0.9)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Conversational head movement
    if (this.randomChance(0.01)) {
      this.addAnimation('HEAD_NOD', currentTime, 400, 0.3, triggered);
    }

    // Head tilt variations while speaking
    if (!this.hasAnimation('HEAD_TILT') && this.randomChance(0.007)) {
      this.addAnimation('HEAD_TILT', currentTime, 1200, 0.2, triggered);
    }

    // Body sway (gesturing)
    if (!this.hasAnimation('BODY_SWAY') && this.randomChance(0.004)) {
      this.addAnimation('BODY_SWAY', currentTime, 1500, 0.25, triggered);
    }

    // Gaze stays on listener
    this.gazeState.target = { x: 0, y: 0.1 };
  }

  private scheduleRelaxedAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Slow blink
    if (this.shouldBlink(currentTime, 1.3)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Gentle gaze drift
    if (this.shouldShiftGaze(currentTime, 0.5)) {
      this.gazeState.target = {
        x: Math.sin(this.gazeState.driftAngle) * 0.1,
        y: 0.2 + Math.cos(this.gazeState.driftAngle) * 0.05,
      };
      this.gazeState.nextShiftTime = currentTime + 6000 + this.randomJitter();
      this.addAnimation('GAZE_SHIFT', currentTime, 1200, 0.2, triggered);
    }

    // Subtle body sway
    if (!this.hasAnimation('BODY_SWAY') && this.randomChance(0.003)) {
      this.addAnimation('BODY_SWAY', currentTime, 2500, 0.15, triggered);
    }

    // Head tilt
    if (this.randomChance(0.003)) {
      this.addAnimation('HEAD_TILT', currentTime, 2000, 0.2, triggered);
    }
  }

  private scheduleSleepingAnimations(currentTime: number, _state: AvatarMainState, triggered: MicroAnimation[]): void {
    // Very slow blink
    if (this.shouldBlink(currentTime, 2.0)) {
      this.triggerBlink(currentTime, triggered);
    }

    // Slow, deep breathing
    // (handled by breathPhase with lower breathRate)

    // Minimal gaze (eyes closed, but target is neutral)
    this.gazeState.target = { x: 0, y: -0.1 };
  }

  // --- Blink Logic ---

  private shouldBlink(currentTime: number, speedMultiplier: number = 1.0): boolean {
    if (currentTime < this.blinkSchedule.nextBlinkTime) return false;
    return true;
  }

  private triggerBlink(currentTime: number, triggered: MicroAnimation[]): void {
    const isDouble = this.randomChance(0.15);
    const animType: MicroAnimation = isDouble ? 'BLINK_DOUBLE' : 'BLINK';

    this.addAnimation(animType, currentTime, this.config.blinkDuration * (isDouble ? 2 : 1), 1.0, triggered);

    this.blinkSchedule.blinkCount++;
    this.blinkSchedule.isDoubleBlink = isDouble;

    // Schedule next blink with natural variation
    const nextInterval = this.config.blinkInterval * (0.7 + Math.random() * 0.6);
    this.blinkSchedule.nextBlinkTime = currentTime + nextInterval;
  }

  // --- Gaze Logic ---

  private shouldShiftGaze(currentTime: number, speedMultiplier: number = 1.0): boolean {
    return currentTime >= this.gazeState.nextShiftTime;
  }

  private updateGaze(currentTime: number, _state: AvatarMainState, eyeTarget: Point | null): void {
    if (eyeTarget !== null) {
      this.gazeState.target = eyeTarget;
    }

    // Natural drift
    if (this.gazeState.target !== null) {
      this.gazeState.driftAngle += 0.001;
      const driftX = Math.sin(this.gazeState.driftAngle) * 0.02;
      const driftY = Math.cos(this.gazeState.driftAngle * 0.7) * 0.01;
      this.gazeState = {
        ...this.gazeState,
        target: {
          x: this.gazeState.target.x + driftX,
          y: this.gazeState.target.y + driftY,
        },
      };
    }
  }

  private triggerGazeShift(currentTime: number, triggered: MicroAnimation[]): void {
    const angles = [0, Math.PI / 4, Math.PI / 2, Math.PI, -Math.PI / 4, -Math.PI / 2];
    const chosenAngle = angles[Math.floor(Math.random() * angles.length)];
    this.gazeState.driftAngle = chosenAngle;

    const dist = 0.05 + Math.random() * 0.15;
    this.gazeState.target = {
      x: Math.cos(chosenAngle) * dist,
      y: Math.sin(chosenAngle) * dist * 0.5 + 0.1,
    };

    this.addAnimation('GAZE_SHIFT', currentTime, 800, 0.3, triggered);
    this.gazeState.nextShiftTime = currentTime + this.config.gazeShiftInterval + this.randomJitter();
  }

  // --- Helpers ---

  private addAnimation(type: MicroAnimation, startTime: number, duration: number, intensity: number, triggered: MicroAnimation[]): void {
    if (this.activeAnimations.length >= this.config.maxMicroAnimations) return;
    if (this.hasAnimation(type)) return;

    this.activeAnimations.push({ type, startTime, duration, intensity });
    triggered.push(type);
  }

  private hasAnimation(type: MicroAnimation): boolean {
    return this.activeAnimations.some(a => a.type === type);
  }

  private getBreathIntensity(state: AvatarMainState): number {
    switch (state) {
      case 'SLEEPING': return 0.8;
      case 'RELAXED': return 0.6;
      case 'SPEAKING': return 0.4;
      case 'ERROR': return 0.3;
      default: return 0.5;
    }
  }

  private randomJitter(): number {
    return (Math.random() - 0.5) * 1000;
  }

  private randomChance(probability: number): boolean {
    return Math.random() < probability;
  }

  private randomChoice<T extends readonly string[]>(arr: T): T[number] {
    return arr[Math.floor(Math.random() * arr.length)];
  }
}
