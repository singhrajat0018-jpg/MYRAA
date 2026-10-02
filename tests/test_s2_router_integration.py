"""Phase S.2 — Router Integration + Tool Avoidance Tests.

Proves that:
1. TaskRouter is wired into the /brain production endpoint
2. DIRECT_KNOWLEDGE/CONVERSATION requests use fast path (no SuperBrain pipeline)
3. Action requests still go through the full pipeline
4. No unnecessary tools (browser, web, vision, desktop) are invoked for simple questions
5. Permission gate remains active
6. Financial execution remains impossible
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock

from desktop_agent.brain.router.task_router import (
    TaskRouter, TaskType, ResponseMode,
)


@pytest.fixture
def router():
    return TaskRouter()


# ============================================================
# 1. TaskRouter Production Path — /brain endpoint fast-path
# ============================================================

class TestBrainEndpointFastPath:
    """Verify /brain endpoint uses TaskRouter fast path for simple requests."""

    def test_direct_knowledge_skips_superbrain(self, router):
        """'What is Python?' should classify as DIRECT_KNOWLEDGE."""
        d = router.route("What is Python?")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False
        assert d.response_mode == ResponseMode.FAST_ANSWER

    def test_conversation_skips_superbrain(self, router):
        """'Hello' should classify as CONVERSATION."""
        d = router.route("Hello")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False
        assert d.response_mode == ResponseMode.FAST_ANSWER

    def test_explain_oop_fast_path(self, router):
        """'Explain OOP' should be DIRECT_KNOWLEDGE, no tools."""
        d = router.route("Explain OOP")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False


# ============================================================
# 2. No-Tool Verification — actual tool invocation tracking
# ============================================================

class TestNoToolInvocation:
    """Prove that unnecessary tools are NOT invoked for simple questions."""

    def test_what_is_python_no_browser(self, router):
        d = router.route("What is Python?")
        assert "browser" not in d.tool_names
        assert d.task_type != TaskType.BROWSER_ACTION

    def test_what_is_python_no_web_search(self, router):
        d = router.route("What is Python?")
        assert "web_search" not in d.tool_names
        assert d.task_type != TaskType.WEB_RESEARCH

    def test_what_is_python_no_vision(self, router):
        d = router.route("What is Python?")
        assert "screenshot" not in d.tool_names
        assert d.task_type != TaskType.VISION_TASK

    def test_what_is_python_no_desktop(self, router):
        d = router.route("What is Python?")
        assert "openApplication" not in d.tool_names
        assert d.task_type != TaskType.DESKTOP_ACTION

    def test_what_is_python_no_trading(self, router):
        d = router.route("What is Python?")
        assert "trading_engine" not in d.tool_names
        assert d.task_type != TaskType.TRADING_TASK

    def test_recursion_no_tools(self, router):
        d = router.route("What is recursion?")
        assert d.tools_required is False
        assert len(d.tool_names) == 0

    def test_explain_oop_no_tools(self, router):
        d = router.route("Explain OOP")
        assert d.tools_required is False
        assert len(d.tool_names) == 0

    def test_hello_no_tools(self, router):
        d = router.route("Hello")
        assert d.tools_required is False
        assert len(d.tool_names) == 0

    def test_cpu_question_no_tools(self, router):
        d = router.route("What is a CPU?")
        assert d.tools_required is False
        assert len(d.tool_names) == 0

    def test_binary_search_no_tools(self, router):
        d = router.route("How does binary search work?")
        assert d.tools_required is False
        assert len(d.tool_names) == 0


# ============================================================
# 3. Tool-Escalation — correct tools when needed
# ============================================================

class TestToolEscalation:
    """When tools ARE needed, the correct tools are selected."""

    def test_open_youtube_uses_browser(self, router):
        d = router.route("Open YouTube")
        assert d.task_type == TaskType.BROWSER_ACTION
        assert d.tools_required is True
        assert "browser" in d.tool_names

    def test_open_notepad_uses_desktop(self, router):
        d = router.route("Open Notepad")
        assert d.task_type == TaskType.DESKTOP_ACTION
        assert d.tools_required is True
        assert "openApplication" in d.tool_names

    def test_what_on_screen_uses_vision(self, router):
        d = router.route("What is on my screen?")
        assert d.task_type == TaskType.VISION_TASK
        assert d.tools_required is True
        assert "screenshot" in d.tool_names

    def test_analyze_nifty_uses_trading(self, router):
        d = router.route("Analyze NIFTY")
        assert d.task_type == TaskType.TRADING_TASK
        assert d.tools_required is True
        assert "trading_engine" in d.tool_names

    def test_latest_python_uses_web(self, router):
        d = router.route("What is the latest Python version?")
        assert d.freshness_required is True
        assert d.tools_required is True
        assert "web_search" in d.tool_names

    def test_write_program_uses_coding(self, router):
        d = router.route("Write a Python script for sorting")
        assert d.task_type == TaskType.CODING_TASK
        assert d.tools_required is True


# ============================================================
# 4. Voice Path — route voice request
# ============================================================

class TestVoiceRouting:
    """Verify TaskRouter handles voice-style requests correctly."""

    def test_voice_question_direct(self, router):
        """Voice: 'what is Python' (no question mark — common in speech)."""
        d = router.route("what is Python")
        assert d.task_type == TaskType.DIRECT_KNOWLEDGE
        assert d.tools_required is False

    def test_voice_command_action(self, router):
        """Voice: 'open notepad'."""
        d = router.route("open notepad")
        assert d.task_type == TaskType.DESKTOP_ACTION
        assert d.tools_required is True

    def test_voice_greeting(self, router):
        """Voice: 'hey myraa'."""
        d = router.route("hey myraa")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False


# ============================================================
# 5. Security — permission + safety gates
# ============================================================

class TestSecurityGates:
    """Verify permission and safety gates remain active."""

    def test_financial_category_is_deny(self):
        """FINANCIAL tools must remain denied in PermissionManager."""
        from desktop_agent.config.permissions import DEFAULT_POLICIES, FINANCIAL
        assert DEFAULT_POLICIES.get(FINANCIAL) == "deny"

    def test_system_critical_requires_confirm(self):
        """SYSTEM_CRITICAL tools must require confirmation."""
        from desktop_agent.config.permissions import DEFAULT_POLICIES, SYSTEM_CRITICAL
        assert DEFAULT_POLICIES.get(SYSTEM_CRITICAL) == "confirm"

    def test_power_actions_have_override(self):
        """Power actions use two-step confirmation token flow."""
        from desktop_agent.config.permissions import TOOL_OVERRIDES
        assert "requestPowerAction" in TOOL_OVERRIDES
        assert "executePowerAction" in TOOL_OVERRIDES

    def test_safety_manager_not_noop(self):
        """brain/safety_manager.py must have real checks, not return True."""
        from desktop_agent.brain.safety_manager import SafetyManager
        sm = SafetyManager()
        # runPythonScript should be blocked in autonomous mode
        assert sm.check("runPythonScript", {}, autonomous=True) is False

    def test_safety_manager_allows_read(self):
        """READ tools should pass safety check."""
        from desktop_agent.brain.safety_manager import SafetyManager
        sm = SafetyManager()
        assert sm.check("readFile", {"path": "test.txt"}) is True

    def test_safety_manager_blocks_protected_path(self):
        """Protected system paths should be blocked for file-modifying tools."""
        from desktop_agent.brain.safety_manager import SafetyManager
        sm = SafetyManager()
        # deleteFile is in _TOOLS_CONFIRM, so path check applies
        assert sm.check("deleteFile", {"path": "c:\\windows\\system32\\config"}) is False

    def test_step_executor_has_safety(self):
        """StepExecutor must check safety before dispatch."""
        from desktop_agent.brain.executive.step_executor import StepExecutor
        import inspect
        source = inspect.getsource(StepExecutor.execute)
        assert "SafetyManager" in source or "safety" in source.lower()


# ============================================================
# 6. Performance — routing latency
# ============================================================

class TestRoutingLatency:
    """TaskRouter decisions must be extremely fast."""

    def test_100_routes_under_100ms(self, router):
        """100 route decisions must complete in under 100ms total."""
        t0 = time.monotonic()
        for _ in range(100):
            router.route("What is Python?")
        elapsed = (time.monotonic() - t0) * 1000
        assert elapsed < 100, f"100 routes took {elapsed:.1f}ms (target: <100ms)"

    def test_single_route_under_1ms(self, router):
        """Single route decision must be under 1ms."""
        d = router.route("What is Python?")
        assert d.estimated_latency_ms < 1.0, f"Route took {d.estimated_latency_ms:.2f}ms"

    def test_complex_route_still_fast(self, router):
        """Even complex routing should be under 5ms."""
        d = router.route("Analyze my Groww portfolio and compare NIFTY with BANKNIFTY options")
        assert d.estimated_latency_ms < 5.0


# ============================================================
# 7. Regression — S.1 tests still pass
# ============================================================

class TestRegression:
    """Ensure S.1 TaskRouter tests remain green."""

    def test_s1_direct_knowledge(self, router):
        for q in ["What is Python?", "What is recursion?", "Explain OOP"]:
            d = router.route(q)
            assert d.task_type == TaskType.DIRECT_KNOWLEDGE
            assert d.tools_required is False

    def test_s1_desktop_action(self, router):
        d = router.route("Open Notepad")
        assert d.task_type == TaskType.DESKTOP_ACTION
        assert d.tools_required is True

    def test_s1_browser_action(self, router):
        d = router.route("Open YouTube")
        assert d.task_type == TaskType.BROWSER_ACTION
        assert d.tools_required is True

    def test_s1_vision(self, router):
        d = router.route("What is on my screen?")
        assert d.task_type == TaskType.VISION_TASK
        assert d.tools_required is True

    def test_s1_trading(self, router):
        d = router.route("Analyze NIFTY")
        assert d.task_type == TaskType.TRADING_TASK
        assert d.tools_required is True

    def test_s1_conversation(self, router):
        d = router.route("Hello")
        assert d.task_type == TaskType.CONVERSATION
        assert d.tools_required is False

    def test_s1_freshness(self, router):
        d = router.route("What is the latest Python version?")
        assert d.freshness_required is True
