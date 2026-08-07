"""
MYRAA Vision V3

Screen Transition Engine

Compares two ScreenSummary objects and generates
high-level semantic events.

Author
------
MYRAA Vision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .screen_analyzer import ScreenSummary


# ==========================================================
# Event Types
# ==========================================================

class VisionEventType(str, Enum):

    SCREEN_CHANGED = "screen_changed"

    SCREEN_TYPE_CHANGED = "screen_type_changed"

    APPLICATION_CHANGED = "application_changed"

    DIALOG_OPENED = "dialog_opened"

    DIALOG_CLOSED = "dialog_closed"

    PRIMARY_ACTION_CHANGED = "primary_action_changed"

    NAVIGATION_CHANGED = "navigation_changed"

    INPUT_CHANGED = "input_changed"

    CONTENT_CHANGED = "content_changed"


# ==========================================================
# Vision Event
# ==========================================================

@dataclass(slots=True)
class VisionEvent:

    event: VisionEventType

    confidence: float = 1.0

    description: str = ""

    metadata: Dict[str, object] = field(default_factory=dict)


# ==========================================================
# Transition Engine
# ==========================================================

class ScreenTransition:

    """
    Detects semantic transitions between two screen states.
    """

    # ------------------------------------------------------

    def compare(
        self,
        previous: Optional[ScreenSummary],
        current: Optional[ScreenSummary],
    ) -> List[VisionEvent]:

        events: List[VisionEvent] = []

        if current is None:
            return events

        if previous is None:

            events.append(

                VisionEvent(

                    VisionEventType.SCREEN_CHANGED,

                    description="Initial screen detected."

                )

            )

            return events

        # ----------------------------------------
        # Screen type
        # ----------------------------------------

        if previous.screen_type != current.screen_type:

            events.append(

                VisionEvent(

                    VisionEventType.SCREEN_TYPE_CHANGED,

                    description=f"{previous.screen_type.value} → {current.screen_type.value}"

                )

            )

        # ----------------------------------------
        # Dialog
        # ----------------------------------------

        if previous.dialog is None and current.dialog is not None:

            events.append(

                VisionEvent(

                    VisionEventType.DIALOG_OPENED,

                    description="Dialog opened."

                )

            )

        elif previous.dialog is not None and current.dialog is None:

            events.append(

                VisionEvent(

                    VisionEventType.DIALOG_CLOSED,

                    description="Dialog closed."

                )

            )

        # ----------------------------------------
        # Primary Action
        # ----------------------------------------

        previous_action = (
            previous.primary_action.text.lower()
            if previous.primary_action
            else ""
        )

        current_action = (
            current.primary_action.text.lower()
            if current.primary_action
            else ""
        )

        if previous_action != current_action:

            events.append(

                VisionEvent(

                    VisionEventType.PRIMARY_ACTION_CHANGED,

                    description=f"{previous_action} → {current_action}"

                )

            )

        # ----------------------------------------
        # Navigation
        # ----------------------------------------

        if len(previous.navigation) != len(current.navigation):

            events.append(

                VisionEvent(

                    VisionEventType.NAVIGATION_CHANGED,

                    description="Navigation layout changed."

                )

            )

        # ----------------------------------------
        # Inputs
        # ----------------------------------------

        if len(previous.inputs) != len(current.inputs):

            events.append(

                VisionEvent(

                    VisionEventType.INPUT_CHANGED,

                    description="Input controls changed."

                )

            )

        # ----------------------------------------
        # Content
        # ----------------------------------------

        if len(previous.labels) != len(current.labels):

            events.append(

                VisionEvent(

                    VisionEventType.CONTENT_CHANGED,

                    description="Visible content changed."

                )

            )

        return events