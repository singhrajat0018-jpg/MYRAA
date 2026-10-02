from __future__ import annotations

"""Self-Healing Telemetry / UI Exposure for MYRAA.

Provides event recording, health snapshots, incident tracking, healing
statistics, and JSON export for the self-healing subsystem.  Events are
stored in a bounded ring buffer (oldest evicted when full) and all access
is thread-safe.
"""

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_EVENTS = 500

_VALID_EVENT_TYPES = frozenset({
    "healing_started",
    "healing_completed",
    "healing_failed",
    "diagnosis",
    "root_cause",
    "escalation",
    "optimization",
    "reflection",
    "engineering",
    "rollback",
})

_VALID_SEVERITIES = frozenset({"info", "warning", "error", "critical"})


@dataclass
class HealingEvent:
    """A single telemetry event emitted by the self-healing subsystem."""

    event_id: str
    event_type: str
    component: str
    details: dict[str, Any]
    timestamp: float
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "component": self.component,
            "details": dict(self.details),
            "timestamp": self.timestamp,
            "severity": self.severity,
        }

    def __repr__(self) -> str:
        return (
            f"HealingEvent(type={self.event_type!r}, "
            f"component={self.component!r}, severity={self.severity!r})"
        )


@dataclass
class SystemHealthSnapshot:
    """Point-in-time summary of overall system health."""

    timestamp: float
    overall_status: str
    subsystems: dict[str, dict[str, Any]]
    active_incidents: int
    healing_in_progress: int
    last_heal_time: Optional[float]
    total_heals_today: int
    success_rate_today: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "subsystems": dict(self.subsystems),
            "active_incidents": self.active_incidents,
            "healing_in_progress": self.healing_in_progress,
            "last_heal_time": self.last_heal_time,
            "total_heals_today": self.total_heals_today,
            "success_rate_today": self.success_rate_today,
        }

    def __repr__(self) -> str:
        return (
            f"SystemHealthSnapshot(status={self.overall_status!r}, "
            f"incidents={self.active_incidents}, "
            f"heals_today={self.total_heals_today})"
        )


