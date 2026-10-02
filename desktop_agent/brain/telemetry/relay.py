"""
MYRAA Brain - Telemetry Relay (Phase C).

Bridges the Python TelemetryCollector (ring buffer + derived metrics) to
Node/React by exposing a simple poll-based drain() / stream() API.

Design constraints
------------------
* Bounded: at most max_events events in memory at any time.
* Sanitizing: payloads are scanned for secret-like keys before storage.
* Thread-safe: all public methods acquire the relay lock.
* No external dependencies: stdlib only.
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..metrics import TelemetryCollector, telemetry


# ---------------------------------------------------------------------------
# Event-type constants (semantic, not exhaustive of TelemetryEvent fields).
# ---------------------------------------------------------------------------

REQUEST_STARTED = "request_started"
ROUTE_SELECTED = "route_selected"
MEMORY_RETRIEVED = "memory_retrieved"
PLAN_CREATED = "plan_created"
TOOL_STARTED = "tool_started"
TOOL_COMPLETED = "tool_completed"
VERIFICATION_STARTED = "verification_started"
VERIFICATION_COMPLETED = "verification_completed"
RECOVERY_STARTED = "recovery_started"
AUTONOMY_STATE_CHANGED = "autonomy_state_changed"
VISION_STATE_CHANGED = "vision_state_changed"
VOICE_STATE_CHANGED = "voice_state_changed"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"

ALL_EVENT_TYPES: tuple = (
    REQUEST_STARTED,
    ROUTE_SELECTED,
    MEMORY_RETRIEVED,
    PLAN_CREATED,
    TOOL_STARTED,
    TOOL_COMPLETED,
    VERIFICATION_STARTED,
    VERIFICATION_COMPLETED,
    RECOVERY_STARTED,
    AUTONOMY_STATE_CHANGED,
    VISION_STATE_CHANGED,
    VOICE_STATE_CHANGED,
    TASK_COMPLETED,
    TASK_FAILED,
)

# ---------------------------------------------------------------------------
# Payload sanitization - redact values whose key looks like a secret.
# ---------------------------------------------------------------------------

_SECRET_KEY_RE = re.compile(
    r"(api[_\-]?key|token|password|secret|auth|credential|bearer)",
    re.IGNORECASE,
)

# Patterns that look like API key/secret VALUES (not key names).
_SECRET_VALUE_RE = re.compile(
    r"(AIzaSy[A-Za-z0-9_-]{33}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|"
    r"xox[bpsa]-[A-Za-z0-9-]+|AKIA[A-Z0-9]{16}|"
    r"[A-Za-z0-9]{20,})",  # generic long token strings (20+ chars)
)


def _sanitize_value(value: Any) -> Any:
    """Recursively walk value and mask anything that looks like a secret."""
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if _SECRET_KEY_RE.search(k) else _sanitize_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, str) and _SECRET_VALUE_RE.search(value):
        return "***REDACTED***"
    return value


# ---------------------------------------------------------------------------
# Relay event - lightweight wrapper stored in the buffer.
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RelayEvent:
    """One buffered telemetry event ready for Node consumption."""

    event_type: str
    payload: Dict[str, Any]
    request_id: str = ""
    task_id: str = ""
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# TelemetryRelay
# ---------------------------------------------------------------------------

class TelemetryRelay:
    """
    Thin adapter that sits in front of the existing TelemetryCollector and
    adds a poll-friendly drain() / stream() interface for Node/React.

    Usage::

        relay = TelemetryRelay()
        relay.emit(TOOL_STARTED, {"tool": "takeScreenshot"}, request_id="r-1")
        events = relay.drain()          # Node polls this endpoint
        relay.stream(count=10)          # last 10 events (non-destructive)
    """

    def __init__(
        self,
        *,
        max_events: int = 500,
        collector: Optional[TelemetryCollector] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._buffer: deque = deque(maxlen=max_events)
        self._collector: TelemetryCollector = collector or telemetry
        self._counts: Dict[str, int] = defaultdict(int)
        self._started_at: float = time.time()
        self._listeners: List[Callable] = []

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        request_id: str = "",
        task_id: str = "",
    ) -> RelayEvent:
        """Record a telemetry event into the bounded buffer.

        The same event is also forwarded to the TelemetryCollector so
        derived metrics (counters, histograms) stay consistent.
        """
        sanitized = _sanitize_value(dict(payload))
        event = RelayEvent(
            event_type=event_type,
            payload=sanitized,
            request_id=request_id,
            task_id=task_id,
        )

        with self._lock:
            self._buffer.append(event)
            self._counts[event_type] += 1

        # Forward to the canonical collector for counters / histograms.
        try:
            collector_copy = dict(sanitized)
            self._collector.record(
                component=collector_copy.pop("component", "desktop_agent"),
                route=collector_copy.pop("route", ""),
                intent=collector_copy.pop("intent", ""),
                tool=collector_copy.pop("tool", ""),
                status=collector_copy.pop("status", "ok"),
                latency_ms=collector_copy.pop("latency_ms", 0.0),
                request_id=request_id,
                task_id=task_id,
            )
        except Exception:
            pass

        # Notify synchronous listeners.
        for cb in list(self._listeners):
            try:
                cb(event_type, sanitized)
            except Exception:
                pass

        return event

    def drain(self) -> List[Dict[str, Any]]:
        """Return AND clear every buffered event (for Node polling).

        Each event is returned as a plain dict safe for JSON serialization.
        """
        with self._lock:
            events = list(self._buffer)
            self._buffer.clear()

        return [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "request_id": e.request_id,
                "task_id": e.task_id,
                "timestamp": e.timestamp,
            }
            for e in events
        ]

    def stream(self, count: int = 50) -> List[Dict[str, Any]]:
        """Return the last *count* events without clearing the buffer."""
        with self._lock:
            events = list(self._buffer)[-count:]

        return [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "request_id": e.request_id,
                "task_id": e.task_id,
                "timestamp": e.timestamp,
            }
            for e in events
        ]

    def status(self) -> Dict[str, Any]:
        """Health-check payload for the relay."""
        with self._lock:
            buffered = len(self._buffer)
            counts = dict(self._counts)

        return {
            "ok": True,
            "buffered": buffered,
            "max_events": self._buffer.maxlen,
            "event_counts": counts,
            "uptime_seconds": round(time.time() - self._started_at, 2),
        }

    # ------------------------------------------------------------------
    # Listener API
    # ------------------------------------------------------------------

    def on_event(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a synchronous callback invoked on every emit()."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Drop all buffered events without processing."""
        with self._lock:
            self._buffer.clear()

    def reset(self) -> None:
        """Full reset: buffer, counts, listeners, uptime."""
        with self._lock:
            self._buffer.clear()
            self._counts.clear()
            self._listeners.clear()
            self._started_at = time.time()


# ---------------------------------------------------------------------------
# Global singleton for cross-module use.
# ---------------------------------------------------------------------------

telemetry_relay = TelemetryRelay()
