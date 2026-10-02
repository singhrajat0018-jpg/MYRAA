// ============================================================================
// MYRAA Vision Core — Scene Builder
// ============================================================================

import type {
  VisualScene, ObservationId, ScreenCapture, OcrBlock, VisualElement,
  VisualWindow, VisualRegion, VisualNotification, VisualDialog,
  VisualMenu, VisualTable, VisualMenuItem, MonitorId, Bounds,
  VisualElementType, ElementId, RegionId, RegionPurpose,
} from './contracts';
import {
  observationId, elementId, regionId,
  OCR_BLOCK_SEPARATOR, CONFIDENCE_MEDIUM,
} from './contracts';

// ============================================================================
// Scene Builder
// ============================================================================

export class SceneBuilder {
  private elementCounter = 0;
  private regionCounter = 0;

  reset(): void {
    this.elementCounter = 0;
    this.regionCounter = 0;
  }

  buildScene(params: {
    capture: ScreenCapture;
    ocrBlocks: readonly OcrBlock[];
    elements?: readonly VisualElement[];
    windows?: readonly VisualWindow[];
    previousScene?: VisualScene;
  }): VisualScene {
    const { capture, ocrBlocks } = params;
    const elements = params.elements ?? this.inferElementsFromOcr(ocrBlocks);
    const windows = params.windows ?? [];
    const activeWindow = windows.find(w => w.isFocused) ?? null;

    const textContent = this.extractTextContent(ocrBlocks);
    const regions = this.detectRegions(elements, capture.bounds);
    const notifications = this.detectNotifications(elements);
    const dialogs = this.detectDialogs(elements, windows);
    const menus = this.detectMenus(elements);
    const tables = this.detectTables(elements);
    const confidence = this.computeSceneConfidence(ocrBlocks, elements, capture);

    return {
      sceneId: observationId(`scene-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`),
      timestamp: capture.timestamp,
      captureId: capture.captureId,
      monitorId: capture.monitorId,
      bounds: capture.bounds,
      dpiScale: capture.dpiScale,
      activeWindow,
      windows,
      elements,
      ocrBlocks,
      textContent,
      regions,
      notifications,
      dialogs,
      menus,
      tables,
      confidence,
    };
  }

  // --- Element Inference from OCR ---

  private inferElementsFromOcr(blocks: readonly OcrBlock[]): readonly VisualElement[] {
    const elements: VisualElement[] = [];

    for (const block of blocks) {
      const inferredType = this.inferElementType(block);
      elements.push({
        elementId: elementId(`el-${++this.elementCounter}`),
        type: inferredType,
        bounds: block.bounds,
        text: block.text,
        confidence: block.confidence,
        parentElementId: null,
        zOrder: 0,
        isVisible: true,
        isEnabled: true,
        isFocused: false,
        isSelected: false,
        isClickable: this.isClickableType(inferredType),
        accessibilityRole: this.typeToA11yRole(inferredType),
        accessibilityLabel: block.text,
        className: null,
      });
    }

    return elements;
  }

  private inferElementType(block: OcrBlock): VisualElementType {
    const text = block.text.toLowerCase().trim();

    if (text.includes('button') || text.match(/^(ok|cancel|yes|no|submit|save|close)$/)) {
      return 'BUTTON';
    }
    if (text.includes('search') || text.includes('find')) {
      return 'TEXT_FIELD';
    }
    if (text.includes('menu') || text.includes('file') || text.includes('edit')) {
      return 'MENU';
    }
    if (text.includes('tab')) {
      return 'TAB';
    }
    if (text.includes('checkbox') || text.includes('check')) {
      return 'CHECKBOX';
    }
    if (text.includes('dropdown') || text.includes('select')) {
      return 'DROPDOWN';
    }
    if (text.includes('link') || text.includes('http')) {
      return 'LINK';
    }
    if (text.includes('error') || text.includes('warning') || text.includes('alert')) {
      return 'NOTIFICATION';
    }
    if (text.includes('table') || text.includes('row') || text.includes('column')) {
      return 'TABLE';
    }

    return 'TEXT_BLOCK';
  }

