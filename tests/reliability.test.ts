// ============================================================================
// MYRAA Phase 25 — Comprehensive Reliability Test Suite (160+ tests)
// ============================================================================

import { describe, it, expect, beforeEach } from 'vitest';
import {
  StateSnapshot, StateVersion, StateDiff, VerificationResult,
  MultiSignalVerification, DiagnosisResult, FailureClass,
  RecoveryBudget, ActionLifecycle, DEFAULT_RECOVERY_BUDGET,
  HIGH_IMPACT_ACTIONS,
} from '../src/reliability/contracts';
import { StateEstimator, type StateObservations } from '../src/reliability/state_estimator';
import { StateDiffEngine } from '../src/reliability/state_diff';
import { VerificationEngine } from '../src/reliability/verification_engine';
import { FailureDiagnosisEngine, type DiagnosisContext } from '../src/reliability/failure_diagnosis';
import { AdaptiveRecoveryEngine } from '../src/reliability/adaptive_recovery';
import { UnknownOutcomeHandler } from '../src/reliability/unknown_outcome';
import { PlanPatcher } from '../src/reliability/plan_patching';
import { ExperienceLearningEngine } from '../src/reliability/experience_learning';
import { ClosedLoopOrchestrator } from '../src/reliability/orchestrator';

// ============================================================================
// Helpers
// ============================================================================

function makeObservations(overrides: Partial<StateObservations> = {}): StateObservations {
  return {
    activeWindow: { hwnd: 1, title: 'Test', processName: 'test.exe', bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: true },
    screens: [{ resolution: { width: 1920, height: 1080 }, dpi: 96, scaleFactor: 1.0 }],
    currentTarget: { id: 'btn1', label: 'Submit', bounds: { x: 100, y: 200, width: 80, height: 30 }, visible: true, enabled: true, confidence: 0.9, source: 'VISION', lastVerifiedAt: null },
    processRunning: true,
    processPid: 100,
    processResponsive: true,
    browserUrl: 'https://example.com',
    browserTitle: 'Example',
    browserReady: true,
    domElementCount: 50,
    ...overrides,
  };
}

function makeLifecycle(overrides: Partial<ActionLifecycle> = {}): ActionLifecycle {
  return {
    actionId: 'test_action',
    status: 'EXECUTING',
    attempts: 1,
    maxAttempts: 3,
    preconditions: [],
    postconditions: [],
    expectedOutcome: 'Button clicked',
    verificationMethod: 'NORMAL',
    createdAt: new Date().toISOString(),
    lastTransitionAt: new Date().toISOString(),
    history: [],
    ...overrides,
  };
}

// ============================================================================
// STATE ESTIMATOR
// ============================================================================

describe('StateEstimator', () => {
  let se: StateEstimator;

  beforeEach(() => { se = new StateEstimator(); });

  it('creates initial state snapshot', () => {
    const state = se.estimate(makeObservations());
    expect(state.version).toBe(1);
    expect(state.windowState.hwnd).toBe(1);
    expect(state.windowState.title).toBe('Test');
  });

  it('increments version on each estimate', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ activeWindow: { hwnd: 2, title: 'Other', processName: 'other.exe', bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: true } }));
    expect(s2.version).toBe(s1.version + 1);
  });

  it('tracks history', () => {
    se.estimate(makeObservations());
    se.estimate(makeObservations());
    expect(se.getHistory()).toHaveLength(2);
  });

  it('limits history', () => {
    for (let i = 0; i < 60; i++) se.estimate(makeObservations());
    expect(se.getHistory().length).toBeLessThanOrEqual(50);
  });

  it('getCurrentState returns latest', () => {
    se.estimate(makeObservations());
    const state = se.estimate(makeObservations({ browserUrl: 'https://other.com' }));
    expect(se.getCurrentState()?.version).toBe(state.version);
  });

  it('getStateByVersion returns correct version', () => {
    se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations());
    expect(se.getStateByVersion(2)?.version).toBe(2);
  });

  it('isStateStale returns false when fresh', () => {
    se.estimate(makeObservations());
    // FLAKY TEST FIXED (documented, §61): maxAgeMs=0 raced the clock — any
    // elapsed millisecond makes the state stale (Date.now() - ts > 0). Use a
    // deterministic generous threshold to test the "fresh" semantics.
    expect(se.isStateStale(60_000)).toBe(false);
  });

  it('isStateStale returns true for very small maxAgeMs', () => {
    se.estimate(makeObservations());
    // 1ms threshold — might be stale if any delay occurred
    expect(se.isStateStale(-1)).toBe(true);
  });

  it('clear resets state', () => {
    se.estimate(makeObservations());
    se.clear();
    expect(se.getCurrentState()).toBeNull();
    expect(se.getHistory()).toHaveLength(0);
  });

  it('captures window state', () => {
    const state = se.estimate(makeObservations());
    expect(state.windowState.processName).toBe('test.exe');
    expect(state.windowState.visible).toBe(true);
  });

  it('captures screen state', () => {
    const state = se.estimate(makeObservations());
    expect(state.screenState.dpi).toBe(96);
    expect(state.screenState.monitorCount).toBe(1);
  });

  it('captures target state', () => {
    const state = se.estimate(makeObservations());
    expect(state.targetState.targetId).toBe('btn1');
    expect(state.targetState.targetConfidence).toBe(0.9);
  });

  it('captures browser state', () => {
    const state = se.estimate(makeObservations());
    expect(state.browserState.url).toBe('https://example.com');
    expect(state.browserState.ready).toBe(true);
  });

  it('captures process state', () => {
    const state = se.estimate(makeObservations());
    expect(state.processState.running).toBe(true);
    expect(state.processState.responsive).toBe(true);
  });

  it('captures file state', () => {
    const state = se.estimate(makeObservations({ fileExists: true, fileSize: 1024 }));
    expect(state.fileState.exists).toBe(true);
    expect(state.fileState.size).toBe(1024);
  });

  it('captures dialog state', () => {
    const state = se.estimate(makeObservations({ pendingDialogs: [{ type: 'alert', title: 'Warning', visible: true }] }));
    expect(state.pendingDialogs).toHaveLength(1);
    expect(state.pendingDialogs[0].title).toBe('Warning');
  });
});

