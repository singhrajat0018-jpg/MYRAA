"""
MYRAA Desktop Application Bridge

Thin bridge between the planner layer and the low-level
application tools.

The bridge contains no business logic. It simply forwards
requests to tools_applications.py so the architecture remains
consistent with the File System module.
"""

from __future__ import annotations

from typing import Any, Dict

from desktop_agent.tools_applications import (
    open_application,
    close_application,
)

from desktop_agent.desktop.windows.application_locator import (
    ApplicationLocator,
)
    

class ApplicationBridge:
    """Bridge for Windows application actions."""


    def __init__(self):

        self.locator = ApplicationLocator()

    ...

    async def activate_window(
        self,
        application: str,
    ):

        return {
            "status": self.locator.focus(application)
        }

    async def minimize_window(
        self,
        application: str,
    ):

        return {
            "status": self.locator.minimize(application)
        }

    async def maximize_window(
        self,
        application: str,
    ):

        return {
            "status": self.locator.maximize(application)
        }

    async def restore_window(
        self,
        application: str,
    ):

        return {
            "status": self.locator.restore(application)
        }

    async def open_application(
        self,
        application: str,
    ) -> Dict[str, Any]:

        return open_application(
            {
                "application": application,
            }
        )

    async def close_application(
        self,
        application: str,
    ) -> Dict[str, Any]:

        return close_application(
            {
                "application": application,
            }
        )

    