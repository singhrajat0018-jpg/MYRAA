"""
MYRAA Desktop Control V3
Application Locator

Responsibilities:
- Resolve application information
- Check if application is running
- Find associated window
- Return unified application state

No AI logic.
No Planner logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from .models import ApplicationInfo
from .process_manager import ProcessManager
from .window_manager import WindowManager

@dataclass
class ApplicationInfo:

    name: str

    installed: bool
    running: bool

    pid: Optional[int] = None
    process_name: Optional[str] = None
    exe: Optional[str] = None
    status: Optional[str] = None

    hwnd: Optional[int] = None
    title: Optional[str] = None


class ApplicationLocator:

    def __init__(self):
        self.process = ProcessManager()
        self.windows = WindowManager()

    def locate(self, application: str) -> ApplicationInfo:

        app = application.lower().strip()

        # ------------------------
        # Window Lookup
        # ------------------------

        matched_window = None

        for win in self.windows.list_windows():

            if app in (win.title or "").lower():

                matched_window = win
                break

        # ------------------------
        # Process Lookup
        # ------------------------

        process = self.process.find_process(app)

        # ------------------------
        # Build Result
        # ------------------------

        return ApplicationInfo(

            name=application,

            installed=(process is not None) or (matched_window is not None),

            running=(process is not None) or (matched_window is not None),

            pid=process.pid if process else None,

            process_name=process.name if process else None,

            exe=process.exe if process else None,

            status=process.status if process else None,

            hwnd=matched_window.hwnd if matched_window else None,

            title=matched_window.title if matched_window else None,
        )

    def focus(self, application: str) -> bool:

        info = self.locate(application)

        if not info.hwnd:
            return False

        return self.windows.focus_hwnd(info.hwnd)

    def minimize(self, application: str) -> bool:

        info = self.locate(application)

        return bool(info.hwnd and self.windows.minimize_hwnd(info.hwnd))

    def maximize(self, application: str) -> bool:

        info = self.locate(application)

        return bool(info.hwnd and self.windows.maximize_hwnd(info.hwnd))

    def restore(self, application: str) -> bool:

        info = self.locate(application)

        return bool(info.hwnd and self.windows.restore_hwnd(info.hwnd))

    def close(self, application: str) -> bool:
        info = self.locate(application)

        if not info.running:
            return False

        if not info.hwnd:
            return False

        return self.windows.close_hwnd(info.hwnd)