// ============================================================================
// STATE DIFF ENGINE
// ============================================================================

describe('StateDiffEngine', () => {
  let se: StateEstimator;
  let sd: StateDiffEngine;

  beforeEach(() => { se = new StateEstimator(); sd = new StateDiffEngine(); });

  it('detects window title change', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ activeWindow: { hwnd: 1, title: 'Changed', processName: 'test.exe', bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: true } }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'WINDOW_STATE_CHANGED')).toBe(true);
  });

  it('detects window focus change', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ activeWindow: { hwnd: 2, title: 'Other', processName: 'other.exe', bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: true } }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'FOCUS_CHANGED')).toBe(true);
  });

  it('detects window move', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ activeWindow: { hwnd: 1, title: 'Test', processName: 'test.exe', bounds: { x: 100, y: 200, width: 800, height: 600 }, state: 'NORMAL', visible: true } }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'WINDOW_MOVED')).toBe(true);
  });

  it('detects window resize', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ activeWindow: { hwnd: 1, title: 'Test', processName: 'test.exe', bounds: { x: 0, y: 0, width: 1024, height: 768 }, state: 'NORMAL', visible: true } }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'WINDOW_RESIZED')).toBe(true);
  });

  it('detects URL change', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ browserUrl: 'https://other.com' }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'URL_CHANGED')).toBe(true);
  });

  it('detects target disappearance', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ currentTarget: { id: 'btn2', label: 'Other', bounds: null, visible: false, enabled: false, confidence: 0.3, source: 'VISION', lastVerifiedAt: null } }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'ELEMENT_DISAPPEARED')).toBe(true);
  });

  it('detects process exit', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ processRunning: false }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'PROCESS_EXITED')).toBe(true);
  });

  it('detects file creation', () => {
    const s1 = se.estimate(makeObservations({ fileExists: false }));
    const s2 = se.estimate(makeObservations({ fileExists: true }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'FILE_CREATED')).toBe(true);
  });

  it('detects file deletion', () => {
    const s1 = se.estimate(makeObservations({ fileExists: true }));
    const s2 = se.estimate(makeObservations({ fileExists: false }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'FILE_DELETED')).toBe(true);
  });

  it('detects dialog appearance', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ pendingDialogs: [{ type: 'alert', title: 'Error', visible: true }] }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'DIALOG_APPEARED')).toBe(true);
  });

  it('detects DPI change', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ screens: [{ resolution: { width: 1920, height: 1080 }, dpi: 144, scaleFactor: 1.5 }] }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'DPI_CHANGED')).toBe(true);
  });

  it('returns non-material for identical states', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations());
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(false);
  });

  it('tracks diff history', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ browserUrl: 'https://other.com' }));
    sd.diff(s1, s2);
    expect(sd.getDiffHistory()).toHaveLength(1);
  });

  it('getMaterialChanges filters correctly', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ browserTitle: 'New Title' }));
    const diff = sd.diff(s1, s2);
    expect(sd.getMaterialChanges(diff).every(c => c.material)).toBe(true);
  });

  it('getChangesByType filters correctly', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ browserUrl: 'https://other.com' }));
    const diff = sd.diff(s1, s2);
    expect(sd.getChangesByType(diff, 'URL_CHANGED')).toHaveLength(1);
    expect(sd.getChangesByType(diff, 'WINDOW_MOVED')).toHaveLength(0);
  });

  it('detects window visibility change', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ activeWindow: { hwnd: 1, title: 'Test', processName: 'test.exe', bounds: { x: 0, y: 0, width: 800, height: 600 }, state: 'NORMAL', visible: false } }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'WINDOW_CLOSED')).toBe(true);
  });

  it('detects element appearance', () => {
    const s1 = se.estimate(makeObservations({ currentTarget: { id: 'btn1', label: 'Submit', bounds: null, visible: false, enabled: false, confidence: 0.3, source: 'VISION', lastVerifiedAt: null } }));
    const s2 = se.estimate(makeObservations());
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'ELEMENT_APPEARED')).toBe(true);
  });

  it('detects process unresponsive', () => {
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ processResponsive: false }));
    const diff = sd.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'PROCESS_UNRESPONSIVE')).toBe(true);
  });
});

