"""
MYRAA AI Manager
"""

from __future__ import annotations

from .providers import (
    OllamaProvider,
    GeminiProvider,
)


class AIManager:

    def __init__(self):

        self.providers = [

            OllamaProvider(),

            GeminiProvider(),

        ]

    def active_provider(self):

        for provider in self.providers:

            if provider.available():

                return provider

        raise RuntimeError(
            "No AI Provider available."
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:

        provider = self.active_provider()

        return provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            **kwargs,
        )

   