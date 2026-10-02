// ============================================================================
// MYRAA Avatar Expression Engine — Deterministic Expression Mapping
// ============================================================================

import type {
  AvatarExpression,
  AvatarContext,
  ExpressionRule,
  VoiceState,
  TaskState,
} from './contracts';

// ============================================================================
// Expression Interpolation Helper
// ============================================================================

interface ExpressionBlend {
  readonly from: AvatarExpression;
  readonly to: AvatarExpression;
  readonly progress: number;
  readonly target: AvatarExpression;
}

// ============================================================================
// Default Expression Rules (ordered by priority, first match wins)
// ============================================================================

const DEFAULT_EXPRESSION_RULES: readonly ExpressionRule[] = [
  // --- High priority: Interruption / Error ---
  { voiceState: null, taskState: null, taskSuccess: null, taskFailure: null, userInterruption: true, urgency: null, expression: 'SURPRISED', confidence: 0.95 },
  { voiceState: 'error', taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'CONCERNED', confidence: 0.9 },
  { voiceState: null, taskState: 'failed', taskSuccess: null, taskFailure: true, userInterruption: null, urgency: null, expression: 'CONCERNED', confidence: 0.9 },
  { voiceState: null, taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: 'high', expression: 'FOCUSED', confidence: 0.85 },

  // --- Voice-driven expressions ---
  { voiceState: 'listening', taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'ATTENTIVE', confidence: 0.9 },
  { voiceState: 'speaking', taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'CONVERSATIONAL', confidence: 0.85 },
  { voiceState: 'processing', taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'THOUGHTFUL', confidence: 0.85 },
  { voiceState: 'interrupted', taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'SURPRISED', confidence: 0.8 },

  // --- Task-driven expressions ---
  { voiceState: null, taskState: 'planning', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'THOUGHTFUL', confidence: 0.85 },
  { voiceState: null, taskState: 'gathering', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'FOCUSED', confidence: 0.85 },
  { voiceState: null, taskState: 'executing', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'FOCUSED', confidence: 0.85 },
  { voiceState: null, taskState: 'verifying', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'CURIOUS', confidence: 0.8 },
  { voiceState: null, taskState: 'recovering', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'CONCERNED', confidence: 0.8 },
  { voiceState: null, taskState: 'complete', taskSuccess: true, taskFailure: null, userInterruption: null, urgency: null, expression: 'HAPPY', confidence: 0.85 },
  { voiceState: null, taskState: 'failed', taskSuccess: false, taskFailure: true, userInterruption: null, urgency: null, expression: 'SAD', confidence: 0.85 },
  { voiceState: null, taskState: 'cancelled', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'CALM', confidence: 0.75 },

  // --- Success / Failure (independent of task state) ---
  { voiceState: null, taskState: null, taskSuccess: true, taskFailure: null, userInterruption: null, urgency: null, expression: 'HAPPY', confidence: 0.8 },
  { voiceState: null, taskState: null, taskSuccess: false, taskFailure: true, userInterruption: null, urgency: null, expression: 'CONCERNED', confidence: 0.8 },

  // --- Idle states ---
  { voiceState: 'idle', taskState: 'idle', taskSuccess: null, taskFailure: null, userInterruption: null, urgency: null, expression: 'NEUTRAL', confidence: 0.7 },
  { voiceState: null, taskState: null, taskSuccess: null, taskFailure: null, userInterruption: null, urgency: 'low', expression: 'CALM', confidence: 0.6 },
];

// ============================================================================
// Expression Weights for blending
// ============================================================================

const EXPRESSION_WEIGHTS: Record<AvatarExpression, number> = {
  NEUTRAL: 0.5,
  HAPPY: 0.6,
  EXCITED: 0.7,
  CALM: 0.4,
  CURIOUS: 0.5,
  CONCERNED: 0.6,
  SAD: 0.5,
  SURPRISED: 0.8,
  CONFUSED: 0.5,
  ANGRY: 0.7,
  FOCUSED: 0.6,
  ATTENTIVE: 0.6,
  CONVERSATIONAL: 0.5,
  THOUGHTFUL: 0.5,
  RELAXED: 0.3,
  SLEEPY: 0.3,
};

// ============================================================================
// ExpressionEngine
// ============================================================================

export class ExpressionEngine {
  private _rules: ExpressionRule[];
  private currentExpression: AvatarExpression = 'NEUTRAL';
  private previousExpression: AvatarExpression = 'NEUTRAL';
  private expressionStartTime: number = Date.now();
  private blendProgress: number = 1;
  private blending: boolean = false;
  private expressionHistory: Array<{ expression: AvatarExpression; timestamp: string; confidence: number }> = [];
  private maxHistory: number = 50;
  private interruptionTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(rules?: readonly ExpressionRule[]) {
    this._rules = rules ? [...rules] : [...DEFAULT_EXPRESSION_RULES];
  }

  // --- Core API ---

  getCurrentExpression(): AvatarExpression {
    return this.currentExpression;
  }