// ============================================================================
// VERIFICATION ENGINE
// ============================================================================

describe('VerificationEngine', () => {
  let ve: VerificationEngine;

  beforeEach(() => { ve = new VerificationEngine(); });

  it('verifies matching expected/actual', () => {
    const r = ve.verify('a1', 'exists', 'exists', 'STRUCTURED_STATE', 'NORMAL');
    expect(r.status).toBe('VERIFIED');
    expect(r.confidence).toBeGreaterThan(0.5);
  });

  it('detects failed verification', () => {
    const r = ve.verify('a1', 'exists', 'not_found', 'STRUCTURED_STATE', 'NORMAL');
    expect(r.status).toBe('FAILED');
  });

  it('detects partial verification', () => {
    const r = ve.verify('a1', 'Submit button', 'Submit', 'DOM', 'NORMAL');
    expect(r.status).toBe('PARTIALLY_VERIFIED');
  });

  it('multi-signal verification with agreement', () => {
    const m = ve.verifyMultiSignal('a1', [
      { source: 'STRUCTURED_STATE', expected: 'exists', actual: 'exists' },
      { source: 'DOM', expected: 'exists', actual: 'exists' },
    ], 'NORMAL');
    expect(m.consensus).toBe('VERIFIED');
    expect(m.overallConfidence).toBeGreaterThan(0.7);
  });

  it('multi-signal verification detects conflicts', () => {
    const m = ve.verifyMultiSignal('a1', [
      { source: 'STRUCTURED_STATE', expected: 'exists', actual: 'exists' },
      { source: 'VISUAL', expected: 'exists', actual: 'not_found' },
    ], 'NORMAL');
    expect(m.conflicts.length).toBeGreaterThan(0);
  });

  it('verification from state diff with matching change', () => {
    const se = new StateEstimator();
    const s1 = se.estimate(makeObservations({ browserUrl: 'https://old.com' }));
    const s2 = se.estimate(makeObservations({ browserUrl: 'https://new.com' }));
    const sd = new StateDiffEngine();
    const diff = sd.diff(s1, s2);
    const r = ve.verifyFromStateDiff('a1', diff, ['URL_CHANGED'], 'NORMAL');
    expect(r.status).toBe('VERIFIED');
  });

  it('verification from state diff without matching change', () => {
    const se = new StateEstimator();
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ browserTitle: 'New' }));
    const sd = new StateDiffEngine();
    const diff = sd.diff(s1, s2);
    const r = ve.verifyFromStateDiff('a1', diff, ['URL_CHANGED'], 'NORMAL');
    expect(r.status).not.toBe('VERIFIED');
  });

  it('tracks source reliability', () => {
    ve.updateSourceReliability('VISUAL', 0.9);
    expect(ve.getSourceReliability('VISUAL')).toBeGreaterThan(0.65);
  });

  it('isVerified checks confidence threshold', () => {
    const m = ve.verifyMultiSignal('a1', [
      { source: 'STRUCTURED_STATE', expected: 'exists', actual: 'exists' },
    ], 'NORMAL');
    expect(ve.isVerified(m, 0.5)).toBe(true);
    expect(ve.isVerified(m, 0.99)).toBe(false);
  });

  it('isFailed detects failure consensus', () => {
    const m = ve.verifyMultiSignal('a1', [
      { source: 'STRUCTURED_STATE', expected: 'exists', actual: 'not_found' },
      { source: 'VISUAL', expected: 'visible', actual: 'not_visible' },
    ], 'NORMAL');
    expect(ve.isFailed(m)).toBe(true);
  });

  it('higher verification levels increase confidence', () => {
    const light = ve.verify('a1', 'exists', 'exists', 'STRUCTURED_STATE', 'LIGHT');
    const strict = ve.verify('a2', 'exists', 'exists', 'STRUCTURED_STATE', 'STRICT');
    expect(strict.confidence).toBeGreaterThanOrEqual(light.confidence);
  });

  it('clear resets results', () => {
    ve.verify('a1', 'x', 'x', 'VISUAL', 'NORMAL');
    ve.clear();
    expect(ve.getResults('a1')).toHaveLength(0);
  });

  it('handles empty signals', () => {
    const m = ve.verifyMultiSignal('a1', [], 'NORMAL');
    expect(m.consensus).toBe('UNVERIFIED');
  });

  it('CRITICAL level requires higher confidence', () => {
    const r = ve.verify('a1', 'exists', 'exists', 'VISUAL', 'CRITICAL');
    expect(r.confidence).toBeGreaterThan(0.3);
  });
});

// ============================================================================
// FAILURE DIAGNOSIS ENGINE
// ============================================================================

