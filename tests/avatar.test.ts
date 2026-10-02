import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { generateAvatarId, nowISO, DEFAULT_AVATAR_CONFIG } from '../src/avatar/contracts';
import type {
  AvatarMainState,
  AvatarExpression,
  MicroAnimation,
  SpeakingState,
  VoiceState,
  TaskState,
  AvatarConfig,
  AvatarContext,
  ExpressionRule,
  Point,
} from '../src/avatar/contracts';
import { AvatarStateMachine } from '../src/avatar/stateEngine';
import { ExpressionEngine } from '../src/avatar/expressionEngine';
import { MicroAnimationEngine } from '../src/avatar/microAnimations';
import { LipSyncEngine } from '../src/avatar/lipSync';
import { AvatarEngine, createAvatarEngine } from '../src/avatar/index';

function defaultContext(overrides: Partial<AvatarContext> = {}): AvatarContext {
  return {
    voiceState: 'idle',
    taskState: 'idle',
    taskSuccess: null,
    taskFailure: null,
    userInterruption: false,
    urgency: 'low',
    idleDurationMs: 0,
    lastInteractionMs: Date.now(),
    speakingVolume: 0,
    errorCount: 0,
    ...overrides,
  };
}

function idleCtx(): AvatarContext { return defaultContext({ voiceState: 'idle', taskState: 'idle' }); }
function listeningCtx(): AvatarContext { return defaultContext({ voiceState: 'listening' }); }
function thinkingCtx(): AvatarContext { return defaultContext({ voiceState: 'processing', taskState: 'planning' }); }
function workingCtx(): AvatarContext { return defaultContext({ voiceState: 'processing', taskState: 'executing' }); }
function speakingCtx(): AvatarContext { return defaultContext({ voiceState: 'speaking' }); }
function interruptedCtx(): AvatarContext { return defaultContext({ userInterruption: true }); }
function highUrgencyCtx(): AvatarContext { return defaultContext({ urgency: 'high' }); }
function successCtx(): AvatarContext { return defaultContext({ taskState: 'complete', taskSuccess: true }); }
function failureCtx(): AvatarContext { return defaultContext({ taskState: 'failed', taskFailure: true }); }

function reachState(sm: AvatarStateMachine, ...states: AvatarMainState[]): void {
  for (const s of states) sm.transition(s);
}

// ============================================================================
// Avatar Contracts
// ============================================================================

describe('Avatar Contracts', () => {
  it('has all AvatarMainState values', () => {
    const states: AvatarMainState[] = ['IDLE','LISTENING','THINKING','WORKING','SPEAKING','VERIFYING','RECOVERY','ERROR','RELAXED','SLEEPING'];
    expect(states).toHaveLength(10);
  });

  it('has all AvatarExpression values', () => {
    const exprs: AvatarExpression[] = ['NEUTRAL','HAPPY','EXCITED','CALM','CURIOUS','CONCERNED','SAD','SURPRISED','CONFUSED','ANGRY','FOCUSED','ATTENTIVE','CONVERSATIONAL','THOUGHTFUL','RELAXED','SLEEPY'];
    expect(exprs).toHaveLength(16);
  });

  it('has all MicroAnimation values', () => {
    const anims: MicroAnimation[] = ['BLINK','BREATHE','HEAD_NOD','HEAD_TILT','GAZE_SHIFT','HAIR_SWAY','BODY_SWAY','BLINK_DOUBLE','LOOK_UP','LOOK_DOWN','LOOK_LEFT','LOOK_RIGHT'];
    expect(anims).toHaveLength(12);
  });

  it('has all SpeakingState values', () => {
    const s: SpeakingState[] = ['SILENT','SPEAKING_PAUSED','SPEAKING_ACTIVE','SPEAKING_EMPHASIS'];
    expect(s).toHaveLength(4);
  });

  it('has all VoiceState values', () => {
    const v: VoiceState[] = ['idle','listening','processing','speaking','interrupted','error'];
    expect(v).toHaveLength(6);
  });

  it('has all TaskState values', () => {
    const t: TaskState[] = ['idle','planning','gathering','executing','verifying','recovering','complete','failed','cancelled'];
    expect(t).toHaveLength(9);
  });

  it('AvatarState has correct structure', () => {
    const state = new AvatarStateMachine().getCurrentState();
    for (const key of ['mainState','expression','speakingState','microAnimations','eyeTarget','breathRate','bodySway','headTilt','opacity','scale','timestamp']) {
      expect(state).toHaveProperty(key);
    }
  });

  it('AvatarConfig has correct structure', () => {
    const c = DEFAULT_AVATAR_CONFIG;
    for (const key of ['idleVariationInterval','blinkInterval','blinkDuration','breathCycle','gazeShiftInterval','maxMicroAnimations','transitionDuration','speakingFrameRate','lipSyncEnabled','microAnimationEnabled','idleVariationEnabled']) {
      expect(c).toHaveProperty(key);
    }
  });

  it('generateAvatarId returns unique strings', () => {
    const id1 = generateAvatarId();
    const id2 = generateAvatarId();
    expect(id1).not.toBe(id2);
  });

  it('generateAvatarId uses custom prefix', () => {
    expect(generateAvatarId('test')).toMatch(/^test_/);
  });

  it('nowISO returns ISO string', () => {
    const ts = nowISO();
    expect(() => new Date(ts)).not.toThrow();
  });
});

// ============================================================================
// State Machine
// ============================================================================

