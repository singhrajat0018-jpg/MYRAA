"""
MYRAA Knowledge Engine
File Watcher
"""

from __future__ import annotations

from pathlib import Path

from watchdog.observers import Observer

from .event_handler import KnowledgeEventHandler


class FileWatcher:

    def __init__(self, index_manager):

        self.index_manager = index_manager

        self.observer = Observer()

    # -----------------------------------------------------

    def start(
        self,
        root: str | Path,
    ):

        root = Path(root)

        handler = KnowledgeEventHandler(self.index_manager)

        self.observer.schedule(
            handler,
            str(root),
            recursive=True,
        )

        self.observer.start()

        print(f"[Watcher] Watching: {root}")

    # -----------------------------------------------------

    def stop(self):

        self.observer.stop()

        self.observer.join()

        print("[Watcher] Stopped")