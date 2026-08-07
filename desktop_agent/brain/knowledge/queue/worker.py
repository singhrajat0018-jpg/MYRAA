"""
MYRAA Knowledge Queue Worker
"""

from __future__ import annotations

import threading
from pathlib import Path


class KnowledgeWorker(threading.Thread):

    def __init__(self, queue, index_manager):

        super().__init__(daemon=True)

        self.queue = queue
        self.index_manager = index_manager

        self.running = True

    # ----------------------------------------------------

    def run(self):

        print("[Knowledge Worker] Started")

        while self.running:

            event_type, path = self.queue.get()

            try:

                path = Path(path)

                if event_type in (
                    "created",
                    "modified",
                    "moved",
                ):
                    self.index_manager.metadata.index(path)

                elif event_type == "deleted":
                    # We'll implement delete synchronization later
                    pass

            except Exception as e:

                print(f"[Knowledge Worker] {e}")

            finally:

                self.queue.task_done()

    # ----------------------------------------------------

    def stop(self):

        self.running = False