"""
Window management: minimize / maximize / close the active window or switch apps.

Uses win32gui for the foreground window and pygetwindow for title-based lookups,
with graceful degradation if a backend isn't present.
"""

from __future__ import annotations

import platform
import time
from typing import Any, Dict
from .desktop.windows.application_locator import ApplicationLocator

from .registry import ToolError, register

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
SW_HIDE = 0

@register("minimizeWindow")
def minimize_window(args: Dict[str, Any]) -> Dict[str, Any]:

    title = args.get("title") or args.get("application")

    if not title:
        raise ToolError("Application name is required.")

    locator = ApplicationLocator()

    if not locator.minimize(str(title)):
        raise ToolError(f"Could not minimize '{title}'.")

    return {
        "result": f"Minimized {title}."
    }


@register("maximizeWindow")
def maximize_window(args: Dict[str, Any]) -> Dict[str, Any]:

    title = args.get("title") or args.get("application")

    if not title:
        raise ToolError("Application name is required.")

    locator = ApplicationLocator()

    if not locator.maximize(str(title)):
        raise ToolError(f"Could not maximize '{title}'.")

    return {
        "result": f"Maximized {title}."
    }

@register("restoreWindow")
def restore_window(args: Dict[str, Any]) -> Dict[str, Any]:

    title = args.get("title") or args.get("application")

    if not title:
        raise ToolError("Application name is required.")

    locator = ApplicationLocator()

    if not locator.restore(str(title)):
        raise ToolError(f"Could not restore '{title}'.")

    return {
        "result": f"Restored {title}."
    }
    


@register("closeWindow")
def close_window(args: Dict[str, Any]) -> Dict[str, Any]:

    title = args.get("title") or args.get("application")

    if not title:
        raise ToolError("Application name is required.")

    locator = ApplicationLocator()

    if not locator.close(str(title)):
        raise ToolError(f"Could not close '{title}'.")

    return {
        "result": f"Closed {title}."
    }


@register("activateWindow")
def activate_window(args: Dict[str, Any]) -> Dict[str, Any]:

    title = args.get("title") or args.get("application")

    if not title:
        raise ToolError("Application name is required.")

    locator = ApplicationLocator()

    if not locator.focus(str(title)):
        raise ToolError(f"Could not activate '{title}'.")

    return {
        "result": f"Activated {title}."
    }


@register("switchApplication")
def switch_application(args):

    title = args.get("title") or args.get("application")

    if not title:
        raise ToolError("Parameter 'application' is required.")

    locator = ApplicationLocator()

    info = locator.locate(str(title))

    if not info.running:
        raise ToolError(f"Application '{title}' is not running.")

    if not info.hwnd:
        raise ToolError(f"No window found for '{title}'.")

    if not locator.focus(str(title)):
        raise ToolError(f"Unable to focus '{title}'.")

    return {
        "result": f"Switched to {info.title}."
    }

__all__ = [
    "minimize_window",
    "maximize_window",
     "restore_window",
    "activate_window",
    "close_window",
    "switch_application",
]
