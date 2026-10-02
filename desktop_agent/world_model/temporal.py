"""World Model Temporal State — time-aware entity state tracking.

Tracks: created, updated, started, completed, failed, paused, resumed, expired, invalidated.
Supports: PAST, PRESENT, FUTURE queries.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TemporalPhase(str, Enum):
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"


@dataclass
class TimelineEntry:
    """A single point-in-time state record for an entity."""
    entity_id: str
    state: str
    timestamp: float
    phase: TemporalPhase = TemporalPhase.PRESENT
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "timestamp": self.timestamp,
            "phase": self.phase.value,
            "metadata": dict(self.metadata),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineEntry:
        return cls(
            entity_id=data["entity_id"],
            state=data["state"],
            timestamp=data["timestamp"],
            phase=TemporalPhase(data.get("phase", "present")),
            metadata=data.get("metadata", {}),
            source=data.get("source", "system"),
        )


class TemporalState:
    """Tracks time-aware state history for all entities.

    Supports:
    - record state change
    - query by entity
    - query by time range
    - diff between time points
    - stale detection
    """

    def __init__(self, max_entries_per_entity: int = 500) -> None:
        self._history: Dict[str, deque[TimelineEntry]] = defaultdict(
            lambda: deque(maxlen=max_entries_per_entity)
        )
        self._current: Dict[str, TimelineEntry] = {}

    def record(
        self,
        entity_id: str,
        state: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "system",
        timestamp: Optional[float] = None,
    ) -> TimelineEntry:
        """Record a state change for an entity."""
        ts = timestamp or time.time()
        entry = TimelineEntry(
            entity_id=entity_id,
            state=state,
            timestamp=ts,
            phase=self._classify_phase(ts),
            metadata=metadata or {},
            source=source,
        )
        self._history[entity_id].append(entry)
        self._current[entity_id] = entry
        return entry

    def current_state(self, entity_id: str) -> Optional[TimelineEntry]:
        """Get the most recent state for an entity."""
        return self._current.get(entity_id)

    def history(
        self,
        entity_id: str,
        limit: int = 50,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[TimelineEntry]:
        """Get state history for an entity."""
        entries = list(self._history.get(entity_id, []))
        if since is not None:
            entries = [e for e in entries if e.timestamp >= since]
        if until is not None:
            entries = [e for e in entries if e.timestamp <= until]
        return entries[-limit:]

    def diff(
        self,
        entity_id: str,
        time_a: float,
        time_b: float,
    ) -> Optional[Dict[str, Any]]:
        """Compare state of entity at two time points."""
        history = list(self._history.get(entity_id, []))
        state_a = None
        state_b = None
        for entry in history:
            if entry.timestamp <= time_a:
                state_a = entry.state
            if entry.timestamp <= time_b:
                state_b = entry.state
        if state_a is None and state_b is None:
            return None
        return {
            "entity_id": entity_id,
            "state_at_a": state_a,
            "state_at_b": state_b,
            "changed": state_a != state_b,
            "time_a": time_a,
            "time_b": time_b,
        }

    def what_changed_since(self, since: float) -> List[Dict[str, Any]]:
        """Find all entities whose state changed since a given time."""
        changes: List[Dict[str, Any]] = []
        for entity_id, entries in self._history.items():
            for entry in entries:
                if entry.timestamp >= since:
                    changes.append({
                        "entity_id": entity_id,
                        "state": entry.state,
                        "timestamp": entry.timestamp,
                        "source": entry.source,
                    })
                    break  # only most recent change
        return sorted(changes, key=lambda x: x["timestamp"], reverse=True)

    def stale_entities(self, max_age_seconds: float = 3600) -> List[Dict[str, Any]]:
        """Find entities that haven't been updated within max_age."""
        now = time.time()
        stale: List[Dict[str, Any]] = []
        for entity_id, entry in self._current.items():
            age = now - entry.timestamp
            if age > max_age_seconds:
                stale.append({
                    "entity_id": entity_id,
                    "last_state": entry.state,
                    "age_seconds": age,
                    "last_update": entry.timestamp,
                })
        return stale

    def all_current_states(self) -> Dict[str, str]:
        """Get current state of all tracked entities."""
        return {eid: entry.state for eid, entry in self._current.items()}

    def count(self) -> int:
        """Total number of tracked entities."""
        return len(self._current)

    def _classify_phase(self, timestamp: float) -> TemporalPhase:
        """Classify a timestamp as PAST, PRESENT, or FUTURE."""
        now = time.time()
        diff = timestamp - now
        if diff < -300:  # more than 5 minutes ago
            return TemporalPhase.PAST
        elif diff > 300:  # more than 5 minutes from now
            return TemporalPhase.FUTURE
        return TemporalPhase.PRESENT

    def to_dict(self) -> Dict[str, Any]:
        """Serialize temporal state."""
        return {
            "current": {
                eid: entry.to_dict()
                for eid, entry in self._current.items()
            },
            "history_counts": {
                eid: len(entries)
                for eid, entries in self._history.items()
            },
        }

    def clear(self) -> None:
        """Clear all temporal state."""
        self._history.clear()
        self._current.clear()
