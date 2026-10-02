// ============================================================================
// MYRAA Computer Control Engine — Main orchestrator for computer automation
// ============================================================================

import type {
  ComputerAction, ComputerEnvironment, ComputerActionTelemetry,
  AutomationBudget, UITarget, ScreenInfo, WindowInfo,
  UserTakeoverState, InputState, ActionType, DPICalibration,
} from './contracts';
import { DEFAULT_AUTOMATION_BUDGET, TARGET_STALENESS_MS } from './contracts';
import { DPIManager } from './dpi';
import { MouseEngine } from './mouse_engine';
import { KeyboardEngine } from './keyboard_engine';
import { ScrollDragEngine } from './scroll_drag';
import { WindowControl, ApplicationControl } from './window_app_control';
import { VisualTargeter } from './visual_targeting';
import { TargetResolver } from './target_resolution';
import { PolicyEngine } from './policy';
import { TransactionManager } from './transactions';
import { LoopDetector, type StuckState } from './loop_detection';

// ============================================================================
// Engine State
// ============================================================================

export interface EngineState {
  readonly initialized: boolean;
  readonly budget: AutomationBudget;
  readonly takeover: UserTakeoverState;
  readonly inputState: InputState;
  readonly stuckState: StuckState;
  readonly lastActionAt: string | null;
  readonly totalActionsExecuted: number;
  readonly totalFailures: number;
}

// ============================================================================
// Computer Control Engine
// ============================================================================

export class ComputerControlEngine {
  private dpiManager: DPIManager;
  private mouseEngine: MouseEngine;
  private keyboardEngine: KeyboardEngine;
  private scrollDragEngine: ScrollDragEngine;
  private windowControl: WindowControl;
  private applicationControl: ApplicationControl;
  private visualTargeter: VisualTargeter;
  private targetResolver: TargetResolver;
  private policyEngine: PolicyEngine;
  private transactionManager: TransactionManager;
  private loopDetector: LoopDetector;

  private budget: AutomationBudget;
  private environment: ComputerEnvironment | null = null;
  private telemetry: ComputerActionTelemetry[] = [];
  private maxTelemetry = 500;

  constructor() {
    this.dpiManager = new DPIManager();
    this.mouseEngine = new MouseEngine(this.dpiManager);
    this.keyboardEngine = new KeyboardEngine();
    this.scrollDragEngine = new ScrollDragEngine(this.dpiManager);
    this.windowControl = new WindowControl();
    this.applicationControl = new ApplicationControl();
    this.visualTargeter = new VisualTargeter();
    this.targetResolver = new TargetResolver();
    this.policyEngine = new PolicyEngine();
    this.transactionManager = new TransactionManager();
    this.loopDetector = new LoopDetector();
    this.budget = { ...DEFAULT_AUTOMATION_BUDGET };
  }

  // --- Initialization ---

  initialize(environment: ComputerEnvironment): void {
    this.environment = environment;
    this.calibrateScreens(environment.screens);
    this.windowControl.updateWindows(environment.windows);
    this.visualTargeter.updateTargets(environment.detectedTargets, environment.stateHash);
  }

  private calibrateScreens(screens: readonly ScreenInfo[]): void {
    for (const screen of screens) {
      this.dpiManager.calibrateScreen(screen);
    }
  }

  // --- Main Execution ---

