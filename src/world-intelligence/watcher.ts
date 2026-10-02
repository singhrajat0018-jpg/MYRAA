// ============================================================================
// MYRAA World Watcher Engine
// ============================================================================

import {
  WorldWatcher, WatcherPolicy, WatcherAlert, WatcherStatus,
  WorldEvent, ImportanceLevel,
  EntityType, WorldEventType,
  generateWorldId, nowISO,
} from './contracts';
import { WorldStateEngine } from './world_state_engine';

export class WorldWatcherEngine {
  private watchers: Map<string, WorldWatcher> = new Map();
  private alerts: Map<string, WatcherAlert> = new Map();
  private stateEngine: WorldStateEngine;
  private alertCooldowns: Map<string, number> = new Map(); // watcherId -> last alert timestamp

  constructor(stateEngine: WorldStateEngine) {
    this.stateEngine = stateEngine;
  }

  watch(options: {
    entityType?: EntityType;
    entityIds?: string[];
    topics?: string[];
    eventTypes?: WorldEventType[];
    policy: WatcherPolicy;
  }): WorldWatcher {
    const id = generateWorldId();
    const now = nowISO();
    const watcher: WorldWatcher = {
      id,
      entityType: options.entityType,
      entityIds: options.entityIds || [],
      topics: options.topics || [],
      eventTypes: options.eventTypes || [],
      policy: options.policy,
      status: 'ACTIVE',
      createdAt: now,
      triggerCount: 0,
      metadata: {},
    };
    this.watchers.set(id, watcher);
    return watcher;
  }

  pause(watcherId: string): boolean {
    const watcher = this.watchers.get(watcherId);
    if (!watcher) return false;
    this.watchers.set(watcherId, { ...watcher, status: 'PAUSED' });
    return true;
  }

  resume(watcherId: string): boolean {
    const watcher = this.watchers.get(watcherId);
    if (!watcher) return false;
    this.watchers.set(watcherId, { ...watcher, status: 'ACTIVE' });
    return true;
  }

  stop(watcherId: string): boolean {
    const watcher = this.watchers.get(watcherId);
    if (!watcher) return false;
    this.watchers.set(watcherId, { ...watcher, status: 'STOPPED' });
    return true;
  }

  unwatch(watcherId: string): boolean {
    return this.watchers.delete(watcherId);
  }

  getWatcher(id: string): WorldWatcher | undefined {
    return this.watchers.get(id);
  }

  getActiveWatchers(): WorldWatcher[] {
    return Array.from(this.watchers.values()).filter(w => w.status === 'ACTIVE');
  }

  getAllWatchers(): WorldWatcher[] {
    return Array.from(this.watchers.values());
  }

  evaluate(event: WorldEvent): WatcherAlert[] {
    const newAlerts: WatcherAlert[] = [];
    for (const watcher of this.watchers.values()) {
      if (watcher.status !== 'ACTIVE') continue;
      if (!this.matchesWatcher(event, watcher)) continue;
      // Check cooldown
      const lastAlert = this.alertCooldowns.get(watcher.id) || 0;
      const now = Date.now();
      if (now - lastAlert < watcher.policy.cooldownMs) continue;
      // Check max alerts per hour
      const recentAlerts = this.getRecentAlerts(watcher.id, 60 * 60 * 1000);
      if (recentAlerts.length >= watcher.policy.maxAlertsPerHour) continue;
      // Check expiration
      if (watcher.policy.expirationMs) {
        const age = now - new Date(watcher.createdAt).getTime();
        if (age > watcher.policy.expirationMs) {
          this.watchers.set(watcher.id, { ...watcher, status: 'EXPIRED' });
          continue;
        }
      }
      // Create alert
      const alert: WatcherAlert = {
        id: generateWorldId(),
        watcherId: watcher.id,
        eventIds: [event.id],
        entityIds: event.entityIds,
        title: event.title,
        summary: event.summary,
        importance: this.mergeImportance(event.importance, watcher.policy.importance),
        createdAt: nowISO(),
        acknowledged: false,
      };
      this.alerts.set(alert.id, alert);
      this.alertCooldowns.set(watcher.id, now);
      this.watchers.set(watcher.id, {
        ...watcher,
        lastTriggeredAt: nowISO(),
        triggerCount: watcher.triggerCount + 1,
      });
      newAlerts.push(alert);
    }
    return newAlerts;
  }

  evaluateBatch(events: WorldEvent[]): WatcherAlert[] {
    const allAlerts: WatcherAlert[] = [];
    for (const event of events) {
      allAlerts.push(...this.evaluate(event));
    }
    return allAlerts;
  }

  getAlerts(watcherId?: string, unacknowledgedOnly = false): WatcherAlert[] {
    let alerts = Array.from(this.alerts.values());
    if (watcherId) alerts = alerts.filter(a => a.watcherId === watcherId);
    if (unacknowledgedOnly) alerts = alerts.filter(a => !a.acknowledged);
    return alerts.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  acknowledgeAlert(alertId: string): boolean {
    const alert = this.alerts.get(alertId);
    if (!alert) return false;
    this.alerts.set(alertId, { ...alert, acknowledged: true });
    return true;
  }

  private matchesWatcher(event: WorldEvent, watcher: WorldWatcher): boolean {
    // Check event type
    if (watcher.eventTypes && watcher.eventTypes.length > 0) {
      if (!watcher.eventTypes.includes(event.type)) return false;
    }
    // Check entity match
    if (watcher.entityIds && watcher.entityIds.length > 0) {
      const hasMatch = event.entityIds.some(eid => watcher.entityIds!.includes(eid));
      if (!hasMatch) return false;
    }
    // Check topic match
    if (watcher.topics && watcher.topics.length > 0) {
      const hasMatch = event.topicIds.some(t => watcher.topics!.map(wt => wt.toLowerCase()).includes(t.toLowerCase()));
      if (!hasMatch) return false;
    }
    return true;
  }

  private getRecentAlerts(watcherId: string, withinMs: number): WatcherAlert[] {
    const cutoff = new Date(Date.now() - withinMs).toISOString();
    return Array.from(this.alerts.values()).filter(
      a => a.watcherId === watcherId && a.createdAt >= cutoff
    );
  }

  private mergeImportance(eventImp: ImportanceLevel, watcherImp: ImportanceLevel): ImportanceLevel {
    const order: ImportanceLevel[] = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
    const eIdx = order.indexOf(eventImp);
    const wIdx = order.indexOf(watcherImp);
    return order[Math.max(eIdx, wIdx)];
  }

  getStats() {
    const watchers = Array.from(this.watchers.values());
    return {
      totalWatchers: watchers.length,
      activeWatchers: watchers.filter(w => w.status === 'ACTIVE').length,
      pausedWatchers: watchers.filter(w => w.status === 'PAUSED').length,
      stoppedWatchers: watchers.filter(w => w.status === 'STOPPED').length,
      expiredWatchers: watchers.filter(w => w.status === 'EXPIRED').length,
      totalAlerts: this.alerts.size,
      unacknowledgedAlerts: Array.from(this.alerts.values()).filter(a => !a.acknowledged).length,
      totalTriggers: watchers.reduce((sum, w) => sum + w.triggerCount, 0),
    };
  }
}
