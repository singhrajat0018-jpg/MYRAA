"""
MYRAA Desktop Control V3

UI Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InteractiveType(str, Enum):
    """Types of interactive elements."""
    NONE = "none"
    BUTTON = "button"
    INPUT = "input"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    LINK = "link"
    MENU_ITEM = "menu_item"
    TAB = "tab"
    DROPDOWN = "dropdown"


class UIElementType(str, Enum):

    UNKNOWN = "unknown"

    TEXT = "text"

    BUTTON = "button"

    TEXTBOX = "textbox"

    TEXTAREA = "textarea"

    CHECKBOX = "checkbox"

    RADIO = "radio"

    DROPDOWN = "dropdown"

    ICON = "icon"

    IMAGE = "image"

    MENU = "menu"

    MENU_ITEM = "menu_item"

    TAB = "tab"

    TOOLBAR = "toolbar"

    WINDOW = "window"

    LABEL = "label"

    LINK = "link"

    PANEL = "panel"

    HEADER = "header"

    STATUSBAR = "statusbar"

    SIDEBAR = "sidebar"

    LIST = "list"

    LIST_ITEM = "list_item"

    TREE = "tree"

    TREE_ITEM = "tree_item"

    TABLE = "table"

    CELL = "cell"

    POPUP = "popup"

    DIALOG = "dialog"

    CONTENT = "content"

    PLAYER_CONTROL = "player_control"

    SCROLL_REGION = "scroll_region"

    VIDEO = "video"


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

    def contains(self, other: 'BoundingBox') -> bool:
        """Check if this bounding box completely contains another bounding box."""
        return (self.x <= other.x and
                self.y <= other.y and
                self.right >= other.right and
                self.bottom >= other.bottom)

    def contains_point(self, point: tuple[int, int]) -> bool:
        """Check if this bounding box contains a point."""
        x, y = point
        return (self.x <= x <= self.right and
                self.y <= y <= self.bottom)


@dataclass(slots=True)
class UIElement:
    id: int
    type: UIElementType
    text: str
    confidence: float
    bounds: BoundingBox
    clickable: bool = False
    enabled: bool = True
    visible: bool = True
    interactive: InteractiveType = field(init=False)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Set interactive type based on UI element type."""
        interactive_mapping = {
            UIElementType.BUTTON: InteractiveType.BUTTON,
            UIElementType.TEXTBOX: InteractiveType.INPUT,
            UIElementType.TEXTAREA: InteractiveType.INPUT,
            UIElementType.CHECKBOX: InteractiveType.CHECKBOX,
            UIElementType.RADIO: InteractiveType.RADIO,
            UIElementType.DROPDOWN: InteractiveType.DROPDOWN,
            UIElementType.LINK: InteractiveType.LINK,
            UIElementType.MENU_ITEM: InteractiveType.MENU_ITEM,
            UIElementType.TAB: InteractiveType.TAB,
        }
        self.interactive = interactive_mapping.get(self.type, InteractiveType.NONE)

    @property
    def center(self) -> tuple[int, int]:
        """Calculate center point from bounds."""
        return self.bounds.center