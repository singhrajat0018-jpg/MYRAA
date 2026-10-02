"""MYRAA News Provider — Tavily-based news search.

Fetches current news using Tavily search API with news-specific queries.
Deduplicates, ranks by freshness, and formats for natural response.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """A single news item."""
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "published_date": self.published_date,
            "score": self.score,
        }


@dataclass
class NewsResult:
    """Aggregated news result."""
    items: List[NewsItem] = field(default_factory=list)
    query: str = ""
    source: str = "tavily"
    timestamp: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [i.to_dict() for i in self.items],
            "query": self.query,
            "source": self.source,
            "timestamp": self.timestamp,
            "count": len(self.items),
            "error": self.error,
        }

    def to_natural_response(self, max_items: int = 5) -> str:
        """Generate a natural language news summary."""
        if self.error:
            return f"News unavailable: {self.error}"
        if not self.items:
            return f"No recent news found for '{self.query}'."

        lines = [f"Here are the latest updates on '{self.query}':\n"]
        for i, item in enumerate(self.items[:max_items], 1):
            source_str = f" ({item.source})" if item.source else ""
            date_str = f" — {item.published_date}" if item.published_date else ""
            lines.append(f"{i}. {item.title}{source_str}{date_str}")
            if item.snippet:
                lines.append(f"   {item.snippet[:150]}")
            lines.append("")

        return "\n".join(lines)


class NewsProvider:
    """Fetches news using Tavily search API."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self.timeout = timeout
        self._cache: Dict[str, tuple[float, NewsResult]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _is_available(self) -> bool:
        return bool(self.api_key)

    def _build_query(self, text: str, category: Optional[str] = None) -> str:
        """Build a news-optimized search query."""
        # Strip common Hindi/Hinglish prefixes
        clean = text
        for prefix in ['bata', 'dikhao', 'suno', 'tell me', 'show me', 'what is', 'what are']:
            clean = clean.replace(prefix, '').strip()

        # Add "news" suffix if not present
        if 'news' not in clean.lower() and 'khabar' not in clean.lower():
            clean = f"{clean} news"

        # Add category filter
        if category:
            clean = f"{category} news {clean}"

        return clean.strip()

    def _extract_category(self, text: str) -> Optional[str]:
        """Extract news category from query."""
        t = text.lower()
        categories = {
            'technology': ['tech', 'technology', 'ai', 'artificial intelligence', 'machine learning', 'startup', 'software', 'coding'],
            'business': ['business', 'economy', 'market', 'stock', 'finance', 'investment', 'ipo'],
            'sports': ['sports', 'cricket', 'football', 'tennis', 'f1', 'match', 'game', 'world cup'],
            'world': ['world', 'international', 'global', 'war', 'politics', 'election'],
            'india': ['india', 'indian', 'delhi', 'mumbai', 'bangalore', 'hindustan'],
        }
        for cat, keywords in categories.items():
            if any(kw in t for kw in keywords):
                return cat
        return None

    def _deduplicate(self, items: List[NewsItem]) -> List[NewsItem]:
        """Deduplicate news items by URL and similar titles."""
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        result: List[NewsItem] = []

        for item in items:
            # Skip duplicate URLs
            if item.url in seen_urls:
                continue
            # Skip duplicate titles (fuzzy)
            title_key = item.title.lower().strip()[:50]
            if title_key in seen_titles:
                continue
            seen_urls.add(item.url)
            seen_titles.add(title_key)
            result.append(item)

        return result

    def _rank_by_freshness(self, items: List[NewsItem]) -> List[NewsItem]:
        """Rank items by freshness (newer = higher score)."""
        # Simple heuristic: items with dates get a boost
        for item in items:
            if item.published_date:
                item.score += 0.2
            if 'today' in (item.published_date or '').lower():
                item.score += 0.3
            if 'hour' in (item.published_date or '').lower():
                item.score += 0.4
        return sorted(items, key=lambda x: x.score, reverse=True)

    def fetch(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 8,
    ) -> NewsResult:
        """Fetch news using Tavily."""
        if not self._is_available():
            return NewsResult(
                query=query,
                error="Tavily API key not configured",
                timestamp=time.time(),
            )

        # Check cache
        cache_key = f"{query}:{category or 'all'}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        search_query = self._build_query(query, category)
        detected_category = category or self._extract_category(query)

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self.api_key)
            response = client.search(
                query=search_query,
                search_depth="basic",
                max_results=max_results,
                include_answer=False,
                topic="news" if detected_category else "general",
            )

            items: List[NewsItem] = []
            for r in response.get("results", []):
                items.append(NewsItem(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", "")[:300],
                    source=self._extract_source(r.get("url", "")),
                    published_date=r.get("published_date", ""),
                    score=r.get("score", 0.0),
                ))

            # Deduplicate and rank
            items = self._deduplicate(items)
            items = self._rank_by_freshness(items)

            result = NewsResult(
                items=items,
                query=query,
                source="tavily",
                timestamp=time.time(),
            )

            # Cache
            self._cache[cache_key] = (time.time(), result)
            return result

        except ImportError:
            log.warning("[News] tavily package not installed")
            return NewsResult(query=query, error="Tavily not installed", timestamp=time.time())
        except Exception as e:
            log.warning("[News] Error: %s", e)
            return NewsResult(query=query, error=str(e)[:200], timestamp=time.time())

    def _extract_source(self, url: str) -> str:
        """Extract source name from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            # Map common domains to readable names
            source_map = {
                'timesofindia.timesofindia.indiatimes.com': 'Times of India',
                'hindustantimes.com': 'Hindustan Times',
                'ndtv.com': 'NDTV',
                'bbc.com': 'BBC',
                'bbc.co.uk': 'BBC',
                'cnn.com': 'CNN',
                'reuters.com': 'Reuters',
                'techcrunch.com': 'TechCrunch',
                'theverge.com': 'The Verge',
                'arstechnica.com': 'Ars Technica',
                'wired.com': 'Wired',
                'github.blog': 'GitHub Blog',
                'medium.com': 'Medium',
                'espn.com': 'ESPN',
                'bloomberg.com': 'Bloomberg',
                'economictimes.com': 'Economic Times',
                'moneycontrol.com': 'MoneyControl',
            }
            for key, name in source_map.items():
                if key in domain:
                    return name
            # Use domain as source name
            return domain.split('.')[0].title()
        except Exception:
            return ""
