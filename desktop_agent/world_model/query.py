"""World Model Query Engine — natural-language queries over the world model.

Returns evidence/provenance with every answer.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from .entity import Entity, EntityType, EntityState
from .relationship import Relationship, RelationshipGraph, RelationshipType
from .temporal import TemporalState


class WorldQueryEngine:
    """Natural-language query engine over the World Model.

    Supports:
    - Structured queries (by type, state, relationship)
    - Natural-language pattern matching
    - Evidence/provenance with every answer
    """

    def __init__(
        self,
        entities: Dict[str, Entity],
        graph: RelationshipGraph,
        temporal: TemporalState,
    ) -> None:
        self._entities = entities
        self._graph = graph
        self._temporal = temporal

    def query_by_type(
        self,
        entity_type: EntityType,
        state: Optional[EntityState] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query entities by type and optional state."""
        results = []
        for entity in self._entities.values():
            if entity.type != entity_type:
                continue
            if state and entity.state != state:
                continue
            results.append(self._entity_with_context(entity))
        return results[:limit]

    def query_by_state(
        self,
        state: EntityState,
        entity_type: Optional[EntityType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query entities by state."""
        results = []
        for entity in self._entities.values():
            if entity.state != state:
                continue
            if entity_type and entity.type != entity_type:
                continue
            results.append(self._entity_with_context(entity))
        return results[:limit]

    def query_blocked(self) -> List[Dict[str, Any]]:
        """Find all blocked entities."""
        return self.query_by_state(EntityState.BLOCKED)

    def query_active(self) -> List[Dict[str, Any]]:
        """Find all active entities."""
        return self.query_by_state(EntityState.ACTIVE)

    def query_dependencies(self, entity_id: str) -> Dict[str, Any]:
        """Get dependency graph for an entity."""
        deps = self._graph.dependencies_of(entity_id)
        dependents = self._graph.dependents_of(entity_id)
        return {
            "entity_id": entity_id,
            "depends_on": [self._get_entity_summary(eid) for eid in deps],
            "depended_by": [self._get_entity_summary(eid) for eid in dependents],
            "evidence": f"Dependency graph for {entity_id}",
        }

    def query_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get full entity with relationships and temporal state."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return None
        return self._entity_with_context(entity)

    def query_relationships(
        self,
        entity_id: str,
        direction: str = "both",
        rel_type: Optional[RelationshipType] = None,
    ) -> List[Dict[str, Any]]:
        """Query relationships for an entity."""
        results = []
        if direction in ("outgoing", "both"):
            for rel in self._graph.outgoing(entity_id, rel_type):
                results.append({
                    "relationship": rel.to_dict(),
                    "target": self._get_entity_summary(rel.target_id),
                })
        if direction in ("incoming", "both"):
            for rel in self._graph.incoming(entity_id, rel_type):
                results.append({
                    "relationship": rel.to_dict(),
                    "source": self._get_entity_summary(rel.source_id),
                })
        return results

    def query_path(self, from_id: str, to_id: str) -> Optional[Dict[str, Any]]:
        """Find path between two entities."""
        path = self._graph.find_path(from_id, to_id)
        if path is None:
            return None
        return {
            "path": path,
            "length": len(path),
            "steps": [
                {
                    "from": self._get_entity_summary(path[i]),
                    "to": self._get_entity_summary(path[i + 1]),
                }
                for i in range(len(path) - 1)
            ],
        }

    def query_changed_since(self, since: float) -> List[Dict[str, Any]]:
        """Find all entities that changed since a given time."""
        changes = self._temporal.what_changed_since(since)
        return [
            {
                **change,
                "entity": self._get_entity_summary(change["entity_id"]),
            }
            for change in changes
        ]

    def query_stale(self, max_age_seconds: float = 3600) -> List[Dict[str, Any]]:
        """Find stale entities."""
        return self._temporal.stale_entities(max_age_seconds)

    def query_by_tag(self, tag: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Query entities by tag."""
        results = []
        for entity in self._entities.values():
            if tag in entity.tags:
                results.append(self._entity_with_context(entity))
        return results[:limit]

    def query_by_source(self, source: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Query entities by source."""
        results = []
        for entity in self._entities.values():
            if entity.source.value == source:
                results.append(self._entity_with_context(entity))
        return results[:limit]

    def query_high_importance(self, min_importance: float = 0.7) -> List[Dict[str, Any]]:
        """Query entities with high confidence/freshness."""
        results = []
        for entity in self._entities.values():
            importance = (entity.confidence + entity.freshness) / 2
            if importance >= min_importance:
                results.append(self._entity_with_context(entity))
        return results

    def query_natural(self, question: str) -> Dict[str, Any]:
        """Answer a natural-language question about the world model.

        Uses pattern matching for common queries.
        """
        q = question.lower()

        if any(kw in q for kw in ["what am i working on", "current task", "current project"]):
            return self._answer_current_focus()
        if any(kw in q for kw in ["blocked", "stuck", "blocker"]):
            return self._answer_blockers()
        if any(kw in q for kw in ["changed today", "what changed", "recent"]):
            return self._answer_recent_changes()
        if any(kw in q for kw in ["pending", "todo", "incomplete"]):
            return self._answer_pending()
        if any(kw in q for kw in ["goal", "objective", "target"]):
            return self._answer_goals()

        return {
            "answer": "I don't have enough context to answer that question.",
            "evidence": [],
            "confidence": 0.0,
        }

    def _answer_current_focus(self) -> Dict[str, Any]:
        active_tasks = self.query_by_type(EntityType.TASK, EntityState.ACTIVE, limit=5)
        active_projects = self.query_by_type(EntityType.PROJECT, EntityState.ACTIVE, limit=3)
        return {
            "answer": f"You have {len(active_tasks)} active tasks and {len(active_projects)} active projects.",
            "tasks": active_tasks,
            "projects": active_projects,
            "evidence": ["Active entities from world model"],
            "confidence": 0.8,
        }

    def _answer_blockers(self) -> Dict[str, Any]:
        blocked = self.query_blocked()
        return {
            "answer": f"There are {len(blocked)} blocked items.",
            "blocked": blocked,
            "evidence": ["Blocked entities from world model"],
            "confidence": 0.9,
        }

    def _answer_recent_changes(self) -> Dict[str, Any]:
        since = time.time() - 86400  # last 24 hours
        changes = self.query_changed_since(since)
        return {
            "answer": f"{len(changes)} entities changed in the last 24 hours.",
            "changes": changes,
            "evidence": ["Temporal state diff"],
            "confidence": 0.85,
        }

    def _answer_pending(self) -> Dict[str, Any]:
        pending = self.query_by_state(EntityState.PENDING, limit=20)
        return {
            "answer": f"{len(pending)} items are pending.",
            "pending": pending,
            "evidence": ["Pending entities from world model"],
            "confidence": 0.85,
        }

    def _answer_goals(self) -> Dict[str, Any]:
        goals = self.query_by_type(EntityType.GOAL, limit=10)
        return {
            "answer": f"{len(goals)} goals tracked.",
            "goals": goals,
            "evidence": ["Goal entities from world model"],
            "confidence": 0.8,
        }

    def _entity_with_context(self, entity: Entity) -> Dict[str, Any]:
        """Entity with relationships and temporal state."""
        outgoing = self._graph.outgoing(entity.id)
        incoming = self._graph.incoming(entity.id)
        temporal = self._temporal.current_state(entity.id)
        return {
            "entity": entity.to_dict(),
            "outgoing_relationships": len(outgoing),
            "incoming_relationships": len(incoming),
            "temporal_state": temporal.to_dict() if temporal else None,
        }

    def _get_entity_summary(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get lightweight entity summary."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return {"id": entity_id, "name": "unknown"}
        return {
            "id": entity.id,
            "type": entity.type.value,
            "name": entity.name,
            "state": entity.state.value,
        }

    def count(self) -> Dict[str, int]:
        """Count entities by type and state."""
        by_type: Dict[str, int] = {}
        by_state: Dict[str, int] = {}
        for entity in self._entities.values():
            by_type[entity.type.value] = by_type.get(entity.type.value, 0) + 1
            by_state[entity.state.value] = by_state.get(entity.state.value, 0) + 1
        return {"by_type": by_type, "by_state": by_state, "total": len(self._entities)}
