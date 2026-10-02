// ============================================================================
// MYRAA Computer Control — Comprehensive Test Suite
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  toBoundingRect, pointInRect, rectOverlap, iou,
  type Vec2, type BoundingBox, type ComputerAction, type UITarget, type ActionType,
  type ScreenInfo, type ComputerEnvironment,
  DEFAULT_AUTOMATION_BUDGET, CLICK_MARGIN, TARGET_STALENESS_MS,
  CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW,
} from '../src/computer/contracts';
import { DPIManager } from '../src/computer/dpi';
import { MouseEngine } from '../src/computer/mouse_engine';
import { KeyboardEngine } from '../src/computer/keyboard_engine';
import { ScrollDragEngine } from '../src/computer/scroll_drag';
import { WindowControl, ApplicationControl } from '../src/computer/window_app_control';
import { VisualTargeter } from '../src/computer/visual_targeting';
import { TargetResolver } from '../src/computer/target_resolution';
import { PolicyEngine } from '../src/computer/policy';
import { TransactionManager } from '../src/computer/transactions';
import { LoopDetector } from '../src/computer/loop_detection';
import { ComputerControlEngine } from '../src/computer/engine';

// ============================================================================
// Helpers
// ============================================================================

function makeTarget(overrides: Partial<UITarget> = {}): UITarget {
  return {
    id: `t_${Math.random().toString(36).slice(2, 8)}`,
    type: 'BUTTON',
    label: 'Submit',
    bounds: { x: 100, y: 200, width: 80, height: 30 },
    clickable: true,
    confidence: 0.9,
    source: 'VISION',
    parent: null,
    windowId: null,
    timestamp: new Date().toISOString(),
    observedAt: new Date().toISOString(),
    screenStateHash: 'hash1',
    ...overrides,
  };
}

function makeAction(overrides: Partial<ComputerAction> = {}): ComputerAction {
  return {
    actionId: `act_${Math.random().toString(36).slice(2, 8)}`,
    type: 'CLICK',
    coordinateSpace: 'SCREEN_ABSOLUTE',
    confidence: 0.9,
    risk: 'SAFE',
    source: 'USER_REQUEST',
    reversible: true,
    expectedOutcome: 'Click performed',
    timeout: 5000,
    timestamp: new Date().toISOString(),
    dryRun: false,
    ...overrides,
  };
}

function makeScreen(overrides: Partial<ScreenInfo> = {}): ScreenInfo {
  return {
    screenId: 0,
    bounds: { x: 0, y: 0, width: 1920, height: 1080 },
    resolution: { width: 1920, height: 1080 },
    scaleFactor: 1.0,
    dpi: 96,
    orientation: 'LANDSCAPE',
    primary: true,
    workArea: { x: 0, y: 0, width: 1920, height: 1040 },
    ...overrides,
  };
}

function makeEnvironment(overrides: Partial<ComputerEnvironment> = {}): ComputerEnvironment {
  return {
    timestamp: new Date().toISOString(),
    screens: [makeScreen()],
    activeWindow: null,
    windows: [],
    cursorPosition: { x: 960, y: 540 },
    keyboardFocus: null,
    detectedTargets: [],
    stateHash: 'state1',
    ...overrides,
  };
}

// ============================================================================
// Contracts: Geometry Helpers
// ============================================================================

describe('Computer Control Contracts — Geometry', () => {
  it('toBoundingRect computes derived fields', () => {
    const rect = toBoundingRect({ x: 10, y: 20, width: 100, height: 50 });
    expect(rect.right).toBe(110);
    expect(rect.bottom).toBe(70);
    expect(rect.centerX).toBe(60);
    expect(rect.centerY).toBe(45);
  });

  it('pointInRect detects inside point', () => {
    expect(pointInRect({ x: 50, y: 50 }, { x: 0, y: 0, width: 100, height: 100 })).toBe(true);
  });

  it('pointInRect rejects outside point', () => {
    expect(pointInRect({ x: 150, y: 50 }, { x: 0, y: 0, width: 100, height: 100 })).toBe(false);
  });

  it('pointInRect handles edge cases', () => {
    expect(pointInRect({ x: 0, y: 0 }, { x: 0, y: 0, width: 100, height: 100 })).toBe(true);
    expect(pointInRect({ x: 100, y: 100 }, { x: 0, y: 0, width: 100, height: 100 })).toBe(true);
  });

  it('rectOverlap detects overlapping rects', () => {
    expect(rectOverlap(
      { x: 0, y: 0, width: 50, height: 50 },
      { x: 25, y: 25, width: 50, height: 50 },
    )).toBe(true);
  });

  it('rectOverlap rejects non-overlapping rects', () => {
    expect(rectOverlap(
      { x: 0, y: 0, width: 50, height: 50 },
      { x: 100, y: 100, width: 50, height: 50 },
    )).toBe(false);
  });

  it('iou computes 1.0 for identical rects', () => {
    const b = { x: 0, y: 0, width: 100, height: 100 };
    expect(iou(b, b)).toBe(1.0);
  });

  it('iou computes 0.0 for non-overlapping rects', () => {
    expect(iou(
      { x: 0, y: 0, width: 50, height: 50 },
      { x: 100, y: 100, width: 50, height: 50 },
    )).toBe(0);
  });

  it('iou computes partial overlap correctly', () => {
    const overlap = iou(
      { x: 0, y: 0, width: 100, height: 100 },
      { x: 50, y: 50, width: 100, height: 100 },
    );
    expect(overlap).toBeGreaterThan(0);
    expect(overlap).toBeLessThan(1);
  });

  it('CLICK_MARGIN is positive', () => {
    expect(CLICK_MARGIN).toBeGreaterThan(0);
  });

  it('TARGET_STALENESS_MS is reasonable', () => {
    expect(TARGET_STALENESS_MS).toBeGreaterThanOrEqual(10_000);
    expect(TARGET_STALENESS_MS).toBeLessThanOrEqual(60_000);
  });

  it('CONFIDENCE thresholds are ordered', () => {
    expect(CONFIDENCE_HIGH).toBeGreaterThan(CONFIDENCE_MEDIUM);
    expect(CONFIDENCE_MEDIUM).toBeGreaterThan(CONFIDENCE_LOW);
  });
});

