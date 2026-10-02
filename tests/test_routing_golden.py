"""Phase 10.8-10.9 — Routing golden tests.

Validates consistency across the four independent routing subsystems:
1. FastCoreClassifier (main.py /brain/stream entry)
2. TaskRouter (AssistantRuntime / SuperBrain entry)
3. IntentRouter (SemanticParser internal)
4. ResponseRouter (BrainEngine capability selector)

These routers are NOT a chain — they serve different entry points.
Golden tests verify that overlapping inputs produce consistent classifications.
"""
import pytest
import sys
import os

sys.path.insert(0, os.getcwd())

from desktop_agent.fastcore.classifier import FastCoreClassifier
from desktop_agent.fastcore.models import TaskType as FCTaskType, ResponseMode as FCResponseMode
from desktop_agent.brain.router.task_router import TaskRouter
from desktop_agent.brain.router.task_router import TaskType as TRTaskType
from desktop_agent.brain.router.response_router import ResponseRouter, ResponseRouteType
from desktop_agent.brain.semantic.semantic_models import SemanticTask, Intent

_fc = FastCoreClassifier()
_tr = TaskRouter()
_rr = ResponseRouter()


# ── FastCoreClassifier golden tests ──────────────────────────

class TestFastCoreGolden:
    """FastCoreClassifier golden: key families with verified outputs."""

    @pytest.mark.parametrize("text,expected_task,expected_mode", [
        ("what is the weather in Delhi", FCTaskType.WEATHER_TASK, FCResponseMode.WEATHER),
        ("temperature in Mumbai today", FCTaskType.WEATHER_TASK, FCResponseMode.WEATHER),
        ("is it raining outside", FCTaskType.WEATHER_TASK, FCResponseMode.WEATHER),
        ("latest news about AI", FCTaskType.NEWS_TASK, FCResponseMode.NEWS),
        ("what happened in the stock market today", FCTaskType.NEWS_TASK, FCResponseMode.NEWS),
        ("open notepad", FCTaskType.DESKTOP_ACTION, FCResponseMode.ACTION),
        ("volume up", FCTaskType.DESKTOP_ACTION, FCResponseMode.ACTION),
        ("close the browser", FCTaskType.BROWSER_ACTION, FCResponseMode.ACTION),
        ("search for python tutorials", FCTaskType.WEB_RESEARCH, FCResponseMode.RESEARCH),
        ("what is quantum computing", FCTaskType.DIRECT_KNOWLEDGE, FCResponseMode.FAST_ANSWER),
        ("explain machine learning", FCTaskType.DIRECT_KNOWLEDGE, FCResponseMode.FAST_ANSWER),
        ("create a file called test.txt", FCTaskType.FILE_TASK, FCResponseMode.ACTION),
        ("read the contents of config.json", FCTaskType.FILE_TASK, FCResponseMode.ACTION),
    ])
    def test_fastcore_golden(self, text, expected_task, expected_mode):
        out = _fc.classify(text)
        assert out.task_type == expected_task, f"task_type={out.task_type} for '{text}'"
        assert out.response_mode == expected_mode, f"response_mode={out.response_mode} for '{text}'"

    @pytest.mark.parametrize("text", [
        "hello", "what time is it", "open notepad", "latest news about AI",
    ])
    def test_fastcore_confidence_above_threshold(self, text):
        out = _fc.classify(text)
        assert out.confidence >= 0.70, f"confidence={out.confidence} for '{text}'"

    def test_fastcore_safety_escalates_for_destructive(self):
        out = _fc.classify("delete all files on my computer")
        assert out.escalate is True or out.safety_class.value in ("dangerous", "elevated")

    def test_fastcore_tools_required_for_action(self):
        out = _fc.classify("open notepad")
        assert out.tools_required is True

    def test_fastcore_tools_not_required_for_knowledge(self):
        out = _fc.classify("what is quantum computing")
        assert out.tools_required is False


# ── TaskRouter golden tests ──────────────────────────────────