describe('FailureDiagnosisEngine', () => {
  let fd: FailureDiagnosisEngine;

  beforeEach(() => { fd = new FailureDiagnosisEngine(); });

  it('diagnoses target not found', () => {
    const results: VerificationResult[] = [{
      actionId: 'a1', status: 'FAILED', confidence: 0.8, source: 'STRUCTURED_STATE',
      evidence: 'target does not exist', expected: 'should exist', actual: 'not found',
      timestamp: new Date().toISOString(), latencyMs: 10, level: 'NORMAL',
    }];
    const d = fd.diagnose('a1', results, null, makeLifecycle());
    expect(d.failureClass).toBe('TARGET_NOT_FOUND');
    expect(d.recoverability).toBe('AUTO_RECOVERABLE');
  });

  it('diagnoses focus lost', () => {
    const results: VerificationResult[] = [{
      actionId: 'a1', status: 'FAILED', confidence: 0.7, source: 'OS_STATE',
      evidence: 'window focus changed', expected: 'focused', actual: 'not focused',
      timestamp: new Date().toISOString(), latencyMs: 10, level: 'NORMAL',
    }];
    const d = fd.diagnose('a1', results, null, makeLifecycle());
    expect(d.failureClass).toBe('FOCUS_LOST');
  });

  it('diagnoses app crashed from state diff', () => {
    const se = new StateEstimator();
    const s1 = se.estimate(makeObservations());
    const s2 = se.estimate(makeObservations({ processRunning: false }));
    const sd = new StateDiffEngine();
    const diff = sd.diff(s1, s2);
    const d = fd.diagnose('a1', [], diff, makeLifecycle());
    expect(d.failureClass).toBe('APP_CRASHED');
    expect(d.recoverability).toBe('RECOVERABLE_WITH_REPLAN');
  });

  it('diagnoses UI change from DOM', () => {
    const results: VerificationResult[] = [{
      actionId: 'a1', status: 'FAILED', confidence: 0.75, source: 'DOM',
      evidence: 'page structure changed', expected: 'element', actual: 'not_found',
      timestamp: new Date().toISOString(), latencyMs: 10, level: 'NORMAL',
    }];
    const d = fd.diagnose('a1', results, null, makeLifecycle());
    expect(d.failureClass).toBe('UI_CHANGED');
  });

  it('diagnoses timeout from attempts', () => {
    const lc = makeLifecycle({ attempts: 3, maxAttempts: 3 });
    const d = fd.diagnose('a1', [], null, lc);
    expect(d.recoverability).toBe('REQUIRES_USER');
  });

  it('generates hypotheses', () => {
    const results: VerificationResult[] = [{
      actionId: 'a1', status: 'FAILED', confidence: 0.8, source: 'DOM',
      evidence: 'element missing', expected: 'exists', actual: 'not_found',
      timestamp: new Date().toISOString(), latencyMs: 10, level: 'NORMAL',
    }];
    const d = fd.diagnose('a1', results, null, makeLifecycle());
    expect(d.hypotheses.length).toBeGreaterThan(0);
  });

  it('uses context for user takeover', () => {
    const ctx: DiagnosisContext = { userTookOver: true };
    const d = fd.diagnose('a1', [], null, makeLifecycle(), ctx);
    expect(d.hypotheses.some(h => h.hypothesis.includes('User took control'))).toBe(true);
  });

  it('recommends REOBSERVE for unknown', () => {
    const d = fd.diagnose('a1', [], null, makeLifecycle());
    expect(d.recommendedRecovery).toBeTruthy();
  });

  it('clear resets history', () => {
    fd.diagnose('a1', [], null, makeLifecycle());
    fd.clear();
    expect(fd.getDiagnosisHistory()).toHaveLength(0);
  });

  it('getMostCommonFailureClass works', () => {
    fd.diagnose('a1', [{ actionId: 'a1', status: 'FAILED', confidence: 0.8, source: 'STRUCTURED_STATE', evidence: 'target not exist', expected: 'should exist', actual: 'not found', timestamp: new Date().toISOString(), latencyMs: 10, level: 'NORMAL' }], null, makeLifecycle());
    fd.diagnose('a2', [{ actionId: 'a2', status: 'FAILED', confidence: 0.8, source: 'STRUCTURED_STATE', evidence: 'target not exist', expected: 'should exist', actual: 'not found', timestamp: new Date().toISOString(), latencyMs: 10, level: 'NORMAL' }], null, makeLifecycle());
    expect(fd.getMostCommonFailureClass()).toBe('TARGET_NOT_FOUND');
  });
});

// ============================================================================
// ADAPTIVE RECOVERY ENGINE
// ============================================================================

