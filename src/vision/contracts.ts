// ============================================================================
// MYRAA Vision Core — Contracts & Types
// ============================================================================

// ============================================================================
// Branded IDs
// ============================================================================

export type MonitorId = string & { readonly __brand: unique symbol };
export type ObservationId = string & { readonly __brand: unique symbol };
export type ElementId = string & { readonly __brand: unique symbol };
export type RegionId = string & { readonly __brand: unique symbol };

export function monitorId(id: string): MonitorId { return id as MonitorId; }
export function observationId(id: string): ObservationId { return id as ObservationId; }
export function elementId(id: string): ElementId { return id as ElementId; }
export function regionId(id: string): RegionId { return id as RegionId; }

// ============================================================================
// Geometry Primitives
// ============================================================================

export interface Bounds {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface Point {
  readonly x: number;
  readonly y: number;
}

// ============================================================================
// Monitor Model
// ============================================================================

export interface MonitorInfo {
  readonly id: MonitorId;
  readonly index: number;
  readonly bounds: Bounds;
  readonly dpiScale: number;
  readonly isPrimary: boolean;
  readonly orientation: 'landscape' | 'portrait';
  readonly colorDepth: number;
}

// ============================================================================
// Screen Capture
// ============================================================================

export type CaptureFormat = 'png' | 'jpeg';

export interface ScreenCapture {
  readonly captureId: string;
  readonly timestamp: string;
  readonly monitorId: MonitorId;
  readonly bounds: Bounds;
  readonly dpiScale: number;
  readonly imageData: string;
  readonly format: CaptureFormat;
  readonly width: number;
  readonly height: number;
}

export interface CaptureRegion {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

// ============================================================================
// OCR — Spatial Text Recognition
// ============================================================================

export interface OcrWord {
  readonly text: string;
  readonly bounds: Bounds;
  readonly confidence: number;
}

export interface OcrLine {
  readonly text: string;
  readonly bounds: Bounds;
  readonly confidence: number;
  readonly words: readonly OcrWord[];
}

export interface OcrBlock {
  readonly blockId: string;
  readonly text: string;
  readonly bounds: Bounds;
  readonly confidence: number;
  readonly lines: readonly OcrLine[];
  readonly readingOrder: number;
}

// ============================================================================
// Visual Elements — Detected UI Components
// ============================================================================

export type VisualElementType =
  | 'BUTTON' | 'TEXT_FIELD' | 'LINK' | 'TAB' | 'DROPDOWN'
  | 'CHECKBOX' | 'RADIO' | 'DIALOG' | 'MENU' | 'NOTIFICATION'
  | 'TABLE' | 'LIST_ROW' | 'CARD' | 'IMAGE' | 'ICON'
  | 'TOOLBAR' | 'WINDOW' | 'PANEL' | 'SCROLLBAR' | 'TEXT_BLOCK'
  | 'COMBOBOX' | 'SLIDER' | 'TOGGLE' | 'PROGRESS' | 'TREE'
  | 'UNKNOWN';

export interface VisualElement {
  readonly elementId: ElementId;
  readonly type: VisualElementType;
  readonly bounds: Bounds;
  readonly text: string;
  readonly confidence: number;
  readonly parentElementId: ElementId | null;
  readonly zOrder: number;
  readonly isVisible: boolean;
  readonly isEnabled: boolean;
  readonly isFocused: boolean;
  readonly isSelected: boolean;
  readonly isClickable: boolean;
  readonly accessibilityRole: string | null;
  readonly accessibilityLabel: string | null;
  readonly className: string | null;
}

// ============================================================================
// Visual Scene — Structured Screen Representation
// ============================================================================

export interface VisualWindow {
  readonly windowId: string;
  readonly title: string;
  readonly processName: string;
  readonly bounds: Bounds;
  readonly isFocused: boolean;
  readonly isMinimized: boolean;
  readonly isMaximized: boolean;
  readonly zIndex: number;
}

export type RegionPurpose =
  | 'content' | 'navigation' | 'toolbar' | 'sidebar'
  | 'statusbar' | 'dialog' | 'overlay';

export interface VisualRegion {
  readonly regionId: RegionId;
  readonly label: string;
  readonly bounds: Bounds;
  readonly elementIds: readonly ElementId[];
  readonly purpose: RegionPurpose;
}

export type NotificationSeverity = 'info' | 'warning' | 'error' | 'success';

export interface VisualNotification {
  readonly notificationId: string;
  readonly text: string;
  readonly bounds: Bounds;
  readonly severity: NotificationSeverity;
  readonly source: string;
  readonly timestamp: string;
}

export interface VisualDialog {
  readonly dialogId: string;
  readonly title: string;
  readonly bounds: Bounds;
  readonly content: string;
  readonly buttons: readonly VisualElement[];
  readonly isModal: boolean;
}

export interface VisualMenuItem {
  readonly label: string;
  readonly bounds: Bounds;
  readonly isEnabled: boolean;
  readonly isChecked: boolean;
  readonly shortcut: string | null;
  readonly subItems: readonly VisualMenuItem[];
}

export interface VisualMenu {
  readonly menuId: string;
  readonly bounds: Bounds;
  readonly items: readonly VisualMenuItem[];
  readonly depth: number;
}

export interface VisualTable {
  readonly tableId: string;
  readonly bounds: Bounds;
  readonly headers: readonly string[];
  readonly rows: readonly (readonly string[])[];
  readonly columnCount: number;
  readonly rowCount: number;
}

export interface VisualScene {
  readonly sceneId: ObservationId;
  readonly timestamp: string;
  readonly captureId: string;
  readonly monitorId: MonitorId;
  readonly bounds: Bounds;
  readonly dpiScale: number;
  readonly activeWindow: VisualWindow | null;
  readonly windows: readonly VisualWindow[];
  readonly elements: readonly VisualElement[];
  readonly ocrBlocks: readonly OcrBlock[];
  readonly textContent: string;
  readonly regions: readonly VisualRegion[];
  readonly notifications: readonly VisualNotification[];
  readonly dialogs: readonly VisualDialog[];
  readonly menus: readonly VisualMenu[];
  readonly tables: readonly VisualTable[];
  readonly confidence: number;
}

// ============================================================================
// Visual Change Detection
// ============================================================================

export type ChangeType =
  | 'ADDED' | 'REMOVED' | 'MOVED' | 'CHANGED'
  | 'FOCUSED' | 'UNFOCUSED' | 'OPENED' | 'CLOSED'
  | 'NAVIGATED' | 'SELECTED' | 'DESELECTED';

export type ChangeSignificance = 'trivial' | 'minor' | 'moderate' | 'major' | 'critical';

export interface VisualChange {
  readonly changeId: string;
  readonly type: ChangeType;
  readonly elementType: VisualElementType;
  readonly elementId: ElementId | null;
  readonly previousState: Partial<VisualElement> | null;
  readonly currentState: Partial<VisualElement> | null;
  readonly timestamp: string;
  readonly significance: ChangeSignificance;
}

export interface SceneDiff {
  readonly diffId: string;
  readonly fromSceneId: ObservationId;
  readonly toSceneId: ObservationId;
  readonly timestamp: string;
  readonly changes: readonly VisualChange[];
  readonly windowChanged: boolean;
  readonly navigationOccurred: boolean;
  readonly dialogOpened: boolean;
  readonly dialogClosed: boolean;
  readonly focusChanged: boolean;
  readonly layoutChanged: boolean;
  readonly changeCount: number;
}

// ============================================================================
// Vision Context — Agent-Facing Summary
// ============================================================================

export interface VisionContext {
  readonly timestamp: string;
  readonly sceneId: ObservationId;
  readonly activeApplication: string;
  readonly activeWindowTitle: string;
  readonly screenText: string;
  readonly keyElements: readonly VisualElement[];
  readonly importantControls: readonly VisualElement[];
  readonly currentDialog: VisualDialog | null;
  readonly notifications: readonly VisualNotification[];
  readonly confidence: number;
  readonly monitorId: MonitorId;
  readonly dpiScale: number;
  readonly recentChanges: readonly VisualChange[];
}

// ============================================================================
// Target Resolution — Natural Language → Screen Location
// ============================================================================

export type CoordinateSpace = 'screen' | 'window' | 'element';
export type ResolutionMethod = 'accessibility' | 'ocr' | 'visual' | 'spatial' | 'ordinal' | 'hybrid';

export interface VisualTarget {
  readonly targetId: string;
  readonly description: string;
  readonly element: VisualElement | null;
  readonly bounds: Bounds;
  readonly center: Point;
  readonly monitorId: MonitorId;
  readonly coordinateSpace: CoordinateSpace;
  readonly confidence: number;
  readonly resolutionMethod: ResolutionMethod;
  readonly observationId: ObservationId;
}

export interface TargetResolutionRequest {
  readonly query: string;
  readonly context: VisionContext;
  readonly preferredMonitor: MonitorId | null;
  readonly maxCandidates: number;
  readonly minConfidence: number;
}

export type AmbiguityLevel = 'none' | 'low' | 'medium' | 'high';

export interface TargetResolutionResult {
  readonly primary: VisualTarget | null;
  readonly candidates: readonly VisualTarget[];
  readonly confidence: number;
  readonly ambiguity: AmbiguityLevel;
  readonly suggestion: string | null;
}

// ============================================================================
// Vision Engine Configuration
// ============================================================================

export interface VisionConfig {
  readonly captureInterval: number;
  readonly ocrEnabled: boolean;
  readonly layoutAnalysisEnabled: boolean;
  readonly elementDetectionEnabled: boolean;
  readonly changeTrackingEnabled: boolean;
  readonly maxSceneHistory: number;
  readonly cacheSize: number;
  readonly maxConcurrentCaptures: number;
  readonly regionFirstAnalysis: boolean;
  readonly unchangedScreenDetection: boolean;
  readonly debounceMs: number;
}

// ============================================================================
// Vision Provider — External Vision API Bridge
// ============================================================================

export interface VisionProvider {
  readonly providerId: string;
  readonly name: string;
  analyzeImage(base64: string, prompt: string): Promise<string>;
  isAvailable(): boolean;
}

// ============================================================================
// Vision Events
// ============================================================================

export type VisionEventType =
  | 'SCENE_READY'
  | 'CHANGE_DETECTED'
  | 'TARGET_RESOLVED'
  | 'CAPTURE_STARTED'
  | 'CAPTURE_COMPLETED'
  | 'OCR_COMPLETED'
  | 'ENGINE_STARTED'
  | 'ENGINE_STOPPED'
  | 'ENGINE_ERROR';

export interface VisionEvent {
  readonly type: VisionEventType;
  readonly timestamp: string;
  readonly data: Record<string, unknown>;
}

export type VisionEventListener = (event: VisionEvent) => void;

// ============================================================================
// Security Constraints
// ============================================================================

export interface ImageSecurityPolicy {
  readonly maxImageSizeBytes: number;
  readonly maxImageWidth: number;
  readonly maxImageHeight: number;
  readonly allowedFormats: readonly CaptureFormat[];
  readonly sanitizeBeforeLogging: boolean;
  readonly rateLimitPerMinute: number;
}

// ============================================================================
// Cache Entry
// ============================================================================

export interface CacheEntry<T> {
  readonly value: T;
  readonly createdAt: number;
  readonly accessCount: number;
  readonly lastAccessedAt: number;
}

// ============================================================================
// Constants
// ============================================================================

export const DEFAULT_VISION_CONFIG: VisionConfig = {
  captureInterval: 1000,
  ocrEnabled: true,
  layoutAnalysisEnabled: true,
  elementDetectionEnabled: true,
  changeTrackingEnabled: true,
  maxSceneHistory: 30,
  cacheSize: 64,
  maxConcurrentCaptures: 2,
  regionFirstAnalysis: false,
  unchangedScreenDetection: true,
  debounceMs: 150,
};

export const DEFAULT_SECURITY_POLICY: ImageSecurityPolicy = {
  maxImageSizeBytes: 10 * 1024 * 1024,
  maxImageWidth: 7680,
  maxImageHeight: 4320,
  allowedFormats: ['png', 'jpeg'],
  sanitizeBeforeLogging: true,
  rateLimitPerMinute: 60,
};

export const CONFIDENCE_HIGH = 0.85;
export const CONFIDENCE_MEDIUM = 0.6;
export const CONFIDENCE_LOW = 0.4;
export const CONFIDENCE_MINIMUM = 0.2;

export const OCR_BLOCK_SEPARATOR = '\n';
export const OCR_LINE_SEPARATOR = ' ';
export const OCR_WORD_SEPARATOR = ' ';

export const SIGNIFICANCE_WEIGHTS: Record<ChangeSignificance, number> = {
  trivial: 0.1,
  minor: 0.3,
  moderate: 0.5,
  major: 0.8,
  critical: 1.0,
};

export const WINDOW_TITLE_MAX_LENGTH = 256;
export const SCREEN_TEXT_MAX_LENGTH = 4096;
export const ELEMENT_TEXT_MAX_LENGTH = 512;