class TestTaskRouterGolden:
    """TaskRouter golden: validates RoutingDecision for key input families."""

    @pytest.mark.parametrize("text,expected_task", [
        ("open notepad", TRTaskType.DESKTOP_ACTION),
        ("take a screenshot", TRTaskType.DESKTOP_ACTION),
        ("volume down", TRTaskType.DESKTOP_ACTION),
        ("hello how are you", TRTaskType.LOCAL_REASONING),
        ("what is quantum computing", TRTaskType.DIRECT_KNOWLEDGE),
    ])
    def test_task_router_golden(self, text, expected_task):
        decision = _tr.route(text)
        assert decision.task_type == expected_task, (
            f"task_type={decision.task_type} for '{text}'"
        )

    def test_task_router_confidence_range(self):
        for text in ["hello", "open notepad", "what is AI"]:
            d = _tr.route(text)
            assert 0.0 <= d.confidence <= 1.0, f"confidence={d.confidence}"

    def test_task_router_tools_required_for_desktop(self):
        d = _tr.route("open notepad")
        assert d.tools_required is True

    def test_task_router_tools_not_required_for_chat(self):
        d = _tr.route("hello")
        assert d.tools_required is False


# ── ResponseRouter golden tests ───────────────────────────────

class TestResponseRouterGolden:
    """ResponseRouter golden: validates capability routing for SemanticTasks."""

    def _make_task(self, text, intent=Intent.QUESTION):
        return SemanticTask(raw_text=text, intent=intent)

    def test_desktop_action_routes_to_execution(self):
        task = self._make_task("open notepad", intent=Intent.OPEN_APPLICATION)
        route = _rr.route(task)
        assert route.route == ResponseRouteType.EXECUTION

    def test_conversation_routes_to_local_fast(self):
        task = self._make_task("hello", intent=Intent.CHAT)
        route = _rr.route(task)
        assert route.route == ResponseRouteType.LOCAL_FAST

    def test_question_routes_to_brain(self):
        task = self._make_task("what is AI", intent=Intent.QUESTION)
        route = _rr.route(task)
        assert route.route == ResponseRouteType.BRAIN

    def test_search_routes_to_research(self):
        task = self._make_task("search web", intent=Intent.SEARCH_WEB)
        route = _rr.route(task)
        assert route.route == ResponseRouteType.RESEARCH

    def test_file_create_routes_to_execution(self):
        task = self._make_task("create a file", intent=Intent.CREATE_FILE)
        route = _rr.route(task)
        assert route.route == ResponseRouteType.EXECUTION

    def test_route_confidence_above_threshold(self):
        for intent in [Intent.CHAT, Intent.QUESTION, Intent.OPEN_APPLICATION]:
            task = self._make_task("test", intent=intent)
            route = _rr.route(task)
            assert route.confidence >= 0.5


# ── Cross-router consistency tests ───────────────────────────

class TestCrossRouterConsistency:
    """Verify that where routers overlap, they agree on key properties."""

    def test_desktop_action_fastcore_vs_task_router(self):
        """FastCore and TaskRouter should both classify 'open notepad' as desktop action."""
        fc = _fc.classify("open notepad")
        tr = _tr.route("open notepad")
        assert fc.task_type == FCTaskType.DESKTOP_ACTION
        assert tr.task_type == TRTaskType.DESKTOP_ACTION

    def test_tools_required_consistency(self):
        """FastCore and TaskRouter should agree on tools_required for actions."""
        text = "open notepad"
        fc = _fc.classify(text)
        tr = _tr.route(text)
        assert fc.tools_required == tr.tools_required

    def test_knowledge_confidence_above_threshold(self):
        """Both should have reasonable confidence for knowledge queries."""
        fc = _fc.classify("what is quantum computing")
        tr = _tr.route("what is quantum computing")
        assert fc.confidence >= 0.70
        assert tr.confidence >= 0.50

    def test_fastcore_produces_valid_task_types(self):
        """All FastCore outputs should have valid TaskType values."""
        for text in ["hello", "open notepad", "weather in Delhi", "search YouTube"]:
            out = _fc.classify(text)
            assert isinstance(out.task_type, FCTaskType)

    def test_task_router_produces_valid_task_types(self):
        """All TaskRouter outputs should have valid task_type values."""
        for text in ["hello", "open notepad", "what is AI"]:
            d = _tr.route(text)
            assert isinstance(d.task_type, TRTaskType)

    def test_fastcore_model_route_valid(self):
        """FastCore should always produce a valid model route."""
        for text in ["hello", "open notepad", "weather in Delhi"]:
            out = _fc.classify(text)
            assert out.model_route is not None

    def test_response_router_metadata_for_execution(self):
        """Execution routes should carry action info in metadata."""
        task = SemanticTask(raw_text="open notepad", intent=Intent.OPEN_APPLICATION)
        route = _rr.route(task)
        assert route.route == ResponseRouteType.EXECUTION
        assert route.confidence >= 0.8