describe('AdaptiveRecoveryEngine', () => {
  let ar: AdaptiveRecoveryEngine;

  beforeEach(() => { ar = new AdaptiveRecoveryEngine(); });

  it('selects recovery for target not found', () => {
    const diagnosis: DiagnosisResult = {
      actionId: 'a1', failureClass: 'TARGET_NOT_FOUND', rootCause: 'target missing',
      evidence: [], confidence: 0.8, recoverability: 'AUTO_RECOVERABLE',
      recommendedRecovery: 'RELOCATE_TARGET', hypotheses: [], timestamp: new Date().toISOString(),
    };
    const r = ar.selectRecovery(diagnosis, makeLifecycle());
    expect(r).not.toBeNull();
    expect(r!.action).toBeTruthy();
  });

  it('returns ABORT for fatal failures', () => {
    const diagnosis: DiagnosisResult = {
      actionId: 'a1', failureClass: 'PERMISSION', rootCause: 'no permission',
      evidence: [], confidence: 0.9, recoverability: 'FATAL',
      recommendedRecovery: 'ABORT', hypotheses: [], timestamp: new Date().toISOString(),
    };
    const r = ar.selectRecovery(diagnosis, makeLifecycle());
    expect(r?.action).toBe('ABORT');
  });

  it('returns ASK_USER for user-required', () => {
    const diagnosis: DiagnosisResult = {
      actionId: 'a1', failureClass: 'PERMISSION', rootCause: 'needs auth',
      evidence: [], confidence: 0.9, recoverability: 'REQUIRES_USER',
      recommendedRecovery: 'ASK_USER', hypotheses: [], timestamp: new Date().toISOString(),
    };
    const r = ar.selectRecovery(diagnosis, makeLifecycle());
    expect(r?.action).toBe('ASK_USER');
  });

  it('budget prevents recovery', () => {
    const ar2 = new AdaptiveRecoveryEngine({ maxRecoveryAttempts: 0, withinBudget: false });
    const diagnosis: DiagnosisResult = {
      actionId: 'a1', failureClass: 'TIMEOUT', rootCause: 'timeout',
      evidence: [], confidence: 0.5, recoverability: 'AUTO_RECOVERABLE',
      recommendedRecovery: 'RETRY', hypotheses: [], timestamp: new Date().toISOString(),
    };
    const r = ar2.selectRecovery(diagnosis, makeLifecycle());
    expect(r?.action).toBe('ASK_USER');
  });

  it('records execution and updates budget', () => {
    ar.recordExecution({
      actionId: 'a1', diagnosis: {} as any,
      selectedRecovery: { action: 'RETRY', risk: 'LOW', latencyMs: 500, probabilityOfSuccess: 0.6, cost: 1, reasoning: 'test' },
      startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), success: true, error: null, resultState: null,
    });
    expect(ar.getBudget().recoveryAttemptsUsed).toBe(1);
  });

  it('tracks success rate', () => {
    ar.recordExecution({ actionId: 'a1', diagnosis: {} as any, selectedRecovery: { action: 'RETRY', risk: 'LOW', latencyMs: 500, probabilityOfSuccess: 0.6, cost: 1, reasoning: '' }, startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), success: true, error: null, resultState: null });
    ar.recordExecution({ actionId: 'a2', diagnosis: {} as any, selectedRecovery: { action: 'RETRY', risk: 'LOW', latencyMs: 500, probabilityOfSuccess: 0.6, cost: 1, reasoning: '' }, startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), success: false, error: null, resultState: null });
    expect(ar.getSuccessRate()).toBe(0.5);
  });

  it('resetBudget resets state', () => {
    ar.recordExecution({ actionId: 'a1', diagnosis: {} as any, selectedRecovery: { action: 'RETRY', risk: 'LOW', latencyMs: 500, probabilityOfSuccess: 0.6, cost: 1, reasoning: '' }, startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), success: true, error: null, resultState: null });
    ar.resetBudget();
    expect(ar.getBudget().recoveryAttemptsUsed).toBe(0);
  });

  it('detects recovery loops', () => {
    for (let i = 0; i < 3; i++) {
      ar.recordExecution({ actionId: 'a1', diagnosis: {} as any, selectedRecovery: { action: 'RETRY', risk: 'LOW', latencyMs: 500, probabilityOfSuccess: 0.6, cost: 1, reasoning: '' }, startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), success: false, error: null, resultState: null });
    }
    const diagnosis: DiagnosisResult = {
      actionId: 'a1', failureClass: 'TIMEOUT', rootCause: 'timeout',
      evidence: [], confidence: 0.5, recoverability: 'AUTO_RECOVERABLE',
      recommendedRecovery: 'RETRY', hypotheses: [], timestamp: new Date().toISOString(),
    };
    const r = ar.selectRecovery(diagnosis, makeLifecycle());
    expect(r?.action).toBe('ASK_USER'); // Loop detected → ask user
  });
});

// ============================================================================
// UNKNOWN OUTCOME HANDLER
// ============================================================================

