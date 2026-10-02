// ============================================================================
// MYRAA Avatar Engine — Orchestrator
// ============================================================================

import type {
  AvatarConfig,
  AvatarContext,
  AvatarEvent,
  AvatarEventType,
  AvatarExpression,
  AvatarMainState,
  AvatarState,
  ExpressionRule,
  MicroAnimation,
  Point,
  SpeakingState,
  VoiceState,
  TaskState,
} from './contracts';
import { DEFAULT_AVATAR_CONFIG, nowISO, generateAvatarId } from './contracts';
import { AvatarStateMachine } from './stateEngine';
import { ExpressionEngine } from './expressionEngine';
import { MicroAnimationEngine } from './microAnimations';
import { LipSyncEngine } from './lipSync';

// ============================================================================
// Event Handler Type
// ============================================================================

type AvatarEventHandler = (event: AvatarEvent) => void;

// ============================================================================
// AvatarEngine
// ============================================================================

export class AvatarEngine {
  readonly stateMachine: AvatarStateMachine;
  readonly expressionEngine: ExpressionEngine;
  readonly microAnimations: MicroAnimationEngine;
  readonly lipSync: LipSyncEngine;

  private config: AvatarConfig;
  private id: string;
  private running: boolean = false;
  private updateIntervalMs: number;
  private updateTimer: ReturnType<typeof setInterval> | null = null;
  private eventHandlers: Map<AvatarEventType, AvatarEventHandler[]> = new Map();
  private eventHistory: AvatarEvent[] = [];
  private maxEventHistory: number = 200;
  private lastContext: AvatarContext;
  private lastUpdateTime: number = 0;
  private idleStartTime: number = Date.now();
  private lastVoiceState: VoiceState = 'idle';
  private lastTaskState: TaskState = 'idle';

  constructor(config: Partial<AvatarConfig> & { updateRate?: number } = {}) {
    const { updateRate, ...avatarConfig } = config;
    this.config = { ...DEFAULT_AVATAR_CONFIG, ...avatarConfig };
    this.id = generateAvatarId('eng');
    this.updateIntervalMs = updateRate ? 1000 / updateRate : 1000 / 30;

    this.stateMachine = new AvatarStateMachine(this.config);
    this.expressionEngine = new ExpressionEngine();
    this.microAnimations = new MicroAnimationEngine(this.config);
    this.lipSync = new LipSyncEngine(this.config);

    this.lastContext = this.buildDefaultContext();
  }

  // --- Lifecycle ---

  start(): void {
    if (this.running) return;
    this.running = true;
    this.idleStartTime = Date.now();

    this.updateTimer = setInterval(() => {
      this.tick();
    }, this.updateIntervalMs);
  }

  stop(): void {
    if (!this.running) return;
    this.running = false;

    if (this.updateTimer !== null) {
      clearInterval(this.updateTimer);
      this.updateTimer = null;
    }
  }

  isRunning(): boolean {
    return this.running;
  }

  getId(): string {
    return this.id;
  }

  // --- Get Current State ---

  getCurrentState(): AvatarState {
    const base = this.stateMachine.getCurrentState();
    const expression = this.expressionEngine.getBlendedExpression();
    const microAnims = this.microAnimations.getActiveAnimations();
    const eyeTarget = this.microAnimations.getGazeTarget();

    return {
      ...base,
      expression,
      microAnimations: microAnims,
      eyeTarget: eyeTarget ?? base.eyeTarget,
      breathRate: this.microAnimations.getBreathPhase() / Math.PI,
      bodySway: this.microAnimations.getBodySway(),
      headTilt: this.microAnimations.getHeadTilt(),
      timestamp: nowISO(),
    };
  }

  // --- Input: Update Context ---

  updateContext(context: Partial<AvatarContext>): void {
    const merged: AvatarContext = {
      ...this.lastContext,
      ...context,
    };
    this.lastContext = merged;

    // Detect voice state changes
    if (merged.voiceState !== this.lastVoiceState) {
      this.onVoiceStateChanged(this.lastVoiceState, merged.voiceState);
      this.lastVoiceState = merged.voiceState;
    }

    // Detect task state changes
    if (merged.taskState !== this.lastTaskState) {
      this.onTaskStateChanged(this.lastTaskState, merged.taskState);
      this.lastTaskState = merged.taskState;
    }

    // Handle interruption
    if (merged.userInterruption) {
      this.handleInterruption();
    }
  }

  // --- Input: Direct State Transitions ---

  requestTransition(to: AvatarMainState, reason: string = ''): boolean {
    if (!this.stateMachine.canTransition(to)) {
      return false;
    }

    const prev = this.stateMachine.getCurrentState();
    this.stateMachine.transition(to, {}, reason);

    const current = this.stateMachine.getCurrentState();
    this.emitEvent('STATE_CHANGED', prev.mainState, current.mainState, current.expression, { reason });

    return true;
  }

