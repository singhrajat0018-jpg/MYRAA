"""Tests for the Intelligent Task Router (Phase S.1).

Verifies that MYRAA routes requests to the correct subsystem and does NOT
invoke unnecessary tools (browser, web, vision, trading, desktop) when
they are not needed.
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.router.task_router import (
    TaskRouter,
    TaskType,
    ResponseMode,
    requires_freshness,
)


@pytest.fixture
def router():
    return TaskRouter()


# ============================================================
# DIRECT_KNOWLEDGE — no tools, no browser, no web
# ============================================================

class TestDirectKnowledge:
    """Simple knowledge questions must use FAST_ANSWER, no tools."""

    def test_what_is_python(self, router):
        d = router.route("What is Python?")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False
        assert d.response_mode == ResponseMode.FAST_ANSWER

    def test_what_is_recursion(self, router):
        d = router.route("What is recursion?")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False

    def test_explain_oop(self, router):
        d = router.route("Explain OOP.")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False

    def test_what_is_cpu(self, router):
        d = router.route("What is a CPU?")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False

    def test_how_does_binary_search_work(self, router):
        d = router.route("How does binary search work?")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False

    def test_difference_between_list_and_tuple(self, router):
        d = router.route("What is the difference between a list and a tuple?")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False

    def test_write_factorial_program(self, router):
        """'Write a C program for factorial' — coding but answerable by model."""
        d = router.route("Write a C program for factorial.")
        assert d.task_type == TaskType.CODING_TASK
        assert d.tools_required is True

    def test_no_browser_invoked(self, router):
        """Critical: simple questions must NEVER trigger browser."""
        for q in [
            "What is Python?",
            "What is recursion?",
            "Explain OOP.",
            "What is a CPU?",
        ]:
            d = router.route(q)
            assert "browser" not in d.tool_names
            assert d.task_type != TaskType.BROWSER_ACTION
            assert d.task_type != TaskType.VISION_TASK


# ============================================================
# CURRENT_INFORMATION — freshness required
# ============================================================

class TestCurrentInformation:
    """Requests requiring fresh data should route to RESEARCH."""

    def test_latest_python_version(self, router):
        d = router.route("What is the latest Python version?")
        assert d.freshness_required is True
        assert d.tools_required is True
        assert d.task_type == TaskType.CURRENT_INFORMATION

    def test_current_nifty_price(self, router):
        d = router.route("What is NIFTY doing right now?")
        assert d.task_type == TaskType.TRADING_TASK
        assert d.freshness_required is True

    def test_today_weather(self, router):
        d = router.route("What is today's weather?")
        assert d.freshness_required is True


# ============================================================
# DESKTOP_ACTION — tools required
# ============================================================

class TestDesktopAction:
    """Desktop commands must route to ACTION with tools."""

    def test_open_notepad(self, router):
        d = router.route("Open Notepad")
        assert d.task_type == TaskType.DESKTOP_ACTION
        assert d.tools_required is True
        assert d.response_mode == ResponseMode.ACTION

    def test_close_application(self, router):
        d = router.route("Close Chrome")
        assert d.task_type == TaskType.DESKTOP_ACTION
        assert d.tools_required is True


# ============================================================
# BROWSER_ACTION — browser required
# ============================================================

class TestBrowserAction:
    """Browser commands must route to ACTION with browser tool."""

    def test_open_youtube(self, router):
        d = router.route("Open YouTube")
        assert d.task_type == TaskType.BROWSER_ACTION
        assert d.tools_required is True

    def test_search_google(self, router):
        d = router.route("Search on Google for Python docs")
        assert d.task_type == TaskType.BROWSER_ACTION
        assert d.tools_required is True


# ============================================================
# VISION_TASK — vision required
# ============================================================

class TestVisionTask:
    """Screen analysis tasks must route to VISION."""

    def test_what_on_screen(self, router):
        d = router.route("What is on my screen?")
        assert d.task_type == TaskType.VISION_TASK
        assert d.tools_required is True
        assert d.response_mode == ResponseMode.VISION


# ============================================================
# TRADING_TASK — market data required
# ============================================================

class TestTradingTask:
    """Trading/market tasks must route to TRADING."""

    def test_analyze_nifty(self, router):
        d = router.route("Analyze NIFTY options")
        assert d.task_type == TaskType.TRADING_TASK
        assert d.tools_required is True

    def test_portfolio_analysis(self, router):
        d = router.route("Analyze my Groww portfolio")
        assert d.task_type == TaskType.TRADING_TASK
        assert d.tools_required is True


# ============================================================
# TOOL ESCALATION — confidence-based
# ============================================================

class TestToolEscalation:
    """Requests should only escalate to tools when necessary."""

    def test_simple_question_low_confidence_still_no_tools(self, router):
        """Even with lower confidence, simple questions stay tool-free."""
        d = router.route("Tell me something interesting")
        assert d.tools_required is False


# ============================================================
# FRESHNESS DETECTION
# ============================================================

class TestFreshnessDetection:
    """Temporal keywords should trigger freshness detection."""

    def test_latest_detected(self):
        assert requires_freshness("What is the latest version?") is True

    def test_today_detected(self):
        assert requires_freshness("What happened today?") is True

    def test_now_detected(self):
        assert requires_freshness("What is happening now?") is True

    def test_no_freshness_for_static(self):
        assert requires_freshness("What is Python?") is False

    def test_no_freshness_for_explanation(self):
        assert requires_freshness("Explain recursion") is False


# ============================================================
# CONVERSATIONAL — no tools
# ============================================================

class TestConversational:
    """Greetings and simple chat must use no tools."""

    def test_hello(self, router):
        d = router.route("Hello")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False

    def test_thanks(self, router):
        d = router.route("Thanks")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False

    def test_empty(self, router):
        d = router.route("")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False


# ============================================================
# CONVERSATION INVARIANT — the core Stage 1 test set
# Every greeting / simple-chat input MUST produce:
#   task_type = CONVERSATION
#   tools_required = False
#   tool_calls = 0 (no tools in tool_names)
# ============================================================

class TestConversationInvariant:
    """Bug: 'Hello Myraa' → searchWeb → Google.  This must never happen.

    Every test in this class verifies:
      task_type == CONVERSATION
      tools_required is False
      tool_names is empty
    """

    GREETINGS = [
        "Hello",
        "Hi",
        "Hey",
        "Hey Myraa",
        "Hello Myraa",
        "Good morning",
        "Good evening",
        "How are you?",
        "Are you there?",
        "What are you doing?",
        "Thank you",
        "Thanks",
        "Who are you?",
        "What can you do?",
        "Tell me about yourself",
        "Nice to meet you",
        "Good night",
        "Bye",
        "Let's talk",
        "I'm bored",
        "Stay with me",
        # Wake-word + greeting variants
        "hello myraa",
        "hey myra",
        "hi myraa",
        "Hello Myra",
        "Hey Myra",
        "Hi Myra",
        "hello there",
        "hey there",
        "hi there",
        "good morning myraa",
        "good evening myra",
        # Short / casual
        "ok",
        "okay",
        "sure",
        "yes",
        "no",
        "sup",
        "yo",
    ]

    def test_all_greetings_are_conversation(self, router):
        """Every greeting MUST be classified as CONVERSATION with no tools."""
        for greeting in self.GREETINGS:
            d = router.route(greeting)
            assert d.task_type == TaskType.CONVERSATION, (
                f"Greeting {greeting!r} classified as {d.task_type.name}, "
                f"expected CONVERSATION"
            )
            assert d.tools_required is False, (
                f"Greeting {greeting!r} has tools_required=True"
            )
            assert d.tool_names == [], (
                f"Greeting {greeting!r} has tool_names={d.tool_names}"
            )

    def test_hello_myraa_no_google(self, router):
        """THE BUG: 'Hello Myraa' must NOT trigger searchWeb."""
        d = router.route("Hello Myraa")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False
        assert "searchWeb" not in d.tool_names
        assert "searchGoogle" not in d.tool_names
        assert "browser" not in d.tool_names

    def test_voice_convergence(self, router):
        """Voice greeting must use the same route as text greeting."""
        for greeting in ["Hello Myraa", "Hey Myraa", "Hi Myraa"]:
            d = router.route(greeting)
            assert d.task_type == TaskType.CONVERSATION
            assert d.tools_required is False
            assert d.response_mode == ResponseMode.FAST_ANSWER


# ============================================================
# PERFORMANCE — routing decision must be fast
# ============================================================

class TestRoutingPerformance:
    """Routing decisions must be extremely fast (< 1ms)."""

    def test_routing_latency(self, router):
        import time
        t0 = time.monotonic()
        for _ in range(100):
            router.route("What is Python?")
        elapsed = (time.monotonic() - t0) * 1000
        assert elapsed < 100, f"100 route decisions took {elapsed:.1f}ms (target: <100ms)"


# ============================================================
# KNOWLEDGE INVARIANT — no tools for static knowledge
# ============================================================

class TestKnowledgeInvariant:
    """Static knowledge questions must produce DIRECT_KNOWLEDGE, no tools."""

    KNOWLEDGE_QUESTIONS = [
        "What is Python?",
        "What is recursion?",
        "Explain OOP.",
        "What is RAM?",
        "What is CPU?",
        "How does binary search work?",
    ]

    def test_all_knowledge_questions_no_tools(self, router):
        for q in self.KNOWLEDGE_QUESTIONS:
            d = router.route(q)
            assert d.task_type == TaskType.DIRECT_KNOWLEDGE, (
                f"Knowledge question {q!r} classified as {d.task_type.name}, "
                f"expected DIRECT_KNOWLEDGE"
            )
            assert d.tools_required is False, (
                f"Knowledge question {q!r} has tools_required=True"
            )
            assert d.tool_names == [], (
                f"Knowledge question {q!r} has tool_names={d.tool_names}"
            )


# ============================================================
# FRESH INFORMATION — must require tools
# ============================================================

class TestFreshInformation:
    """Fresh/current information requests MUST require tools (web search)."""

    FRESH_QUERIES = [
        "Latest Python version",
        "Current weather",
        "Today's AI news",
        "Latest NVIDIA model",
        "What is the current price of NIFTY?",
    ]

    def test_fresh_queries_require_tools(self, router):
        for q in self.FRESH_QUERIES:
            d = router.route(q)
            assert d.tools_required is True, (
                f"Fresh query {q!r} has tools_required=False"
            )
            assert d.freshness_required is True, (
                f"Fresh query {q!r} has freshness_required=False"
            )


# ============================================================
# EXPLICIT ACTIONS — must route to correct capability
# ============================================================

class TestExplicitActions:
    """Explicit user actions must route to the correct capability."""

    def test_open_youtube(self, router):
        d = router.route("Open YouTube")
        assert d.task_type == TaskType.BROWSER_ACTION
        assert d.tools_required is True

    def test_take_screenshot(self, router):
        d = router.route("Take a screenshot")
        assert d.task_type == TaskType.DESKTOP_ACTION
        assert d.tools_required is True

    def test_whats_on_screen(self, router):
        d = router.route("What's on my screen?")
        assert d.task_type == TaskType.VISION_TASK
        assert d.tools_required is True

    def test_analyze_nifty(self, router):
        d = router.route("Analyze NIFTY")
        assert d.task_type == TaskType.TRADING_TASK
        assert d.tools_required is True

    def test_create_file(self, router):
        d = router.route("Create a file called test.txt")
        assert d.task_type == TaskType.FILE_TASK
        assert d.tools_required is True

    def test_design_futuristic_bike_falls_to_default(self, router):
        d = router.route("Design a futuristic bike")
        assert d.task_type != TaskType.DESIGN_TASK

    def test_fix_project_bug(self, router):
        d = router.route("Fix this project bug")
        assert d.task_type == TaskType.CODING_TASK
        assert d.tools_required is True
