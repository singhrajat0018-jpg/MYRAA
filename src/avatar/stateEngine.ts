// ============================================================================
// MYRAA Avatar State Engine — Deterministic State Machine
// ============================================================================

import type {
  AvatarMainState,
  AvatarState,
  AvatarExpression,
  SpeakingState,
  MicroAnimation,
  Point,
  StateTransition,
  AvatarConfig,
} from './contracts';
import { DEFAULT_AVATAR_CONFIG, nowISO } from './contracts';

// ============================================================================
// Valid Transitions Table
// ============================================================================

const VALID_TRANSITIONS: Record<AvatarMainState, readonly AvatarMainState[]> = {
  IDLE: ['LISTENING', 'RELAXED', 'SLEEPING', 'ERROR'],
  LISTENING: ['THINKING', 'IDLE', 'ERROR'],
  THINKING: ['WORKING', 'IDLE', 'ERROR'],
  WORKING: ['VERIFYING', 'SPEAKING', 'ERROR'],
  SPEAKING: ['IDLE', 'LISTENING', 'ERROR'],
  VERIFYING: ['WORKING', 'RECOVERY', 'SPEAKING', 'IDLE', 'ERROR'],
  RECOVERY: ['WORKING', 'ERROR', 'IDLE'],
  ERROR: ['IDLE'],
  RELAXED: ['IDLE', 'SLEEPING', 'ERROR'],
  SLEEPING: ['IDLE', 'ERROR'],
};

// ============================================================================
// Transition Definitions (with timing)
// ============================================================================

const TRANSITION_DEFINITIONS: readonly StateTransition[] = [
  { from: 'IDLE', to: 'LISTENING', condition: 'User starts speaking', duration: 150, easing: 'ease-out' },
  { from: 'IDLE', to: 'RELAXED', condition: 'Long idle period', duration: 1000, easing: 'ease-in-out' },
  { from: 'IDLE', to: 'SLEEPING', condition: 'Very long idle period', duration: 2000, easing: 'ease-in' },
  { from: 'IDLE', to: 'ERROR', condition: 'System error', duration: 0, easing: 'linear' },

  { from: 'LISTENING', to: 'THINKING', condition: 'User finishes speaking, processing starts', duration: 200, easing: 'ease-in' },
  { from: 'LISTENING', to: 'IDLE', condition: 'Listening cancelled', duration: 150, easing: 'ease-out' },
  { from: 'LISTENING', to: 'ERROR', condition: 'Error during listening', duration: 0, easing: 'linear' },

  { from: 'THINKING', to: 'WORKING', condition: 'Plan formed, execution starts', duration: 250, easing: 'ease-in-out' },
  { from: 'THINKING', to: 'IDLE', condition: 'Thinking complete, nothing to do', duration: 200, easing: 'ease-out' },
  { from: 'THINKING', to: 'ERROR', condition: 'Error during thinking', duration: 0, easing: 'linear' },

  { from: 'WORKING', to: 'VERIFYING', condition: 'Action done, checking result', duration: 200, easing: 'ease-in' },
  { from: 'WORKING', to: 'SPEAKING', condition: 'Response ready', duration: 150, easing: 'ease-out' },
  { from: 'WORKING', to: 'ERROR', condition: 'Error during work', duration: 0, easing: 'linear' },

  { from: 'SPEAKING', to: 'IDLE', condition: 'Response complete', duration: 300, easing: 'ease-in-out' },
  { from: 'SPEAKING', to: 'LISTENING', condition: 'User interrupts', duration: 100, easing: 'ease-out' },
  { from: 'SPEAKING', to: 'ERROR', condition: 'Error during speech', duration: 0, easing: 'linear' },

  { from: 'VERIFYING', to: 'WORKING', condition: 'Needs retry', duration: 150, easing: 'ease-in' },
  { from: 'VERIFYING', to: 'RECOVERY', condition: 'Failure detected', duration: 200, easing: 'ease-in' },
  { from: 'VERIFYING', to: 'SPEAKING', condition: 'Verification passed, response ready', duration: 150, easing: 'ease-out' },
  { from: 'VERIFYING', to: 'IDLE', condition: 'Verification complete', duration: 200, easing: 'ease-out' },
  { from: 'VERIFYING', to: 'ERROR', condition: 'Error during verification', duration: 0, easing: 'linear' },

  { from: 'RECOVERY', to: 'WORKING', condition: 'Retrying', duration: 200, easing: 'ease-in' },
  { from: 'RECOVERY', to: 'ERROR', condition: 'Recovery failed', duration: 0, easing: 'linear' },
  { from: 'RECOVERY', to: 'IDLE', condition: 'Recovery aborted', duration: 200, easing: 'ease-out' },

  { from: 'ERROR', to: 'IDLE', condition: 'Error handled', duration: 500, easing: 'ease-in-out' },

  { from: 'RELAXED', to: 'IDLE', condition: 'Activity detected', duration: 200, easing: 'ease-out' },
  { from: 'RELAXED', to: 'SLEEPING', condition: 'Extended inactivity', duration: 1500, easing: 'ease-in' },

  { from: 'SLEEPING', to: 'IDLE', condition: 'Wake signal', duration: 500, easing: 'spring' },
];

