"""
MYRAA Vision V3

Spatial Graph Engine

Purpose
-------
Represents spatial relationships between detected UI elements.

Used by

- Fusion Engine
- Semantic Tree
- Screen Analyzer
- Planner

Author
------
MYRAA Vision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .layout_analyzer import Rect
from .fusion_engine import SemanticNode


# ==========================================================
# Spatial Relations
# ==========================================================

class SpatialRelation(str, Enum):

    INSIDE = "inside"

    CONTAINS = "contains"

    LEFT_OF = "left_of"

    RIGHT_OF = "right_of"

    ABOVE = "above"

    BELOW = "below"

    OVERLAPS = "overlaps"

    TOUCHING = "touching"

    NEAREST = "nearest"

    INTERSECTS = "intersects"


# ==========================================================
# Graph Edge
# ==========================================================

@dataclass(slots=True)
class SpatialEdge:

    source: int

    target: int

    relation: SpatialRelation

    distance: float

    confidence: float = 1.0


# ==========================================================
# Graph Node Reference
# ==========================================================

@dataclass(slots=True)
class SpatialNodeRef:

    id: int

    node: SemanticNode

    incoming: List[SpatialEdge] = field(default_factory=list)

    outgoing: List[SpatialEdge] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)


# ==========================================================
# Spatial Graph
# ==========================================================

class SpatialGraph:

    """
    Graph of semantic nodes.

    Every UI element becomes
    one graph node.

    Relationships are represented
    by SpatialEdge objects.
    """

    def __init__(self):

        self.nodes: Dict[int, SpatialNodeRef] = {}

        self.next_id = 0

    # ------------------------------------------------------
    # Node Registration
    # ------------------------------------------------------

    def add_node(

        self,

        node: SemanticNode,

    ) -> int:

        node_id = self.next_id

        self.next_id += 1

        self.nodes[node_id] = SpatialNodeRef(

            id=node_id,

            node=node,

        )

        return node_id

    # ------------------------------------------------------
    # Edge Registration
    # ------------------------------------------------------

    def add_edge(

        self,

        source: int,

        target: int,

        relation: SpatialRelation,

        distance: float,

        confidence: float = 1.0,

    ):

        edge = SpatialEdge(

            source=source,

            target=target,

            relation=relation,

            distance=distance,

            confidence=confidence,

        )

        self.nodes[source].outgoing.append(edge)

        self.nodes[target].incoming.append(edge)

    # ------------------------------------------------------
    # Queries
    # ------------------------------------------------------

    def get_node(

        self,

        node_id: int,

    ) -> Optional[SpatialNodeRef]:

        return self.nodes.get(node_id)

    def all_nodes(

        self,

    ) -> List[SpatialNodeRef]:

        return list(self.nodes.values())

    def neighbors(

        self,

        node_id: int,

    ) -> List[SpatialNodeRef]:

        result = []

        for edge in self.nodes[node_id].outgoing:

            result.append(

                self.nodes[edge.target]

            )

        return result

    def outgoing(

        self,

        node_id: int,

    ) -> List[SpatialEdge]:

        return self.nodes[node_id].outgoing

    def incoming(

        self,

        node_id: int,

    ) -> List[SpatialEdge]:

        return self.nodes[node_id].incoming

    def clear(self):

        self.nodes.clear()

        self.next_id = 0


    # ------------------------------------------------------
    # Geometry Helpers
    # ------------------------------------------------------

    @staticmethod
    def _distance(a: Rect, b: Rect) -> float:
        """
        Euclidean distance between rectangle centers.
        """
        ax, ay = a.center
        bx, by = b.center

        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    @staticmethod
    def _contains(outer: Rect, inner: Rect) -> bool:
        """
        Returns True if outer completely contains inner.
        """
        return (
            outer.x <= inner.x
            and outer.y <= inner.y
            and outer.right >= inner.right
            and outer.bottom >= inner.bottom
        )

    @staticmethod
    def _intersects(a: Rect, b: Rect) -> bool:
        """
        Rectangle intersection test.
        """
        return not (
            a.right < b.x
            or b.right < a.x
            or a.bottom < b.y
            or b.bottom < a.y
        )

    @staticmethod
    def _overlap_area(a: Rect, b: Rect) -> float:
        """
        Calculates overlap area.
        """

        left = max(a.x, b.x)
        top = max(a.y, b.y)
        right = min(a.right, b.right)
        bottom = min(a.bottom, b.bottom)

        if right <= left or bottom <= top:
            return 0.0

        return (right - left) * (bottom - top)

    @staticmethod
    def _touching(a: Rect, b: Rect, tolerance: int = 2) -> bool:
        """
        Returns True if rectangles touch each other.
        """

        horizontal = (
            abs(a.right - b.x) <= tolerance
            or abs(b.right - a.x) <= tolerance
        )

        vertical_overlap = not (
            a.bottom < b.y
            or b.bottom < a.y
        )

        vertical = (
            abs(a.bottom - b.y) <= tolerance
            or abs(b.bottom - a.y) <= tolerance
        )

        horizontal_overlap = not (
            a.right < b.x
            or b.right < a.x
        )

        return (
            (horizontal and vertical_overlap)
            or
            (vertical and horizontal_overlap)
        )

    @staticmethod
    def _left_of(a: Rect, b: Rect) -> bool:
        return a.right <= b.x

    @staticmethod
    def _right_of(a: Rect, b: Rect) -> bool:
        return a.x >= b.right

    @staticmethod
    def _above(a: Rect, b: Rect) -> bool:
        return a.bottom <= b.y

    @staticmethod
    def _below(a: Rect, b: Rect) -> bool:
        return a.y >= b.bottom

    @classmethod
    def from_nodes(
        cls,
        nodes: list[SemanticNode],
    ) -> "SpatialGraph":
        """
        Creates a SpatialGraph from semantic nodes.
        """

        graph = cls()

        for node in nodes:
            graph.add_node(node)

        graph.build_relationships()

        return graph

    # ------------------------------------------------------
    # Automatic Relationship Builder
    # ------------------------------------------------------

    def build_relationships(self) -> None:
        """
        Automatically generates spatial relationships
        between every registered node.
        """

        node_refs = list(self.nodes.values())

        for i, source in enumerate(node_refs):

            for target in node_refs[i + 1:]:

                self._analyze_pair(source, target)

    # ------------------------------------------------------

    def _analyze_pair(
        self,
        source: SpatialNodeRef,
        target: SpatialNodeRef,
    ) -> None:

        a = source.node.bounds
        b = target.node.bounds

        distance = self._distance(a, b)

        # ------------------------------
        # Contains
        # ------------------------------

        if self._contains(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.CONTAINS,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.INSIDE,
                distance,
            )

        elif self._contains(b, a):

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.CONTAINS,
                distance,
            )

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.INSIDE,
                distance,
            )

        # ------------------------------
        # Intersections
        # ------------------------------

        if self._intersects(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.INTERSECTS,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.INTERSECTS,
                distance,
            )

        # ------------------------------
        # Overlap
        # ------------------------------

        overlap = self._overlap_area(a, b)

        if overlap > 0:

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.OVERLAPS,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.OVERLAPS,
                distance,
            )

        # ------------------------------
        # Touching
        # ------------------------------

        if self._touching(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.TOUCHING,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.TOUCHING,
                distance,
            )

        # ------------------------------
        # Relative Position
        # ------------------------------

        if self._left_of(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.LEFT_OF,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.RIGHT_OF,
                distance,
            )

        elif self._right_of(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.RIGHT_OF,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.LEFT_OF,
                distance,
            )

        if self._above(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.ABOVE,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.BELOW,
                distance,
            )

        elif self._below(a, b):

            self.add_edge(
                source.id,
                target.id,
                SpatialRelation.BELOW,
                distance,
            )

            self.add_edge(
                target.id,
                source.id,
                SpatialRelation.ABOVE,
                distance,
            )


    # ------------------------------------------------------
    # Relationship Queries
    # ------------------------------------------------------

    def find_by_relation(
        self,
        node_id: int,
        relation: SpatialRelation,
    ) -> List[SpatialNodeRef]:
        """
        Returns all nodes connected by a given relation.
        """

        result: List[SpatialNodeRef] = []

        for edge in self.outgoing(node_id):

            if edge.relation == relation:

                result.append(
                    self.nodes[edge.target]
                )

        return result

    # ------------------------------------------------------

    def parents_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:
        """
        Returns all parent nodes.
        """

        return self.find_by_relation(
            node_id,
            SpatialRelation.INSIDE,
        )

    # ------------------------------------------------------

    def children_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:
        """
        Returns all child nodes.
        """

        return self.find_by_relation(
            node_id,
            SpatialRelation.CONTAINS,
        )

    # ------------------------------------------------------

    def find_inside(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.INSIDE,
        )

    # ------------------------------------------------------

    def find_contains(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.CONTAINS,
        )

    # ------------------------------------------------------

    def find_left_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.LEFT_OF,
        )

    # ------------------------------------------------------

    def find_right_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.RIGHT_OF,
        )

    # ------------------------------------------------------

    def find_above(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.ABOVE,
        )

    # ------------------------------------------------------

    def find_below(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.BELOW,
        )

    # ------------------------------------------------------
    # Nearest Node
    # ------------------------------------------------------

    def find_nearest(
        self,
        node_id: int,
    ) -> Optional[SpatialNodeRef]:
        """
        Returns the nearest node to the given node.
        """

        nearest: Optional[SpatialNodeRef] = None

        nearest_distance = float("inf")

        for edge in self.outgoing(node_id):

            if edge.target == node_id:
                continue

            if edge.distance < nearest_distance:

                nearest_distance = edge.distance

                nearest = self.nodes[edge.target]

        return nearest

    # ------------------------------------------------------

    def nearest_distance(
        self,
        node_id: int,
    ) -> Optional[float]:
        """
        Returns distance to nearest node.
        """

        nearest = float("inf")

        found = False

        for edge in self.outgoing(node_id):

            if edge.target == node_id:
                continue

            found = True

            nearest = min(
                nearest,
                edge.distance,
            )

        if not found:
            return None

        return nearest


    # ------------------------------------------------------
    # Relationship Queries
    # ------------------------------------------------------

    def find_by_relation(
        self,
        node_id: int,
        relation: SpatialRelation,
    ) -> List[SpatialNodeRef]:
        """
        Returns all nodes connected by a given relation.
        """

        result: List[SpatialNodeRef] = []

        for edge in self.outgoing(node_id):

            if edge.relation == relation:

                result.append(
                    self.nodes[edge.target]
                )

        return result

    # ------------------------------------------------------

    def parents_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:
        """
        Returns all parent nodes.
        """

        return self.find_by_relation(
            node_id,
            SpatialRelation.INSIDE,
        )

    # ------------------------------------------------------

    def children_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:
        """
        Returns all child nodes.
        """

        return self.find_by_relation(
            node_id,
            SpatialRelation.CONTAINS,
        )

    # ------------------------------------------------------

    def find_inside(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.INSIDE,
        )

    # ------------------------------------------------------

    def find_contains(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.CONTAINS,
        )

    # ------------------------------------------------------

    def find_left_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.LEFT_OF,
        )

    # ------------------------------------------------------

    def find_right_of(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.RIGHT_OF,
        )

    # ------------------------------------------------------

    def find_above(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.ABOVE,
        )

    # ------------------------------------------------------

    def find_below(
        self,
        node_id: int,
    ) -> List[SpatialNodeRef]:

        return self.find_by_relation(
            node_id,
            SpatialRelation.BELOW,
        )

    # ------------------------------------------------------
    # Nearest Node
    # ------------------------------------------------------

    def find_nearest(
        self,
        node_id: int,
    ) -> Optional[SpatialNodeRef]:
        """
        Returns the nearest node to the given node.
        """

        nearest: Optional[SpatialNodeRef] = None

        nearest_distance = float("inf")

        for edge in self.outgoing(node_id):

            if edge.target == node_id:
                continue

            if edge.distance < nearest_distance:

                nearest_distance = edge.distance

                nearest = self.nodes[edge.target]

        return nearest

    # ------------------------------------------------------

    def nearest_distance(
        self,
        node_id: int,
    ) -> Optional[float]:
        """
        Returns distance to nearest node.
        """

        nearest = float("inf")

        found = False

        for edge in self.outgoing(node_id):

            if edge.target == node_id:
                continue

            found = True

            nearest = min(
                nearest,
                edge.distance,
            )

        if not found:
            return None

        return nearest