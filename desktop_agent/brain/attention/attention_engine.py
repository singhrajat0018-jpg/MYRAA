from __future__ import annotations

from .attention_queue import AttentionQueue
from .attention_item import AttentionItem
from .attention_policy import AttentionPolicy


class AttentionEngine:

    """
    Filters incoming events before
    they reach reasoning.
    """

    def __init__(self):

        self.queue = AttentionQueue()

    def submit(
        self,
        decision,
        event,
    ):

        if decision.priority < AttentionPolicy.MIN_PRIORITY:
            return

        item = AttentionItem(
            source=getattr(event, "source", ""),
            title=getattr(event, "title", ""),
            priority=decision.priority,
            payload=event,
        )

        self.queue.push(item)

    def next(self):

        return self.queue.pop()