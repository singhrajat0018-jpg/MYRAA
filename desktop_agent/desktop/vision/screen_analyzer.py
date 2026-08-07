"""
MYRAA Vision V3

Screen Analyzer

Converts raw vision data into a high-level
understanding of the current screen.

Author
------
MYRAA Vision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from .analyzers.generic import GenericAnalyzer

from .vision_context import VisionContext
from .fusion_engine import (
    SemanticNode,
    SemanticRole,
)


# ==========================================================
# Screen Type
# ==========================================================

class ScreenType(str, Enum):

    UNKNOWN = "unknown"

    DESKTOP = "desktop"

    BROWSER = "browser"

    FILE_EXPLORER = "file_explorer"

    SETTINGS = "settings"

    LOGIN = "login"

    DIALOG = "dialog"

    POPUP = "popup"

    FORM = "form"

    APPLICATION = "application"


# ==========================================================
# Screen Summary
# ==========================================================

@dataclass(slots=True)
class ScreenSummary:

    screen_type: ScreenType = ScreenType.UNKNOWN

    confidence: float = 0.0

    title: str = ""

    primary_action: Optional[SemanticNode] = None

    focused_element: Optional[SemanticNode] = None

    dialog: Optional[SemanticNode] = None

    navigation: List[SemanticNode] = field(default_factory=list)

    actions: List[SemanticNode] = field(default_factory=list)

    inputs: List[SemanticNode] = field(default_factory=list)

    labels: List[SemanticNode] = field(default_factory=list)

    metadata: Dict[str, str] = field(default_factory=dict)


# ==========================================================
# Screen Analyzer
# ==========================================================

class ScreenAnalyzer:

    

    def __init__(self):

        self.analyzers = [

            GenericAnalyzer(),

        ]

        # ------------------------------------------------------

    def analyze(
        self,
        vision: VisionContext,
    ) -> ScreenSummary:
        """
        Analyze the current screen and produce a semantic summary.
        """

        summary = ScreenSummary()

        summary.dialog = self._find_dialog(vision)

        summary.navigation = self._find_navigation(vision)

        summary.actions = self._find_actions(vision)

        summary.inputs = self._find_inputs(vision)

        summary.labels = self._find_labels(vision)

        summary.primary_action = self._find_primary_action(summary)

        summary.screen_type = self._detect_screen_type(summary)

        summary.confidence = self._estimate_confidence(summary)

        # --------------------------------------
        # Specialized analyzers
        # --------------------------------------

        for analyzer in self.analyzers:

            if analyzer.can_handle(vision):

                summary = analyzer.analyze(

                    vision,

                    summary,

                )

                break

        return summary

        

    # ------------------------------------------------------
    # Dialog Detection
    # ------------------------------------------------------

    def _find_dialog(
        self,
        vision: VisionContext,
    ) -> Optional[SemanticNode]:

        dialogs = vision.screen.find_role(
            SemanticRole.DIALOG
        )

        if dialogs:
            return dialogs[0]

        return None

    # ------------------------------------------------------
    # Navigation Detection
    # ------------------------------------------------------

    def _find_navigation(
        self,
        vision: VisionContext,
    ) -> List[SemanticNode]:

        result = []

        result.extend(
            vision.screen.find_role(
                SemanticRole.TOOLBAR
            )
        )

        result.extend(
            vision.screen.find_role(
                SemanticRole.SIDEBAR
            )
        )

        return result

    # ------------------------------------------------------
    # Action Detection
    # ------------------------------------------------------

    def _find_actions(
        self,
        vision: VisionContext,
    ) -> List[SemanticNode]:

        return vision.screen.find_role(
            SemanticRole.BUTTON
        )

    # ------------------------------------------------------
    # Input Detection
    # ------------------------------------------------------

    def _find_inputs(
        self,
        vision: VisionContext,
    ) -> List[SemanticNode]:

        return vision.screen.find_role(
            SemanticRole.TEXTBOX
        )

    # ------------------------------------------------------
    # Label Detection
    # ------------------------------------------------------

    def _find_labels(
        self,
        vision: VisionContext,
    ) -> List[SemanticNode]:

        labels = []

        labels.extend(
            vision.screen.find_role(
                SemanticRole.LABEL
            )
        )

        labels.extend(
            vision.screen.find_role(
                SemanticRole.TEXT
            )
        )

        return labels



    # ------------------------------------------------------
    # Primary Action
    # ------------------------------------------------------

    def _find_primary_action(
        self,
        summary: ScreenSummary,
    ) -> Optional[SemanticNode]:
        """
        Selects the most likely primary action.
        """

        if not summary.actions:
            return None

        # Prefer buttons with meaningful labels
        priority = [
            "search",
            "login",
            "sign in",
            "submit",
            "save",
            "open",
            "continue",
            "next",
            "ok",
        ]

        for keyword in priority:

            for action in summary.actions:

                if keyword in action.text.lower():

                    return action

        # Otherwise return the first button

        return summary.actions[0]

    # ------------------------------------------------------
    # Screen Type Detection
    # ------------------------------------------------------

    def _detect_screen_type(
        self,
        summary: ScreenSummary,
    ) -> ScreenType:
        """
        Determines the screen type using semantic evidence.
        """

        # Dialog always has highest priority
        if summary.dialog is not None:

            return ScreenType.DIALOG

        # Login form

        if (
            len(summary.inputs) >= 2
            and any(
                "login" in b.text.lower()
                or "sign in" in b.text.lower()
                for b in summary.actions
            )
        ):

            return ScreenType.LOGIN

        # Generic form

        if len(summary.inputs) >= 2:

            return ScreenType.FORM

        # Popup

        if (
            len(summary.actions) <= 2
            and len(summary.labels) > 0
            and summary.dialog is None
        ):

            return ScreenType.POPUP

        # Application window

        if summary.navigation:

            return ScreenType.APPLICATION

        return ScreenType.UNKNOWN

    # ------------------------------------------------------
    # Confidence
    # ------------------------------------------------------

    def _estimate_confidence(
        self,
        summary: ScreenSummary,
    ) -> float:
        """
        Estimates confidence of analysis.
        """

        score = 0.0

        if summary.navigation:

            score += 0.25

        if summary.actions:

            score += 0.25

        if summary.inputs:

            score += 0.20

        if summary.labels:

            score += 0.20

        if summary.primary_action:

            score += 0.10

        return min(score, 1.0)