"""
Temporary Gemini Stub
"""

from __future__ import annotations

from ..provider import AIProvider


class GeminiProvider(AIProvider):

    @property
    def name(self):

        return "gemini"

    def available(self):

        return False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ):

        raise RuntimeError(
            "Gemini disabled."
        )