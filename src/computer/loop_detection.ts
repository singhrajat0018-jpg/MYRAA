// ============================================================================
// MYRAA Loop Detection — Detect repetitive action loops and stuck states
// ============================================================================

import type { ComputerAction, ActionType, ComputerFailureType } from './contracts';

// ============================================================================
// Loop Detector
// ============================================================================

export interface LoopSignature {
  readonly actionSequence: string;
  readonly targetHash: string;
  readonly count: number;
}

export interface StuckState {
  readonly detected: boolean;
  readonly stuckType: 'REPEATED_ACTION' | 'REPEATED_FAILURE' | 'TARGET_OSCILLATION' | 'NONE';
  readonly actionCount: number;
  readonly failureCount: number;
  readonly similarActionCount: number;
  readonly recommendation: string;
}

export class LoopDetector {
  private actionHistory: ComputerAction[] = [];
  private failureHistory: ComputerFailureType[] = [];
  private maxHistory = 50;
  private loopThreshold = 3;
  private timeWindowMs = 30_000;

  // --- Detection ---

  recordAction(action: ComputerAction): void {
    this.actionHistory.push(action);
    if (this.actionHistory.length > this.maxHistory) this.actionHistory.shift();
  }

  recordFailure(failure: ComputerFailureType): void {
    this.failureHistory.push(failure);
    if (this.failureHistory.length > this.maxHistory) this.failureHistory.shift();
  }

  detectLoop(): LoopSignature | null {
    if (this.actionHistory.length < this.loopThreshold) return null;

    const recent = this.actionHistory.slice(-this.loopThreshold);

    // Check same action type
    const types = recent.map(a => a.type);
    if (types.every(t => t === types[0])) {
      // Check same target area (within 20px)
      const targets = recent.map(a => a.coordinates ?? (a.target ? { x: a.target.bounds.x, y: a.target.bounds.y } : null));
      const sameTarget = targets.every(t =>
        t && targets[0] && Math.abs(t.x - targets[0].x) < 20 && Math.abs(t.y - targets[0].y) < 20,
      );

      if (sameTarget) {
        return {
          actionSequence: types.join('→'),
          targetHash: targets[0] ? `${targets[0].x},${targets[0].y}` : 'none',
          count: this.loopThreshold,
        };
      }
    }

    return null;
  }

  // --- Stuck Detection ---

  detectStuck(): StuckState {
    const now = Date.now();
    const recentWindow = this.actionHistory.filter(a =>
      new Date(a.timestamp).getTime() > now - this.timeWindowMs,
    );

    const recentFailures = this.failureHistory.slice(-5);

    // Repeated action
    if (recentWindow.length >= this.loopThreshold) {
      const types = recentWindow.map(a => a.type);
      const allSame = types.every(t => t === types[0]);
      if (allSame) {
        return {
          detected: true,
          stuckType: 'REPEATED_ACTION',
          actionCount: recentWindow.length,
          failureCount: recentFailures.length,
          similarActionCount: recentWindow.length,
          recommendation: `Repeated ${types[0]} ${recentWindow.length} times. Consider different approach.`,
        };
      }
    }

    // Repeated failure
    if (recentFailures.length >= 3) {
      const types = recentFailures.slice(-3);
      const allSame = types.every(t => t === types[0]);
      if (allSame) {
        return {
          detected: true,
          stuckType: 'REPEATED_FAILURE',
          actionCount: recentWindow.length,
          failureCount: recentFailures.length,
          similarActionCount: recentFailures.length,
          recommendation: `Repeated ${types[0]} failure. Escalating.`,
        };
      }
    }

    // Target oscillation (same action alternating between two targets)
    if (recentWindow.length >= 4) {
      const coords = recentWindow.map(a => {
        const c = a.coordinates ?? (a.target ? { x: a.target.bounds.x, y: a.target.bounds.y } : null);
        return c ? `${Math.round(c.x / 20)},${Math.round(c.y / 20)}` : 'none';
      });
      const pattern = coords.slice(-4);
      if (pattern[0] === pattern[2] && pattern[1] === pattern[3] && pattern[0] !== pattern[1]) {
        return {
          detected: true,
          stuckType: 'TARGET_OSCILLATION',
          actionCount: recentWindow.length,
          failureCount: recentFailures.length,
          similarActionCount: 4,
          recommendation: 'Target oscillation detected. Action bouncing between two positions.',
        };
      }
    }

    return {
      detected: false,
      stuckType: 'NONE',
      actionCount: recentWindow.length,
      failureCount: recentFailures.length,
      similarActionCount: 0,
      recommendation: '',
    };
  }

  // --- Reset ---

  reset(): void {
    this.actionHistory = [];
    this.failureHistory = [];
  }

  getActionCount(): number {
    return this.actionHistory.length;
  }

  getFailureCount(): number {
    return this.failureHistory.length;
  }
}