// ============================================================================
// Build transition lookup
// ============================================================================

function buildTransitionLookup(): Map<string, StateTransition> {
  const map = new Map<string, StateTransition>();
  for (const t of TRANSITION_DEFINITIONS) {
    map.set(`${t.from}->${t.to}`, t);
  }
  return map;
}

// ============================================================================
// Build default AvatarState
// ============================================================================

function buildDefaultState(mainState: AvatarMainState = 'IDLE'): AvatarState {
  return {
    mainState,
    expression: 'NEUTRAL',
    speakingState: 'SILENT',
    microAnimations: [],
    eyeTarget: null,
    breathRate: 0.5,
    bodySway: 0,
    headTilt: 0,
    opacity: 1,
    scale: 1,
    timestamp: nowISO(),
  };
}

// ============================================================================
// State History Entry
// ============================================================================

interface StateHistoryEntry {
  readonly from: AvatarMainState;
  readonly to: AvatarMainState;
  readonly timestamp: string;
  readonly duration: number;
  readonly reason: string;
}

// ============================================================================
// AvatarStateMachine
// ============================================================================

export class AvatarStateMachine {
  private currentState: AvatarState;
  private transitionLookup: Map<string, StateTransition>;
  private history: StateHistoryEntry[] = [];
  private maxHistory: number;
  private config: AvatarConfig;
  private transitionStartTime: number = 0;
  private previousMainState: AvatarMainState;

  constructor(config: Partial<AvatarConfig> = {}) {
    this.config = { ...DEFAULT_AVATAR_CONFIG, ...config };
    this.transitionLookup = buildTransitionLookup();
    this.currentState = buildDefaultState();
    this.previousMainState = this.currentState.mainState;
  }

  // --- Core API ---

  getCurrentState(): AvatarState {
    return this.currentState;
  }

  getPreviousMainState(): AvatarMainState {
    return this.previousMainState;
  }

  canTransition(to: AvatarMainState): boolean {
    const from = this.currentState.mainState;
    return VALID_TRANSITIONS[from]?.includes(to) ?? false;
  }

  getValidTransitions(): readonly AvatarMainState[] {
    return VALID_TRANSITIONS[this.currentState.mainState] ?? [];
  }

  getTransition(from: AvatarMainState, to: AvatarMainState): StateTransition | null {
    return this.transitionLookup.get(`${from}->${to}`) ?? null;
  }

  // --- Transition ---

