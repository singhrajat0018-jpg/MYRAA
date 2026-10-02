"""Phase E: Universal Control Tests.

Tests: UIDiscovery, SemanticMapper, UniversalController,
UniversalElement, AppProfile, WorkflowMemory, NotificationEngine.

Universal Control consumes existing ContinuousVisionController output.
NO screenshot capture. NO independent vision pipeline.
"""

import time
import threading
import pytest
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_agent.universal_control.ui_element import (
    UniversalElement, ElementType, InteractiveRole,
)
from desktop_agent.universal_control.ui_discovery import UIDiscovery, DiscoveryResult
from desktop_agent.universal_control.semantic_mapper import SemanticMapper, MappingResult
from desktop_agent.universal_control.universal_controller import (
    UniversalController, ControlResult, ControlStatus, ControlAction,
)
from desktop_agent.universal_control.app_profile import (
    AppProfile, AppCapability, ControlStrategy, AppProfileRegistry,
)
from desktop_agent.universal_control.workflow_memory import (
    WorkflowMemory, Workflow, WorkflowStep,
)
from desktop_agent.notifications.engine import (
    NotificationEngine, Notification, NotificationType, NotificationPriority,
)


@dataclass
class MockVisualState:
    application: str = "chrome"
    window_title: str = "Google - Chrome"
    page_type: str = "web_page"
    ui_targets: list = field(default_factory=list)
    visual_state: str = "browsing"
    confidence: float = 0.85
    timestamp: float = 0.0
    frame_id: int = 1
    has_error: bool = False
    changed: bool = False


@dataclass
class MockVisionController:
    current_state: Optional[MockVisualState] = None
    _verified: bool = True

    def get_current_state(self):
        return self.current_state

    def verify_action(self, expected: dict) -> dict:
        return {"verified": self._verified, "checks": []}


class TestUniversalElement:
    def test_from_visual_state_target(self):
        target = {
            "type": "button", "text": "OK",
            "bounds": {"x": 100, "y": 200, "width": 80, "height": 30},
            "confidence": 0.9,
        }
        elem = UniversalElement.from_visual_state_target(target, 0)
        assert elem.element_type == ElementType.BUTTON
        assert elem.label == "OK"
        assert elem.x == 100
        assert elem.center_x == 140
        assert elem.center_y == 215
        assert elem.role == InteractiveRole.PRIMARY_ACTION

    def test_from_visual_state_no_bounds(self):
        target = {"type": "text", "text": "Hello"}
        elem = UniversalElement.from_visual_state_target(target, 0)
        assert elem.element_type == ElementType.TEXT_LABEL

    def test_from_visual_state_list_bounds(self):
        target = {"type": "button", "text": "Click", "bounds": [10, 20, 50, 30]}
        elem = UniversalElement.from_visual_state_target(target, 0)
        assert elem.x == 10
        assert elem.width == 50

    def test_distance_to(self):
        e1 = UniversalElement("a", ElementType.BUTTON, "A", 0.9, x=0, y=0, width=10, height=10)
        e2 = UniversalElement("b", ElementType.BUTTON, "B", 0.9, x=10, y=0, width=10, height=10)
        assert e1.distance_to(e2) == 10.0

    def test_to_dict(self):
        elem = UniversalElement("a", ElementType.BUTTON, "OK", 0.9, x=10, y=20, width=50, height=30)
        d = elem.to_dict()
        assert d["type"] == "button"
        assert d["x"] == 10

    def test_contains_point(self):
        elem = UniversalElement("a", ElementType.BUTTON, "OK", 0.9, x=10, y=20, width=50, height=30)
        assert elem.contains_point(30, 30)
        assert not elem.contains_point(100, 100)


