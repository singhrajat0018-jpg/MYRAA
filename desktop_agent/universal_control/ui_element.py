"""Universal UI element — thin adapter over existing vision UIElement.

Consume the live VisualState from ContinuousVisionController.
This module provides a universal element format that bridges the existing
vision pipeline's UIElement/ui_targets to the universal control layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ElementType(Enum):
    BUTTON = "button"
    TEXT_FIELD = "text_field"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    LINK = "link"
    TAB = "tab"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    ICON = "icon"
    SLIDER = "slider"
    TOGGLE = "toggle"
    TABLE = "table"
    LIST_ITEM = "list_item"
    IMAGE = "image"
    TEXT_LABEL = "text_label"
    PANEL = "panel"
    DIALOG = "dialog"
    TOOLBAR = "toolbar"
    TREE = "tree"
    TREE_ITEM = "tree_item"
    UNKNOWN = "unknown"


class InteractiveRole(Enum):
    PRIMARY_ACTION = "primary_action"
    SECONDARY_ACTION = "secondary_action"
    NAVIGATION = "navigation"
    INPUT = "input"
    TOGGLE = "toggle"
    DESTRUCTIVE = "destructive"
    INFORMATIONAL = "informational"
    NONE = "none"


@dataclass
class UniversalElement:
    """Universal representation of any UI control.

    Created from existing vision pipeline outputs:
    - VisualState.ui_targets (dict format from ContinuousVisionController)
    - ScreenState.elements (UIElement from vision/ui_models.py)
    - UIDetector output (UIElement from vision/ui_detector.py)
    """
    element_id: str
    element_type: ElementType
    label: str
    confidence: float
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    text: str = ""
    role: InteractiveRole = InteractiveRole.NONE
    enabled: bool = True
    visible: bool = True
    metadata: dict = field(default_factory=dict)
    source: str = "vision"
    selector: str = ""

    def __post_init__(self):
        if self.role == InteractiveRole.NONE:
            self.role = _infer_role(self.element_type, self.text)

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    @property
    def area(self) -> int:
        return self.width * self.height

    def contains_point(self, px: int, py: int) -> bool:
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)

    def distance_to(self, other: 'UniversalElement') -> float:
        dx = self.center_x - other.center_x
        dy = self.center_y - other.center_y
        return (dx * dx + dy * dy) ** 0.5

    def to_dict(self) -> dict:
        return {
            "id": self.element_id,
            "type": self.element_type.value,
            "label": self.label,
            "confidence": self.confidence,
            "x": self.x, "y": self.y,
            "width": self.width, "height": self.height,
            "text": self.text,
            "role": self.role.value,
            "enabled": self.enabled,
            "source": self.source,
        }

    @classmethod
    def from_visual_state_target(cls, target: dict, index: int) -> 'UniversalElement':
        """Convert a VisualState.ui_targets dict to UniversalElement."""
        bounds = target.get("bounds")
        x, y, w, h = 0, 0, 0, 0
        if isinstance(bounds, dict):
            x = bounds.get("x", 0)
            y = bounds.get("y", 0)
            w = bounds.get("width", 0)
            h = bounds.get("height", 0)
        elif isinstance(bounds, (list, tuple)) and len(bounds) >= 4:
            x, y, w, h = bounds[0], bounds[1], bounds[2], bounds[3]

        raw_type = target.get("type", "unknown")
        etype = _map_type(raw_type)
        text = target.get("text", "")
        role = _infer_role(etype, text)
        return cls(
            element_id=f"vs_{index}",
            element_type=etype,
            label=text[:100],
            confidence=target.get("confidence", 0.7),
            x=x, y=y, width=w, height=h,
            text=text, role=role,
            source="visual_state",
        )

    @classmethod
    def from_vision_ui_element(cls, elem: Any, index: int) -> 'UniversalElement':
        """Convert an existing vision UIElement (ui_models.py) to UniversalElement."""
        bounds = getattr(elem, "bounds", None)
        x = getattr(bounds, "x", 0) if bounds else 0
        y = getattr(bounds, "y", 0) if bounds else 0
        w = getattr(bounds, "width", 0) if bounds else 0
        h = getattr(bounds, "height", 0) if bounds else 0
        raw_type = getattr(getattr(elem, "type", None), "value", "unknown")
        etype = _map_type(raw_type)
        text = getattr(elem, "text", "")
        role = _infer_role(etype, text)
        return cls(
            element_id=f"ui_{getattr(elem, 'id', index)}",
            element_type=etype,
            label=text[:100],
            confidence=getattr(elem, "confidence", 0.7),
            x=x, y=y, width=w, height=h,
            text=text, role=role,
            enabled=getattr(elem, "enabled", True),
            visible=getattr(elem, "visible", True),
            source="vision_detector",
        )


def _map_type(raw: str) -> ElementType:
    mapping = {
        "button": ElementType.BUTTON,
        "textbox": ElementType.TEXT_FIELD,
        "textarea": ElementType.TEXT_FIELD,
        "text_field": ElementType.TEXT_FIELD,
        "input": ElementType.TEXT_FIELD,
        "dropdown": ElementType.DROPDOWN,
        "select": ElementType.DROPDOWN,
        "checkbox": ElementType.CHECKBOX,
        "radio": ElementType.RADIO,
        "link": ElementType.LINK,
        "tab": ElementType.TAB,
        "menu": ElementType.MENU,
        "menu_item": ElementType.MENU_ITEM,
        "icon": ElementType.ICON,
        "slider": ElementType.SLIDER,
        "toggle": ElementType.TOGGLE,
        "table": ElementType.TABLE,
        "list": ElementType.LIST_ITEM,
        "list_item": ElementType.LIST_ITEM,
        "image": ElementType.IMAGE,
        "text": ElementType.TEXT_LABEL,
        "label": ElementType.TEXT_LABEL,
        "panel": ElementType.PANEL,
        "dialog": ElementType.DIALOG,
        "toolbar": ElementType.TOOLBAR,
        "tree": ElementType.TREE,
        "tree_item": ElementType.TREE_ITEM,
        "window": ElementType.PANEL,
        "header": ElementType.TEXT_LABEL,
        "statusbar": ElementType.TEXT_LABEL,
        "sidebar": ElementType.PANEL,
        "content": ElementType.PANEL,
    }
    return mapping.get(raw.lower(), ElementType.UNKNOWN)


def _infer_role(etype: ElementType, text: str) -> InteractiveRole:
    if etype == ElementType.BUTTON:
        lower = text.lower()
        if any(d in lower for d in ("delete", "remove", "close", "cancel")):
            return InteractiveRole.DESTRUCTIVE
        return InteractiveRole.PRIMARY_ACTION
    if etype in (ElementType.TEXT_FIELD, ElementType.DROPDOWN):
        return InteractiveRole.INPUT
    if etype == ElementType.TAB:
        return InteractiveRole.NAVIGATION
    if etype in (ElementType.LINK, ElementType.MENU_ITEM):
        return InteractiveRole.NAVIGATION
    if etype == ElementType.CHECKBOX:
        return InteractiveRole.TOGGLE
    return InteractiveRole.NONE
