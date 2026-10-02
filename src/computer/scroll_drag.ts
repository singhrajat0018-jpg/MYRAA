// ============================================================================
// MYRAA Scroll & Drag Engine — Scroll and drag automation
// ============================================================================

import type { Vec2, BoundingBox, ComputerAction } from './contracts';
import { toBoundingRect } from './contracts';
import { DPIManager } from './dpi';

// ============================================================================
// Scroll & Drag Engine
// ============================================================================

export class ScrollDragEngine {
  private dpiManager: DPIManager;
  private scrollPositions: Map<number, Vec2> = new Map(); // windowId -> last scroll pos

  constructor(dpiManager: DPIManager) {
    this.dpiManager = dpiManager;
  }

  // --- Scroll ---

  async scroll(action: ComputerAction): Promise<{ success: boolean; error?: string }> {
    const amount = action.scrollAmount ?? 3;
    const direction = action.scrollDirection ?? 'DOWN';
    const target = action.coordinates ?? (action.target ? this.targetCenter(action.target.bounds) : null);

    if (!target) return { success: false, error: 'No scroll target' };

    // Store scroll position for this window
    if (action.windowId !== undefined) {
      this.scrollPositions.set(action.windowId, target);
    }

    // Validate scroll amount
    if (Math.abs(amount) > 100) {
      return { success: false, error: `Scroll amount ${amount} exceeds max 100` };
    }

    return { success: true };
  }

  // --- Drag ---

  async drag(action: ComputerAction): Promise<{ success: boolean; destination?: Vec2; error?: string }> {
    const start = action.coordinates ?? (action.target ? this.targetCenter(action.target.bounds) : null);
    const end = action.dragDestination;

    if (!start) return { success: false, error: 'No drag start' };
    if (!end) return { success: false, error: 'No drag destination' };

    // Validate drag distance (at least 5px to be meaningful)
    const dist = Math.hypot(end.x - start.x, end.y - start.y);
    if (dist < 5) {
      return { success: false, error: `Drag distance ${dist.toFixed(1)}px too short (min 5px)` };
    }

    // Validate drag not too far (>10,000px likely wrong)
    if (dist > 10_000) {
      return { success: false, error: `Drag distance ${dist.toFixed(1)}px exceeds max 10,000px` };
    }

    return { success: true, destination: end };
  }

  // --- Scroll into View ---

  async scrollIntoView(
    targetBounds: BoundingBox,
    windowBounds: BoundingBox,
    scrollDirection: 'UP' | 'DOWN',
  ): Promise<{ success: boolean; scrollAmount: number }> {
    const targetRect = toBoundingRect(targetBounds);
    const windowRect = toBoundingRect(windowBounds);

    // Check if target is already visible
    if (targetRect.top >= windowRect.top && targetRect.bottom <= windowRect.bottom) {
      return { success: true, scrollAmount: 0 };
    }

    // Calculate scroll needed
    let amount: number;
    if (scrollDirection === 'DOWN') {
      amount = Math.ceil((targetRect.bottom - windowRect.bottom) / 40); // ~line height
    } else {
      amount = Math.ceil((windowRect.top - targetRect.top) / 40);
    }

    return { success: true, scrollAmount: Math.min(amount, 50) };
  }

  // --- Helpers ---

  private targetCenter(bounds: BoundingBox): Vec2 {
    const r = toBoundingRect(bounds);
    return { x: r.centerX, y: r.centerY };
  }

  getLastScrollPosition(windowId: number): Vec2 | undefined {
    return this.scrollPositions.get(windowId);
  }
}
