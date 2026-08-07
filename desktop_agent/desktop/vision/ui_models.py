"""
MYRAA Desktop Control V3

UI Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class UIElementType(str, Enum):

    UNKNOWN = "unknown"

    TEXT = "text"

    BUTTON = "button"

    TEXTBOX = "textbox"

    CHECKBOX = "checkbox"

    RADIO = "radio"

    DROPDOWN = "dropdown"

    ICON = "icon"

    IMAGE = "image"

    MENU = "menu"

    TOOLBAR = "toolbar"

    WINDOW = "window"

    LABEL = "label"

    LINK = "link"


@dataclass(slots=True)
class BoundingBox:

    x: int

    y: int

    width: int

    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (
            self.x + self.width // 2,
            self.y + self.height // 2,
        )


@dataclass(slots=True)
class UIElement:

    type: UIElementType

    text: str

    confidence: float

    bounds: BoundingBox

    clickable: bool = False

    enabled: bool = True

    visible: bool = True

    metadata: dict = field(default_factory=dict)