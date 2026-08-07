"""
MYRAA Vision V3

Desktop State

Stores the latest semantic understanding of the desktop.

This class is intentionally lightweight.
It does NOT store history.
History belongs to the Memory subsystem.

Author
------
MYRAA Vision
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .vision_context import VisionContext
from .screen_analyzer import ScreenSummary


# ==========================================================
# Desktop State
# ==========================================================

@dataclass(slots=True)
class DesktopState:
    """
    Current semantic desktop state.
    """

    frame_id: int = 0

    timestamp: float = field(default_factory=time.time)

    screen_summary: Optional[ScreenSummary] = None

    vision_context: Optional[VisionContext] = None

    changed_regions: List[Any] = field(default_factory=list)

    screen_hash: str = ""

    confidence: float = 0.0

    active_window: str = ""

    active_application: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------

    @property
    def ready(self) -> bool:
        """
        True when semantic data exists.
        """
        return (
            self.screen_summary is not None
            and self.vision_context is not None
        )

    # ------------------------------------------------------

    @property
    def node_count(self) -> int:

        if self.vision_context is None:
            return 0

        return self.vision_context.node_count

    # ------------------------------------------------------

    @property
    def screen_type(self):

        if self.screen_summary is None:
            return None

        return self.screen_summary.screen_type

    # ------------------------------------------------------

    @property
    def primary_action(self):

        if self.screen_summary is None:
            return None

        return self.screen_summary.primary_action

    # ------------------------------------------------------

    def update(
        self,
        *,
        frame_id: int,
        vision_context: VisionContext,
        screen_summary: ScreenSummary,
        changed_regions: Optional[List[Any]] = None,
        screen_hash: str = "",
        active_window: str = "",
        active_application: str = "",
        confidence: Optional[float] = None,
    ) -> None:
        """
        Replace current desktop state.
        """

        self.frame_id = frame_id

        self.timestamp = time.time()

        self.vision_context = vision_context

        self.screen_summary = screen_summary

        self.changed_regions = changed_regions or []

        self.screen_hash = screen_hash

        self.active_window = active_window

        self.active_application = active_application

        self.confidence = (
            confidence
            if confidence is not None
            else screen_summary.confidence
        )

    # ------------------------------------------------------

    def clear(self) -> None:
        """
        Reset desktop state.
        """

        self.frame_id = 0

        self.timestamp = time.time()

        self.screen_summary = None

        self.vision_context = None

        self.changed_regions.clear()

        self.screen_hash = ""

        self.confidence = 0.0

        self.active_window = ""

        self.active_application = ""

        self.metadata.clear()

    # ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Lightweight representation for logging/debugging.
        """

        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "screen_type": (
                self.screen_summary.screen_type.value
                if self.screen_summary
                else None
            ),
            "confidence": self.confidence,
            "node_count": self.node_count,
            "active_window": self.active_window,
            "active_application": self.active_application,
            "changed_regions": len(self.changed_regions),
        }

    # ------------------------------------------------------

    def __bool__(self):

        return self.ready