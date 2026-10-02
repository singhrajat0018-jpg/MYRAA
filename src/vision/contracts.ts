// ============================================================================
// MYRAA Vision & Vision Intelligence — Typed Contracts
// ============================================================================

export type MonitorId = string;

export function monitorId(id: string): MonitorId {
  return id || 'primary';
}

export interface ScreenRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type UIElementType =
  | 'button'
  | 'input'
  | 'tab'
  | 'menu'
  | 'dialog'
  | 'notification'
  | 'panel'
  | 'terminal'
  | 'code_editor'
  | 'text'
  | 'unknown';

export interface UIElement {
  id: string;
  type: UIElementType;
  text?: string;
  box: ScreenRegion;
  confidence: number;
  interactive: boolean;
  role?: string;
}

export interface OcrBlock {
  text: string;
  confidence: number;
  bbox: ScreenRegion;
  line?: number;
  block?: number;
  language?: string;
}

export interface ActiveWindowInfo {
  application: string;
  title: string;
  bounds?: ScreenRegion;
  active: boolean;
  pid?: number;
  hwnd?: number;
}

export interface VisualDelta {
  changed: boolean;
  magnitude: number; // 0.0 to 1.0 fraction of screen change
  regions: ScreenRegion[];
  likelyEvent?: string;
  confidence: number;
}

export type VisualEventType =
  | 'WINDOW_OPENED'
  | 'WINDOW_CLOSED'
  | 'WINDOW_FOCUSED'
  | 'WINDOW_CHANGED'
  | 'DIALOG_APPEARED'
  | 'ERROR_APPEARED'
  | 'TEXT_CHANGED'
  | 'BUTTON_CHANGED'
  | 'PAGE_CHANGED'
  | 'TERMINAL_OUTPUT_CHANGED'
  | 'APPLICATION_STARTED'
  | 'APPLICATION_FINISHED'
  | 'NOTIFICATION_APPEARED'
  | 'SCREEN_LAYOUT_CHANGED'
  | 'SIGNIFICANT_VISUAL_CHANGE'
  | 'USER_IDLE_VISUALLY'
  | 'UNKNOWN_VISUAL_CHANGE';

export type PerceptionSource =
  | 'WINDOWS_API'
  | 'OCR'
  | 'ACCESSIBILITY'
  | 'FRAME_DIFFERENCE'
  | 'VISION_MODEL'
  | 'USER'
  | 'TOOL_RESULT';

export interface VisualEvent {
  id: string;
  type: VisualEventType;
  timestamp: number;
  confidence: number;
  significance: number; // 0.0 (ignorable) to 1.0 (critical action required)
  description: string;
  affectedRegion?: ScreenRegion;
  source: PerceptionSource;
  previousState?: string;
  newState?: string;
  metadata?: Record<string, unknown>;
}

export interface VisionEvidence {
  claim: string;
  source: PerceptionSource;
  region?: ScreenRegion;
  timestamp: number;
  text?: string;
  confidence: number;
}

export interface ObservedScene {
  sceneId: string;
  timestamp: number;
  monitorId: MonitorId;
  width: number;
  height: number;
  activeWindow: ActiveWindowInfo;
  elements: UIElement[];
  ocrBlocks: OcrBlock[];
  textContent: string;
  delta?: VisualDelta;
  events: VisualEvent[];
  significance: number;
  confidence: number;
  provenance: PerceptionSource;
  untrustedScreenData: boolean; // Screen text is marked untrusted data (prompt-injection defense)
  hasError: boolean;
  errorText?: string;
  evidence?: VisionEvidence[];
}

export type VisionStatus =
  | 'OFFLINE'
  | 'INITIALIZING'
  | 'CAPTURING'
  | 'ANALYZING'
  | 'HEALTHY'
  | 'DEGRADED'
  | 'PAUSED'
  | 'FAILED'
  | 'RECOVERING';

export interface VisionTelemetry {
  status: VisionStatus;
  isCapturing: boolean;
  totalObservations: number;
  framesCaptured: number;
  framesSkipped: number;
  framesDropped: number;
  significantEventsEmitted: number;
  avgCaptureLatencyMs: number;
  avgAnalysisLatencyMs: number;
  avgOcrLatencyMs: number;
  lastObservationTime: number;
  lastChangeTime: number;
  consecutiveNoChangeCount: number;
  desktopAgentConnected: boolean;
}

export interface FastCoreVisualPerception {
  activeApplication: string;
  activeWindowTitle: string;
  visibleEvent?: string;
  resultSummary?: string;
  confidence: number;
  significance: number;
  hasError: boolean;
  errorText?: string;
  recentHistorySummary: string;
  untrustedDataWarning: boolean;
  evidence: VisionEvidence[];
}
