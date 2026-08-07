"""
Title Generator

Creates a meaningful title for summarized knowledge.
"""

from __future__ import annotations

from ..provider_response import ProviderResponse


class TitleGenerator:
    """
    Generates summary titles.
    """

    DEFAULT_TITLE = "Knowledge Summary"

    def generate(
        self,
        response: ProviderResponse,
    ) -> str:

        metadata = response.metadata or {}

        # ----------------------------------------
        # Explicit title
        # ----------------------------------------

        title = metadata.get("title")

        if isinstance(title, str) and title.strip():
            return self._normalize(title)

        # ----------------------------------------
        # Original Query
        # ----------------------------------------

        query = metadata.get("query")

        if isinstance(query, str) and query.strip():

            return self._query_to_title(query)

        # ----------------------------------------
        # First Source
        # ----------------------------------------

        if response.sources:

            first = response.sources[0]

            if first.title.strip():
                return self._normalize(first.title)

        # ----------------------------------------
        # Provider Name
        # ----------------------------------------

        if response.provider:

            return f"{response.provider.title()} Summary"

        return self.DEFAULT_TITLE

    # ------------------------------------------------------

    @staticmethod
    def _normalize(title: str) -> str:

        title = " ".join(title.split())

        if len(title) > 80:
            title = title[:77].rstrip() + "..."

        return title

    # ------------------------------------------------------

    @staticmethod
    def _query_to_title(query: str) -> str:

        query = query.strip()

        if not query:
            return "Knowledge Summary"

        if query.endswith("?"):
            query = query[:-1]

        words = query.split()

        return " ".join(word.capitalize() for word in words)