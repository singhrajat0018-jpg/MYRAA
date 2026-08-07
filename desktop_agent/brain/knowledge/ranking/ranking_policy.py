"""
Ranking Policy

Determines provider priority depending
on the query type.
"""

from __future__ import annotations

from ..intelligence.query_type import QueryType


class RankingPolicy:

    """
    Returns provider priority.

    Higher value means higher priority.
    """

    DEFAULT = {

        "tavily": 1.00,

        "wikipedia": 0.95,

        "duckduckgo": 0.90,

    }

    RESEARCH = {

        "tavily": 1.00,

        "wikipedia": 0.85,

        "duckduckgo": 0.75,

    }

    NEWS = {

        "tavily": 1.00,

        "duckduckgo": 0.80,

        "wikipedia": 0.55,

    }

    FACT = {

        "wikipedia": 1.00,

        "duckduckgo": 0.90,

        "tavily": 0.85,

    }

    PROGRAMMING = {

        "duckduckgo": 1.00,

        "tavily": 0.90,

        "wikipedia": 0.60,

    }

    # ------------------------------------------------------

    def priority(

        self,

        provider: str,

        query_type: QueryType | None = None,

    ) -> float:

        provider = provider.lower()

        table = self.DEFAULT

        if query_type == QueryType.RESEARCH:

            table = self.RESEARCH

        elif query_type == QueryType.NEWS:

            table = self.NEWS

        elif query_type == QueryType.WIKIPEDIA:

            table = self.FACT

        elif query_type == QueryType.PROGRAMMING:

            table = self.PROGRAMMING

        return table.get(
            provider,
            0.50,
        )