  private isClickableType(type: VisualElementType): boolean {
    const clickable: VisualElementType[] = [
      'BUTTON', 'LINK', 'TAB', 'CHECKBOX', 'RADIO',
      'DROPDOWN', 'COMBOBOX', 'TOGGLE', 'MENU', 'LIST_ROW',
    ];
    return clickable.includes(type);
  }

  private typeToA11yRole(type: VisualElementType): string | null {
    const roleMap: Record<VisualElementType, string> = {
      BUTTON: 'button',
      TEXT_FIELD: 'textbox',
      LINK: 'link',
      TAB: 'tab',
      DROPDOWN: 'combobox',
      CHECKBOX: 'checkbox',
      RADIO: 'radio',
      DIALOG: 'dialog',
      MENU: 'menu',
      NOTIFICATION: 'alert',
      TABLE: 'table',
      LIST_ROW: 'listitem',
      CARD: 'article',
      IMAGE: 'img',
      ICON: 'img',
      TOOLBAR: 'toolbar',
      WINDOW: 'window',
      PANEL: 'region',
      SCROLLBAR: 'scrollbar',
      TEXT_BLOCK: 'text',
      COMBOBOX: 'combobox',
      SLIDER: 'slider',
      TOGGLE: 'switch',
      PROGRESS: 'progressbar',
      TREE: 'tree',
      UNKNOWN: '',
    };
    return roleMap[type] ?? null;
  }

  // --- Region Detection ---

  private detectRegions(
    elements: readonly VisualElement[],
    screenBounds: Bounds,
  ): readonly VisualRegion[] {
    const regions: VisualRegion[] = [];

    const toolbars = elements.filter(e =>
      e.type === 'TOOLBAR' || (e.bounds.height < 60 && e.bounds.y < 80)
    );
    if (toolbars.length > 0) {
      regions.push(this.buildRegion('Toolbar', 'toolbar', toolbars, screenBounds));
    }

    const sidebars = elements.filter(e =>
      e.type === 'PANEL' && e.bounds.width < 300 && e.bounds.x < screenBounds.width / 3
    );
    if (sidebars.length > 0) {
      regions.push(this.buildRegion('Sidebar', 'sidebar', sidebars, screenBounds));
    }

    const statusBars = elements.filter(e =>
      e.bounds.y > screenBounds.height - 40 && e.bounds.height < 40
    );
    if (statusBars.length > 0) {
      regions.push(this.buildRegion('Status Bar', 'statusbar', statusBars, screenBounds));
    }

    const navElements = elements.filter(e => e.type === 'MENU' || e.type === 'TAB');
    if (navElements.length > 0) {
      regions.push(this.buildRegion('Navigation', 'navigation', navElements, screenBounds));
    }

    const contentElements = elements.filter(e =>
      !regions.some(r => r.elementIds.includes(e.elementId))
    );
    if (contentElements.length > 0) {
      regions.push(this.buildRegion('Content', 'content', contentElements, screenBounds));
    }

    return regions;
  }

  private buildRegion(
    label: string,
    purpose: RegionPurpose,
    elements: readonly VisualElement[],
    screenBounds: Bounds,
  ): VisualRegion {
    const bounds = this.computeBoundingBox(elements.map(e => e.bounds), screenBounds);

    return {
      regionId: regionId(`region-${++this.regionCounter}`),
      label,
      bounds,
      elementIds: elements.map(e => e.elementId),
      purpose,
    };
  }

  private computeBoundingBox(boundsList: readonly Bounds[], fallback: Bounds): Bounds {
    if (boundsList.length === 0) return fallback;

    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;

    for (const b of boundsList) {
      minX = Math.min(minX, b.x);
      minY = Math.min(minY, b.y);
      maxX = Math.max(maxX, b.x + b.width);
      maxY = Math.max(maxY, b.y + b.height);
    }

    return {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY,
    };
  }

  // --- Detection Helpers ---

  private detectNotifications(elements: readonly VisualElement[]): readonly VisualNotification[] {
    return elements
      .filter(e => e.type === 'NOTIFICATION')
      .map(e => ({
        notificationId: `notif-${e.elementId}`,
        text: e.text,
        bounds: e.bounds,
        severity: this.inferNotificationSeverity(e.text) as VisualNotification['severity'],
        source: e.className ?? 'unknown',
        timestamp: new Date().toISOString(),
      }));
  }

