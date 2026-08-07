"""
Freshness Score

Calculates freshness score using metadata timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone


class FreshnessScore:
    """
    Calculates document freshness.
    """

    def __init__(

        self,

        newest_score: float = 1.0,

        oldest_score: float = 0.2,

    ) -> None:

        self.newest_score = newest_score

        self.oldest_score = oldest_score

    def calculate(

        self,

        published_at: datetime | None,

    ) -> float:

        if published_at is None:

            return 0.5

        if published_at.tzinfo is None:

            published_at = published_at.replace(

                tzinfo=timezone.utc

            )

        now = datetime.now(timezone.utc)

        age = (now - published_at).days

        # Today
        if age <= 1:

            return 1.0

        # Week
        if age <= 7:

            return 0.90

        # Month
        if age <= 30:

            return 0.80

        # Quarter
        if age <= 90:

            return 0.65

        # Year
        if age <= 365:

            return 0.45

        return self.oldest_score