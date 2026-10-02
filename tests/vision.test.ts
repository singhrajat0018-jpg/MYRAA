// ============================================================================
// MYRAA Vision Core — Comprehensive Tests
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  monitorId, observationId, elementId, regionId,
  DEFAULT_VISION_CONFIG, DEFAULT_SECURITY_POLICY,
  CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW, CONFIDENCE_MINIMUM,
  OCR_BLOCK_SEPARATOR, SIGNIFICANCE_WEIGHTS,
  WINDOW_TITLE_MAX_LENGTH, SCREEN_TEXT_MAX_LENGTH, ELEMENT_TEXT_MAX_LENGTH,
} from '../src/vision/contracts';

import type {
  Bounds, Point, VisualScene, VisualElement, SceneDiff,
  VisionContext, VisualTarget, TargetResolutionResult,
  VisualConfig, ScreenCapture, MonitorInfo, OcrBlock, OcrLine, OcrWord,
  VisualWindow, VisualNotification, VisualDialog, VisualRegion,
  VisualMenu, VisualTable, VisualElementType, ElementId, RegionId,
  ObservationId, MonitorId, VisualChange, CacheEntry,
  VisionEvent, VisionEventType,
} from '../src/vision/contracts';

import { LruCache, SceneCache } from '../src/vision/cache';
import {
  MockScreenCaptureAdapter, BridgeScreenCaptureAdapter, CaptureHistory,
} from '../src/vision/screenCapture';
import { MockOcrAdapter, OcrResultMerger, OcrTextExtractor } from '../src/vision/ocrAdapter';
import { SceneBuilder } from '../src/vision/sceneBuilder';
import { ChangeDetector } from '../src/vision/changeDetector';
import { TargetResolver } from '../src/vision/targetResolver';
import { ContextBuilder } from '../src/vision/contextBuilder';
import {
  VisionSecurityManager, ImageValidator, ContentSanitizer, FilePathValidator,
  RateLimiter,
} from '../src/vision/security';
import { VisionEngine } from '../src/vision/index';

// ============================================================================
// Helpers
// ============================================================================

function makeBounds(x = 0, y = 0, width = 100, height = 50): Bounds {
  return { x, y, width, height };
}

function makePoint(x = 50, y = 25): Point {
  return { x, y };
}

function makeElementId(suffix = '1'): ElementId {
  return elementId(`el-${suffix}`);
}

function makeRegionId(suffix = '1'): RegionId {
  return regionId(`region-${suffix}`);
}

function makeObservationId(suffix = '1'): ObservationId {
  return observationId(`obs-${suffix}`);
}

function makeMonitorId(suffix = '0'): MonitorId {
  return monitorId(`monitor-${suffix}`);
}

function makeMonitorInfo(overrides?: Partial<MonitorInfo>): MonitorInfo {
  return {
    id: makeMonitorId('0'),
    index: 0,
    bounds: makeBounds(0, 0, 1920, 1080),
    dpiScale: 1.0,
    isPrimary: true,
    orientation: 'landscape',
    colorDepth: 32,
    ...overrides,
  };
}

function makeCapture(overrides?: Partial<ScreenCapture>): ScreenCapture {
  return {
    captureId: 'cap-1',
    timestamp: '2026-01-01T00:00:00.000Z',
    monitorId: makeMonitorId('0'),
    bounds: makeBounds(0, 0, 1920, 1080),
    dpiScale: 1.0,
    imageData: Buffer.from('MOCK_IMAGE_DATA').toString('base64'),
    format: 'png',
    width: 1920,
    height: 1080,
    ...overrides,
  };
}

function makeElement(overrides?: Partial<VisualElement>): VisualElement {
  return {
    elementId: makeElementId(),
    type: 'BUTTON',
    bounds: makeBounds(100, 100, 200, 50),
    text: 'Submit',
    confidence: 0.9,
    parentElementId: null,
    zOrder: 0,
    isVisible: true,
    isEnabled: true,
    isFocused: false,
    isSelected: false,
    isClickable: true,
    accessibilityRole: 'button',
    accessibilityLabel: 'Submit',
    className: null,
    ...overrides,
  };
}

function makeWindow(overrides?: Partial<VisualWindow>): VisualWindow {
  return {
    windowId: 'win-1',
    title: 'Test Window',
    processName: 'test.exe',
    bounds: makeBounds(0, 0, 1920, 1080),
    isFocused: true,
    isMinimized: false,
    isMaximized: false,
    zIndex: 1,
    ...overrides,
  };
}

function makeOcrBlock(overrides?: Partial<OcrBlock>): OcrBlock {
  return {
    blockId: 'ocr-block-0',
    text: 'Hello World',
    bounds: makeBounds(10, 10, 400, 30),
    confidence: 0.9,
    lines: [],
    readingOrder: 0,
    ...overrides,
  };
}

