"""
MYRAA Cognitive Engine

System Action Adapter

Handles operating system actions.

Supported:

- SYSTEM_CONTROL
- SHUTDOWN
- RESTART
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



class SystemAdapter(BaseAdapter):
    """
    Adapter for system level operations.
    """



    def __init__(
        self,
        system_tools=None,
    ) -> None:


        super().__init__(
            name="system_adapter"
        )


        self.system_tools = (
            system_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {


            ActionType.OPEN_FILE,

            ActionType.SAVE_FILE,

            ActionType.CLOSE_FILE,

            ActionType.SYSTEM_CONTROL,

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


        if action_type == ActionType.SYSTEM_CONTROL:

            return await self._system_control(
                parameters
            )


        if action_type == ActionType.OPEN_FILE:

            return await self._open_file(
                parameters
            )


        if action_type == ActionType.SAVE_FILE:

            return await self._save_file(
                parameters
            )


        if action_type == ActionType.CLOSE_FILE:

            return await self._close_file(
                parameters
            )


        if action_type == ActionType.COPY:

            return await self._copy()


        if action_type == ActionType.CUT:

            return await self._cut()


        if action_type == ActionType.PASTE:

            return await self._paste()


        if action_type == ActionType.UNDO:

            return await self._undo()


        if action_type == ActionType.REDO:

            return await self._redo()


        if action_type == ActionType.SELECT_ALL:

            return await self._select_all()



        raise ExecutionError(
            f"Unsupported system action: {action_type}"
        )



    # =====================================================
    # System Operations
    # =====================================================


    async def _system_control(
        self,
        parameters,
    ):


        command = parameters.get(
            "command"
        )


        if not command:

            raise ExecutionError(
                "System command missing"
            )



        if self.system_tools:

            return await self.system_tools.system_control(
                command
            )



        return {

            "command": command,

            "status": "executed"

        }



    async def _open_file(
        self,
        parameters,
    ):


        path = parameters.get(
            "path"
        )


        if self.system_tools:

            return await self.system_tools.open_file(
                path
            )


        return {

            "path": path,

            "status": "opened"

        }



    async def _save_file(
        self,
        parameters,
    ):


        if self.system_tools:

            return await self.system_tools.save_file()



        return {

            "status": "saved"

        }



    async def _close_file(
        self,
        parameters,
    ):


        if self.system_tools:

            return await self.system_tools.close_file()



        return {

            "status": "closed"

        }



    async def _copy(
        self,
    ):


        if self.system_tools:

            return await self.system_tools.copy()



        return {

            "status": "copied"

        }



    async def _cut(
        self,
    ):


        if self.system_tools:

            return await self.system_tools.cut()



        return {

            "status": "cut"

        }



    async def _paste(
        self,
    ):


        if self.system_tools:

            return await self.system_tools.paste()



        return {

            "status": "pasted"

        }



    async def _undo(
        self,
    ):


        if self.system_tools:

            return await self.system_tools.undo()



        return {

            "status": "undo"

        }



    async def _redo(
        self,
    ):


        if self.system_tools:

            return await self.system_tools.redo()



        return {

            "status": "redo"

        }



    async def _select_all(
        self,
    ):


        if self.system_tools:

            return await self.system_tools.select_all()



        return {

            "status": "selected_all"

        }