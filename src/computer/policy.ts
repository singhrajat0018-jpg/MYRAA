// ============================================================================
// MYRAA Action Policy — Risk assessment, approval, safety gates
// ============================================================================

import type {
  ComputerAction, ActionType, ActionRisk, ActionSource,
  UITarget, AutomationBudget, DEFAULT_AUTOMATION_BUDGET,
} from './contracts';

// ============================================================================
// Policy Rule
// ============================================================================

export interface PolicyRule {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly condition: (action: ComputerAction, context: PolicyContext) => boolean;
  readonly risk: ActionRisk;
  readonly requiresApproval: boolean;
  readonly blockMessage?: string;
}

export interface PolicyContext {
  readonly budget: AutomationBudget;
  readonly recentActions: readonly ComputerAction[];
  readonly takeoverActive: boolean;
  readonly activeWindow?: { processName: string; title: string } | null;
}

// ============================================================================
// Policy Engine
// ============================================================================

export class PolicyEngine {
  private rules: PolicyRule[] = [];
  private approvalHistory: Map<string, boolean> = new Map();

  constructor() {
    this.registerBuiltinRules();
  }

  // --- Evaluation ---

  evaluate(action: ComputerAction, context: PolicyContext): PolicyDecision {
    // Budget check
    if (!context.budget.withinBudget) {
      return {
        approved: false,
        risk: 'CRITICAL',
        reason: 'Automation budget exceeded',
        requiresApproval: false,
        blockedBy: 'BUDGET',
      };
    }

    // Takeover check
    if (context.takeoverActive) {
      return {
        approved: false,
        risk: 'HIGH',
        reason: 'User takeover active',
        requiresApproval: false,
        blockedBy: 'TAKEOVER',
      };
    }

    // Check rules
    for (const rule of this.rules) {
      if (rule.condition(action, context)) {
        return {
          approved: !rule.requiresApproval,
          risk: rule.risk,
          reason: rule.blockMessage ?? rule.name,
          requiresApproval: rule.requiresApproval,
          blockedBy: rule.id,
        };
      }
    }

    // Default: approve low-risk, require approval for high-risk
    const risk = this.assessRisk(action);
    return {
      approved: risk !== 'CRITICAL' && risk !== 'HIGH',
      risk,
      reason: `Auto-approved (${risk})`,
      requiresApproval: risk === 'HIGH' || risk === 'CRITICAL',
    };
  }

  // --- Risk Assessment ---

  assessRisk(action: ComputerAction): ActionRisk {
    let risk: ActionRisk = 'SAFE';

    // High-risk actions
    const highRiskTypes: ActionType[] = ['CLOSE_APP', 'DRAG'];
    if (highRiskTypes.includes(action.type)) risk = 'HIGH';

    // Moderate risk
    const moderateRiskTypes: ActionType[] = ['TYPE_TEXT', 'PASTE_TEXT', 'HOTKEY'];
    if (moderateRiskTypes.includes(action.type) && risk === 'SAFE') risk = 'MODERATE';

    // Auto-approved sources are lower risk
    if (action.source === 'APPROVED_AUTOMATION' && risk === 'MODERATE') risk = 'SAFE';

    return risk;
  }

  // --- Rules ---

  private registerBuiltinRules(): void {
    this.rules = [
      {
        id: 'NO_CLOSE_UNVERIFIED',
        name: 'No unverified close',
        description: 'Block closing apps without prior verification',
        condition: (a) => a.type === 'CLOSE_APP',
        risk: 'HIGH',
        requiresApproval: true,
        blockMessage: 'App close requires verification',
      },
      {
        id: 'DRAG_REQUIRES_TARGET',
        name: 'Drag requires valid target',
        description: 'Block drags without clear target',
        condition: (a) => a.type === 'DRAG' && !a.target,
        risk: 'MODERATE',
        requiresApproval: true,
        blockMessage: 'Drag without explicit target requires approval',
      },
      {
        id: 'LOW_CONFIDENCE_BLOCK',
        name: 'Low confidence block',
        description: 'Block actions with very low confidence',
        condition: (a) => a.confidence < 0.3,
        risk: 'HIGH',
        requiresApproval: true,
        blockMessage: `Confidence ${(a: ComputerAction) => (a.confidence * 100).toFixed(0)}% too low`,
      },
      {
        id: 'CRITICAL_RISK_BLOCK',
        name: 'Critical risk block',
        description: 'Block critical risk actions',
        condition: (a) => a.risk === 'CRITICAL',
        risk: 'CRITICAL',
        requiresApproval: false,
        blockMessage: 'Critical risk action blocked',
      },
    ];
  }

  addRule(rule: PolicyRule): void {
    this.rules.push(rule);
  }

  removeRule(ruleId: string): boolean {
    const idx = this.rules.findIndex(r => r.id === ruleId);
    if (idx >= 0) { this.rules.splice(idx, 1); return true; }
    return false;
  }

  getRules(): readonly PolicyRule[] {
    return this.rules;
  }

  // --- Approval ---

  recordApproval(actionId: string, approved: boolean): void {
    this.approvalHistory.set(actionId, approved);
  }

  isApproved(actionId: string): boolean {
    return this.approvalHistory.get(actionId) ?? false;
  }
}

// ============================================================================
// Policy Decision
// ============================================================================

export interface PolicyDecision {
  readonly approved: boolean;
  readonly risk: ActionRisk;
  readonly reason: string;
  readonly requiresApproval: boolean;
  readonly blockedBy?: string;
}