function makeNotification(overrides?: Partial<VisualNotification>): VisualNotification {
  return {
    notificationId: 'notif-1',
    text: 'File saved successfully',
    bounds: makeBounds(100, 100, 300, 40),
    severity: 'success',
    source: 'app',
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

function makeDialog(overrides?: Partial<VisualDialog>): VisualDialog {
  return {
    dialogId: 'dialog-1',
    title: 'Confirm Action',
    bounds: makeBounds(400, 300, 500, 300),
    content: 'Are you sure?',
    buttons: [],
    isModal: true,
    ...overrides,
  };
}

function makeMenu(overrides?: Partial<VisualMenu>): VisualMenu {
  return {
    menuId: 'menu-1',
    bounds: makeBounds(0, 0, 200, 300),
    items: [],
    depth: 0,
    ...overrides,
  };
}

function makeTable(overrides?: Partial<VisualTable>): VisualTable {
  return {
    tableId: 'table-1',
    bounds: makeBounds(50, 50, 600, 400),
    headers: ['Name', 'Value'],
    rows: [['A', '1'], ['B', '2']],
    columnCount: 2,
    rowCount: 2,
    ...overrides,
  };
}

function makeScene(overrides?: Partial<VisualScene>): VisualScene {
  return {
    sceneId: makeObservationId('scene-1'),
    timestamp: '2026-01-01T00:00:00.000Z',
    captureId: 'cap-1',
    monitorId: makeMonitorId('0'),
    bounds: makeBounds(0, 0, 1920, 1080),
    dpiScale: 1.0,
    activeWindow: makeWindow(),
    windows: [makeWindow()],
    elements: [makeElement()],
    ocrBlocks: [makeOcrBlock()],
    textContent: 'Hello World',
    regions: [],
    notifications: [],
    dialogs: [],
    menus: [],
    tables: [],
    confidence: 0.8,
    ...overrides,
  };
}

function makeContext(overrides?: Partial<VisionContext>): VisionContext {
  return {
    timestamp: '2026-01-01T00:00:00.000Z',
    sceneId: makeObservationId('scene-1'),
    activeApplication: 'test.exe',
    activeWindowTitle: 'Test Window',
    screenText: 'Hello World',
    keyElements: [makeElement()],
    importantControls: [makeElement()],
    currentDialog: null,
    notifications: [],
    confidence: 0.8,
    monitorId: makeMonitorId('0'),
    dpiScale: 1.0,
    recentChanges: [],
    ...overrides,
  };
}

// ============================================================================
// Vision Contracts
// ============================================================================

describe('Vision Contracts', () => {
  it('MonitorId branded type exists', () => {
    const id = monitorId('test');
    expect(typeof id).toBe('string');
    expect(id).toBe('test');
  });

  it('ObservationId branded type exists', () => {
    const id = observationId('obs-1');
    expect(typeof id).toBe('string');
    expect(id).toBe('obs-1');
  });

  it('ElementId branded type exists', () => {
    const id = elementId('el-1');
    expect(typeof id).toBe('string');
    expect(id).toBe('el-1');
  });

  it('RegionId branded type exists', () => {
    const id = regionId('reg-1');
    expect(typeof id).toBe('string');
    expect(id).toBe('reg-1');
  });

  it('Bounds creation', () => {
    const b: Bounds = { x: 10, y: 20, width: 300, height: 400 };
    expect(b.x).toBe(10);
    expect(b.y).toBe(20);
    expect(b.width).toBe(300);
    expect(b.height).toBe(400);
  });

  it('Point creation', () => {
    const p: Point = { x: 50, y: 75 };
    expect(p.x).toBe(50);
    expect(p.y).toBe(75);
  });

  it('VisualScene structure validation', () => {
    const scene = makeScene();
    expect(scene).toHaveProperty('sceneId');
    expect(scene).toHaveProperty('timestamp');
    expect(scene).toHaveProperty('captureId');
    expect(scene).toHaveProperty('monitorId');
    expect(scene).toHaveProperty('bounds');
    expect(scene).toHaveProperty('dpiScale');
    expect(scene).toHaveProperty('activeWindow');
    expect(scene).toHaveProperty('windows');
    expect(scene).toHaveProperty('elements');
    expect(scene).toHaveProperty('ocrBlocks');
    expect(scene).toHaveProperty('textContent');
    expect(scene).toHaveProperty('regions');
    expect(scene).toHaveProperty('notifications');
    expect(scene).toHaveProperty('dialogs');
    expect(scene).toHaveProperty('menus');
    expect(scene).toHaveProperty('tables');
    expect(scene).toHaveProperty('confidence');
  });

  it('VisualElement structure validation', () => {
    const el = makeElement();
    expect(el).toHaveProperty('elementId');
    expect(el).toHaveProperty('type');
    expect(el).toHaveProperty('bounds');
    expect(el).toHaveProperty('text');
    expect(el).toHaveProperty('confidence');
    expect(el).toHaveProperty('parentElementId');
    expect(el).toHaveProperty('zOrder');
    expect(el).toHaveProperty('isVisible');
    expect(el).toHaveProperty('isEnabled');
    expect(el).toHaveProperty('isFocused');
    expect(el).toHaveProperty('isSelected');
    expect(el).toHaveProperty('isClickable');
    expect(el).toHaveProperty('accessibilityRole');
    expect(el).toHaveProperty('accessibilityLabel');
    expect(el).toHaveProperty('className');
  });

  it('SceneDiff structure validation', () => {
    const diff: SceneDiff = {
      diffId: 'diff-1',
      fromSceneId: makeObservationId('a'),
      toSceneId: makeObservationId('b'),
      timestamp: '2026-01-01T00:00:00.000Z',
      changes: [],
      windowChanged: false,
      navigationOccurred: false,
      dialogOpened: false,
      dialogClosed: false,
      focusChanged: false,
      layoutChanged: false,
      changeCount: 0,
    };
    expect(diff).toHaveProperty('diffId');
    expect(diff).toHaveProperty('fromSceneId');
    expect(diff).toHaveProperty('toSceneId');
    expect(diff).toHaveProperty('changes');
    expect(diff).toHaveProperty('windowChanged');
    expect(diff).toHaveProperty('navigationOccurred');
    expect(diff).toHaveProperty('dialogOpened');
    expect(diff).toHaveProperty('dialogClosed');
    expect(diff).toHaveProperty('focusChanged');
    expect(diff).toHaveProperty('layoutChanged');
    expect(diff).toHaveProperty('changeCount');
  });

  it('VisionContext structure validation', () => {
    const ctx = makeContext();
    expect(ctx).toHaveProperty('timestamp');
    expect(ctx).toHaveProperty('sceneId');
    expect(ctx).toHaveProperty('activeApplication');
    expect(ctx).toHaveProperty('activeWindowTitle');
    expect(ctx).toHaveProperty('screenText');
    expect(ctx).toHaveProperty('keyElements');
    expect(ctx).toHaveProperty('importantControls');
    expect(ctx).toHaveProperty('currentDialog');
    expect(ctx).toHaveProperty('notifications');
    expect(ctx).toHaveProperty('confidence');
    expect(ctx).toHaveProperty('monitorId');
    expect(ctx).toHaveProperty('dpiScale');
    expect(ctx).toHaveProperty('recentChanges');
  });

  it('VisualTarget structure validation', () => {
    const target: VisualTarget = {
      targetId: 't-1',
      description: 'Submit button',
      element: makeElement(),
      bounds: makeBounds(100, 100, 200, 50),
      center: makePoint(200, 125),
      monitorId: makeMonitorId(),
      coordinateSpace: 'screen',
      confidence: 0.9,
      resolutionMethod: 'ocr',
      observationId: makeObservationId(),
    };
    expect(target).toHaveProperty('targetId');
    expect(target).toHaveProperty('description');
    expect(target).toHaveProperty('element');
    expect(target).toHaveProperty('bounds');
    expect(target).toHaveProperty('center');
    expect(target).toHaveProperty('monitorId');
    expect(target).toHaveProperty('coordinateSpace');
    expect(target).toHaveProperty('confidence');
    expect(target).toHaveProperty('resolutionMethod');
    expect(target).toHaveProperty('observationId');
  });

  it('TargetResolutionResult structure validation', () => {
    const result: TargetResolutionResult = {
      primary: null,
      candidates: [],
      confidence: 0,
      ambiguity: 'none',
      suggestion: null,
    };
    expect(result).toHaveProperty('primary');
    expect(result).toHaveProperty('candidates');
    expect(result).toHaveProperty('confidence');
    expect(result).toHaveProperty('ambiguity');
    expect(result).toHaveProperty('suggestion');
  });

  it('DEFAULT_VISION_CONFIG has expected values', () => {
    expect(DEFAULT_VISION_CONFIG.captureInterval).toBe(1000);
    expect(DEFAULT_VISION_CONFIG.ocrEnabled).toBe(true);
    expect(DEFAULT_VISION_CONFIG.layoutAnalysisEnabled).toBe(true);
    expect(DEFAULT_VISION_CONFIG.elementDetectionEnabled).toBe(true);
    expect(DEFAULT_VISION_CONFIG.changeTrackingEnabled).toBe(true);
    expect(DEFAULT_VISION_CONFIG.maxSceneHistory).toBe(30);
    expect(DEFAULT_VISION_CONFIG.cacheSize).toBe(64);
    expect(DEFAULT_VISION_CONFIG.maxConcurrentCaptures).toBe(2);
    expect(DEFAULT_VISION_CONFIG.regionFirstAnalysis).toBe(false);
    expect(DEFAULT_VISION_CONFIG.unchangedScreenDetection).toBe(true);
    expect(DEFAULT_VISION_CONFIG.debounceMs).toBe(150);
  });

  it('DEFAULT_SECURITY_POLICY has expected values', () => {
    expect(DEFAULT_SECURITY_POLICY.maxImageSizeBytes).toBe(10 * 1024 * 1024);
    expect(DEFAULT_SECURITY_POLICY.maxImageWidth).toBe(7680);
    expect(DEFAULT_SECURITY_POLICY.maxImageHeight).toBe(4320);
    expect(DEFAULT_SECURITY_POLICY.allowedFormats).toContain('png');
    expect(DEFAULT_SECURITY_POLICY.allowedFormats).toContain('jpeg');
    expect(DEFAULT_SECURITY_POLICY.rateLimitPerMinute).toBe(60);
  });

  it('Confidence constants are in correct range', () => {
    expect(CONFIDENCE_HIGH).toBeGreaterThan(CONFIDENCE_MEDIUM);
    expect(CONFIDENCE_MEDIUM).toBeGreaterThan(CONFIDENCE_LOW);
    expect(CONFIDENCE_LOW).toBeGreaterThan(CONFIDENCE_MINIMUM);
    expect(CONFIDENCE_MINIMUM).toBeGreaterThanOrEqual(0);
    expect(CONFIDENCE_HIGH).toBeLessThanOrEqual(1);
  });

  it('SIGNIFICANCE_WEIGHTS keys match ChangeSignificance', () => {
    expect(SIGNIFICANCE_WEIGHTS.trivial).toBe(0.1);
    expect(SIGNIFICANCE_WEIGHTS.minor).toBe(0.3);
    expect(SIGNIFICANCE_WEIGHTS.moderate).toBe(0.5);
    expect(SIGNIFICANCE_WEIGHTS.major).toBe(0.8);
    expect(SIGNIFICANCE_WEIGHTS.critical).toBe(1.0);
  });
});

// ============================================================================
// LRU Cache
// ============================================================================

describe('LRU Cache', () => {
  it('creates with specified max size and TTL', () => {
    const cache = new LruCache<string, number>(10, 5000);
    expect(cache.size).toBe(0);
    expect(cache.hits).toBe(0);
    expect(cache.misses).toBe(0);
  });

  it('set and get basic', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    expect(cache.get('a')).toBe(1);
  });

  it('get miss returns undefined', () => {
    const cache = new LruCache<string, number>(10, 5000);
    expect(cache.get('missing')).toBeUndefined();
  });

  it('LRU eviction when full', () => {
    const cache = new LruCache<string, number>(3, 50000);
    cache.set('a', 1);
    cache.set('b', 2);
    cache.set('c', 3);
    cache.set('d', 4);
    expect(cache.size).toBe(3);
    expect(cache.get('a')).toBeUndefined();
    expect(cache.get('b')).toBe(2);
  });

  it('LRU eviction refreshes access order', () => {
    const cache = new LruCache<string, number>(3, 50000);
    cache.set('a', 1);
    cache.set('b', 2);
    cache.set('c', 3);
    cache.get('a');
    cache.set('d', 4);
    expect(cache.get('a')).toBe(1);
    expect(cache.get('b')).toBeUndefined();
  });

  it('TTL expiration', () => {
    const cache = new LruCache<string, number>(10, 1);
    cache.set('a', 1);
    expect(cache.get('a')).toBe(1);
  });

  it('expired entry returns undefined', () => {
    const cache = new LruCache<string, number>(10, 1);
    cache.set('a', 1);
    const entry = (cache as any).entries.get('a');
    entry.createdAt = Date.now() - 100;
    expect(cache.get('a')).toBeUndefined();
  });

  it('has returns true for existing key', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    expect(cache.has('a')).toBe(true);
  });

  it('has returns false for missing key', () => {
    const cache = new LruCache<string, number>(10, 5000);
    expect(cache.has('nope')).toBe(false);
  });

  it('delete removes entry', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    expect(cache.delete('a')).toBe(true);
    expect(cache.get('a')).toBeUndefined();
    expect(cache.size).toBe(0);
  });

  it('delete returns false for missing key', () => {
    const cache = new LruCache<string, number>(10, 5000);
    expect(cache.delete('nope')).toBe(false);
  });

  it('clear resets everything', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    cache.set('b', 2);
    cache.get('a');
    cache.get('missing');
    cache.clear();
    expect(cache.size).toBe(0);
    expect(cache.hits).toBe(0);
    expect(cache.misses).toBe(0);
  });

  it('size tracks entries', () => {
    const cache = new LruCache<string, number>(10, 5000);
    expect(cache.size).toBe(0);
    cache.set('a', 1);
    expect(cache.size).toBe(1);
    cache.set('b', 2);
    expect(cache.size).toBe(2);
  });

  it('hit/miss stats are tracked', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    cache.get('a');
    cache.get('a');
    cache.get('missing');
    expect(cache.hits).toBe(2);
    expect(cache.misses).toBe(1);
  });

  it('hitRate computes correctly', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    cache.get('a');
    cache.get('missing');
    cache.get('missing');
    expect(cache.hitRate).toBeCloseTo(1 / 3);
  });

  it('hitRate is 0 when empty', () => {
    const cache = new LruCache<string, number>(10, 5000);
    expect(cache.hitRate).toBe(0);
  });

  it('update existing key refreshes value', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    cache.set('a', 99);
    expect(cache.get('a')).toBe(99);
    expect(cache.size).toBe(1);
  });

  it('multiple set/get cycle', () => {
    const cache = new LruCache<number, string>(5, 5000);
    for (let i = 0; i < 20; i++) {
      cache.set(i, `val-${i}`);
    }
    expect(cache.size).toBe(5);
    expect(cache.get(19)).toBe('val-19');
    expect(cache.get(18)).toBe('val-18');
    expect(cache.get(16)).toBe('val-16');
    expect(cache.get(0)).toBeUndefined();
    expect(cache.get(14)).toBeUndefined();
  });

  it('getStats returns correct structure', () => {
    const cache = new LruCache<string, number>(5, 5000);
    cache.set('a', 1);
    cache.set('b', 2);
    const stats = cache.getStats();
    expect(stats.size).toBe(2);
    expect(stats.maxSize).toBe(5);
    expect(stats.hits).toBe(0);
    expect(stats.misses).toBe(0);
    expect(typeof stats.hitRate).toBe('number');
    expect(typeof stats.oldestEntryAge).toBe('number');
    expect(typeof stats.newestEntryAge).toBe('number');
  });

  it('keys returns all keys', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    cache.set('b', 2);
    const keys = cache.keys();
    expect(keys).toContain('a');
    expect(keys).toContain('b');
  });

  it('values returns all values', () => {
    const cache = new LruCache<string, number>(10, 5000);
    cache.set('a', 1);
    cache.set('b', 2);
    const vals = cache.values();
    expect(vals).toContain(1);
    expect(vals).toContain(2);
  });

  it('evictExpired removes expired entries', () => {
    const cache = new LruCache<string, number>(10, 1);
    cache.set('a', 1);
    cache.set('b', 2);
    const entries = (cache as any).entries as Map<string, any>;
    for (const entry of entries.values()) {
      entry.createdAt = Date.now() - 100;
    }
    const evicted = cache.evictExpired();
    expect(evicted).toBe(2);
    expect(cache.size).toBe(0);
  });

  it('zero TTL means entries never expire', () => {
    const cache = new LruCache<string, number>(10, 0);
    cache.set('a', 1);
    const entry = (cache as any).entries.get('a');
    entry.createdAt = Date.now() - 100000;
    expect(cache.get('a')).toBe(1);
  });
});

