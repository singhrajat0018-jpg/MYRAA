"""
MYRAA Vision V3

Vision Context

Central container shared between

- Fusion Engine
- Spatial Graph
- Semantic Tree
- Screen Analyzer
- Planner

Author
------
MYRAA Vision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from .fusion_engine import SemanticScreen
from .spatial_graph import SpatialGraph
from .semantic_tree import SemanticTree


# ==========================================================
# Vision Context
# ==========================================================

@dataclass(slots=True)
class VisionContext:

    screen: SemanticScreen

    graph: SpatialGraph

    tree: SemanticTree

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def width(self):

        return self.screen.width

    @property
    def height(self):

        return self.screen.height

    @property
    def nodes(self):

        return self.screen.nodes

    @property
    def node_count(self):

        return len(self.screen.nodes)



# ==========================================================
# Vision Context Builder
# ==========================================================

from .fusion_engine import (
    FusionEngine,
    FusionConfig,
)

from .spatial_graph import SpatialGraph

from .semantic_tree import SemanticTree

from .layout_analyzer import ScreenLayout

from .shape_detector import ShapeCandidate

from .text_region import TextRegion


class VisionContextBuilder:

    """
    Complete Vision Pipeline

    Layout
        ↓
    Fusion
        ↓
    Spatial Graph
        ↓
    Semantic Tree
        ↓
    Vision Context
    """

    def __init__(

        self,

        fusion: Optional[FusionEngine] = None,

    ):

        self.fusion = fusion or FusionEngine()

    # ------------------------------------------------------

    def build(

        self,

        layout: ScreenLayout,

        text_regions: list[TextRegion],

        shapes: list[ShapeCandidate],

    ) -> VisionContext:

        # ----------------------------------------------
        # Fusion
        # ----------------------------------------------

        screen = self.fusion.fuse(

            layout,

            text_regions,

            shapes,

        )

        # ----------------------------------------------
        # Spatial Graph
        # ----------------------------------------------

        graph = SpatialGraph.from_nodes(

            screen.nodes

        )

        # ----------------------------------------------
        # Semantic Tree
        # ----------------------------------------------

        tree = SemanticTree()

        tree.build(graph)

        # ----------------------------------------------
        # Final Context
        # ----------------------------------------------

        return VisionContext(

            screen=screen,

            graph=graph,

            tree=tree,

        )