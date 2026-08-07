"""
MYRAA Cognitive Engine

Browser Action Adapter

Handles browser operations.

Supported:

- OPEN_URL
- NEW_TAB
- CLOSE_TAB
- SWITCH_TAB
- REFRESH_PAGE
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError



class BrowserAdapter(BaseAdapter):
    """
    Adapter for browser automation.
    """



    def __init__(
        self,
        browser_tools=None,
    ) -> None:


        super().__init__(
            name="browser_adapter"
        )


        self.browser_tools = (
            browser_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {

            ActionType.OPEN_URL,

            ActionType.NEW_TAB,

            ActionType.CLOSE_TAB,

            ActionType.SWITCH_TAB,

            ActionType.REFRESH_PAGE,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:


        if action_type == ActionType.OPEN_URL:

            return await self._open_url(
                parameters
            )



        if action_type == ActionType.NEW_TAB:

            return await self._new_tab(
                parameters
            )



        if action_type == ActionType.CLOSE_TAB:

            return await self._close_tab(
                parameters
            )



        if action_type == ActionType.SWITCH_TAB:

            return await self._switch_tab(
                parameters
            )



        if action_type == ActionType.REFRESH_PAGE:

            return await self._refresh_page(
                parameters
            )



        raise ExecutionError(
            f"Unsupported browser action: {action_type}"
        )



    # =====================================================
    # Browser Operations
    # =====================================================


    async def _open_url(
        self,
        parameters,
    ):


        url = parameters.get(
            "url"
        )


        if not url:

            raise ExecutionError(
                "URL missing"
            )



        if self.browser_tools:

            return await self.browser_tools.open_url(
                url
            )



        return {

            "url": url,

            "status": "opened"

        }



    async def _new_tab(
        self,
        parameters,
    ):


        if self.browser_tools:

            return await self.browser_tools.new_tab()



        return {

            "status": "new_tab_created"

        }



    async def _close_tab(
        self,
        parameters,
    ):


        if self.browser_tools:

            return await self.browser_tools.close_tab()



        return {

            "status": "tab_closed"

        }



    async def _switch_tab(
        self,
        parameters,
    ):


        tab = parameters.get(
            "tab"
        )


        if self.browser_tools:

            return await self.browser_tools.switch_tab(
                tab
            )



        return {

            "tab": tab,

            "status": "switched"

        }



    async def _refresh_page(
        self,
        parameters,
    ):


        if self.browser_tools:

            return await self.browser_tools.refresh_page()



        return {

            "status": "page_refreshed"

        }