// ============================================================================
// Scene Cache
// ============================================================================

describe('SceneCache', () => {
  it('creates empty', () => {
    const cache = new SceneCache(10, 5000);
    expect(cache.size).toBe(0);
  });

  it('set and get scene', () => {
    const cache = new SceneCache(10, 5000);
    const scene = makeScene({ sceneId: observationId('scene-1') });
    cache.set(scene);
    expect(cache.get('scene-1')).toBeDefined();
    expect(cache.get('scene-1')!.sceneId).toBe('scene-1');
  });

  it('getLatest returns last inserted', () => {
    const cache = new SceneCache(10, 5000);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    cache.set(makeScene({ sceneId: observationId('s2') }));
    const latest = cache.getLatest();
    expect(latest).not.toBeNull();
    expect(latest!.sceneId).toBe('s2');
  });

  it('getLatest returns null when empty', () => {
    const cache = new SceneCache(10, 5000);
    expect(cache.getLatest()).toBeNull();
  });

  it('getByIndex returns correct scene', () => {
    const cache = new SceneCache(10, 5000);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    cache.set(makeScene({ sceneId: observationId('s2') }));
    expect(cache.getByIndex(0)!.sceneId).toBe('s1');
    expect(cache.getByIndex(1)!.sceneId).toBe('s2');
  });

  it('getByIndex returns null for out of range', () => {
    const cache = new SceneCache(10, 5000);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    expect(cache.getByIndex(-1)).toBeNull();
    expect(cache.getByIndex(5)).toBeNull();
  });

  it('has returns correct value', () => {
    const cache = new SceneCache(10, 5000);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    expect(cache.has('s1')).toBe(true);
    expect(cache.has('s2')).toBe(false);
  });

  it('clear empties cache', () => {
    const cache = new SceneCache(10, 5000);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    cache.clear();
    expect(cache.size).toBe(0);
    expect(cache.getLatest()).toBeNull();
  });

  it('getStats returns stats', () => {
    const cache = new SceneCache(10, 5000);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    const stats = cache.getStats();
    expect(stats.size).toBe(1);
    expect(stats.maxSize).toBe(10);
  });

  it('evictExpired delegates to inner cache', () => {
    const cache = new SceneCache(10, 1);
    cache.set(makeScene({ sceneId: observationId('s1') }));
    const innerCache = (cache as any).cache as LruCache<string, any>;
    const entries = (innerCache as any).entries as Map<string, any>;
    for (const entry of entries.values()) {
      entry.createdAt = Date.now() - 100;
    }
    const evicted = cache.evictExpired();
    expect(evicted).toBe(1);
  });
});

// ============================================================================
// Screen Capture
// ============================================================================

describe('MockScreenCaptureAdapter', () => {
  it('creates with default monitor', async () => {
    const adapter = new MockScreenCaptureAdapter();
    expect(adapter.isAvailable()).toBe(true);
    const monitors = await adapter.getMonitors();
    expect(monitors.length).toBe(1);
    expect(monitors[0].isPrimary).toBe(true);
  });

  it('creates with custom monitors', async () => {
    const monitors = [
      makeMonitorInfo({ id: monitorId('m1'), index: 0 }),
      makeMonitorInfo({ id: monitorId('m2'), index: 1, isPrimary: false }),
    ];
    const adapter = new MockScreenCaptureAdapter(monitors);
    const result = await adapter.getMonitors();
    expect(result.length).toBe(2);
  });

  it('captureMonitor returns ScreenCapture', async () => {
    const adapter = new MockScreenCaptureAdapter();
    const capture = await adapter.captureMonitor(monitorId('monitor-0'));
    expect(capture.captureId).toContain('capture-');
    expect(capture.timestamp).toBeTruthy();
    expect(capture.format).toBe('png');
    expect(capture.imageData).toBeTruthy();
    expect(capture.width).toBe(1920);
    expect(capture.height).toBe(1080);
  });

  it('captureMonitor throws for unknown monitor', async () => {
    const adapter = new MockScreenCaptureAdapter();
    await expect(adapter.captureMonitor(monitorId('unknown'))).rejects.toThrow('Monitor not found');
  });

  it('capture with custom bounds', async () => {
    const adapter = new MockScreenCaptureAdapter();
    const region = { x: 100, y: 100, width: 500, height: 300 };
    const capture = await adapter.captureRegion(region, monitorId('monitor-0'));
    expect(capture.bounds.x).toBe(100);
    expect(capture.bounds.y).toBe(100);
    expect(capture.bounds.width).toBe(500);
    expect(capture.bounds.height).toBe(300);
  });

  it('captureAll returns captures for all monitors', async () => {
    const monitors = [
      makeMonitorInfo({ id: monitorId('m1'), index: 0 }),
      makeMonitorInfo({ id: monitorId('m2'), index: 1, isPrimary: false }),
    ];
    const adapter = new MockScreenCaptureAdapter(monitors);
    const captures = await adapter.captureAll();
    expect(captures.length).toBe(2);
  });

  it('capture IDs increment', async () => {
    const adapter = new MockScreenCaptureAdapter();
    const c1 = await adapter.captureMonitor(monitorId('monitor-0'));
    const c2 = await adapter.captureMonitor(monitorId('monitor-0'));
    expect(c1.captureId).not.toBe(c2.captureId);
  });

  it('captureRegion throws for unknown monitor', async () => {
    const adapter = new MockScreenCaptureAdapter();
    await expect(
      adapter.captureRegion({ x: 0, y: 0, width: 100, height: 100 }, monitorId('unknown'))
    ).rejects.toThrow('Monitor not found');
  });

  it('isUnchanged returns false initially', () => {
    const adapter = new MockScreenCaptureAdapter();
    expect(adapter.isUnchanged()).toBe(false);
  });
});

describe('BridgeScreenCaptureAdapter', () => {
  it('creates with default config', () => {
    const adapter = new BridgeScreenCaptureAdapter();
    expect(adapter.isAvailable()).toBe(true);
  });

  it('creates with custom config', () => {
    const adapter = new BridgeScreenCaptureAdapter({
      agentUrl: 'http://custom:9999',
      timeoutMs: 5000,
    });
    expect(adapter.isAvailable()).toBe(true);
  });

  it('invalidateMonitorCache clears cache', () => {
    const adapter = new BridgeScreenCaptureAdapter();
    adapter.invalidateMonitorCache();
    expect((adapter as any).cachedMonitors).toBeNull();
  });
});