// ============================================================================
// DPI Manager
// ============================================================================

describe('DPIManager', () => {
  let dpi: DPIManager;

  beforeEach(() => {
    dpi = new DPIManager();
  });

  it('calibrates screen and stores calibration', () => {
    const cal = dpi.calibrateScreen(makeScreen());
    expect(cal.calibrated).toBe(true);
    expect(cal.screenId).toBe(0);
    expect(dpi.getCalibration(0)).toBeDefined();
  });

  it('returns undefined for unknown screen', () => {
    expect(dpi.getCalibration(99)).toBeUndefined();
  });

  it('screenToMouse returns same point when not calibrated', () => {
    const p = dpi.screenToMouse({ x: 100, y: 200 }, 99);
    expect(p.x).toBe(100);
    expect(p.y).toBe(200);
  });

  it('screenToMouse scales with calibration', () => {
    dpi.calibrateScreen(makeScreen({ screenId: 1, scaleFactor: 1.5 }));
    const p = dpi.screenToMouse({ x: 100, y: 200 }, 1);
    expect(p.x).toBe(150);
    expect(p.y).toBe(300);
  });

  it('mouseToScreen inverses screenToMouse', () => {
    dpi.calibrateScreen(makeScreen({ screenId: 1, scaleFactor: 2.0 }));
    const p = dpi.screenToMouse({ x: 100, y: 200 }, 1);
    const inv = dpi.mouseToScreen(p, 1);
    expect(inv.x).toBe(100);
    expect(inv.y).toBe(200);
  });

  it('windowToScreen adds window offset', () => {
    const p = dpi.windowToScreen({ x: 50, y: 60 }, { x: 200, y: 300, width: 800, height: 600 });
    expect(p.x).toBe(250);
    expect(p.y).toBe(360);
  });

  it('screenToWindow subtracts window offset', () => {
    const p = dpi.screenToWindow({ x: 250, y: 360 }, { x: 200, y: 300, width: 800, height: 600 });
    expect(p.x).toBe(50);
    expect(p.y).toBe(60);
  });

  it('safeClickPoint stays within bounds with margin', () => {
    const p = dpi.safeClickPoint({ x: 100, y: 200, width: 80, height: 30 }, 4);
    expect(p.x).toBeGreaterThanOrEqual(104);
    expect(p.x).toBeLessThanOrEqual(176);
    expect(p.y).toBeGreaterThanOrEqual(204);
    expect(p.y).toBeLessThanOrEqual(226);
  });

  it('safeClickPoint handles small bounding box', () => {
    const p = dpi.safeClickPoint({ x: 0, y: 0, width: 2, height: 2 }, 4);
    expect(p.x).toBeGreaterThanOrEqual(0);
    expect(p.y).toBeGreaterThanOrEqual(0);
  });

  it('screenContaining finds correct screen', () => {
    const screens = [makeScreen({ screenId: 0 }), makeScreen({ screenId: 1, bounds: { x: 1920, y: 0, width: 1920, height: 1080 } })];
    const found = dpi.screenContaining({ x: 2000, y: 500 }, screens);
    expect(found?.screenId).toBe(1);
  });

  it('screenContaining returns null for point outside all screens', () => {
    const screens = [makeScreen()];
    expect(dpi.screenContaining({ x: 5000, y: 5000 }, screens)).toBeNull();
  });

  it('clampToScreens clamps to nearest screen', () => {
    const screens = [makeScreen()];
    const p = dpi.clampToScreens({ x: 5000, y: 5000 }, screens);
    expect(p.x).toBeLessThanOrEqual(1919);
    expect(p.y).toBeLessThanOrEqual(1079);
  });

  it('clampToScreens returns original if already on screen', () => {
    const screens = [makeScreen()];
    const p = dpi.clampToScreens({ x: 500, y: 500 }, screens);
    expect(p.x).toBe(500);
    expect(p.y).toBe(500);
  });

  it('createTransform returns correct transform', () => {
    dpi.calibrateScreen(makeScreen({ screenId: 1, scaleFactor: 1.5 }));
    const t = dpi.createTransform({
      fromSpace: 'SCREEN_ABSOLUTE',
      toSpace: 'WINDOW_RELATIVE',
      screenId: 1,
      windowBounds: { x: 100, y: 200, width: 800, height: 600 },
    });
    expect(t.dpiScale).toBe(1.5);
    expect(t.windowOffset.x).toBe(100);
    expect(t.windowOffset.y).toBe(200);
  });
});

// ============================================================================
// Mouse Engine
// ============================================================================

