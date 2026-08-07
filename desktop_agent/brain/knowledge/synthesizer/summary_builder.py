"""
Summary Builder

Builds the final short summary for MYRAA.
"""

from __future__ import annotations

from ..provider_response import ProviderResponse


class SummaryBuilder:
    """
    Creates a concise summary.
    """

    def __init__(
        self,
        max_length: int = 250,
    ) -> None:

        self.max_length = max_length

    def build(
        self,
        response: ProviderResponse,
        bullets: list[str],
    ) -> str:

        # ----------------------------------------
        # Provider Answer
        # ----------------------------------------

        if response.answer:

            return self._trim(
                self._clean(response.answer)
            )

        # ----------------------------------------
        # Bullets
        # ----------------------------------------

        if bullets:

            summary = ". ".join(bullets[:3])

            return self._trim(summary)

        # ----------------------------------------
        # Source Snippets
        # ----------------------------------------

        if response.sources:

            snippets = []

            for source in response.sources[:3]:

                if source.snippet:

                    snippets.append(
                        self._clean(source.snippet)
                    )

            if snippets:

                return self._trim(
                    ". ".join(snippets)
                )

        return ""

    # -------------------------------------------------

    @staticmethod
    def _clean(text: str) -> str:

        return " ".join(text.split())

    # -------------------------------------------------

    def _trim(
        self,
        text: str,
    ) -> str:

        if len(text) <= self.max_length:

            return text

        return text[: self.max_length].rstrip() + "..."