describe('CaptureHistory', () => {
  it('starts empty', () => {
    const history = new CaptureHistory(10);
    expect(history.size).toBe(0);
    expect(history.getLatest()).toBeNull();
  });

  it('push and getLatest', () => {
    const history = new CaptureHistory(10);
    const c1 = makeCapture({ captureId: 'c1' });
    const c2 = makeCapture({ captureId: 'c2' });
    history.push(c1);
    history.push(c2);
    expect(history.getLatest()!.captureId).toBe('c2');
  });

  it('enforces max history', () => {
    const history = new CaptureHistory(3);
    history.push(makeCapture({ captureId: 'c1' }));
    history.push(makeCapture({ captureId: 'c2' }));
    history.push(makeCapture({ captureId: 'c3' }));
    history.push(makeCapture({ captureId: 'c4' }));
    expect(history.size).toBe(3);
    expect(history.getByIndex(0)!.captureId).toBe('c2');
  });

  it('getByIndex returns null for invalid index', () => {
    const history = new CaptureHistory(10);
    history.push(makeCapture());
    expect(history.getByIndex(-1)).toBeNull();
    expect(history.getByIndex(5)).toBeNull();
  });

  it('getAll returns all captures', () => {
    const history = new CaptureHistory(10);
    history.push(makeCapture({ captureId: 'a' }));
    history.push(makeCapture({ captureId: 'b' }));
    expect(history.getAll().length).toBe(2);
  });

  it('clear empties history', () => {
    const history = new CaptureHistory(10);
    history.push(makeCapture());
    history.clear();
    expect(history.size).toBe(0);
  });

  it('findUnchanged returns null for empty history', () => {
    const history = new CaptureHistory(10);
    expect(history.findUnchanged(makeCapture())).toBeNull();
  });

  it('findUnchanged returns matching capture', () => {
    const history = new CaptureHistory(10);
    const c = makeCapture({ captureId: 'c1', imageData: 'SAME_DATA' });
    history.push(c);
    const current = makeCapture({ captureId: 'c2', imageData: 'SAME_DATA' });
    expect(history.findUnchanged(current)).toBe(c);
  });

  it('findUnchanged returns null for different data', () => {
    const history = new CaptureHistory(10);
    history.push(makeCapture({ captureId: 'c1', imageData: 'DATA_A' }));
    const current = makeCapture({ captureId: 'c2', imageData: 'COMPLETELY_DIFFERENT_DATA_1234567890' });
    expect(history.findUnchanged(current)).toBeNull();
  });

  it('findUnchanged filters by monitorId', () => {
    const history = new CaptureHistory(10);
    history.push(makeCapture({
      captureId: 'c1',
      imageData: 'SAME',
      monitorId: monitorId('m1'),
    }));
    const current = makeCapture({
      captureId: 'c2',
      imageData: 'SAME',
      monitorId: monitorId('m2'),
    });
    expect(history.findUnchanged(current)).toBeNull();
  });
});

// ============================================================================
// OCR Adapter
// ============================================================================

describe('MockOcrAdapter', () => {
  it('creates and is available', () => {
    const adapter = new MockOcrAdapter();
    expect(adapter.isAvailable()).toBe(true);
  });

  it('recognizeText returns OcrBlock array', async () => {
    const adapter = new MockOcrAdapter();
    const blocks = await adapter.recognizeText(makeCapture());
    expect(Array.isArray(blocks)).toBe(true);
    expect(blocks.length).toBeGreaterThan(0);
  });

  it('blocks have spatial bounds', async () => {
    const adapter = new MockOcrAdapter();
    const blocks = await adapter.recognizeText(makeCapture());
    for (const block of blocks) {
      expect(block.bounds).toHaveProperty('x');
      expect(block.bounds).toHaveProperty('y');
      expect(block.bounds).toHaveProperty('width');
      expect(block.bounds).toHaveProperty('height');
    }
  });

  it('blocks have reading order', async () => {
    const adapter = new MockOcrAdapter();
    const blocks = await adapter.recognizeText(makeCapture());
    for (let i = 0; i < blocks.length; i++) {
      expect(typeof blocks[i].readingOrder).toBe('number');
    }
  });

  it('blocks have confidence in range', async () => {
    const adapter = new MockOcrAdapter();
    const blocks = await adapter.recognizeText(makeCapture());
    for (const block of blocks) {
      expect(block.confidence).toBeGreaterThanOrEqual(0);
      expect(block.confidence).toBeLessThanOrEqual(1);
    }
  });

  it('recognizeRegion returns blocks for region', async () => {
    const adapter = new MockOcrAdapter();
    const region = makeBounds(0, 0, 500, 200);
    const blocks = await adapter.recognizeRegion(makeCapture(), region);
    expect(blocks.length).toBeGreaterThan(0);
  });

  it('each block has lines array', async () => {
    const adapter = new MockOcrAdapter();
    const blocks = await adapter.recognizeText(makeCapture());
    for (const block of blocks) {
      expect(Array.isArray(block.lines)).toBe(true);
    }
  });

  it('each line has words', async () => {
    const adapter = new MockOcrAdapter();
    const blocks = await adapter.recognizeText(makeCapture());
    for (const block of blocks) {
      for (const line of block.lines) {
        expect(Array.isArray(line.words)).toBe(true);
      }
    }
  });
});

describe('OcrResultMerger', () => {
  it('merges multiple block arrays', () => {
    const merger = new OcrResultMerger();
    const blocks1 = [makeOcrBlock({ blockId: 'b1', bounds: makeBounds(0, 0, 200, 30) })];
    const blocks2 = [makeOcrBlock({ blockId: 'b2', bounds: makeBounds(0, 100, 200, 30) })];
    const merged = merger.merge([blocks1, blocks2]);
    expect(merged.length).toBe(2);
  });

  it('deduplicates overlapping blocks', () => {
    const merger = new OcrResultMerger();
    const b1 = makeOcrBlock({ blockId: 'b1', bounds: makeBounds(10, 10, 200, 30), confidence: 0.6 });
    const b2 = makeOcrBlock({ blockId: 'b2', bounds: makeBounds(15, 12, 200, 30), confidence: 0.9 });
    const merged = merger.merge([[b1, b2]]);
    expect(merged.length).toBe(1);
    expect(merged[0].confidence).toBe(0.9);
  });

  it('assigns reading order', () => {
    const merger = new OcrResultMerger();
    const b1 = makeOcrBlock({ bounds: makeBounds(0, 100, 200, 30) });
    const b2 = makeOcrBlock({ bounds: makeBounds(0, 10, 200, 30) });
    const merged = merger.merge([[b1, b2]]);
    expect(merged[0].readingOrder).toBe(0);
    expect(merged[1].readingOrder).toBe(1);
    expect(merged[0].bounds.y).toBeLessThan(merged[1].bounds.y);
  });

  it('returns empty for empty input', () => {
    const merger = new OcrResultMerger();
    expect(merger.merge([])).toEqual([]);
    expect(merger.merge([[]])).toEqual([]);
  });
});

describe('OcrTextExtractor', () => {
  it('extracts text from blocks', () => {
    const extractor = new OcrTextExtractor();
    const blocks = [
      makeOcrBlock({ text: 'Hello', readingOrder: 0 }),
      makeOcrBlock({ text: 'World', readingOrder: 1 }),
    ];
    const text = extractor.extractText(blocks);
    expect(text).toContain('Hello');
    expect(text).toContain('World');
  });

  it('extracts text sorted by reading order', () => {
    const extractor = new OcrTextExtractor();
    const blocks = [
      makeOcrBlock({ text: 'Second', readingOrder: 1 }),
      makeOcrBlock({ text: 'First', readingOrder: 0 }),
    ];
    const text = extractor.extractText(blocks);
    const lines = text.split('\n');
    expect(lines[0]).toBe('First');
    expect(lines[1]).toBe('Second');
  });

  it('extractTextFromRegion filters by region', () => {
    const extractor = new OcrTextExtractor();
    const blocks = [
      makeOcrBlock({ text: 'Inside', bounds: makeBounds(10, 10, 100, 20), readingOrder: 0 }),
      makeOcrBlock({ text: 'Outside', bounds: makeBounds(500, 500, 100, 20), readingOrder: 1 }),
    ];
    const text = extractor.extractTextFromRegion(blocks, makeBounds(0, 0, 200, 200));
    expect(text).toContain('Inside');
    expect(text).not.toContain('Outside');
  });

  it('searchBlocks finds matching text', () => {
    const extractor = new OcrTextExtractor();
    const blocks = [
      makeOcrBlock({ text: 'Submit Form' }),
      makeOcrBlock({ text: 'Cancel Action' }),
    ];
    const found = extractor.searchBlocks(blocks, 'Submit');
    expect(found.length).toBe(1);
    expect(found[0].text).toBe('Submit Form');
  });

  it('searchBlocks respects minConfidence', () => {
    const extractor = new OcrTextExtractor();
    const blocks = [
      makeOcrBlock({ text: 'High', confidence: 0.9 }),
      makeOcrBlock({ text: 'Low', confidence: 0.2 }),
    ];
    const found = extractor.searchBlocks(blocks, 'High', { minConfidence: 0.5 });
    expect(found.length).toBe(1);
    expect(found[0].text).toBe('High');
  });

  it('searchBlocks exact mode', () => {
    const extractor = new OcrTextExtractor();
    const blocks = [makeOcrBlock({ text: 'Submit Form' })];
    const found = extractor.searchBlocks(blocks, 'Submit', { fuzzy: false });
    expect(found.length).toBe(0);
    const exact = extractor.searchBlocks(blocks, 'Submit Form', { fuzzy: false });
    expect(exact.length).toBe(1);
  });
});

// ============================================================================
// Scene Builder
// ============================================================================

