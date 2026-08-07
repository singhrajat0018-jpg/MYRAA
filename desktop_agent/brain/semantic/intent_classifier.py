"""
MYRAA Cognitive Engine
Intent Classifier

Responsibility:
----------------
Determine WHAT the user wants to do.

This module NEVER:

- Executes tools
- Extracts entities
- Plans tasks

It only predicts the user's intent.

Future versions may use:

- Gemini
- Local LLM
- Embedding Model
- Fine-tuned classifier

without changing the interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .semantic_models import Intent


# ============================================================
# Provider Interface
# ============================================================

class BaseIntentProvider(ABC):
    """
    Interface implemented by every intent provider.
    """

    @abstractmethod
    def classify(self, text: str) -> Intent:
        raise NotImplementedError


# ============================================================
# Rule-Based Provider (Temporary Bootstrap)
# ============================================================

class RuleBasedIntentProvider(BaseIntentProvider):
    """
    Bootstrap provider.

    This is NOT intended to be the final solution.
    It exists so the Cognitive Engine can function
    before an LLM provider is integrated.

    Replace this later with GeminiIntentProvider
    without changing the rest of the architecture.
    """

    def classify(self, text: str) -> Intent:

        t = text.lower()

        if any(x in t for x in ("open", "launch", "start", "khol")):
            return Intent.OPEN_APPLICATION

        if any(x in t for x in ("close", "band")):
            return Intent.CLOSE_APPLICATION

        if any(x in t for x in ("search", "find", "google")):
            return Intent.SEARCH_WEB

        if any(x in t for x in ("message", "whatsapp", "msg")):
            return Intent.SEND_MESSAGE

        if "email" in t:
            return Intent.SEND_EMAIL

        if any(x in t for x in ("create folder", "new folder")):
            return Intent.CREATE_FOLDER

        if any(x in t for x in ("create file", "new file")):
            return Intent.CREATE_FILE

        if any(x in t for x in ("delete", "remove")):
            return Intent.DELETE_FILE

        if any(x in t for x in ("shutdown", "restart", "sleep")):
            return Intent.SYSTEM_CONTROL

        if any(x in t for x in ("play", "music", "spotify")):
            return Intent.PLAY_MEDIA

        if any(x in t for x in ("camera", "see", "look", "screen")):
            return Intent.VISION

        return Intent.CHAT


# ============================================================
# Intent Classifier
# ============================================================

class IntentClassifier:
    """
    Public interface used by Semantic Parser.
    """

    def __init__(
        self,
        provider: Optional[BaseIntentProvider] = None,
    ):

        self.provider = provider or RuleBasedIntentProvider()

    def classify(self, text: str) -> Intent:

        if not text.strip():
            return Intent.UNKNOWN

        return self.provider.classify(text)