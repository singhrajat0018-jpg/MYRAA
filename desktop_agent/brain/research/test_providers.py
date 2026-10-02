"""
EPIC-09 deterministic provider mapping tests.

The real provider classes are exercised with MOCKED underlying clients/SDKs so no
network is touched. Verifies title/url/snippet/published_date/score are mapped
only when the provider returned them — never invented, never leaked.
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.research import providers as P


# ---------------------------------------------------------------
# Tavily
# ---------------------------------------------------------------

def test_tavily_maps_results_and_never_invents_metadata():
    provider = P.TavilyResearchProvider.__new__(P.TavilyResearchProvider)

    class FakeClient:
        def search(self, **kwargs):
            assert kwargs["search_depth"] == "basic"
            return {
                "results": [
                    {
                        "url": "https://nvidia.com/news",
                        "title": "NVIDIA news",
                        "content": "Some snippet",
                        "published_date": "2026-08-01",
                        "score": 0.92,
                    },
                    {
                        "url": "https://example.com/min",
                        "title": "Minimal",
                        # no content/date/score -> must stay empty/0.0
                    },
                ]
            }

    provider._client = FakeClient()
    sources = provider.search("Latest NVIDIA news", 5)
    assert len(sources) == 2

    full = sources[0]
    assert full.provider == "tavily"
    assert full.url == "https://nvidia.com/news"
    assert full.title == "NVIDIA news"
    assert full.snippet == "Some snippet"
    assert full.published_date == "2026-08-01"
    assert full.score == 0.92

    minimal = sources[1]
    assert minimal.snippet == ""
    assert minimal.published_date == ""
    assert minimal.score == 0.0


def test_tavily_drops_results_without_url():
    provider = P.TavilyResearchProvider.__new__(P.TavilyResearchProvider)

    class FakeClient:
        def search(self, **kwargs):
            return {"results": [{"title": "no-url"}]}

    provider._client = FakeClient()
    assert provider.search("q", 5) == []


# ---------------------------------------------------------------
# DuckDuckGo (keyless)
# ---------------------------------------------------------------

def test_duckduckgo_maps_and_has_no_invented_dates(monkeypatch):
    class FakeDDGS:
        def __init__(self, timeout=10.0):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def text(self, query, max_results=None):
            return [
                {"href": "https://ddg.com/a", "title": "A", "body": "snippet a"},
                {"href": "https://ddg.com/b", "title": "B"},  # no body
            ]

    import duckduckgo_search
    monkeypatch.setattr(duckduckgo_search, "DDGS", FakeDDGS)
    provider = P.DuckDuckGoResearchProvider()
    sources = provider.search("query", 5)
    assert len(sources) == 2
    a = sources[0]
    assert a.provider == "duckduckgo"
    assert a.url == "https://ddg.com/a"
    assert a.snippet == "snippet a"
    # DuckDuckGo returns no dates -> must remain empty (not invented).
    assert a.published_date == ""
    assert sources[1].snippet == ""


# ---------------------------------------------------------------
# Wikipedia (keyless)
# ---------------------------------------------------------------

def test_wikipedia_maps_search_results():
    provider = P.WikipediaResearchProvider.__new__(P.WikipediaResearchProvider)
    provider._timeout = 5.0

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "query": {
                    "search": [
                        {"title": "Rayleigh scattering", "snippet": "<span>Light scatter</span>"}
                    ]
                }
            }

    class FakeHTTP:
        def __init__(self, resp):
            self._resp = resp
            self.last_params = None

        def get(self, url, params=None, timeout=None):
            self.last_params = params
            # For the list=search call return hits; the intro extract call is
            # exercised separately.
            return FakeResp()

    http = FakeHTTP(FakeResp())
    provider._http = http
    sources = provider.search("Rayleigh scattering", 3)
    assert len(sources) == 1
    s = sources[0]
    assert s.provider == "wikipedia"
    assert s.title == "Rayleigh scattering"
    assert "https://en.wikipedia.org/wiki/Rayleigh_scattering" in s.url
    # HTML tags stripped from the snippet.
    assert "<span>" not in s.snippet and "<" not in s.snippet
    assert s.published_date == ""


def test_wikipedia_intro_failure_is_graceful():
    provider = P.WikipediaResearchProvider.__new__(P.WikipediaResearchProvider)
    provider._timeout = 5.0

    class BoomResp:
        def raise_for_status(self):
            raise RuntimeError("HTTP error")

    class BoomHTTP:
        def get(self, url, params=None, timeout=None):
            return BoomResp()

    provider._http = BoomHTTP()
    # A transport failure propagates so the ResearchRouter can record it and
    # fail over (provider-level contract). It must not raise a fake success.
    with pytest.raises(RuntimeError):
        provider.search("anything", 3)
