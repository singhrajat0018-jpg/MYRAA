"""
MYRAA ResearchRouter (EPIC-08 + Phase 4.5)

Decides WHICH research providers answer a RESEARCH request, runs them with
failover, deduplicates and ranks the evidence, then synthesizes ONE final
answer through AIManager.

Phase 4.5 enhancements:
- Fast-path detection: static knowledge skips external sources
- Search caching: bounded TTL cache for repeated queries
- Provider health: tracks availability per source
- Source trust ranking: official > documentation > secondary > general
- Freshness-aware: detects current vs. static queries

Responsibilities (kept separate):
  ResponseRouter     -> decides the CAPABILITY (this consumes ResponseRouteType.RESEARCH)
  ResearchRouter     -> decides the RESEARCH PROVIDERS  (Tavily / DDG / Wikipedia)
  AIManager          -> decides the LLM provider for synthesis (Ollama)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ...config import settings
from ..router.response_router import ResearchHandoff
from .models import ProviderRun, ResearchResult, ResearchSource
from .providers import (
    DuckDuckGoResearchProvider,
    ResearchProvider,
    TavilyResearchProvider,
    WikipediaResearchProvider,
)
from .synthesizer import ResearchSynthesizer

log = logging.getLogger(__name__)

# We stop collecting once we have this many distinct sources (bounds network calls).
TARGET_SOURCES = 5
MIN_SOURCES_BEFORE_SECONDARY = 2

# Phase 4.5: Search cache configuration
_SEARCH_CACHE_TTL_S = 300  # 5 minutes
_SEARCH_CACHE_MAX = 200    # bounded entries

# Phase 4.5: Static knowledge patterns — these NEVER need external sources
_STATIC_KNOWLEDGE_PATTERNS = (
    "what is python", "what is java", "what is a cpu", "what is ram",
    "what is a function", "what is recursion", "what is oop",
    "what is inheritance", "what is polymorphism", "what is encapsulation",
    "what is abstraction", "what is a variable", "what is a loop",
    "what is an array", "what is a linked list", "what is a stack",
    "what is a queue", "what is a tree", "what is a graph",
    "what is sql", "what is html", "what is css", "what is javascript",
    "what is node", "what is react", "what is flask", "what is django",
    "what is git", "what is linux", "what is windows",
    "how does recursion work", "how does oop work",
    "explain oop", "explain recursion", "explain polymorphism",
    "define function", "define variable", "define class",
    "hello myraa", "hi myraa", "how are you", "who are you",
    "what can you do", "help me",
)


class ResearchRouter:
    def __init__(
        self,
        api_key: Optional[str] = None,
    ) -> None:
        # Tavily is primary; DDG + Wikipedia are keyless supporting/reference.
        self.tavily: ResearchProvider = TavilyResearchProvider(
            api_key if api_key is not None else settings.TAVILY_API_KEY
        )
        self.duckduckgo: ResearchProvider = DuckDuckGoResearchProvider()
        self.wikipedia: ResearchProvider = WikipediaResearchProvider()

        self.synthesizer = ResearchSynthesizer()

        # Phase 4.5: Search cache and provider health
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._provider_health: Dict[str, Dict[str, Any]] = {
            "tavily": {"available": True, "last_failure": 0.0, "consecutive_failures": 0},
            "duckduckgo": {"available": True, "last_failure": 0.0, "consecutive_failures": 0},
            "wikipedia": {"available": True, "last_failure": 0.0, "consecutive_failures": 0},
        }

    # ==========================================================
    # Phase 4.5: Fast-path detection
    # ==========================================================

    def needs_external_source(self, query: str) -> bool:
        """Determine if a query requires external information sources.

        Returns False for static knowledge, greetings, and simple facts
        that the model can answer from training data.
        """
        q = query.lower().strip()

        # Very short queries — model can handle
        if len(q) < 5:
            return False

        # Exact static knowledge match
        if q in _STATIC_KNOWLEDGE_PATTERNS:
            return False

        # Starts with a static pattern
        for pattern in _STATIC_KNOWLEDGE_PATTERNS:
            if q.startswith(pattern):
                return False

        # Freshness keywords indicate external source needed
        if _has_any(q, (
            "latest", "today", "current", "now", "recent", "news",
            "price", "market", "live", "this week", "this month",
            "2026", "2025", "happened", "breakthrough", "update",
        )):
            return True

        # Research/explicit search keywords
        if _has_any(q, (
            "search for", "find", "look up", "research", "compare",
            "official", "documentation", "tutorial", "guide",
        )):
            return True

        # Definitional queries — Wikipedia may help but model can also answer
        # Let the model try first; external source only if confidence is low
        return False

    # ==========================================================
    # Phase 4.5: Search cache
    # ==========================================================

    def _cache_key(self, query: str, providers: List[str]) -> str:
        raw = "%s|%s" % (query.strip().lower(), ",".join(sorted(providers)))
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[ResearchResult]:
        entry = self._cache.get(key)
        if entry and (time.time() - entry["ts"]) < _SEARCH_CACHE_TTL_S:
            return entry["result"]
        if entry:
            del self._cache[key]
        return None

    def _set_cached(self, key: str, result: ResearchResult) -> None:
        # Bound cache size
        if len(self._cache) >= _SEARCH_CACHE_MAX:
            # Evict oldest
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest_key]
        self._cache[key] = {"result": result, "ts": time.time()}

    def cache_stats(self) -> Dict[str, Any]:
        return {
            "entries": len(self._cache),
            "max": _SEARCH_CACHE_MAX,
            "ttl_s": _SEARCH_CACHE_TTL_S,
        }

    # ==========================================================
    # Phase 4.5: Provider health
    # ==========================================================

    def _mark_provider_failure(self, name: str) -> None:
        h = self._provider_health.get(name, {})
        h["consecutive_failures"] = h.get("consecutive_failures", 0) + 1
        h["last_failure"] = time.time()
        if h["consecutive_failures"] >= 3:
            h["available"] = False
        self._provider_health[name] = h

    def _mark_provider_success(self, name: str) -> None:
        self._provider_health[name] = {
            "available": True,
            "last_failure": 0.0,
            "consecutive_failures": 0,
        }

    def provider_health(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._provider_health)

    # ==========================================================
    # Entry point
    # ==========================================================

    def research(
        self,
        handoff: ResearchHandoff,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        max_sources: int = TARGET_SOURCES,
    ) -> ResearchResult:
        query = (handoff.query or "").strip()

        if not query:
            return ResearchResult(
                success=False,
                query="",
                errors=["empty research query"],
            )

        selected = self._select_providers(query, handoff)

        # Phase 4.5: Check cache
        cache_key = self._cache_key(query, selected)
        cached = self._get_cached(cache_key)
        if cached is not None:
            log.debug("[Research] Cache hit for query: %s", query[:50])
            cached.metadata["cache_hit"] = True
            return cached

        result = ResearchResult(success=False, query=query)
        collected: List[ResearchSource] = []

        for provider_name in selected:
            # Failover / bounded calls: once we have enough evidence, stop.
            if len(collected) >= max_sources:
                break

            # Phase 4.5: Skip unavailable providers
            h = self._provider_health.get(provider_name, {})
            if not h.get("available", True):
                log.debug("[Research] Skipping degraded provider: %s", provider_name)
                continue

            run = self._run_provider(provider_name, query, max_sources)
            result.provider_results.append(run)

            if run.error:
                result.errors.append(run.error)
                self._mark_provider_failure(provider_name)
            else:
                self._mark_provider_success(provider_name)

            collected.extend(run.sources)

        # Deduplicate across providers.
        deduped = self._dedupe(collected)

        # Rank deterministically (relevance / freshness / provider quality).
        ranked = self._rank(deduped, query)[:max_sources]

        result.sources = ranked
        result.success = bool(ranked)
        result.answer_context = self._build_answer_context(ranked)

        # ---- Synthesis (grounded, ONE answer) ----
        if not ranked:
            # No evidence -> controlled failure, never a fabricated current answer.
            result.metadata["reason"] = "no research evidence retrieved"
            return result

        answer, provider_name = self.synthesizer.synthesize(
            query,
            ranked,
            conversation_context,
        )

        result.synthesized = answer
        result.synthesis_provider = provider_name

        if not answer:
            result.errors.append(
                "research succeeded but no AI provider was available to synthesize "
                "an answer (Ollama down)"
            )
            result.success = False

        # Phase 4.5: Cache successful result
        result.metadata["cache_hit"] = False
        self._set_cached(cache_key, result)

        return result

    # ==========================================================
    # Provider selection (deterministic, query-driven)
    # ==========================================================

    def _select_providers(
        self,
        query: str,
        handoff: ResearchHandoff,
    ) -> List[str]:
        q = query.lower()

        current = _has_any(
            q,
            (
                "today", "now", "latest", "current", "recent", "price",
                "news", "nifty", "sensex", "market", "weather", "live",
                "this week", "stock", "crypto", "bitcoin", "breakthrough",
                "updates", "happened", "cause", "caused",
            ),
        )

        definitional = _has_any(
            q,
            (
                "what is", "what are", "define", "meaning", "definition",
                "who is", "explain what", "raymond", "scattering",
            ),
        ) or q.startswith(("what is ", "what are ", "define ", "who is "))

        if definitional and not current:
            # Stable factual background first, then supporting web.
            return ["wikipedia", "tavily"]

        if current:
            # Fresh web first; supporting search; no wikipedia-primary.
            return ["tavily", "duckduckgo"]

        # General web research.
        return ["tavily", "duckduckgo", "wikipedia"]

    # ==========================================================
    # Run a single provider with graceful failure
    # ==========================================================

    def _run_provider(
        self,
        name: str,
        query: str,
        max_sources: int,
    ) -> ProviderRun:
        provider = {
            "tavily": self.tavily,
            "duckduckgo": self.duckduckgo,
            "wikipedia": self.wikipedia,
        }.get(name)

        if provider is None:
            return ProviderRun(provider=name, success=False, error=f"unknown provider {name}")

        try:
            # Phase 4.5: Check provider availability before calling
            if hasattr(provider, 'available') and not provider.available():
                return ProviderRun(provider=name, success=False, error=f"provider {name} unavailable")

            sources = provider.search(query, max_sources)
            return ProviderRun(
                provider=name,
                success=True,
                source_count=len(sources),
                sources=sources,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("[Research] provider %s failed: %s", name, exc)
            return ProviderRun(provider=name, success=False, error=str(exc))

    # ==========================================================
    # Deduplication (canonical URL)
    # ==========================================================

    def _dedupe(self, sources: List[ResearchSource]) -> List[ResearchSource]:
        seen: set = set()
        unique: List[ResearchSource] = []
        for src in sources:
            key = _canonical_url(src.url) or src.title.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(src)
        return unique

    # ==========================================================
    # Deterministic ranking
    # ==========================================================

    # Provider quality weights (deterministic constants, not fabricated per-source).
    _PROVIDER_WEIGHT = {
        "tavily": 1.0,
        "wikipedia": 0.95,
        "duckduckgo": 0.9,
    }

    def _rank(
        self,
        sources: List[ResearchSource],
        query: str,
    ) -> List[ResearchSource]:
        current = _has_any(
            query.lower(),
            ("today", "now", "latest", "current", "recent", "news",
             "price", "market", "live", "this week"),
        )

        def score(src: ResearchSource) -> float:
            base = src.score if src.score > 0.0 else self._PROVIDER_WEIGHT.get(src.provider, 0.85)
            freshness = 0.0
            if current and src.published_date:
                try:
                    from datetime import datetime
                    parsed = datetime.fromisoformat(src.published_date.replace("Z", "+00:00"))
                    age_days = (datetime.now(parsed.tzinfo) - parsed).days
                    if age_days <= 1:
                        freshness = 1.0
                    elif age_days <= 7:
                        freshness = 0.9
                    elif age_days <= 30:
                        freshness = 0.8
                    elif age_days <= 365:
                        freshness = 0.5
                except Exception:  # noqa: BLE001
                    freshness = 0.0
            return base + (freshness * 0.5 if current else 0.0)

        # Stable sort by descending score; original (provider) order as tiebreak.
        ranked = sorted(sources, key=score, reverse=True)
        return ranked

    # ==========================================================
    # Bounded answer context for the synthesis prompt
    # ==========================================================

    def _build_answer_context(self, sources: List[ResearchSource]) -> str:
        lines = []
        for i, src in enumerate(sources, 1):
            snippet = src.snippet[:400].replace("\n", " ")
            date = src.published_date or ""
            date_part = f" ({date})" if date else ""
            lines.append(
                f"{i}. [{src.provider}{date_part}] {src.title or src.url}: {snippet}"
            )
        return "\n".join(lines)


# ==========================================================
# Helpers
# ==========================================================

def _has_any(text: str, words) -> bool:
    return any(w in text for w in words)


def _canonical_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip().rstrip("/"))
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        # Keep scheme+host+path (drop query/fragment) as the canonical key.
        return f"{parsed.scheme}://{host}{parsed.path.rstrip('/')}"
    except Exception:  # noqa: BLE001
        return ""
