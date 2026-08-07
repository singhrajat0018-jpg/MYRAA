"""
News Analyzer

Future:
- Yahoo News
- Google News
- NSE Announcements
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NewsAnalysis:

    sentiment: str

    confidence: float

    summary: str


class NewsAnalyzer:

    def analyze(

        self,

        headlines: list[str],

    ) -> NewsAnalysis:

        if not headlines:

            return NewsAnalysis(

                sentiment="UNKNOWN",

                confidence=0.0,

                summary="No recent news.",

            )

        text = " ".join(headlines).lower()

        positive = [

            "approval",

            "profit",

            "growth",

            "record",

            "award",

            "contract",

        ]

        negative = [

            "loss",

            "warning",

            "investigation",

            "decline",

            "fraud",

            "penalty",

        ]

        score = 0

        for word in positive:

            if word in text:

                score += 1

        for word in negative:

            if word in text:

                score -= 1

        if score > 0:

            sentiment = "POSITIVE"

        elif score < 0:

            sentiment = "NEGATIVE"

        else:

            sentiment = "NEUTRAL"

        return NewsAnalysis(

            sentiment=sentiment,

            confidence=min(abs(score) / 3, 1.0),

            summary=headlines[0],

        )