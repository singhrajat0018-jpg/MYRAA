"""
MYRAA Vision V3

Semantic Tree

Builds a hierarchical UI tree from a SpatialGraph.

Author
------
MYRAA Vision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .fusion_engine import SemanticNode
from .spatial_graph import (
    SpatialGraph,
    SpatialRelation,
)


# ==========================================================
# Tree Node
# ==========================================================

@dataclass(slots=True)
class TreeNode:

    node: SemanticNode

    parent: Optional["TreeNode"] = None

    children: List["TreeNode"] = field(default_factory=list)

    depth: int = 0

    def add_child(
        self,
        child: "TreeNode",
    ):

        child.parent = self

        child.depth = self.depth + 1

        self.children.append(child)

    @property
    def is_root(self):

        return self.parent is None

    @property
    def is_leaf(self):

        return len(self.children) == 0


# ==========================================================
# Semantic Tree
# ==========================================================

class SemanticTree:

    def __init__(self):

        self.roots: List[TreeNode] = []

        self.nodes: List[TreeNode] = []

    def clear(self):

        self.roots.clear()

        self.nodes.clear()

    def __len__(self):

        return len(self.nodes)


    # ------------------------------------------------------
    # Build Tree
    # ------------------------------------------------------

    def build(
        self,
        graph: SpatialGraph,
    ) -> None:
        """
        Builds a semantic hierarchy from the spatial graph.
        """

        self.clear()

        # ----------------------------------------------
        # Create TreeNode objects
        # ----------------------------------------------

        node_map = {}

        for graph_node in graph.all_nodes():

            tree_node = TreeNode(
                node=graph_node.node,
            )

            node_map[graph_node.id] = tree_node

            self.nodes.append(tree_node)

        # ----------------------------------------------
        # Build parent-child relationships
        # ----------------------------------------------

        for graph_node in graph.all_nodes():

            current = node_map[graph_node.id]

            parents = graph.find_by_relation(
                graph_node.id,
                SpatialRelation.INSIDE,
            )

            if not parents:

                self.roots.append(current)

                continue

            parent = self._nearest_parent(
                graph,
                graph_node.id,
                parents,
            )

            if parent is None:

                self.roots.append(current)

                continue

            parent_node = node_map[parent.id]

            parent_node.add_child(current)

    # ------------------------------------------------------
    # Parent Selection
    # ------------------------------------------------------

    def _nearest_parent(
        self,
        graph: SpatialGraph,
        node_id: int,
        parents,
    ):
        """
        Select the smallest container as parent.
        """

        best = None

        smallest_area = float("inf")

        for parent in parents:

            area = parent.node.bounds.area

            if area < smallest_area:

                smallest_area = area

                best = parent

        return best

    # ------------------------------------------------------
    # Root Nodes
    # ------------------------------------------------------

    def root_nodes(
        self,
    ) -> List[TreeNode]:

        return self.roots



    # ------------------------------------------------------
    # Tree Traversal
    # ------------------------------------------------------

    def walk(self):
        """
        Depth-first traversal of the semantic tree.
        """

        for root in self.roots:

            yield from self._walk(root)

    def _walk(
        self,
        node: TreeNode,
    ):

        yield node

        for child in node.children:

            yield from self._walk(child)

    # ------------------------------------------------------
    # Search Helpers
    # ------------------------------------------------------

    def find_role(
        self,
        role,
    ) -> List[TreeNode]:
        """
        Returns all nodes with the given semantic role.
        """

        result = []

        for node in self.walk():

            if node.node.role == role:

                result.append(node)

        return result

    # ------------------------------------------------------

    def find_text(
        self,
        keyword: str,
    ) -> List[TreeNode]:
        """
        Case-insensitive text search.
        """

        keyword = keyword.lower()

        result = []

        for node in self.walk():

            if keyword in node.node.text.lower():

                result.append(node)

        return result

    # ------------------------------------------------------

    def find_depth(
        self,
        depth: int,
    ) -> List[TreeNode]:
        """
        Returns every node at the specified depth.
        """

        result = []

        for node in self.walk():

            if node.depth == depth:

                result.append(node)

        return result

    # ------------------------------------------------------

    def leaf_nodes(
        self,
    ) -> List[TreeNode]:
        """
        Returns all leaf nodes.
        """

        return [

            node

            for node in self.walk()

            if node.is_leaf

        ]

    # ------------------------------------------------------

    def parent_of(
        self,
        node: TreeNode,
    ) -> Optional[TreeNode]:

        return node.parent

    # ------------------------------------------------------

    def children_of(
        self,
        node: TreeNode,
    ) -> List[TreeNode]:

        return node.children



    # ------------------------------------------------------
    # Tree Statistics
    # ------------------------------------------------------

    def node_count(self) -> int:
        """
        Total number of tree nodes.
        """

        return len(self.nodes)

    # ------------------------------------------------------

    def max_depth(self) -> int:
        """
        Returns maximum tree depth.
        """

        if not self.nodes:
            return 0

        return max(
            node.depth
            for node in self.nodes
        )

    # ------------------------------------------------------

    def statistics(self) -> dict:
        """
        Returns tree statistics.
        """

        return {

            "roots": len(self.roots),

            "nodes": self.node_count(),

            "max_depth": self.max_depth(),

            "leaf_nodes": len(
                self.leaf_nodes()
            ),

        }

    # ------------------------------------------------------
    # Serialization
    # ------------------------------------------------------

    def to_dict(self) -> list:
        """
        Converts the tree into a nested dictionary.
        """

        return [

            self._node_to_dict(root)

            for root in self.roots

        ]

    # ------------------------------------------------------

    def _node_to_dict(
        self,
        node: TreeNode,
    ) -> dict:

        return {

            "role": node.node.role.value,

            "text": node.node.text,

            "bounds": {

                "x": node.node.bounds.x,

                "y": node.node.bounds.y,

                "width": node.node.bounds.width,

                "height": node.node.bounds.height,

            },

            "confidence": node.node.confidence,

            "depth": node.depth,

            "children": [

                self._node_to_dict(child)

                for child in node.children

            ],

        }

    # ------------------------------------------------------
    # Debug Printing
    # ------------------------------------------------------

    def print_tree(self) -> None:
        """
        Pretty-prints the semantic tree.
        """

        for root in self.roots:

            self._print_node(root)

    # ------------------------------------------------------

    def _print_node(
        self,
        node: TreeNode,
    ) -> None:

        indent = "    " * node.depth

        label = node.node.role.value

        if node.node.text:

            label += f" : {node.node.text}"

        print(f"{indent}- {label}")

        for child in node.children:

            self._print_node(child)