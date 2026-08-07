"""
MYRAA Desktop Vision V3

Layout Analyzer

Responsibilities
----------------
- Screen layout understanding
- Detect major UI regions
- Geometry utilities
- Region models

NOTE:
Detection algorithms are implemented in Part 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .shape_detector import ShapeCandidate
from .text_region import TextRegion


# =====================================================
# Layout Types
# =====================================================

class LayoutType(str, Enum):

    UNKNOWN = "unknown"

    HEADER = "header"

    TOOLBAR = "toolbar"

    SIDEBAR = "sidebar"

    CONTENT = "content"

    STATUSBAR = "statusbar"

    FOOTER = "footer"

    POPUP = "popup"

    DIALOG = "dialog"

    PANEL = "panel"

    NAVIGATION = "navigation"


# =====================================================
# Rectangle
# =====================================================

@dataclass(slots=True)
class Rect:

    x: int

    y: int

    width: int

    height: int

    @property
    def right(self):

        return self.x + self.width

    @property
    def bottom(self):

        return self.y + self.height

    @property
    def area(self):

        return self.width * self.height

    @property
    def center(self):

        return (

            self.x + self.width / 2,

            self.y + self.height / 2,

        )


# =====================================================
# Layout Region
# =====================================================

@dataclass(slots=True)
class LayoutRegion:

    layout_type: LayoutType

    bounds: Rect

    confidence: float = 1.0

    texts: List[TextRegion] = field(default_factory=list)

    shapes: List[ShapeCandidate] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)

    def __str__(self):

        return (

            f"{self.layout_type.value}"

            f" "

            f"({self.bounds.x},"

            f"{self.bounds.y},"

            f"{self.bounds.width},"

            f"{self.bounds.height})"

        )


# =====================================================
# Screen Layout
# =====================================================

@dataclass(slots=True)
class ScreenLayout:

    width: int

    height: int

    regions: List[LayoutRegion]

    metadata: dict = field(default_factory=dict)

    def by_type(

        self,

        layout_type: LayoutType,

    ) -> List[LayoutRegion]:

        return [

            r

            for r in self.regions

            if r.layout_type == layout_type

        ]


# =====================================================
# Configuration
# =====================================================

@dataclass(slots=True)
class LayoutConfig:

    minimum_region_area: int = 3000

    minimum_confidence: float = 0.50

    merge_gap: int = 15

    edge_margin: int = 20

    sidebar_ratio: float = 0.25

    header_ratio: float = 0.15

    footer_ratio: float = 0.10

    popup_ratio: float = 0.60


# =====================================================
# Layout Analyzer
# =====================================================

class LayoutAnalyzer:

   

    def __init__(
        self,
        config: LayoutConfig | None = None,
    ):
        self.config = config or LayoutConfig()

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------

    def analyze(

        self,

        image,

        text_regions: List[TextRegion],

        shapes: List[ShapeCandidate],

    ) -> ScreenLayout:

        """
        Main layout pipeline.

        Detection logic is implemented in Part 2.
        """

        height, width = image.shape[:2]

        regions = self._detect_regions(

            width,

            height,

            text_regions,

            shapes,

        )

        layout = ScreenLayout(

            width=width,

            height=height,

            regions=regions,

        )

        self._assign_text(

            layout,

            text_regions,

        )

        self._assign_shapes(

            layout,

            shapes,

        )



        h, w = image.shape[:2]

        regions = [

            self._header(image),

            self._sidebar(image),

            self._content(image),

            self._footer(image),

        ]

        return ScreenLayout(

            width=w,

            height=h,

            regions=regions,

    )

              
    # -------------------------------------------------
    # Geometry Helpers
    # -------------------------------------------------

    def _intersects(

        self,

        a: Rect,

        b: Rect,

    ) -> bool:

        return not (

            a.right < b.x

            or

            b.right < a.x

            or

            a.bottom < b.y

            or

            b.bottom < a.y

        )

    def _contains(

        self,

        outer: Rect,

        inner: Rect,

    ) -> bool:

        return (

            outer.x <= inner.x

            and

            outer.y <= inner.y

            and

            outer.right >= inner.right

            and

            outer.bottom >= inner.bottom

        )

    def _union(

        self,

        a: Rect,

        b: Rect,

    ) -> Rect:

        left = min(a.x, b.x)

        top = min(a.y, b.y)

        right = max(a.right, b.right)

        bottom = max(a.bottom, b.bottom)

        return Rect(

            left,

            top,

            right - left,

            bottom - top,

        )

    def _distance(

        self,

        a: Rect,

        b: Rect,

    ) -> float:

        ax, ay = a.center

        bx, by = b.center

        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _near_edge(

        self,

        rect: Rect,

        width: int,

        height: int,

    ) -> bool:

        margin = self.config.edge_margin

        return (

            rect.x <= margin

            or

            rect.y <= margin

            or

            rect.right >= width - margin

            or

            rect.bottom >= height - margin

        )


    # -------------------------------------------------
    # Region Detection Pipeline
    # -------------------------------------------------

    def _detect_regions(

        self,

        width: int,

        height: int,

        text_regions: List[TextRegion],

        shapes: List[ShapeCandidate],

    ) -> List[LayoutRegion]:

        regions: List[LayoutRegion] = []

        header = self._detect_header(width, height)
        if header:
            regions.append(header)

        sidebar = self._detect_sidebar(width, height)
        if sidebar:
            regions.append(sidebar)

        footer = self._detect_footer(width, height)
        if footer:
            regions.append(footer)

        content = self._detect_content(
            width,
            height,
            header,
            sidebar,
            footer,
        )

        if content:
            regions.append(content)

        toolbar = self._detect_toolbar(

            width,

            height,

            header,

        )

        if toolbar:

            regions.append(toolbar)

        popup = self._detect_popup(

            width,

            height,

            shapes,

        )

        if popup:

            regions.append(popup)

        dialog = self._detect_dialog(

            width,

            height,

            shapes,

        )

        if dialog:

            regions.append(dialog)

        regions = self._merge_regions(regions)

        regions = self._filter_regions(regions)

        return regions      

    # -------------------------------------------------
    # Header
    # -------------------------------------------------

    def _detect_header(

        self,

        width: int,

        height: int,

    ) -> LayoutRegion:

        header_height = int(
            height * self.config.header_ratio
        )

        return LayoutRegion(

            layout_type=LayoutType.HEADER,

            bounds=Rect(

                0,

                0,

                width,

                header_height,

            ),

            confidence=0.80,

        )

    # -------------------------------------------------
    # Sidebar
    # -------------------------------------------------

    def _detect_sidebar(

        self,

        width: int,

        height: int,

    ) -> LayoutRegion:

        sidebar_width = int(
            width * self.config.sidebar_ratio
        )

        return LayoutRegion(

            layout_type=LayoutType.SIDEBAR,

            bounds=Rect(

                0,

                0,

                sidebar_width,

                height,

            ),

            confidence=0.70,

        )

    # -------------------------------------------------
    # Footer
    # -------------------------------------------------

    def _detect_footer(

        self,

        width: int,

        height: int,

    ) -> LayoutRegion:

        footer_height = int(
            height * self.config.footer_ratio
        )

        return LayoutRegion(

            layout_type=LayoutType.STATUSBAR,

            bounds=Rect(

                0,

                height - footer_height,

                width,

                footer_height,

            ),

            confidence=0.75,

        )

    # -------------------------------------------------
    # Content
    # -------------------------------------------------

    def _detect_content(

        self,

        width: int,

        height: int,

        header: LayoutRegion | None,

        sidebar: LayoutRegion | None,

        footer: LayoutRegion | None,

    ) -> LayoutRegion:

        left = 0
        top = 0
        right = width
        bottom = height

        if sidebar:

            left = sidebar.bounds.right

        if header:

            top = header.bounds.bottom

        if footer:

            bottom = footer.bounds.y

        return LayoutRegion(

            layout_type=LayoutType.CONTENT,

            bounds=Rect(

                left,

                top,

                right - left,

                bottom - top,

            ),

            confidence=0.90,

        )

    # -------------------------------------------------
    # Attach OCR Regions
    # -------------------------------------------------

    def _assign_text(

        self,

        layout: ScreenLayout,

        text_regions: List[TextRegion],

    ):

        for text in text_regions:

            bounds = Rect(

                text.bounds.x,

                text.bounds.y,

                text.bounds.width,

                text.bounds.height,

            )

            for region in layout.regions:

                if self._contains(

                    region.bounds,

                    bounds,

                ):

                    region.texts.append(text)

                    break

    # -------------------------------------------------
    # Attach Shapes
    # -------------------------------------------------

    def _assign_shapes(

        self,

        layout: ScreenLayout,

        shapes: List[ShapeCandidate],

    ):

        for shape in shapes:

            bounds = Rect(

                shape.bounds.x,

                shape.bounds.y,

                shape.bounds.width,

                shape.bounds.height,

            )

            for region in layout.regions:

                if self._contains(

                    region.bounds,

                    bounds,

                ):

                    region.shapes.append(shape)

                    break


    # -------------------------------------------------
    # Toolbar Detection
    # -------------------------------------------------

    def _detect_toolbar(

        self,

        width: int,

        height: int,

        header: LayoutRegion | None,

    ) -> LayoutRegion | None:

        if header is None:

            return None

        toolbar_height = max(
            40,
            int(height * 0.05),
        )

        return LayoutRegion(

            layout_type=LayoutType.TOOLBAR,

            bounds=Rect(

                0,

                header.bounds.bottom,

                width,

                toolbar_height,

            ),

            confidence=0.65,

        )

    # -------------------------------------------------
    # Popup Detection
    # -------------------------------------------------

    def _detect_popup(

        self,

        width: int,

        height: int,

        shapes: List[ShapeCandidate],

    ) -> LayoutRegion | None:

        minimum_area = (

            width

            * height

            * self.config.popup_ratio

        )

        for shape in shapes:

            area = (

                shape.bounds.width

                * shape.bounds.height

            )

            if area >= minimum_area:

                return LayoutRegion(

                    layout_type=LayoutType.POPUP,

                    bounds=Rect(

                        shape.bounds.x,

                        shape.bounds.y,

                        shape.bounds.width,

                        shape.bounds.height,

                    ),

                    confidence=shape.confidence,

                )

        return None

    # -------------------------------------------------
    # Dialog Detection
    # -------------------------------------------------

    def _detect_dialog(

        self,

        width: int,

        height: int,

        shapes: List[ShapeCandidate],

    ) -> LayoutRegion | None:

        center_x = width / 2

        center_y = height / 2

        tolerance = 120

        for shape in shapes:

            cx = (

                shape.bounds.x

                + shape.bounds.width / 2

            )

            cy = (

                shape.bounds.y

                + shape.bounds.height / 2

            )

            if (

                abs(cx - center_x)

                < tolerance

                and

                abs(cy - center_y)

                < tolerance

            ):

                return LayoutRegion(

                    layout_type=LayoutType.DIALOG,

                    bounds=Rect(

                        shape.bounds.x,

                        shape.bounds.y,

                        shape.bounds.width,

                        shape.bounds.height,

                    ),

                    confidence=shape.confidence,

                )

        return None

    # -------------------------------------------------
    # Merge Duplicate Regions
    # -------------------------------------------------

    def _merge_regions(

        self,

        regions: List[LayoutRegion],

    ) -> List[LayoutRegion]:

        merged: List[LayoutRegion] = []

        for region in regions:

            duplicate = False

            for existing in merged:

                if (

                    existing.layout_type

                    == region.layout_type

                ):

                    if self._intersects(

                        existing.bounds,

                        region.bounds,

                    ):

                        existing.bounds = self._union(

                            existing.bounds,

                            region.bounds,

                        )

                        existing.confidence = max(

                            existing.confidence,

                            region.confidence,

                        )

                        duplicate = True

                        break

            if not duplicate:

                merged.append(region)

        return merged

    # -------------------------------------------------
    # Remove Tiny Regions
    # -------------------------------------------------

    def _filter_regions(

        self,

        regions: List[LayoutRegion],

    ) -> List[LayoutRegion]:

        output = []

        for region in regions:

            if (

                region.bounds.area

                >= self.config.minimum_region_area

            ):

                output.append(region)

        return output

    # -------------------------------------------------
    # Visualization Support
    # -------------------------------------------------

    def draw_layout(

        self,

        image,

        layout: ScreenLayout,

    ):

        import cv2

        output = image.copy()

        for region in layout.regions:

            cv2.rectangle(

                output,

                (

                    region.bounds.x,

                    region.bounds.y,

                ),

                (

                    region.bounds.right,

                    region.bounds.bottom,

                ),

                (0, 255, 255),

                2,

            )

            cv2.putText(

                output,

                region.layout_type.value,

                (

                    region.bounds.x,

                    max(

                        20,

                        region.bounds.y - 5,

                    ),

                ),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.6,

                (0, 255, 255),

                2,

            )

        return output

    def _screen_rect(self, image):

        h, w = image.shape[:2]

        return Rect(
            x=0,
            y=0,
            width=w,
            height=h,
        )

    def _header(self, image):

        h, w = image.shape[:2]

        return LayoutRegion(
            layout_type=LayoutType.HEADER,
            bounds=Rect(
                0,
                0,
                w,
                int(h * self.config.header_ratio),
            ),
        )

    def _footer(self, image):

        h, w = image.shape[:2]

        height = int(h * self.config.footer_ratio)

        return LayoutRegion(
            layout_type=LayoutType.FOOTER,
            bounds=Rect(
                0,
                h - height,
                w,
                height,
            ),
        )

    def _sidebar(self, image):

        h, w = image.shape[:2]

        width = int(w * self.config.sidebar_ratio)

        return LayoutRegion(
            layout_type=LayoutType.SIDEBAR,
            bounds=Rect(
                0,
                0,
                width,
                h,
            ),
        )

    def _content(self, image):

        h, w = image.shape[:2]

        sidebar = int(w * self.config.sidebar_ratio)

        header = int(h * self.config.header_ratio)

        footer = int(h * self.config.footer_ratio)

        return LayoutRegion(
            layout_type=LayoutType.CONTENT,
            bounds=Rect(
                sidebar,
                header,
                w - sidebar,
                h - header - footer,
            ),
        )