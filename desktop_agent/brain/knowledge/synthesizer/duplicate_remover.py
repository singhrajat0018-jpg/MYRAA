"""
Duplicate Remover

Removes duplicate or near-identical snippets before
summary generation.
"""

from __future__ import annotations

from difflib import SequenceMatcher


class DuplicateRemover:
    """
    Removes duplicate snippets.

    Exact duplicates are removed first.

    Similar snippets above the similarity threshold
    are also discarded.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.92,
    ) -> None:

        self.similarity_threshold = similarity_threshold

    def remove(
        self,
        snippets: list[str],
    ) -> list[str]:

        unique: list[str] = []

        for snippet in snippets:

            snippet = self._clean(snippet)

            if not snippet:
                continue

            if self._is_duplicate(snippet, unique):
                continue

            unique.append(snippet)

        return unique

    def _is_duplicate(
        self,
        candidate: str,
        existing: list[str],
    ) -> bool:

        for text in existing:

            if candidate.lower() == text.lower():
                return True

            similarity = SequenceMatcher(
                None,
                candidate.lower(),
                text.lower(),
            ).ratio()

            if similarity >= self.similarity_threshold:
                return True

        return False

    @staticmethod
    def _clean(text: str) -> str:

        return " ".join(text.strip().split())