class SelfHealingTelemetry:
    """Thread-safe singleton telemetry store for self-healing events.

    Events are stored in a bounded ring buffer (``MAX_EVENTS``).  Oldest
    events are evicted when the buffer is full.

    Example::

        telemetry = SelfHealingTelemetry()
        telemetry.record_event("healing_completed", "voice", {"ok": True})
        snap = telemetry.get_health_snapshot(diagnostics_engine)
    """

    _instance: Optional[SelfHealingTelemetry] = None
    _lock_class = threading.Lock()

    def __new__(cls) -> SelfHealingTelemetry:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._lock = threading.Lock()
        self._events: deque[HealingEvent] = deque(maxlen=MAX_EVENTS)
        self._healing_in_progress: int = 0
        self._last_heal_time: Optional[float] = None
        logger.info("SelfHealingTelemetry initialised (max_events=%d)", MAX_EVENTS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        component: str,
        details: dict[str, Any],
        severity: str = "info",
    ) -> HealingEvent:
        """Record a telemetry event and return it.

        Raises ``ValueError`` if *event_type* or *severity* are invalid.
        """
        if event_type not in _VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type {event_type!r}; expected one of "
                f"{sorted(_VALID_EVENT_TYPES)}"
            )
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity {severity!r}; expected one of "
                f"{sorted(_VALID_SEVERITIES)}"
            )

        event = HealingEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            component=component,
            details=dict(details),
            timestamp=time.time(),
            severity=severity,
        )

        with self._lock:
            self._events.append(event)

            # Track in-progress heals
            if event_type == "healing_started":
                self._healing_in_progress += 1
            elif event_type in ("healing_completed", "healing_failed"):
                self._healing_in_progress = max(0, self._healing_in_progress - 1)

            # Track last heal time
            if event_type in ("healing_completed", "healing_failed"):
                self._last_heal_time = event.timestamp

        logger.debug(
            "Recorded event: type=%s component=%s severity=%s",
            event_type,
            component,
            severity,
        )
        return event

    def get_events(
        self,
        limit: int = 50,
        event_type: Optional[str] = None,
    ) -> list[HealingEvent]:
        """Return up to *limit* most-recent events, optionally filtered by type."""
        with self._lock:
            events = list(self._events)

        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def get_health_snapshot(
        self,
        diagnostics_engine: Any,
    ) -> SystemHealthSnapshot:
        """Build a ``SystemHealthSnapshot`` from the given DiagnosticsEngine.

        The *diagnostics_engine* must expose a ``health_summary()`` method
        returning a dict with at least ``overall_status`` and ``subsystems``.
        """
        now = time.time()
        today_start = self._today_start(now)

        try:
            summary = diagnostics_engine.health_summary()
        except Exception:
            logger.exception("Failed to obtain health summary from diagnostics engine")
            summary = {"overall_status": "unknown", "subsystems": {}}

        # Count today's heal events
        heals_today = 0
        successes_today = 0
        with self._lock:
            for ev in self._events:
                if ev.timestamp < today_start:
                    continue
                if ev.event_type in ("healing_completed", "healing_failed"):
                    heals_today += 1
                    if ev.event_type == "healing_completed":
                        successes_today += 1

        success_rate = successes_today / heals_today if heals_today > 0 else 0.0

        # Count active incidents (error/critical unresolved)
        incidents = 0
        with self._lock:
            for ev in self._events:
                if ev.severity in ("error", "critical"):
                    # An event is considered unresolved unless followed by a
                    # healing_completed for the same component
                    resolved = False
                    for later in self._events:
                        if later.timestamp <= ev.timestamp:
                            continue
                        if (
                            later.event_type == "healing_completed"
                            and later.component == ev.component
                        ):
                            resolved = True
                            break
                    if not resolved:
                        incidents += 1

        return SystemHealthSnapshot(
            timestamp=now,
            overall_status=str(summary.get("overall_status", "unknown")),
            subsystems=dict(summary.get("subsystems", {})),
            active_incidents=incidents,
            healing_in_progress=self._healing_in_progress,
            last_heal_time=self._last_heal_time,
            total_heals_today=heals_today,
            success_rate_today=round(success_rate, 4),
        )

    def get_incidents(self) -> list[HealingEvent]:
        """Return unresolved error/critical events (heuristic: no subsequent
        healing_completed for the same component)."""
        with self._lock:
            events = list(self._events)

        incidents: list[HealingEvent] = []
        for ev in events:
            if ev.severity not in ("error", "critical"):
                continue
            resolved = False
            for later in events:
                if later.timestamp <= ev.timestamp:
                    continue
                if (
                    later.event_type == "healing_completed"
                    and later.component == ev.component
                ):
                    resolved = True
                    break
            if not resolved:
                incidents.append(ev)
        return incidents

    def get_healing_stats(self) -> dict[str, Any]:
        """Aggregate statistics: counts by type, success rate, avg healing time."""
        with self._lock:
            events = list(self._events)

        by_type: dict[str, int] = {}
        for ev in events:
            by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1

        # Compute average healing time from started/completed pairs
        started_times: dict[str, float] = {}
        healing_durations: list[float] = []
        for ev in sorted(events, key=lambda e: e.timestamp):
            if ev.event_type == "healing_started":
                started_times[ev.component] = ev.timestamp
            elif ev.event_type == "healing_completed":
                start = started_times.pop(ev.component, None)
                if start is not None:
                    healing_durations.append(ev.timestamp - start)

        total_heals = by_type.get("healing_completed", 0) + by_type.get("healing_failed", 0)
        successes = by_type.get("healing_completed", 0)
        success_rate = successes / total_heals if total_heals > 0 else 0.0
        avg_duration = (
            sum(healing_durations) / len(healing_durations)
            if healing_durations
            else 0.0
        )

        return {
            "total_events": len(events),
            "by_type": by_type,
            "success_rate": round(success_rate, 4),
            "avg_healing_time_s": round(avg_duration, 3),
            "healing_durations_count": len(healing_durations),
        }

    def get_telemetry_summary(self) -> dict[str, Any]:
        """Full summary: counts by type, by component, by severity, time range."""
        with self._lock:
            events = list(self._events)

        by_type: dict[str, int] = {}
        by_component: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for ev in events:
            by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
            by_component[ev.component] = by_component.get(ev.component, 0) + 1
            by_severity[ev.severity] = by_severity.get(ev.severity, 0) + 1

        timestamps = [ev.timestamp for ev in events] if events else [0.0]

        return {
            "total_events": len(events),
            "by_type": by_type,
            "by_component": by_component,
            "by_severity": by_severity,
            "earliest_event": min(timestamps),
            "latest_event": max(timestamps),
            "max_events": MAX_EVENTS,
            "buffer_usage": len(events) / MAX_EVENTS if MAX_EVENTS > 0 else 0.0,
        }

    def export_events(self, path: str, limit: int = 100) -> int:
        """Write up to *limit* most-recent events to a JSON file.

        Returns the number of events written.
        """
        with self._lock:
            events = list(self._events)

        events = events[-limit:]
        payload = [ev.to_dict() for ev in events]

        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, default=str)
            logger.info("Exported %d events to %s", len(payload), path)
            return len(payload)
        except OSError:
            logger.exception("Failed to export events to %s", path)
            return 0

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance._events.clear()
                cls._instance._healing_in_progress = 0
                cls._instance._last_heal_time = None
            cls._instance = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _today_start(now: float) -> float:
        """Return the epoch timestamp for the start of today (midnight UTC)."""
        import datetime

        dt = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
        midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.timestamp()
