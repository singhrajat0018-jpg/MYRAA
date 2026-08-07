"""
MYRAA Knowledge Event Queue
"""

from __future__ import annotations

from queue import Queue


class KnowledgeEventQueue:

    def __init__(self):
        self._queue = Queue()

    # ------------------------------------------

    def put(self, event_type: str, path: str):

        self._queue.put(
            (
                event_type,
                path,
            )
        )

    # ------------------------------------------

    def get(self):

        return self._queue.get()

    # ------------------------------------------

    def task_done(self):

        self._queue.task_done()

    # ------------------------------------------

    def empty(self):

        return self._queue.empty()