  // --- Input: Force State ---

  forceState(state: AvatarMainState, reason: string = 'forced'): void {
    const prev = this.stateMachine.getCurrentState();
    this.stateMachine.forceState(state, reason);

    const current = this.stateMachine.getCurrentState();
    this.emitEvent('STATE_CHANGED', prev.mainState, current.mainState, current.expression, { reason });
  }

  // --- Input: Set Expression ---

  setExpression(expression: AvatarExpression): void {
    this.expressionEngine.forceExpression(expression);
    const current = this.stateMachine.getCurrentState();
    this.emitEvent('EXPRESSION_CHANGED', current.mainState, current.mainState, expression, {});
  }

  // --- Input: Update Speaking State ---

  setSpeakingState(state: SpeakingState): void {
    const prev = this.stateMachine.getCurrentState();
    const prevSpeaking = prev.speakingState;

    this.stateMachine.transition(prev.mainState, { speakingState: state }, 'speaking state update');

    if (prevSpeaking === 'SILENT' && state === 'SPEAKING_ACTIVE') {
      this.emitEvent('SPEAKING_STARTED', prev.mainState, prev.mainState, prev.expression, {});
    } else if (prevSpeaking !== 'SILENT' && state === 'SILENT') {
      this.emitEvent('SPEAKING_ENDED', prev.mainState, prev.mainState, prev.expression, {});
    }

    this.lipSync.onSpeakingStateChanged(state);
  }

  // --- Input: Lip Sync Data ---

  processLipSyncVolume(volume: number): void {
    this.lipSync.generateFrameFromVolume(volume, Date.now());
  }

  processLipSyncPhoneme(phoneme: string, volume: number): void {
    this.lipSync.generateFrameFromPhoneme(phoneme, volume, Date.now());
  }

  // --- Event Handlers ---

  on(eventType: AvatarEventType, handler: AvatarEventHandler): void {
    const handlers = this.eventHandlers.get(eventType) ?? [];
    handlers.push(handler);
    this.eventHandlers.set(eventType, handlers);
  }