class TestUIDiscovery:
    def test_from_visual_state(self):
        vs = MockVisualState(ui_targets=[
            {"type": "button", "text": "OK", "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
            {"type": "text", "text": "Hello World", "bounds": {"x": 10, "y": 10, "width": 200, "height": 20}},
        ])
        disc = UIDiscovery()
        result = disc.from_visual_state(vs)
        assert result.total_elements == 2
        assert result.source == "visual_state"
        assert result.application == "chrome"

    def test_from_visual_state_empty(self):
        vs = MockVisualState(ui_targets=[])
        disc = UIDiscovery()
        result = disc.from_visual_state(vs)
        assert result.total_elements == 0

    def test_from_ocr_fallback(self):
        ocr = [
            {"text": "OK", "x": 100, "y": 200, "width": 80, "height": 30, "confidence": 0.9},
            {"text": "Cancel", "x": 200, "y": 200, "width": 80, "height": 30, "confidence": 0.85},
        ]
        disc = UIDiscovery()
        result = disc.from_ocr_fallback(ocr)
        assert result.source == "ocr_fallback"
        assert result.total_elements == 2

    def test_find_element(self):
        elements = [
            UniversalElement("a", ElementType.BUTTON, "Submit", 0.9),
            UniversalElement("b", ElementType.TEXT_FIELD, "Email", 0.8),
        ]
        disc = UIDiscovery()
        found = disc.find_element(elements, "submit")
        assert found is not None
        assert found.label == "Submit"

    def test_find_interactive(self):
        elements = [
            UniversalElement("a", ElementType.BUTTON, "OK", 0.9, role=InteractiveRole.PRIMARY_ACTION),
            UniversalElement("b", ElementType.TEXT_LABEL, "Label", 0.9, role=InteractiveRole.NONE),
        ]
        disc = UIDiscovery()
        interactive = disc.find_interactive(elements)
        assert len(interactive) == 1
        assert interactive[0].label == "OK"

    def test_find_by_type(self):
        elements = [
            UniversalElement("a", ElementType.BUTTON, "OK", 0.9),
            UniversalElement("b", ElementType.BUTTON, "Cancel", 0.9),
            UniversalElement("c", ElementType.TEXT_FIELD, "Input", 0.8),
        ]
        disc = UIDiscovery()
        buttons = disc.find_by_type(elements, ElementType.BUTTON)
        assert len(buttons) == 2


class TestSemanticMapper:
    def test_click_intent(self):
        elements = [
            UniversalElement("a", ElementType.BUTTON, "Submit", 0.9, x=100, y=200, width=80, height=30),
        ]
        mapper = SemanticMapper()
        result = mapper.map_intent("click submit", elements)
        assert result.target_element is not None
        assert result.action_type == "click"
        assert result.args["x"] == 140

    def test_type_intent(self):
        elements = [
            UniversalElement("a", ElementType.TEXT_FIELD, "Search", 0.9, x=100, y=200, width=200, height=30),
        ]
        mapper = SemanticMapper()
        result = mapper.map_intent('type "hello world"', elements)
        assert result.action_type == "type"
        assert result.args["text"] == "hello world"

    def test_no_match(self):
        elements = [
            UniversalElement("a", ElementType.TEXT_LABEL, "Label", 0.9),
        ]
        mapper = SemanticMapper()
        result = mapper.map_intent("click submit button", elements)
        assert result.target_element is None

    def test_fallback_elements(self):
        elements = [
            UniversalElement("a", ElementType.BUTTON, "OK", 0.9),
            UniversalElement("b", ElementType.BUTTON, "Submit", 0.85),
            UniversalElement("c", ElementType.BUTTON, "Confirm", 0.8),
        ]
        mapper = SemanticMapper()
        result = mapper.map_intent("click ok", elements)
        assert len(result.fallback_elements) <= 3


class TestUniversalController:
    def test_execute_intent_no_vision(self):
        ctrl = UniversalController()
        result = ctrl.execute_intent("click button")
        assert result.status == ControlStatus.NO_VISION

    def test_execute_intent_no_element(self):
        vs = MockVisualState(ui_targets=[])
        vc = MockVisionController(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent("click submit")
        assert result.status == ControlStatus.NO_ELEMENT

    def test_execute_intent_success(self):
        vs = MockVisualState(ui_targets=[
            {"type": "button", "text": "OK", "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVisionController(current_state=vs, _verified=True)
        ctrl = UniversalController(vision_controller=vc)
        result = ctrl.execute_intent("click ok")
        assert result.status == ControlStatus.SUCCESS
        assert result.verified
        assert result.tool_call["tool"] == "leftClick"

    def test_discover_elements(self):
        vs = MockVisualState(ui_targets=[
            {"type": "button", "text": "OK", "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVisionController(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        disc = ctrl.discover_elements()
        assert disc is not None
        assert disc.total_elements == 1

    def test_find_element(self):
        vs = MockVisualState(ui_targets=[
            {"type": "button", "text": "OK", "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVisionController(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        elem = ctrl.find_element("OK")
        assert elem is not None
        assert elem.label == "OK"

    def test_action_history(self):
        vs = MockVisualState(ui_targets=[
            {"type": "button", "text": "OK", "bounds": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ])
        vc = MockVisionController(current_state=vs)
        ctrl = UniversalController(vision_controller=vc)
        ctrl.execute_intent("click ok")
        history = ctrl.get_action_history()
        assert len(history) == 1


class TestAppProfile:
    def test_default_profiles(self):
        reg = AppProfileRegistry()
        chrome = reg.get("chrome")
        assert chrome is not None
        assert chrome.display_name == "Google Chrome"

    def test_has_capability(self):
        reg = AppProfileRegistry()
        chrome = reg.get("chrome")
        assert chrome.has_capability(AppCapability.TAB_NAVIGATION)
        assert not chrome.has_capability(AppCapability.VOICE)

    def test_get_shortcut(self):
        reg = AppProfileRegistry()
        chrome = reg.get("chrome")
        assert chrome.get_shortcut("new_tab") == "ctrl+t"

    def test_find_profile(self):
        reg = AppProfileRegistry()
        found = reg.find_profile("vscode")
        assert found is not None
        assert found.app_name == "vscode"

    def test_register_custom(self):
        reg = AppProfileRegistry()
        custom = AppProfile(app_name="myapp", display_name="My App")
        reg.register(custom)
        assert reg.get("myapp") is not None

    def test_all_profiles(self):
        reg = AppProfileRegistry()
        all_p = reg.all_profiles()
        assert len(all_p) >= 7


class TestWorkflowMemory:
    def test_record_workflow(self):
        wm = WorkflowMemory()
        wf_id = wm.start_recording("test workflow", "chrome")
        wm.record_step("click", "button", {"x": 100, "y": 200})
        wm.record_step("type", "field", {"text": "hello"})
        wf = wm.stop_recording()
        assert wf is not None
        assert wf.step_count == 2
        assert wf.name == "test workflow"

    def test_find_by_name(self):
        wm = WorkflowMemory()
        wm.start_recording("my workflow", "chrome")
        wm.stop_recording()
        found = wm.find_by_name("my")
        assert len(found) == 1

    def test_find_by_app(self):
        wm = WorkflowMemory()
        wm.start_recording("wf1", "chrome")
        wm.stop_recording()
        wm.start_recording("wf2", "notepad")
        wm.stop_recording()
        found = wm.find_by_app("chrome")
        assert len(found) == 1

    def test_record_run(self):
        wm = WorkflowMemory()
        wm.start_recording("test", "chrome")
        wf = wm.stop_recording()
        wm.record_run(wf.workflow_id, True)
        wm.record_run(wf.workflow_id, True)
        wm.record_run(wf.workflow_id, False)
        updated = wm.get_workflow(wf.workflow_id)
        assert updated.run_count == 3
        assert updated.success_count == 2

    def test_delete(self):
        wm = WorkflowMemory()
        wm.start_recording("test", "chrome")
        wf = wm.stop_recording()
        assert wm.delete_workflow(wf.workflow_id)
        assert wm.get_workflow(wf.workflow_id) is None

    def test_popular(self):
        wm = WorkflowMemory()
        for i in range(5):
            wm.start_recording(f"wf{i}", "chrome")
            wf = wm.stop_recording()
            for _ in range(i):
                wm.record_run(wf.workflow_id, True)
        popular = wm.popular_workflows(3)
        assert len(popular) == 3
        assert popular[0].run_count >= popular[1].run_count

    def test_clear(self):
        wm = WorkflowMemory()
        wm.start_recording("test", "chrome")
        wm.stop_recording()
        wm.clear()
        assert len(wm.list_all()) == 0

    def test_max_limit(self):
        wm = WorkflowMemory(max_workflows=3)
        for i in range(5):
            wm.start_recording(f"wf{i}", "chrome")
            wm.stop_recording()
        assert len(wm.list_all()) <= 3


class TestNotificationEngine:
    def setup_method(self):
        NotificationEngine.reset_singleton()

    def teardown_method(self):
        NotificationEngine.reset_singleton()

    def test_notify(self):
        engine = NotificationEngine()
        n = engine.notify(NotificationType.TASK_COMPLETE, "Done", "Task finished")
        assert n.notification_type == NotificationType.TASK_COMPLETE
        assert n.title == "Done"

    def test_task_complete(self):
        engine = NotificationEngine()
        n = engine.task_complete("Open App", "Notepad opened")
        assert n.priority == NotificationPriority.LOW

    def test_task_failed(self):
        engine = NotificationEngine()
        n = engine.task_failed("Open App", "Failed to find")
        assert n.priority == NotificationPriority.HIGH

    def test_follow_up(self):
        engine = NotificationEngine()
        n = engine.follow_up("Which file?")
        assert n.notification_type == NotificationType.FOLLOW_UP

    def test_suggestion(self):
        engine = NotificationEngine()
        n = engine.suggestion("Try using keyboard shortcuts")
        assert n.notification_type == NotificationType.SUGGESTION

    def test_degraded_warning(self):
        engine = NotificationEngine()
        n = engine.degraded_warning("Vision pipeline degraded")
        assert n.priority == NotificationPriority.HIGH

    def test_on_notification_callback(self):
        engine = NotificationEngine()
        received = []
        engine.on_notification(lambda n: received.append(n))
        engine.notify(NotificationType.SYSTEM, "Test", "msg")
        assert len(received) == 1

    def test_mark_read(self):
        engine = NotificationEngine()
        n = engine.notify(NotificationType.SYSTEM, "Test", "msg")
        assert engine.mark_read(n.notification_id)
        assert len(engine.unread()) == 0

    def test_dismiss(self):
        engine = NotificationEngine()
        n = engine.notify(NotificationType.SYSTEM, "Test", "msg")
        assert engine.dismiss(n.notification_id)
        assert len(engine.unread()) == 0

    def test_unread(self):
        engine = NotificationEngine()
        n1 = engine.notify(NotificationType.SYSTEM, "A", "msg1")
        n2 = engine.notify(NotificationType.SYSTEM, "B", "msg2")
        engine.mark_read(n1.notification_id)
        unread = engine.unread()
        assert len(unread) == 1
        assert unread[0].notification_id == n2.notification_id

    def test_recent(self):
        engine = NotificationEngine()
        for i in range(5):
            engine.notify(NotificationType.SYSTEM, f"N{i}", f"msg{i}")
        recent = engine.recent(3)
        assert len(recent) == 3

    def test_by_type(self):
        engine = NotificationEngine()
        engine.notify(NotificationType.TASK_COMPLETE, "A", "a")
        engine.notify(NotificationType.TASK_FAILED, "B", "b")
        engine.notify(NotificationType.TASK_COMPLETE, "C", "c")
        complete = engine.by_type(NotificationType.TASK_COMPLETE)
        assert len(complete) == 2

    def test_stats(self):
        engine = NotificationEngine()
        engine.notify(NotificationType.TASK_COMPLETE, "A", "a")
        engine.notify(NotificationType.TASK_FAILED, "B", "b")
        s = engine.stats()
        assert s["total"] == 2
        assert s["by_type"]["task_complete"] == 1

    def test_auto_dismiss_expired(self):
        engine = NotificationEngine()
        n = engine.notify(NotificationType.SYSTEM, "Test", "msg",
                          auto_dismiss_ms=1)
        time.sleep(0.01)
        dismissed = engine.auto_dismiss_expired()
        assert n.notification_id in dismissed

    def test_singleton(self):
        e1 = NotificationEngine.singleton()
        e2 = NotificationEngine.singleton()
        assert e1 is e2

    def test_clear(self):
        engine = NotificationEngine()
        engine.notify(NotificationType.SYSTEM, "Test", "msg")
        engine.clear()
        assert engine.stats()["total"] == 0
