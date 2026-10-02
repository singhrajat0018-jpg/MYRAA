"""
MYRAA Vision V3
Screen State

Canonical structured representation of the currently visible desktop.
Provides structured understanding for perception and planning layers.

COORDINATE SYSTEM:
All coordinates are in virtual screen space (pixels), where:
- (0, 0) is the top-left corner of the primary monitor
- X increases to the right, Y increases downward
- Coordinates can be negative for monitors positioned left/above primary
- This matches the coordinate system used by Windows API and MSS capture
- No additional transformation is needed for most use cases
- For DPI-aware applications, coordinates should be interpreted as physical pixels
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from .ui_models import UIElementType, BoundingBox, UIElement
from .text_region import TextRegion
from .fusion_engine import SemanticNode


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


@dataclass(slots=True)
class ActiveWindow:
    """Information about the currently active window."""
    title: str = ""
    application: str = ""
    hwnd: Optional[int] = None


@dataclass(slots=True)
class TextRegionWithGeometry:
    """OCR text region with geometric information."""
    text: str
    bounds: BoundingBox
    confidence: float
    language: str = ""  # Detected language if available


@dataclass(slots=True)
class ChangedRegion:
    """Region of the screen that has changed."""
    bounds: BoundingBox
    timestamp: float
    change_type: str = "modified"  # modified, added, removed
    confidence: float = 1.0




@dataclass(slots=True)
class ScreenState:
    """
    Canonical structured representation of the currently visible desktop.

    This is the main output of the perception layer that provides
    a structured understanding of what is visible on the user's desktop.
    """
    timestamp: float = field(default_factory=time.time)
    screen_width: int = 0
    screen_height: int = 0

    active_window: ActiveWindow = field(default_factory=ActiveWindow)

    elements: List[UIElement] = field(default_factory=list)
    text_regions: List[TextRegionWithGeometry] = field(default_factory=list)
    changed_regions: List[ChangedRegion] = field(default_factory=list)

    source_frame_timestamp: float = field(default_factory=time.time)

    # Metadata for debugging and diagnostics
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_elements_by_type(self, element_type: UIElementType) -> List[UIElement]:
        """Get all elements of a specific type."""
        return [elem for elem in self.elements if elem.type == element_type]

    def get_interactive_elements(self) -> List[UIElement]:
        """Get all interactive elements."""
        return [elem for elem in self.elements if elem.interactive != InteractiveType.NONE]

    def get_element_at_position(self, x: int, y: int) -> Optional[UIElement]:
        """Get the topmost element at the given screen coordinates."""
        # Check in reverse order (topmost first)
        for elem in reversed(self.elements):
            if (elem.bounds.x <= x <= elem.bounds.right and
                elem.bounds.y <= y <= elem.bounds.bottom):
                return elem
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization/debugging."""
        return {
            "timestamp": self.timestamp,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "active_window": {
                "title": self.active_window.title,
                "application": self.active_window.application,
                "hwnd": self.active_window.hwnd
            },
            "elements": [
                {
                    "id": elem.id,
                    "type": elem.type.value,
                    "text": elem.text,
                    "bounds": {
                        "x": elem.bounds.x,
                        "y": elem.bounds.y,
                        "width": elem.bounds.width,
                        "height": elem.bounds.height
                    },
                    "center": list(elem.center),
                    "confidence": elem.confidence,
                    "visible": elem.visible,
                    "interactive": elem.interactive.value
                }
                for elem in self.elements
            ],
            "text_regions": [
                {
                    "text": region.text,
                    "bounds": {
                        "x": region.bounds.x,
                        "y": region.bounds.y,
                        "width": region.bounds.width,
                        "height": region.bounds.height
                    },
                    "confidence": region.confidence,
                    "language": region.language
                }
                for region in self.text_regions
            ],
            "changed_regions": [
                {
                    "bounds": {
                        "x": region.bounds.x,
                        "y": region.bounds.y,
                        "width": region.bounds.width,
                        "height": region.bounds.height
                    },
                    "timestamp": region.timestamp,
                    "change_type": region.change_type,
                    "confidence": region.confidence
                }
                for region in self.changed_regions
            ],
            "source_frame_timestamp": self.source_frame_timestamp,
            "metadata": self.metadata
        }