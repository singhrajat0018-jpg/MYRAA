"""
MYRAA Skill Resolver

Adds domain intelligence to SemanticTask.
"""

from __future__ import annotations

from .semantic_models import SemanticTask, Intent


class SkillResolver:

    NEWS_WORDS = {
        "news",
        "headlines",
        "breaking",
        "current affairs",
        "latest news",
    }

    WEATHER_WORDS = {
        "weather",
        "temperature",
        "forecast",
        "rain",
    }

    TRADING_WORDS = {
        "stock",
        "share",
        "nifty",
        "sensex",
        "bitcoin",
        "btc",
        "crypto",
    }

    @classmethod
    def process(cls, task: SemanticTask) -> SemanticTask:

        if task.intent != Intent.SEARCH_WEB:
            return task

        text = task.raw_text.lower()

        skill = None

        if any(word in text for word in cls.NEWS_WORDS):
            skill = "news"

        elif any(word in text for word in cls.WEATHER_WORDS):
            skill = "weather"

        elif any(word in text for word in cls.TRADING_WORDS):
            skill = "trading"

        if skill:
            task.metadata["skill"] = skill

        return task