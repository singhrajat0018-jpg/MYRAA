import type { AvatarMainState, AvatarExpression } from '../avatar/contracts';

// ============================================================================
// Voice State
// ============================================================================

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'interrupted' | 'reconnecting' | 'error';

// ============================================================================
// Chat Message
// ============================================================================

export interface ChatMessage {
  readonly id: string;
  readonly role: 'user' | 'assistant';
  readonly content: string;
  readonly timestamp: string;
  readonly isStreaming: boolean;
  readonly taskProgress?: readonly TaskProgress[];
  readonly metadata?: Record<string, unknown>;
}

// ============================================================================
// Task Progress
// ============================================================================

export interface TaskProgress {
  readonly label: string;
  readonly status: 'pending' | 'active' | 'complete' | 'error';
  readonly icon?: string;
}

// ============================================================================
// UI Events (Discriminated Union)
// ============================================================================

export type UIEvent =
  | { type: 'UI_READY' }
  | { type: 'VOICE_STATE_CHANGED'; state: VoiceState }
  | { type: 'TRANSCRIPT_PARTIAL'; text: string }
  | { type: 'TRANSCRIPT_FINAL'; text: string }
  | { type: 'RESPONSE_DELTA'; text: string; messageId: string }
  | { type: 'RESPONSE_COMPLETE'; messageId: string }
  | { type: 'TASK_STARTED'; taskId: string; description: string }
  | { type: 'TASK_PROGRESS'; taskId: string; progress: number; status: string }
  | { type: 'TASK_COMPLETE'; taskId: string; success: boolean }
  | { type: 'VISION_RESULT'; sceneId: string }
  | { type: 'TARGET_FOUND'; targetId: string; confidence: number }
  | { type: 'VERIFICATION_RESULT'; passed: boolean; details: string }
  | { type: 'ERROR'; message: string; recoverable: boolean }
  | { type: 'AVATAR_STATE_CHANGED'; state: AvatarMainState; expression: AvatarExpression }
  | { type: 'INTERRUPTED' };

// ============================================================================
// Companion Tab IDs
// ============================================================================

export type CompanionTab = 'chat' | 'vision' | 'memory' | 'tools';
