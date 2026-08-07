"""
MYRAA Cognitive Engine

File Action Adapter

Handles file system operations.

Supported:

- CREATE_FILE
- CREATE_FOLDER
- DELETE_FILE
- MOVE_FILE
- COPY_FILE
- OPEN_FILE
- SAVE_FILE
"""

from __future__ import annotations


from typing import Any, Dict


from .base_adapter import BaseAdapter


from ...models.action_types import ActionType


from ..exceptions import ExecutionError



class FileAdapter(BaseAdapter):
    """
    Adapter for file and folder operations.
    """



    def __init__(
        self,
        file_tools=None,
    ) -> None:


        super().__init__(
            name="file_adapter"
        )


        self.file_tools = (
            file_tools
        )



    # =====================================================
    # Supported Actions
    # =====================================================

    def supports(
        self,
        action_type,
    ) -> bool:


        return action_type in {

            ActionType.CREATE_FILE,

            ActionType.CREATE_FOLDER,

            ActionType.DELETE_FILE,

            ActionType.MOVE_FILE,

            ActionType.COPY_FILE,

            ActionType.OPEN_FILE,

            ActionType.SAVE_FILE,

        }



    # =====================================================
    # Execute
    # =====================================================

    async def _execute(
        self,
        action_type,
        parameters: Dict[str, Any],
    ) -> Any:


        if action_type == ActionType.CREATE_FILE:

            return await self._create_file(
                parameters
            )



        if action_type == ActionType.CREATE_FOLDER:

            return await self._create_folder(
                parameters
            )



        if action_type == ActionType.DELETE_FILE:

            return await self._delete_file(
                parameters
            )



        if action_type == ActionType.MOVE_FILE:

            return await self._move_file(
                parameters
            )



        if action_type == ActionType.COPY_FILE:

            return await self._copy_file(
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



        raise ExecutionError(
            f"Unsupported file action: {action_type}"
        )



    # =====================================================
    # File Operations
    # =====================================================


    async def _create_file(
        self,
        parameters,
    ):


        path = parameters.get(
            "path"
        )


        if not path:

            raise ExecutionError(
                "File path missing"
            )



        if self.file_tools:

            return await self.file_tools.create_file(
                path
            )


        return {

            "path": path,

            "status": "file_created"

        }



    async def _create_folder(
        self,
        parameters,
    ):


        path = parameters.get(
            "path"
        )


        if not path:

            raise ExecutionError(
                "Folder path missing"
            )



        if self.file_tools:

            return await self.file_tools.create_folder(
                path
            )



        return {

            "path": path,

            "status": "folder_created"

        }



    async def _delete_file(
        self,
        parameters,
    ):


        path = parameters.get(
            "path"
        )


        if self.file_tools:

            return await self.file_tools.delete_file(
                path
            )



        return {

            "path": path,

            "status": "deleted"

        }



    async def _move_file(
        self,
        parameters,
    ):


        source = parameters.get(
            "source"
        )

        destination = parameters.get(
            "destination"
        )



        if self.file_tools:

            return await self.file_tools.move_file(
                source,
                destination,
            )



        return {

            "source": source,

            "destination": destination,

            "status": "moved"

        }



    async def _copy_file(
        self,
        parameters,
    ):


        source = parameters.get(
            "source"
        )

        destination = parameters.get(
            "destination"
        )



        if self.file_tools:

            return await self.file_tools.copy_file(
                source,
                destination,
            )



        return {

            "source": source,

            "destination": destination,

            "status": "copied"

        }



    async def _open_file(
        self,
        parameters,
    ):


        path = parameters.get(
            "path"
        )


        if self.file_tools:

            return await self.file_tools.open_file(
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


        path = parameters.get(
            "path"
        )


        if self.file_tools:

            return await self.file_tools.save_file(
                path
            )



        return {

            "path": path,

            "status": "saved"

        }