  getBlendedExpression(): AvatarExpression {
    if (!this.blending || this.blendProgress >= 1) {
      return this.currentExpression;
    }
    return this.blendProgress < 0.5 ? this.previousExpression : this.currentExpression;
  }

  getBlendProgress(): number {
    return this.blendProgress;
  }

  isBlending(): boolean {
    return this.blending;
  }

  getExpressionHistory(): Array<{ expression: AvatarExpression; timestamp: string; confidence: number }> {
    return this.expressionHistory;
  }

  // --- Evaluate Expression from Context ---

  evaluateExpression(context: AvatarContext): AvatarExpression {
    const matched = this.findMatchingRule(context);
    if (!matched) {
      return this.resolveIdleExpression(context);
    }
    return matched;
  }

  // --- Update Expression (with smooth blending) ---

  update(context: AvatarContext): AvatarExpression {
    const newExpression = this.evaluateExpression(context);

    if (newExpression !== this.currentExpression) {
      this.previousExpression = this.currentExpression;
      this.currentExpression = newExpression;
      this.expressionStartTime = Date.now();
      this.blendProgress = 0;
      this.blending = true;

      this.expressionHistory.push({
        expression: newExpression,
        timestamp: new Date().toISOString(),
        confidence: this.findConfidence(context),
      });

      // Trim history
      if (this.expressionHistory.length > this.maxHistory) {
        this.expressionHistory = this.expressionHistory.slice(-this.maxHistory);
      }
    }

    // Advance blend
    if (this.blending) {
      this.blendProgress = Math.min(1, this.blendProgress + 0.05);
      if (this.blendProgress >= 1) {
        this.blending = false;
      }
    }

    return this.currentExpression;
  }

  // --- Handle Interruption (brief SURPRISED flash) ---

  handleInterruption(durationMs: number = 400): AvatarExpression {
    if (this.interruptionTimer !== null) {
      clearTimeout(this.interruptionTimer);
    }

    this.previousExpression = this.currentExpression;
    this.currentExpression = 'SURPRISED';
    this.expressionStartTime = Date.now();
    this.blendProgress = 0;
    this.blending = true;

    this.expressionHistory.push({
      expression: 'SURPRISED',
      timestamp: new Date().toISOString(),
      confidence: 0.95,
    });

    // Revert after duration
    this.interruptionTimer = setTimeout(() => {
      this.currentExpression = this.previousExpression;
      this.blendProgress = 0;
      this.blending = true;
      this.interruptionTimer = null;
    }, durationMs);

    return 'SURPRISED';
  }

  // --- Force Expression (for testing / explicit control) ---

  forceExpression(expression: AvatarExpression): void {
    if (this.interruptionTimer !== null) {
      clearTimeout(this.interruptionTimer);
      this.interruptionTimer = null;
    }
    this.previousExpression = this.currentExpression;
    this.currentExpression = expression;
    this.expressionStartTime = Date.now();
    this.blendProgress = 1;
    this.blending = false;
  }

  // --- Rule Management ---

  addRule(rule: ExpressionRule): void {
    this._rules.push(rule);
  }

  getRules(): readonly ExpressionRule[] {
    return this._rules;
  }

  // --- Private Helpers ---

  private findMatchingRule(context: AvatarContext): AvatarExpression | null {
    let bestMatch: { expression: AvatarExpression; confidence: number } | null = null;

    for (const rule of this._rules) {
      if (this.matchesRule(rule, context)) {
        if (!bestMatch || rule.confidence > bestMatch.confidence) {
          bestMatch = { expression: rule.expression, confidence: rule.confidence };
        }
      }
    }

    return bestMatch?.expression ?? null;
  }

  private matchesRule(rule: ExpressionRule, context: AvatarContext): boolean {
    if (rule.voiceState !== null && rule.voiceState !== context.voiceState) return false;
    if (rule.taskState !== null && rule.taskState !== context.taskState) return false;
    if (rule.taskSuccess !== null && rule.taskSuccess !== context.taskSuccess) return false;
    if (rule.taskFailure !== null && rule.taskFailure !== context.taskFailure) return false;
    if (rule.userInterruption !== null && rule.userInterruption !== context.userInterruption) return false;
    if (rule.urgency !== null && rule.urgency !== context.urgency) return false;
    return true;
  }

  private findConfidence(context: AvatarContext): number {
    const matched = this.findMatchingRule(context);
    if (!matched) return 0.5;

    const rule = this._rules.find(r => r.expression === matched && this.matchesRule(r, context));
    return rule?.confidence ?? 0.5;
  }

  private resolveIdleExpression(context: AvatarContext): AvatarExpression {
    if (context.idleDurationMs > 120_000) return 'SLEEPY';
    if (context.idleDurationMs > 60_000) return 'RELAXED';
    if (context.errorCount > 3) return 'CONCERNED';
    return 'NEUTRAL';
  }

  // --- Cleanup ---

  destroy(): void {
    if (this.interruptionTimer !== null) {
      clearTimeout(this.interruptionTimer);
      this.interruptionTimer = null;
    }
  }
}