  transition(
    to: AvatarMainState,
    overrides: Partial<Pick<AvatarState, 'expression' | 'speakingState' | 'microAnimations' | 'eyeTarget' | 'breathRate' | 'bodySway' | 'headTilt' | 'opacity' | 'scale'>> = {},
    reason: string = '',
  ): AvatarState {
    const from = this.currentState.mainState;

    if (!this.canTransition(to)) {
      return this.currentState;
    }

    this.previousMainState = from;
    this.transitionStartTime = Date.now();

    const newMainState = to;
    const expression = overrides.expression ?? this.currentState.expression;
    const speakingState = overrides.speakingState ?? this.getDefaultSpeakingState(newMainState);

    const newState: AvatarState = {
      ...this.currentState,
      mainState: newMainState,
      expression,
      speakingState,
      microAnimations: overrides.microAnimations ?? this.currentState.microAnimations,
      eyeTarget: overrides.eyeTarget ?? this.getDefaultEyeTarget(newMainState),
      breathRate: overrides.breathRate ?? this.getDefaultBreathRate(newMainState),
      bodySway: overrides.bodySway ?? this.getDefaultBodySway(newMainState),
      headTilt: overrides.headTilt ?? this.getDefaultHeadTilt(newMainState),
      opacity: overrides.opacity ?? this.getDefaultOpacity(newMainState),
      scale: overrides.scale ?? this.currentState.scale,
      timestamp: nowISO(),
    };

    this.currentState = newState;

    // Record history
    this.history.push({
      from,
      to: newMainState,
      timestamp: nowISO(),
      duration: Date.now() - this.transitionStartTime,
      reason,
    });

    // Trim history
    if (this.history.length > this.maxHistory) {
      this.history = this.history.slice(-this.maxHistory);
    }

    return newState;
  }

  // --- Force State (for error recovery / initialization) ---

  forceState(state: AvatarMainState, reason: string = 'forced'): AvatarState {
    const from = this.currentState.mainState;
    this.previousMainState = from;
    this.currentState = buildDefaultState(state);
    this.history.push({
      from,
      to: state,
      timestamp: nowISO(),
      duration: 0,
      reason,
    });
    return this.currentState;
  }

  // --- State History ---

  getHistory(): readonly StateHistoryEntry[] {
    return this.history;
  }

  getHistorySince(timestamp: string): readonly StateHistoryEntry[] {
    const ts = new Date(timestamp).getTime();
    return this.history.filter(h => new Date(h.timestamp).getTime() >= ts);
  }

  getTransitionDuration(): number {
    return this.transitionStartTime > 0 ? Date.now() - this.transitionStartTime : 0;
  }

  // --- Default Values per State ---

  private getDefaultSpeakingState(state: AvatarMainState): SpeakingState {
    switch (state) {
      case 'SPEAKING': return 'SPEAKING_ACTIVE';
      case 'LISTENING': return 'SILENT';
      case 'WORKING': return 'SILENT';
      case 'THINKING': return 'SILENT';
      default: return 'SILENT';
    }
  }

  private getDefaultEyeTarget(state: AvatarMainState): Point | null {
    switch (state) {
      case 'LISTENING': return { x: 0, y: 0.3 };
      case 'THINKING': return { x: 0.2, y: 0.5 };
      case 'WORKING': return { x: 0, y: -0.2 };
      case 'SPEAKING': return { x: 0, y: 0 };
      case 'IDLE': return null;
      default: return null;
    }
  }

  private getDefaultBreathRate(state: AvatarMainState): number {
    switch (state) {
      case 'IDLE': return 0.4;
      case 'LISTENING': return 0.5;
      case 'THINKING': return 0.5;
      case 'WORKING': return 0.6;
      case 'SPEAKING': return 0.7;
      case 'RELAXED': return 0.3;
      case 'SLEEPING': return 0.2;
      case 'ERROR': return 0.8;
      default: return 0.5;
    }
  }

  private getDefaultBodySway(state: AvatarMainState): number {
    switch (state) {
      case 'IDLE': return 0;
      case 'LISTENING': return 0.05;
      case 'THINKING': return -0.05;
      case 'WORKING': return 0;
      case 'SPEAKING': return 0.05;
      case 'RELAXED': return 0.1;
      case 'SLEEPING': return 0.02;
      default: return 0;
    }
  }

  private getDefaultHeadTilt(state: AvatarMainState): number {
    switch (state) {
      case 'IDLE': return 0;
      case 'LISTENING': return 0.1;
      case 'THINKING': return 0.15;
      case 'WORKING': return -0.05;
      case 'SPEAKING': return 0.05;
      case 'RELAXED': return 0.1;
      case 'SLEEPING': return 0.1;
      default: return 0;
    }
  }

  private getDefaultOpacity(state: AvatarMainState): number {
    switch (state) {
      case 'SLEEPING': return 0.7;
      case 'ERROR': return 0.9;
      default: return 1;
    }
  }

  // --- Reset ---

  reset(): void {
    this.currentState = buildDefaultState();
    this.previousMainState = 'IDLE';
    this.history = [];
    this.transitionStartTime = 0;
  }
}
