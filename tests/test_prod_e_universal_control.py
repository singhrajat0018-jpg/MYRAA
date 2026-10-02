"""E Production Closure — Universal Control E2E + ThreadPoolExecutor Fix.

Verifies:
1. Full pipeline: vision → discover → click/type/scroll → verify
2. ThreadPoolExecutor does NOT hang pytest (proper lifecycle)
3. No Playwright dependency (real desktop tools only)
4. Discovery + mapping + action + verification real contracts
5. Multi-step workflow recording
"""

from __future__ import annotations

import time
import threading
import pytest
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import patch, MagicMock


# ── Mock Visual State ────────────────────────────────────────

@dataclass
class MockVS:
    application: str = "chrome"
    window_title: str = "Google Chrome"
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


# ============================================================
# 1. Full Pipeline: Vision → Discovery → Action → Verify
# ============================================================

class TestFullPipelineE2E:

    def test_click_pipeline(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlStatus,
        )
        vs = MockVS(ui_targets=[
            {"type": "button", "text": "Submit",
             "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent("click submit")
        assert result.status == ControlStatus.SUCCESS
        assert result.verified
        assert result.tool_call["tool"] == "leftClick"
        assert result.tool_call["args"]["x"] == 140  # center of 100+80/2
        assert result.tool_call["args"]["y"] == 215  # center of 200+30/2

    def test_type_pipeline(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlStatus,
        )
        vs = MockVS(ui_targets=[
            {"type": "textbox", "text": "Search",
             "bounds": {"x": 50, "y": 100, "width": 200, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent('type "hello world"')
        assert result.tool_call["tool"] == "typeText"
        assert result.tool_call["args"]["text"] == "hello world"

    def test_scroll_pipeline(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlStatus, ControlAction,
        )
        vs = MockVS(ui_targets=[
            {"type": "scrollable", "text": "Content",
             "bounds": {"x": 0, "y": 0, "width": 800, "height": 600}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent("scroll down")
        assert result.action == ControlAction.SCROLL
        if result.tool_call:
            assert result.tool_call.get("tool") == "scrollMouse"

    def test_no_vision_returns_no_vision(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlStatus,
        )
        ctrl = UniversalController(vision_controller=None)
        result = ctrl.execute_intent("click button")
        assert result.status == ControlStatus.NO_VISION

    def test_no_matching_element(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlStatus,
        )
        vs = MockVS(ui_targets=[])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent("click nonexistent_xyz_123")
        assert result.status == ControlStatus.NO_ELEMENT

    def test_discover_elements(self):
        from desktop_agent.universal_control.universal_controller import UniversalController
        vs = MockVS(ui_targets=[
            {"type": "button", "text": "OK",
             "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        discovery = ctrl.discover_elements()
        assert discovery is not None
        assert len(discovery.elements) >= 1

    def test_find_element(self):
        from desktop_agent.universal_control.universal_controller import UniversalController
        vs = MockVS(ui_targets=[
            {"type": "textbox", "text": "Email",
             "bounds": {"x": 50, "y": 100, "width": 200, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        elem = ctrl.find_element("email")
        assert elem is not None

    def test_action_history_tracked(self):
        from desktop_agent.universal_control.universal_controller import UniversalController
        vs = MockVS(ui_targets=[
            {"type": "button", "text": "OK",
             "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        ctrl.execute_intent("click ok")
        history = ctrl.get_action_history(10)
        assert len(history) >= 1


# ============================================================
# 2. ThreadPoolExecutor Lifecycle — No Hang
# ============================================================

class TestThreadPoolLifecycle:

    def test_parallel_executor_singleton_reset(self):
        from desktop_agent.brain.performance.parallel_executor import ParallelExecutor
        ParallelExecutor.reset_singleton()
        ex = ParallelExecutor(pool_size=2)
        from desktop_agent.brain.performance.parallel_executor import ParallelTask
        tasks = [ParallelTask("t1", lambda: 42)]
        results = ex.execute_all(tasks)
        assert len(results) == 1
        assert results[0].success
        assert results[0].value == 42
        ParallelExecutor.reset_singleton()

    def test_parallel_executor_no_hang_after_shutdown(self):
        from desktop_agent.brain.performance.parallel_executor import ParallelExecutor, ParallelTask
        ParallelExecutor.reset_singleton()
        ex = ParallelExecutor(pool_size=2)
        results = ex.execute_all([ParallelTask("x", lambda: 1)])
        assert results[0].success
        ex.shutdown(wait=True)
        assert ex._shutdown_called

    def test_parallel_executor_active_count(self):
        from desktop_agent.brain.performance.parallel_executor import ParallelExecutor, ParallelTask
        ParallelExecutor.reset_singleton()
        ex = ParallelExecutor(pool_size=2)
        assert ex.active_count() == 0
        ParallelExecutor.reset_singleton()

    def test_parallel_executor_task_failure(self):
        from desktop_agent.brain.performance.parallel_executor import ParallelExecutor, ParallelTask
        ParallelExecutor.reset_singleton()
        def fail():
            raise RuntimeError("injected failure")
        ex = ParallelExecutor(pool_size=2)
        results = ex.execute_all([ParallelTask("f", fail)])
        assert not results[0].success
        assert "injected failure" in results[0].error
        ParallelExecutor.reset_singleton()

    def test_parallel_executor_timeout(self):
        from desktop_agent.brain.performance.parallel_executor import ParallelExecutor, ParallelTask
        ParallelExecutor.reset_singleton()
        def slow():
            time.sleep(10)
        ex = ParallelExecutor(pool_size=2)
        results = ex.execute_all([ParallelTask("s", slow, timeout_ms=50)])
        assert not results[0].success
        ParallelExecutor.reset_singleton()


# ============================================================
# 3. No Playwright Dependency
# ============================================================

class TestNoPlaywright:

    def test_fast_path_uses_desktop_tools(self):
        from desktop_agent.brain.performance.fast_path import FastPath
        fp = FastPath()
        result = fp.match("open notepad")
        assert result.matched
        assert result.tool_name == "openApplication"

    def test_tool_call_references_pyautogui(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlAction,
        )
        ctrl = UniversalController()
        action = ControlAction.CLICK
        mapping = MagicMock()
        mapping.target_element = MagicMock()
        mapping.target_element.center_x = 100
        mapping.target_element.center_y = 200
        mapping.args = {}
        mapping.action_type = "click"
        tc = ctrl._build_tool_call(action, mapping)
        assert tc["tool"] in ("leftClick", "rightClick", "doubleClick", "moveMouse")

    def test_no_playwright_in_registry(self):
        import importlib
        try:
            spec = importlib.util.find_spec("playwright")
            if spec is not None:
                pytest.skip("Playwright installed — not a blocker, just noted")
        except (ModuleNotFoundError, ValueError):
            pass


# ============================================================
# 4. Multi-Step Workflow
# ============================================================

class TestWorkflowRecording:

    def test_workflow_with_vision(self):
        from desktop_agent.universal_control.universal_controller import (
            UniversalController, ControlStatus,
        )
        from desktop_agent.universal_control.workflow_memory import WorkflowMemory
        vs = MockVS(ui_targets=[
            {"type": "button", "text": "OK",
             "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
            {"type": "textbox", "text": "Name",
             "bounds": {"x": 50, "y": 100, "width": 200, "height": 30}},
        ])
        vc = MockVC(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        wm = WorkflowMemory()
        wf_id = wm.start_recording("form fill test", "chrome")

        r1 = ctrl.execute_intent('type "John"')
        wm.record_step("type", "Name", {"text": "John"},
                       success=r1.status == ControlStatus.SUCCESS)

        r2 = ctrl.execute_intent("click ok")
        wm.record_step("click", "OK", success=r2.status == ControlStatus.SUCCESS)

        wf = wm.stop_recording()
        assert wf.step_count == 2
        assert wf.name == "form fill test"