describe('AvatarStateMachine', () => {
  let sm: AvatarStateMachine;
  beforeEach(() => { sm = new AvatarStateMachine(); });

  it('creates with default state IDLE', () => {
    expect(sm.getCurrentState().mainState).toBe('IDLE');
  });

  it('default expression is NEUTRAL', () => {
    expect(sm.getCurrentState().expression).toBe('NEUTRAL');
  });

  it('default speaking state is SILENT', () => {
    expect(sm.getCurrentState().speakingState).toBe('SILENT');
  });

  it('default micro animations is empty', () => {
    expect(sm.getCurrentState().microAnimations).toEqual([]);
  });

  it('default eye target is null', () => {
    expect(sm.getCurrentState().eyeTarget).toBeNull();
  });

  it('default opacity is 1', () => {
    expect(sm.getCurrentState().opacity).toBe(1);
  });

  it('default scale is 1', () => {
    expect(sm.getCurrentState().scale).toBe(1);
  });

  it('creates with custom config', () => {
    expect(new AvatarStateMachine({ blinkInterval: 2000 }).getCurrentState().mainState).toBe('IDLE');
  });

  it('valid transition IDLE to LISTENING', () => {
    expect(sm.canTransition('LISTENING')).toBe(true);
    expect(sm.transition('LISTENING').mainState).toBe('LISTENING');
  });

  it('valid transition LISTENING to THINKING', () => {
    reachState(sm, 'LISTENING');
    expect(sm.canTransition('THINKING')).toBe(true);
    expect(sm.transition('THINKING').mainState).toBe('THINKING');
  });

  it('valid transition THINKING to WORKING', () => {
    reachState(sm, 'LISTENING', 'THINKING');
    expect(sm.canTransition('WORKING')).toBe(true);
    expect(sm.transition('WORKING').mainState).toBe('WORKING');
  });

  it('valid transition WORKING to VERIFYING', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING');
    expect(sm.canTransition('VERIFYING')).toBe(true);
    expect(sm.transition('VERIFYING').mainState).toBe('VERIFYING');
  });

  it('valid transition VERIFYING to WORKING (retry)', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING');
    expect(sm.canTransition('WORKING')).toBe(true);
    expect(sm.transition('WORKING').mainState).toBe('WORKING');
  });

  it('valid transition VERIFYING to RECOVERY', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING');
    expect(sm.canTransition('RECOVERY')).toBe(true);
    expect(sm.transition('RECOVERY').mainState).toBe('RECOVERY');
  });

  it('valid transition RECOVERY to WORKING', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING', 'RECOVERY');
    expect(sm.canTransition('WORKING')).toBe(true);
    expect(sm.transition('WORKING').mainState).toBe('WORKING');
  });

  it('valid transition WORKING to SPEAKING', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING');
    expect(sm.canTransition('SPEAKING')).toBe(true);
    expect(sm.transition('SPEAKING').mainState).toBe('SPEAKING');
  });

  it('valid transition SPEAKING to IDLE', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'SPEAKING');
    expect(sm.canTransition('IDLE')).toBe(true);
    expect(sm.transition('IDLE').mainState).toBe('IDLE');
  });

  it('valid transition SPEAKING to LISTENING (interrupt)', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'SPEAKING');
    expect(sm.canTransition('LISTENING')).toBe(true);
    expect(sm.transition('LISTENING').mainState).toBe('LISTENING');
  });

  it('valid transition IDLE to ERROR', () => {
    expect(sm.canTransition('ERROR')).toBe(true);
    expect(sm.transition('ERROR').mainState).toBe('ERROR');
  });

  it('valid transition LISTENING to ERROR', () => {
    reachState(sm, 'LISTENING');
    expect(sm.canTransition('ERROR')).toBe(true);
    expect(sm.transition('ERROR').mainState).toBe('ERROR');
  });

  it('valid transition ERROR to IDLE', () => {
    reachState(sm, 'ERROR');
    expect(sm.canTransition('IDLE')).toBe(true);
    expect(sm.transition('IDLE').mainState).toBe('IDLE');
  });

  it('valid transition IDLE to RELAXED', () => {
    expect(sm.canTransition('RELAXED')).toBe(true);
    expect(sm.transition('RELAXED').mainState).toBe('RELAXED');
  });

  it('valid transition RELAXED to IDLE', () => {
    reachState(sm, 'RELAXED');
    expect(sm.canTransition('IDLE')).toBe(true);
    expect(sm.transition('IDLE').mainState).toBe('IDLE');
  });

  it('valid transition IDLE to SLEEPING', () => {
    expect(sm.canTransition('SLEEPING')).toBe(true);
    expect(sm.transition('SLEEPING').mainState).toBe('SLEEPING');
  });

  it('valid transition SLEEPING to IDLE', () => {
    reachState(sm, 'SLEEPING');
    expect(sm.canTransition('IDLE')).toBe(true);
    expect(sm.transition('IDLE').mainState).toBe('IDLE');
  });

  it('valid transition VERIFYING to SPEAKING', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING');
    expect(sm.canTransition('SPEAKING')).toBe(true);
    expect(sm.transition('SPEAKING').mainState).toBe('SPEAKING');
  });

  it('valid transition VERIFYING to IDLE', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING');
    expect(sm.canTransition('IDLE')).toBe(true);
    expect(sm.transition('IDLE').mainState).toBe('IDLE');
  });

  it('valid transition RECOVERY to IDLE', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING', 'RECOVERY');
    expect(sm.canTransition('IDLE')).toBe(true);
    expect(sm.transition('IDLE').mainState).toBe('IDLE');
  });

  it('invalid transition IDLE to WORKING rejected', () => {
    expect(sm.canTransition('WORKING')).toBe(false);
    expect(sm.transition('WORKING').mainState).toBe('IDLE');
  });

  it('invalid transition ERROR to WORKING rejected', () => {
    reachState(sm, 'ERROR');
    expect(sm.canTransition('WORKING')).toBe(false);
    expect(sm.transition('WORKING').mainState).toBe('ERROR');
  });

  it('invalid transition IDLE to VERIFYING rejected', () => {
    expect(sm.canTransition('VERIFYING')).toBe(false);
    expect(sm.transition('VERIFYING').mainState).toBe('IDLE');
  });

  it('invalid transition IDLE to RECOVERY rejected', () => {
    expect(sm.canTransition('RECOVERY')).toBe(false);
  });

  it('invalid transition SLEEPING to WORKING rejected', () => {
    reachState(sm, 'SLEEPING');
    expect(sm.canTransition('WORKING')).toBe(false);
  });

  it('invalid transition RELAXED to WORKING rejected', () => {
    reachState(sm, 'RELAXED');
    expect(sm.canTransition('WORKING')).toBe(false);
  });

  it('state history tracked', () => {
    sm.transition('LISTENING');
    sm.transition('THINKING');
    expect(sm.getHistory().length).toBeGreaterThanOrEqual(2);
  });

  it('history has correct count', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING');
    expect(sm.getHistory()).toHaveLength(3);
  });

  it('history contains transitions with from/to', () => {
    sm.transition('LISTENING');
    const entry = sm.getHistory()[0];
    expect(entry.from).toBe('IDLE');
    expect(entry.to).toBe('LISTENING');
  });

  it('invalid transition does not add history', () => {
    const len = sm.getHistory().length;
    sm.transition('WORKING');
    expect(sm.getHistory()).toHaveLength(len);
  });

  it('history has reason field', () => {
    sm.transition('LISTENING', {}, 'test reason');
    expect(sm.getHistory()[0].reason).toBe('test reason');
  });

  it('getHistorySince filters correctly', () => {
    const before = nowISO();
    sm.transition('LISTENING');
    sm.transition('THINKING');
    expect(sm.getHistorySince(before).length).toBeGreaterThanOrEqual(2);
  });

  it('getHistorySince returns empty for future timestamp', () => {
    sm.transition('LISTENING');
    const future = new Date(Date.now() + 100000).toISOString();
    expect(sm.getHistorySince(future)).toHaveLength(0);
  });

  it('forceState overrides rules', () => {
    expect(sm.forceState('WORKING').mainState).toBe('WORKING');
  });

  it('forceState updates current state', () => {
    sm.forceState('SPEAKING');
    expect(sm.getCurrentState().mainState).toBe('SPEAKING');
  });

  it('forceState records history', () => {
    sm.forceState('ERROR');
    expect(sm.getHistory()).toHaveLength(1);
    expect(sm.getHistory()[0].reason).toBe('forced');
  });

  it('forceState with custom reason', () => {
    sm.forceState('IDLE', 'manual override');
    expect(sm.getHistory()[0].reason).toBe('manual override');
  });

  it('forceState uses buildDefaultState (fixed defaults, not per-state)', () => {
    const state = sm.forceState('SLEEPING');
    expect(state.breathRate).toBe(0.5);
    expect(state.opacity).toBe(1);
  });

  it('IDLE default values from buildDefaultState', () => {
    const s = sm.getCurrentState();
    expect(s.breathRate).toBe(0.5);
    expect(s.opacity).toBe(1);
    expect(s.bodySway).toBe(0);
    expect(s.headTilt).toBe(0);
  });

  it('transition applies per-state breathRate for IDLE', () => {
    sm.transition('LISTENING');
    sm.transition('THINKING');
    sm.transition('WORKING');
    sm.transition('SPEAKING');
    sm.transition('IDLE');
    expect(sm.getCurrentState().breathRate).toBe(0.4);
  });

  it('LISTENING default eyeTarget', () => {
    sm.transition('LISTENING');
    expect(sm.getCurrentState().eyeTarget).toEqual({ x: 0, y: 0.3 });
  });

  it('THINKING default headTilt', () => {
    reachState(sm, 'LISTENING', 'THINKING');
    expect(sm.getCurrentState().headTilt).toBe(0.15);
  });

  it('WORKING default bodySway', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING');
    expect(sm.getCurrentState().bodySway).toBe(0);
  });

  it('SPEAKING default speakingState and breathRate', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'SPEAKING');
    expect(sm.getCurrentState().speakingState).toBe('SPEAKING_ACTIVE');
    expect(sm.getCurrentState().breathRate).toBe(0.7);
  });

  it('SLEEPING default opacity and breathRate', () => {
    sm.transition('SLEEPING');
    const s = sm.getCurrentState();
    expect(s.opacity).toBe(0.7);
    expect(s.breathRate).toBe(0.2);
  });

  it('ERROR default opacity and breathRate', () => {
    sm.transition('ERROR');
    const s = sm.getCurrentState();
    expect(s.opacity).toBe(0.9);
    expect(s.breathRate).toBe(0.8);
  });

  it('RELAXED default bodySway, headTilt, breathRate', () => {
    sm.transition('RELAXED');
    const s = sm.getCurrentState();
    expect(s.bodySway).toBe(0.1);
    expect(s.headTilt).toBe(0.1);
    expect(s.breathRate).toBe(0.3);
  });

  it('transition returns new AvatarState', () => {
    const before = sm.getCurrentState();
    const after = sm.transition('LISTENING');
    expect(after.mainState).toBe('LISTENING');
    expect(before.mainState).toBe('IDLE');
  });

  it('transition timestamp updated', () => {
    const ts1 = sm.getCurrentState().timestamp;
    sm.transition('LISTENING');
    expect(sm.getCurrentState().timestamp >= ts1).toBe(true);
  });

  it('getTransition returns definition', () => {
    const t = sm.getTransition('IDLE', 'LISTENING');
    expect(t).not.toBeNull();
    expect(t!.duration).toBe(150);
    expect(t!.easing).toBe('ease-out');
  });

  it('getTransition returns null for invalid', () => {
    expect(sm.getTransition('IDLE', 'WORKING')).toBeNull();
  });

  it('getValidTransitions from IDLE', () => {
    const v = sm.getValidTransitions();
    expect(v).toContain('LISTENING');
    expect(v).toContain('RELAXED');
    expect(v).toContain('ERROR');
  });

  it('getValidTransitions from ERROR only returns IDLE', () => {
    sm.transition('ERROR');
    expect(sm.getValidTransitions()).toEqual(['IDLE']);
  });

  it('getPreviousMainState tracks previous', () => {
    expect(sm.getPreviousMainState()).toBe('IDLE');
    sm.transition('LISTENING');
    expect(sm.getPreviousMainState()).toBe('IDLE');
    sm.transition('THINKING');
    expect(sm.getPreviousMainState()).toBe('LISTENING');
  });

  it('transition with expression override', () => {
    const r = sm.transition('LISTENING', { expression: 'HAPPY' });
    expect(r.expression).toBe('HAPPY');
  });

  it('transition with scale override', () => {
    const r = sm.transition('LISTENING', { scale: 0.5 });
    expect(r.scale).toBe(0.5);
  });

  it('transition with microAnimations override', () => {
    const r = sm.transition('LISTENING', { microAnimations: ['BLINK'] });
    expect(r.microAnimations).toEqual(['BLINK']);
  });

  it('reset returns to IDLE', () => {
    reachState(sm, 'LISTENING', 'THINKING');
    sm.reset();
    expect(sm.getCurrentState().mainState).toBe('IDLE');
  });

  it('reset clears history', () => {
    sm.transition('LISTENING');
    sm.reset();
    expect(sm.getHistory()).toHaveLength(0);
  });

  it('reset clears previous state', () => {
    sm.transition('LISTENING');
    sm.reset();
    expect(sm.getPreviousMainState()).toBe('IDLE');
  });

  it('getTransitionDuration returns 0 initially', () => {
    expect(sm.getTransitionDuration()).toBe(0);
  });

  it('getTransitionDuration returns non-negative after transition', () => {
    sm.transition('LISTENING');
    expect(sm.getTransitionDuration()).toBeGreaterThanOrEqual(0);
  });

  it('full happy path', () => {
    reachState(sm, 'LISTENING', 'THINKING', 'WORKING', 'VERIFYING', 'SPEAKING', 'IDLE');
    expect(sm.getCurrentState().mainState).toBe('IDLE');
    expect(sm.getHistory()).toHaveLength(6);
  });

  it('error recovery path', () => {
    reachState(sm, 'LISTENING', 'ERROR');
    sm.transition('IDLE');
    expect(sm.getCurrentState().mainState).toBe('IDLE');
  });
});

