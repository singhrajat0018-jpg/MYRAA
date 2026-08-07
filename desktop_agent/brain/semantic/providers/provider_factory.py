"""
Semantic Provider Factory
"""

from __future__ import annotations

from desktop_agent.brain.ai import AIManager

from .ollama_provider import OllamaSemanticProvider
from .gemini_provider import GeminiSemanticProvider


class ProviderFactory:

    @staticmethod
    def create():

        ai = AIManager()

        provider = ai.active_provider()

        if provider.name == "ollama":
            return OllamaSemanticProvider(ai)

        if provider.name == "gemini":
            return GeminiSemanticProvider(ai)

        raise RuntimeError(
            f"Unsupported provider: {provider.name}"
        )