"""
Knowledge Summary Model

Represents the final summarized knowledge that MYRAA's Brain
consumes after provider responses have been synthesized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...knowledge_source import KnowledgeSource


@dataclass(slots=True)
class KnowledgeSummary:
    """
    Final summarized knowledge object.
    """

    title: str = ""
    summary: str = ""

    bullets: list[str] = field(default_factory=list)

    confidence: float = 0.0

    provider: str = ""

    sources: list[KnowledgeSource] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_summary(self) -> bool:
        return bool(self.summary.strip())

    @property
    def has_bullets(self) -> bool:
        return len(self.bullets) > 0

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def add_bullet(self, bullet: str) -> None:
        bullet = bullet.strip()

        if not bullet:
            return

        self.bullets.append(bullet)

    def add_source(self, source: KnowledgeSource) -> None:
        self.sources.append(source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "bullets": self.bullets,
            "confidence": self.confidence,
            "provider": self.provider,
            "sources": [
                {
                    "provider": s.provider,
                    "title": s.title,
                    "url": s.url,
                    "snippet": s.snippet,
                    "confidence": s.confidence,
                }
                for s in self.sources
            ],
            "metadata": self.metadata,
        }