  private inferNotificationSeverity(text: string): string {
    const lower = text.toLowerCase();
    if (lower.includes('error') || lower.includes('fail')) return 'error';
    if (lower.includes('warning') || lower.includes('warn')) return 'warning';
    if (lower.includes('success') || lower.includes('done') || lower.includes('complete')) return 'success';
    return 'info';
  }

  private detectDialogs(
    elements: readonly VisualElement[],
    windows: readonly VisualWindow[],
  ): readonly VisualDialog[] {
    const dialogs: VisualDialog[] = [];

    for (const el of elements) {
      if (el.type === 'DIALOG') {
        const buttons = elements.filter(
          b => b.type === 'BUTTON' && this.boundsOverlap(b.bounds, el.bounds)
        );
        dialogs.push({
          dialogId: `dialog-${el.elementId}`,
          title: el.text.slice(0, 64),
          bounds: el.bounds,
          content: el.text,
          buttons,
          isModal: true,
        });
      }
    }

    for (const win of windows) {
      if (win.isMaximized) continue;
      const isDialog = win.title.length < 80 &&
        win.bounds.width < 800 && win.bounds.height < 600;

      if (isDialog && !dialogs.some(d => this.boundsOverlap(d.bounds, win.bounds))) {
        dialogs.push({
          dialogId: `dialog-window-${win.windowId}`,
          title: win.title,
          bounds: win.bounds,
          content: '',
          buttons: [],
          isModal: true,
        });
      }
    }

    return dialogs;
  }

  private detectMenus(elements: readonly VisualElement[]): readonly VisualMenu[] {
    return elements
      .filter(e => e.type === 'MENU')
      .map(el => {
        const items: VisualMenuItem[] = [{
          label: el.text,
          bounds: el.bounds,
          isEnabled: el.isEnabled,
          isChecked: el.isSelected,
          shortcut: null,
          subItems: [],
        }];

        return {
          menuId: `menu-${el.elementId}`,
          bounds: el.bounds,
          items,
          depth: 0,
        };
      });
  }

  private detectTables(elements: readonly VisualElement[]): readonly VisualTable[] {
    return elements
      .filter(e => e.type === 'TABLE')
      .map(el => {
        const headers: string[] = [];
        const rows: string[][] = [];

        const lines = el.text.split('\n').filter(l => l.trim().length > 0);
        if (lines.length > 0) {
          headers.push(...lines[0].split(/[|\t]/).map(h => h.trim()));
          for (let i = 1; i < lines.length; i++) {
            rows.push(lines[i].split(/[|\t]/).map(c => c.trim()));
          }
        }

        return {
          tableId: `table-${el.elementId}`,
          bounds: el.bounds,
          headers,
          rows,
          columnCount: headers.length,
          rowCount: rows.length,
        };
      });
  }

  // --- Confidence ---

  private computeSceneConfidence(
    ocrBlocks: readonly OcrBlock[],
    elements: readonly VisualElement[],
    capture: ScreenCapture,
  ): number {
    let score = 0.5;

    if (ocrBlocks.length > 0) {
      const avgOcrConf = ocrBlocks.reduce((sum, b) => sum + b.confidence, 0) / ocrBlocks.length;
      score += avgOcrConf * 0.2;
    }

    if (elements.length > 0) {
      const avgElConf = elements.reduce((sum, e) => sum + e.confidence, 0) / elements.length;
      score += avgElConf * 0.2;
    }

    if (capture.width > 0 && capture.height > 0) {
      score += 0.1;
    }

    return Math.min(1, Math.max(0, score));
  }

  // --- Text ---

  private extractTextContent(blocks: readonly OcrBlock[]): string {
    const sorted = blocks
      .slice()
      .sort((a, b) => a.readingOrder - b.readingOrder);

    return sorted.map(b => b.text).join(OCR_BLOCK_SEPARATOR);
  }

  // --- Geometry Helpers ---

  private boundsOverlap(a: Bounds, b: Bounds): boolean {
    return (
      a.x < b.x + b.width &&
      a.x + a.width > b.x &&
      a.y < b.y + b.height &&
      a.y + a.height > b.y
    );
  }
}
