"""
MYRAA Cognitive Engine

Keyboard Action Adapter

Handles keyboard operations.

Supported:

- TYPE_TEXT
- PRESS_KEY
- HOTKEY
- KEY_DOWN
- KEY_UP
- COPY
- CUT
- PASTE
- UNDO
- REDO
- SELECT_ALL
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError

from desktop_agent.tools_keyboard import (
    type_text,
    press_key,
    hotkey,
)



class KeyboardAdapter(BaseAdapter):
    """
    Adapter for keyboard control.
    """



    def __init__(
        self,
        keyboard_tools=None,
    ) -> None:


        super().__init__(
            name="keyboard_adapter"
        )


        self.keyboard_tools = (
            keyboard_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {


            ActionType.TYPE_TEXT,

            ActionType.PRESS_KEY,

            ActionType.HOTKEY,

            ActionType.KEY_DOWN,

            ActionType.KEY_UP,

            ActionType.COPY,

            ActionType.CUT,

            ActionType.PASTE,

            ActionType.UNDO,

            ActionType.REDO,

            ActionType.SELECT_ALL,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:


        if action_type == ActionType.TYPE_TEXT:

            return await self._type_text(
                parameters
            )



        if action_type == ActionType.PRESS_KEY:

            return await self._press_key(
                parameters
            )



        if action_type == ActionType.HOTKEY:

            return await self._hotkey(
                parameters
            )



        if action_type == ActionType.KEY_DOWN:

            return await self._key_down(
                parameters
            )



        if action_type == ActionType.KEY_UP:

            return await self._key_up(
                parameters
            )



        if action_type == ActionType.COPY:

            return await self._copy(
                parameters
            )



        if action_type == ActionType.CUT:

            return await self._cut(
                parameters
            )



        if action_type == ActionType.PASTE:

            return await self._paste(
                parameters
            )



        if action_type == ActionType.UNDO:

            return await self._undo(
                parameters
            )



        if action_type == ActionType.REDO:

            return await self._redo(
                parameters
            )



        if action_type == ActionType.SELECT_ALL:

            return await self._select_all(
                parameters
            )



        raise ExecutionError(
            f"Unsupported keyboard action: {action_type}"
        )



    # =====================================================
    # Keyboard Operations
    # =====================================================


    async def _type_text(
        self,
        parameters,
    ):


        text = parameters.get(
            "text"
        )


        if text is None:

            raise ExecutionError(
                "Text missing"
            )



        return type_text(
            {
                "text": text
            }
        )


    async def _press_key(
        self,
        parameters,
    ):


        key = parameters.get(
            "key"
        )


        if self.keyboard_tools:

            return await self.keyboard_tools.press_key(
                key
            )



        return press_key(
            {
                "key": key
            }
        )



    async def _hotkey(
        self,
        parameters,
    ):


        keys = parameters.get(
            "keys"
        )



        if self.keyboard_tools:

            return await self.keyboard_tools.hotkey(
                keys
            )



        return hotkey(
            {
                "keys": keys
            }
        )


    async def _key_down(
        self,
        parameters,
    ):


        key = parameters.get(
            "key"
        )


        if self.keyboard_tools:

            return await self.keyboard_tools.key_down(
                key
            )


        return {

            "key": key,

            "status": "key_down"

        }



    async def _key_up(
        self,
        parameters,
    ):


        key = parameters.get(
            "key"
        )


        if self.keyboard_tools:

            return await self.keyboard_tools.key_up(
                key
            )


        return {

            "key": key,

            "status": "key_up"

        }



    async def _copy(
        self,
        parameters,
    ):


        if self.keyboard_tools:

            return await self.keyboard_tools.copy()



        return {

            "status": "copied"

        }



    async def _cut(
        self,
        parameters,
    ):


        if self.keyboard_tools:

            return await self.keyboard_tools.cut()



        return {

            "status": "cut"

        }



    async def _paste(
        self,
        parameters,
    ):


        if self.keyboard_tools:

            return await self.keyboard_tools.paste()



        return {

            "status": "pasted"

        }



    async def _undo(
        self,
        parameters,
    ):


        if self.keyboard_tools:

            return await self.keyboard_tools.undo()



        return {

            "status": "undo"

        }



    async def _redo(
        self,
        parameters,
    ):


        if self.keyboard_tools:

            return await self.keyboard_tools.redo()



        return {

            "status": "redo"

        }



    async def _select_all(
        self,
        parameters,
    ):


        if self.keyboard_tools:

            return await self.keyboard_tools.select_all()



        return {

            "status": "selected_all"

        }