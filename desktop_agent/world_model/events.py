"""World Model Event Ingestion — consume meaningful events from existing systems.

Events flow:
  SOURCE → validate → dedup → contextualize → update world state → emit change
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(str, Enum):
    """Meaningful event types the World Model consumes."""
    ENTITY_CREATED = "entity.created"
    ENTITY_UPDATED = "entity.updated"
    ENTITY_DELETED = "entity.deleted"
    STATE_CHANGED = "state.changed"
    RELATIONSHIP_CREATED = "relationship.created"
    RELATIONSHIP_DELETED = "relationship.deleted"
    GOAL_STARTED = "goal.started"
    GOAL_COMPLETED = "goal.completed"
    GOAL_BLOCKED = "goal.blocked"
    GOAL_FAILED = "goal.failed"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_BLOCKED = "task.blocked"
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    FILE_CHANGED = "file.changed"
    BROWSER_OPENED = "browser.opened"
    BROWSER_TAB_CHANGED = "browser.tab_changed"
    APPLICATION_OPENED = "application.opened"
    APPLICATION_CLOSED = "application.closed"
    VISION_STATE_CHANGED = "vision.state_changed"
    VOICE_SESSION_STARTED = "voice.session_started"
    TRADING_ALERT = "trading.alert"
    WORKFLOW_COMPLETED = "workflow.completed"
    PREFERENCE_LEARNED = "preference.learned"
    SYSTEM_HEALTH_CHANGED = "system.health_changed"
    CONTEXT_CHANGED = "context.changed"
    USER_CORRECTION = "user.correction"
    # Extensible


@dataclass
class WorldEvent:
    """A validated, deduplicated world event."""
    id: str
    type: EventType
    entity_id: str
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    importance: float = 0.5
    dedup_key: str = ""

    def __post_init__(self):
        if not self.dedup_key:
            self.dedup_key = self._compute_dedup_key()

    def _compute_dedup_key(self) -> str:
        raw = f"{self.type.value}:{self.entity_id}:{self.timestamp:.0f}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp,
            "data": dict(self.data),
            "source": self.source,
            "importance": self.importance,
            "dedup_key": self.dedup_key,
        }


class EventIngestor:
    """Event ingestion pipeline with dedup, filtering, and importance scoring.

    Consumes events from existing systems (EventBus, Blackboard, observers).
    Emits world-change events for subscribers.
    """

    def __init__(self, max_events: int = 5000, dedup_window_seconds: float = 300) -> None:
        self._events: deque[WorldEvent] = deque(maxlen=max_events)
        self._seen_dedup_keys: Dict[str, float] = {}
        self._dedup_window = dedup_window_seconds
        self._subscribers: Dict[str, List[Callable]] = {}
        self._importance_threshold = 0.1
        self._event_count = 0
        self._filtered_count = 0

    def ingest(self, event: WorldEvent) -> bool:
        """Ingest a world event. Returns True if accepted (not filtered/deduped)."""
        self._event_count += 1

        # Importance filter
        if event.importance < self._importance_threshold:
            self._filtered_count += 1
            return False

        # Dedup check
        now = time.time()
        if event.dedup_key in self._seen_dedup_keys:
            age = now - self._seen_dedup_keys[event.dedup_key]
            if age < self._dedup_window:
                self._filtered_count += 1
                return False

        # Accept
        self._seen_dedup_keys[event.dedup_key] = now
        self._events.append(event)

        # Cleanup old dedup keys
        if len(self._seen_dedup_keys) > 10000:
            cutoff = now - self._dedup_window
            self._seen_dedup_keys = {
                k: v for k, v in self._seen_dedup_keys.items() if v > cutoff
            }

        # Notify subscribers
        self._notify(event)
        return True

    def subscribe(self, event_type: str, callback: Callable[[WorldEvent], None]) -> None:
        """Subscribe to world events."""
        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from world events."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb != callback
            ]

    def recent(self, limit: int = 50) -> List[WorldEvent]:
        """Get recent events."""
        return list(self._events)[-limit:]

    def by_entity(self, entity_id: str, limit: int = 50) -> List[WorldEvent]:
        """Get events for a specific entity."""
        return [e for e in self._events if e.entity_id == entity_id][-limit:]

    def by_type(self, event_type: EventType, limit: int = 50) -> List[WorldEvent]:
        """Get events of a specific type."""
        return [e for e in self._events if e.type == event_type][-limit:]

    def stats(self) -> Dict[str, Any]:
        """Event ingestion statistics."""
        return {
            "total_ingested": len(self._events),
            "total_received": self._event_count,
            "total_filtered": self._filtered_count,
            "dedup_keys_active": len(self._seen_dedup_keys),
            "subscriber_count": sum(len(subs) for subs in self._subscribers.values()),
        }

    def _notify(self, event: WorldEvent) -> None:
        """Notify subscribers of a new event."""
        for callback in self._subscribers.get(event.type.value, []):
            try:
                callback(event)
            except Exception:
                pass
        for callback in self._subscribers.get("*", []):
            try:
                callback(event)
            except Exception:
                pass

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
        self._seen_dedup_keys.clear()