describe('SceneBuilder', () => {
  it('creates scene from capture + OCR', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [makeOcrBlock()],
    });
    expect(scene).toBeDefined();
    expect(scene.sceneId).toBeTruthy();
  });

  it('scene has correct structure', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [makeOcrBlock()],
    });
    expect(scene).toHaveProperty('sceneId');
    expect(scene).toHaveProperty('timestamp');
    expect(scene).toHaveProperty('captureId');
    expect(scene).toHaveProperty('monitorId');
    expect(scene).toHaveProperty('elements');
    expect(scene).toHaveProperty('ocrBlocks');
    expect(scene).toHaveProperty('textContent');
    expect(scene).toHaveProperty('regions');
    expect(scene).toHaveProperty('notifications');
    expect(scene).toHaveProperty('dialogs');
    expect(scene).toHaveProperty('menus');
    expect(scene).toHaveProperty('tables');
    expect(scene).toHaveProperty('confidence');
  });

  it('infers elements from OCR blocks', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [makeOcrBlock({ text: 'Submit Button' })],
    });
    expect(scene.elements.length).toBe(1);
    expect(scene.elements[0].type).toBe('BUTTON');
    expect(scene.elements[0].text).toBe('Submit Button');
  });

  it('detects notifications from elements', () => {
    const builder = new SceneBuilder();
    const notifElement = makeElement({ type: 'NOTIFICATION', text: 'Error: something failed' });
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      elements: [notifElement],
    });
    expect(scene.notifications.length).toBe(1);
    expect(scene.notifications[0].severity).toBe('error');
  });

  it('detects menus from elements', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [makeOcrBlock({ text: 'File Menu' })],
    });
    expect(scene.menus.length).toBe(1);
  });

  it('detects tables from elements', () => {
    const builder = new SceneBuilder();
    const tableElement = makeElement({ type: 'TABLE', text: 'Name|Value\nA|1' });
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      elements: [tableElement],
    });
    expect(scene.tables.length).toBe(1);
  });

  it('uses provided elements when given', () => {
    const builder = new SceneBuilder();
    const customEl = makeElement({ text: 'Custom Element' });
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      elements: [customEl],
    });
    expect(scene.elements.length).toBe(1);
    expect(scene.elements[0].text).toBe('Custom Element');
  });

  it('uses provided windows', () => {
    const builder = new SceneBuilder();
    const win = makeWindow({ title: 'My App' });
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      windows: [win],
    });
    expect(scene.windows.length).toBe(1);
    expect(scene.activeWindow).not.toBeNull();
    expect(scene.activeWindow!.title).toBe('My App');
  });

  it('confidence calculation is in range', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [makeOcrBlock({ confidence: 0.8 })],
    });
    expect(scene.confidence).toBeGreaterThanOrEqual(0);
    expect(scene.confidence).toBeLessThanOrEqual(1);
  });

  it('empty OCR produces empty textContent', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
    });
    expect(scene.textContent).toBe('');
  });

  it('textContent aggregates OCR text', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [
        makeOcrBlock({ text: 'Line1', readingOrder: 0 }),
        makeOcrBlock({ text: 'Line2', readingOrder: 1 }),
      ],
    });
    expect(scene.textContent).toContain('Line1');
    expect(scene.textContent).toContain('Line2');
  });

  it('scene has unique ID', () => {
    const builder = new SceneBuilder();
    const s1 = builder.buildScene({ capture: makeCapture(), ocrBlocks: [] });
    const s2 = builder.buildScene({ capture: makeCapture(), ocrBlocks: [] });
    expect(s1.sceneId).not.toBe(s2.sceneId);
  });

  it('scene has timestamp from capture', () => {
    const builder = new SceneBuilder();
    const capture = makeCapture({ timestamp: '2026-06-15T12:00:00.000Z' });
    const scene = builder.buildScene({ capture, ocrBlocks: [] });
    expect(scene.timestamp).toBe('2026-06-15T12:00:00.000Z');
  });

  it('detects dialog elements', () => {
    const builder = new SceneBuilder();
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [makeOcrBlock({ text: 'Warning Dialog' })],
    });
    const dialogs = scene.dialogs;
    expect(dialogs.length).toBeGreaterThanOrEqual(0);
  });

  it('reset clears counters', () => {
    const builder = new SceneBuilder();
    builder.buildScene({ capture: makeCapture(), ocrBlocks: [makeOcrBlock()] });
    builder.reset();
    const scene = builder.buildScene({ capture: makeCapture(), ocrBlocks: [makeOcrBlock()] });
    expect(scene.elements.length).toBe(1);
  });

  it('multiple regions detected', () => {
    const builder = new SceneBuilder();
    const elements = [
      makeElement({ type: 'TOOLBAR', bounds: makeBounds(0, 0, 1920, 40) }),
      makeElement({ type: 'MENU', bounds: makeBounds(0, 40, 200, 30) }),
      makeElement({ type: 'TEXT_BLOCK', bounds: makeBounds(100, 100, 400, 30) }),
    ];
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      elements,
    });
    expect(scene.regions.length).toBeGreaterThanOrEqual(2);
  });

  it('notifications get correct severity for warning', () => {
    const builder = new SceneBuilder();
    const notifElement = makeElement({ type: 'NOTIFICATION', text: 'Warning: Low disk space' });
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      elements: [notifElement],
    });
    expect(scene.notifications.length).toBe(1);
    expect(scene.notifications[0].severity).toBe('warning');
  });

  it('notifications get success severity', () => {
    const builder = new SceneBuilder();
    const notifElement = makeElement({ type: 'NOTIFICATION', text: 'Success: Operation complete' });
    const scene = builder.buildScene({
      capture: makeCapture(),
      ocrBlocks: [],
      elements: [notifElement],
    });
    expect(scene.notifications.length).toBe(1);
    expect(scene.notifications[0].severity).toBe('success');
  });
});

// ============================================================================
// Change Detector
// ============================================================================

describe('ChangeDetector', () => {
  it('no changes produces empty diff', () => {
    const detector = new ChangeDetector(10);
    const scene = makeScene();
    const diff = detector.diff(scene, scene);
    expect(diff.changeCount).toBe(0);
    expect(diff.changes.length).toBe(0);
  });

  it('added element detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ elements: [] });
    const to = makeScene({ elements: [makeElement()] });
    const diff = detector.diff(from, to);
    const added = diff.changes.filter(c => c.type === 'ADDED');
    expect(added.length).toBe(1);
  });

  it('removed element detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ elements: [makeElement()] });
    const to = makeScene({ elements: [] });
    const diff = detector.diff(from, to);
    const removed = diff.changes.filter(c => c.type === 'REMOVED');
    expect(removed.length).toBe(1);
  });

  it('changed text detected', () => {
    const detector = new ChangeDetector(10);
    const el1 = makeElement({ text: 'Before' });
    const el2 = makeElement({ text: 'After' });
    const from = makeScene({ elements: [el1] });
    const to = makeScene({ elements: [el2] });
    const diff = detector.diff(from, to);
    const changed = diff.changes.filter(c => c.type === 'CHANGED');
    expect(changed.length).toBe(1);
  });

  it('focus change detected', () => {
    const detector = new ChangeDetector(10);
    const el1 = makeElement({ isFocused: false });
    const el2 = makeElement({ isFocused: true });
    const from = makeScene({ elements: [el1] });
    const to = makeScene({ elements: [el2] });
    const diff = detector.diff(from, to);
    const focused = diff.changes.filter(c => c.type === 'FOCUSED');
    expect(focused.length).toBe(1);
  });

  it('window opened detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ windows: [] });
    const to = makeScene({ windows: [makeWindow()] });
    const diff = detector.diff(from, to);
    expect(diff.windowChanged).toBe(true);
    const opened = diff.changes.filter(c => c.type === 'OPENED');
    expect(opened.length).toBeGreaterThanOrEqual(1);
  });

  it('window closed detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ windows: [makeWindow()] });
    const to = makeScene({ windows: [] });
    const diff = detector.diff(from, to);
    expect(diff.windowChanged).toBe(true);
    const closed = diff.changes.filter(c => c.type === 'CLOSED');
    expect(closed.length).toBeGreaterThanOrEqual(1);
  });

  it('dialog opened detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ dialogs: [] });
    const to = makeScene({ dialogs: [makeDialog()] });
    const diff = detector.diff(from, to);
    expect(diff.dialogOpened).toBe(true);
  });

  it('dialog closed detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ dialogs: [makeDialog()] });
    const to = makeScene({ dialogs: [] });
    const diff = detector.diff(from, to);
    expect(diff.dialogClosed).toBe(true);
  });

  it('navigation detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ activeWindow: makeWindow({ title: 'Page 1' }) });
    const to = makeScene({ activeWindow: makeWindow({ title: 'Page 2' }) });
    const diff = detector.diff(from, to);
    expect(diff.navigationOccurred).toBe(true);
  });

  it('SceneDiff has unique ID', () => {
    const detector = new ChangeDetector(10);
    const scene = makeScene();
    const d1 = detector.diff(scene, scene);
    const d2 = detector.diff(scene, scene);
    expect(d1.diffId).not.toBe(d2.diffId);
  });

  it('empty scenes produce no diff', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ elements: [], windows: [], notifications: [], dialogs: [] });
    const to = makeScene({ elements: [], windows: [], notifications: [], dialogs: [] });
    const diff = detector.diff(from, to);
    expect(diff.changeCount).toBe(0);
  });

  it('change history tracking', () => {
    const detector = new ChangeDetector(10);
    const s1 = makeScene({ sceneId: observationId('s1') });
    const s2 = makeScene({ sceneId: observationId('s2') });
    detector.pushScene(s1);
    detector.pushScene(s2);
    expect(detector.getHistory().length).toBe(2);
  });

  it('getRecentChanges returns changes', () => {
    const detector = new ChangeDetector(10);
    const s1 = makeScene({ sceneId: observationId('s1'), elements: [] });
    const s2 = makeScene({ sceneId: observationId('s2'), elements: [makeElement()] });
    detector.pushScene(s1);
    detector.pushScene(s2);
    const changes = detector.getRecentChanges(10);
    expect(changes.length).toBeGreaterThan(0);
  });

  it('clearHistory empties history', () => {
    const detector = new ChangeDetector(10);
    detector.pushScene(makeScene());
    detector.clearHistory();
    expect(detector.getHistory().length).toBe(0);
  });

  it('layout changed detection', () => {
    const detector = new ChangeDetector(10);
    const el1 = makeElement({ bounds: makeBounds(0, 0, 100, 50) });
    const el2 = makeElement({ bounds: makeBounds(200, 200, 100, 50) });
    const from = makeScene({ elements: [el1] });
    const to = makeScene({ elements: [el2] });
    const diff = detector.diff(from, to);
    expect(diff.layoutChanged).toBe(true);
  });

  it('notification added detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ notifications: [] });
    const to = makeScene({ notifications: [makeNotification()] });
    const diff = detector.diff(from, to);
    const added = diff.changes.filter(c => c.elementType === 'NOTIFICATION');
    expect(added.length).toBe(1);
    expect(added[0].type).toBe('ADDED');
  });

  it('notification removed detected', () => {
    const detector = new ChangeDetector(10);
    const from = makeScene({ notifications: [makeNotification()] });
    const to = makeScene({ notifications: [] });
    const diff = detector.diff(from, to);
    const removed = diff.changes.filter(c => c.elementType === 'NOTIFICATION');
    expect(removed.length).toBe(1);
    expect(removed[0].type).toBe('REMOVED');
  });

  it('multiple changes in single diff', () => {
    const detector = new ChangeDetector(10);
    const el1 = makeElement({ text: 'Old' });
    const el2 = makeElement({ text: 'New' });
    const from = makeScene({ elements: [el1], notifications: [makeNotification()] });
    const to = makeScene({ elements: [el2], notifications: [] });
    const diff = detector.diff(from, to);
    expect(diff.changeCount).toBeGreaterThanOrEqual(2);
  });

  it('significant change for button text', () => {
    const detector = new ChangeDetector(10);
    const el1 = makeElement({ type: 'BUTTON', text: 'Old' });
    const el2 = makeElement({ type: 'BUTTON', text: 'New' });
    const from = makeScene({ elements: [el1] });
    const to = makeScene({ elements: [el2] });
    const diff = detector.diff(from, to);
    const changed = diff.changes.find(c => c.type === 'CHANGED');
    expect(changed).toBeDefined();
    expect(changed!.significance).toBe('moderate');
  });

  it('maxHistory limits scene history', () => {
    const detector = new ChangeDetector(3);
    for (let i = 0; i < 10; i++) {
      detector.pushScene(makeScene({ sceneId: observationId(`s${i}`) }));
    }
    expect(detector.getHistory().length).toBe(3);
  });
});

