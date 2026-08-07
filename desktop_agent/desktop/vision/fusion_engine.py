"""
MYRAA Vision V3
Fusion Engine

Purpose
-------
Combines information from

- OCR
- Shape Detector
- Layout Analyzer

into a semantic representation of the screen.

This module DOES NOT perform OCR or detection itself.

Instead, it transforms low-level vision data into
high-level UI objects that the planner can reason about.

Author:
MYRAA Vision System
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from .layout_analyzer import (
    LayoutRegion,
    ScreenLayout,
    LayoutType,
    Rect,
)

from .shape_detector import ShapeCandidate

from .text_region import TextRegion


# ==========================================================
# Semantic Roles
# ==========================================================

class SemanticRole(str, Enum):

    UNKNOWN = "unknown"

    WINDOW = "window"

    PANEL = "panel"

    BUTTON = "button"

    ICON = "icon"

    IMAGE = "image"

    LABEL = "label"

    TEXT = "text"

    TEXTBOX = "textbox"

    CHECKBOX = "checkbox"

    RADIO = "radio"

    MENU = "menu"

    MENU_ITEM = "menu_item"

    TAB = "tab"

    TOOLBAR = "toolbar"

    SIDEBAR = "sidebar"

    HEADER = "header"

    STATUSBAR = "statusbar"

    LIST = "list"

    LIST_ITEM = "list_item"

    TREE = "tree"

    TREE_ITEM = "tree_item"

    TABLE = "table"

    CELL = "cell"

    LINK = "link"

    POPUP = "popup"

    DIALOG = "dialog"

    CONTENT = "content"


# ==========================================================
# Semantic Node
# ==========================================================

@dataclass(slots=True)
class SemanticNode:

    role: SemanticRole

    bounds: Rect

    confidence: float = 1.0

    text: str = ""

    layout: Optional[LayoutType] = None

    shape: Optional[ShapeCandidate] = None

    source_text: Optional[TextRegion] = None

    children: List["SemanticNode"] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    # --------------------------------------------------
    # NEW
    # --------------------------------------------------

    node_id: int = -1

    parent: Optional["SemanticNode"] = None

    merged: bool = False

    source: str = ""

    relations: Dict[str, List[int]] = field(
        default_factory=dict
    )

    @property
    def area(self):

        return self.bounds.area

    @property
    def center(self):

        return self.bounds.center

    def add_child(
        self,
        node: "SemanticNode",
    ):

        node.parent = self

        self.children.append(node)

    def __str__(self):

        return (

            f"{self.role.value}"

            f" "

            f"'{self.text}'"

            f" "

            f"({self.bounds.x},"

            f"{self.bounds.y},"

            f"{self.bounds.width},"

            f"{self.bounds.height})"

        )


# ==========================================================
# Semantic Screen
# ==========================================================

@dataclass(slots=True)
class SemanticScreen:

    width: int

    height: int

    nodes: List[SemanticNode]

    metadata: Dict[str, Any] = field(default_factory=dict)

    def find_role(

        self,

        role: SemanticRole,

    ) -> List[SemanticNode]:

        return [

            node

            for node in self.nodes

            if node.role == role

        ]

    def find_text(

        self,

        keyword: str,

    ) -> List[SemanticNode]:

        keyword = keyword.lower()

        return [

            node

            for node in self.nodes

            if keyword in node.text.lower()

        ]


# ==========================================================
# Configuration
# ==========================================================

@dataclass(slots=True)
class FusionConfig:

    minimum_confidence: float = 0.50

    merge_distance: int = 18

    text_margin: int = 8

    shape_margin: int = 8

    allow_duplicate_text: bool = False

    attach_text_to_shapes: bool = True

    attach_shapes_to_layout: bool = True


# ==========================================================
# Fusion Engine
# ==========================================================

class FusionEngine:

    """
    Vision Fusion Engine

    Receives

    OCR
    Shapes
    Layout

    Produces

    Semantic Screen
    """

    def __init__(

        self,

        config: Optional[FusionConfig] = None,

    ):

        self.config = config or FusionConfig()

        self._next_node_id = 0

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------

    def fuse(

        self,

        layout: ScreenLayout,

        text_regions: List[TextRegion],

        shapes: List[ShapeCandidate],

    ) -> SemanticScreen:

        """
        Main Fusion Pipeline

        Part 2 implements:

        - text fusion
        - shape fusion
        - layout fusion
        - semantic generation
        """

        layout_nodes = self._fuse_layout(layout)

        text_nodes = self._fuse_text(text_regions)

        text_nodes = self._remove_duplicate_text(
            text_nodes,
        )

        shape_nodes = self._fuse_shapes(shapes)

        self._merge_text_and_shapes(
            text_nodes,
            shape_nodes,
        )

        self._classify_shapes(
            shape_nodes,
        )

        self._promote_textboxes(
            shape_nodes,
        )

        self._associate_labels(
            text_nodes,
            shape_nodes,
        )

        self._attach_text_to_layout(
            layout_nodes,
            text_nodes,
        )

        self._attach_shapes_to_layout(
            layout_nodes,
            shape_nodes,
        )

        self._detect_menus(
            layout_nodes,
        )

        nodes = []

        nodes.extend(layout_nodes)

        nodes.extend(text_nodes)

        nodes.extend(shape_nodes)

        nodes = self._cleanup_nodes(
            nodes,
        )

        screen = SemanticScreen(

            width=layout.width,

            height=layout.height,

            nodes=nodes,

            metadata=self._build_metadata(
                nodes,
            ),

        )

        self._validate_screen(
            screen,
        )

        return screen


    # ------------------------------------------------------
    # Geometry Helpers
    # ------------------------------------------------------

    def _rect_from_text(
        self,
        text: TextRegion,
    ) -> Rect:

        return Rect(
            text.bounds.x,
            text.bounds.y,
            text.bounds.width,
            text.bounds.height,
        )

    def _rect_from_shape(
        self,
        shape: ShapeCandidate,
    ) -> Rect:

        return Rect(
            shape.bounds.x,
            shape.bounds.y,
            shape.bounds.width,
            shape.bounds.height,
        )

    def _contains(
        self,
        outer: Rect,
        inner: Rect,
    ) -> bool:

        return (
            outer.x <= inner.x
            and outer.y <= inner.y
            and outer.right >= inner.right
            and outer.bottom >= inner.bottom
        )

    def _distance(
        self,
        a: Rect,
        b: Rect,
    ) -> float:

        ax, ay = a.center
        bx, by = b.center

        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


    # ------------------------------------------------------
    # Node IDs
    # ------------------------------------------------------

    def _assign_node_id(
        self,
        node: SemanticNode,
    ):

        node.node_id = self._next_node_id

        self._next_node_id += 1

    # ------------------------------------------------------
    # Text -> Semantic Nodes
    # ------------------------------------------------------

    def _fuse_text(
        self,
        text_regions: List[TextRegion],
    ) -> List[SemanticNode]:

        nodes: List[SemanticNode] = []

        for text in text_regions:

            node = SemanticNode(

                role=SemanticRole.TEXT,

                bounds=self._rect_from_text(text),

                confidence=text.confidence,

                text=text.text,

                source_text=text,

            )

            node.source = "ocr"
            self._assign_node_id(node)

            nodes.append(node)

        return nodes

    # ------------------------------------------------------
    # Shape -> Semantic Nodes
    # ------------------------------------------------------

    def _fuse_shapes(
        self,
        shapes: List[ShapeCandidate],
    ) -> List[SemanticNode]:

        nodes: List[SemanticNode] = []

        for shape in shapes:

            node = SemanticNode(

                role=SemanticRole.UNKNOWN,

                bounds=self._rect_from_shape(shape),

                confidence=shape.confidence,

                shape=shape,

            )

            node.source = "shape"
            self._assign_node_id(node)

            nodes.append(node)

        return nodes

    # ------------------------------------------------------
    # Layout -> Semantic Nodes
    # ------------------------------------------------------

    def _fuse_layout(
        self,
        layout: ScreenLayout,
    ) -> List[SemanticNode]:

        nodes: List[SemanticNode] = []

        mapping = {

            LayoutType.HEADER: SemanticRole.HEADER,

            LayoutType.TOOLBAR: SemanticRole.TOOLBAR,

            LayoutType.SIDEBAR: SemanticRole.SIDEBAR,

            LayoutType.STATUSBAR: SemanticRole.STATUSBAR,

            LayoutType.CONTENT: SemanticRole.CONTENT,

            LayoutType.POPUP: SemanticRole.POPUP,

            LayoutType.DIALOG: SemanticRole.DIALOG,

            LayoutType.PANEL: SemanticRole.PANEL,

            LayoutType.NAVIGATION: SemanticRole.PANEL,

        }

        for region in layout.regions:

            role = mapping.get(

                region.layout_type,

                SemanticRole.UNKNOWN,

            )

            node = SemanticNode(

                role=role,

                bounds=region.bounds,

                confidence=region.confidence,

                layout=region.layout_type,

            )

            node.source = "layout"
            self._assign_node_id(node)

            nodes.append(node)

        return nodes

    # ------------------------------------------------------
    # Attach Text To Layout
    # ------------------------------------------------------

    def _attach_text_to_layout(
        self,
        layout_nodes: List[SemanticNode],
        text_nodes: List[SemanticNode],
    ):

        for text in text_nodes:

            for layout in layout_nodes:

                if self._contains(
                    layout.bounds,
                    text.bounds,
                ):

                    layout.add_child(text)

                    break

    # ------------------------------------------------------
    # Attach Shapes To Layout
    # ------------------------------------------------------

    def _attach_shapes_to_layout(
        self,
        layout_nodes: List[SemanticNode],
        shape_nodes: List[SemanticNode],
    ):

        for shape in shape_nodes:

            for layout in layout_nodes:

                if self._contains(
                    layout.bounds,
                    shape.bounds,
                ):

                    layout.add_child(shape)

                    break


    # ------------------------------------------------------
    # Geometry
    # ------------------------------------------------------

    def _overlap_ratio(
        self,
        a: Rect,
        b: Rect,
    ) -> float:

        left = max(a.x, b.x)
        top = max(a.y, b.y)
        right = min(a.right, b.right)
        bottom = min(a.bottom, b.bottom)

        if right <= left or bottom <= top:
            return 0.0

        intersection = (right - left) * (bottom - top)

        smaller = min(a.area, b.area)

        if smaller <= 0:
            return 0.0

        return intersection / smaller


    def _near(
        self,
        a: Rect,
        b: Rect,
    ) -> bool:

        return (
            self._distance(a, b)
            <= self.config.merge_distance
        )


    # ------------------------------------------------------
    # Merge Detection
    # ------------------------------------------------------

    def _should_merge(
        self,
        text: SemanticNode,
        shape: SemanticNode,
    ) -> bool:

        if self._contains(shape.bounds, text.bounds):
            return True

        if self._overlap_ratio(
            text.bounds,
            shape.bounds,
        ) > 0.40:
            return True

        if self._near(
            text.bounds,
            shape.bounds,
        ):
            return True

        return False


    # ------------------------------------------------------
    # Role Keywords
    # ------------------------------------------------------

    _BUTTON_WORDS = {
        "ok", "cancel", "save", "open", "close",
        "search", "submit", "login", "sign in",
        "continue", "next", "back", "apply",
        "finish", "yes", "no", "retry"
    }

    _LINK_WORDS = {
        "learn more",
        "forgot password",
        "privacy",
        "terms",
        "help",
        "details"
    }

    _TEXTBOX_HINTS = {
        "search",
        "username",
        "email",
        "password",
        "phone",
        "address"
    }

    _TAB_WORDS = {
        "home",
        "settings",
        "profile",
        "general",
        "advanced"
    }


    # ------------------------------------------------------
    # Role Inference
    # ------------------------------------------------------

    def _infer_role(
        self,
        text: SemanticNode,
        shape: SemanticNode,
    ) -> SemanticRole:

        value = text.text.lower().strip()

        # ---------------- Button ----------------

        if value in self._BUTTON_WORDS:
            return SemanticRole.BUTTON

        # ---------------- Link ----------------

        if value in self._LINK_WORDS:
            return SemanticRole.LINK

        # ---------------- Textbox ----------------

        if any(
            hint in value
            for hint in self._TEXTBOX_HINTS
        ):
            return SemanticRole.TEXTBOX

        # ---------------- Tab ----------------

        if value in self._TAB_WORDS:
            return SemanticRole.TAB

        # ---------------- Icon ----------------

        if (
            shape.bounds.width <= 40
            and shape.bounds.height <= 40
        ):
            return SemanticRole.ICON

        # ---------------- Image ----------------

        if (
            shape.bounds.width >= 100
            and shape.bounds.height >= 100
        ):
            return SemanticRole.IMAGE

        return SemanticRole.UNKNOWN


    # ------------------------------------------------------
    # Merge Text + Shapes
    # ------------------------------------------------------

    def _merge_text_and_shapes(
        self,
        text_nodes: List[SemanticNode],
        shape_nodes: List[SemanticNode],
    ) -> None:

        for shape in shape_nodes:

            for text in text_nodes:

                if not self._should_merge(
                    text,
                    shape,
                ):
                    continue

                shape.role = self._infer_role(
                    text,
                    shape,
                )

                shape.text = text.text

                shape.metadata["merged_from"] = text.node_id
                shape.source = "fusion"

                shape.source_text = text

                text.merged = True

                shape.confidence = self._fuse_confidence(
                    shape,
                    text,
                )               

                break


    # ------------------------------------------------------
    # Confidence Fusion
    # ------------------------------------------------------

    def _fuse_confidence(
        self,
        shape: SemanticNode,
        text: SemanticNode,
    ) -> float:
        """
        Combines OCR confidence and shape confidence into a single score.
        """

        shape_conf = max(0.0, min(shape.confidence, 1.0))
        text_conf = max(0.0, min(text.confidence, 1.0))

        # Weighted average
        confidence = (shape_conf * 0.4) + (text_conf * 0.6)

        return min(confidence, 1.0)


    # ------------------------------------------------------
    # Label Association
    # ------------------------------------------------------

    def _associate_labels(
        self,
        text_nodes: List[SemanticNode],
        shape_nodes: List[SemanticNode],
    ) -> None:
        """
        Associates nearby text labels with textbox shapes.
        """

        for shape in shape_nodes:

            if shape.role != SemanticRole.TEXTBOX:
                continue

            best = None
            best_distance = float("inf")

            for text in text_nodes:

                if not text.text.strip():
                    continue

                # Labels are usually left or above the textbox
                if (
                    text.bounds.right <= shape.bounds.right
                    and text.bounds.bottom <= shape.bounds.bottom + 25
                ):

                    distance = self._distance(
                        text.bounds,
                        shape.bounds,
                    )

                    if distance < best_distance:
                        best_distance = distance
                        best = text

            if best:

                shape.metadata["label"] = best.text

                shape.add_child(best)


    # ------------------------------------------------------
    # Duplicate Removal
    # ------------------------------------------------------

    def _remove_duplicate_text(
        self,
        text_nodes: List[SemanticNode],
    ) -> List[SemanticNode]:

        unique = []

        for node in text_nodes:

            duplicate = False

            for existing in unique:

                if (
                    node.text == existing.text
                    and self._overlap_ratio(
                        node.bounds,
                        existing.bounds,
                    ) > 0.80
                ):
                    duplicate = True
                    break

            if not duplicate:
                unique.append(node)

        return unique



    # ------------------------------------------------------
    # Shape Classification
    # ------------------------------------------------------

    def _classify_shapes(
        self,
        shape_nodes: List[SemanticNode],
    ) -> None:

        for node in shape_nodes:

            if node.role != SemanticRole.UNKNOWN:
                continue

            shape = node.shape

            if shape is None:
                continue

            kind = shape.shape.lower()

            w = node.bounds.width
            h = node.bounds.height

            # ---------------- Checkbox ----------------

            if (
                kind in ("square", "rectangle")
                and 12 <= w <= 35
                and 12 <= h <= 35
            ):
                node.role = SemanticRole.CHECKBOX
                continue

            # ---------------- Radio ----------------

            if (
                kind == "circle"
                and 12 <= w <= 35
                and 12 <= h <= 35
            ):
                node.role = SemanticRole.RADIO
                continue

            # ---------------- Icon ----------------

            if (
                max(w, h) <= 48
            ):
                node.role = SemanticRole.ICON
                continue

            # ---------------- Image ----------------

            if (
                w >= 100
                and h >= 100
                and not node.text
            ):
                node.role = SemanticRole.IMAGE

            if (
                node.role == SemanticRole.UNKNOWN
                and node.text
            ):
                node.role = SemanticRole.LABEL


    # ------------------------------------------------------
    # Menu Detection
    # ------------------------------------------------------

    def _detect_menus(
        self,
        layout_nodes: List[SemanticNode],
    ) -> None:

        for layout in layout_nodes:

            if layout.role != SemanticRole.TOOLBAR:
                continue

            buttons = [

                child

                for child in layout.children

                if child.role in (

                    SemanticRole.BUTTON,

                    SemanticRole.ICON,

                )

            ]

            if len(buttons) >= 3:

                layout.role = SemanticRole.MENU


    # ------------------------------------------------------
    # Promote Textboxes
    # ------------------------------------------------------

    def _promote_textboxes(
        self,
        shape_nodes: List[SemanticNode],
    ) -> None:

        for node in shape_nodes:

            if node.role != SemanticRole.UNKNOWN:
                continue

            if not node.text:
                continue

            text = node.text.lower()

            if any(

                word in text

                for word in (

                    "search",

                    "username",

                    "email",

                    "password",

                )

            ):

                node.role = SemanticRole.TEXTBOX


    # ------------------------------------------------------
    # Semantic Cleanup
    # ------------------------------------------------------

    def _cleanup_nodes(
        self,
        nodes: List[SemanticNode],
    ) -> List[SemanticNode]:
        """
        Remove invalid semantic nodes and normalize values.
        """

        cleaned: List[SemanticNode] = []

        for node in nodes:

            if node.bounds.width <= 0:
                continue

            if node.bounds.height <= 0:
                continue

            node.text = node.text.strip()

            if node.confidence < 0:
                node.confidence = 0.0

            if node.confidence > 1:
                node.confidence = 1.0

            if (
                node.role == SemanticRole.TEXT
                and node.merged
            ):
                continue

            cleaned.append(node)

        return cleaned

    # ------------------------------------------------------
    # Validation
    # ------------------------------------------------------

    def _validate_screen(
        self,
        screen: SemanticScreen,
    ) -> None:
        """
        Validate semantic screen consistency.
        """

        for node in screen.nodes:

            if node.role is None:

                raise ValueError(
                    "Semantic node without role."
                )

            if node.bounds.width <= 0:

                raise ValueError(
                    "Invalid node width."
                )

            if node.bounds.height <= 0:

                raise ValueError(
                    "Invalid node height."
                )

    # ------------------------------------------------------
    # Statistics
    # ------------------------------------------------------

    def _build_statistics(
        self,
        nodes: List[SemanticNode],
    ) -> Dict[str, int]:

        stats: Dict[str, int] = {}

        for node in nodes:

            key = node.role.value

            stats[key] = stats.get(
                key,
                0,
            ) + 1

        return stats


    # ------------------------------------------------------
    # Metadata
    # ------------------------------------------------------

    def _build_metadata(
        self,
        nodes: List[SemanticNode],
    ) -> Dict[str, object]:

        return {

            "node_count": len(nodes),

            "statistics": self._build_statistics(
                nodes
            ),

            "buttons": sum(
                1
                for n in nodes
                if n.role == SemanticRole.BUTTON
            ),

            "textboxes": sum(
                1
                for n in nodes
                if n.role == SemanticRole.TEXTBOX
            ),

            "images": sum(
                1
                for n in nodes
                if n.role == SemanticRole.IMAGE
            ),

            "icons": sum(
                1
                for n in nodes
                if n.role == SemanticRole.ICON
            ),
        }