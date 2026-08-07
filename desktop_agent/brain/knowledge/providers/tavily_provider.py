from __future__ import annotations

import time

from tavily import TavilyClient

from ..mappers.tavily_mapper import TavilyMapper
from ..providers.provider_response import ProviderResponse
from .search_provider import SearchProvider


class TavilyProvider(SearchProvider):

    name = "tavily"

    priority = 100

    realtime = True

    def __init__(
        self,
        api_key: str,
    ):

        self.client = TavilyClient(
            api_key=api_key,
        )

        self.mapper = TavilyMapper()

    def supports(
        self,
        request,
    ):

        return True

    def search(
        self,
        request,
    ) -> ProviderResponse:

        started = time.perf_counter()

        try:

            response = self.client.search(
                query=request.query,
                search_depth="advanced",
                max_results=request.max_sources,
                include_answer=True,
            )

            result = self.mapper.map(
                response,
            )

            result.latency = (
                time.perf_counter()
                - started
            )

            return result

        except Exception as exc:

            return ProviderResponse(
                provider=self.name,
                success=False,
                answer="",
                metadata={
                    "error": str(exc),
                },
                latency=time.perf_counter()
                - started,
            )