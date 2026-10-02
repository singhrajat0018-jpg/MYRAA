// ============================================================================
// MYRAA DPI Calibration — Scale-aware coordinate conversion
// ============================================================================

import type { Vec2, BoundingBox, ScreenInfo, DPICalibration, CoordinateTransform } from './contracts';
import { toBoundingRect } from './contracts';

// ============================================================================
// DPI Manager
// ============================================================================

export class DPIManager {
  private calibrations: Map<number, DPICalibration> = new Map();
  private systemDpi = 96;
  private systemScaleFactor = 1.0;

  constructor() {
    this.detectSystemDPI();
  }

  // --- Detection ---

  private detectSystemDPI(): void {
    // Default Windows DPI is 96 (100% scaling)
    // This will be overridden by actual system detection
    this.systemDpi = 96;
    this.systemScaleFactor = 1.0;
  }

  // --- Calibration ---

  calibrateScreen(screen: ScreenInfo): DPICalibration {
    const scaleFactor = screen.scaleFactor;
    const systemDpi = this.systemDpi;
    const captureScale = this.estimateCaptureScale(screen);
    const mouseScale = this.estimateMouseScale(screen);

    const calibration: DPICalibration = {
      screenId: screen.screenId,
      systemDpi,
      scaleFactor,
      captureScale,
      mouseScale,
      calibrated: true,
      calibratedAt: new Date().toISOString(),
    };

    this.calibrations.set(screen.screenId, calibration);
    return calibration;
  }

  getCalibration(screenId: number): DPICalibration | undefined {
    return this.calibrations.get(screenId);
  }

  // --- Coordinate Conversion ---

  screenToMouse(point: Vec2, screenId: number): Vec2 {
    const cal = this.calibrations.get(screenId);
    if (!cal || !cal.calibrated) return point;

    return {
      x: Math.round(point.x * cal.mouseScale),
      y: Math.round(point.y * cal.mouseScale),
    };
  }

  mouseToScreen(point: Vec2, screenId: number): Vec2 {
    const cal = this.calibrations.get(screenId);
    if (!cal || !cal.calibrated) return point;

    return {
      x: Math.round(point.x / cal.mouseScale),
      y: Math.round(point.y / cal.mouseScale),
    };
  }

  screenToCapture(point: Vec2, screenId: number): Vec2 {
    const cal = this.calibrations.get(screenId);
    if (!cal || !cal.calibrated) return point;

    return {
      x: Math.round(point.x * cal.captureScale),
      y: Math.round(point.y * cal.captureScale),
    };
  }

  captureToScreen(point: Vec2, screenId: number): Vec2 {
    const cal = this.calibrations.get(screenId);
    if (!cal || !cal.calibrated) return point;

    return {
      x: Math.round(point.x / cal.captureScale),
      y: Math.round(point.y / cal.captureScale),
    };
  }

  // --- Window-Relative ---

  windowToScreen(point: Vec2, windowBounds: BoundingBox): Vec2 {
    return {
      x: windowBounds.x + point.x,
      y: windowBounds.y + point.y,
    };
  }

  screenToWindow(point: Vec2, windowBounds: BoundingBox): Vec2 {
    return {
      x: point.x - windowBounds.x,
      y: point.y - windowBounds.y,
    };
  }

  // --- Safe Point Selection ---

  safeClickPoint(bounds: BoundingBox, margin = 4): Vec2 {
    const rect = toBoundingRect(bounds);
    return {
      x: Math.max(bounds.x + margin, Math.min(rect.right - margin, rect.centerX)),
      y: Math.max(bounds.y + margin, Math.min(rect.bottom - margin, rect.centerY)),
    };
  }

  // --- Multi-Monitor ---

  screenContaining(point: Vec2, screens: readonly ScreenInfo[]): ScreenInfo | null {
    for (const screen of screens) {
      const r = toBoundingRect(screen.bounds);
      if (point.x >= screen.bounds.x && point.x <= r.right &&
          point.y >= screen.bounds.y && point.y <= r.bottom) {
        return screen;
      }
    }
    return null;
  }

  clampToScreens(point: Vec2, screens: readonly ScreenInfo[]): Vec2 {
    const screen = this.screenContaining(point, screens);
    if (screen) return point;

    // Find nearest screen
    let nearest: ScreenInfo | null = null;
    let minDist = Infinity;
    for (const s of screens) {
      const cx = s.bounds.x + s.bounds.width / 2;
      const cy = s.bounds.y + s.bounds.height / 2;
      const dist = Math.hypot(point.x - cx, point.y - cy);
      if (dist < minDist) { minDist = dist; nearest = s; }
    }
    if (!nearest) return point;

    return {
      x: Math.max(nearest.bounds.x, Math.min(point.x, nearest.bounds.x + nearest.bounds.width - 1)),
      y: Math.max(nearest.bounds.y, Math.min(point.y, nearest.bounds.y + nearest.bounds.height - 1)),
    };
  }

  // --- Helpers ---

  private estimateCaptureScale(screen: ScreenInfo): number {
    // MSS captures at physical pixel resolution
    // If screen resolution differs from DPI-scaled resolution, there's a capture ratio
    return screen.resolution.width / (screen.bounds.width || screen.resolution.width);
  }

  private estimateMouseScale(screen: ScreenInfo): number {
    // pyautogui uses virtual screen coordinates
    // At 100% DPI: 1:1
    // At 150% DPI: coordinates are scaled
    return screen.scaleFactor;
  }

  // --- Transform ---

  createTransform(params: {
    fromSpace: CoordinateTransform['fromSpace'];
    toSpace: CoordinateTransform['toSpace'];
    screenId: number;
    windowBounds?: BoundingBox;
  }): CoordinateTransform {
    const cal = this.calibrations.get(params.screenId);
    return {
      fromSpace: params.fromSpace,
      toSpace: params.toSpace,
      dpiScale: cal?.scaleFactor ?? 1.0,
      windowOffset: params.windowBounds ? { x: params.windowBounds.x, y: params.windowBounds.y } : { x: 0, y: 0 },
      screenOffset: { x: 0, y: 0 },
      monitorIndex: params.screenId,
    };
  }
}

// ============================================================================
// Singleton
// ============================================================================

let _instance: DPIManager | null = null;

export function getDPIManager(): DPIManager {
  if (!_instance) _instance = new DPIManager();
  return _instance;
}
