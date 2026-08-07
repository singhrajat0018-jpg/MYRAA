"""
MYRAA Knowledge Engine
Drive Scanner

Discovers files and folders.
Does NOT index or store anything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator


class DriveScanner:

    DEFAULT_SKIP = {
        "$Recycle.Bin",
        "System Volume Information",
        "Windows",
        "Program Files",
        "Program Files (x86)",
        "AppData",
        "ProgramData",
        ".git",
        "__pycache__",
        "node_modules",
        "node_modules - Copy",  
        ".pytest_cache",         
        ".venv",
        "venv",
        "dist",                 
        "build",                
        ".idea",               
        ".vscode",                
    }

    def __init__(self, skip: set[str] | None = None):

        self.skip = self.DEFAULT_SKIP.copy()

        if skip:
            self.skip.update(skip)

    # ---------------------------------------------------------

    def scan(self, root: str | Path) -> Iterator[Path]:

        root = Path(root)

        if not root.exists():
            return

        # Yield the workspace root first
        yield root

        yield from self._walk(root)

    # ---------------------------------------------------------

    def _walk(
        self,
        folder: Path,
    ) -> Iterator[Path]:

        try:

            for item in folder.iterdir():

                if item.name in self.skip:
                    continue

                yield item

                if item.is_dir():

                    yield from self._walk(item)

        except (
            PermissionError,
            FileNotFoundError,
            OSError,
        ):
            return