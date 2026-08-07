from __future__ import annotations

from .query_classifier import QueryClassifier
from .query_type import QueryType
from .routing_result import RoutingResult


class SearchRouter:

    def __init__(self):

        self.classifier = QueryClassifier()

    def route(
        self,
        query: str,
    ) -> RoutingResult:

        query_type = self.classifier.classify(
            query
        )

        if query_type == QueryType.GENERAL:

            return RoutingResult(
                query_type=query_type,
                providers=[
                    "duckduckgo",
                ],
                use_local=False,
                use_external=True,
            )

        if query_type == QueryType.RESEARCH:

            return RoutingResult(
                query_type=query_type,
                providers=[
                    "tavily",
                    "wikipedia",
                ],
                use_local=False,
                use_external=True,
                priority=100,
            )

        if query_type == QueryType.PROGRAMMING:

            return RoutingResult(
                query_type=query_type,
                providers=[
                    "github",
                    "duckduckgo",
                ],
                use_local=False,
                use_external=True,
            )

        if query_type == QueryType.NEWS:

            return RoutingResult(
                query_type=query_type,
                providers=[
                    "tavily",
                ],
                use_local=False,
                use_external=True,
            )

        if query_type == QueryType.WEATHER:

            return RoutingResult(
                query_type=query_type,
                providers=[
                    "weather",
                ],
                use_local=False,
                use_external=True,
            )

        if query_type == QueryType.FINANCE:

            return RoutingResult(
                query_type=query_type,
                providers=[
                    "finance",
                ],
                use_local=False,
                use_external=True,
            )

        return RoutingResult(
            query_type=query_type,
            providers=[
                "duckduckgo",
            ],
            use_local=False,
            use_external=True,
        )