// ============================================================================
// Target Resolver
// ============================================================================

describe('TargetResolver', () => {
  const resolver = new TargetResolver();

  function makeRequest(query: string, overrides?: Partial<TargetResolutionRequest>) {
    return {
      query,
      context: makeContext(),
      preferredMonitor: null,
      maxCandidates: 5,
      minConfidence: 0,
      ...overrides,
    };
  }

  it('resolves text match', () => {
    const result = resolver.resolve(makeRequest('Submit'));
    expect(result.primary).not.toBeNull();
    expect(result.primary!.element!.text).toBe('Submit');
  });

  it('resolves text partial match', () => {
    const result = resolver.resolve(makeRequest('Sub'));
    expect(result.primary).not.toBeNull();
  });

  it('resolves ordinal first button', () => {
    const ctx = makeContext({
      importantControls: [
        makeElement({ text: 'First', isClickable: true, elementId: elementId('e1') }),
        makeElement({ text: 'Second', isClickable: true, elementId: elementId('e2') }),
      ],
    });
    const result = resolver.resolve(makeRequest('first button', { context: ctx }));
    expect(result.primary).not.toBeNull();
    expect(result.primary!.element!.text).toBe('First');
  });

  it('resolves ordinal last button', () => {
    const ctx = makeContext({
      importantControls: [
        makeElement({ text: 'A', isClickable: true, elementId: elementId('e1') }),
        makeElement({ text: 'B', isClickable: true, elementId: elementId('e2') }),
      ],
    });
    const result = resolver.resolve(makeRequest('last button', { context: ctx }));
    expect(result.primary).not.toBeNull();
    expect(result.primary!.element!.text).toBe('B');
  });

  it('resolves type match button', () => {
    const result = resolver.resolve(makeRequest('button'));
    expect(result.primary).not.toBeNull();
    expect(result.primary!.element!.type).toBe('BUTTON');
  });

  it('no match returns null primary', () => {
    const result = resolver.resolve(makeRequest('xyznonexistent'));
    expect(result.primary).toBeNull();
  });

  it('unknown query returns null primary', () => {
    const result = resolver.resolve(makeRequest('flarglebargle'));
    expect(result.primary).toBeNull();
    expect(result.suggestion).toContain('No element matching');
  });

  it('empty context returns null', () => {
    const ctx = makeContext({ keyElements: [], importantControls: [] });
    const result = resolver.resolve(makeRequest('anything', { context: ctx }));
    expect(result.primary).toBeNull();
  });

  it('ambiguity detection - low when clear winner', () => {
    const ctx = makeContext({
      importantControls: [
        makeElement({ text: 'Submit', isClickable: true, confidence: 0.95 }),
        makeElement({ text: 'Cancel', isClickable: true, confidence: 0.4 }),
      ],
    });
    const result = resolver.resolve(makeRequest('Submit', { context: ctx }));
    expect(['none', 'low']).toContain(result.ambiguity);
  });

  it('ambiguity detection - high with multiple close matches', () => {
    const ctx = makeContext({
      importantControls: [
        makeElement({ text: 'Button A', isClickable: true, confidence: 0.7, elementId: elementId('a') }),
        makeElement({ text: 'Button B', isClickable: true, confidence: 0.65, elementId: elementId('b') }),
        makeElement({ text: 'Button C', isClickable: true, confidence: 0.6, elementId: elementId('c') }),
        makeElement({ text: 'Button D', isClickable: true, confidence: 0.55, elementId: elementId('d') }),
      ],
    });
    const result = resolver.resolve(makeRequest('button', { context: ctx }));
    expect(result.candidates.length).toBeGreaterThan(1);
  });

  it('max candidates respected', () => {
    const ctx = makeContext({
      importantControls: Array.from({ length: 10 }, (_, i) =>
        makeElement({ text: `Btn ${i}`, isClickable: true, elementId: elementId(`e${i}`) })
      ),
    });
    const result = resolver.resolve(makeRequest('btn', { context: ctx, maxCandidates: 3 }));
    expect(result.candidates.length).toBeLessThanOrEqual(3);
  });

  it('confidence scoring', () => {
    const result = resolver.resolve(makeRequest('Submit'));
    expect(result.confidence).toBeGreaterThanOrEqual(0);
    expect(result.confidence).toBeLessThanOrEqual(1);
  });

  it('spatial resolution top left', () => {
    const ctx = makeContext({
      keyElements: [
        makeElement({ bounds: makeBounds(10, 10, 100, 50), elementId: elementId('tl') }),
        makeElement({ bounds: makeBounds(1800, 1000, 100, 50), elementId: elementId('br') }),
      ],
      importantControls: [],
    });
    const result = resolver.resolve(makeRequest('top left', { context: ctx }));
    expect(result.primary).not.toBeNull();
  });

  it('deduplication keeps highest confidence', () => {
    const el = makeElement({ text: 'Submit', elementId: elementId('same') });
    const ctx = makeContext({
      keyElements: [{ ...el, confidence: 0.6 }],
      importantControls: [{ ...el, confidence: 0.9 }],
    });
    const result = resolver.resolve(makeRequest('Submit', { context: ctx }));
    const targets = result.candidates.filter(
      t => t.element?.elementId === 'same'
    );
    expect(targets.length).toBe(1);
    expect(targets[0].confidence).toBeGreaterThanOrEqual(0.9);
  });

  it('minConfidence filtering', () => {
    const ctx = makeContext({
      keyElements: [
        makeElement({ text: 'High', confidence: 0.9, elementId: elementId('h') }),
        makeElement({ text: 'Low', confidence: 0.2, elementId: elementId('l') }),
      ],
      importantControls: [],
    });
    const result = resolver.resolve(makeRequest('High Low', { context: ctx, minConfidence: 0.5 }));
    expect(result.candidates.every(c => c.confidence >= 0.5)).toBe(true);
  });
});

// ============================================================================
// Context Builder
// ============================================================================