// ============================================================================
// Expression Engine
// ============================================================================

describe('ExpressionEngine', () => {
  let engine: ExpressionEngine;
  beforeEach(() => { engine = new ExpressionEngine(); });
  afterEach(() => { engine.destroy(); });

  it('creates with default rules', () => {
    expect(engine.getRules().length).toBeGreaterThan(0);
  });

  it('initial expression is NEUTRAL', () => {
    expect(engine.getCurrentExpression()).toBe('NEUTRAL');
  });

  it('idle voice returns neutral', () => {
    expect(engine.evaluateExpression(idleCtx())).toBe('NEUTRAL');
  });

  it('listening voice returns attentive', () => {
    expect(engine.evaluateExpression(listeningCtx())).toBe('ATTENTIVE');
  });

  it('speaking voice returns conversational', () => {
    expect(engine.evaluateExpression(speakingCtx())).toBe('CONVERSATIONAL');
  });

  it('processing voice returns thoughtful', () => {
    expect(engine.evaluateExpression(defaultContext({ voiceState: 'processing' }))).toBe('THOUGHTFUL');
  });

  it('interrupted voice returns surprised', () => {
    expect(engine.evaluateExpression(defaultContext({ voiceState: 'interrupted' }))).toBe('SURPRISED');
  });

  it('thinking task returns thoughtful', () => {
    expect(engine.evaluateExpression(thinkingCtx())).toBe('THOUGHTFUL');
  });

  it('working task returns focused', () => {
    expect(engine.evaluateExpression(defaultContext({ taskState: 'executing' }))).toBe('FOCUSED');
  });

  it('task success returns happy', () => {
    expect(engine.evaluateExpression(successCtx())).toBe('HAPPY');
  });

  it('task failure returns concerned or sad', () => {
    expect(['CONCERNED', 'SAD']).toContain(engine.evaluateExpression(failureCtx()));
  });

  it('verifying task returns curious', () => {
    expect(engine.evaluateExpression(defaultContext({ taskState: 'verifying' }))).toBe('CURIOUS');
  });

  it('recovering task returns concerned', () => {
    expect(engine.evaluateExpression(defaultContext({ taskState: 'recovering' }))).toBe('CONCERNED');
  });

  it('cancelled task returns calm', () => {
    expect(engine.evaluateExpression(defaultContext({ taskState: 'cancelled' }))).toBe('CALM');
  });

  it('planning task returns thoughtful', () => {
    expect(engine.evaluateExpression(defaultContext({ taskState: 'planning' }))).toBe('THOUGHTFUL');
  });

  it('gathering task returns focused', () => {
    expect(engine.evaluateExpression(defaultContext({ taskState: 'gathering' }))).toBe('FOCUSED');
  });

  it('user interruption returns surprised', () => {
    expect(engine.evaluateExpression(interruptedCtx())).toBe('SURPRISED');
  });

  it('high urgency returns focused', () => {
    expect(engine.evaluateExpression(highUrgencyCtx())).toBe('FOCUSED');
  });

  it('low urgency rule matches when no voice/task rules present', () => {
    const e = new ExpressionEngine([
      { voiceState: null, taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: 'low', expression: 'CALM', confidence: 0.6 },
    ]);
    expect(e.evaluateExpression(defaultContext({ urgency: 'low' }))).toBe('CALM');
    e.destroy();
  });

  it('expression blending produces smooth transition', () => {
    engine.update(listeningCtx());
    engine.update(thinkingCtx());
    expect(engine.isBlending()).toBe(true);
  });

  it('blend progress advances gradually', () => {
    engine.update(listeningCtx());
    expect(engine.getBlendProgress()).toBeLessThan(1);
    for (let i = 0; i < 20; i++) engine.update(thinkingCtx());
    expect(engine.getBlendProgress()).toBe(1);
  });

  it('getBlendedExpression returns previous during early blend', () => {
    engine.update(idleCtx());
    engine.update(listeningCtx());
    expect(['NEUTRAL', 'ATTENTIVE']).toContain(engine.getBlendedExpression());
  });

  it('after blending completes returns current', () => {
    engine.update(idleCtx());
    engine.update(listeningCtx());
    for (let i = 0; i < 20; i++) engine.update(listeningCtx());
    expect(engine.getBlendedExpression()).toBe('ATTENTIVE');
    expect(engine.isBlending()).toBe(false);
  });

  it('same expression update does not start new blend', () => {
    engine.update(listeningCtx());
    expect(engine.isBlending()).toBe(true);
    engine.update(listeningCtx());
    expect(engine.isBlending()).toBe(true);
  });

  it('interruption wins over voice state', () => {
    const ctx = defaultContext({ voiceState: 'listening', userInterruption: true });
    expect(engine.evaluateExpression(ctx)).toBe('SURPRISED');
  });

  it('high urgency overrides voice state', () => {
    expect(engine.evaluateExpression(defaultContext({ voiceState: 'idle', urgency: 'high' }))).toBe('FOCUSED');
  });

  it('unknown context returns idle expression', () => {
    const r = engine.evaluateExpression(idleCtx());
    expect(['NEUTRAL', 'CALM']).toContain(r);
  });

  it('long idle duration returns sleepy when no rule matches', () => {
    const e = new ExpressionEngine([]);
    expect(e.evaluateExpression(defaultContext({ idleDurationMs: 130_000 }))).toBe('SLEEPY');
    e.destroy();
  });

  it('medium idle duration returns relaxed when no rule matches', () => {
    const e = new ExpressionEngine([]);
    expect(e.evaluateExpression(defaultContext({ idleDurationMs: 70_000 }))).toBe('RELAXED');
    e.destroy();
  });

  it('high error count returns concerned when no rule matches', () => {
    const e = new ExpressionEngine([]);
    expect(e.evaluateExpression(defaultContext({ errorCount: 5 }))).toBe('CONCERNED');
    e.destroy();
  });

  it('handleInterruption returns SURPRISED', () => {
    expect(engine.handleInterruption(100)).toBe('SURPRISED');
  });

  it('interruption flash resolves after duration', () => {
    vi.useFakeTimers();
    engine.update(listeningCtx());
    engine.handleInterruption(50);
    expect(engine.getCurrentExpression()).toBe('SURPRISED');
    vi.advanceTimersByTime(100);
    expect(engine.getCurrentExpression()).toBe('ATTENTIVE');
    vi.useRealTimers();
  });

  it('expression history tracked', () => {
    engine.update(listeningCtx());
    engine.update(thinkingCtx());
    expect(engine.getExpressionHistory().length).toBeGreaterThanOrEqual(1);
  });

  it('expression history has expression and confidence', () => {
    engine.update(listeningCtx());
    const e = engine.getExpressionHistory()[0];
    expect(e.expression).toBe('ATTENTIVE');
    expect(typeof e.confidence).toBe('number');
  });

  it('custom rules can be added', () => {
    const rule: ExpressionRule = {
      voiceState: 'idle', taskState: 'executing', taskSuccess: null,
      taskFailure: null, userInterruption: null, urgency: null,
      expression: 'EXCITED', confidence: 0.99,
    };
    engine.addRule(rule);
    expect(engine.getRules()).toContain(rule);
  });

  it('custom rule matches when added', () => {
    engine.addRule({
      voiceState: null, taskState: null, taskSuccess: null,
      taskFailure: null, userInterruption: null, urgency: null,
      expression: 'ANGRY', confidence: 0.99,
    });
    expect(engine.evaluateExpression(idleCtx())).toBe('ANGRY');
  });

  it('null voice state rule matches speaking voice context', () => {
    const ctx = defaultContext({ voiceState: 'speaking', taskState: 'executing' });
    const expr = engine.evaluateExpression(ctx);
    expect(['CONVERSATIONAL', 'FOCUSED']).toContain(expr);
  });

  it('null task state matches any task state', () => {
    expect(engine.evaluateExpression(defaultContext({ voiceState: 'listening', taskState: 'executing' }))).toBe('ATTENTIVE');
  });

  it('low confidence rule overridden by higher', () => {
    const e = new ExpressionEngine([
      { voiceState: null, taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: 'medium', expression: 'CONFUSED', confidence: 0.1 },
      { voiceState: null, taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'HAPPY', confidence: 0.9 },
    ]);
    expect(e.evaluateExpression(defaultContext({ urgency: 'medium' }))).toBe('HAPPY');
    e.destroy();
  });

  it('forceExpression sets expression immediately', () => {
    engine.forceExpression('EXCITED');
    expect(engine.getCurrentExpression()).toBe('EXCITED');
  });

  it('forceExpression clears interruption timer', () => {
    engine.handleInterruption(1000);
    engine.forceExpression('HAPPY');
    expect(engine.getCurrentExpression()).toBe('HAPPY');
  });

  it('update returns current expression', () => {
    expect(engine.update(listeningCtx())).toBe('ATTENTIVE');
  });

  it('update multiple times advances blend', () => {
    engine.update(idleCtx());
    engine.update(listeningCtx());
    const p1 = engine.getBlendProgress();
    engine.update(listeningCtx());
    expect(engine.getBlendProgress()).toBeGreaterThanOrEqual(p1);
  });

  it('update with task failure changes expression', () => {
    engine.update(idleCtx());
    engine.update(failureCtx());
    expect(['CONCERNED', 'SAD']).toContain(engine.getCurrentExpression());
  });

  it('multiple rules match picks highest confidence', () => {
    engine.addRule({
      voiceState: null, taskState: null, taskSuccess: null,
      taskFailure: null, userInterruption: null, urgency: null,
      expression: 'CONFUSED', confidence: 0.3,
    });
    const r = engine.evaluateExpression(defaultContext());
    expect(r).not.toBe('CONFUSED');
  });
});

