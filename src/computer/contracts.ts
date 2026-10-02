// ============================================================================
// MYRAA Computer Control Contracts — Types, Enums, Interfaces
// ============================================================================

// ============================================================================
// Coordinate Systems
// ============================================================================

export type CoordinateSpace = 'SCREEN_ABSOLUTE' | 'WINDOW_RELATIVE' | 'CLIENT_RELATIVE' | 'ELEMENT_RELATIVE';

export interface Vec2 {
  readonly x: number;
  readonly y: number;
}

export interface BoundingBox {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface BoundingRect extends BoundingBox {
  readonly right: number;
  readonly bottom: number;
  readonly top: number;
  readonly centerX: number;
  readonly centerY: number;
}

export function toBoundingRect(b: BoundingBox): BoundingRect {
  return {
    ...b,
    right: b.x + b.width,
    bottom: b.y + b.height,
    top: b.y,
    centerX: b.x + b.width / 2,
    centerY: b.y + b.height / 2,
  };
}

export function pointInRect(p: Vec2, b: BoundingBox): boolean {
  return p.x >= b.x && p.x <= b.x + b.width && p.y >= b.y && p.y <= b.y + b.height;
}

export function rectOverlap(a: BoundingBox, b: BoundingBox): boolean {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

export function iou(a: BoundingBox, b: BoundingBox): number {
  const interArea = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x))
    * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  const unionArea = a.width * a.height + b.width * b.height - interArea;
  return unionArea > 0 ? interArea / unionArea : 0;
}

// ============================================================================
// Screen Model
// ============================================================================

export interface ScreenInfo {
  readonly screenId: number;
  readonly bounds: BoundingBox;
  readonly resolution: { readonly width: number; readonly height: number };
  readonly scaleFactor: number;
  readonly dpi: number;
  readonly orientation: 'LANDSCAPE' | 'PORTRAIT' | 'SQUARE';
  readonly primary: boolean;
  readonly workArea: BoundingBox;
}

export interface ScreenState {
  readonly timestamp: string;
  readonly screens: readonly ScreenInfo[];
  readonly activeWindow: WindowInfo | null;
  readonly cursorPosition: Vec2;
  readonly keyboardFocus: KeyboardFocusInfo | null;
  readonly virtualScreenBounds: BoundingBox;
}

// ============================================================================
// DPI / Scaling
// ============================================================================

export interface DPICalibration {
  readonly screenId: number;
  readonly systemDpi: number;
  readonly scaleFactor: number;
  readonly captureScale: number;
  readonly mouseScale: number;
  readonly calibrated: boolean;
  readonly calibratedAt: string;
}

export interface CoordinateTransform {
  readonly fromSpace: CoordinateSpace;
  readonly toSpace: CoordinateSpace;
  readonly dpiScale: number;
  readonly windowOffset: Vec2;
  readonly screenOffset: Vec2;
  readonly monitorIndex: number;
}

// ============================================================================
// Window Model
// ============================================================================

export type WindowState = 'NORMAL' | 'MINIMIZED' | 'MAXIMIZED' | 'FULLSCREEN' | 'HIDDEN' | 'OFF_SCREEN';

export interface WindowInfo {
  readonly hwnd: number;
  readonly title: string;
  readonly processName: string;
  readonly processId: number;
  readonly bounds: BoundingBox;
  readonly state: WindowState;
  readonly visible: boolean;
  readonly focused: boolean;
  readonly zOrder: number;
}

// ============================================================================
// Application Model
// ============================================================================

export type AppReadiness = 'NOT_RUNNING' | 'STARTING' | 'READY' | 'UNRESPONSIVE' | 'UNKNOWN';

export interface ApplicationInfo {
  readonly name: string;
  readonly processName: string;
  readonly processId: number | null;
  readonly executablePath: string | null;
  readonly hwnd: number | null;
  readonly windowTitle: string | null;
  readonly readiness: AppReadiness;
  readonly hasAdapter: boolean;
}

// ============================================================================
// UI Target Model
// ============================================================================

export type UITargetType =
  | 'BUTTON' | 'TEXT' | 'INPUT' | 'CHECKBOX' | 'RADIO'
  | 'TAB' | 'MENU' | 'MENU_ITEM' | 'LINK' | 'ICON'
  | 'SLIDER' | 'SCROLL_REGION' | 'DIALOG' | 'WINDOW'
  | 'DROPDOWN' | 'TEXTAREA' | 'TOOLBAR' | 'SIDEBAR'
  | 'LIST_ITEM' | 'TABLE_CELL' | 'OTHER';