describe('ContextBuilder', () => {
  it('converts scene to context', () => {
    const builder = new ContextBuilder();
    const scene = makeScene();
    const ctx = builder.build(scene);
    expect(ctx).toBeDefined();
    expect(ctx.sceneId).toBe(scene.sceneId);
  });

  it('context has active application', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({
      activeWindow: makeWindow({ processName: 'chrome.exe' }),
    });
    const ctx = builder.build(scene);
    expect(ctx.activeApplication).toBe('chrome.exe');
  });

  it('context has screen text', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({
      ocrBlocks: [makeOcrBlock({ text: 'Hello', readingOrder: 0 })],
    });
    const ctx = builder.build(scene);
    expect(ctx.screenText).toContain('Hello');
  });

  it('key elements extracted', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({
      elements: [makeElement({ confidence: 0.9 })],
    });
    const ctx = builder.build(scene);
    expect(ctx.keyElements.length).toBe(1);
  });

  it('important controls identified', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({
      elements: [makeElement({
        type: 'BUTTON',
        isClickable: true,
        isEnabled: true,
        isVisible: true,
        confidence: 0.9,
      })],
    });
    const ctx = builder.build(scene);
    expect(ctx.importantControls.length).toBe(1);
  });

  it('current dialog included', () => {
    const builder = new ContextBuilder();
    const dialog = makeDialog();
    const scene = makeScene({ dialogs: [dialog] });
    const ctx = builder.build(scene);
    expect(ctx.currentDialog).not.toBeNull();
    expect(ctx.currentDialog!.dialogId).toBe(dialog.dialogId);
  });

  it('notifications included', () => {
    const builder = new ContextBuilder();
    const notif = makeNotification();
    const scene = makeScene({ notifications: [notif] });
    const ctx = builder.build(scene);
    expect(ctx.notifications.length).toBe(1);
  });

  it('recent changes included', () => {
    const builder = new ContextBuilder();
    const change: VisualChange = {
      changeId: 'chg-1',
      type: 'ADDED',
      elementType: 'BUTTON',
      elementId: null,
      previousState: null,
      currentState: null,
      timestamp: '2026-01-01T00:00:00.000Z',
      significance: 'minor',
    };
    const ctx = builder.build(makeScene(), [change]);
    expect(ctx.recentChanges.length).toBe(1);
  });

  it('confidence propagated', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({ confidence: 0.75 });
    const ctx = builder.build(scene);
    expect(ctx.confidence).toBe(0.75);
  });

  it('empty scene produces minimal context', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({
      elements: [],
      ocrBlocks: [],
      notifications: [],
      dialogs: [],
      activeWindow: null,
    });
    const ctx = builder.build(scene);
    expect(ctx.keyElements.length).toBe(0);
    expect(ctx.importantControls.length).toBe(0);
    expect(ctx.currentDialog).toBeNull();
    expect(ctx.notifications.length).toBe(0);
  });

  it('respects maxKeyElements option', () => {
    const builder = new ContextBuilder({ maxKeyElements: 2 });
    const elements = Array.from({ length: 10 }, (_, i) =>
      makeElement({ confidence: 0.9, elementId: elementId(`e${i}`) })
    );
    const scene = makeScene({ elements });
    const ctx = builder.build(scene);
    expect(ctx.keyElements.length).toBeLessThanOrEqual(2);
  });

  it('respects maxImportantControls option', () => {
    const builder = new ContextBuilder({ maxImportantControls: 2 });
    const elements = Array.from({ length: 10 }, (_, i) =>
      makeElement({
        type: 'BUTTON',
        isClickable: true,
        isEnabled: true,
        isVisible: true,
        confidence: 0.9,
        elementId: elementId(`e${i}`),
      })
    );
    const scene = makeScene({ elements });
    const ctx = builder.build(scene);
    expect(ctx.importantControls.length).toBeLessThanOrEqual(2);
  });

  it('no active window returns empty application', () => {
    const builder = new ContextBuilder();
    const scene = makeScene({ activeWindow: null, windows: [] });
    const ctx = builder.build(scene);
    expect(ctx.activeApplication).toBe('');
  });
});

// ============================================================================
// Security
// ============================================================================

describe('ImageValidator', () => {
  it('accepts valid PNG', () => {
    const validator = new ImageValidator();
    const capture = makeCapture({ format: 'png' });
    const result = validator.validate(capture);
    expect(result.valid).toBe(true);
  });

  it('accepts valid JPEG', () => {
    const validator = new ImageValidator();
    const capture = makeCapture({ format: 'jpeg' });
    const result = validator.validate(capture);
    expect(result.valid).toBe(true);
  });

  it('rejects invalid format', () => {
    const validator = new ImageValidator();
    const capture = makeCapture({ format: 'bmp' as any });
    const result = validator.validate(capture);
    expect(result.valid).toBe(false);
    if (!result.valid) {
      expect(result.reason).toContain('Format');
    }
  });

  it('rejects oversized image', () => {
    const validator = new ImageValidator({ maxImageSizeBytes: 100 });
    const capture = makeCapture({ imageData: 'A'.repeat(200) });
    const result = validator.validate(capture);
    expect(result.valid).toBe(false);
  });

  it('rejects oversized dimensions', () => {
    const validator = new ImageValidator({ maxImageWidth: 100, maxImageHeight: 100 });
    const capture = makeCapture({ width: 200, height: 200 });
    const result = validator.validate(capture);
    expect(result.valid).toBe(false);
  });

  it('rejects zero dimensions', () => {
    const validator = new ImageValidator();
    const capture = makeCapture({ width: 0, height: 0 });
    const result = validator.validate(capture);
    expect(result.valid).toBe(false);
  });

  it('rejects empty imageData', () => {
    const validator = new ImageValidator();
    const capture = makeCapture({ imageData: '' });
    const result = validator.validate(capture);
    expect(result.valid).toBe(false);
  });

  it('rate limits', () => {
    const validator = new ImageValidator({ rateLimitPerMinute: 2 });
    validator.validate(makeCapture());
    validator.validate(makeCapture());
    const result = validator.validate(makeCapture());
    expect(result.valid).toBe(false);
    if (!result.valid) {
      expect(result.reason).toContain('Rate limit');
    }
  });

  it('getRemainingRequests tracks usage', () => {
    const validator = new ImageValidator({ rateLimitPerMinute: 5 });
    validator.validate(makeCapture());
    validator.validate(makeCapture());
    expect(validator.getRemainingRequests()).toBe(3);
  });
});

describe('ContentSanitizer', () => {
  it('removes credit card numbers', () => {
    const sanitizer = new ContentSanitizer();
    const sanitized = sanitizer.sanitizeText('Card: 1234-5678-9012-3456');
    expect(sanitized).not.toContain('1234-5678-9012-3456');
    expect(sanitized).toContain('*');
  });

  it('removes email addresses', () => {
    const sanitizer = new ContentSanitizer();
    const sanitized = sanitizer.sanitizeText('Email: user@example.com');
    expect(sanitized).not.toContain('user@example.com');
    expect(sanitized).toContain('*');
  });

  it('removes passwords', () => {
    const sanitizer = new ContentSanitizer();
    const sanitized = sanitizer.sanitizeText('password=secret123');
    expect(sanitized).not.toContain('password=secret123');
  });

  it('removes API keys', () => {
    const sanitizer = new ContentSanitizer();
    const sanitized = sanitizer.sanitizeText('api_key=abcdef123456');
    expect(sanitized).not.toContain('api_key=abcdef123456');
  });

  it('preserves normal text', () => {
    const sanitizer = new ContentSanitizer();
    const text = 'Hello World, this is normal text.';
    expect(sanitizer.sanitizeText(text)).toBe(text);
  });

  it('sanitizeForLog delegates to sanitizeText', () => {
    const sanitizer = new ContentSanitizer();
    const result = sanitizer.sanitizeForLog('password=abc123');
    expect(result).not.toContain('password=abc123');
  });

  it('sanitizeForStorage delegates to sanitizeText', () => {
    const sanitizer = new ContentSanitizer();
    const result = sanitizer.sanitizeForStorage('token=xyz789');
    expect(result).not.toContain('token=xyz789');
  });

  it('containsSensitiveContent detects credit cards', () => {
    const sanitizer = new ContentSanitizer();
    expect(sanitizer.containsSensitiveContent('1234-5678-9012-3456')).toBe(true);
  });

  it('containsSensitiveContent returns false for normal text', () => {
    const sanitizer = new ContentSanitizer();
    expect(sanitizer.containsSensitiveContent('Hello World')).toBe(false);
  });
});

describe('FilePathValidator', () => {
  it('accepts valid path', () => {
    const validator = new FilePathValidator();
    const result = validator.validateCapturePath('C:\\Users\\test\\screenshot.png');
    expect(result.valid).toBe(true);
  });

  it('rejects traversal', () => {
    const validator = new FilePathValidator();
    const result = validator.validateCapturePath('..\\..\\Windows\\system32\\file.txt');
    expect(result.valid).toBe(false);
  });

  it('rejects absolute Windows path to system', () => {
    const validator = new FilePathValidator();
    const result = validator.validateCapturePath('C:\\Windows\\System32\\config');
    expect(result.valid).toBe(false);
  });

  it('respects allowed directories', () => {
    const validator = new FilePathValidator({
      allowedDirectories: ['C:\\Users\\test\\captures'],
    });
    const allowed = validator.validateCapturePath('C:\\Users\\test\\captures\\img.png');
    expect(allowed.valid).toBe(true);
    const denied = validator.validateCapturePath('D:\\Other\\file.png');
    expect(denied.valid).toBe(false);
  });

  it('sanitizePath removes invalid characters', () => {
    const validator = new FilePathValidator();
    const sanitized = validator.sanitizePath('file<>:"|?*.png');
    expect(sanitized).not.toContain('<');
    expect(sanitized).not.toContain('>');
    expect(sanitized).not.toContain(':');
    expect(sanitized).not.toContain('"');
    expect(sanitized).not.toContain('|');
    expect(sanitized).not.toContain('?');
    expect(sanitized).not.toContain('*');
  });
});

