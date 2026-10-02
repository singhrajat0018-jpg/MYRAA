"""
MYRAA Research capability (EPIC-08)
Data models for the ResearchRouter pipeline.

RESEARCH capability -> ResearchRouter -> providers -> bounded evidence
-> AIManager synthesis -> ONE final MYRAA response.

These models are owned by the research capability. They are deliberately
separate from AIManager (LLM providers) and from the ResponseRouter (capability
decision).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ResearchSource:
    """
    A single retrieved evidence item, carrying only metadata the provider
    actually returned. ``published_date`` is "" when the provider supplied none;
    ``score`` is 0.0 when the provider supplied none (we never fabricate one).
    """

    provider: str
    title: str
    url: str
    snippet: str = ""
    published_date: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "published_date": self.published_date,
            "score": self.score,
        }


@dataclass(slots=True)
class ProviderRun:
    """
    Outcome of one provider attempt, preserved for diagnostics and source
    grounding. Serialized (no API keys / credentials ever).
    """

    provider: str
    success: bool
    source_count: int = 0
    error: str = ""
    # Sources this run produced (internal plumbing for grounding). Not
    # serialized here — they are surfaced via ResearchResult.sources.
    sources: List[ResearchSource] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "success": self.success,
            "source_count": self.source_count,
            "error": self.error,
        }


@dataclass(slots=True)
class ResearchResult:
    """
    Final research outcome, ready for synthesis and safe to serialize.
    ``synthesized`` holds the final MYRAA answer (empty until synthesized).
    """

    success: bool
    query: str
    answer_context: str = ""
    sources: List[ResearchSource] = field(default_factory=list)
    provider_results: List[ProviderRun] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    synthesized: str = ""
    synthesis_provider: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "query": self.query,
            "answer_context": self.answer_context,
            "sources": [s.to_dict() for s in self.sources],
            "provider_results": [p.to_dict() for p in self.provider_results],
            "errors": self.errors,
            "synthesized": self.synthesized,
            "synthesis_provider": self.synthesis_provider,
            "metadata": self.metadata,
        }