export type TargetSource = 'ACCESSIBILITY' | 'DOM' | 'VISION' | 'OCR' | 'WINDOW' | 'COORDINATE' | 'SEMANTIC';

export interface UITarget {
  readonly id: string;
  readonly type: UITargetType;
  readonly label: string;
  readonly bounds: BoundingBox;
  readonly clickable: boolean;
  readonly confidence: number;
  readonly source: TargetSource;
  readonly parent: string | null;
  readonly windowId: number | null;
  readonly timestamp: string;
  readonly observedAt: string;
  readonly screenStateHash: string;
  readonly text?: string;
  readonly role?: string;
  readonly enabled?: boolean;
  readonly visible?: boolean;
}

// ============================================================================
// Computer Actions
// ============================================================================

export type ActionType =
  | 'MOUSE_MOVE' | 'CLICK' | 'DOUBLE_CLICK' | 'RIGHT_CLICK'
  | 'MIDDLE_CLICK' | 'MOUSE_DOWN' | 'MOUSE_UP' | 'DRAG'
  | 'SCROLL' | 'HORIZONTAL_SCROLL'
  | 'KEY_PRESS' | 'HOTKEY' | 'TYPE_TEXT' | 'PASTE_TEXT'
  | 'FOCUS_WINDOW' | 'OPEN_APP' | 'CLOSE_APP'
  | 'MINIMIZE' | 'MAXIMIZE' | 'RESTORE'
  | 'WAIT' | 'OBSERVE' | 'SCROLL_INTO_VIEW';

export type ActionSource = 'USER_REQUEST' | 'PLANNER' | 'APPROVED_AUTOMATION' | 'RECOVERY';
export type ActionRisk = 'SAFE' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface ComputerAction {
  readonly actionId: string;
  readonly type: ActionType;
  readonly target?: UITarget;
  readonly coordinates?: Vec2;
  readonly coordinateSpace: CoordinateSpace;
  readonly windowId?: number;
  readonly windowBounds?: BoundingBox;
  readonly text?: string;
  readonly keys?: readonly string[];
  readonly scrollAmount?: number;
  readonly scrollDirection?: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT';
  readonly dragDestination?: Vec2;
  readonly confidence: number;
  readonly risk: ActionRisk;
  readonly source: ActionSource;
  readonly reversible: boolean;
  readonly expectedOutcome: string;
  readonly timeout: number;
  readonly timestamp: string;
  readonly dryRun: boolean;
}

// ============================================================================
// Action Verification
// ============================================================================

export type VerificationMethod = 'STATE_CHECK' | 'VISUAL' | 'ACCESSIBILITY' | 'DOM' | 'COORDINATE' | 'SCREEN_CHANGE';

export interface ActionVerification {
  readonly actionId: string;
  readonly method: VerificationMethod;
  readonly expected: string;
  readonly actual?: string;
  readonly passed: boolean;
  readonly confidence: number;
  readonly timestamp: string;
  readonly latencyMs: number;
}

// ============================================================================
// Action Transaction
// ============================================================================

export type TransactionStatus = 'PENDING' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'ROLLED_BACK' | 'CANCELLED';

export interface ActionStep {
  actionId: string;
  action: ComputerAction;
  preconditions: string[];
  postconditions: string[];
  verification?: ActionVerification;
  status: 'PENDING' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
  error?: string;
}

export interface ActionTransaction {
  transactionId: string;
  steps: ActionStep[];
  status: TransactionStatus;
  rollbackPlan: string[];
  createdAt: string;
  completedAt?: string;
}

// ============================================================================
// Failure Classification
// ============================================================================

export type ComputerFailureType =
  | 'TARGET_NOT_FOUND'
  | 'TARGET_AMBIGUOUS'
  | 'WRONG_WINDOW'
  | 'FOCUS_LOST'
  | 'UI_CHANGED'
  | 'APP_NOT_READY'
  | 'TIMEOUT'
  | 'INPUT_REJECTED'
  | 'ACCESSIBILITY_UNAVAILABLE'
  | 'VISUAL_LOW_CONFIDENCE'
  | 'USER_INTERRUPTED'
  | 'COORDINATE_INVALID'
  | 'PERMISSION_DENIED'
  | 'BACKEND_UNAVAILABLE';