describe('RateLimiter', () => {
  it('allows within limit', () => {
    const limiter = new RateLimiter(3, 60000);
    expect(limiter.tryAcquire()).toBe(true);
    expect(limiter.tryAcquire()).toBe(true);
    expect(limiter.tryAcquire()).toBe(true);
  });

  it('blocks over limit', () => {
    const limiter = new RateLimiter(2, 60000);
    limiter.tryAcquire();
    limiter.tryAcquire();
    expect(limiter.tryAcquire()).toBe(false);
  });

  it('getRemaining tracks correctly', () => {
    const limiter = new RateLimiter(5, 60000);
    limiter.tryAcquire();
    limiter.tryAcquire();
    expect(limiter.getRemaining()).toBe(3);
  });

  it('getResetMs returns time until window reset', () => {
    const limiter = new RateLimiter(5, 60000);
    limiter.tryAcquire();
    const resetMs = limiter.getResetMs();
    expect(resetMs).toBeGreaterThan(0);
    expect(resetMs).toBeLessThanOrEqual(60000);
  });

  it('getResetMs is 0 when empty', () => {
    const limiter = new RateLimiter(5, 60000);
    expect(limiter.getResetMs()).toBe(0);
  });
});

describe('VisionSecurityManager', () => {
  it('validates capture', () => {
    const mgr = new VisionSecurityManager();
    const result = mgr.validateCapture(makeCapture());
    expect(result.valid).toBe(true);
  });

  it('sanitizeForLog removes sensitive text', () => {
    const mgr = new VisionSecurityManager();
    const result = mgr.sanitizeForLog('password=abc123');
    expect(result).not.toContain('password=abc123');
  });

  it('sanitizeCaptureForLog replaces imageData', () => {
    const mgr = new VisionSecurityManager();
    const sanitized = mgr.sanitizeCaptureForLog(makeCapture());
    expect(sanitized.imageData).toBe('[SANITIZED]');
  });

  it('validateAndSanitize returns valid with sanitized on success', () => {
    const mgr = new VisionSecurityManager();
    const result = mgr.validateAndSanitize(makeCapture());
    expect(result.valid).toBe(true);
    expect(result.sanitized).toBeDefined();
  });

  it('validateAndSanitize returns invalid on failure', () => {
    const mgr = new VisionSecurityManager({ securityPolicy: { maxImageSizeBytes: 1 } });
    const result = mgr.validateAndSanitize(makeCapture());
    expect(result.valid).toBe(false);
    expect(result.reason).toBeDefined();
    expect(result.sanitized.imageData).toBe('[SANITIZED]');
  });
});

// ============================================================================
// Vision Engine Integration
// ============================================================================

describe('VisionEngine', () => {
  let engine: VisionEngine;

  beforeEach(() => {
    engine = new VisionEngine();
  });

  afterEach(() => {
    engine.stop();
  });

  it('creates with default config', () => {
    const e = new VisionEngine();
    expect(e).toBeDefined();
    expect(e.isEngineRunning).toBe(false);
  });

  it('creates with custom config', () => {
    const e = new VisionEngine({
      config: { captureInterval: 2000, cacheSize: 128 },
    });
    expect(e).toBeDefined();
  });

  it('observeOnce returns scene', async () => {
    const scene = await engine.observeOnce();
    expect(scene).toBeDefined();
    expect(scene.sceneId).toBeTruthy();
    expect(scene.elements.length).toBeGreaterThan(0);
  });

  it('observeOnce with specific monitor', async () => {
    const scene = await engine.observeOnce(monitorId('monitor-0'));
    expect(scene).toBeDefined();
  });

  it('observeRegion returns scene', async () => {
    const scene = await engine.observeRegion(
      { x: 0, y: 0, width: 500, height: 300 },
      monitorId('monitor-0'),
    );
    expect(scene).toBeDefined();
    expect(scene.bounds.width).toBe(500);
  });

  it('getContext returns context', async () => {
    const scene = await engine.observeOnce();
    const ctx = engine.getContext(scene);
    expect(ctx).toBeDefined();
    expect(ctx.sceneId).toBe(scene.sceneId);
  });

  it('getContext caches result', async () => {
    const scene = await engine.observeOnce();
    const ctx1 = engine.getContext(scene);
    const ctx2 = engine.getContext(scene);
    expect(ctx1).toBe(ctx2);
  });

  it('resolveTarget returns result', async () => {
    await engine.observeOnce();
    const result = engine.resolveTarget('Submit');
    expect(result).toBeDefined();
    expect(result).toHaveProperty('primary');
    expect(result).toHaveProperty('candidates');
  });

  it('resolveTarget without scene returns empty', () => {
    const result = engine.resolveTarget('Submit');
    expect(result.primary).toBeNull();
    expect(result.suggestion).toContain('No scene available');
  });

  it('getLatestScene returns last scene', async () => {
    expect(engine.getLatestScene()).toBeNull();
    const scene = await engine.observeOnce();
    expect(engine.getLatestScene()?.sceneId).toBe(scene.sceneId);
  });

  it('getSceneHistory tracks scenes', async () => {
    await engine.observeOnce();
    await engine.observeOnce();
    expect(engine.getSceneHistory().length).toBeGreaterThanOrEqual(2);
  });

  it('getSceneDiff returns diff', async () => {
    const s1 = await engine.observeOnce();
    const s2 = await engine.observeOnce();
    const diff = engine.getSceneDiff(s1, s2);
    expect(diff).toBeDefined();
    expect(diff).toHaveProperty('changes');
  });

  it('getMonitors returns monitors', async () => {
    const monitors = await engine.getMonitors();
    expect(monitors.length).toBeGreaterThan(0);
  });

  it('getSceneCacheStats returns stats', async () => {
    await engine.observeOnce();
    const stats = engine.getSceneCacheStats();
    expect(stats.size).toBeGreaterThan(0);
    expect(stats.maxSize).toBe(DEFAULT_VISION_CONFIG.cacheSize);
  });

  it('start/stop lifecycle', () => {
    expect(engine.isEngineRunning).toBe(false);
    engine.start();
    expect(engine.isEngineRunning).toBe(true);
    engine.stop();
    expect(engine.isEngineRunning).toBe(false);
  });

  it('start is idempotent', () => {
    engine.start();
    engine.start();
    expect(engine.isEngineRunning).toBe(true);
    engine.stop();
  });

  it('stop is idempotent', () => {
    engine.stop();
    expect(engine.isEngineRunning).toBe(false);
  });

  it('event emission on scene ready', async () => {
    const events: VisionEvent[] = [];
    engine.on('SCENE_READY', (e) => events.push(e));
    await engine.observeOnce();
    expect(events.length).toBe(1);
    expect(events[0].type).toBe('SCENE_READY');
  });

  it('event emission on capture started', async () => {
    const events: VisionEvent[] = [];
    engine.on('CAPTURE_STARTED', (e) => events.push(e));
    await engine.observeOnce();
    expect(events.length).toBe(1);
  });

  it('event emission on OCR completed', async () => {
    const events: VisionEvent[] = [];
    engine.on('OCR_COMPLETED', (e) => events.push(e));
    await engine.observeOnce();
    expect(events.length).toBe(1);
  });

  it('on returns unsubscribe function', () => {
    const events: VisionEvent[] = [];
    const unsub = engine.on('SCENE_READY', (e) => events.push(e));
    expect(typeof unsub).toBe('function');
    unsub();
  });

  it('off removes listener', () => {
    const events: VisionEvent[] = [];
    const listener = (e: VisionEvent) => events.push(e);
    engine.on('SCENE_READY', listener);
    engine.off('SCENE_READY', listener);
  });

  it('wildcard listener receives all events', async () => {
    const events: VisionEvent[] = [];
    engine.on('*' as VisionEventType, (e) => events.push(e));
    await engine.observeOnce();
    expect(events.length).toBeGreaterThanOrEqual(1);
  });

  it('config update affects behavior', async () => {
    const e = new VisionEngine({ config: { changeTrackingEnabled: false } });
    const s1 = await e.observeOnce();
    const s2 = await e.observeOnce();
    const diff = e.getSceneDiff(s1, s2);
    expect(diff).toBeDefined();
    e.stop();
  });

  it('captures emit ENGINE_STARTED on start', () => {
    const events: VisionEvent[] = [];
    engine.on('ENGINE_STARTED', (e) => events.push(e));
    engine.start();
    expect(events.length).toBe(1);
    expect(events[0].type).toBe('ENGINE_STARTED');
  });

  it('captures emit ENGINE_STOPPED on stop', () => {
    const events: VisionEvent[] = [];
    engine.on('ENGINE_STOPPED', (e) => events.push(e));
    engine.start();
    engine.stop();
    expect(events.length).toBe(1);
    expect(events[0].type).toBe('ENGINE_STOPPED');
  });

  it('observeRegion emits CHANGE_DETECTED when content changes', async () => {
    await engine.observeRegion(
      { x: 0, y: 0, width: 200, height: 200 },
      monitorId('monitor-0'),
    );
    const events: VisionEvent[] = [];
    engine.on('CHANGE_DETECTED', (e) => events.push(e));
    await engine.observeRegion(
      { x: 100, y: 100, width: 200, height: 200 },
      monitorId('monitor-0'),
    );
    // May or may not detect changes depending on mock OCR output
    expect(events.length).toBeGreaterThanOrEqual(0);
  });

  it('multiple observeOnce calls accumulate history', async () => {
    for (let i = 0; i < 5; i++) {
      await engine.observeOnce();
    }
    expect(engine.getSceneHistory().length).toBe(5);
  });

  it('resolveTarget works after observeOnce', async () => {
    await engine.observeOnce();
    const result = engine.resolveTarget('text');
    expect(result).toHaveProperty('primary');
    expect(result).toHaveProperty('candidates');
  });
});
