/**
 * MYRAA Node Telemetry Relay — Phase C.
 *
 * Polls the Python desktop agent's /telemetry/drain endpoint on a configurable
 * interval and broadcasts events to connected React clients over WebSocket.
 *
 * Design constraints:
 * - Bounded: maxEvents in the local ring buffer.
 * - Secret redaction: API keys, tokens, passwords are stripped before broadcast.
 * - Reconnect-safe: if Python agent is down, skips silently and retries next cycle.
 * - No duplicate authority: the Python TelemetryRelay is the single source of truth.
 * - Correlation IDs preserved end-to-end.
 */

import WebSocket from "ws";
import { DESKTOP_AGENT_URL } from "../desktop/desktop_agent";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 2000;       // how often to poll Python /telemetry/drain
const REQUEST_TIMEOUT_MS = 3000;     // HTTP timeout for drain call
const MAX_BUFFERED_EVENTS = 500;     // local ring buffer cap
const MAX_BROADCAST_BATCH = 100;     // max events per WS broadcast cycle

// Secret-redaction regex — matches key names that look sensitive.
const SECRET_KEY_RE =
  /api[_\-]?key|token|password|secret|auth|credential|bearer/i;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TelemetryEvent {
  event_type: string;
  payload: Record<string, unknown>;
  request_id: string;
  task_id: string;
  timestamp: number;
}

interface DrainResponse {
  events: TelemetryEvent[];
  count: number;
}

// ---------------------------------------------------------------------------
// TelemetryRelay (Node-side)
// ---------------------------------------------------------------------------

export class NodeTelemetryRelay {
  private _buffer: TelemetryEvent[] = [];
  private _clients: Set<WebSocket> = new Set();
  private _pollTimer: ReturnType<typeof setInterval> | null = null;
  private _running = false;
  private _stats = {
    totalDrained: 0,
    totalBroadcast: 0,
    pollErrors: 0,
    redactedKeys: 0,
    startedAt: Date.now(),
  };

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /** Start polling Python /telemetry/drain and broadcasting to WS clients. */
  start(): void {
    if (this._running) return;
    this._running = true;
    this._stats.startedAt = Date.now();
    this._pollTimer = setInterval(() => this._pollAndBroadcast(), POLL_INTERVAL_MS);
  }

  /** Stop polling and close all client connections. */
  stop(): void {
    this._running = false;
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    for (const ws of this._clients) {
      try { ws.close(); } catch { /* best-effort */ }
    }
    this._clients.clear();
  }

  /** Register a WebSocket client to receive telemetry broadcasts. */
  addClient(ws: WebSocket): void {
    this._clients.add(ws);
    ws.on("close", () => this._clients.delete(ws));
    ws.on("error", () => this._clients.delete(ws));
  }

  /** Number of currently connected telemetry WS clients. */
  get clientCount(): number {
    return this._clients.size;
  }

  /** Relay health/status for /health endpoints. */
  status(): Record<string, unknown> {
    return {
      ok: true,
      running: this._running,
      clients: this._clients.size,
      buffered: this._buffer.length,
      maxBuffered: MAX_BUFFERED_EVENTS,
      stats: { ...this._stats },
      uptimeSeconds: Math.round((Date.now() - this._stats.startedAt) / 1000),
    };
  }

  // ------------------------------------------------------------------
  // Internal — poll, sanitize, broadcast
  // ------------------------------------------------------------------

  private async _pollAndBroadcast(): Promise<void> {
    if (!this._running) return;

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      const resp = await fetch(`${DESKTOP_AGENT_URL}/telemetry/drain`, {
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!resp.ok) return;

      const data: DrainResponse = await resp.json();
      if (!data.events || data.events.length === 0) return;

      // Sanitize and buffer
      const sanitized = data.events
        .slice(0, MAX_BROADCAST_BATCH)
        .map((e) => this._sanitize(e));

      // Append to local ring buffer
      for (const event of sanitized) {
        this._buffer.push(event);
        if (this._buffer.length > MAX_BUFFERED_EVENTS) {
          this._buffer.shift();
        }
      }

      this._stats.totalDrained += data.events.length;

      // Broadcast to all connected React clients
      this._broadcast(sanitized);
    } catch {
      // Python agent may be offline — skip silently, retry next cycle.
      this._stats.pollErrors++;
    }
  }

  private _broadcast(events: TelemetryEvent[]): void {
    if (this._clients.size === 0) return;

    const message = JSON.stringify({
      type: "telemetry",
      events,
      count: events.length,
      timestamp: Date.now(),
    });

    for (const ws of this._clients) {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(message);
          this._stats.totalBroadcast += events.length;
        } catch {
          this._clients.delete(ws);
        }
      } else {
        this._clients.delete(ws);
      }
    }
  }

  /** Recursively redact secret-like keys from event payloads. */
  private _sanitize(event: TelemetryEvent): TelemetryEvent {
    return {
      ...event,
      payload: this._sanitizeValue(event.payload) as Record<string, unknown>,
    };
  }

  private _sanitizeValue(value: unknown): unknown {
    if (value === null || value === undefined) return value;

    if (typeof value === "object" && !Array.isArray(value)) {
      const obj = value as Record<string, unknown>;
      const result: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(obj)) {
        if (SECRET_KEY_RE.test(k)) {
          result[k] = "***REDACTED***";
          this._stats.redactedKeys++;
        } else {
          result[k] = this._sanitizeValue(v);
        }
      }
      return result;
    }

    if (Array.isArray(value)) {
      return value.map((v) => this._sanitizeValue(v));
    }

    return value;
  }
}

// ---------------------------------------------------------------------------
// Global singleton
// ---------------------------------------------------------------------------

export const nodeTelemetryRelay = new NodeTelemetryRelay();
