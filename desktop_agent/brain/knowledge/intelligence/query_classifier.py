from __future__ import annotations

from .query_type import QueryType


class QueryClassifier:
    """
    Rule-based classifier.

    Later this can be replaced by
    an ML/LLM classifier without
    changing SearchRouter.
    """

    def classify(
        self,
        query: str,
    ) -> QueryType:

        q = query.lower()

        # --------------------------------------------------
        # Weather
        # --------------------------------------------------

        if any(
            word in q
            for word in (
                "weather",
                "temperature",
                "rain",
                "forecast",
            )
        ):
            return QueryType.WEATHER

        # --------------------------------------------------
        # News
        # --------------------------------------------------

        if any(
            word in q
            for word in (
                "latest",
                "breaking",
                "today",
                "news",
            )
        ):
            return QueryType.NEWS

        # --------------------------------------------------
        # Finance
        # --------------------------------------------------

        if any(
            word in q
            for word in (
                "stock",
                "share",
                "market",
                "crypto",
                "price",
            )
        ):
            return QueryType.FINANCE

        # --------------------------------------------------
        # Programming
        # --------------------------------------------------

        if any(
            word in q
            for word in (
                "python",
                "java",
                "c++",
                "bug",
                "error",
                "github",
                "api",
                "code",
            )
        ):
            return QueryType.PROGRAMMING

        # --------------------------------------------------
        # Research
        # --------------------------------------------------

        if any(
            word in q
            for word in (
                "research",
                "compare",
                "analysis",
                "study",
            )
        ):
            return QueryType.RESEARCH

        return QueryType.GENERAL