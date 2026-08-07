"""
MYRAA File Tool Bridge

Connects FileAdapter
with tools_files.py
"""

from __future__ import annotations

from desktop_agent import tools_files


class FileToolBridge:


    async def create_file(
        self,
        path,
    ):

        return tools_files.create_file(
            {
                "path": path
            }
        )


    async def create_folder(
        self,
        path,
    ):

        # folder creation through pathlib
        from pathlib import Path

        folder = Path(path)

        folder.mkdir(
            parents=True,
            exist_ok=True
        )

        return {
            "result": f"Created folder: {folder}",
            "path": str(folder)
        }



    async def delete_file(
        self,
        path,
    ):

        return tools_files.delete_file(
            {
                "path": path
            }
        )



    async def move_file(
        self,
        source,
        destination,
    ):

        return tools_files.move_file(
            {
                "path": source,
                "destination": destination,
            }
        )



    async def copy_file(
        self,
        source,
        destination,
    ):

        return tools_files.copy_file(
            {
                "path": source,
                "destination": destination,
            }
        )



    async def open_file(
        self,
        path,
    ):

        return tools_files.open_file(
            {
                "path": path
            }
        )



    async def save_file(
        self,
        path,
        content="",
        append=False,
    ):

        return tools_files.write_file(
            {
                "path": path,
                "content": content,
                "append": append,
            }
        )

    async def read_file(
        self,
        path,
    ):

        return tools_files.read_file(
            {
                "path": path
            }
        )

    async def rename_file(
        self,
        path,
        new_name,
    ):

        return tools_files.rename_file(
            {
                "path": path,
                "new_name": new_name,
            }
        )

    async def list_files(
        self,
        path,
        pattern="*",
    ):

        return tools_files.list_files(
            {
                "path": path,
                "pattern": pattern,
            }
        )

    async def search_files(
        self,
        folder,
        pattern,
    ):

        return tools_files.search_files(
            {
                "folder": folder,
                "pattern": pattern,
            }
        )

    async def open_folder(
        self,
        path,
    ):

        return tools_files.open_folder(
            {
                "path": path
            }
        )