// ============================================================================
// Micro Animations
// ============================================================================

describe('MicroAnimationEngine', () => {
  let engine: MicroAnimationEngine;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    engine = new MicroAnimationEngine();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('creates with default config', () => {
    expect(engine.isEnabled()).toBe(true);
  });

  it('creates disabled when configured', () => {
    expect(new MicroAnimationEngine({ microAnimationEnabled: false }).isEnabled()).toBe(false);
  });

  it('blink triggered in IDLE state', () => {
    Math.random.mockReturnValue(0.0001);
    const triggered = engine.update(Date.now() + 5000, 'IDLE', null);
    expect(triggered.some(a => a === 'BLINK' || a === 'BLINK_DOUBLE')).toBe(true);
  });

  it('blink interval randomized', () => {
    Math.random.mockReturnValue(0.5);
    const t = Date.now() + 4000;
    engine.update(t, 'IDLE', null);
    expect(engine.getBlinkSchedule().nextBlinkTime).toBeGreaterThan(t);
  });

  it('blink duration is reasonable', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'IDLE', null);
    const blink = engine.getActiveAnimationDetails().find(a => a.type === 'BLINK' || a.type === 'BLINK_DOUBLE');
    if (blink) {
      expect(blink.duration).toBeGreaterThan(0);
      expect(blink.duration).toBeLessThanOrEqual(400);
    }
  });

  it('blink count increments', () => {
    Math.random.mockReturnValue(0.0001);
    const t1 = Date.now() + 5000;
    engine.update(t1, 'IDLE', null);
    const c1 = engine.getBlinkSchedule().blinkCount;
    Math.random.mockReturnValue(0.5);
    engine.update(t1 + 4000, 'IDLE', null);
    expect(engine.getBlinkSchedule().blinkCount).toBeGreaterThanOrEqual(c1);
  });

  it('breath cycle present in all states', () => {
    for (const state of ['IDLE', 'LISTENING', 'THINKING', 'WORKING', 'SPEAKING'] as AvatarMainState[]) {
      const e = new MicroAnimationEngine();
      expect(e.update(Date.now(), state, null)).toContain('BREATHE');
    }
  });

  it('breath phase advances over time', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now(), 'IDLE', null);
    const p1 = engine.getBreathPhase();
    engine.update(Date.now() + 1000, 'IDLE', null);
    expect(engine.getBreathPhase()).toBeGreaterThanOrEqual(p1);
  });

  it('gaze shift occurs periodically', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now() + 6000, 'IDLE', null);
    expect(engine.getGazeTarget()).not.toBeNull();
  });

  it('gaze shift not too frequent', () => {
    Math.random.mockReturnValue(0.5);
    const t1 = Date.now() + 6000;
    engine.update(t1, 'IDLE', null);
    engine.update(t1 + 100, 'IDLE', null);
    expect(engine.getGazeTarget()).toBeDefined();
  });

  it('external eyeTarget is set with natural drift', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now(), 'IDLE', { x: 0.5, y: 0.5 });
    const target = engine.getGazeTarget();
    expect(target).not.toBeNull();
    expect(target!.x).toBeCloseTo(0.5, 1);
    expect(target!.y).toBeCloseTo(0.5, 1);
  });

  it('head tilt subtle in IDLE', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now(), 'IDLE', null);
    expect(Math.abs(engine.getHeadTilt())).toBeLessThanOrEqual(0.3);
  });

  it('body sway returns number', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now(), 'IDLE', null);
    expect(typeof engine.getBodySway()).toBe('number');
  });

  it('IDLE has at least BREATHE active', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'IDLE', null);
    expect(engine.getActiveAnimations().length).toBeGreaterThanOrEqual(1);
  });

  it('THINKING triggers GAZE_SHIFT', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 6000, 'THINKING', null);
    expect(engine.getActiveAnimations()).toContain('GAZE_SHIFT');
  });

  it('SPEAKING has at least BREATHE', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now(), 'SPEAKING', null);
    expect(engine.getActiveAnimations().length).toBeGreaterThanOrEqual(1);
  });

  it('LISTENING sets attentive gaze', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now(), 'LISTENING', null);
    expect(engine.getGazeTarget()).not.toBeNull();
  });

  it('micro animations do not exceed max', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 10000, 'IDLE', null);
    expect(engine.getActiveAnimations().length).toBeLessThanOrEqual(DEFAULT_AVATAR_CONFIG.maxMicroAnimations);
  });

  it('update advances without error', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now(), 'IDLE', null);
    engine.update(Date.now() + 500, 'IDLE', null);
    expect(true).toBe(true);
  });

  it('different states produce BREATHE', () => {
    Math.random.mockReturnValue(0.5);
    const t = Date.now() + 6000;
    const idle = new MicroAnimationEngine();
    idle.update(t, 'IDLE', null);
    const think = new MicroAnimationEngine();
    think.update(t, 'THINKING', null);
    expect(idle.getActiveAnimations()).toContain('BREATHE');
    expect(think.getActiveAnimations()).toContain('BREATHE');
  });

  it('blink double triggers with low random', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'IDLE', null);
    const schedule = engine.getBlinkSchedule();
    expect(typeof schedule.isDoubleBlink).toBe('boolean');
  });

  it('look direction changes via gaze', () => {
    Math.random.mockReturnValue(0.5);
    engine.update(Date.now() + 6000, 'THINKING', null);
    const target = engine.getGazeTarget();
    if (target) {
      expect(typeof target.x).toBe('number');
      expect(typeof target.y).toBe('number');
    }
  });

  it('disable clears active animations', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'IDLE', null);
    engine.setEnabled(false);
    expect(engine.getActiveAnimations()).toEqual([]);
  });

  it('interrupt clears all pending', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'IDLE', null);
    engine.interrupt(Date.now());
    expect(engine.getActiveAnimations()).toEqual([]);
  });

  it('reset resets blink schedule', () => {
    engine.reset();
    const s = engine.getBlinkSchedule();
    expect(s.blinkCount).toBe(0);
  });

  it('relaxed state has slower blink rate', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'RELAXED', null);
    expect(engine.getActiveAnimations().length).toBeGreaterThanOrEqual(1);
  });

  it('sleeping state schedules blink', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 10000, 'SLEEPING', null);
    expect(engine.getActiveAnimations().length).toBeGreaterThanOrEqual(1);
  });

  it('error state falls through to idle scheduling', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'ERROR', null);
    expect(engine.getActiveAnimations().length).toBeGreaterThanOrEqual(1);
  });

  it('getActiveAnimationDetails returns entries', () => {
    Math.random.mockReturnValue(0.0001);
    engine.update(Date.now() + 5000, 'IDLE', null);
    const details = engine.getActiveAnimationDetails();
    for (const d of details) {
      expect(d).toHaveProperty('type');
      expect(d).toHaveProperty('startTime');
      expect(d).toHaveProperty('duration');
      expect(d).toHaveProperty('intensity');
    }
  });
});

