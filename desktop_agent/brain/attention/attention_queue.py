from __future__ import annotations

from collections import deque

from .attention_item import AttentionItem


class AttentionQueue:

    def __init__(
        self,
        max_items: int = 100,
    ):

        self._queue = deque(maxlen=max_items)

    def push(
        self,
        item: AttentionItem,
    ):

        self._queue.append(item)

    def pop(self):

        if not self._queue:
            return None

        highest = max(
            self._queue,
            key=lambda x: x.priority,
        )

        self._queue.remove(highest)

        return highest

    def empty(self):

        return len(self._queue) == 0

    def size(self):

        return len(self._queue)

    def clear(self):

        self._queue.clear()