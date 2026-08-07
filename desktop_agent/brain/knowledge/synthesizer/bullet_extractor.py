"""
Bullet Extractor

Extracts concise bullet points from a ProviderResponse.
"""

from __future__ import annotations

import re

from ..provider_response import ProviderResponse


class BulletExtractor:
    """
    Extracts important bullet points from provider data.
    """

    def __init__(
        self,
        max_bullets: int = 5,
        max_length: int = 140,
    ) -> None:

        self.max_bullets = max_bullets
        self.max_length = max_length

    def extract(
        self,
        response: ProviderResponse,
    ) -> list[str]:

        bullets: list[str] = []

        # --------------------------------------------------
        # Provider Answer
        # --------------------------------------------------

        if response.answer:

            bullets.extend(
                self._split_into_points(response.answer)
            )

        # --------------------------------------------------
        # Source Snippets
        # --------------------------------------------------

        for source in response.sources:

            if len(bullets) >= self.max_bullets:
                break

            if source.snippet:

                bullets.extend(
                    self._split_into_points(source.snippet)
                )

        # --------------------------------------------------
        # Cleanup
        # --------------------------------------------------

        cleaned: list[str] = []

        for bullet in bullets:

            bullet = self._clean(bullet)

            if not bullet:
                continue

            if bullet in cleaned:
                continue

            cleaned.append(bullet)

            if len(cleaned) >= self.max_bullets:
                break

        return cleaned

    # --------------------------------------------------

    def _split_into_points(
        self,
        text: str,
    ) -> list[str]:

        sentences = re.split(r"[.!?]\s+", text)

        output: list[str] = []

        for sentence in sentences:

            sentence = sentence.strip()

            if len(sentence) < 15:
                continue

            if len(sentence) > self.max_length:
                sentence = sentence[: self.max_length].rstrip() + "..."

            output.append(sentence)

        return output

    # --------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:

        return " ".join(text.split())