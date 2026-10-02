"""World Model — canonical structured world state layer.

Maintains ENTITIES + RELATIONSHIPS + STATE + EVENTS + TIME + CONTEXT.

Integrates with existing authorities:
  Memory 2.0, SuperBrain, Autonomy, TaskRouter, NeuralEngine,
  ContinuousVision, UniversalControl, Trading

DO NOT create second memory, brain, planner, scheduler, autonomy, or vision.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .entity import Entity, EntityType, EntityState, EntitySource, EntityScope
from .relationship import Relationship, RelationshipGraph, RelationshipType
from .temporal import TemporalState, TimelineEntry
from .events import WorldEvent, EventType, EventIngestor
from .query import WorldQueryEngine
from .privacy import DataClassification, PrivacyGate
from .context import WorldContext, ContextPackager
from .persistence import WorldModelPersistence

logger = logging.getLogger(__name__)


class WorldModel:
    """Canonical World Model — the single authority for structured world state.

    Thread-safe singleton. All mutations go through public API.
    """

    _instance: Optional[WorldModel] = None
    _class_lock = threading.Lock()

    def __new__(cls, **kwargs: Any) -> WorldModel:
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        persistence: Optional[WorldModelPersistence] = None,
    ) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._entities: Dict[str, Entity] = {}
        self._graph = RelationshipGraph()
        self._temporal = TemporalState()
        self._events = EventIngestor()
        self._privacy = PrivacyGate()
        self._persistence = persistence or WorldModelPersistence()
        self._lock = threading.RLock()

        # Derived engines
        self._query = WorldQueryEngine(self._entities, self._graph, self._temporal)
        self._context = ContextPackager(self._entities, self._graph, self._temporal)

        # Event hooks
        self._on_change: List[Callable[[str, Any], None]] = []

        logger.info("WorldModel initialised")

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._class_lock:
            cls._instance = None

    # ── Entity Operations ─────────────────────────────────────────────

    def create_entity(
        self,
        entity_type: EntityType,
        name: str,
        state: EntityState = EntityState.ACTIVE,
        source: EntitySource = EntitySource.SYSTEM,
        scope: EntityScope = EntityScope.PRIVATE,
        confidence: float = 1.0,
        tags: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> Entity:
        """Create a new world entity."""
        with self._lock:
            entity = Entity.create(
                entity_type=entity_type,
                name=name,
                state=state,
                source=source,
                scope=scope,
                confidence=confidence,
                tags=tags or set(),
                metadata=metadata or {},
                description=description,
            )
            # Privacy: reject secrets
            if metadata:
                allowed, reason = self._privacy.reject_secrets(metadata)
                if not allowed:
                    raise ValueError(f"Entity rejected: {reason}")

            self._entities[entity.id] = entity
            self._temporal.record(entity.id, state.value, source=source.value)

            # Emit event
            self._events.ingest(WorldEvent(
                id=f"evt_{entity.id[:8]}",
                type=EventType.ENTITY_CREATED,
                entity_id=entity.id,
                timestamp=time.time(),
                data={"type": entity_type.value, "name": name},
                source=source.value,
                importance=0.6,
            ))

            self._notify_change("entity_created", entity)
            logger.info("Created entity: %s (%s)", name, entity_type.value)
            return entity

    def update_entity(self, entity_id: str, **kwargs: Any) -> bool:
        """Update an existing entity."""
        with self._lock:
            entity = self._entities.get(entity_id)
            if entity is None:
                return False

            if not self._privacy.check_permission(entity_id, "update"):
                return False

            # Privacy: reject secrets in metadata
            if "metadata" in kwargs:
                allowed, reason = self._privacy.reject_secrets(kwargs["metadata"])
                if not allowed:
                    raise ValueError(f"Update rejected: {reason}")

            old_state = entity.state.value
            entity.update(**kwargs)

            # Record temporal change
            new_state = kwargs.get("state", old_state)
            if new_state != old_state:
                self._temporal.record(entity_id, new_state if isinstance(new_state, str) else new_state.value)

            # Emit event
            self._events.ingest(WorldEvent(
                id=f"evt_{entity_id[:8]}_{int(time.time())}",
                type=EventType.ENTITY_UPDATED,
                entity_id=entity_id,
                timestamp=time.time(),
                data=kwargs,
                importance=0.5,
            ))

            self._notify_change("entity_updated", entity)
            return True

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relationships."""
        with self._lock:
            entity = self._entities.pop(entity_id, None)
            if entity is None:
                return False

            if not self._privacy.check_permission(entity_id, "delete"):
                self._entities[entity_id] = entity  # restore
                return False

            # Remove relationships
            for rel in list(self._graph.outgoing(entity_id)):
                self._graph.delete(rel.id)
            for rel in list(self._graph.incoming(entity_id)):
                self._graph.delete(rel.id)

            self._temporal.record(entity_id, "deleted")

            self._events.ingest(WorldEvent(
                id=f"evt_del_{entity_id[:8]}",
                type=EventType.ENTITY_DELETED,
                entity_id=entity_id,
                timestamp=time.time(),
                importance=0.4,
            ))

            self._notify_change("entity_deleted", {"id": entity_id})
            return True

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by id."""
        return self._entities.get(entity_id)

    def find_entity(
        self,
        entity_type: Optional[EntityType] = None,
        name: Optional[str] = None,
        state: Optional[EntityState] = None,
        limit: int = 50,
    ) -> List[Entity]:
        """Find entities by criteria."""
        results: List[Entity] = []
        for entity in self._entities.values():
            if entity_type and entity.type != entity_type:
                continue
            if name and entity.name != name:
                continue
            if state and entity.state != state:
                continue
            results.append(entity)
            if len(results) >= limit:
                break
        return results

    # ── Relationship Operations ───────────────────────────────────────

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
    ) -> Relationship:
        """Create a relationship between two entities."""
        with self._lock:
            if source_id not in self._entities or target_id not in self._entities:
                raise ValueError(f"One or both entities not found: {source_id}, {target_id}")

            rel = self._graph.create(source_id, target_id, rel_type, weight, metadata, confidence)

            self._events.ingest(WorldEvent(
                id=f"evt_rel_{rel.id[:8]}",
                type=EventType.RELATIONSHIP_CREATED,
                entity_id=source_id,
                timestamp=time.time(),
                data={"target_id": target_id, "type": rel_type.value},
                importance=0.4,
            ))

            return rel

    def delete_relationship(self, rel_id: str) -> bool:
        """Delete a relationship."""
        with self._lock:
            return self._graph.delete(rel_id)

    # ── Query Engine ──────────────────────────────────────────────────

    @property
    def query(self) -> WorldQueryEngine:
        """Access the query engine."""
        return self._query

    def context_for_request(self, user_request: str, task_type: Optional[str] = None) -> WorldContext:
        """Get relevant context for a user request."""
        return self._context.pack_for_request(user_request, task_type)

    def context_for_entity(self, entity_id: str) -> WorldContext:
        """Get context for a specific entity."""
        return self._context.pack_for_entity(entity_id)

    # ── Event Operations ──────────────────────────────────────────────

    def ingest_event(self, event: WorldEvent) -> bool:
        """Ingest a world event."""
        return self._events.ingest(event)

    def subscribe_event(self, event_type: str, callback: Callable) -> None:
        """Subscribe to world events."""
        self._events.subscribe(event_type, callback)

    # ── Privacy Operations ────────────────────────────────────────────

    def classify(self, entity_type: str, metadata: Dict[str, Any]) -> DataClassification:
        """Classify data sensitivity."""
        return self._privacy.classify(entity_type, metadata)

    def freeze_entity(self, entity_id: str) -> None:
        """Freeze an entity."""
        self._privacy.freeze_entity(entity_id)

    def restrict_entity(self, entity_id: str) -> None:
        """Restrict an entity to read-only."""
        self._privacy.restrict_entity(entity_id)

    def correct(self, entity_id: str, field_name: str, new_value: Any) -> None:
        """Apply user correction."""
        self._privacy.apply_user_correction(entity_id, field_name, new_value)

    # ── Maintenance ───────────────────────────────────────────────────

    def decay_freshness(self, half_life_seconds: float = 86400) -> int:
        """Apply freshness decay to all entities."""
        count = 0
        with self._lock:
            for entity in self._entities.values():
                old = entity.freshness
                entity.decay_freshness(half_life_seconds)
                if entity.freshness != old:
                    count += 1
        return count

    def repair(self) -> Dict[str, Any]:
        """Detect and repair world model issues."""
        issues: List[str] = []

        # Check for orphan entities (referenced but not in store)
        all_referenced: Set[str] = set()
        for rel in self._graph.all_relationships():
            all_referenced.add(rel.source_id)
            all_referenced.add(rel.target_id)
        orphans = all_referenced - set(self._entities.keys())
        if orphans:
            issues.append(f"Found {len(orphans)} orphan references")

        # Check for stale entities
        stale = self._temporal.stale_entities(86400)
        if stale:
            issues.append(f"{len(stale)} entities stale for >24h")

        # Check for conflicting state
        conflicts = 0
        for entity_id, entries in self._temporal._history.items():
            if len(entries) >= 2:
                recent = list(entries)[-2:]
                if recent[0].state != recent[1].state:
                    conflicts += 1

        return {
            "orphan_references": len(orphans),
            "stale_entities": len(stale),
            "state_conflicts": conflicts,
            "issues": issues,
            "entity_count": len(self._entities),
            "relationship_count": self._graph.count(),
            "temporal_count": self._temporal.count(),
        }

    def health(self) -> Dict[str, Any]:
        """World model health metrics."""
        return {
            "entity_count": len(self._entities),
            "relationship_count": self._graph.count(),
            "temporal_count": self._temporal.count(),
            "event_stats": self._events.stats(),
            "privacy": self._privacy.to_dict(),
            "timestamp": time.time(),
        }

    # ── Persistence ───────────────────────────────────────────────────

    def save(self) -> bool:
        """Persist world model state to disk."""
        with self._lock:
            return self._persistence.save_all(
                entities=[e.to_dict() for e in self._entities.values()],
                relationships=self._graph.to_dict(),
                temporal=self._temporal.to_dict(),
                events=[e.to_dict() for e in self._events.recent(1000)],
            )

    def load(self) -> bool:
        """Load world model state from disk."""
        with self._lock:
            data = self._persistence.load_all()

            # Restore entities
            for d in data.get("entities", []):
                entity = Entity.from_dict(d)
                self._entities[entity.id] = entity

            # Restore relationships
            self._graph = RelationshipGraph.from_dict(data.get("relationships", []))

            # Rebuild query engine with current data
            self._query = WorldQueryEngine(self._entities, self._graph, self._temporal)
            self._context = ContextPackager(self._entities, self._graph, self._temporal)

            logger.info(
                "World model loaded: %d entities, %d relationships",
                len(self._entities),
                self._graph.count(),
            )
            return True

    # ── Change Notification ───────────────────────────────────────────

    def on_change(self, callback: Callable[[str, Any], None]) -> None:
        """Register a change listener."""
        self._on_change.append(callback)

    def _notify_change(self, change_type: str, data: Any) -> None:
        """Notify change listeners."""
        for cb in self._on_change:
            try:
                cb(change_type, data)
            except Exception:
                pass

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """World model statistics."""
        counts = self._query.count()
        return {
            **counts,
            "relationship_count": self._graph.count(),
            "temporal_count": self._temporal.count(),
            "event_stats": self._events.stats(),
        }

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._class_lock:
            cls._instance = None
