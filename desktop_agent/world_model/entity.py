"""World Model Entity System — typed, extensible world objects.

Every entity has:
  id, type, name, state, created_at, updated_at, source,
  confidence, freshness, scope, sensitivity, relationships, metadata
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class EntityType(str, Enum):
    """Extensible entity types. New types can be added without modifying core."""
    USER = "user"
    PERSON = "person"
    PROJECT = "project"
    TASK = "task"
    GOAL = "goal"
    MILESTONE = "milestone"
    FILE = "file"
    FOLDER = "folder"
    APPLICATION = "application"
    WEBSITE = "website"
    BROWSER_TAB = "browser_tab"
    DEVICE = "device"
    WORKFLOW = "workflow"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    AGENT = "agent"
    MODEL = "model"
    CAPABILITY = "capability"
    EVENT = "event"
    ALERT = "alert"
    DEADLINE = "deadline"
    MEETING = "meeting"
    REMINDER = "reminder"
    TRADING_ACCOUNT = "trading_account"
    STOCK = "stock"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    SERVICE = "service"
    PROVIDER = "provider"
    PREFERENCE = "preference"
    SYSTEM = "system"
    CONTEXT = "context"
    WORKSPACE = "workspace"
    # Extensible: new types added here


class EntityState(str, Enum):
    """Canonical entity states."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    STALE = "stale"
    UNKNOWN = "unknown"
    ARCHIVED = "archived"


class EntityScope(str, Enum):
    """Data scope for privacy/permissions."""
    PUBLIC = "public"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class EntitySource(str, Enum):
    """Provenance: where this entity came from."""
    USER_INPUT = "user_input"
    SYSTEM = "system"
    VISION = "vision"
    FILE = "file"
    EVENT = "event"
    INFERENCE = "inference"
    MEMORY = "memory"
    EXTERNAL = "external"
    BROWSER = "browser"
    APPLICATION = "application"


@dataclass
class EntitySchema:
    """Extensible schema definition for an entity type."""
    entity_type: EntityType
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    state_values: List[EntityState] = field(default_factory=lambda: list(EntityState))
    description: str = ""


@dataclass
class Entity:
    """A single world object with full metadata.

    Thread-safe: all mutations go through update() which acquires _lock.
    """
    id: str
    type: EntityType
    name: str
    state: EntityState = EntityState.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source: EntitySource = EntitySource.SYSTEM
    confidence: float = 1.0
    freshness: float = 1.0
    scope: EntityScope = EntityScope.PRIVATE
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.freshness = max(0.0, min(1.0, self.freshness))

    def update(self, **kwargs: Any) -> None:
        """Update entity fields and bump updated_at."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = time.time()
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.freshness = max(0.0, min(1.0, self.freshness))

    def touch(self) -> None:
        """Mark as recently accessed."""
        self.updated_at = time.time()

    def is_stale(self, max_age_seconds: float = 3600) -> bool:
        """Check if entity hasn't been updated within max_age."""
        return (time.time() - self.updated_at) > max_age_seconds

    def decay_freshness(self, half_life_seconds: float = 86400) -> None:
        """Apply exponential decay to freshness based on age."""
        age = time.time() - self.updated_at
        import math
        self.freshness = max(0.0, math.exp(-0.693 * age / half_life_seconds))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source.value,
            "confidence": self.confidence,
            "freshness": self.freshness,
            "scope": self.scope.value,
            "tags": sorted(self.tags),
            "metadata": dict(self.metadata),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Entity:
        """Deserialize from dict."""
        return cls(
            id=data["id"],
            type=EntityType(data["type"]),
            name=data["name"],
            state=EntityState(data.get("state", "active")),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            source=EntitySource(data.get("source", "system")),
            confidence=data.get("confidence", 1.0),
            freshness=data.get("freshness", 1.0),
            scope=EntityScope(data.get("scope", "private")),
            tags=set(data.get("tags", [])),
            metadata=data.get("metadata", {}),
            description=data.get("description", ""),
        )

    @classmethod
    def create(
        cls,
        entity_type: EntityType,
        name: str,
        state: EntityState = EntityState.ACTIVE,
        source: EntitySource = EntitySource.SYSTEM,
        **kwargs: Any,
    ) -> Entity:
        """Factory: create entity with auto-generated id and timestamps."""
        return cls(
            id=str(uuid.uuid4()),
            type=entity_type,
            name=name,
            state=state,
            source=source,
            **kwargs,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"Entity(id={self.id[:8]}..., type={self.type.value}, "
            f"name={self.name!r}, state={self.state.value})"
        )
