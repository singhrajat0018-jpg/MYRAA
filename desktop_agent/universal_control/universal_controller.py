"""Universal Controller — the main orchestrator for universal app control.

Consumes existing ContinuousVisionController output.
Executes actions via existing desktop/browser tools.
Verifies results via ContinuousVisionController.verify_action().

NO screenshot capture. NO independent vision pipeline.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .ui_discovery import UIDiscovery, DiscoveryResult
from .ui_element import UniversalElement, ElementType, InteractiveRole
from .semantic_mapper import SemanticMapper, MappingResult

log = logging.getLogger(__name__)


class ControlAction(Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    TOGGLE = "toggle"
    READ = "read"
    OPEN = "open"
    CLOSE = "close"
    NAVIGATE = "navigate"
    HOTKEY = "hotkey"
    UNKNOWN = "unknown"


class ControlStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NO_VISION = "no_vision"
    NO_ELEMENT = "no_element"
    DEGRADED = "degraded"


@dataclass
class ControlResult:
    status: ControlStatus
    action: ControlAction
    element: Optional[UniversalElement]
    mapping: Optional[MappingResult]
    verified: bool
    execution_ms: float
    verification_ms: float = 0.0
    error: str = ""
    tool_call: dict = field(default_factory=dict)
    verification_result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "action": self.action.value,
            "element_id": self.element.element_id if self.element else None,
            "verified": self.verified,
            "execution_ms": round(self.execution_ms, 1),
            "error": self.error,
        }


class UniversalController:
    """Orchestrates universal app control by consuming existing vision output.

    Flow:
    1. Read VisualState from ContinuousVisionController
    2. Discover elements via UIDiscovery.from_visual_state()
    3. Map intent via SemanticMapper
    4. Execute action via existing desktop/browser tools
    5. Verify result via ContinuousVisionController.verify_action()

    NO independent capture or vision pipeline.
    """

    def __init__(self, vision_controller: Optional[Any] = None,
                 tool_executor: Optional[Callable] = None):
        self._vision = vision_controller
        self._tool_executor = tool_executor
        self._discovery = UIDiscovery()
        self._mapper = SemanticMapper()
        self._lock = threading.Lock()
        self._action_history: list[ControlResult] = []
        self._workflow_recorder: Optional[Any] = None

    def set_vision_controller(self, controller: Any):
        """Set the ContinuousVisionController to consume."""
        self._vision = controller

    def set_tool_executor(self, executor: Callable):
        """Set the tool execution function (e.g., CommandDispatcher.dispatch)."""
        self._tool_executor = executor

    def execute_intent(self, intent: str) -> ControlResult:
        """Execute a natural language intent against the current visual state.

        This is the main entry point. It:
        1. Reads current VisualState from ContinuousVisionController
        2. Discovers UI elements from that state
        3. Maps the intent to a concrete action
        4. Executes the action via existing tools
        5. Verifies the result via vision
        """
        start = time.perf_counter()
        visual_state = self._get_visual_state()
        if visual_state is None:
            return ControlResult(
                status=ControlStatus.NO_VISION,
                action=ControlAction.UNKNOWN,
                element=None, mapping=None,
                verified=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                error="No visual state available from ContinuousVisionController",
            )

        discovery = self._discovery.from_visual_state(visual_state)
        mapping = self._mapper.map_intent(intent, discovery.elements)

        if mapping.target_element is None:
            return ControlResult(
                status=ControlStatus.NO_ELEMENT,
                action=ControlAction(mapping.action_type if mapping.action_type else "unknown"),
                element=None, mapping=mapping,
                verified=False,
                execution_ms=(time.perf_counter() - start) * 1000,
                error=f"No matching element for: {intent}",
            )

        action = self._parse_action(mapping.action_type)
        tool_call = self._build_tool_call(action, mapping)

        exec_start = time.perf_counter()
        exec_result = self._execute_tool(tool_call)
        exec_ms = (time.perf_counter() - exec_start) * 1000

        verify_start = time.perf_counter()
        verified = self._verify_result(action, mapping)
        verify_ms = (time.perf_counter() - verify_start) * 1000

        total_ms = (time.perf_counter() - start) * 1000
        status = ControlStatus.SUCCESS if verified else ControlStatus.PARTIAL

        result = ControlResult(
            status=status,
            action=action,
            element=mapping.target_element,
            mapping=mapping,
            verified=verified,
            execution_ms=exec_ms,
            verification_ms=verify_ms,
            tool_call=tool_call,
        )

        with self._lock:
            self._action_history.append(result)
            if len(self._action_history) > 200:
                self._action_history = self._action_history[-200:]

        return result

    def discover_elements(self) -> Optional[DiscoveryResult]:
        """Discover UI elements from current visual state."""
        vs = self._get_visual_state()
        if vs is None:
            return None
        return self._discovery.from_visual_state(vs)

    def find_element(self, hint: str) -> Optional[UniversalElement]:
        """Find an element by text/type hint from current visual state."""
        discovery = self.discover_elements()
        if discovery is None:
            return None
        return self._discovery.find_element(discovery.elements, hint)

    def get_action_history(self, n: int = 10) -> list[ControlResult]:
        with self._lock:
            return self._action_history[-n:]

    def _get_visual_state(self) -> Optional[Any]:
        if self._vision is None:
            return None
        try:
            return self._vision.get_current_state()
        except Exception as e:
            log.debug("Failed to get visual state: %s", e)
            return None

    def _parse_action(self, action_str: str) -> ControlAction:
        mapping = {
            "click": ControlAction.CLICK,
            "type": ControlAction.TYPE,
            "scroll": ControlAction.SCROLL,
            "toggle": ControlAction.TOGGLE,
            "read": ControlAction.READ,
            "open": ControlAction.OPEN,
            "close": ControlAction.CLOSE,
            "navigate": ControlAction.NAVIGATE,
        }
        return mapping.get(action_str, ControlAction.UNKNOWN)

    def _build_tool_call(self, action: ControlAction, mapping: MappingResult) -> dict:
        elem = mapping.target_element
        if action == ControlAction.CLICK:
            return {"tool": "leftClick", "args": {"x": elem.center_x, "y": elem.center_y}}
        if action == ControlAction.TYPE:
            text = mapping.args.get("text", "")
            return {"tool": "typeText", "args": {"text": text}}
        if action == ControlAction.SCROLL:
            direction = mapping.args.get("direction", "down")
            clicks = 3 if direction == "down" else -3
            return {"tool": "scrollMouse", "args": {"clicks": clicks}}
        if action == ControlAction.HOTKEY:
            keys = mapping.args.get("keys", [])
            return {"tool": "hotkey", "args": {"keys": keys}}
        return {"tool": "unknown", "args": {}}

    def _execute_tool(self, tool_call: dict) -> Optional[Any]:
        if self._tool_executor is None:
            return None
        try:
            return self._tool_executor(tool_call["tool"], tool_call["args"])
        except Exception as e:
            log.debug("Tool execution failed: %s", e)
            return None

    def _verify_result(self, action: ControlAction, mapping: MappingResult) -> bool:
        if self._vision is None:
            return False
        try:
            expected = {}
            if action == ControlAction.CLICK:
                expected["visual_state"] = ""
            return self._vision.verify_action(expected).get("verified", False)
        except Exception:
            return False
