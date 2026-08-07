"""
MYRAA Knowledge Diagnostic

Tests

- Knowledge Manager
- Intelligence Engine
- Search Orchestrator
- Provider Registry
- Provider Manager
- Tavily Provider
- Configuration
"""

from __future__ import annotations

import traceback
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class KnowledgeTest:

    def __init__(self):

        self.total = 0
        self.passed = 0
        self.failed = 0

    # -----------------------------------------------------

    def run(self, name, func):

        self.total += 1

        print("-" * 60)
        print(name)
        print("-" * 60)

        try:

            func()

            self.passed += 1

            print("PASS")

        except Exception:

            self.failed += 1

            print("FAIL")

            traceback.print_exc()

        print()

    # -----------------------------------------------------

    def summary(self):

        print("=" * 60)
        print("Knowledge Test Summary")
        print("=" * 60)

        print(f"Passed : {self.passed}")
        print(f"Failed : {self.failed}")
        print(f"Total  : {self.total}")

        if self.total:

            print(
                f"Health : {(self.passed/self.total)*100:.1f}%"
            )

    # =====================================================
    # Config
    # =====================================================

    def test_config(self):

        from desktop_agent.config.settings import (
            TAVILY_API_KEY,
        )

        assert TAVILY_API_KEY

        print("TAVILY_API_KEY OK")



    # =====================================================
    # Intelligence Engine
    # =====================================================

    def test_intelligence_engine(self):

        from desktop_agent.brain.knowledge.intelligence.intelligence_engine import (
            IntelligenceEngine,
        )

        engine = IntelligenceEngine()

        assert engine is not None

        print("IntelligenceEngine OK")

    # =====================================================
    # Search Orchestrator
    # =====================================================

    def test_search_orchestrator(self):

        from unittest.mock import MagicMock

        from desktop_agent.brain.knowledge.search.search_engine import (
            SearchEngine,
        )

        db = MagicMock()

        engine = SearchEngine(

            db=db,

        )

        assert engine is not None

        print("SearchEngine OK")

    # =====================================================
    # Provider Registry
    # =====================================================

    def test_provider_registry(self):

        from desktop_agent.brain.knowledge.providers.provider_registry import (
            ProviderRegistry,
        )

        registry = ProviderRegistry()

        assert registry is not None

        print("ProviderRegistry OK")

    # =====================================================
    # Provider Manager
    # =====================================================

    def test_provider_manager(self):

        from desktop_agent.brain.knowledge.providers.provider_manager import (
            ProviderManager,
        )

        manager = ProviderManager()

        assert manager is not None

        print("ProviderManager OK")

    # =====================================================
    # Tavily Provider
    # =====================================================

    def test_tavily_provider(self):

        from desktop_agent.config.settings import (
            TAVILY_API_KEY,
        )

        from desktop_agent.brain.knowledge.providers.tavily_provider import (
            TavilyProvider,
        )

        provider = TavilyProvider(

            api_key=TAVILY_API_KEY,

        )

        assert provider is not None

        print("TavilyProvider OK")


# ==========================================================
# Main
# ==========================================================

def main():

    test = KnowledgeTest()

    test.run(

        "Configuration",

        test.test_config,

    )



    test.run(

        "Intelligence Engine",

        test.test_intelligence_engine,

    )

    test.run(
        "Search Engine",
        test.test_search_orchestrator,
    )

    test.run(

        "Provider Registry",

        test.test_provider_registry,

    )

    test.run(

        "Provider Manager",

        test.test_provider_manager,

    )

    test.run(

        "Tavily Provider",

        test.test_tavily_provider,

    )

    test.summary()


if __name__ == "__main__":

    main()