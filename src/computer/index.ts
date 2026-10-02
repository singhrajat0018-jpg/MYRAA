// ============================================================================
// MYRAA Computer Control — Public API Barrel Export
// ============================================================================

export type {
  Vec2, BoundingBox, BoundingRect, CoordinateSpace, CoordinateTransform,
  ScreenInfo, ScreenState, WindowInfo, WindowState, KeyboardFocusInfo,
  ApplicationInfo, AppReadiness,
  UITarget, UITargetType, TargetSource,
  ComputerAction, ActionType, ActionSource, ActionRisk,
  ActionVerification, VerificationMethod,
  ActionStep, ActionTransaction, TransactionStatus,
  AutomationBudget, ComputerActionTelemetry,
  ComputerEnvironment, DPICalibration,
  UserTakeoverState, InputState,
  ComputerFailureType, RecoveryStrategy, RecoveryPlan,
  TakeoverPolicy,
} from './contracts';

export {
  toBoundingRect, pointInRect, rectOverlap, iou,
  DEFAULT_AUTOMATION_BUDGET, DEFAULT_RECOVERY_PLAN,
  CLICK_MARGIN, TARGET_STALENESS_MS,
  AMBIGUITY_THRESHOLD, CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW,
} from './contracts';

export { DPIManager, getDPIManager } from './dpi';
export { MouseEngine } from './mouse_engine';
export { KeyboardEngine } from './keyboard_engine';
export { ScrollDragEngine } from './scroll_drag';
export { WindowControl, ApplicationControl } from './window_app_control';
export { VisualTargeter } from './visual_targeting';
export { TargetResolver } from './target_resolution';
export { PolicyEngine } from './policy';
export type { PolicyRule, PolicyContext, PolicyDecision } from './policy';
export { TransactionManager } from './transactions';
export { LoopDetector } from './loop_detection';
export type { LoopSignature, StuckState } from './loop_detection';
export { ComputerControlEngine, getComputerControlEngine } from './engine';
export type { EngineState, ComputerActionResult, TransactionResult } from './engine';
