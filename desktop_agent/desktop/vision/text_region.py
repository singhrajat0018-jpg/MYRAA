"""
MYRAA Desktop Control V3

Text Region Models
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ui_models import BoundingBox


@dataclass(slots=True)
class TextRegion:
    """
    Represents a merged OCR text region.
    """

    text: str

    confidence: float

    bounds: BoundingBox

    words: list[str] = field(default_factory=list)

    line: int = 0

    paragraph: int = 0

    metadata: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:

        return self.bounds.center

    @property
    def right(self) -> int:

        return self.bounds.right

    @property
    def bottom(self) -> int:

        return self.bounds.bottom

    @property
    def area(self) -> int:

        return self.bounds.width * self.bounds.height

    