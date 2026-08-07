"""
MYRAA Desktop Control V3
Mouse Tools

Responsibilities:
- Move mouse
- Left click
- Right click
- Double click
- Middle click
- Drag mouse
- Scroll mouse
- Get mouse position

No AI logic.
No Planner logic.
"""

from __future__ import annotations

from typing import Any, Dict

import pyautogui

from desktop_agent.registry import register, ToolError


# ---------------------------------------------------------
# Move Mouse
# ---------------------------------------------------------

@register("moveMouse")
def move_mouse(args: Dict[str, Any]) -> Dict[str, Any]:

    x = args.get("x")
    y = args.get("y")
    duration = float(args.get("duration", 0.2))

    if x is None or y is None:
        raise ToolError("x and y are required")

    pyautogui.moveTo(int(x), int(y), duration=duration)

    return {
        "result": "Mouse moved.",
        "x": x,
        "y": y,
    }


# ---------------------------------------------------------
# Left Click
# ---------------------------------------------------------

@register("leftClick")
def left_click(args: Dict[str, Any]) -> Dict[str, Any]:

    pyautogui.click()

    return {
        "result": "Left click executed."
    }


# ---------------------------------------------------------
# Right Click
# ---------------------------------------------------------

@register("rightClick")
def right_click(args: Dict[str, Any]) -> Dict[str, Any]:

    pyautogui.rightClick()

    return {
        "result": "Right click executed."
    }


# ---------------------------------------------------------
# Double Click
# ---------------------------------------------------------

@register("doubleClick")
def double_click(args: Dict[str, Any]) -> Dict[str, Any]:

    pyautogui.doubleClick()

    return {
        "result": "Double click executed."
    }


# ---------------------------------------------------------
# Middle Click
# ---------------------------------------------------------

@register("middleClick")
def middle_click(args: Dict[str, Any]) -> Dict[str, Any]:

    pyautogui.middleClick()

    return {
        "result": "Middle click executed."
    }


# ---------------------------------------------------------
# Drag Mouse
# ---------------------------------------------------------

@register("dragMouse")
def drag_mouse(args: Dict[str, Any]) -> Dict[str, Any]:

    x = args.get("x")
    y = args.get("y")
    duration = float(args.get("duration", 0.5))

    if x is None or y is None:
        raise ToolError("x and y are required")

    pyautogui.dragTo(
        int(x),
        int(y),
        duration=duration,
        button="left",
    )

    return {
        "result": "Mouse dragged.",
        "x": x,
        "y": y,
    }


# ---------------------------------------------------------
# Scroll
# ---------------------------------------------------------

@register("scrollMouse")
def scroll_mouse(args: Dict[str, Any]) -> Dict[str, Any]:

    clicks = int(args.get("clicks", 500))

    pyautogui.scroll(clicks)

    return {
        "result": "Mouse scrolled.",
        "clicks": clicks,
    }


# ---------------------------------------------------------
# Mouse Position
# ---------------------------------------------------------

@register("mousePosition")
def mouse_position(args: Dict[str, Any]) -> Dict[str, Any]:

    x, y = pyautogui.position()

    return {
        "x": x,
        "y": y,
    }


__all__ = [
    "move_mouse",
    "left_click",
    "right_click",
    "double_click",
    "middle_click",
    "drag_mouse",
    "scroll_mouse",
    "mouse_position",
]