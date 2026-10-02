"""World Model Relationship Graph — typed relationships between entities.

Supports: create, update, delete, query, traverse, path discovery.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class RelationshipType(str, Enum):
    """Typed relationships between entities."""
    # Structural
    OWNS = "owns"
    CONTAINS = "contains"
    BELONGS_TO = "belongs_to"
    PART_OF = "part_of"
    HAS = "has"

    # Dependency
    DEPENDS_ON = "depends_on"
    BLOCKED_BY = "blocked_by"
    PROVIDES = "provides"
    USES = "uses"
    REQUIRES = "requires"

    # Temporal
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    SCHEDULED_BY = "scheduled_by"

    # Causal
    CAUSES = "causes"
    TRIGGERS = "triggers"
    AFFECTS = "affects"

    # Social/Workflow
    MANAGES = "manages"
    ASSIGNED_TO = "assigned_to"
    CREATED_BY = "created_by"
    REVIEWED_BY = "reviewed_by"

    # Trading
    TRACKS = "tracks"
    POSITION_IN = "position_in"
    SECTOR_OF = "sector_of"

    # Cognitive
    INFORMS = "informs"
    VALIDATES = "validates"
    CONTEXT_FOR = "context_for"

    # Extensible
    CUSTOM = "custom"


@dataclass(frozen=True)
class Relationship:
    """An immutable typed edge between two entities."""
    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    confidence: float = 1.0

    def __post_init__(self):
        object.__setattr__(self, 'confidence', max(0.0, min(1.0, self.confidence)))
        object.__setattr__(self, 'weight', max(0.0, min(1.0, self.weight)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type.value,
            "weight": self.weight,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Relationship:
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            type=RelationshipType(data["type"]),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", 0.0),
            confidence=data.get("confidence", 1.0),
        )


class RelationshipGraph:
    """Thread-safe typed relationship graph with adjacency lists.

    Supports:
    - create / delete
    - query by source, target, type
    - traverse (BFS/DFS)
    - path discovery
    - dependency resolution
    """

    def __init__(self) -> None:
        self._relationships: Dict[str, Relationship] = {}
        self._outgoing: Dict[str, List[str]] = defaultdict(list)  # source_id -> [rel_id]
        self._incoming: Dict[str, List[str]] = defaultdict(list)  # target_id -> [rel_id]
        self._by_type: Dict[str, List[str]] = defaultdict(list)   # type -> [rel_id]
        self._by_pair: Dict[Tuple[str, str], List[str]] = defaultdict(list)  # (src,tgt) -> [rel_id]

    def create(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        rel_id: Optional[str] = None,
    ) -> Relationship:
        """Create a new relationship."""
        import uuid
        rel = Relationship(
            id=rel_id or str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            type=rel_type,
            weight=weight,
            metadata=metadata or {},
            confidence=confidence,
        )
        self._relationships[rel.id] = rel
        self._outgoing[source_id].append(rel.id)
        self._incoming[target_id].append(rel.id)
        self._by_type[rel.type.value].append(rel.id)
        self._by_pair[(source_id, target_id)].append(rel.id)
        return rel

    def delete(self, rel_id: str) -> bool:
        """Remove a relationship by id."""
        rel = self._relationships.pop(rel_id, None)
        if rel is None:
            return False
        self._outgoing[rel.source_id] = [
            r for r in self._outgoing[rel.source_id] if r != rel_id
        ]
        self._incoming[rel.target_id] = [
            r for r in self._incoming[rel.target_id] if r != rel_id
        ]
        self._by_type[rel.type.value] = [
            r for r in self._by_type[rel.type.value] if r != rel_id
        ]
        self._by_pair[(rel.source_id, rel.target_id)] = [
            r for r in self._by_pair[(rel.source_id, rel.target_id)] if r != rel_id
        ]
        return True

    def get(self, rel_id: str) -> Optional[Relationship]:
        """Get relationship by id."""
        return self._relationships.get(rel_id)

    def outgoing(self, entity_id: str, rel_type: Optional[RelationshipType] = None) -> List[Relationship]:
        """Get all outgoing relationships from entity."""
        rel_ids = self._outgoing.get(entity_id, [])
        rels = [self._relationships[rid] for rid in rel_ids if rid in self._relationships]
        if rel_type is not None:
            rels = [r for r in rels if r.type == rel_type]
        return rels

    def incoming(self, entity_id: str, rel_type: Optional[RelationshipType] = None) -> List[Relationship]:
        """Get all incoming relationships to entity."""
        rel_ids = self._incoming.get(entity_id, [])
        rels = [self._relationships[rid] for rid in rel_ids if rid in self._relationships]
        if rel_type is not None:
            rels = [r for r in rels if r.type == rel_type]
        return rels

    def neighbors(self, entity_id: str) -> Set[str]:
        """Get all directly connected entity ids (both directions)."""
        result: Set[str] = set()
        for rid in self._outgoing.get(entity_id, []):
            rel = self._relationships.get(rid)
            if rel:
                result.add(rel.target_id)
        for rid in self._incoming.get(entity_id, []):
            rel = self._relationships.get(rid)
            if rel:
                result.add(rel.source_id)
        return result

    def by_type(self, rel_type: RelationshipType) -> List[Relationship]:
        """Get all relationships of a given type."""
        rel_ids = self._by_type.get(rel_type.value, [])
        return [self._relationships[rid] for rid in rel_ids if rid in self._relationships]

    def between(self, source_id: str, target_id: str) -> List[Relationship]:
        """Get all relationships between two entities."""
        rel_ids = self._by_pair.get((source_id, target_id), [])
        return [self._relationships[rid] for rid in rel_ids if rid in self._relationships]

    def traverse_bfs(
        self,
        start_id: str,
        max_depth: int = 10,
        rel_types: Optional[Set[RelationshipType]] = None,
    ) -> List[Tuple[str, int]]:
        """BFS traversal from start_id. Returns [(entity_id, depth)]."""
        visited: Set[str] = set()
        result: List[Tuple[str, int]] = []
        queue: deque[Tuple[str, int]] = deque([(start_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            result.append((current, depth))

            for rel in self.outgoing(current, None):
                if rel_types and rel.type not in rel_types:
                    continue
                if rel.target_id not in visited:
                    queue.append((rel.target_id, depth + 1))

        return result

    def find_path(
        self,
        start_id: str,
        end_id: str,
        max_depth: int = 10,
    ) -> Optional[List[str]]:
        """Find shortest path between two entities. Returns list of entity ids."""
        if start_id == end_id:
            return [start_id]

        visited: Set[str] = set()
        parent: Dict[str, str] = {}
        queue: deque[Tuple[str, int]] = deque([(start_id, 0)])
        visited.add(start_id)

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for rel in self.outgoing(current):
                neighbor = rel.target_id
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                parent[neighbor] = current

                if neighbor == end_id:
                    path = [end_id]
                    while path[-1] != start_id:
                        path.append(parent[path[-1]])
                    path.reverse()
                    return path

                queue.append((neighbor, depth + 1))

        return None

    def dependencies_of(self, entity_id: str) -> List[str]:
        """Get all entities that entity_id depends on (DEPENDS_ON, BLOCKED_BY, REQUIRES)."""
        deps: List[str] = []
        for rel in self.outgoing(entity_id):
            if rel.type in (RelationshipType.DEPENDS_ON, RelationshipType.BLOCKED_BY, RelationshipType.REQUIRES):
                deps.append(rel.target_id)
        return deps

    def dependents_of(self, entity_id: str) -> List[str]:
        """Get all entities that depend on entity_id."""
        deps: List[str] = []
        for rel in self.incoming(entity_id):
            if rel.type in (RelationshipType.DEPENDS_ON, RelationshipType.BLOCKED_BY, RelationshipType.REQUIRES):
                deps.append(rel.source_id)
        return deps

    def count(self) -> int:
        """Total number of relationships."""
        return len(self._relationships)

    def all_relationships(self) -> List[Relationship]:
        """Return all relationships."""
        return list(self._relationships.values())

    def clear(self) -> None:
        """Remove all relationships."""
        self._relationships.clear()
        self._outgoing.clear()
        self._incoming.clear()
        self._by_type.clear()
        self._by_pair.clear()

    def to_dict(self) -> List[Dict[str, Any]]:
        """Serialize all relationships."""
        return [r.to_dict() for r in self._relationships.values()]

    @classmethod
    def from_dict(cls, data: List[Dict[str, Any]]) -> RelationshipGraph:
        """Deserialize relationships."""
        graph = cls()
        for d in data:
            rel = Relationship.from_dict(d)
            graph._relationships[rel.id] = rel
            graph._outgoing[rel.source_id].append(rel.id)
            graph._incoming[rel.target_id].append(rel.id)
            graph._by_type[rel.type.value].append(rel.id)
            graph._by_pair[(rel.source_id, rel.target_id)].append(rel.id)
        return graph
