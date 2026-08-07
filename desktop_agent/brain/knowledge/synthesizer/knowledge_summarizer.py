"""
Knowledge Summarizer

Coordinates the knowledge summarization pipeline.
"""

from __future__ import annotations

from .bullet_extractor import BulletExtractor
from .duplicate_remover import DuplicateRemover
from .summary_builder import SummaryBuilder
from .title_generator import TitleGenerator
from .models.knowledge_summary import KnowledgeSummary

from ..provider_response import ProviderResponse


class KnowledgeSummarizer:
    """
    Converts ProviderResponse into KnowledgeSummary.
    """

    def __init__(self) -> None:

        self.duplicate_remover = DuplicateRemover()

        self.bullet_extractor = BulletExtractor()

        self.title_generator = TitleGenerator()

        self.summary_builder = SummaryBuilder()

    # -----------------------------------------------------

    def summarize(
        self,
        response: ProviderResponse,
    ) -> KnowledgeSummary:

        bullets = self.bullet_extractor.extract(
            response
        )

        bullets = self.duplicate_remover.remove(
            bullets
        )

        title = self.title_generator.generate(
            response
        )

        summary = self.summary_builder.build(
            response,
            bullets,
        )

        return KnowledgeSummary(

            title=title,

            summary=summary,

            bullets=bullets,

            confidence=response.confidence,

            provider=response.provider,

            sources=response.sources,

            metadata=response.metadata,
        )