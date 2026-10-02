// ============================================================================
// MYRAA World Model Vision Bridge — Ingests Vision Events into World Model
// ============================================================================

import type { ObservedScene, VisualEvent } from './contracts';

export interface WorldModelBridgeOptions {
  agentUrl: string;
}

export class WorldModelVisionBridge {
  private agentUrl: string;
  private lastSyncedTimestamp = 0;

  constructor(options: WorldModelBridgeOptions) {
    this.agentUrl = options.agentUrl || 'http://127.0.0.1:8765';
  }

  /**
   * Forward significant visual events to Python World Model.
   * Emits `vision.state_changed` world events and updates the active application entity.
   */
  public async syncToWorldModel(scene: ObservedScene, events: VisualEvent[]): Promise<boolean> {
    // Only forward if there are significant events or periodically
    const hasSignificant = events.some(e => e.significance >= 0.5);
    const now = Date.now();
    if (!hasSignificant && (now - this.lastSyncedTimestamp < 30000)) {
      return false;
    }

    this.lastSyncedTimestamp = now;

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);

      const payload = {
        event_type: 'vision.state_changed',
        entity_id: `app-${scene.activeWindow.application.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
        timestamp: scene.timestamp / 1000,
        data: {
          application: scene.activeWindow.application,
          window_title: scene.activeWindow.title,
          events: events.map(e => ({ type: e.type, description: e.description, significance: e.significance })),
          has_error: scene.hasError,
          significance: scene.significance,
        },
        source: 'vision_pipeline',
        importance: scene.significance,
      };

      // Best-effort post to Desktop Agent's event ingestion
      const resp = await fetch(`${this.agentUrl}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: 'logEvent',
          args: payload,
        }),
        signal: controller.signal,
      }).catch(() => null);

      clearTimeout(timeout);
      return resp ? resp.ok : false;
    } catch {
      // Degraded/offline safety: never throw or block
      return false;
    }
  }
}
