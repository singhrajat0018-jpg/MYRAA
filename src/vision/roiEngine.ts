// ============================================================================
// MYRAA Region-Of-Interest (ROI) Engine
// ============================================================================

import type { ScreenRegion, ActiveWindowInfo, OcrBlock } from './contracts';

export type ROIType =
  | 'ACTIVE_WINDOW'
  | 'TERMINAL'
  | 'DIALOG'
  | 'NOTIFICATION'
  | 'TEXT_CLUSTER'
  | 'FULL_SCREEN';

export interface RegionOfInterest {
  id: string;
  type: ROIType;
  region: ScreenRegion;
  priority: number; // 1 (highest) to 5 (lowest)
  description: string;
}

export class ROIEngine {
  /**
   * Determine primary and secondary Regions of Interest from window and OCR hints.
   */
  public extractROIs(
    activeWindow: ActiveWindowInfo,
    ocrBlocks: OcrBlock[],
    screenWidth = 1920,
    screenHeight = 1080
  ): RegionOfInterest[] {
    const rois: RegionOfInterest[] = [];

    // 1. Active Window ROI
    if (activeWindow.bounds) {
      rois.push({
        id: 'roi-active-window',
        type: 'ACTIVE_WINDOW',
        region: activeWindow.bounds,
        priority: 1,
        description: `Active Application: ${activeWindow.application}`,
      });
    } else {
      // Default center viewport window approximation
      rois.push({
        id: 'roi-active-window-default',
        type: 'ACTIVE_WINDOW',
        region: { x: 100, y: 50, width: screenWidth - 200, height: screenHeight - 100 },
        priority: 1,
        description: activeWindow.application,
      });
    }

    // 2. Dialog ROI check (small centered window or dialog title)
    const isDialog = /dialog|confirm|alert|prompt|security|uac|error/i.test(activeWindow.title);
    if (isDialog) {
      rois.push({
        id: 'roi-dialog',
        type: 'DIALOG',
        region: {
          x: Math.round(screenWidth * 0.25),
          y: Math.round(screenHeight * 0.25),
          width: Math.round(screenWidth * 0.5),
          height: Math.round(screenHeight * 0.5),
        },
        priority: 1,
        description: `Dialog: ${activeWindow.title}`,
      });
    }

    // 3. Terminal ROI check
    const isTerminal = /terminal|powershell|cmd|bash|wsl|alacritty/i.test(activeWindow.application + ' ' + activeWindow.title);
    if (isTerminal) {
      rois.push({
        id: 'roi-terminal',
        type: 'TERMINAL',
        region: { x: 50, y: 100, width: screenWidth - 100, height: screenHeight - 150 },
        priority: 1,
        description: 'Terminal Console Area',
      });
    }

    // 4. Text clusters with errors
    const errorBlock = ocrBlocks.find(b => /(error|failed|exception|syntaxerror)/i.test(b.text));
    if (errorBlock) {
      rois.push({
        id: 'roi-error-cluster',
        type: 'NOTIFICATION',
        region: {
          x: Math.max(0, errorBlock.bbox.x - 20),
          y: Math.max(0, errorBlock.bbox.y - 20),
          width: Math.min(screenWidth, errorBlock.bbox.width + 40),
          height: Math.min(screenHeight, errorBlock.bbox.height + 40),
        },
        priority: 1,
        description: `Error Detected: ${errorBlock.text.slice(0, 50)}`,
      });
    }

    // 5. Full Screen fallback
    rois.push({
      id: 'roi-fullscreen',
      type: 'FULL_SCREEN',
      region: { x: 0, y: 0, width: screenWidth, height: screenHeight },
      priority: 5,
      description: 'Full Display View',
    });

    return rois.sort((a, b) => a.priority - b.priority);
  }
}
