export class ExecutionFirewall {
  readonly liveTradeExecution = false;
  readonly transferFunds = false;
  readonly allowLlmOverride = false;

  isBlocked(action: string): boolean {
    return true;
  }

  getStatus() {
    return {
      active: true,
      firewallMode: "STRICT_READONLY",
      liveTradeExecution: false,
      transferFunds: false,
    };
  }

  getPolicy() {
    return {
      liveTradingExecution: "DISABLED",
      transferFunds: "DISABLED",
      allowLlmOverride: false,
    };
  }

  getAuditLog() {
    return [];
  }

  classifyCapability(action: string): string {
    return "FINANCIAL_EXECUTION_BLOCKED";
  }

  evaluate(action: string, classification?: string) {
    return {
      allowed: false,
      reason: "Financial execution permanently disabled by safety policy.",
    };
  }
}

export const GLOBAL_FIREWALL = new ExecutionFirewall();
