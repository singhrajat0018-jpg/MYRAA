"""
MYRAA Cognitive Engine

Action Builder
"""

from __future__ import annotations

from typing import Any

from ..models.action_types import ActionType
from ..models.plan_step import PlanStep


class ActionBuilder:
    """
    Factory responsible for creating planner steps.
    """

    def __init__(self) -> None:
        self._step_id = 0

    # =====================================================
    # Internal
    # =====================================================

    def _next_id(self) -> int:
        self._step_id += 1
        return self._step_id

    def _build(
        self,
        *,
        action: ActionType,
        name: str,
        description: str = "",
        parameters: dict[str, Any] | None = None,
        timeout: float = 30.0,
        requires_verification: bool = True,
    ) -> PlanStep:

        return PlanStep(
            id=self._next_id(),
            name=name,
            action=action,
            description=description,
            parameters=parameters or {},
            timeout=timeout,
            requires_verification=requires_verification,
        )

    # =====================================================
    # Mouse
    # =====================================================

    def click(self, target: Any) -> PlanStep:
        return self._build(
            action=ActionType.CLICK,
            name="Click",
            description=f"Click '{target}'",
            parameters={"target": target},
        )

    def double_click(self, target: Any) -> PlanStep:
        return self._build(
            action=ActionType.DOUBLE_CLICK,
            name="Double Click",
            description=f"Double click '{target}'",
            parameters={"target": target},
        )

    def right_click(self, target: Any) -> PlanStep:
        return self._build(
            action=ActionType.RIGHT_CLICK,
            name="Right Click",
            description=f"Right click '{target}'",
            parameters={"target": target},
        )

    # =====================================================
    # Keyboard
    # =====================================================

    def type_text(self, text: str) -> PlanStep:
        return self._build(
            action=ActionType.TYPE_TEXT,
            name="Type Text",
            description="Type text",
            parameters={"text": text},
        )

    def press_key(self, key: str) -> PlanStep:
        return self._build(
            action=ActionType.PRESS_KEY,
            name="Press Key",
            description=f"Press {key}",
            parameters={"key": key},
        )

    def hotkey(self, *keys: str) -> PlanStep:
        return self._build(
            action=ActionType.HOTKEY,
            name="Hotkey",
            description="+".join(keys),
            parameters={"keys": list(keys)},
        )

    # =====================================================
    # Applications
    # =====================================================

    def open_application(self, application: str) -> PlanStep:
        return self._build(
            action=ActionType.OPEN_APPLICATION,
            name="Open Application",
            description=f"Open {application}",
            parameters={"application": application},
        )

    def close_application(self, application: str) -> PlanStep:
        return self._build(
            action=ActionType.CLOSE_APPLICATION,
            name="Close Application",
            description=f"Close {application}",
            parameters={"application": application},
        )

    # =====================================================
    # Browser
    # =====================================================

    def open_url(self, url: str) -> PlanStep:
        return self._build(
            action=ActionType.OPEN_URL,
            name="Open URL",
            description=url,
            parameters={"url": url},
        )

    # =====================================================
    # Synchronization
    # =====================================================

    def wait(self, seconds: float) -> PlanStep:
        return self._build(
            action=ActionType.WAIT,
            name="Wait",
            description=f"Wait {seconds} seconds",
            parameters={"seconds": seconds},
            timeout=seconds,
            requires_verification=False,
        )

    # =====================================================
    # Vision
    # =====================================================

    def verify_element(self, target: Any) -> PlanStep:
        return self._build(
            action=ActionType.VERIFY_ELEMENT,
            name="Verify Element",
            description=f"Verify '{target}'",
            parameters={"target": target},
        )

    def capture_screen(self) -> PlanStep:
        return self._build(
            action=ActionType.CAPTURE_SCREEN,
            name="Capture Screen",
            description="Capture current screen",
            requires_verification=False,
        )

    def tool_call(self, tool_name, parameters):

        print("\n========== ACTION BUILDER ==========")
        print("Tool       :", tool_name)
        print("Parameters :", parameters)
        print("===================================\n")

        return self._build(
            action=ActionType.CUSTOM,
            name=f"Tool: {tool_name}",
            description=f"Execute {tool_name}",
            parameters={
                "tool_name": tool_name,
                "parameters": parameters,
            },
            requires_verification=False,
        )