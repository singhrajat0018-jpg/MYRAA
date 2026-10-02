// ============================================================================
// MYRAA Phase 25 — Plan Patching: Minimal Replanning
// ============================================================================

import type { PlanPatch, PlanPatchType } from './contracts';

// ============================================================================
// Plan Patcher
// ============================================================================

export class PlanPatcher {
  private patches: PlanPatch[] = [];
  private maxPatches = 50;

  // --- Patch Operations ---

  insertTask(
    planId: string,
    afterTaskId: string,
    newTask: unknown,
    reason: string,
  ): PlanPatch {
    const patch = this.makePatch(planId, 'INSERT_TASK', afterTaskId, undefined, newTask, reason);
    this.patches.push(patch);
    return patch;
  }

  removeTask(planId: string, taskId: string, reason: string): PlanPatch {
    const patch = this.makePatch(planId, 'REMOVE_TASK', taskId, undefined, undefined, reason);
    this.patches.push(patch);
    return patch;
  }

  replaceTask(planId: string, taskId: string, oldTask: unknown, newTask: unknown, reason: string): PlanPatch {
    const patch = this.makePatch(planId, 'REPLACE_TASK', taskId, oldTask, newTask, reason);
    this.patches.push(patch);
    return patch;
  }

  modifyTask(planId: string, taskId: string, modifications: unknown, reason: string): PlanPatch {
    const patch = this.makePatch(planId, 'MODIFY_TASK', taskId, undefined, modifications, reason);
    this.patches.push(patch);
    return patch;
  }

  changeDependency(planId: string, taskId: string, oldDep: unknown, newDep: unknown, reason: string): PlanPatch {
    const patch = this.makePatch(planId, 'CHANGE_DEPENDENCY', taskId, oldDep, newDep, reason);
    this.patches.push(patch);
    return patch;
  }

  // --- Patch Analysis ---

  getPatchesForPlan(planId: string): readonly PlanPatch[] {
    return this.patches.filter(p => p.planId === planId);
  }

  getAffectedTasks(planId: string): readonly string[] {
    return this.patches
      .filter(p => p.planId === planId)
      .map(p => p.targetTaskId);
  }

  canPatchPreserveCompleted(planId: string): boolean {
    const patches = this.getPatchesForPlan(planId);
    return patches.every(p => p.preservesCompleted);
  }

  // --- Minimal Replan ---

  createMinimalReplan(
    planId: string,
    failedTaskId: string,
    replacementTask: unknown,
    completedTaskIds: readonly string[],
  ): PlanPatch[] {
    const patches: PlanPatch[] = [];

    // Replace the failed task
    patches.push(this.replaceTask(planId, failedTaskId, undefined, replacementTask,
      `Task ${failedTaskId} failed — replacing with alternative`));

    return patches;
  }

  // --- Helpers ---

  private makePatch(
    planId: string,
    type: PlanPatchType,
    targetTaskId: string,
    oldTask: unknown,
    newTask: unknown,
    reason: string,
  ): PlanPatch {
    return {
      patchId: `patch_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      planId,
      type,
      targetTaskId,
      oldTask,
      newTask,
      reason,
      appliedAt: new Date().toISOString(),
      preservesCompleted: type !== 'REMOVE_TASK' || true,
    };
  }

  // --- History ---

  getAllPatches(): readonly PlanPatch[] {
    return this.patches;
  }

  getPatchCount(): number {
    return this.patches.length;
  }

  clear(): void {
    this.patches = [];
  }
}
