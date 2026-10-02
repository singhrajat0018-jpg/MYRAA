"""
MYRAA Research providers (EPIC-08)

Tavily (primary real-time web) / DuckDuckGo (supporting, keyless) / Wikipedia
(reference, keyless). Each returns a list of ResearchSource with only the
metadata the provider actually returned.

These are RESEARCH providers. They are NOT LLM providers and are never offered
to AIManager.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List

from .models import ResearchSource

log = logging.getLogger(__name__)


class ResearchProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def search(
        self,
        query: str,
        max_sources: int,
        timeout: float = 10.0,
    ) -> List[ResearchSource]:
        raise NotImplementedError


# ==========================================================
# Tavily (primary)
# ==========================================================

class TavilyResearchProvider(ResearchProvider):
    name = "tavily"

    def __init__(self, api_key: str):
        from tavily import TavilyClient
        self._client = TavilyClient(api_key=api_key)

    def search(
        self,
        query: str,
        max_sources: int,
        timeout: float = 10.0,
    ) -> List[ResearchSource]:
        resp = self._client.search(
            query=query,
            search_depth="basic",
            max_results=max_sources,
            include_answer=False,
        )
        results = resp.get("results", []) if isinstance(resp, dict) else []
        sources: List[ResearchSource] = []
        for item in results:
            url = item.get("url", "") or ""
            if not url:
                continue
            sources.append(
                ResearchSource(
                    provider=self.name,
                    title=item.get("title", "") or "",
                    url=url,
                    snippet=item.get("content", "") or "",
                    published_date=item.get("published_date", "") or "",
                    score=float(item.get("score") or 0.0),
                )
            )
        return sources


# ==========================================================
# DuckDuckGo (supporting / fallback, no API key)
# ==========================================================

class DuckDuckGoResearchProvider(ResearchProvider):
    name = "duckduckgo"

    def search(
        self,
        query: str,
        max_sources: int,
        timeout: float = 10.0,
    ) -> List[ResearchSource]:
        from duckduckgo_search import DDGS

        sources: List[ResearchSource] = []
        # DuckDuckGo occasionally returns empty on the first attempt; retry once.
        for attempt in range(2):
            try:
                with DDGS(timeout=timeout) as ddgs:
                    raw = list(ddgs.text(query, max_results=max_sources))
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 1:
                    raise
                log.warning("[Research:ddg] attempt %s failed, retrying: %s", attempt + 1, exc)
                raw = []

        for item in raw:
            url = (item or {}).get("href") or ""
            if not url:
                continue
            sources.append(
                ResearchSource(
                    provider=self.name,
                    title=(item.get("title") or ""),
                    url=url,
                    snippet=(item.get("body") or ""),
                    published_date="",  # duckduckgo_search does not return dates
                )
            )
        return sources


# ==========================================================
# Wikipedia (reference / stable background, no API key)
# ==========================================================

class WikipediaResearchProvider(ResearchProvider):
    name = "wikipedia"

    _API = "https://en.wikipedia.org/w/api.php"

    def __init__(self, timeout: float = 10.0):
        import requests
        self._http = requests.Session()
        self._timeout = timeout
        # MediaWiki rejects generic clients (403) without a descriptive UA.
        self._http.headers.update(
            {"User-Agent": "MyraaDesktopAssistant/1.0 (research; contact: localhost)"}
        )

    def search(
        self,
        query: str,
        max_sources: int,
        timeout: float = 10.0,
    ) -> List[ResearchSource]:
        # 1) Search for matching article titles.
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": max(1, max_sources),
        }
        data = self._get(params)
        hits = (
            (data.get("query", {}).get("search") or [])
            if isinstance(data, dict)
            else []
        )

        sources: List[ResearchSource] = []
        for hit in hits:
            title = hit.get("title") or ""
            if not title:
                continue
            snippet = self._extract_intro(title) or (hit.get("snippet") or "")
            # snippet arrives with HTML entities/spans from the API.
            import re
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            sources.append(
                ResearchSource(
                    provider=self.name,
                    title=title,
                    url=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    snippet=snippet,
                    published_date="",  # Wikipedia does not expose a simple date here
                )
            )
        return sources

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._http.get(self._API, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def _extract_intro(self, title: str) -> str:
        """Plain-text intro of an article (stable background snippet)."""
        try:
            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": True,
                "exintro": True,
                "redirects": 1,
                "format": "json",
                "titles": title,
            }
            data = self._get(params)
            pages = data.get("query", {}).get("pages") or {}
            for page in pages.values():
                extract = page.get("extract")
                if extract:
                    return extract[:2000]
        except Exception as exc:  # noqa: BLE001
            log.warning("[Research:wikipedia] intro extract failed: %s", exc)
        return ""
