"""
EPIC-09 deterministic unit tests for ResearchRouter (selection, failover,
deduplication, ranking, metadata, controlled failure).

Providers are fakes — no internet, no Tavily/DDG/Wikipedia, no live LLM.
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.research.models import ResearchSource, ProviderRun
from desktop_agent.brain.research.research_router import (
    ResearchRouter,
    _canonical_url,
)
from desktop_agent.brain.router.response_router import ResearchHandoff


class FakeProvider:
    """Provider returning a fixed list of sources or raising on search."""

    def __init__(self, name, sources=None, error=None):
        self.name = name
        self._sources = sources or []
        self._error = error

    def search(self, query, max_sources, timeout=10.0):
        if self._error is not None:
            raise RuntimeError(self._error)
        return self._sources


class StubSynthesizer:
    """Records evidence and returns a canned grounded answer."""

    def __init__(self, answer="SYNTH-ANSWER"):
        self.answer = answer
        self.seen_query = None
        self.seen_sources = None

    def synthesize(self, query, sources, conversation_context=None):
        self.seen_query = query
        self.seen_sources = sources
        return self.answer, "gemini"


def build_router(
    tavily=None,
    ddg=None,
    wiki=None,
    synth=None,
):
    # NOTE: Phase 4.5 added _cache/_provider_health to __init__. This fixture
    # constructs via __new__ to inject fakes without touching real providers,
    # so it must replicate the instance state __init__ would establish —
    # otherwise research() crashes on self._cache (stale-fixture fix).
    r = ResearchRouter.__new__(ResearchRouter)
    r.tavily = tavily if tavily is not None else FakeProvider("tavily")
    r.duckduckgo = ddg if ddg is not None else FakeProvider("duckduckgo")
    r.wikipedia = wiki if wiki is not None else FakeProvider("wikipedia")
    r.synthesizer = synth if synth is not None else StubSynthesizer()
    r._cache = {}
    r._provider_health = {
        "tavily": {"available": True, "last_failure": 0.0, "consecutive_failures": 0},
        "duckduckgo": {"available": True, "last_failure": 0.0, "consecutive_failures": 0},
        "wikipedia": {"available": True, "last_failure": 0.0, "consecutive_failures": 0},
    }
    return r


def src(provider, title, url, snippet="", date="", score=0.0):
    return ResearchSource(
        provider=provider,
        title=title,
        url=url,
        snippet=snippet,
        published_date=date,
        score=score,
    )


# ---------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------

def test_selection_definitional_prefers_wikipedia():
    r = build_router()
    sel = r._select_providers("What is Rayleigh scattering?", ResearchHandoff("What is Rayleigh scattering?"))
    assert sel[0] == "wikipedia"
    assert "tavily" in sel  # supporting web second


def test_selection_current_prefers_tavily_then_ddg():
    r = build_router()
    sel = r._select_providers("What happened to NIFTY today?", ResearchHandoff("What happened to NIFTY today?"))
    assert sel[0] == "tavily"
    assert sel[1] == "duckduckgo"
    assert "wikipedia" not in sel  # no wikipedia-primary for live info


def test_selection_general_uses_multi_provider():
    r = build_router()
    sel = r._select_providers("Compare Python and Rust.", ResearchHandoff("Compare Python and Rust."))
    assert sel == ["tavily", "duckduckgo", "wikipedia"]


def test_empty_query_is_controlled_failure():
    r = build_router()
    res = r.research(ResearchHandoff("   "))
    assert res.success is False
    assert res.synthesized == ""
    assert any("empty research query" in e for e in res.errors)


# ---------------------------------------------------------------
# Failover
# ---------------------------------------------------------------

def test_failover_tavily_fails_ddg_succeeds():
    synth = StubSynthesizer()
    r = build_router(
        tavily=FakeProvider("tavily", error="boom-tavily"),
        ddg=FakeProvider("duckduckgo", [src("duckduckgo", "DDG1", "https://ddg.com/1")]),
        synth=synth,
    )
    res = r.research(ResearchHandoff("Latest news", reason="current"))
    assert res.success is True
    assert res.synthesized == "SYNTH-ANSWER"
    assert any("boom-tavily" in e for e in res.errors)
    assert {p.provider for p in res.provider_results} == {"tavily", "duckduckgo"}
    # Synthesis grounded in the evidence DDG actually returned.
    assert synth.seen_sources and synth.seen_sources[0].url == "https://ddg.com/1"


def test_failover_tavily_and_ddg_fail_wikipedia_succeeds():
    r = build_router(
        tavily=FakeProvider("tavily", error="e1"),
        ddg=FakeProvider("duckduckgo", error="e2"),
        wiki=FakeProvider("wikipedia", [src("wikipedia", "W1", "https://wiki.org/W")]),
    )
    res = r.research(ResearchHandoff("Explain quantum entanglement", reason="definition"))
    assert res.success is True
    assert res.synthesized == "SYNTH-ANSWER"
    assert any("e1" in e for e in res.errors) and any("e2" in e for e in res.errors)


def test_all_providers_fail_is_controlled_failure():
    r = build_router(
        tavily=FakeProvider("tavily", error="down"),
        ddg=FakeProvider("duckduckgo", error="down"),
        wiki=FakeProvider("wikipedia", error="down"),
    )
    res = r.research(ResearchHandoff("What happened to NIFTY today?"))
    # Controlled failure: no fabricated current answer, no exception escaping.
    assert res.success is False
    assert res.synthesized == ""
    assert res.sources == []
    assert len(res.errors) >= 1


def test_no_evidence_without_synthesis_is_controlled_failure():
    """Even with evidence, if synthesis yields nothing -> controlled failure."""
    r = build_router(
        tavily=FakeProvider("tavily", [src("tavily", "T1", "https://t.com/1")]),
        synth=StubSynthesizer(answer=""),
    )
    res = r.research(ResearchHandoff("Latest news"))
    assert res.success is False
    assert res.synthesized == ""


# ---------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------

def test_dedup_canonicalizes_www_slash_and_scheme():
    r = build_router()
    dups = [
        src("tavily", "A", "https://example.com/article"),
        src("duckduckgo", "A2", "https://www.example.com/article/"),  # same canonical
        src("wikipedia", "B", "https://example.org/other"),
        src("tavily", "C", "http://example.com/article"),  # scheme differs -> separate
    ]
    ded = r._dedupe(dups)
    urls = {s.url for s in ded}
    assert len(ded) == 3  # two collide on canonical, plus other, plus scheme-variant
    # The canonicalizer is deterministic across the www/ slash variants.
    seen_canonical = set()
    for s in dups[:2]:
        seen_canonical.add(_canonical_url(s.url))
    assert len(seen_canonical) == 1


def test_dedup_same_url_from_multiple_providers():
    r = build_router()
    dups = [
        src("tavily", "A", "https://example.com/article"),
        src("duckduckgo", "A", "https://example.com/article"),
    ]
    assert len(r._dedupe(dups)) == 1


# ---------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------

def test_ranking_provider_weight_order_when_equal():
    """When relevance/freshness are otherwise equal, provider weight drives order:
    Tavily > Wikipedia > DuckDuckGo."""
    r = build_router()
    sources = [
        src("duckduckgo", "D", "https://d.com/1"),
        src("wikipedia", "W", "https://w.org/1"),
        src("tavily", "T", "https://t.com/1"),
    ]
    ranked = r._rank(sources, "some general query")
    assert [s.provider for s in ranked] == ["tavily", "wikipedia", "duckduckgo"]


def test_ranking_freshness_bonus_for_current_query():
    r = build_router()
    old = src("tavily", "old", "https://a.com/old", score=0.9, date="2020-01-01")
    fresh = src("tavily", "fresh", "https://a.com/fresh", score=0.8, date="2026-08-01")
    ranked = r._rank([old, fresh], "latest news today")
    assert ranked[0].title == "fresh"


def test_ranking_no_invented_dates():
    """A provider that returns no date must keep published_date empty; the
    ranking must not fabricate one."""
    r = build_router()
    s = src("duckduckgo", "no-date", "https://d.com/1", date="")
    ranked = r._rank([s], "latest news today")
    assert ranked[0].published_date == ""


# ---------------------------------------------------------------
# Source metadata & serialization
# ---------------------------------------------------------------

def test_metadata_preserved_and_missing_is_tolerated():
    r = build_router(
        tavily=FakeProvider(
            "tavily",
            [
                src("tavily", "Full", "https://t.com/full", "snippet", "2026-08-01", 0.9),
                ResearchSource(provider="tavily", title="Minimal", url="https://t.com/min"),  # missing snippet/date
            ],
        )
    )
    res = r.research(ResearchHandoff("News"))
    assert res.success
    full = next(s for s in res.sources if s.title == "Full")
    assert full.snippet == "snippet" and full.published_date == "2026-08-01" and full.score == 0.9
    minimal = next(s for s in res.sources if s.title == "Minimal")
    assert minimal.snippet == "" and minimal.published_date == ""


def test_serialization_no_credential_leak():
    r = build_router(
        tavily=FakeProvider("tavily", [src("tavily", "T", "https://t.com/1")]),
    )
    res = r.research(ResearchHandoff("News"))
    flat = repr(res.to_dict())
    assert "tvly-" not in flat
    assert "api_key" not in flat.lower()
    # ProviderRun serialization is also safe.
    for p in res.provider_results:
        flat_p = repr(p.to_dict())
        assert "tvly-" not in flat_p and "api_key" not in flat_p.lower()


def test_provider_run_serializes_safely():
    run = ProviderRun(provider="tavily", success=True, source_count=2)
    assert run.to_dict() == {
        "provider": "tavily",
        "success": True,
        "source_count": 2,
        "error": "",
    }
