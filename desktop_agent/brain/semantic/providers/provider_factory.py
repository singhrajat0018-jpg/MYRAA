"""
Semantic Provider Factory — Local-Only
"""

from __future__ import annotations


class ProviderFactory:

    @staticmethod
    def create(ai=None):
        if ai is None:
            from desktop_agent.brain.ai.ai_manager import AIManager
            ai = AIManager()

        # Route through the authoritative AIManager contract: local Ollama only.
        provider = ai.resolve_provider(
            hints={"categories": ["conversational", "local"]}
        )

        if provider is None:
            return None

        if provider.name == "ollama":
            from .ollama_provider import OllamaSemanticProvider
            return OllamaSemanticProvider(ai)

        return None
