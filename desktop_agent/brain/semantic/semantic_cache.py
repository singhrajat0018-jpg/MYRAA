from __future__ import annotations

from collections import OrderedDict


class SemanticCache:

    """
    Small LRU cache for semantic parsing.
    """

    def __init__(self, size: int = 128):

        self.size = size

        self.cache = OrderedDict()

    # -----------------------------------------

    def get(self, text: str):

        key = text.strip().lower()

        if key not in self.cache:
            return None

        value = self.cache.pop(key)

        self.cache[key] = value

        return value

    # -----------------------------------------

    def put(self, text: str, task):

        key = text.strip().lower()

        if key in self.cache:
            self.cache.pop(key)

        self.cache[key] = task

        while len(self.cache) > self.size:
            self.cache.popitem(last=False)