  off(eventType: AvatarEventType, handler: AvatarEventHandler): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      const idx = handlers.indexOf(handler);
      if (idx >= 0) {
        handlers.splice(idx, 1);
      }
    }
  }

  getEventHistory(): readonly AvatarEvent[] {
    return this.eventHistory;
  }

  getEventsSince(timestamp: string): readonly AvatarEvent[] {
    const ts = new Date(timestamp).getTime();
    return this.eventHistory.filter(e => new Date(e.timestamp).getTime() >= ts);
  }

  // --- Query ---

  getMainState(): AvatarMainState {
    return this.stateMachine.getCurrentState().mainState;
  }

  getExpression(): AvatarExpression {
    return this.expressionEngine.getCurrentExpression();
  }

  getMicroAnimations(): readonly MicroAnimation[] {
    return this.microAnimations.getActiveAnimations();
  }

  getLipSyncFrame(): Point | null {
    const frames = this.lipSync.getFrameBuffer();
    if (frames.length === 0) return null;
    const latest = frames[frames.length - 1];
    return { x: latest.openness, y: 0 };
  }

  getConfig(): AvatarConfig {
    return this.config;
  }

  // --- Private: Tick (main update loop) ---

  private tick(): void {
    const now = Date.now();
    this.lastUpdateTime = now;

    // Update idle duration
    const idleDuration = now - this.idleStartTime;
    const context: AvatarContext = {
      ...this.lastContext,
      idleDurationMs: idleDuration,
    };

    // Check for auto state transitions based on idle time
    this.checkIdleTransitions(idleDuration);

    // Update expression
    this.expressionEngine.update(context);

    // Update micro-animations
    const current = this.stateMachine.getCurrentState();
    this.microAnimations.update(now, current.mainState, current.eyeTarget);

    // Generate lip sync if speaking
    if (current.speakingState === 'SPEAKING_ACTIVE' || current.speakingState === 'SPEAKING_EMPHASIS') {
      this.lipSync.generateSilentFrame(now);
    }
  }

  // --- Private: State Change Handlers ---

  private onVoiceStateChanged(from: VoiceState, to: VoiceState): void {
    const current = this.stateMachine.getCurrentState();

    if (from === 'idle' && to === 'listening') {
      this.idleStartTime = Date.now();
      this.requestTransition('LISTENING', 'user started speaking');
    } else if (from === 'listening' && to === 'processing') {
      this.requestTransition('THINKING', 'user finished speaking');
    } else if (from === 'processing' && to === 'speaking') {
      this.requestTransition('WORKING', 'processing complete');
    } else if (from === 'speaking' && to === 'idle') {
      this.requestTransition('IDLE', 'speaking finished');
    } else if (to === 'error') {
      this.requestTransition('ERROR', 'voice pipeline error');
    }
  }

  private onTaskStateChanged(from: TaskState, to: TaskState): void {
    const current = this.stateMachine.getCurrentState();

    if (to === 'planning') {
      this.requestTransition('THINKING', 'task planning started');
    } else if (to === 'executing') {
      this.requestTransition('WORKING', 'task execution started');
    } else if (to === 'verifying') {
      this.requestTransition('VERIFYING', 'task verification started');
    } else if (to === 'recovering') {
      this.requestTransition('RECOVERY', 'task recovery needed');
    } else if (to === 'complete') {
      this.requestTransition('SPEAKING', 'task completed');
    } else if (to === 'failed') {
      this.requestTransition('ERROR', 'task failed');
    } else if (to === 'idle' && from !== 'idle') {
      this.requestTransition('IDLE', 'task returned to idle');
    }
  }

  private handleInterruption(): void {
    const prev = this.stateMachine.getCurrentState();
    this.expressionEngine.handleInterruption(400);
    this.microAnimations.interrupt(Date.now());
    this.lipSync.interrupt();

    // Transition to LISTENING if we were speaking
    if (prev.mainState === 'SPEAKING' || prev.mainState === 'WORKING') {
      this.stateMachine.transition('LISTENING', { speakingState: 'SILENT' }, 'user interruption');
      const current = this.stateMachine.getCurrentState();
      this.emitEvent('INTERRUPTED', prev.mainState, current.mainState, current.expression, {});
    }
  }

  // --- Private: Idle Transitions ---

  private checkIdleTransitions(idleDurationMs: number): void {
    const current = this.stateMachine.getCurrentState();
    const mainState = current.mainState;

    if (mainState === 'IDLE') {
      if (idleDurationMs > 300_000 && this.stateMachine.canTransition('SLEEPING')) {
        this.stateMachine.transition('SLEEPING', {}, 'extended inactivity');
        const newState = this.stateMachine.getCurrentState();
        this.emitEvent('STATE_CHANGED', 'IDLE', 'SLEEPING', newState.expression, { idleDurationMs });
      } else if (idleDurationMs > 60_000 && this.stateMachine.canTransition('RELAXED')) {
        this.stateMachine.transition('RELAXED', {}, 'long idle period');
        const newState = this.stateMachine.getCurrentState();
        this.emitEvent('STATE_CHANGED', 'IDLE', 'RELAXED', newState.expression, { idleDurationMs });
      }
    } else if (mainState === 'RELAXED' && idleDurationMs < 5_000) {
      if (this.stateMachine.canTransition('IDLE')) {
        this.stateMachine.transition('IDLE', {}, 'activity detected');
        const newState = this.stateMachine.getCurrentState();
        this.emitEvent('STATE_CHANGED', 'RELAXED', 'IDLE', newState.expression, {});
      }
    } else if (mainState === 'SLEEPING' && idleDurationMs < 5_000) {
      if (this.stateMachine.canTransition('IDLE')) {
        this.stateMachine.transition('IDLE', {}, 'wake signal');
        const newState = this.stateMachine.getCurrentState();
        this.emitEvent('STATE_CHANGED', 'SLEEPING', 'IDLE', newState.expression, {});
      }
    }
  }

  // --- Private: Event Emission ---

  private emitEvent(
    type: AvatarEventType,
    previousState: AvatarMainState,
    currentState: AvatarMainState,
    expression: AvatarExpression,
    data: Record<string, unknown>,
  ): void {
    const event: AvatarEvent = {
      type,
      timestamp: nowISO(),
      previousState,
      currentState,
      expression,
      data,
    };

    this.eventHistory.push(event);
    if (this.eventHistory.length > this.maxEventHistory) {
      this.eventHistory = this.eventHistory.slice(-this.maxEventHistory);
    }

    const handlers = this.eventHandlers.get(type);
    if (handlers) {
      for (const handler of handlers) {
        try {
          handler(event);
        } catch {
          // Handler errors should not crash the engine
        }
      }
    }
  }

  // --- Private: Helpers ---

  private buildDefaultContext(): AvatarContext {
    return {
      voiceState: 'idle',
      taskState: 'idle',
      taskSuccess: null,
      taskFailure: null,
      userInterruption: false,
      urgency: 'low',
      idleDurationMs: 0,
      lastInteractionMs: Date.now(),
      speakingVolume: 0,
      errorCount: 0,
    };
  }

  // --- Destroy ---

  destroy(): void {
    this.stop();
    this.expressionEngine.destroy();
    this.lipSync.destroy();
    this.microAnimations.reset();
    this.eventHandlers.clear();
    this.eventHistory = [];
  }
}

// ============================================================================
// Factory Function
// ============================================================================

export function createAvatarEngine(config?: Partial<AvatarConfig> & { updateRate?: number }): AvatarEngine {
  return new AvatarEngine(config);
}
