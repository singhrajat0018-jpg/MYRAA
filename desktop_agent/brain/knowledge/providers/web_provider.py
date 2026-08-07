from __future__ import annotations

from .search_provider import SearchProvider

from ..intelligence.knowledge_request import KnowledgeRequest
from ..intelligence.knowledge_result import KnowledgeResult


class WebProvider(
    SearchProvider
):

    name = "web"

    priority = 10

    realtime = True

    def supports(
        self,
        request: KnowledgeRequest,
    ) -> bool:

        return True

    def search(
        self,
        request: KnowledgeRequest,
    ) -> KnowledgeResult:

        return KnowledgeResult(
            success=True,
            answer="Web Provider Placeholder",
            confidence=0.20,
            provider=self.name,
        )