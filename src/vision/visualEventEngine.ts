// ============================================================================
// MYRAA Visual Event Engine — Detects Semantic Desktop Events Over Time
// ============================================================================

import type { VisualEvent, VisualEventType, ActiveWindowInfo, OcrBlock } from './contracts';

export class VisualEventEngine {
  /**
   * Compare previous observation state to current state and emit structured visual events.
   */
  public detectEvents(
    prev: { activeWindow: ActiveWindowInfo; textContent: string; timestamp: number } | null,
    curr: { activeWindow: ActiveWindowInfo; textContent: string; timestamp: number; ocrBlocks: OcrBlock[] }
  ): VisualEvent[] {
    const events: VisualEvent[] = [];
    const now = curr.timestamp || Date.now();

    if (!prev) {
      events.push({
        id: `ev-init-${now}`,
        type: 'WINDOW_FOCUSED',
        timestamp: now,
        confidence: 0.98,
        significance: 0.6,
        description: `Active window: ${curr.activeWindow.application} — "${curr.activeWindow.title}"`,
        source: 'WINDOWS_API',
        newState: curr.activeWindow.application,
      });
      return events;
    }

    const prevApp = prev.activeWindow.application;
    const currApp = curr.activeWindow.application;
    const prevTitle = prev.activeWindow.title;
    const currTitle = curr.activeWindow.title;

    // 1. Application transition
    if (prevApp !== currApp) {
      events.push({
        id: `ev-app-${now}`,
        type: 'APPLICATION_STARTED',
        timestamp: now,
        confidence: 0.99,
        significance: 0.75,
        description: `Switched from ${prevApp} to ${currApp}`,
        source: 'WINDOWS_API',
        previousState: prevApp,
        newState: currApp,
      });
    } else if (prevTitle !== currTitle) {
      // 2. Window title or tab transition
      const isBrowser = /chrome|firefox|edge|brave|browser/i.test(currApp);
      events.push({
        id: `ev-win-${now}`,
        type: isBrowser ? 'PAGE_CHANGED' : 'WINDOW_CHANGED',
        timestamp: now,
        confidence: 0.95,
        significance: isBrowser ? 0.65 : 0.5,
        description: `Window title updated to: "${currTitle}"`,
        source: 'WINDOWS_API',
        previousState: prevTitle,
        newState: currTitle,
      });
    }

    // 3. Dialog appearance
    const isDialogNow = /dialog|confirm|security|uac|alert|warning/i.test(currTitle);
    const wasDialogPrev = /dialog|confirm|security|uac|alert|warning/i.test(prevTitle);
    if (isDialogNow && !wasDialogPrev) {
      events.push({
        id: `ev-dlg-${now}`,
        type: 'DIALOG_APPEARED',
        timestamp: now,
        confidence: 0.96,
        significance: 0.9, // High significance
        description: `Dialog appeared: "${currTitle}"`,
        source: 'WINDOWS_API',
      });
    }

    // 4. Terminal output change
    const isTerminal = /terminal|powershell|cmd|bash|wsl/i.test(currApp + ' ' + currTitle);
    if (isTerminal && prev.textContent !== curr.textContent) {
      const isBuildComplete = /build (succeeded|completed|failed|passed)/i.test(curr.textContent);
      events.push({
        id: `ev-term-${now}`,
        type: 'TERMINAL_OUTPUT_CHANGED',
        timestamp: now,
        confidence: 0.95,
        significance: isBuildComplete ? 0.85 : 0.6,
        description: isBuildComplete ? 'Terminal build completed' : 'New terminal output detected',
        source: 'OCR',
      });
    }

    // 5. Error detection
    const errorMatch = curr.ocrBlocks.find(b =>
      /(build failed|fatal error|syntaxerror|typeerror|panic|uncaught exception)/i.test(b.text)
    );
    if (errorMatch) {
      events.push({
        id: `ev-err-${now}`,
        type: 'ERROR_APPEARED',
        timestamp: now,
        confidence: 0.94,
        significance: 0.95, // Critical significance
        description: `Error on screen: ${errorMatch.text.slice(0, 100)}`,
        source: 'OCR',
        affectedRegion: errorMatch.bbox,
      });
    }

    // 6. Generic text change if no other specific events
    if (events.length === 0 && prev.textContent !== curr.textContent) {
      events.push({
        id: `ev-text-${now}`,
        type: 'TEXT_CHANGED',
        timestamp: now,
        confidence: 0.85,
        significance: 0.3,
        description: 'On-screen text changed',
        source: 'OCR',
      });
    }

    // 7. Idle detection
    if (events.length === 0) {
      events.push({
        id: `ev-idle-${now}`,
        type: 'USER_IDLE_VISUALLY',
        timestamp: now,
        confidence: 0.99,
        significance: 0.05, // Negligible significance
        description: 'Screen unchanged',
        source: 'FRAME_DIFFERENCE',
      });
    }

    return events;
  }
}
