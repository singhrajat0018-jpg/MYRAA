"""
Knowledge Decision Engine

Decides whether MYRAA should:
1. Answer directly
2. Open browser
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KnowledgeDecision:

    use_browser: bool

    use_knowledge: bool

    reason: str = ""


class KnowledgeDecisionEngine:

    BROWSER_WORDS = {

        "open",
        "show",
        "display",
        "visit",
        "website",
        "youtube",
        "google",
        "search on",
        "search in",
        "browser",
        "image",
        "images",
        "video",
        "videos",
        "chart",
        "graph",
        "tradingview",

    }

    @classmethod
    def decide(cls, text: str) -> KnowledgeDecision:

        lower = text.lower()

        if any(word in lower for word in cls.BROWSER_WORDS):

            return KnowledgeDecision(

                use_browser=True,

                use_knowledge=False,

                reason="Browser requested",

            )

        return KnowledgeDecision(

            use_browser=False,

            use_knowledge=True,

            reason="Direct knowledge answer",

        )