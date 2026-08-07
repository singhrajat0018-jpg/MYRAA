"""
MYRAA Cognitive Engine

Intent Classifier
"""

from __future__ import annotations

from enum import Enum

from ..models.models import PlannerGoal

from ..models.intent_types import IntentType



class IntentClassifier:
    """
    Rule-based intent classifier.

    Runs before planning and provides a high-level intent.
    """

    def classify(
        self,
        goal: PlannerGoal,
    ) -> IntentType:

        text = goal.text.lower()

        # --------------------------------------------------
        # Browser Search
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "search",
                "google",
                "find",
                "look up",
            )
        ):
            return IntentType.WEB_SEARCH

        # --------------------------------------------------
        # URLs
        # --------------------------------------------------

        if (
            "http://" in text
            or "https://" in text
            or ".com" in text
            or ".org" in text
            or ".net" in text
        ):
            return IntentType.OPEN_URL

        # --------------------------------------------------
        # Open Application
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "open",
                "launch",
                "start",
                "run",
            )
        ):
            return IntentType.OPEN_APPLICATION

        # --------------------------------------------------
        # Close Application
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "close",
                "exit",
                "quit",
            )
        ):
            return IntentType.CLOSE_APPLICATION

        # --------------------------------------------------
        # File Operations
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "save",
                "copy",
                "paste",
                "delete",
                "rename",
                "move",
                "create file",
                "create folder",
            )
        ):
            return IntentType.FILE_OPERATION

        # --------------------------------------------------
        # Keyboard
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "type",
                "press",
                "enter",
                "shortcut",
                "hotkey",
            )
        ):
            return IntentType.KEYBOARD_ACTION

        # --------------------------------------------------
        # Mouse
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "click",
                "double click",
                "right click",
                "drag",
                "drop",
                "scroll",
                "hover",
            )
        ):
            return IntentType.MOUSE_ACTION

        # --------------------------------------------------
        # System
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "shutdown",
                "restart",
                "sleep",
                "lock",
                "volume",
                "brightness",
            )
        ):
            return IntentType.SYSTEM_CONTROL

        # --------------------------------------------------
        # Desktop
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "desktop",
                "window",
                "minimize",
                "maximize",
                "taskbar",
            )
        ):
            return IntentType.DESKTOP_ACTION

        # --------------------------------------------------
        # Information
        # --------------------------------------------------

        if text.startswith(
            (
                "what",
                "who",
                "when",
                "where",
                "why",
                "how",
            )
        ):
            return IntentType.INFORMATION

        # --------------------------------------------------
        # Conversation
        # --------------------------------------------------

        if any(
            word in text
            for word in (
                "hello",
                "hi",
                "thanks",
                "thank you",
                "good morning",
                "good night",
            )
        ):
            return IntentType.CONVERSATION

        return IntentType.UNKNOWN