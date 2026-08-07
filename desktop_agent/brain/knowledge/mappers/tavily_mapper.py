from __future__ import annotations

from .base_mapper import BaseMapper

from ..intelligence.knowledge_source import KnowledgeSource
from ..providers.provider_response import ProviderResponse


class TavilyMapper(BaseMapper):

    def map(
        self,
        response,
    ) -> ProviderResponse:

        sources = []

        for item in response.get("results", []):

            sources.append(
                KnowledgeSource(
                    provider="tavily",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    confidence=item.get("score", 0.5),
                )
            )

        # ----------------------------
        # Extract answer
        # ----------------------------

        answer = response.get("answer")

        if not answer:

            results = response.get("results", [])

            if results:

                answer = results[0].get(
                    "content",
                    ""
                )

            else:

                answer = ""

        return ProviderResponse(
            provider="tavily",
            success=True,
            answer=answer,
            sources=sources,
            metadata=response,
        )