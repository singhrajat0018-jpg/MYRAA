"""Phase E: Integration Tests — full pipeline: vision -> discovery -> mapping -> action."""

import time
import pytest
import sys
import os
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_agent.brain.performance.latency_tracker import LatencyTracker, LatencyBudget
from desktop_agent.brain.performance.context_cache import ContextCache, CacheTier
from desktop_agent.brain.performance.fast_path import FastPath
from desktop_agent.brain.performance.dedup import RequestDeduplicator
from desktop_agent.brain.performance.compression import ContextCompressor
from desktop_agent.brain.performance.telemetry import PerformanceTelemetry
try:
    from desktop_agent.brain.performance.model_router import ModelRouter, ModelTier
    HAS_MODEL_ROUTER = True
except ImportError:
    HAS_MODEL_ROUTER = False
from desktop_agent.universal_control.universal_controller import (
    UniversalController, ControlStatus,
)
from desktop_agent.universal_control.ui_discovery import UIDiscovery
from desktop_agent.universal_control.semantic_mapper import SemanticMapper
from desktop_agent.universal_control.workflow_memory import WorkflowMemory
from desktop_agent.notifications.engine import NotificationEngine, NotificationType


@dataclass
class MockVS:
    application: str = "chrome"
    window_title: str = "Google"
    page_type: str = "web_page"
    ui_targets: list = field(default_factory=list)
    visual_state: str = ""
    confidence: float = 0.85
    timestamp: float = 0.0
    frame_id: int = 1
    has_error: bool = False
    changed: bool = False


@dataclass
class MockVC:
    current_state: Optional[MockVS] = None
    _verified: bool = True

    def get_current_state(self):
        return self.current_state

    def verify_action(self, expected: dict) -> dict:
        return {"verified": self._verified, "checks": []}


class TestFullPipeline:
    def setup_method(self):
        LatencyTracker.reset_singleton()
        ContextCache.reset_singleton()
        if HAS_MODEL_ROUTER:
            ModelRouter.reset_singleton()
        PerformanceTelemetry.reset_singleton()
        NotificationEngine.reset_singleton()

    def teardown_method(self):
        LatencyTracker.reset_singleton()
        ContextCache.reset_singleton()
        if HAS_MODEL_ROUTER:
            ModelRouter.reset_singleton()
        PerformanceTelemetry.reset_singleton()
        NotificationEngine.reset_singleton()

    def test_end_to_end_click(self):
        vs = MockVS(ui_targets=[
            {"type": "button", "text": "Submit",
             "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        tracker = LatencyTracker()
        with tracker.measure("total_pipeline", LatencyBudget.TOTAL_BUDGET):
            result = ctrl.execute_intent("click submit")
        assert result.status == ControlStatus.SUCCESS
        assert result.verified
        assert result.tool_call["tool"] == "leftClick"
        report = tracker.report()
        assert "total_pipeline" in report

    def test_end_to_end_type(self):
        vs = MockVS(ui_targets=[
            {"type": "textbox", "text": "Search",
             "bounds": {"x": 50, "y": 100, "width": 200, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent('type "hello"')
        assert result.tool_call["tool"] == "typeText"
        assert result.tool_call["args"]["text"] == "hello"

    def test_fast_path_integration(self):
        fp = FastPath()
        result = fp.match("open notepad")
        assert result.matched
        assert result.tool_name == "openApplication"
        assert result.decision_ms < 10

    def test_cache_with_context(self):
        cache = ContextCache()
        cache.put("screen:latest", {"app": "chrome"}, CacheTier.L1_SCREEN)
        cached = cache.get("screen:latest", CacheTier.L1_SCREEN)
        assert cached is not None

    def test_dedup_cache_integration(self):
        dedup = RequestDeduplicator()
        cache = ContextCache()
        r1 = dedup.check("click", {"x": 100, "y": 200})
        assert not r1.is_duplicate
        cache.put(r1.key, {"status": "pending"}, CacheTier.L2_TOOL_RESULT)
        r2 = dedup.check("click", {"x": 100, "y": 200})
        assert r2.is_duplicate
        cached = cache.get(r1.key, CacheTier.L2_TOOL_RESULT)
        assert cached is not None
        dedup.release(r1.key)

    def test_compression_cache_integration(self):
        comp = ContextCompressor(max_tokens=100)
        long_text = "word " * 500
        result = comp.compress(long_text)
        assert result.compressed_tokens < result.original_tokens
        cache = ContextCache()
        cache.put("compressed:query", result.compressed, CacheTier.L5_SEMANTIC)
        cached = cache.get("compressed:query", CacheTier.L5_SEMANTIC)
        assert cached == result.compressed

    def test_telemetry_pipeline(self):
        tel = PerformanceTelemetry()
        tracker = LatencyTracker()
        with tracker.measure("test", LatencyBudget.PERCEPTION):
            time.sleep(0.001)
        report = tracker.get_stage_stats("test")
        tel.build_report(
            stage_latencies={"test": report.avg_ms},
            total_ms=report.avg_ms,
            fast_path_hit=True,
        )
        s = tel.summary()
        assert s["total_requests"] == 1

    def test_notification_on_failure(self):
        vs = MockVS(ui_targets=[])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        engine = NotificationEngine()
        result = ctrl.execute_intent("click submit")
        if result.status != ControlStatus.SUCCESS:
            engine.task_failed("Universal Control", result.error)
        unread = engine.unread()
        assert len(unread) >= 1

    def test_workflow_with_vision(self):
        vs = MockVS(ui_targets=[
            {"type": "button", "text": "OK",
             "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
            {"type": "textbox", "text": "Name",
             "bounds": {"x": 50, "y": 100, "width": 200, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        wm = WorkflowMemory()
        wf_id = wm.start_recording("test form fill", "chrome")
        r1 = ctrl.execute_intent('type "John"')
        wm.record_step("type", "Name", {"text": "John"},
                       success=r1.status == ControlStatus.SUCCESS)
        r2 = ctrl.execute_intent("click ok")
        wm.record_step("click", "OK", success=r2.status == ControlStatus.SUCCESS)
        wf = wm.stop_recording()
        assert wf.step_count == 2
        assert wf.name == "test form fill"

    @pytest.mark.skipif(not HAS_MODEL_ROUTER, reason="ModelRouter removed")
    def test_model_router_with_cache(self):
        router = ModelRouter()
        cache = ContextCache()
        decision = router.route(complexity=0.2, latency_budget_ms=300)
        cache.put(f"route:{decision.tier.value}", decision, CacheTier.L5_SEMANTIC)
        cached = cache.get(f"route:{decision.tier.value}", CacheTier.L5_SEMANTIC)
        assert cached is not None
        assert cached.tier == ModelTier.FAST