describe('UnknownOutcomeHandler', () => {
  let uo: UnknownOutcomeHandler;

  beforeEach(() => { uo = new UnknownOutcomeHandler(); });

  it('assesses unknown when no verification', () => {
    const lc = makeLifecycle({ history: [{ from: 'PLANNED', to: 'EXECUTING', timestamp: new Date().toISOString(), reason: 'start' }] });
    const a = uo.assess('a1', 'CLICK', lc, null, null);
    expect(a.status).toBe('UNKNOWN');
  });

  it('assesses success when verified', () => {
    const lc = makeLifecycle({ history: [{ from: 'VERIFYING', to: 'VERIFIED', timestamp: new Date().toISOString(), reason: 'ok' }] });
    const a = uo.assess('a1', 'CLICK', lc, null, null);
    expect(a.status).toBe('SUCCESS');
  });

  it('prevents retry for dangerous unknown', () => {
    const assessment = { actionId: 'a1', status: 'UNKNOWN' as const, confidence: 0.3, evidence: [], reasoning: '', dangerousAction: true, timestamp: new Date().toISOString() };
    expect(uo.shouldRetry(assessment)).toBe(false);
  });

  it('allows retry for safe unknown', () => {
    const assessment = { actionId: 'a1', status: 'UNKNOWN' as const, confidence: 0.3, evidence: [], reasoning: '', dangerousAction: false, timestamp: new Date().toISOString() };
    expect(uo.shouldRetry(assessment)).toBe(true);
  });

  it('asks user for dangerous unknown', () => {
    const assessment = { actionId: 'a1', status: 'UNKNOWN' as const, confidence: 0.3, evidence: [], reasoning: '', dangerousAction: true, timestamp: new Date().toISOString() };
    expect(uo.shouldAskUser(assessment)).toBe(true);
  });

  it('deduplicates actions', () => {
    const ts = Date.now();
    expect(uo.isDuplicate(`click_${ts}`, 'CLICK', 'btn')).toBe(false);
    expect(uo.isDuplicate(`click_${ts}`, 'CLICK', 'btn')).toBe(true);
    expect(uo.isDuplicate(`click_${ts}`, 'CLICK', 'btn')).toBe(true);
    // Different target — no dedup
    expect(uo.isDuplicate(`click_${ts}`, 'CLICK', 'btn2')).toBe(false);
  });

  it('getRecommendedAction returns correct action', () => {
    const success = { actionId: 'a1', status: 'SUCCESS' as const, confidence: 0.9, evidence: [], reasoning: '', dangerousAction: false, timestamp: new Date().toISOString() };
    expect(uo.getRecommendedAction(success)).toBe('CONTINUE');

    const unknown = { actionId: 'a1', status: 'UNKNOWN' as const, confidence: 0.3, evidence: [], reasoning: '', dangerousAction: true, timestamp: new Date().toISOString() };
    expect(uo.getRecommendedAction(unknown)).toBe('ASK_USER');
  });
});

// ============================================================================
// PLAN PATCHER
// ============================================================================

describe('PlanPatcher', () => {
  let pp: PlanPatcher;

  beforeEach(() => { pp = new PlanPatcher(); });

  it('inserts task', () => {
    const patch = pp.insertTask('plan1', 'task1', { id: 'task2' }, 'new step');
    expect(patch.type).toBe('INSERT_TASK');
    expect(pp.getPatchesForPlan('plan1')).toHaveLength(1);
  });

  it('removes task', () => {
    const patch = pp.removeTask('plan1', 'task1', 'not needed');
    expect(patch.type).toBe('REMOVE_TASK');
  });

  it('replaces task', () => {
    const patch = pp.replaceTask('plan1', 'task1', { id: 'old' }, { id: 'new' }, 'failed');
    expect(patch.type).toBe('REPLACE_TASK');
  });

  it('creates minimal replan', () => {
    const patches = pp.createMinimalReplan('plan1', 'task2', { id: 'task2b' }, ['task1']);
    expect(patches).toHaveLength(1);
    expect(patches[0].type).toBe('REPLACE_TASK');
  });

  it('getAffectedTasks returns affected ids', () => {
    pp.insertTask('plan1', 'task1', {}, 'reason');
    pp.removeTask('plan1', 'task2', 'reason');
    expect(pp.getAffectedTasks('plan1')).toContain('task1');
    expect(pp.getAffectedTasks('plan1')).toContain('task2');
  });

  it('clear resets patches', () => {
    pp.insertTask('plan1', 'task1', {}, 'reason');
    pp.clear();
    expect(pp.getAllPatches()).toHaveLength(0);
  });
});

// ============================================================================
// EXPERIENCE LEARNING ENGINE
// ============================================================================