// ============================================================================
// Recovery Strategy
// ============================================================================

export type RecoveryStrategy =
  | 'REOBSERVE_AND_RETRY'
  | 'REACQUIRE_TARGET'
  | 'ALTERNATE_METHOD'
  | 'REFOCUS_WINDOW'
  | 'WAIT_AND_RETRY'
  | 'ESCALATE_TO_USER'
  | 'ABORT';

export interface RecoveryPlan {
  readonly failureType: ComputerFailureType;
  readonly strategy: RecoveryStrategy;
  readonly maxRetries: number;
  readonly backoffMs: number;
  readonly fallbackStrategies: readonly RecoveryStrategy[];
}

// ============================================================================
// User Takeover
// ============================================================================

export type TakeoverPolicy = 'PAUSE' | 'CANCEL' | 'IGNORE';

export interface UserTakeoverState {
  readonly detected: boolean;
  readonly detectedAt: string;
  readonly mouseMoved: boolean;
  readonly keyTyped: boolean;
  readonly policy: TakeoverPolicy;
  readonly automationPaused: boolean;
}

// ============================================================================
// Input State (Safety)
// ============================================================================

export interface InputState {
  readonly heldKeys: readonly string[];
  readonly heldMouseButtons: readonly string[];
  readonly automationOwnsMouse: boolean;
  readonly automationOwnsKeyboard: boolean;
  readonly lastActionTimestamp: string;
}

// ============================================================================
// Computer Control Budget
// ============================================================================

export interface AutomationBudget {
  readonly maxActions: number;
  readonly maxDuration: number;
  readonly maxRetries: number;
  readonly maxScreenshots: number;
  readonly maxVisionCalls: number;
  readonly actionsUsed: number;
  readonly durationUsed: number;
  readonly retriesUsed: number;
  readonly screenshotsUsed: number;
  readonly visionCallsUsed: number;
  readonly withinBudget: boolean;
}

// ============================================================================
// Telemetry
// ============================================================================

export interface ComputerActionTelemetry {
  readonly actionId: string;
  readonly taskId?: string;
  readonly type: ActionType;
  readonly targetSource?: TargetSource;
  readonly confidence: number;
  readonly coordinates?: Vec2;
  readonly windowId?: number;
  readonly duration: number;
  readonly result: 'SUCCESS' | 'FAILED' | 'TIMEOUT' | 'CANCELLED';
  readonly verificationPassed?: boolean;
  readonly recoveryAttempted: boolean;
  readonly failureType?: ComputerFailureType;
  readonly timestamp: string;
}

// ============================================================================
// Environment Observation
// ============================================================================

export interface ComputerEnvironment {
  readonly timestamp: string;
  readonly screens: readonly ScreenInfo[];
  readonly activeWindow: WindowInfo | null;
  readonly windows: readonly WindowInfo[];
  readonly cursorPosition: Vec2;
  readonly keyboardFocus: KeyboardFocusInfo | null;
  readonly detectedTargets: readonly UITarget[];
  readonly stateHash: string;
}

export interface KeyboardFocusInfo {
  readonly hwnd: number;
  readonly title: string;
  readonly processName: string;
  readonly processId: number;
}

// ============================================================================
// Default Constants
// ============================================================================

export const DEFAULT_AUTOMATION_BUDGET: AutomationBudget = {
  maxActions: 50,
  maxDuration: 120_000,
  maxRetries: 3,
  maxScreenshots: 20,
  maxVisionCalls: 10,
  actionsUsed: 0,
  durationUsed: 0,
  retriesUsed: 0,
  screenshotsUsed: 0,
  visionCallsUsed: 0,
  withinBudget: true,
};

export const DEFAULT_RECOVERY_PLAN: RecoveryPlan = {
  failureType: 'TARGET_NOT_FOUND',
  strategy: 'REOBSERVE_AND_RETRY',
  maxRetries: 3,
  backoffMs: 500,
  fallbackStrategies: ['REACQUIRE_TARGET', 'ALTERNATE_METHOD', 'ESCALATE_TO_USER'],
};

export const CLICK_MARGIN = 4;
export const TARGET_STALENESS_MS = 30_000;
export const AMBIGUITY_THRESHOLD = 0.3;
export const CONFIDENCE_HIGH = 0.85;
export const CONFIDENCE_MEDIUM = 0.6;
export const CONFIDENCE_LOW = 0.4;