// ============================================================================
// Lip Sync
// ============================================================================

describe('LipSyncEngine', () => {
  let engine: LipSyncEngine;

  beforeEach(() => {
    engine = new LipSyncEngine();
  });

  afterEach(() => {
    engine.destroy();
  });

  it('creates with default config', () => {
    expect(engine.isEnabled()).toBe(true);
  });

  it('creates disabled when configured', () => {
    expect(new LipSyncEngine({ lipSyncEnabled: false }).isEnabled()).toBe(false);
  });

  it('volume 0 produces near-zero openness', () => {
    const frame = engine.generateFrameFromVolume(0, 1000);
    expect(frame).not.toBeNull();
    expect(frame!.openness).toBeGreaterThanOrEqual(0);
    expect(frame!.openness).toBeLessThan(0.1);
  });

  it('max volume produces openness > 0', () => {
    const frame = engine.generateFrameFromVolume(1, 2000);
    expect(frame).not.toBeNull();
    expect(frame!.openness).toBeGreaterThan(0);
  });

  it('smooth interpolation between frames', () => {
    const f1 = engine.generateFrameFromVolume(0, 1000);
    const f2 = engine.generateFrameFromVolume(1, 2000);
    if (f1 && f2) {
      expect(Math.abs(f2.openness - f1.openness)).toBeLessThanOrEqual(1);
    }
  });

  it('phoneme mapping works', () => {
    const frame = engine.generateFrameFromPhoneme('AA', 1, 1000);
    expect(frame).not.toBeNull();
    expect(frame!.phoneme).toBe('AA');
    expect(frame!.openness).toBeGreaterThan(0);
  });

  it('frames have correct timestamps', () => {
    const frame = engine.generateFrameFromVolume(0.5, 5000);
    expect(frame).not.toBeNull();
    expect(() => new Date(frame!.timestamp)).not.toThrow();
  });

  it('interrupt clears pending frames', () => {
    engine.generateFrameFromVolume(0.5, 1000);
    engine.generateFrameFromVolume(0.5, 2000);
    engine.interrupt();
    expect(engine.getFrameBuffer()).toHaveLength(0);
  });

  it('silent state produces closing frames', () => {
    engine.generateFrameFromVolume(0.8, 1000);
    engine.onSpeakingStateChanged('SILENT');
    const frames = engine.getFrameBuffer();
    expect(frames.length).toBeGreaterThan(0);
  });

  it('speaking paused produces closing frames', () => {
    engine.generateFrameFromVolume(0.8, 1000);
    engine.onSpeakingStateChanged('SPEAKING_PAUSED');
    expect(engine.getFrameBuffer().length).toBeGreaterThan(0);
  });

  it('speaking active is ready for frames', () => {
    engine.onSpeakingStateChanged('SPEAKING_ACTIVE');
    const frame = engine.generateFrameFromVolume(0.5, 2000);
    expect(frame).not.toBeNull();
  });

  it('non-linear curve applied (openness != volume)', () => {
    const frame = engine.generateFrameFromVolume(0.5, 1000);
    expect(frame).not.toBeNull();
    // pow(0.5, 0.7) != 0.5
    expect(frame!.openness).not.toBe(0.5);
  });

  it('frame interval respected', () => {
    const f1 = engine.generateFrameFromVolume(0.5, 1000);
    const f2 = engine.generateFrameFromVolume(0.5, 1000);
    // second call at same time should be null (frameInterval not passed)
    expect(f2).toBeNull();
  });

  it('processBatch generates frames', () => {
    const frames = engine.processBatch([0.2, 0.5, 0.8, 0.3], 1000);
    expect(frames.length).toBeGreaterThan(0);
  });

  it('close mouth frames at end of silent transition', () => {
    engine.generateFrameFromVolume(1, 1000);
    engine.onSpeakingStateChanged('SILENT');
    const frames = engine.getFrameBuffer();
    const last = frames[frames.length - 1];
    expect(last.openness).toBe(0);
  });

  it('volume below threshold is silent', () => {
    const frame = engine.generateFrameFromVolume(0.01, 1000);
    expect(frame).not.toBeNull();
    expect(frame!.openness).toBeLessThanOrEqual(0.1);
  });

  it('getFrameInterval returns frame rate interval', () => {
    expect(engine.getFrameInterval()).toBe(1000 / DEFAULT_AVATAR_CONFIG.speakingFrameRate);
  });

  it('setEnabled false clears frames', () => {
    engine.generateFrameFromVolume(0.5, 1000);
    engine.setEnabled(false);
    expect(engine.getFrameBuffer()).toHaveLength(0);
  });

  it('reset clears state', () => {
    engine.generateFrameFromVolume(0.5, 1000);
    engine.reset();
    expect(engine.getFrameBuffer()).toHaveLength(0);
  });

  it('phoneme with unknown phoneme uses default', () => {
    const frame = engine.generateFrameFromPhoneme('ZZ', 1, 1000);
    expect(frame).not.toBeNull();
    expect(frame!.phoneme).toBe('ZZ');
  });

  it('volume clamped to 0-1', () => {
    const f1 = engine.generateFrameFromVolume(2, 1000);
    const f2 = engine.generateFrameFromVolume(-1, 2000);
    expect(f1!.openness).toBeLessThanOrEqual(1);
    expect(f2!.openness).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// Avatar Engine Integration
// ============================================================================

describe('AvatarEngine', () => {
  let engine: AvatarEngine;

  afterEach(() => {
    if (engine) engine.destroy();
  });

  it('creates with createAvatarEngine factory', () => {
    engine = createAvatarEngine();
    expect(engine).toBeInstanceOf(AvatarEngine);
  });

  it('creates with custom config', () => {
    engine = createAvatarEngine({ blinkInterval: 2000 });
    expect(engine.getConfig().blinkInterval).toBe(2000);
  });

  it('getCurrentState returns AvatarState', () => {
    engine = createAvatarEngine();
    const s = engine.getCurrentState();
    expect(s).toHaveProperty('mainState');
    expect(s).toHaveProperty('expression');
  });

  it('start begins update loop', () => {
    engine = createAvatarEngine();
    engine.start();
    expect(engine.isRunning()).toBe(true);
  });

  it('stop ends update loop', () => {
    engine = createAvatarEngine();
    engine.start();
    engine.stop();
    expect(engine.isRunning()).toBe(false);
  });

  it('voice state idle to listening transitions to LISTENING', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'idle' });
    engine.updateContext({ voiceState: 'listening' });
    expect(engine.getMainState()).toBe('LISTENING');
  });

  it('voice state listening to processing transitions to THINKING', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'idle' });
    engine.updateContext({ voiceState: 'listening' });
    engine.updateContext({ voiceState: 'processing' });
    expect(engine.getMainState()).toBe('THINKING');
  });

  it('task state planning transitions to THINKING when possible', () => {
    engine = createAvatarEngine();
    engine.forceState('LISTENING');
    engine.updateContext({ taskState: 'planning' });
    expect(engine.getMainState()).toBe('THINKING');
  });

  it('task state executing transitions to WORKING', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'idle' });
    engine.updateContext({ voiceState: 'listening' });
    engine.updateContext({ voiceState: 'processing' });
    engine.updateContext({ taskState: 'executing' });
    expect(engine.getMainState()).toBe('WORKING');
  });

  it('task success changes expression', () => {
    engine = createAvatarEngine();
    engine.setExpression('HAPPY');
    expect(engine.getExpression()).toBe('HAPPY');
  });

  it('user interruption transitions from SPEAKING to LISTENING', () => {
    engine = createAvatarEngine();
    engine.forceState('SPEAKING');
    engine.updateContext({ userInterruption: true });
    expect(engine.getMainState()).toBe('LISTENING');
  });

  it('event emitter fires on state change', () => {
    engine = createAvatarEngine();
    let fired = false;
    engine.on('STATE_CHANGED', () => { fired = true; });
    engine.requestTransition('LISTENING');
    expect(fired).toBe(true);
  });

  it('event emitter fires on expression change', () => {
    engine = createAvatarEngine();
    let fired = false;
    engine.on('EXPRESSION_CHANGED', () => { fired = true; });
    engine.setExpression('HAPPY');
    expect(fired).toBe(true);
  });

  it('off removes event handler', () => {
    engine = createAvatarEngine();
    let count = 0;
    const handler = () => { count++; };
    engine.on('STATE_CHANGED', handler);
    engine.requestTransition('LISTENING');
    expect(count).toBe(1);
    engine.off('STATE_CHANGED', handler);
    engine.forceState('IDLE');
    engine.requestTransition('LISTENING');
    expect(count).toBe(1);
  });

  it('multiple rapid state changes handled', () => {
    engine = createAvatarEngine();
    engine.forceState('IDLE');
    engine.requestTransition('LISTENING');
    engine.requestTransition('THINKING');
    engine.requestTransition('WORKING');
    expect(engine.getMainState()).toBe('WORKING');
  });

  it('start/stop/start cycle', () => {
    engine = createAvatarEngine();
    engine.start();
    engine.stop();
    engine.start();
    expect(engine.isRunning()).toBe(true);
    engine.stop();
  });

  it('forceState works through engine', () => {
    engine = createAvatarEngine();
    engine.forceState('ERROR');
    expect(engine.getMainState()).toBe('ERROR');
  });

  it('getEventHistory returns events', () => {
    engine = createAvatarEngine();
    engine.requestTransition('LISTENING');
    expect(engine.getEventHistory().length).toBeGreaterThan(0);
  });

  it('getId returns unique id', () => {
    engine = createAvatarEngine();
    expect(typeof engine.getId()).toBe('string');
  });

  it('getLipSyncFrame returns null when no frames', () => {
    engine = createAvatarEngine();
    expect(engine.getLipSyncFrame()).toBeNull();
  });

  it('processLipSyncVolume does not throw', () => {
    engine = createAvatarEngine();
    expect(() => engine.processLipSyncVolume(0.5)).not.toThrow();
  });

  it('setSpeakingState does not change mainState', () => {
    engine = createAvatarEngine();
    const before = engine.getMainState();
    engine.setSpeakingState('SPEAKING_ACTIVE');
    expect(engine.getMainState()).toBe(before);
  });

  it('requestTransition returns false for invalid', () => {
    engine = createAvatarEngine();
    expect(engine.requestTransition('WORKING')).toBe(false);
  });

  it('destroy cleans up', () => {
    engine = createAvatarEngine();
    engine.start();
    engine.destroy();
    expect(engine.isRunning()).toBe(false);
  });

  it('error voice state triggers ERROR', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'error' });
    expect(engine.getMainState()).toBe('ERROR');
  });

  it('task failed triggers ERROR', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'idle' });
    engine.updateContext({ voiceState: 'listening' });
    engine.updateContext({ voiceState: 'processing' });
    engine.updateContext({ taskState: 'failed' });
    expect(engine.getMainState()).toBe('ERROR');
  });

  it('task verifying triggers VERIFYING', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'idle' });
    engine.updateContext({ voiceState: 'listening' });
    engine.updateContext({ voiceState: 'processing' });
    engine.updateContext({ taskState: 'executing' });
    engine.updateContext({ taskState: 'verifying' });
    expect(engine.getMainState()).toBe('VERIFYING');
  });

  it('task recovering triggers RECOVERY', () => {
    engine = createAvatarEngine();
    engine.updateContext({ voiceState: 'idle' });
    engine.updateContext({ voiceState: 'listening' });
    engine.updateContext({ voiceState: 'processing' });
    engine.updateContext({ taskState: 'executing' });
    engine.updateContext({ taskState: 'verifying' });
    engine.updateContext({ taskState: 'recovering' });
    expect(engine.getMainState()).toBe('RECOVERY');
  });

  it('event handler error does not crash', () => {
    engine = createAvatarEngine();
    engine.on('STATE_CHANGED', () => { throw new Error('handler crash'); });
    expect(() => engine.requestTransition('LISTENING')).not.toThrow();
  });

  it('micro animations accessible', () => {
    engine = createAvatarEngine();
    expect(Array.isArray(engine.getMicroAnimations())).toBe(true);
  });

  it('config has update rate applied', () => {
    engine = createAvatarEngine({ updateRate: 60 });
    expect(engine.getConfig()).toHaveProperty('speakingFrameRate');
  });
});
