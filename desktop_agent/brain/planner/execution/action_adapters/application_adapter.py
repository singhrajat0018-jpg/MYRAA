"""
MYRAA Cognitive Engine

Application Action Adapter

Handles desktop application actions.

Supported:

- OPEN_APPLICATION
- CLOSE_APPLICATION
- ACTIVATE_WINDOW
- MINIMIZE_WINDOW
- MAXIMIZE_WINDOW
- RESTORE_WINDOW
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError

from desktop_agent.tools_applications import (
    open_application,
    close_application,
)
from desktop_agent.desktop.applications.application_bridge import (
        ApplicationBridge,
    )



class ApplicationAdapter(BaseAdapter):
    """
    Adapter for Windows application control.
    """



    def __init__(
        self,
        application_tools=None,
    ) -> None:

        super().__init__(
            name="application_adapter"
        )

        self.bridge = ApplicationBridge()

        self.application_tools = (
            application_tools
        )

    

        self.bridge = ApplicationBridge()


    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {

            ActionType.OPEN_APPLICATION,

            ActionType.CLOSE_APPLICATION,

            ActionType.ACTIVATE_WINDOW,

            ActionType.MINIMIZE_WINDOW,

            ActionType.MAXIMIZE_WINDOW,

            ActionType.RESTORE_WINDOW,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:


        if action_type == ActionType.OPEN_APPLICATION:

            return await self._open_application(
                parameters
            )



        if action_type == ActionType.CLOSE_APPLICATION:

            return await self._close_application(
                parameters
            )



        if action_type == ActionType.ACTIVATE_WINDOW:

            return await self._activate_window(
                parameters
            )



        if action_type == ActionType.MINIMIZE_WINDOW:

            return await self._minimize_window(
                parameters
            )



        if action_type == ActionType.MAXIMIZE_WINDOW:

            return await self._maximize_window(
                parameters
            )



        if action_type == ActionType.RESTORE_WINDOW:

            return await self._restore_window(
                parameters
            )



        raise ExecutionError(

            f"Unsupported application action: {action_type}"

        )



    # =====================================================
    # Actions
    # =====================================================


    async def _open_application(
        self,
        parameters,
    ):

        application = parameters.get(
            "application"
        )


        if not application:

            raise ExecutionError(
                "Application name missing"
            )


        return await self.bridge.open_application(
            application
        )


    async def _close_application(
        self,
        parameters,
    ):

        application = parameters.get(
            "application"
        )


        return await self.bridge.close_application(
            application
        )


    async def _activate_window(
        self,
        parameters,
    ):

        application = (
            parameters.get("application")
            or parameters.get("window")
        )

        if not application:
            raise ExecutionError(
                "Application name missing"
            )

        return await self.bridge.activate_window(
            application
        )


    async def _minimize_window(
        self,
        parameters,
    ):

        application = (
            parameters.get("application")
            or parameters.get("window")
        )

        if not application:
            raise ExecutionError(
                "Application name missing"
            )

        return await self.bridge.minimize_window(
            application
        )


    async def _maximize_window(
        self,
        parameters,
    ):

        application = (
            parameters.get("application")
            or parameters.get("window")
        )

        if not application:
            raise ExecutionError(
                "Application name missing"
            )

        return await self.bridge.maximize_window(
            application
        )


    async def _restore_window(
        self,
        parameters,
    ):

        application = (
            parameters.get("application")
            or parameters.get("window")
        )

        if not application:
            raise ExecutionError(
                "Application name missing"
            )

        return await self.bridge.restore_window(
            application
        )
        