  async executeAction(action: ComputerAction): Promise<ComputerActionResult> {
    const start = Date.now();

    // Budget check
    if (!this.budget.withinBudget) {
      return this.buildResult(action, false, 'Budget exceeded', Date.now() - start);
    }

    // Loop detection
    const stuck = this.loopDetector.detectStuck();
    if (stuck.detected && stuck.stuckType === 'REPEATED_ACTION') {
      return this.buildResult(action, false, stuck.recommendation, Date.now() - start);
    }

    // Policy check
    const decision = this.policyEngine.evaluate(action, {
      budget: this.budget,
      recentActions: [],
      takeoverActive: this.mouseEngine.getTakeoverState().automationPaused,
    });

    if (!decision.approved) {
      return this.buildResult(action, false, `Policy blocked: ${decision.reason}`, Date.now() - start);
    }

    // Execute based on action type
    let result: ComputerActionResult;
    if (this.isMouseAction(action.type)) {
      const mouseResult = await this.mouseEngine.execute(action, this.environment?.screens ?? []);
      result = this.buildResult(action, mouseResult.success, mouseResult.error, mouseResult.duration);
    } else if (this.isKeyboardAction(action.type)) {
      const kbResult = await this.keyboardEngine.execute(action);
      result = this.buildResult(action, kbResult.success, kbResult.error, kbResult.duration);
    } else if (this.isScrollDragAction(action.type)) {
      const sdResult = action.type === 'SCROLL' || action.type === 'HORIZONTAL_SCROLL'
        ? await this.scrollDragEngine.scroll(action)
        : await this.scrollDragEngine.drag(action);
      result = this.buildResult(action, sdResult.success, sdResult.error, Date.now() - start);
    } else if (this.isWindowAction(action.type)) {
      result = await this.executeWindowAction(action);
    } else {
      result = this.buildResult(action, false, `Unsupported action type: ${action.type}`, Date.now() - start);
    }

    // Record
    this.loopDetector.recordAction(action);
    this.updateBudget(action);
    this.recordTelemetry(action, result);

    return result;
  }

  // --- Transaction Support ---

  async executeTransaction(actions: ComputerAction[]): Promise<TransactionResult> {
    const tx = this.transactionManager.createTransaction(actions);

    const verification = async (action: ComputerAction) => {
      const result = await this.executeAction(action);
      return {
        actionId: action.actionId,
        method: 'STATE_CHECK' as const,
        expected: action.expectedOutcome,
        actual: result.success ? 'executed' : result.error,
        passed: result.success,
        confidence: action.confidence,
        timestamp: new Date().toISOString(),
        latencyMs: result.duration,
      };
    };

    const completedTx = await this.transactionManager.executeTransaction(tx.transactionId, verification);
    return {
      transactionId: completedTx.transactionId,
      status: completedTx.status,
      stepsCompleted: completedTx.steps.filter(s => s.status === 'COMPLETED').length,
      totalSteps: completedTx.steps.length,
      duration: Date.now() - new Date(completedTx.createdAt).getTime(),
    };
  }

  // --- Environment ---

  updateEnvironment(env: ComputerEnvironment): void {
    this.environment = env;
    this.calibrateScreens(env.screens);
    this.windowControl.updateWindows(env.windows);
    this.visualTargeter.updateTargets(env.detectedTargets, env.stateHash);
  }

  getEnvironment(): ComputerEnvironment | null {
    return this.environment;
  }

  // --- Target Resolution ---

  findTarget(query: string): ReturnType<TargetResolver['resolve']> {
    const targets = this.environment?.detectedTargets ?? [];
    return this.targetResolver.resolve(query, targets);
  }

  findTargetVisual(description: string): ReturnType<VisualTargeter['findTarget']> {
    const targets = this.environment?.detectedTargets ?? [];
    return this.visualTargeter.findTarget(description, targets);
  }

  // --- DPI ---

  getDPICalibration(screenId: number): DPICalibration | undefined {
    return this.dpiManager.getCalibration(screenId);
  }

  // --- Policy ---

  getPolicyEngine(): PolicyEngine {
    return this.policyEngine;
  }

  // --- State ---

  getState(): EngineState {
    return {
      initialized: this.environment !== null,
      budget: { ...this.budget },
      takeover: this.mouseEngine.getTakeoverState(),
      inputState: this.mouseEngine.getInputState(),
      stuckState: this.loopDetector.detectStuck(),
      lastActionAt: this.telemetry.length > 0 ? this.telemetry[this.telemetry.length - 1].timestamp : null,
      totalActionsExecuted: this.telemetry.length,
      totalFailures: this.telemetry.filter(t => t.result === 'FAILED').length,
    };
  }

  // --- Takeover ---

  pauseForTakeover(): void {
    this.mouseEngine.pauseAutomation();
    this.keyboardEngine.releaseAllKeys();
    this.mouseEngine.releaseAll();
  }

  resumeAfterTakeover(): void {
    this.mouseEngine.resumeAutomation();
  }

  emergencyStop(): void {
    this.mouseEngine.releaseAll();
    this.keyboardEngine.releaseAllKeys();
    this.mouseEngine.pauseAutomation();
  }

  // --- Telemetry ---

  getTelemetry(limit = 50): readonly ComputerActionTelemetry[] {
    return this.telemetry.slice(-limit);
  }

