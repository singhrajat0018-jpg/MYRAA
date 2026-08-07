"""
MYRAA Desktop Control V3
Window Manager

Responsibilities:
- List windows
- Get active window
- Focus window
- Minimize window
- Maximize window
- Restore window
- Close window

No AI logic.
No Planner logic.
No Registry logic.
"""

from __future__ import annotations
from typing import List, Optional
from .models import WindowInfo
import pygetwindow as gw

class WindowManager:

    # -----------------------------
    # Internal
    # -----------------------------

    def _find_window(self, title: str):

        title = title.lower().strip()

        for win in gw.getAllWindows():

            if not win.title:
                continue

            if title in win.title.lower():
                return win

        return None
    # -----------------------------
    # Query
    # -----------------------------

    def list_windows(self) -> List[WindowInfo]:

        windows = []

        active = gw.getActiveWindow()

        for win in gw.getAllWindows():

            if not win.title:
                continue

            windows.append(
                WindowInfo(
                    hwnd=win._hWnd,
                    title=win.title,
                    left=win.left,
                    top=win.top,
                    width=win.width,
                    height=win.height,
                    is_active=(win == active)
                )
            )

        return windows

    def get_active_window(self) -> Optional[WindowInfo]:

        win = gw.getActiveWindow()

        if win is None:
            return None

        return WindowInfo(
            hwnd=win._hWnd,
            title=win.title,
            left=win.left,
            top=win.top,
            width=win.width,
            height=win.height,
            is_active=True
        )

    def window_exists(self, title: str) -> bool:

        return self._find_window(title) is not None

    # -----------------------------
    # Actions
    # -----------------------------

    def focus_window(self, title: str) -> bool:

        win = self._find_window(title)

        if not win:
            return False

        try:
            win.activate()
            return True
        except Exception:
            return False

    def minimize_hwnd(self, hwnd: int) -> bool:
        for win in gw.getAllWindows():
            if getattr(win, "_hWnd", None) == hwnd:
                try:
                    win.minimize()
                    return True
                except Exception:
                    return False
        return False


    def maximize_hwnd(self, hwnd: int) -> bool:
        for win in gw.getAllWindows():
            if getattr(win, "_hWnd", None) == hwnd:
                try:
                    win.maximize()
                    return True
                except Exception:
                    return False
        return False


    def restore_hwnd(self, hwnd: int) -> bool:
        for win in gw.getAllWindows():
            if getattr(win, "_hWnd", None) == hwnd:
                try:
                    win.restore()
                    return True
                except Exception:
                    return False
        return False


    def close_hwnd(self, hwnd: int) -> bool:
        for win in gw.getAllWindows():
            if getattr(win, "_hWnd", None) == hwnd:
                try:
                    win.close()
                    return True
                except Exception:
                    return False
        return False

    def focus_hwnd(self, hwnd: int) -> bool:

        for win in gw.getAllWindows():

            if getattr(win, "_hWnd", None) == hwnd:

                try:
                    win.activate()
                    return True
                except Exception:
                    return False

        return False