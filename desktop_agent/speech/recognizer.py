"""
Base speech recognizer interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Transcript


class BaseRecognizer(ABC):

    @abstractmethod
    def transcribe(self, audio: bytes) -> Transcript:
        """
        Convert PCM audio into text.
        """
        raise NotImplementedError