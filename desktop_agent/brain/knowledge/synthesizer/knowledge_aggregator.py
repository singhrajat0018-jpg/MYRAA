from __future__ import annotations

from ..intelligence.knowledge_result import KnowledgeResult


class KnowledgeAggregator:
    """
    Collects responses from multiple providers.
    """

    def aggregate(
        self,
        results: list[KnowledgeResult],
    ) -> list[KnowledgeResult]:

        return [
            r
            for r in results
            if r.success
        ]