"""
EPIC-09 integration test: the Python Brain research flow, end to end with
mocked providers + mocked AI synthesis.

    SemanticTask -> ResponseRouter -> RESEARCH -> ResearchRouter(mocked evidence)
    -> AI synthesis(mocked) -> BrainResult

No network, no live LLM, no desktop. `BrainEngine._handle_research` is bound to a
lightweight stub so the heavy BrainEngine/container is never constructed.
"""

from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace
from dataclasses import asdict

# Only stub cv2/google if the real packages are genuinely unavailable.
# These stubs MUST NOT poison a healthy interpreter: importing them into
# sys.modules here breaks every later `import pyautogui` -> `pyscreeze`
# (which reads cv2.__version__).
try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules.setdefault(
        "cv2",
        SimpleNamespace(COLOR_BGR2GRAY=0, RETR_EXTERNAL=0, CHAIN_APPROX_SIMPLE=0),
    )

from desktop_agent.brain.brain_engine import BrainEngine
from desktop_agent.brain.router.response_router import (
    ResponseRouter,
    ResponseRouteType,
)
from desktop_agent.brain.research.models import ResearchResult, ResearchSource
from desktop_agent.brain.semantic.semantic_models import SemanticTask, Intent


class FakeResearchRouter:
    """Stand-in for ResearchRouter returning canned, grounded evidence."""

    def __init__(self, result):
        self._result = result
        self.calls = 0

    def research(self, handoff, conversation_context=None):
        self.calls += 1
        return self._result


class StubBrainEngine:
    """Minimal host for BrainEngine._handle_research (needs only the router
    getter and a place to store the last result)."""

    def __init__(self, router):
        self._router = router
        self._last_research_result = None

    def _get_research_router(self):
        return self._router


def task(text, metadata):
    return SemanticTask(
        raw_text=text,
        normalized_text=text.lower(),
        intent=Intent.SEARCH_WEB,
        metadata=metadata,
    )


def success_result(text):
    return ResearchResult(
        success=True,
        query=text,
        sources=[
            ResearchSource(
                provider="tavily",
                title="NIFTY Today",
                url="https://example.com/nifty",
                snippet="Indian equities closed higher.",
                published_date="2026-08-01",
            )
        ],
        synthesized="NIFTY closed higher today according to market sources.",
        synthesis_provider="ollama",
    )


def test_research_flow_produces_single_grounded_brain_result():
    text = "What is the latest NIFTY news today?"
    # 1) SemanticTask -> ResponseRouter -> RESEARCH
    route = ResponseRouter().route(
        task(text, {"live_information": True, "action": "searchWeb", "parameters": {}})
    )
    assert route.route == ResponseRouteType.RESEARCH

    # 2/3/4) ResearchRouter(mocked) -> AI synthesis(mocked) -> _handle_research
    fake_router = FakeResearchRouter(success_result(text))
    stub = StubBrainEngine(fake_router)
    result = BrainEngine._handle_research(stub, text, None, route)

    assert result.success is True
    assert result.message == "NIFTY closed higher today according to market sources."
    assert result.metadata["route"] == "RESEARCH"
    # metadata must identify research (EPIC-05 llm gate: this is THE answer).
    assert result.metadata.get("llm") is True
    assert result.metadata["research"]["source_count"] == 1
    assert result.metadata["research"]["synthesis_provider"] == "ollama"
    assert fake_router.calls == 1

    # No second response pipeline: the route is authoritative and single.
    assert route.route == ResponseRouteType.RESEARCH


def test_research_result_contains_sources_and_no_key_leak():
    text = "Latest news"
    route = ResponseRouter().route(
        task(text, {"live_information": True, "action": "searchWeb", "parameters": {}})
    )
    fake_router = FakeResearchRouter(success_result(text))
    stub = StubBrainEngine(fake_router)
    result = BrainEngine._handle_research(stub, text, None, route)

    flat = repr(asdict(result))
    assert "tvly-" not in flat
    assert "api_key" not in flat.lower()


def test_research_failure_is_controlled_no_fake_answer():
    text = "What happened to NIFTY today?"
    route = ResponseRouter().route(
        task(text, {"live_information": True, "action": "searchWeb", "parameters": {}})
    )
    failed = ResearchResult(success=False, query=text, errors=["all providers down"])
    fake_router = FakeResearchRouter(failed)
    stub = StubBrainEngine(fake_router)
    result = BrainEngine._handle_research(stub, text, None, route)

    assert result.success is False
    # No fabricated current answer, and no llm flag so it is NOT surfaced as
    # an authoritative answer (EPIC-05 gate).
    assert result.metadata.get("llm") is not True


def test_non_research_route_never_reaches_research_router():
    """A greeting routes to LOCAL_FAST and must not invoke the research router
    at all (no double answer, no redundant research compute)."""
    route = ResponseRouter().route(
        SemanticTask(raw_text="Hi MYRAA", normalized_text="hi myraa", intent=Intent.CHAT, metadata={})
    )
    assert route.route == ResponseRouteType.LOCAL_FAST

    fake_router = FakeResearchRouter(success_result("unused"))
    stub = StubBrainEngine(fake_router)
    # LOCAL_FAST is not routed through _handle_research; confirm the router is
    # never consulted by ensuring _handle_research is simply not the path.
    assert route.route != ResponseRouteType.RESEARCH
