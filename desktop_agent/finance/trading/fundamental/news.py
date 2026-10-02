"""
MYRAA Trading Intelligence — News / Event Intelligence (Part 7)

Separate FACT from INTERPRETATION. Do not let one headline produce a trade signal.
"""

from __future__ import annotations

from typing import List

from ..models import NewsAnalysis, NewsItem


class NewsAnalyzer:

    POSITIVE_WORDS = {
        "profit", "growth", "record", "approval", "upgrade", "surge",
        "rally", "beat", "strong", "surplus", "expansion", "contract",
        "dividend", "buyback", "merger", "acquisition", "partnership",
        "innovation", "launch", "breakthrough", "outperform",
    }
    NEGATIVE_WORDS = {
        "loss", "decline", "fraud", "penalty", "investigation", "warning",
        "downgrade", "crash", "slump", "weak", "deficit", "lawsuit",
        "bankruptcy", "default", "recession", "layoff", "cut", "miss",
        "underperform", "sell-off",
    }
    EVENT_KEYWORDS = {
        "earnings", "results", "dividend", "buyback", "merger", "acquisition",
        "split", "bonus", "rights", "ipo", "fpo", "regulatory", "policy",
        "budget", "rate", "inflation", "gdp",
    }

    def analyze(self, symbol: str, headlines: List[NewsItem]) -> NewsAnalysis:
        if not headlines:
            return NewsAnalysis(symbol=symbol, reasoning="No recent news")

        text_all = " ".join(h.title.lower() + " " + h.summary.lower() for h in headlines)

        pos = sum(1 for w in self.POSITIVE_WORDS if w in text_all)
        neg = sum(1 for w in self.NEGATIVE_WORDS if w in text_all)
        score = pos - neg

        if score > 2:
            sentiment = "POSITIVE"
        elif score < -2:
            sentiment = "NEGATIVE"
        elif score > 0:
            sentiment = "SLIGHTLY_POSITIVE"
        elif score < 0:
            sentiment = "SLIGHTLY_NEGATIVE"
        else:
            sentiment = "NEUTRAL"

        event_flags = []
        for kw in self.EVENT_KEYWORDS:
            if kw in text_all:
                event_flags.append(kw.upper())

        top = [h.title for h in headlines[:5]]

        conf = min(len(headlines) / 5, 1.0) * 0.5
        if abs(score) >= 3:
            conf += 0.3
        elif abs(score) >= 1:
            conf += 0.15

        parts = [f"{len(headlines)} headlines analyzed"]
        if sentiment != "NEUTRAL":
            parts.append(f"Sentiment: {sentiment} (score: {score})")
        if event_flags:
            parts.append(f"Events: {', '.join(event_flags)}")

        return NewsAnalysis(
            symbol=symbol,
            sentiment=sentiment,
            sentiment_score=score / max(pos + neg, 1),
            confidence=min(conf, 1.0),
            headline_count=len(headlines),
            top_headlines=top,
            event_flags=event_flags,
            reasoning=" | ".join(parts),
        )