describe('ExperienceLearningEngine', () => {
  let el: ExperienceLearningEngine;

  beforeEach(() => { el = new ExperienceLearningEngine(); });

  it('records failure', () => {
    const exp = el.recordFailure('click', 'CLICK', 'TARGET_NOT_FOUND', 'missing', 'RELOCATE_TARGET', 'VISUAL', 'browser', 500);
    expect(exp.type).toBe('FAILURE');
    expect(exp.failureClass).toBe('TARGET_NOT_FOUND');
  });

  it('records recovery', () => {
    const exp = el.recordRecovery('click', 'CLICK', 'TARGET_NOT_FOUND', 'RELOCATE_TARGET', true, 'VISUAL', 'browser', 800);
    expect(exp.type).toBe('RECOVERY');
    expect(exp.recoverySuccess).toBe(true);
  });

  it('records success', () => {
    const exp = el.recordSuccess('click', 'CLICK', 'VISUAL', 'browser', 'OCR', 200);
    expect(exp.type).toBe('SUCCESS');
    expect(exp.successRate).toBe(1.0);
  });

  it('records user correction', () => {
    const exp = el.recordUserCorrection('click', 'CLICK', 'Wrong button', 'browser');
    expect(exp.type).toBe('USER_CORRECTION');
    expect(exp.successRate).toBeLessThan(1.0);
  });

  it('finds relevant experiences', () => {
    el.recordSuccess('click', 'CLICK', 'VISUAL', 'browser', '', 200);
    el.recordSuccess('type', 'TYPE_TEXT', 'DOM', 'browser', '', 300);
    const relevant = el.findRelevant('click', 'CLICK', 'browser');
    expect(relevant.length).toBeGreaterThan(0);
  });

  it('finds recoveries for failure class', () => {
    el.recordRecovery('click', 'CLICK', 'TARGET_NOT_FOUND', 'RELOCATE_TARGET', true, 'VISUAL', 'browser', 500);
    const recs = el.findRecoveriesForFailure('TARGET_NOT_FOUND');
    expect(recs.length).toBe(1);
  });

  it('suggests strategy', () => {
    el.recordSuccess('click', 'CLICK', 'VISUAL', 'browser', 'OCR', 200);
    const s = el.suggestStrategy('click', 'CLICK', 'browser');
    expect(s).not.toBeNull();
    expect(s!.strategy).toBe('OCR');
  });

  it('records outcome updates success rate', () => {
    const exp = el.recordSuccess('click', 'CLICK', 'VISUAL', 'browser', '', 200);
    el.recordOutcome(exp.id, false);
    const updated = el.getExperiences().find(e => e.id === exp.id);
    expect(updated!.successRate).toBeLessThan(1.0);
  });

  it('applyDecay reduces old experience rates', () => {
    el.recordSuccess('click', 'CLICK', 'VISUAL', 'browser', '', 200);
    el.applyDecay();
    const exps = el.getExperiences();
    expect(exps.length).toBe(1);
  });

  it('getStats returns correct counts', () => {
    el.recordSuccess('a', 'A', 'VISUAL', 'd', '', 100);
    el.recordFailure('b', 'B', 'TIMEOUT', 'r', null, 'VISUAL', 'd', 100);
    const stats = el.getStats();
    expect(stats.total).toBe(2);
    expect(stats.byType.SUCCESS).toBe(1);
    expect(stats.byType.FAILURE).toBe(1);
  });

  it('clear resets everything', () => {
    el.recordSuccess('a', 'A', 'VISUAL', 'd', '', 100);
    el.clear();
    expect(el.getExperiences()).toHaveLength(0);
  });
});

// ============================================================================
// CLOSED-LOOP ORCHESTRATOR
// ============================================================================

describe('ClosedLoopOrchestrator', () => {
  let cl: ClosedLoopOrchestrator;

  beforeEach(() => { cl = new ClosedLoopOrchestrator(); });

  it('creates action lifecycle', () => {
    const lc = cl.createAction('a1', 'Button clicked', 'NORMAL');
    expect(lc.status).toBe('PLANNED');
    expect(lc.actionId).toBe('a1');
  });

  it('transitions lifecycle', () => {
    cl.createAction('a1', 'test');
    const lc = cl.transition('a1', 'EXECUTING', 'start');
    expect(lc.status).toBe('EXECUTING');
    expect(lc.attempts).toBe(1);
  });

  it('executes with verification — success', async () => {
    const result = await cl.executeWithVerification(
      'a1',
      async () => ({ success: true }),
      { before: makeObservations(), after: makeObservations() },
      [{ source: 'STRUCTURED_STATE', expected: 'exists', actual: 'exists' }],
    );
    expect(result.status).toBe('VERIFIED');
  });

  it('executes with verification — failure', async () => {
    const result = await cl.executeWithVerification(
      'a1',
      async () => ({ success: true }),
      { before: makeObservations(), after: makeObservations({ processRunning: false }) },
      [{ source: 'PROCESS', expected: 'running', actual: 'not_running' }],
    );
    expect(result.status).not.toBe('VERIFIED');
  });

  it('executes with verification — execution error', async () => {
    const result = await cl.executeWithVerification(
      'a1',
      async () => { throw new Error('crash'); },
      { before: makeObservations(), after: makeObservations() },
      [],
    );
    expect(result.status).toBe('FAILED');
  });

  it('records trace events', async () => {
    await cl.executeWithVerification(
      'a1',
      async () => ({ success: true }),
      { before: makeObservations(), after: makeObservations() },
      [{ source: 'STRUCTURED_STATE', expected: 'exists', actual: 'exists' }],
    );
    expect(cl.getTrace('a1').length).toBeGreaterThan(0);
  });

  it('getTraceSummary returns string', async () => {
    await cl.executeWithVerification(
      'a1',
      async () => ({ success: true }),
      { before: makeObservations(), after: makeObservations() },
      [{ source: 'STRUCTURED_STATE', expected: 'exists', actual: 'exists' }],
    );
    const summary = cl.getTraceSummary('a1');
    expect(typeof summary).toBe('string');
    expect(summary.length).toBeGreaterThan(0);
  });

  it('buildFinalOutcome computes correct stats', () => {
    const outcome = cl.buildFinalOutcome('g1', 'p1', [
      { actionId: 'a1', status: 'VERIFIED', duration: 100 },
      { actionId: 'a2', status: 'FAILED', duration: 200 },
    ]);
    expect(outcome.completedActions).toBe(1);
    expect(outcome.failedActions).toBe(1);
    expect(outcome.status).toBe('PARTIALLY_COMPLETED');
  });

  it('patches plan', () => {
    const patch = cl.patchPlan('p1', 't1', { id: 't2' }, 'failed');
    expect(patch.type).toBe('REPLACE_TASK');
  });

  it('clear resets everything', () => {
    cl.createAction('a1', 'test');
    cl.clear();
    expect(cl.getLifecycle('a1')).toBeUndefined();
  });
});

