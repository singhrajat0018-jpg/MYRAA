// ============================================================================
// MYRAA Keyboard Engine — Precision keyboard automation with safety
// ============================================================================

import type {
  ComputerAction, ActionType, CoordinateSpace, InputState,
} from './contracts';

// ============================================================================
// Key State
// ============================================================================

export interface KeyboardActionResult {
  readonly actionId: string;
  readonly type: ActionType;
  readonly keys: readonly string[];
  readonly text?: string;
  readonly duration: number;
  readonly success: boolean;
  readonly error?: string;
}

// ============================================================================
// Keyboard Engine
// ============================================================================

export class KeyboardEngine {
  private heldKeys: Set<string> = new Set();
  private typingBuffer: string[] = [];
  private isTyping = false;

  async execute(action: ComputerAction): Promise<KeyboardActionResult> {
    const start = Date.now();

    try {
      switch (action.type) {
        case 'KEY_PRESS':
          return this.executeKeyPress(action, start);
        case 'HOTKEY':
          return this.executeHotkey(action, start);
        case 'TYPE_TEXT':
          return this.executeTypeText(action, start);
        case 'PASTE_TEXT':
          return this.executePasteText(action, start);
        default:
          return this.errorResult(action.actionId, action.type, `Unknown keyboard action: ${action.type}`, Date.now() - start);
      }
    } catch (err) {
      return this.errorResult(
        action.actionId, action.type,
        err instanceof Error ? err.message : 'Unknown error',
        Date.now() - start,
      );
    }
  }

  // --- Actions ---

  private executeKeyPress(action: ComputerAction, start: number): KeyboardActionResult {
    const keys = action.keys ?? [];
    for (const key of keys) {
      this.heldKeys.add(key);
      // Real execution would call pyautogui/keybd_event via Python
      this.heldKeys.delete(key);
    }
    return {
      actionId: action.actionId,
      type: action.type,
      keys,
      duration: Date.now() - start,
      success: true,
    };
  }

  private executeHotkey(action: ComputerAction, start: number): KeyboardActionResult {
    const keys = action.keys ?? [];
    // Press all keys down, then release in reverse
    for (const key of keys) this.heldKeys.add(key);
    for (const key of [...keys].reverse()) this.heldKeys.delete(key);
    return {
      actionId: action.actionId,
      type: action.type,
      keys,
      duration: Date.now() - start,
      success: true,
    };
  }

  private executeTypeText(action: ComputerAction, start: number): KeyboardActionResult {
    const text = action.text ?? '';
    this.isTyping = true;
    // Simulate character-by-character typing
    for (const ch of text) {
      this.typingBuffer.push(ch);
    }
    this.isTyping = false;
    return {
      actionId: action.actionId,
      type: action.type,
      keys: [],
      text,
      duration: Date.now() - start,
      success: true,
    };
  }

  private executePasteText(action: ComputerAction, start: number): KeyboardActionResult {
    const text = action.text ?? '';
    // Paste via Ctrl+V after clipboard set
    return {
      actionId: action.actionId,
      type: action.type,
      keys: ['ctrl', 'v'],
      text,
      duration: Date.now() - start,
      success: true,
    };
  }

  // --- State ---

  getHeldKeys(): readonly string[] {
    return [...this.heldKeys];
  }

  isTypingText(): boolean {
    return this.isTyping;
  }

  releaseAllKeys(): void {
    this.heldKeys.clear();
    this.typingBuffer = [];
    this.isTyping = false;
  }

  getInputState(): InputState {
    return {
      heldKeys: [...this.heldKeys],
      heldMouseButtons: [],
      automationOwnsMouse: false,
      automationOwnsKeyboard: this.heldKeys.size > 0,
      lastActionTimestamp: new Date().toISOString(),
    };
  }

  // --- Helpers ---

  private errorResult(actionId: string, type: ActionType, error: string, duration: number): KeyboardActionResult {
    return { actionId, type, keys: [], duration, success: false, error };
  }
}
