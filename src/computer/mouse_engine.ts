// ============================================================================
// MYRAA Mouse Engine — Precision mouse automation with safety
// ============================================================================

import type {
  Vec2, BoundingBox, CoordinateSpace, ComputerAction, ActionType,
  UITarget, ScreenInfo, InputState, UserTakeoverState, DPICalibration,
  ComputerActionTelemetry,
} from './contracts';
import { toBoundingRect, pointInRect, CLICK_MARGIN } from './contracts';
import { DPIManager } from './dpi';

// ============================================================================
// Mouse State
// ============================================================================

export interface MouseActionParams {
  readonly target?: UITarget;
  readonly coordinates?: Vec2;
  readonly coordinateSpace: CoordinateSpace;
  readonly windowId?: number;
  readonly windowBounds?: BoundingBox;
  readonly dragDestination?: Vec2;
  readonly scrollAmount?: number;
}

export interface MouseActionResult {
  readonly actionId: string;
  readonly type: ActionType;
  readonly executedAt: Vec2;
  readonly screenSpace: Vec2;
  readonly duration: number;
  readonly success: boolean;
  readonly error?: string;
}

// ============================================================================
// Mouse Engine
// ============================================================================

export class MouseEngine {
  private dpiManager: DPIManager;
  private inputState: InputState;
  private takeoverState: UserTakeoverState;
  private heldKeys: Set<string> = new Set();
  private heldMouseButtons: Set<string> = new Set();

  constructor(dpiManager: DPIManager) {
    this.dpiManager = dpiManager;
    this.inputState = {
      heldKeys: [],
      heldMouseButtons: [],
      automationOwnsMouse: false,
      automationOwnsKeyboard: false,
      lastActionTimestamp: new Date().toISOString(),
    };
    this.takeoverState = {
      detected: false,
      detectedAt: new Date().toISOString(),
      mouseMoved: false,
      keyTyped: false,
      policy: 'PAUSE',
      automationPaused: false,
    };
  }

  // --- Core Execution ---

  async execute(action: ComputerAction, screens: readonly ScreenInfo[]): Promise<MouseActionResult> {
    const start = Date.now();

    if (this.takeoverState.automationPaused) {
      return this.errorResult(action.actionId, action.type, 'Automation paused — user takeover detected', start);
    }

    try {
      const screenPos = this.resolveTargetPosition(action, screens);

      switch (action.type) {
        case 'MOUSE_MOVE':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'CLICK':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'DOUBLE_CLICK':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'RIGHT_CLICK':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'MIDDLE_CLICK':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'DRAG':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'MOUSE_DOWN':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'MOUSE_UP':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'SCROLL':
          return this.buildResult(action, screenPos, Date.now() - start);
        case 'HORIZONTAL_SCROLL':
          return this.buildResult(action, screenPos, Date.now() - start);
        default:
          return this.errorResult(action.actionId, action.type, `Unknown mouse action: ${action.type}`, Date.now() - start);
      }
    } catch (err) {
      return this.errorResult(
        action.actionId, action.type,
        err instanceof Error ? err.message : 'Unknown error',
        Date.now() - start,
      );
    }
  }

  // --- Target Resolution ---

  resolveTargetPosition(action: ComputerAction, screens: readonly ScreenInfo[]): Vec2 {
    if (action.target) {
      return this.resolveFromTarget(action.target, action.coordinateSpace, screens);
    }
    if (action.coordinates) {
      return this.resolveFromCoordinates(action.coordinates, action.coordinateSpace, screens, action.windowBounds);
    }
    throw new Error('No target or coordinates provided');
  }

  private resolveFromTarget(target: UITarget, space: CoordinateSpace, screens: readonly ScreenInfo[]): Vec2 {
    const base = toBoundingRect(target.bounds);
    let pos: Vec2 = { x: base.centerX, y: base.centerY };

    switch (space) {
      case 'SCREEN_ABSOLUTE':
        break;
      case 'WINDOW_RELATIVE':
        if (target.windowId) {
          const winBounds = this.getWindowBounds(target.windowId, screens);
          pos = this.dpiManager.windowToScreen(pos, winBounds);
        }
        break;
      case 'CLIENT_RELATIVE':
        if (target.windowId) {
          const winBounds = this.getWindowBounds(target.windowId, screens);
          pos = this.dpiManager.windowToScreen(pos, winBounds);
        }
        break;
      case 'ELEMENT_RELATIVE':
        pos = this.dpiManager.safeClickPoint(target.bounds, CLICK_MARGIN);
        break;
    }

    return this.dpiManager.clampToScreens(pos, screens);
  }

  private resolveFromCoordinates(coords: Vec2, space: CoordinateSpace, screens: readonly ScreenInfo[], windowBounds?: BoundingBox): Vec2 {
    switch (space) {
      case 'SCREEN_ABSOLUTE':
        return this.dpiManager.clampToScreens(coords, screens);
      case 'WINDOW_RELATIVE':
      case 'CLIENT_RELATIVE':
        if (windowBounds) {
          return this.dpiManager.clampToScreens(
            this.dpiManager.windowToScreen(coords, windowBounds),
            screens,
          );
        }
        return coords;
      case 'ELEMENT_RELATIVE':
        return this.dpiManager.clampToScreens(coords, screens);
      default:
        return coords;
    }
  }

  private getWindowBounds(windowId: number, screens: readonly ScreenInfo[]): BoundingBox {
    // Default bounds if window not found — in real impl would query Python
    return { x: 0, y: 0, width: screens[0]?.bounds.width ?? 1920, height: screens[0]?.bounds.height ?? 1080 };
  }

  // --- State ---

  getInputState(): InputState {
    return { ...this.inputState };
  }

  getTakeoverState(): UserTakeoverState {
    return { ...this.takeoverState };
  }

  pauseAutomation(): void {
    this.takeoverState = { ...this.takeoverState, automationPaused: true };
  }

  resumeAutomation(): void {
    this.takeoverState = { ...this.takeoverState, automationPaused: false, detected: false };
  }

  releaseAll(): void {
    this.heldKeys.clear();
    this.heldMouseButtons.clear();
    this.inputState = {
      heldKeys: [],
      heldMouseButtons: [],
      automationOwnsMouse: false,
      automationOwnsKeyboard: false,
      lastActionTimestamp: new Date().toISOString(),
    };
  }

  // --- Helpers ---

  private buildResult(action: ComputerAction, screenPos: Vec2, duration: number): MouseActionResult {
    return {
      actionId: action.actionId,
      type: action.type,
      executedAt: screenPos,
      screenSpace: screenPos,
      duration,
      success: true,
    };
  }

  private errorResult(actionId: string, type: ActionType, error: string, duration: number): MouseActionResult {
    return {
      actionId,
      type,
      executedAt: { x: 0, y: 0 },
      screenSpace: { x: 0, y: 0 },
      duration,
      success: false,
      error,
    };
  }
}