describe('MouseEngine', () => {
  let dpi: DPIManager;
  let mouse: MouseEngine;
  let screens: ScreenInfo[];

  beforeEach(() => {
    dpi = new DPIManager();
    mouse = new MouseEngine(dpi);
    screens = [makeScreen()];
    dpi.calibrateScreen(makeScreen());
  });

  it('executes CLICK with coordinates', async () => {
    const action = makeAction({
      type: 'CLICK',
      coordinates: { x: 500, y: 300 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
    });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
    expect(result.executedAt.x).toBe(500);
    expect(result.executedAt.y).toBe(300);
  });

  it('executes DOUBLE_CLICK with target', async () => {
    const target = makeTarget();
    const action = makeAction({ type: 'DOUBLE_CLICK', target });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
  });

  it('executes RIGHT_CLICK with target', async () => {
    const target = makeTarget();
    const action = makeAction({ type: 'RIGHT_CLICK', target });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
  });

  it('fails without target or coordinates', async () => {
    const action = makeAction({ type: 'CLICK' });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(false);
    expect(result.error).toContain('No target or coordinates');
  });

  it('respects automation pause', async () => {
    mouse.pauseAutomation();
    const action = makeAction({ type: 'CLICK', coordinates: { x: 100, y: 100 }, coordinateSpace: 'SCREEN_ABSOLUTE' });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(false);
    expect(result.error).toContain('paused');
  });

  it('resumes after pause', async () => {
    mouse.pauseAutomation();
    mouse.resumeAutomation();
    const action = makeAction({ type: 'CLICK', coordinates: { x: 100, y: 100 }, coordinateSpace: 'SCREEN_ABSOLUTE' });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
  });

  it('emergency stop releases all', () => {
    mouse.releaseAll();
    const state = mouse.getInputState();
    expect(state.heldKeys).toHaveLength(0);
    expect(state.heldMouseButtons).toHaveLength(0);
  });

  it('getInputState returns current state', () => {
    const state = mouse.getInputState();
    expect(state).toHaveProperty('heldKeys');
    expect(state).toHaveProperty('heldMouseButtons');
    expect(state).toHaveProperty('automationOwnsMouse');
  });

  it('getTakeoverState returns takeover info', () => {
    const state = mouse.getTakeoverState();
    expect(state).toHaveProperty('detected');
    expect(state).toHaveProperty('policy');
  });

  it('resolves target position from SCREEN_ABSOLUTE', async () => {
    const target = makeTarget({ bounds: { x: 100, y: 200, width: 80, height: 30 } });
    const action = makeAction({ type: 'CLICK', target, coordinateSpace: 'SCREEN_ABSOLUTE' });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
    expect(result.executedAt.x).toBe(140);
    expect(result.executedAt.y).toBe(215);
  });

  it('resolves target position from ELEMENT_RELATIVE', async () => {
    const target = makeTarget({ bounds: { x: 100, y: 200, width: 80, height: 30 } });
    const action = makeAction({ type: 'CLICK', target, coordinateSpace: 'ELEMENT_RELATIVE' });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
  });

  it('clamps coordinates to screen bounds', async () => {
    const action = makeAction({ type: 'CLICK', coordinates: { x: 5000, y: 5000 }, coordinateSpace: 'SCREEN_ABSOLUTE' });
    const result = await mouse.execute(action, screens);
    expect(result.success).toBe(true);
    expect(result.executedAt.x).toBeLessThanOrEqual(1919);
    expect(result.executedAt.y).toBeLessThanOrEqual(1079);
  });
});

// ============================================================================
// Keyboard Engine
// ============================================================================

describe('KeyboardEngine', () => {
  let kb: KeyboardEngine;

  beforeEach(() => {
    kb = new KeyboardEngine();
  });

  it('executes KEY_PRESS', async () => {
    const action = makeAction({ type: 'KEY_PRESS', keys: ['enter'] });
    const result = await kb.execute(action);
    expect(result.success).toBe(true);
    expect(result.keys).toEqual(['enter']);
  });

  it('executes HOTKEY', async () => {
    const action = makeAction({ type: 'HOTKEY', keys: ['ctrl', 'c'] });
    const result = await kb.execute(action);
    expect(result.success).toBe(true);
    expect(result.keys).toEqual(['ctrl', 'c']);
  });

  it('executes TYPE_TEXT', async () => {
    const action = makeAction({ type: 'TYPE_TEXT', text: 'hello world' });
    const result = await kb.execute(action);
    expect(result.success).toBe(true);
    expect(result.text).toBe('hello world');
  });

  it('executes PASTE_TEXT', async () => {
    const action = makeAction({ type: 'PASTE_TEXT', text: 'pasted' });
    const result = await kb.execute(action);
    expect(result.success).toBe(true);
    expect(result.text).toBe('pasted');
  });

  it('rejects unknown keyboard action', async () => {
    const action = makeAction({ type: 'CLICK' as any });
    const result = await kb.execute(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('Unknown keyboard action');
  });

  it('getHeldKeys returns current held keys', async () => {
    expect(kb.getHeldKeys()).toHaveLength(0);
    await kb.execute(makeAction({ type: 'KEY_PRESS', keys: ['shift'] }));
    expect(kb.getHeldKeys()).toHaveLength(0); // Released after press
  });

  it('releaseAllKeys clears state', async () => {
    await kb.execute(makeAction({ type: 'HOTKEY', keys: ['ctrl', 'alt', 'del'] }));
    kb.releaseAllKeys();
    expect(kb.getHeldKeys()).toHaveLength(0);
  });

  it('getInputState returns keyboard state', () => {
    const state = kb.getInputState();
    expect(state).toHaveProperty('heldKeys');
    expect(state).toHaveProperty('automationOwnsKeyboard');
  });

  it('isTypingText returns false when not typing', () => {
    expect(kb.isTypingText()).toBe(false);
  });
});

// ============================================================================
// Scroll & Drag Engine
// ============================================================================

describe('ScrollDragEngine', () => {
  let dpi: DPIManager;
  let sd: ScrollDragEngine;

  beforeEach(() => {
    dpi = new DPIManager();
    sd = new ScrollDragEngine(dpi);
  });

  it('scroll succeeds with valid parameters', async () => {
    const action = makeAction({
      type: 'SCROLL',
      coordinates: { x: 500, y: 500 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
      scrollAmount: 3,
      scrollDirection: 'DOWN',
    });
    const result = await sd.scroll(action);
    expect(result.success).toBe(true);
  });

  it('scroll fails without target', async () => {
    const action = makeAction({ type: 'SCROLL', coordinateSpace: 'SCREEN_ABSOLUTE' });
    const result = await sd.scroll(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('No scroll target');
  });

  it('scroll rejects excessive amount', async () => {
    const action = makeAction({
      type: 'SCROLL',
      coordinates: { x: 500, y: 500 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
      scrollAmount: 200,
    });
    const result = await sd.scroll(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('exceeds max');
  });

  it('drag succeeds with valid start and end', async () => {
    const action = makeAction({
      type: 'DRAG',
      coordinates: { x: 100, y: 100 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
      dragDestination: { x: 300, y: 300 },
    });
    const result = await sd.drag(action);
    expect(result.success).toBe(true);
    expect(result.destination).toEqual({ x: 300, y: 300 });
  });

  it('drag fails without destination', async () => {
    const action = makeAction({
      type: 'DRAG',
      coordinates: { x: 100, y: 100 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
    });
    const result = await sd.drag(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('No drag destination');
  });

  it('drag fails with too-short distance', async () => {
    const action = makeAction({
      type: 'DRAG',
      coordinates: { x: 100, y: 100 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
      dragDestination: { x: 101, y: 101 },
    });
    const result = await sd.drag(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('too short');
  });

  it('drag fails with excessive distance', async () => {
    const action = makeAction({
      type: 'DRAG',
      coordinates: { x: 0, y: 0 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
      dragDestination: { x: 50000, y: 50000 },
    });
    const result = await sd.drag(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('exceeds max');
  });

  it('scrollIntoView returns 0 for visible target', async () => {
    const result = await sd.scrollIntoView(
      { x: 100, y: 100, width: 80, height: 30 },
      { x: 0, y: 0, width: 1920, height: 1080 },
      'DOWN',
    );
    expect(result.success).toBe(true);
    expect(result.scrollAmount).toBe(0);
  });

  it('scrollIntoView calculates amount for off-screen target', async () => {
    const result = await sd.scrollIntoView(
      { x: 100, y: 2000, width: 80, height: 30 },
      { x: 0, y: 0, width: 1920, height: 1080 },
      'DOWN',
    );
    expect(result.success).toBe(true);
    expect(result.scrollAmount).toBeGreaterThan(0);
  });
});

// ============================================================================
// Window Control
// ============================================================================

describe('WindowControl', () => {
  let wc: WindowControl;

  beforeEach(() => {
    wc = new WindowControl();
    wc.updateWindows([
      { hwnd: 1, title: 'Test Window', processName: 'test.exe', processId: 100, bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: true, focused: true, zOrder: 0 },
      { hwnd: 2, title: 'Other Window', processName: 'other.exe', processId: 200, bounds: { x: 100, y: 100, width: 600, height: 400 }, state: 'MINIMIZED', visible: true, focused: false, zOrder: 1 },
    ]);
  });

  it('focusWindow succeeds for known window', async () => {
    const result = await wc.focusWindow(1);
    expect(result.success).toBe(true);
  });

  it('focusWindow fails for unknown window', async () => {
    const result = await wc.focusWindow(999);
    expect(result.success).toBe(false);
    expect(result.error).toContain('not found');
  });

  it('minimizeWindow succeeds', async () => {
    const result = await wc.minimizeWindow(1);
    expect(result.success).toBe(true);
  });

  it('maximizeWindow succeeds', async () => {
    const result = await wc.maximizeWindow(1);
    expect(result.success).toBe(true);
  });

  it('restoreWindow succeeds', async () => {
    const result = await wc.restoreWindow(2);
    expect(result.success).toBe(true);
  });

  it('closeWindow succeeds', async () => {
    const result = await wc.closeWindow(1);
    expect(result.success).toBe(true);
  });

  it('findWindowByTitle finds exact match', () => {
    const win = wc.findWindowByTitle('Test Window', true);
    expect(win?.hwnd).toBe(1);
  });

  it('findWindowByTitle finds partial match', () => {
    const win = wc.findWindowByTitle('Test');
    expect(win?.hwnd).toBe(1);
  });

  it('findWindowByTitle returns undefined for no match', () => {
    expect(wc.findWindowByTitle('Nonexistent')).toBeUndefined();
  });

  it('findWindowByProcess finds window', () => {
    const win = wc.findWindowByProcess('other');
    expect(win?.hwnd).toBe(2);
  });

  it('getFocusedWindow returns focused window', () => {
    const win = wc.getFocusedWindow();
    expect(win?.hwnd).toBe(1);
  });

  it('getAllWindows returns all', () => {
    expect(wc.getAllWindows()).toHaveLength(2);
  });

  it('getWindow returns specific window', () => {
    expect(wc.getWindow(1)?.title).toBe('Test Window');
  });

  it('isStale returns true after interval', () => {
    wc.updateWindows([]);
    // Force stale by backdating
    (wc as any).lastScanAt = Date.now() - 5000;
    expect(wc.isStale()).toBe(true);
  });
});

// ============================================================================
// Application Control
// ============================================================================

describe('ApplicationControl', () => {
  let ac: ApplicationControl;

  beforeEach(() => {
    ac = new ApplicationControl();
    ac.updateApps([
      { name: 'notepad', processName: 'notepad.exe', processId: 100, executablePath: 'C:\\Windows\\notepad.exe', hwnd: 1, windowTitle: 'Untitled', readiness: 'READY', hasAdapter: false },
    ]);
  });

  it('openApp succeeds', async () => {
    const result = await ac.openApp('notepad');
    expect(result.success).toBe(true);
  });

  it('closeApp succeeds for running app', async () => {
    const result = await ac.closeApp('notepad');
    expect(result.success).toBe(true);
  });

  it('closeApp fails for non-running app', async () => {
    const result = await ac.closeApp('nonexistent');
    expect(result.success).toBe(false);
    expect(result.error).toContain('not running');
  });

  it('getAppInfo returns app', async () => {
    const info = await ac.getAppInfo('notepad');
    expect(info?.processId).toBe(100);
  });

  it('isAppReady returns true for ready app', async () => {
    expect(await ac.isAppReady('notepad')).toBe(true);
  });

  it('getRunningApps returns running apps', () => {
    expect(ac.getRunningApps()).toHaveLength(1);
  });
});

// ============================================================================
// Visual Targeter
// ============================================================================

describe('VisualTargeter', () => {
  let vt: VisualTargeter;

  beforeEach(() => {
    vt = new VisualTargeter();
  });

  it('findTarget finds matching target', async () => {
    const targets = [
      makeTarget({ id: '1', label: 'Submit', confidence: 0.9, source: 'VISION' }),
      makeTarget({ id: '2', label: 'Cancel', confidence: 0.8, source: 'OCR' }),
    ];
    const result = await vt.findTarget('Submit', targets);
    expect(result.targets.length).toBeGreaterThan(0);
    expect(result.targets[0].label).toBe('Submit');
  });

  it('findTarget returns empty for no match', async () => {
    const result = await vt.findTarget('Nonexistent', []);
    expect(result.targets).toHaveLength(0);
  });

  it('findTarget respects minConfidence', async () => {
    const targets = [makeTarget({ confidence: 0.2 })];
    const result = await vt.findTarget('Submit', targets, { minConfidence: 0.5 });
    expect(result.targets).toHaveLength(0);
  });

  it('findTargetByOCR finds text match', async () => {
    const targets = [
      makeTarget({ id: '1', text: 'Login', confidence: 0.9, source: 'OCR' }),
      makeTarget({ id: '2', text: 'Register', confidence: 0.8, source: 'OCR' }),
    ];
    const result = await vt.findTargetByOCR('Login', targets);
    expect(result.targets.length).toBeGreaterThan(0);
    expect(result.method).toBe('OCR');
  });

  it('findTargetByOCR supports fuzzy matching', async () => {
    const targets = [makeTarget({ text: 'Sign In Button', confidence: 0.9, source: 'OCR' })];
    const result = await vt.findTargetByOCR('Sign In', targets, { fuzzy: true });
    expect(result.targets.length).toBeGreaterThan(0);
  });

  it('findTargetByTemplate finds by IoU', async () => {
    const targets = [makeTarget({ bounds: { x: 50, y: 50, width: 100, height: 100 } })];
    const result = await vt.findTargetByTemplate({ x: 60, y: 60, width: 80, height: 80 }, targets);
    expect(result.targets.length).toBeGreaterThan(0);
  });

  it('findTargetsInRegion filters by region', () => {
    const targets = [
      makeTarget({ bounds: { x: 10, y: 10, width: 50, height: 50 } }),
      makeTarget({ bounds: { x: 200, y: 200, width: 50, height: 50 } }),
    ];
    const found = vt.findTargetsInRegion({ x: 0, y: 0, width: 100, height: 100 }, targets);
    expect(found.length).toBe(1);
  });

  it('findTargetsNear finds nearby targets', () => {
    const targets = [
      makeTarget({ bounds: { x: 95, y: 95, width: 10, height: 10 } }),
      makeTarget({ bounds: { x: 500, y: 500, width: 10, height: 10 } }),
    ];
    const found = vt.findTargetsNear({ x: 100, y: 100 }, targets, 50);
    expect(found.length).toBe(1);
  });

  it('updateTargets stores targets', () => {
    vt.updateTargets([makeTarget()], 'hash1');
    expect(vt.getCachedTargets()).toHaveLength(1);
  });

  it('clearCache removes all targets', () => {
    vt.updateTargets([makeTarget()], 'hash1');
    vt.clearCache();
    expect(vt.getCachedTargets()).toHaveLength(0);
  });

  it('isCacheStale returns true after interval', () => {
    vt.updateTargets([], 'h');
    (vt as any).lastScanAt = Date.now() - 5000;
    expect(vt.isCacheStale()).toBe(true);
  });
});

// ============================================================================
// Target Resolver
// ============================================================================

describe('TargetResolver', () => {
  let tr: TargetResolver;

  beforeEach(() => {
    tr = new TargetResolver();
  });

  it('resolves exact text match', () => {
    const targets = [
      makeTarget({ id: '1', label: 'Submit', text: 'Submit' }),
      makeTarget({ id: '2', label: 'Cancel', text: 'Cancel' }),
    ];
    const result = tr.resolve('Submit', targets);
    expect(result.target?.id).toBe('1');
    expect(result.strategy).toBe('EXACT_TEXT');
    expect(result.confidence).toBeGreaterThan(0.8);
  });

  it('resolves fuzzy text match', () => {
    const targets = [
      makeTarget({ id: '1', label: 'Sign In Button' }),
      makeTarget({ id: '2', label: 'Register' }),
    ];
    const result = tr.resolve('Sign In', targets);
    expect(result.target?.id).toBe('1');
    expect(result.strategy).toBe('FUZZY_TEXT');
  });

  it('resolves ordinal match', () => {
    const targets = [
      makeTarget({ id: '1', label: 'Alpha', clickable: true }),
      makeTarget({ id: '2', label: 'Beta', clickable: true }),
      makeTarget({ id: '3', label: 'Gamma', clickable: true }),
    ];
    const result = tr.resolve('second', targets);
    expect(result.target?.id).toBe('2');
    expect(result.strategy).toBe('ORDINAL');
  });

  it('resolves last ordinal', () => {
    const targets = [
      makeTarget({ id: '1', label: 'Alpha', clickable: true }),
      makeTarget({ id: '2', label: 'Beta', clickable: true }),
      makeTarget({ id: '3', label: 'Gamma', clickable: true }),
    ];
    const result = tr.resolve('last', targets);
    expect(result.target?.id).toBe('3');
  });

  it('resolves Hinglish ordinal', () => {
    const targets = [
      makeTarget({ id: '1', label: 'Alpha', clickable: true }),
      makeTarget({ id: '2', label: 'Beta', clickable: true }),
      makeTarget({ id: '3', label: 'Gamma', clickable: true }),
    ];
    const result = tr.resolve('teesra', targets);
    expect(result.target?.id).toBe('3');
  });

  it('returns null for no match', () => {
    const result = tr.resolve('Nonexistent', []);
    expect(result.target).toBeNull();
    expect(result.confidence).toBe(0);
  });

  it('returns alternatives for ambiguous match', () => {
    const targets = [
      makeTarget({ id: '1', label: 'Submit', text: 'Submit' }),
      makeTarget({ id: '2', label: 'Submit Form', text: 'Submit' }),
    ];
    const result = tr.resolve('Submit', targets);
    expect(result.alternatives.length).toBeGreaterThan(0);
  });

  it('getAvailableStrategies returns all strategies', () => {
    const strategies = tr.getAvailableStrategies();
    expect(strategies).toContain('EXACT_TEXT');
    expect(strategies).toContain('FUZZY_TEXT');
    expect(strategies).toContain('ORDINAL');
  });
});

// ============================================================================
// Policy Engine
// ============================================================================

describe('PolicyEngine', () => {
  let pe: PolicyEngine;
  let budget: typeof DEFAULT_AUTOMATION_BUDGET;

  beforeEach(() => {
    pe = new PolicyEngine();
    budget = { ...DEFAULT_AUTOMATION_BUDGET };
  });

  it('approves safe action within budget', () => {
    const action = makeAction({ type: 'CLICK', risk: 'SAFE', confidence: 0.9 });
    const decision = pe.evaluate(action, { budget, recentActions: [], takeoverActive: false });
    expect(decision.approved).toBe(true);
    expect(decision.risk).toBe('SAFE');
  });

  it('blocks action when budget exceeded', () => {
    const overBudget = { ...budget, withinBudget: false };
    const action = makeAction();
    const decision = pe.evaluate(action, { budget: overBudget, recentActions: [], takeoverActive: false });
    expect(decision.approved).toBe(false);
    expect(decision.blockedBy).toBe('BUDGET');
  });

  it('blocks action during takeover', () => {
    const action = makeAction();
    const decision = pe.evaluate(action, { budget, recentActions: [], takeoverActive: true });
    expect(decision.approved).toBe(false);
    expect(decision.blockedBy).toBe('TAKEOVER');
  });

  it('requires approval for CLOSE_APP', () => {
    const action = makeAction({ type: 'CLOSE_APP' });
    const decision = pe.evaluate(action, { budget, recentActions: [], takeoverActive: false });
    expect(decision.requiresApproval).toBe(true);
  });

  it('blocks low confidence action', () => {
    const action = makeAction({ confidence: 0.1 });
    const decision = pe.evaluate(action, { budget, recentActions: [], takeoverActive: false });
    expect(decision.approved).toBe(false);
  });

  it('assessRisk returns correct risk levels', () => {
    expect(pe.assessRisk(makeAction({ type: 'CLOSE_APP' }))).toBe('HIGH');
    expect(pe.assessRisk(makeAction({ type: 'TYPE_TEXT' }))).toBe('MODERATE');
    expect(pe.assessRisk(makeAction({ type: 'CLICK' }))).toBe('SAFE');
  });

  it('addRule and removeRule work', () => {
    const rule = { id: 'test', name: 'Test', description: 'Test rule', condition: () => false, risk: 'SAFE' as const, requiresApproval: false };
    pe.addRule(rule);
    expect(pe.getRules().some(r => r.id === 'test')).toBe(true);
    pe.removeRule('test');
    expect(pe.getRules().some(r => r.id === 'test')).toBe(false);
  });

  it('recordApproval and isApproved work', () => {
    pe.recordApproval('act1', true);
    expect(pe.isApproved('act1')).toBe(true);
    expect(pe.isApproved('act2')).toBe(false);
  });
});

// ============================================================================
// Transaction Manager
// ============================================================================

describe('TransactionManager', () => {
  let tm: TransactionManager;

  beforeEach(() => {
    tm = new TransactionManager();
  });

  it('creates transaction with steps', () => {
    const actions = [makeAction(), makeAction()];
    const tx = tm.createTransaction(actions);
    expect(tx.steps).toHaveLength(2);
    expect(tx.status).toBe('PENDING');
  });

  it('executes transaction successfully', async () => {
    const actions = [makeAction(), makeAction()];
    const tx = tm.createTransaction(actions);
    const result = await tm.executeTransaction(tx.transactionId, async () => ({
      actionId: 'test',
      method: 'STATE_CHECK',
      expected: 'ok',
      actual: 'ok',
      passed: true,
      confidence: 0.9,
      timestamp: new Date().toISOString(),
      latencyMs: 10,
    }));
    expect(result.status).toBe('COMPLETED');
    expect(result.steps.every(s => s.status === 'COMPLETED')).toBe(true);
  });

  it('fails transaction on step failure', async () => {
    const actions = [makeAction(), makeAction()];
    const tx = tm.createTransaction(actions);
    let callCount = 0;
    const result = await tm.executeTransaction(tx.transactionId, async () => {
      callCount++;
      return {
        actionId: 'test',
        method: 'STATE_CHECK',
        expected: 'ok',
        actual: callCount === 1 ? 'ok' : 'failed',
        passed: callCount === 1,
        confidence: 0.9,
        timestamp: new Date().toISOString(),
        latencyMs: 10,
      };
    });
    expect(result.status).toBe('FAILED');
  });

  it('rollback reverses completed steps', async () => {
    const actions = [makeAction({ reversible: true }), makeAction({ reversible: true })];
    const tx = tm.createTransaction(actions);
    await tm.executeTransaction(tx.transactionId, async () => ({
      actionId: 'test', method: 'STATE_CHECK', expected: 'ok', actual: 'ok', passed: true, confidence: 0.9, timestamp: new Date().toISOString(), latencyMs: 10,
    }));
    const rolled = await tm.rollbackTransaction(tx.transactionId, async () => true);
    expect(rolled).toBe(true);
  });

  it('getTransaction returns active or completed', async () => {
    const tx = tm.createTransaction([makeAction()]);
    expect(tm.getTransaction(tx.transactionId)).toBeDefined();
  });

  it('getStats returns correct counts', async () => {
    const tx = tm.createTransaction([makeAction()]);
    await tm.executeTransaction(tx.transactionId, async () => ({
      actionId: 'test', method: 'STATE_CHECK', expected: 'ok', actual: 'ok', passed: true, confidence: 0.9, timestamp: new Date().toISOString(), latencyMs: 10,
    }));
    const stats = tm.getStats();
    expect(stats.completed).toBe(1);
    expect(stats.active).toBe(0);
  });
});

// ============================================================================
// Loop Detector
// ============================================================================

describe('LoopDetector', () => {
  let ld: LoopDetector;

  beforeEach(() => {
    ld = new LoopDetector();
  });

  it('detects repeated action loop', () => {
    for (let i = 0; i < 3; i++) {
      ld.recordAction(makeAction({
        type: 'CLICK',
        coordinates: { x: 100, y: 200 },
        timestamp: new Date().toISOString(),
      }));
    }
    const loop = ld.detectLoop();
    expect(loop).not.toBeNull();
    expect(loop!.count).toBe(3);
  });

  it('returns null when no loop', () => {
    ld.recordAction(makeAction({ type: 'CLICK' }));
    ld.recordAction(makeAction({ type: 'TYPE_TEXT' }));
    ld.recordAction(makeAction({ type: 'HOTKEY' }));
    expect(ld.detectLoop()).toBeNull();
  });

  it('detects stuck state from repeated actions', () => {
    for (let i = 0; i < 5; i++) {
      ld.recordAction(makeAction({ type: 'CLICK', timestamp: new Date().toISOString() }));
    }
    const stuck = ld.detectStuck();
    expect(stuck.detected).toBe(true);
    expect(stuck.stuckType).toBe('REPEATED_ACTION');
  });

  it('detects stuck from repeated failures', () => {
    for (let i = 0; i < 3; i++) {
      ld.recordFailure('TARGET_NOT_FOUND');
    }
    const stuck = ld.detectStuck();
    expect(stuck.detected).toBe(true);
    expect(stuck.stuckType).toBe('REPEATED_FAILURE');
  });

  it('returns not stuck for normal activity', () => {
    ld.recordAction(makeAction({ type: 'CLICK' }));
    ld.recordAction(makeAction({ type: 'TYPE_TEXT' }));
    const stuck = ld.detectStuck();
    expect(stuck.detected).toBe(false);
  });

  it('reset clears history', () => {
    for (let i = 0; i < 5; i++) ld.recordAction(makeAction({ type: 'CLICK' }));
    ld.reset();
    expect(ld.getActionCount()).toBe(0);
    expect(ld.getFailureCount()).toBe(0);
  });

  it('getActionCount tracks correctly', () => {
    ld.recordAction(makeAction());
    ld.recordAction(makeAction());
    expect(ld.getActionCount()).toBe(2);
  });

  it('getFailureCount tracks correctly', () => {
    ld.recordFailure('TIMEOUT');
    expect(ld.getFailureCount()).toBe(1);
  });
});

// ============================================================================
// Computer Control Engine (Integration)
// ============================================================================

describe('ComputerControlEngine', () => {
  let engine: ComputerControlEngine;

  beforeEach(() => {
    engine = new ComputerControlEngine();
    engine.initialize(makeEnvironment());
  });

  it('initializes with environment', () => {
    const state = engine.getState();
    expect(state.initialized).toBe(true);
  });

  it('executes CLICK action', async () => {
    const action = makeAction({
      type: 'CLICK',
      coordinates: { x: 500, y: 300 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
    });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(true);
  });

  it('executes TYPE_TEXT action', async () => {
    const action = makeAction({ type: 'TYPE_TEXT', text: 'hello' });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(true);
  });

  it('executes HOTKEY action', async () => {
    const action = makeAction({ type: 'HOTKEY', keys: ['ctrl', 's'] });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(true);
  });

  it('executes SCROLL action', async () => {
    const action = makeAction({
      type: 'SCROLL',
      coordinates: { x: 500, y: 500 },
      coordinateSpace: 'SCREEN_ABSOLUTE',
      scrollAmount: 3,
      scrollDirection: 'DOWN',
    });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(true);
  });

  it('executes FOCUS_WINDOW action', async () => {
    engine.updateEnvironment(makeEnvironment({
      windows: [{ hwnd: 1, title: 'Test', processName: 'test.exe', processId: 1, bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: true, focused: true, zOrder: 0 }],
    }));
    const action = makeAction({ type: 'FOCUS_WINDOW', windowId: 1 });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(true);
  });

  it('executes OPEN_APP action', async () => {
    const action = makeAction({ type: 'OPEN_APP', text: 'notepad' });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(true);
  });

  it('executes transaction', async () => {
    const actions = [
      makeAction({ type: 'CLICK', coordinates: { x: 100, y: 100 }, coordinateSpace: 'SCREEN_ABSOLUTE' }),
      makeAction({ type: 'TYPE_TEXT', text: 'hello' }),
    ];
    const result = await engine.executeTransaction(actions);
    expect(result.status).toBe('COMPLETED');
    expect(result.stepsCompleted).toBe(2);
  });

  it('updateEnvironment updates state', () => {
    const env = makeEnvironment({ stateHash: 'newhash' });
    engine.updateEnvironment(env);
    expect(engine.getEnvironment()?.stateHash).toBe('newhash');
  });

  it('findTarget resolves target', () => {
    engine.updateEnvironment(makeEnvironment({
      detectedTargets: [makeTarget({ id: '1', label: 'Submit' })],
    }));
    const result = engine.findTarget('Submit');
    expect(result.target?.id).toBe('1');
  });

  it('findTargetVisual finds target', async () => {
    engine.updateEnvironment(makeEnvironment({
      detectedTargets: [makeTarget({ id: '1', label: 'Submit' })],
    }));
    const result = await engine.findTargetVisual('Submit');
    expect(result.targets.length).toBeGreaterThan(0);
  });

  it('getDPICalibration returns calibration', () => {
    const cal = engine.getDPICalibration(0);
    expect(cal).toBeDefined();
    expect(cal?.calibrated).toBe(true);
  });

  it('getPolicyEngine returns policy engine', () => {
    expect(engine.getPolicyEngine()).toBeInstanceOf(PolicyEngine);
  });

  it('pauseForTakeover pauses automation', () => {
    engine.pauseForTakeover();
    const state = engine.getState();
    expect(state.takeover.automationPaused).toBe(true);
  });

  it('resumeAfterTakeover resumes', () => {
    engine.pauseForTakeover();
    engine.resumeAfterTakeover();
    const state = engine.getState();
    expect(state.takeover.automationPaused).toBe(false);
  });

  it('emergencyStop releases everything', () => {
    engine.emergencyStop();
    const state = engine.getState();
    expect(state.inputState.heldKeys).toHaveLength(0);
  });

  it('resetBudget resets budget', () => {
    engine.resetBudget();
    const state = engine.getState();
    expect(state.budget.actionsUsed).toBe(0);
  });

  it('getTelemetry returns action history', async () => {
    await engine.executeAction(makeAction({ type: 'CLICK', coordinates: { x: 100, y: 100 }, coordinateSpace: 'SCREEN_ABSOLUTE' }));
    const telemetry = engine.getTelemetry();
    expect(telemetry.length).toBeGreaterThan(0);
  });

  it('getState returns complete state', () => {
    const state = engine.getState();
    expect(state).toHaveProperty('initialized');
    expect(state).toHaveProperty('budget');
    expect(state).toHaveProperty('takeover');
    expect(state).toHaveProperty('inputState');
    expect(state).toHaveProperty('stuckState');
    expect(state).toHaveProperty('totalActionsExecuted');
  });

  it('blocks action when budget exceeded', async () => {
    engine.resetBudget();
    // Exhaust budget with varied action types to avoid loop detection
    const actionTypes: ActionType[] = ['CLICK', 'TYPE_TEXT', 'HOTKEY', 'SCROLL', 'DOUBLE_CLICK'];
    for (let i = 0; i < 50; i++) {
      const type = actionTypes[i % actionTypes.length];
      await engine.executeAction(makeAction({
        type,
        coordinates: { x: 100 + i * 5, y: 100 + i * 5 },
        coordinateSpace: 'SCREEN_ABSOLUTE',
        text: type === 'TYPE_TEXT' ? 'x' : undefined,
        keys: type === 'HOTKEY' ? ['ctrl', 'a'] : undefined,
        scrollAmount: type === 'SCROLL' ? 3 : undefined,
        scrollDirection: type === 'SCROLL' ? 'DOWN' : undefined,
      }));
    }
    const action = makeAction({ type: 'CLICK', coordinates: { x: 999, y: 999 }, coordinateSpace: 'SCREEN_ABSOLUTE' });
    const result = await engine.executeAction(action);
    expect(result.success).toBe(false);
    expect(result.error).toContain('Budget');
  });

  it('detects loop and blocks', async () => {
    engine.updateEnvironment(makeEnvironment({
      detectedTargets: [makeTarget({ id: '1', bounds: { x: 100, y: 200, width: 80, height: 30 } })],
    }));
    // Execute same action 3 times to trigger loop
    for (let i = 0; i < 3; i++) {
      await engine.executeAction(makeAction({
        type: 'CLICK',
        target: makeTarget({ bounds: { x: 100, y: 200, width: 80, height: 30 } }),
        coordinateSpace: 'SCREEN_ABSOLUTE',
      }));
    }
    const state = engine.getState();
    expect(state.stuckState.detected).toBe(true);
  });
});

// ============================================================================
// Default Constants
// ============================================================================

describe('Default Constants', () => {
  it('DEFAULT_AUTOMATION_BUDGET has reasonable values', () => {
    expect(DEFAULT_AUTOMATION_BUDGET.maxActions).toBeGreaterThan(0);
    expect(DEFAULT_AUTOMATION_BUDGET.maxDuration).toBeGreaterThan(0);
    expect(DEFAULT_AUTOMATION_BUDGET.maxRetries).toBeGreaterThan(0);
    expect(DEFAULT_AUTOMATION_BUDGET.withinBudget).toBe(true);
  });
});
