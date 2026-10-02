"""
EPIC-09 deterministic unit tests for the ResponseRouter capability matrix.

Tests are pure (no network, no LLM, no desktop): they construct SemanticTask
objects directly and assert the single authoritative capability route.
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.router.response_router import (
    ResponseRouter,
    ResponseRoute,
    ResponseRouteType,
    ResearchHandoff,
)
from desktop_agent.brain.semantic.semantic_models import SemanticTask, Intent


def make_task(text, intent, metadata=None):
    return SemanticTask(
        raw_text=text,
        normalized_text=text.lower(),
        intent=intent,
        metadata=metadata or {},
    )


@pytest.fixture
def router():
    return ResponseRouter()


# ---------------------------------------------------------------
# Capability routing matrix
# ---------------------------------------------------------------

def test_greeting_routes_to_local_fast(router):
    """'Hi MYRAA' -> LOCAL_FAST (fast conversation, no double-answer)."""
    route = router.route(make_task("Hi MYRAA", Intent.CHAT))
    assert route.route == ResponseRouteType.LOCAL_FAST


def test_current_information_routes_to_research(router):
    """'What is today's NIFTY?' -> RESEARCH (fresh web data required)."""
    route = router.route(
        make_task(
            "What is today's NIFTY?",
            Intent.SEARCH_WEB,
            {"live_information": True, "action": "searchWeb", "parameters": {}},
        )
    )
    assert route.route == ResponseRouteType.RESEARCH
    assert isinstance(route.metadata.get("research_handoff"), ResearchHandoff)


def test_desktop_action_routes_to_execution(router):
    """'Open Notepad' -> EXECUTION (structured desktop action)."""
    route = router.route(
        make_task(
            "Open Notepad",
            Intent.OPEN_APPLICATION,
            {"action": "openApplication", "parameters": {}},
        )
    )
    assert route.route == ResponseRouteType.EXECUTION


def test_reasoning_routes_to_brain(router):
    """'Explain recursion' -> BRAIN (deeper reasoning)."""
    route = router.route(make_task("Explain recursion", Intent.QUESTION))
    assert route.route == ResponseRouteType.BRAIN


def test_memory_request_routes_to_memory(router):
    """'Remember my favorite editor' -> MEMORY (keyword-triggered)."""
    route = router.route(make_task("Remember my favorite editor", Intent.CHAT))
    assert route.route == ResponseRouteType.MEMORY


def test_memory_intent_routes_to_memory(router):
    """Explicit SET_GOAL intent -> MEMORY."""
    route = router.route(make_task("Remember X", Intent.SET_GOAL))
    assert route.route == ResponseRouteType.MEMORY


# ---------------------------------------------------------------
# Priority: live_information must beat a mapped search action
# ---------------------------------------------------------------

def test_live_information_beats_action_mapping(router):
    """A current-info request with a searchWeb action must reach RESEARCH,
    not the generic EXECUTION mapping."""
    route = router.route(
        make_task(
            "What is the latest NIFTY news today?",
            Intent.SEARCH_WEB,
            {"live_information": True, "action": "searchWeb", "parameters": {}},
        )
    )
    assert route.route == ResponseRouteType.RESEARCH


def test_non_live_search_action_stays_execution(router):
    """A searchWeb action WITHOUT live_information keeps EXECUTION (EPIC-07
    behaviour preserved)."""
    route = router.route(
        make_task(
            "open a browser search",
            Intent.SEARCH_WEB,
            {"action": "searchWeb", "parameters": {}},
        )
    )
    assert route.route == ResponseRouteType.EXECUTION


# ---------------------------------------------------------------
# Research handoff contract
# ---------------------------------------------------------------

def test_mixed_request_sets_needs_synthesis(router):
    """Mixed research + reasoning -> RESEARCH with needs_synthesis=True."""
    route = router.route(
        make_task(
            "Check today NIFTY and explain what caused the move",
            Intent.SEARCH_WEB,
            {
                "live_information": True,
                "action": "searchWeb",
                "parameters": {},
                "query": "Check today NIFTY and explain what caused the move",
            },
        )
    )
    assert route.route == ResponseRouteType.RESEARCH
    handoff = route.metadata["research_handoff"]
    assert handoff.needs_synthesis is True
    # The handoff must carry the real query, not lowercased text.
    assert handoff.query == "Check today NIFTY and explain what caused the move"


def test_route_is_explainable(router):
    """Every route carries a deterministic reason and intent (explainable)."""
    route = router.route(make_task("Hi MYRAA", Intent.CHAT))
    assert route.reason and route.intent == Intent.CHAT.value
    assert 0.0 <= route.confidence <= 1.0
    d = route.to_dict()
    assert d["route"] == ResponseRouteType.LOCAL_FAST.value
