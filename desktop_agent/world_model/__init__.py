"""MYRAA World Model — Personal World Model + Digital Life Intelligence.

A structured WORLD MODEL layer that maintains:
- Entities + Relationships + State + Time + Context
- Current structured world state and relationships
- Provenance, confidence, freshness, permissions

DO NOT create second memory, brain, planner, scheduler, autonomy, or vision engine.
WorldModel is a NEW DOMAIN STATE LAYER that integrates with existing authorities.
"""

from .entity import Entity, EntityType, EntityState, EntitySchema
from .relationship import Relationship, RelationshipType, RelationshipGraph
from .temporal import TemporalState, TimelineEntry
from .events import WorldEvent, EventType, EventIngestor
from .model import WorldModel
from .query import WorldQueryEngine
from .privacy import DataClassification, PrivacyGate
from .context import WorldContext, ContextPackager

__all__ = [
    "Entity", "EntityType", "EntityState", "EntitySchema",
    "Relationship", "RelationshipType", "RelationshipGraph",
    "TemporalState", "TimelineEntry",
    "WorldEvent", "EventType", "EventIngestor",
    "WorldModel",
    "WorldQueryEngine",
    "DataClassification", "PrivacyGate",
    "WorldContext", "ContextPackager",
]