  private recordTelemetry(action: ComputerAction, result: ComputerActionResult): void {
    const t: ComputerActionTelemetry = {
      actionId: action.actionId,
      type: action.type,
      targetSource: action.target?.source,
      confidence: action.confidence,
      coordinates: action.coordinates,
      windowId: action.windowId,
      duration: result.duration,
      result: result.success ? 'SUCCESS' : 'FAILED',
      recoveryAttempted: false,
      timestamp: new Date().toISOString(),
    };
    this.telemetry.push(t);
    if (this.telemetry.length > this.maxTelemetry) this.telemetry.shift();
  }

  // --- Budget ---

  private updateBudget(action: ComputerAction): void {
    (this.budget as { actionsUsed: number }).actionsUsed++;
    (this.budget as { withinBudget: boolean }).withinBudget =
      this.budget.actionsUsed < this.budget.maxActions;
  }

  resetBudget(): void {
    this.budget = { ...DEFAULT_AUTOMATION_BUDGET };
  }

  // --- Helpers ---

  private isMouseAction(type: ActionType): boolean {
    return ['MOUSE_MOVE', 'CLICK', 'DOUBLE_CLICK', 'RIGHT_CLICK', 'MIDDLE_CLICK', 'MOUSE_DOWN', 'MOUSE_UP', 'DRAG', 'SCROLL', 'HORIZONTAL_SCROLL'].includes(type);
  }

  private isKeyboardAction(type: ActionType): boolean {
    return ['KEY_PRESS', 'HOTKEY', 'TYPE_TEXT', 'PASTE_TEXT'].includes(type);
  }

  private isScrollDragAction(type: ActionType): boolean {
    return ['SCROLL', 'HORIZONTAL_SCROLL', 'DRAG'].includes(type);
  }

  private isWindowAction(type: ActionType): boolean {
    return ['FOCUS_WINDOW', 'OPEN_APP', 'CLOSE_APP', 'MINIMIZE', 'MAXIMIZE', 'RESTORE'].includes(type);
  }

  private async executeWindowAction(action: ComputerAction): Promise<ComputerActionResult> {
    const start = Date.now();
    const hwnd = action.windowId ?? 0;

    switch (action.type) {
      case 'FOCUS_WINDOW': {
        const r = await this.windowControl.focusWindow(hwnd);
        return this.buildResult(action, r.success, r.error, Date.now() - start);
      }
      case 'MINIMIZE': {
        const r = await this.windowControl.minimizeWindow(hwnd);
        return this.buildResult(action, r.success, r.error, Date.now() - start);
      }
      case 'MAXIMIZE': {
        const r = await this.windowControl.maximizeWindow(hwnd);
        return this.buildResult(action, r.success, r.error, Date.now() - start);
      }
      case 'RESTORE': {
        const r = await this.windowControl.restoreWindow(hwnd);
        return this.buildResult(action, r.success, r.error, Date.now() - start);
      }
      case 'OPEN_APP': {
        const r = await this.applicationControl.openApp(action.text ?? '');
        return this.buildResult(action, r.success, r.error, Date.now() - start);
      }
      case 'CLOSE_APP': {
        const r = await this.applicationControl.closeApp(action.text ?? '');
        return this.buildResult(action, r.success, r.error, Date.now() - start);
      }
      default:
        return this.buildResult(action, false, `Unknown window action: ${action.type}`, Date.now() - start);
    }
  }

  private buildResult(action: ComputerAction, success: boolean, error: string | undefined, duration: number): ComputerActionResult {
    return {
      actionId: action.actionId,
      type: action.type,
      success,
      error,
      duration,
      timestamp: new Date().toISOString(),
    };
  }
}

// ============================================================================
// Result Types
// ============================================================================

export interface ComputerActionResult {
  readonly actionId: string;
  readonly type: ActionType;
  readonly success: boolean;
  readonly error?: string;
  readonly duration: number;
  readonly timestamp: string;
}

export interface TransactionResult {
  readonly transactionId: string;
  readonly status: string;
  readonly stepsCompleted: number;
  readonly totalSteps: number;
  readonly duration: number;
}

// ============================================================================
// Singleton
// ============================================================================

let _instance: ComputerControlEngine | null = null;

export function getComputerControlEngine(): ComputerControlEngine {
  if (!_instance) _instance = new ComputerControlEngine();
  return _instance;
}
