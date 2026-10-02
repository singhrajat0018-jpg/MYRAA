// ============================================================================
// MYRAA Avatar State Engine — Contracts & Types
// ============================================================================

// ============================================================================
// IDs
// ============================================================================

let _avatarIdCounter = 0;

export function generateAvatarId(prefix = 'av'): string {
  return `${prefix}_${Date.now().toString(36)}_${(++_avatarIdCounter).toString(36)}`;
}

export function nowISO(): string {
  return new Date().toISOString();
}

// ============================================================================
// Avatar States (driven by application state)
// ============================================================================

export type AvatarMainState =
  | 'IDLE'
  | 'LISTENING'
  | 'THINKING'
  | 'WORKING'
  | 'SPEAKING'
  | 'VERIFYING'
  | 'RECOVERY'
  | 'ERROR'
  | 'RELAXED'
  | 'SLEEPING';

// ============================================================================
// Expressions (mapped from application context)
// ============================================================================

export type AvatarExpression =
  | 'NEUTRAL'
  | 'HAPPY'
  | 'EXCITED'
  | 'CALM'
  | 'CURIOUS'
  | 'CONCERNED'
  | 'SAD'
  | 'SURPRISED'
  | 'CONFUSED'
  | 'ANGRY'
  | 'FOCUSED'
  | 'ATTENTIVE'
  | 'CONVERSATIONAL'
  | 'THOUGHTFUL'
  | 'RELAXED'
  | 'SLEEPY';

// ============================================================================
// Micro-Animations (natural feel)
// ============================================================================

export type MicroAnimation =
  | 'BLINK'
  | 'BREATHE'
  | 'HEAD_NOD'
  | 'HEAD_TILT'
  | 'GAZE_SHIFT'
  | 'HAIR_SWAY'
  | 'BODY_SWAY'
  | 'BLINK_DOUBLE'
  | 'LOOK_UP'
  | 'LOOK_DOWN'
  | 'LOOK_LEFT'
  | 'LOOK_RIGHT';

// ============================================================================
// Speaking State
// ============================================================================

export type SpeakingState =
  | 'SILENT'
  | 'SPEAKING_PAUSED'
  | 'SPEAKING_ACTIVE'
  | 'SPEAKING_EMPHASIS';

// ============================================================================
// Voice State (from voice pipeline)
// ============================================================================

export type VoiceState =
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'interrupted'
  | 'error';

// ============================================================================
// Task State (from agent)
// ============================================================================

export type TaskState =
  | 'idle'
  | 'planning'
  | 'gathering'
  | 'executing'
  | 'verifying'
  | 'recovering'
  | 'complete'
  | 'failed'
  | 'cancelled';

// ============================================================================
// Point
// ============================================================================

export interface Point {
  readonly x: number;
  readonly y: number;
}

// ============================================================================
// Complete Avatar State (deterministic output)
// ============================================================================

export interface AvatarState {
  readonly mainState: AvatarMainState;
  readonly expression: AvatarExpression;
  readonly speakingState: SpeakingState;
  readonly microAnimations: readonly MicroAnimation[];
  readonly eyeTarget: Point | null;
  readonly breathRate: number;
  readonly bodySway: number;
  readonly headTilt: number;
  readonly opacity: number;
  readonly scale: number;
  readonly timestamp: string;
}

// ============================================================================
// State Transition Rules
// ============================================================================

export interface StateTransition {
  readonly from: AvatarMainState;
  readonly to: AvatarMainState;
  readonly condition: string;
  readonly duration: number;
  readonly easing: 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'spring';
}

// ============================================================================
// Expression Mapping Rules
// ============================================================================

export interface ExpressionRule {
  readonly voiceState: VoiceState | null;
  readonly taskState: TaskState | null;
  readonly taskSuccess: boolean | null;
  readonly taskFailure: boolean | null;
  readonly userInterruption: boolean | null;
  readonly urgency: 'low' | 'medium' | 'high' | null;
  readonly expression: AvatarExpression;
  readonly confidence: number;
}

// ============================================================================
// Avatar Configuration
// ============================================================================

export interface AvatarConfig {
  readonly idleVariationInterval: number;
  readonly blinkInterval: number;
  readonly blinkDuration: number;
  readonly breathCycle: number;
  readonly gazeShiftInterval: number;
  readonly maxMicroAnimations: number;
  readonly transitionDuration: number;
  readonly speakingFrameRate: number;
  readonly lipSyncEnabled: boolean;
  readonly microAnimationEnabled: boolean;
  readonly idleVariationEnabled: boolean;
}

export const DEFAULT_AVATAR_CONFIG: AvatarConfig = {
  idleVariationInterval: 8000,
  blinkInterval: 3500,
  blinkDuration: 150,
  breathCycle: 4000,
  gazeShiftInterval: 5000,
  maxMicroAnimations: 6,
  transitionDuration: 300,
  speakingFrameRate: 24,
  lipSyncEnabled: true,
  microAnimationEnabled: true,
  idleVariationEnabled: true,
};

// ============================================================================
// Lip Sync Frame
// ============================================================================

export interface LipSyncFrame {
  readonly timestamp: string;
  readonly openness: number;
  readonly phoneme: string | null;
  readonly volume: number;
}

// ============================================================================
// Avatar Events
// ============================================================================

export type AvatarEventType =
  | 'STATE_CHANGED'
  | 'EXPRESSION_CHANGED'
  | 'SPEAKING_STARTED'
  | 'SPEAKING_ENDED'
  | 'ANIMATION_STARTED'
  | 'ANIMATION_COMPLETED'
  | 'MICRO_ANIMATION_TRIGGERED'
  | 'GAZE_SHIFTED'
  | 'INTERRUPTED';

export interface AvatarEvent {
  readonly type: AvatarEventType;
  readonly timestamp: string;
  readonly previousState: AvatarMainState;
  readonly currentState: AvatarMainState;
  readonly expression: AvatarExpression;
  readonly data: Record<string, unknown>;
}

// ============================================================================
// Application Context (input for expression engine)
// ============================================================================

export interface AvatarContext {
  readonly voiceState: VoiceState;
  readonly taskState: TaskState;
  readonly taskSuccess: boolean | null;
  readonly taskFailure: boolean | null;
  readonly userInterruption: boolean;
  readonly urgency: 'low' | 'medium' | 'high';
  readonly idleDurationMs: number;
  readonly lastInteractionMs: number;
  readonly speakingVolume: number;
  readonly errorCount: number;
}

// ============================================================================
// Phoneme Provider Interface
// ============================================================================

export interface PhonemeProvider {
  getPhoneme(): Promise<string | null>;
}

// ============================================================================
// Audio Volume Provider Interface
// ============================================================================

export interface AudioVolumeProvider {
  getVolume(): Promise<number>;
}