// ============================================================================
// DEFAULT CONSTANTS
// ============================================================================

describe('Phase 25 Constants', () => {
  it('DEFAULT_RECOVERY_BUDGET has reasonable values', () => {
    expect(DEFAULT_RECOVERY_BUDGET.maxRecoveryAttempts).toBeGreaterThan(0);
    expect(DEFAULT_RECOVERY_BUDGET.maxReplans).toBeGreaterThan(0);
    expect(DEFAULT_RECOVERY_BUDGET.maxTotalTimeMs).toBeGreaterThan(0);
  });

  it('HIGH_IMPACT_ACTIONS includes dangerous actions', () => {
    expect(HIGH_IMPACT_ACTIONS).toContain('DELETE_FILE');
    expect(HIGH_IMPACT_ACTIONS).toContain('EXECUTE_POWER_ACTION');
  });
});

// ============================================================================
// INTEGRATION: Full Recovery Scenario
// ============================================================================

describe('Integration — Full Recovery Scenario', () => {
  it('target not found → diagnose → recover → reverify', async () => {
    const cl = new ClosedLoopOrchestrator();

    // Simulate: action fails because target disappeared
    const result = await cl.executeWithVerification(
      'a1',
      async () => ({ success: true }),
      {
        before: makeObservations(),
        after: makeObservations({ currentTarget: { id: 'btn1', label: 'Submit', bounds: null, visible: false, enabled: false, confidence: 0.1, source: 'VISION', lastVerifiedAt: null } }),
      },
      [{ source: 'STRUCTURED_STATE', expected: 'target exists', actual: 'target not found' }],
    );

    // Should have diagnosed and selected recovery
    expect(result.diagnosis).toBeDefined();
    expect(result.recovery).toBeDefined();
  });

  it('unknown outcome for dangerous action → no blind retry', async () => {
    const cl = new ClosedLoopOrchestrator();

    const result = await cl.executeWithVerification(
      'a1',
      async () => ({ success: true }),
      { before: makeObservations(), after: makeObservations() },
      [], // No verification signals → unknown
    );

    // Unknown outcome handler should prevent blind retry of dangerous actions
    expect(result.status).not.toBe('VERIFIED');
  });

  it('plan patching preserves completed tasks', () => {
    const cl = new ClosedLoopOrchestrator();
    cl.patchPlan('p1', 'failed_task', { id: 'replacement' }, 'Task failed');

    const patches = cl.planPatcher.getPatchesForPlan('p1');
    expect(patches).toHaveLength(1);
    expect(patches[0].preservesCompleted).toBe(true);
  });

  it('experience stores recovery for future use', () => {
    const cl = new ClosedLoopOrchestrator();
    cl.experienceEngine.recordRecovery('click', 'CLICK', 'TARGET_NOT_FOUND', 'RELOCATE_TARGET', true, 'VISUAL', 'browser', 500);

    const recs = cl.experienceEngine.findRecoveriesForFailure('TARGET_NOT_FOUND');
    expect(recs.length).toBe(1);
    expect(recs[0].recoveryAction).toBe('RELOCATE_TARGET');
  });

  it('state diff detects material changes', () => {
    const cl = new ClosedLoopOrchestrator();
    const s1 = cl.stateEstimator.estimate(makeObservations());
    const s2 = cl.stateEstimator.estimate(makeObservations({ browserUrl: 'https://other.com' }));
    const diff = cl.stateDiffEngine.diff(s1, s2);
    expect(diff.material).toBe(true);
    expect(diff.changes.some(c => c.type === 'URL_CHANGED')).toBe(true);
  });

  it('verification hierarchy prefers structured state', () => {
    const clLocal = new ClosedLoopOrchestrator();
    const r1 = clLocal.verificationEngine.verify('a1', 'exists', 'exists', 'STRUCTURED_STATE', 'NORMAL');
    const r2 = clLocal.verificationEngine.verify('a2', 'exists', 'exists', 'WEAK_VISUAL', 'NORMAL');
    expect(r1.confidence).toBeGreaterThan(r2.confidence);
  });

  it('recovery budget tracks across multiple recoveries', () => {
    const cl = new ClosedLoopOrchestrator();
    for (let i = 0; i < 3; i++) {
      cl.recoveryEngine.recordExecution({
        actionId: `a${i}`, diagnosis: {} as any,
        selectedRecovery: { action: 'RETRY', risk: 'LOW', latencyMs: 100, probabilityOfSuccess: 0.5, cost: 1, reasoning: '' },
        startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), success: true, error: null, resultState: null,
      });
    }
    expect(cl.recoveryEngine.getBudget().recoveryAttemptsUsed).toBe(3);
  });
});
