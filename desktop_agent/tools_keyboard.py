"""
MYRAA Desktop Control V3
Keyboard Tools

Responsibilities:
- Type text
- Press keys
- Hold keys
- Release keys
- Execute hotkeys

No AI logic.
No Planner logic.
"""

from __future__ import annotations

from typing import Any, Dict

import pyautogui

from desktop_agent.registry import register, ToolError


# ---------------------------------------------------------
# Type Text
# ---------------------------------------------------------

@register("typeText")
def type_text(args: Dict[str, Any]) -> Dict[str, Any]:

    text = args.get("text")

    if not text:
        raise ToolError("text is required")

    pyautogui.write(str(text), interval=0.03)

    return {
        "result": "Text typed.",
        "text": text,
    }


# ---------------------------------------------------------
# Press Key
# ---------------------------------------------------------

@register("pressKey")
def press_key(args: Dict[str, Any]) -> Dict[str, Any]:

    key = args.get("key")

    if not key:
        raise ToolError("key is required")

    pyautogui.press(str(key))

    return {
        "result": "Key pressed.",
        "key": key,
    }


# ---------------------------------------------------------
# Hold Key
# ---------------------------------------------------------

@register("keyDown")
def key_down(args: Dict[str, Any]) -> Dict[str, Any]:

    key = args.get("key")

    if not key:
        raise ToolError("key is required")

    pyautogui.keyDown(str(key))

    return {
        "result": "Key held down.",
        "key": key,
    }


# ---------------------------------------------------------
# Release Key
# ---------------------------------------------------------

@register("keyUp")
def key_up(args: Dict[str, Any]) -> Dict[str, Any]:

    key = args.get("key")

    if not key:
        raise ToolError("key is required")

    pyautogui.keyUp(str(key))

    return {
        "result": "Key released.",
        "key": key,
    }


# ---------------------------------------------------------
# Hotkey
# ---------------------------------------------------------

@register("hotkey")
def hotkey(args: Dict[str, Any]) -> Dict[str, Any]:

    keys = args.get("keys")

    if not keys:
        raise ToolError("keys are required")

    if isinstance(keys, str):
        keys = [keys]

    pyautogui.hotkey(*keys)

    return {
        "result": "Hotkey executed.",
        "keys": keys,
    }


__all__ = [
    "type_text",
    "press_key",
    "key_down",
    "key_up",
    "hotkey",
]