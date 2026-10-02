"""Phase 4.5 — Information Router + Source Selection Tests."""
import sys
import os
import time

sys.path.insert(0, os.getcwd())
from desktop_agent.config.settings import *

def test_phase_4_5_information():
    print("=" * 70)
    print("PHASE 4.5 — INFORMATION ROUTER TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            print("  PASS: %s" % name)
            passed += 1
        else:
            print("  FAIL: %s" % name)
            failed += 1

    # ================================================================
    # 1. ResearchRouter exists and is canonical
    # ================================================================
    print("\n[1] ResearchRouter exists and is canonical")

    from desktop_agent.brain.research.research_router import ResearchRouter
    rr = ResearchRouter()
    check("ResearchRouter created", rr is not None)
    check("has tavily provider", hasattr(rr, 'tavily'))
    check("has duckduckgo provider", hasattr(rr, 'duckduckgo'))
    check("has wikipedia provider", hasattr(rr, 'wikipedia'))
    check("has synthesizer", hasattr(rr, 'synthesizer'))

    # ================================================================
    # 2. Fast-path detection
    # ================================================================
    print("\n[2] Fast-path detection (needs_external_source)")

    # Static knowledge — NO external source needed
    static_queries = [
        "Hello Myraa",
        "Hi",
        "How are you?",
        "What is Python?",
        "What is recursion?",
        "Explain OOP.",
        "What is a CPU?",
        "Define function.",
    ]
    for q in static_queries:
        check("'%s' -> NO external" % q, not rr.needs_external_source(q))

    # Current information — external source needed
    current_queries = [
        "Latest Python version",
        "Current stock price of Apple",
        "Today's news",
        "What happened today?",
        "Recent breakthroughs in AI",
        "Market live updates",
    ]
    for q in current_queries:
        check("'%s' -> external needed" % q, rr.needs_external_source(q))

    # Research queries — external source needed
    research_queries = [
        "Search for Python documentation",
        "Find official NVIDIA page",
        "Research latest AI models",
        "Compare React and Vue",
    ]
    for q in research_queries:
        check("'%s' -> external needed" % q, rr.needs_external_source(q))

    # ================================================================
    # 3. Provider selection
    # ================================================================
    print("\n[3] Provider selection")

    from desktop_agent.brain.router.response_router import ResearchHandoff

    # Definitional -> Wikipedia first
    handoff = ResearchHandoff(query="What is Alan Turing?")
    providers = rr._select_providers("what is alan turing", handoff)
    check("definitional -> wikipedia first", providers[0] == "wikipedia")

    # Current -> Tavily first
    handoff = ResearchHandoff(query="Latest news about AI")
    providers = rr._select_providers("latest news about ai", handoff)
    check("current -> tavily first", providers[0] == "tavily")

    # General -> Tavily + DDG
    handoff = ResearchHandoff(query="How to learn machine learning")
    providers = rr._select_providers("how to learn machine learning", handoff)
    check("general -> tavily in providers", "tavily" in providers)
    check("general -> duckduckgo in providers", "duckduckgo" in providers)

    # ================================================================
    # 4. Search cache
    # ================================================================
    print("\n[4] Search cache")

    stats = rr.cache_stats()
    check("cache_stats has entries", "entries" in stats)
    check("cache_stats has max", "max" in stats)
    check("cache_stats has ttl_s", "ttl_s" in stats)
    check("cache initially empty", stats["entries"] == 0)

    # Cache key is deterministic
    key1 = rr._cache_key("test query", ["tavily"])
    key2 = rr._cache_key("test query", ["tavily"])
    check("cache key deterministic", key1 == key2)

    # Different queries produce different keys
    key3 = rr._cache_key("other query", ["tavily"])
    check("different queries -> different keys", key1 != key3)

    # ================================================================
    # 5. Provider health
    # ================================================================
    print("\n[5] Provider health")

    health = rr.provider_health()
    check("health has tavily", "tavily" in health)
    check("health has duckduckgo", "duckduckgo" in health)
    check("health has wikipedia", "wikipedia" in health)

    for name, h in health.items():
        check("health %s has available" % name, "available" in h)
        check("health %s has consecutive_failures" % name, "consecutive_failures" in h)

    # Simulate failure
    rr._mark_provider_failure("tavily")
    h = rr.provider_health()["tavily"]
    check("tavily failures incremented", h["consecutive_failures"] == 1)

    # Simulate success resets
    rr._mark_provider_success("tavily")
    h = rr.provider_health()["tavily"]
    check("tavily success resets failures", h["consecutive_failures"] == 0)
    check("tavily available after success", h["available"] is True)

    # ================================================================
    # 6. ResponseRouter routing
    # ================================================================
    print("\n[6] ResponseRouter routing")

    from desktop_agent.brain.router.response_router import ResponseRouter, ResponseRouteType
    from desktop_agent.brain.semantic.semantic_models import SemanticTask, Intent

    router = ResponseRouter()

    # Greeting -> LOCAL_FAST
    task = SemanticTask(raw_text="Hello Myraa", intent=Intent.CHAT)
    route = router.route(task)
    check("greeting -> LOCAL_FAST", route.route == ResponseRouteType.LOCAL_FAST)

    # Question -> BRAIN
    task = SemanticTask(raw_text="What is Python?", intent=Intent.QUESTION)
    route = router.route(task)
    check("question -> BRAIN", route.route == ResponseRouteType.BRAIN)

    # Search web -> RESEARCH
    task = SemanticTask(raw_text="Latest news", intent=Intent.SEARCH_WEB)
    route = router.route(task)
    check("search_web -> RESEARCH", route.route == ResponseRouteType.RESEARCH)

    # ================================================================
    # 7. No duplicate router abstractions
    # ================================================================
    print("\n[7] No duplicate router abstractions")

    with open("desktop_agent/brain/research/research_router.py", "r") as f:
        content = f.read()
    check("single ResearchRouter class", content.count("class ResearchRouter") == 1)

    # ================================================================
    # 8. Legacy knowledge/ is NOT used
    # ================================================================
    print("\n[8] Legacy knowledge/ is NOT used")

    with open("desktop_agent/brain/brain_engine.py", "r") as f:
        be_content = f.read()
    check("BrainEngine imports ResearchRouter", "ResearchRouter" in be_content)
    check("BrainEngine does NOT import SearchRouter", "SearchRouter" not in be_content)
    check("BrainEngine does NOT import IntelligenceEngine", "IntelligenceEngine" not in be_content)

    # ================================================================
    # 9. Provider health integration
    # ================================================================
    print("\n[9] Provider health integration")

    from desktop_agent.brain.ai.ai_manager import AIManager
    am = AIManager()
    health = am.provider_health()
    check("AIManager.provider_health() returns list", isinstance(health, list))
    check("AIManager has >= 3 providers", len(health) >= 3)

    for h in health:
        check("provider %s has healthy" % h["provider"], "healthy" in h)
        check("provider %s has model" % h["provider"], "model" in h)

    # ================================================================
    # 10. Fast-path in BrainEngine
    # ================================================================
    print("\n[10] Fast-path in BrainEngine")

    with open("desktop_agent/brain/brain_engine.py", "r") as f:
        be_content = f.read()
    check("fast-path check in _handle_research", "needs_external_source" in be_content)
    check("fast-path skips to LLM", "static knowledge fast-path" in be_content)

    # ================================================================
    # Results
    # ================================================================
    print("\n" + "=" * 70)
    print("RESULTS: %d passed, %d failed" % (passed, failed))
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = test_phase_4_5_information()
    sys.exit(0 if success else 1)
