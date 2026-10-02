"""World Model Context Packaging — compact dynamic context for Super-Brain.

Creates a Personal Context Window:
  WHO, WHERE, WHAT, WHY, WHEN, CURRENT STATE, GOAL, PRIORITY, CONSTRAINTS,
  RELEVANT HISTORY, NEXT ACTION
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .entity import Entity, EntityType, EntityState
from .relationship import RelationshipGraph
from .temporal import TemporalState


@dataclass
class WorldContext:
    """Compact context snapshot for decision-making."""
    who: str = ""
    where: str = ""
    what: str = ""
    why: str = ""
    when: float = 0.0
    current_state: str = "unknown"
    goal: str = ""
    priority: str = "normal"
    constraints: List[str] = field(default_factory=list)
    relevant_history: List[Dict[str, Any]] = field(default_factory=list)
    next_action: str = ""
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    entity_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "who": self.who,
            "where": self.where,
            "what": self.what,
            "why": self.why,
            "when": self.when,
            "current_state": self.current_state,
            "goal": self.goal,
            "priority": self.priority,
            "constraints": self.constraints,
            "relevant_history": self.relevant_history,
            "next_action": self.next_action,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "entity_ids": self.entity_ids,
            "timestamp": self.timestamp,
        }


class ContextPackager:
    """Pack relevant world state into compact context for Super-Brain.

    Uses targeted retrieval — never dumps the entire world model.
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

    def pack_for_request(
        self,
        user_request: str,
        task_type: Optional[str] = None,
        max_entities: int = 10,
    ) -> WorldContext:
        """Pack relevant context for a user request.

        Only retrieves entities relevant to the request.
        """
        context = WorldContext(
            when=time.time(),
            evidence=["World model context packager"],
        )

        # Find relevant entities based on request keywords
        relevant = self._find_relevant_entities(user_request, max_entities)
        context.entity_ids = [e.id for e in relevant]

        # Determine focus
        if relevant:
            primary = relevant[0]
            context.what = f"{primary.type.value}: {primary.name}"
            context.current_state = primary.state.value

        # Find active goals
        active_goals = [
            e for e in self._entities.values()
            if e.type == EntityType.GOAL and e.state == EntityState.ACTIVE
        ]
        if active_goals:
            context.goal = active_goals[0].name
            context.evidence.append(f"Active goal: {active_goals[0].name}")

        # Find blockers
        blocked = [
            e for e in self._entities.values()
            if e.state == EntityState.BLOCKED
        ]
        if blocked:
            context.constraints.append(f"{len(blocked)} blocked items exist")
            context.evidence.append(f"Blocked: {[e.name for e in blocked[:3]]}")

        # Find recent changes
        since = time.time() - 3600
        recent = self._temporal.what_changed_since(since)
        if recent:
            context.relevant_history = recent[:5]
            context.evidence.append(f"{len(recent)} changes in last hour")

        # Determine priority
        high_priority_count = sum(
            1 for e in relevant
            if e.confidence > 0.8 and e.freshness > 0.7
        )
        if high_priority_count > 2:
            context.priority = "high"
        elif high_priority_count == 0:
            context.priority = "low"

        context.confidence = min(1.0, 0.5 + len(relevant) * 0.05)
        return context

    def pack_for_entity(self, entity_id: str) -> WorldContext:
        """Pack full context for a specific entity."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return WorldContext(what="unknown", current_state="not_found")

        outgoing = self._graph.outgoing(entity_id)
        incoming = self._graph.incoming(entity_id)
        deps = self._graph.dependencies_of(entity_id)

        return WorldContext(
            what=f"{entity.type.value}: {entity.name}",
            current_state=entity.state.value,
            when=entity.updated_at,
            evidence=[
                f"Entity confidence: {entity.confidence}",
                f"Source: {entity.source.value}",
                f"Outgoing relationships: {len(outgoing)}",
                f"Incoming relationships: {len(incoming)}",
                f"Dependencies: {len(deps)}",
            ],
            constraints=[f"Depends on: {d}" for d in deps],
            confidence=entity.confidence,
            entity_ids=[entity_id],
        )

    def _find_relevant_entities(
        self,
        text: str,
        limit: int,
    ) -> List[Entity]:
        """Find entities relevant to the given text."""
        text_lower = text.lower()
        scored: List[tuple] = []

        for entity in self._entities.values():
            score = 0.0
            # Name match
            if entity.name.lower() in text_lower:
                score += 1.0
            elif any(word in entity.name.lower() for word in text_lower.split()):
                score += 0.5
            # Type match
            if entity.type.value in text_lower:
                score += 0.3
            # Tag match
            for tag in entity.tags:
                if tag.lower() in text_lower:
                    score += 0.2
            # Boost active entities
            if entity.state == EntityState.ACTIVE:
                score += 0.1
            # Boost high confidence
            score += entity.confidence * 0.1

            if score > 0:
                scored.append((score, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entity for _, entity in scored[:limit]]
