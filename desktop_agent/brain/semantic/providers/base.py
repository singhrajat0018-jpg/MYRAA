from __future__ import annotations

from abc import ABC, abstractmethod

from ..semantic_models import SemanticTask


class BaseSemanticProvider(ABC):
    """
    Interface for every semantic provider.

    Gemini
    Local LLM
    Ollama
    Future MCE Model
    """

    @abstractmethod
    def parse(
        self,
        text: str,
    ) -> SemanticTask:
        raise NotImplementedError