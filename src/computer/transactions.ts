// ============================================================================
// MYRAA Action Transactions — Atomic multi-step action execution with rollback
// ============================================================================

import type {
  ComputerAction, ActionStep, ActionTransaction, ActionVerification,
  TransactionStatus,
} from './contracts';

// ============================================================================
// Transaction Manager
// ============================================================================

export class TransactionManager {
  private activeTransactions: Map<string, ActionTransaction> = new Map();
  private completedTransactions: ActionTransaction[] = [];
  private maxHistory = 100;

  // --- Transaction Lifecycle ---

  createTransaction(steps: ComputerAction[]): ActionTransaction {
    const txId = `tx_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const actionSteps: ActionStep[] = steps.map(action => ({
      actionId: action.actionId,
      action,
      preconditions: [],
      postconditions: [],
      status: 'PENDING',
    }));

    const tx: ActionTransaction = {
      transactionId: txId,
      steps: actionSteps,
      status: 'PENDING',
      rollbackPlan: steps.filter(a => a.reversible).map(a => a.actionId),
      createdAt: new Date().toISOString(),
    };

    this.activeTransactions.set(txId, tx);
    return tx;
  }

  async executeTransaction(
    txId: string,
    executor: (action: ComputerAction) => Promise<ActionVerification>,
  ): Promise<ActionTransaction> {
    const tx = this.activeTransactions.get(txId);
    if (!tx) throw new Error(`Transaction ${txId} not found`);

    this.updateStatus(tx, 'EXECUTING');

    for (const step of tx.steps) {
      if (step.status === 'SKIPPED') continue;

      step.status = 'EXECUTING';
      try {
        const verification = await executor(step.action);
        step.verification = verification;
        step.status = verification.passed ? 'COMPLETED' : 'FAILED';

        if (!verification.passed) {
          step.error = `Verification failed: ${verification.actual ?? 'unknown'}`;
          this.updateStatus(tx, 'FAILED');
          return tx;
        }
      } catch (err) {
        step.status = 'FAILED';
        step.error = err instanceof Error ? err.message : 'Unknown error';
        this.updateStatus(tx, 'FAILED');
        return tx;
      }
    }

    this.updateStatus(tx, 'COMPLETED');
    tx.completedAt = new Date().toISOString();
    this.archiveTransaction(tx);
    return tx;
  }

  // --- Rollback ---

  async rollbackTransaction(
    txId: string,
    rollbackExecutor: (actionId: string) => Promise<boolean>,
  ): Promise<boolean> {
    const tx = this.activeTransactions.get(txId) ?? this.completedTransactions.find(t => t.transactionId === txId);
    if (!tx) return false;

    this.updateStatus(tx, 'ROLLED_BACK');

    // Execute rollback in reverse order
    const reversibleSteps = [...tx.steps]
      .filter(s => s.status === 'COMPLETED' && tx.rollbackPlan.includes(s.actionId))
      .reverse();

    for (const step of reversibleSteps) {
      try {
        await rollbackExecutor(step.actionId);
      } catch {
        // Rollback failure is logged but doesn't stop other rollbacks
      }
    }

    return true;
  }

  // --- Query ---

  getTransaction(txId: string): ActionTransaction | undefined {
    return this.activeTransactions.get(txId) ?? this.completedTransactions.find(t => t.transactionId === txId);
  }

  getActiveTransactions(): readonly ActionTransaction[] {
    return [...this.activeTransactions.values()];
  }

  getCompletedTransactions(): readonly ActionTransaction[] {
    return this.completedTransactions;
  }

  // --- Helpers ---

  private updateStatus(tx: ActionTransaction, status: TransactionStatus): void {
    (tx as { status: TransactionStatus }).status = status;
  }

  private archiveTransaction(tx: ActionTransaction): void {
    this.activeTransactions.delete(tx.transactionId);
    this.completedTransactions.push(tx);
    if (this.completedTransactions.length > this.maxHistory) {
      this.completedTransactions.shift();
    }
  }

  // --- Stats ---

  getStats(): { active: number; completed: number; failed: number; rolledBack: number } {
    const completed = this.completedTransactions.filter(t => t.status === 'COMPLETED').length;
    const failed = this.completedTransactions.filter(t => t.status === 'FAILED').length;
    const rolledBack = this.completedTransactions.filter(t => t.status === 'ROLLED_BACK').length;
    return { active: this.activeTransactions.size, completed, failed, rolledBack };
  }
}
