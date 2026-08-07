"""
MYRAA Knowledge Engine
File System Event Handler
"""

from __future__ import annotations

from pathlib import Path

from watchdog.events import FileSystemEventHandler


class KnowledgeEventHandler(FileSystemEventHandler):

    def __init__(self, index_manager):
        self.index_manager = index_manager

    # ---------------------------------------------------------

    def _should_ignore(self, path: Path) -> bool:
        """
        Ignore files and folders that should never be indexed.
        """

        if path.is_dir():
            return True

        ignored_extensions = {
            ".db",
            ".db-journal",
            ".db-wal",
            ".db-shm",
        }

        if path.suffix.lower() in ignored_extensions:
            return True

        ignored_folders = {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".idea",
            ".vscode",
            "data",
        }

        if any(part in ignored_folders for part in path.parts):
            return True

        return False

    # ---------------------------------------------------------

    def on_created(self, event):

        if event.is_directory:
            return

        path = Path(event.src_path)

        if self._should_ignore(path):
            return

        print(f"[Watcher] Created : {path}")

        self.index_manager.queue.put(
            "created",
            str(path),
        )

    # ---------------------------------------------------------

    def on_modified(self, event):

        if event.is_directory:
            return

        path = Path(event.src_path)

        if self._should_ignore(path):
            return

        self.index_manager.queue.put(
            "modified",
            str(path),
        )

    # ---------------------------------------------------------

    def on_deleted(self, event):

        if event.is_directory:
            return

        path = Path(event.src_path)

        if self._should_ignore(path):
            return

        print(f"[Watcher] Deleted : {path}")

        self.index_manager.queue.put(
            "deleted",
            str(path),
        )

    # ---------------------------------------------------------

    def on_moved(self, event):

        if event.is_directory:
            return

        src = Path(event.src_path)
        dst = Path(event.dest_path)

        if self._should_ignore(src) or self._should_ignore(dst):
            return

        print(f"[Watcher] Renamed : {src.name} -> {dst.name}")

        self.index_manager.queue.put(
            "moved",
            str(dst),
        )