// ============================================================================
// MYRAA Phase 27 — Hard Financial Execution Firewall
// ============================================================================
// IMMOVABLE BARRIER: No live trade execution, no fund transfers,
// no broker API integration, LLM cannot override.
// ============================================================================

import type {
  FirewallDecision, FirewallPolicy, CapabilityClassification,
  OrderIntent,
} from './contracts';

const DEFAULT_POLICY: FirewallPolicy = {
  liveTradeExecution: false,
  transferFunds: false,
  simulateTrade: true,
  readMarketData: true,
  allowLlmOverride: false,
};

export class ExecutionFirewall {
  private readonly policy: FirewallPolicy;
  private readonly auditLog: Array<{
    timestamp: string;
    action: string;
    classification: CapabilityClassification;
    allowed: boolean;
    reason: string;
  }> = [];

  constructor(policy?: Partial<FirewallPolicy>) {
    this.policy = { ...DEFAULT_POLICY, ...policy };
    if (policy?.liveTradeExecution === true) {
      throw new Error('FIREWALL VIOLATION: liveTradeExecution cannot be set to true. This is a hardcoded safety boundary.');
    }
    if (policy?.transferFunds === true) {
      throw new Error('FIREWALL VIOLATION: transferFunds cannot be set to true. This is a hardcoded safety boundary.');
    }
    if (policy?.allowLlmOverride === true) {
      throw new Error('FIREWALL VIOLATION: allowLlmOverride cannot be set to true. This is a hardcoded safety boundary.');
    }
  }

  classifyCapability(action: string): CapabilityClassification {
    const lower = action.toLowerCase();
    if (lower.includes('simulate') || lower.includes('paper_trade') || lower.includes('paper_position')
        || lower.includes('paper_open') || lower.includes('paper_close')
        || (lower.includes('paper') && !lower.includes('execute'))
        || lower.includes('backtest')) {
      return 'SIMULATE_TRADE';
    }
    if (lower.includes('execute_trade') || lower.includes('place_order') || lower.includes('buy_stock')
        || lower.includes('sell_stock') || lower.includes('short_stock') || lower.includes('open_position')
        || lower.includes('close_position') || lower.includes('broker')) {
      return 'EXECUTE_TRADE';
    }
    if (lower.includes('transfer') || lower.includes('withdraw') || lower.includes('deposit')
        || lower.includes('fund') || lower.includes('payment')) {
      return 'TRANSFER_FUNDS';
    }
    return 'READ_MARKET_DATA';
  }

  evaluateIntent(intent: OrderIntent): FirewallDecision {
    const classification = this.classifyCapability('execute_trade');
    return this.evaluate('execute_trade', classification);
  }

  evaluate(action: string, classification?: CapabilityClassification): FirewallDecision {
    const cap = classification ?? this.classifyCapability(action);
    let allowed = false;
    let reason = '';
    let overrideLevel: 'NONE' | 'STRICT' | 'FLEXIBLE' = 'NONE';

    switch (cap) {
      case 'READ_MARKET_DATA':
        allowed = this.policy.readMarketData;
        reason = allowed ? 'Read-only market data access permitted' : 'Market data access disabled by policy';
        break;
      case 'SIMULATE_TRADE':
        allowed = this.policy.simulateTrade;
        reason = allowed ? 'Paper/simulation trading permitted' : 'Simulation trading disabled by policy';
        break;
      case 'EXECUTE_TRADE':
        allowed = false;
        reason = 'LIVE TRADE EXECUTION is HARD-BLOCKED. This system is advisory-only. No real trades are permitted.';
        overrideLevel = 'STRICT';
        break;
      case 'TRANSFER_FUNDS':
        allowed = false;
        reason = 'FUND TRANSFERS are HARD-BLOCKED. This system cannot move real money.';
        overrideLevel = 'STRICT';
        break;
    }

    this.auditLog.push({
      timestamp: new Date().toISOString(),
      action,
      classification: cap,
      allowed,
      reason,
    });

    return { allowed, classification: cap, reason, overrideLevel };
  }

  getAuditLog(): Array<{
    timestamp: string;
    action: string;
    classification: CapabilityClassification;
    allowed: boolean;
    reason: string;
  }> {
    return [...this.auditLog];
  }

  getPolicy(): FirewallPolicy {
    return { ...this.policy };
  }

  canOverride(): boolean {
    return false;
  }

  explainDenial(action: string): string {
    const classification = this.classifyCapability(action);
    const result = this.evaluate(action, classification);
    if (result.allowed) return `${action} is permitted (${classification}).`;
    return `DENIED: ${result.reason} Action '${action}' classified as ${classification}. This is a non-overridable safety boundary.`;
  }
}

export const GLOBAL_FIREWALL = new ExecutionFirewall();
