"""
MYRAA Brain

Working Memory

Responsibilities
----------------
- Stores the user's recent cognitive context.
- Keeps recent actions, observations and goals.
- Fast in-memory retrieval.
- Automatically expires old items.

Working Memory represents MYRAA's short-term memory.
"""

from __future__ import annotations

import threading
import time

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


# ==========================================================
# Memory Entry
# ==========================================================

@dataclass(slots=True)
class MemoryEntry:

    timestamp: float

    category: str

    value: Any

    importance: float = 0.5

    metadata: dict = field(default_factory=dict)


# ==========================================================
# Working Memory
# ==========================================================

class WorkingMemory:

    """
    Short-term cognitive memory.

    Stores recent events and observations.
    """

    def __init__(

        self,

        capacity: int = 100,

        ttl_seconds: int = 600,

    ):

        self.capacity = capacity

        self.ttl = ttl_seconds

        self._lock = threading.RLock()

        self._entries = deque(maxlen=capacity)

    # ------------------------------------------------------

    def add(

        self,

        value: Any,

        category: str = "event",

        importance: float = 0.5,

        metadata: Optional[dict] = None,

    ):

        entry = MemoryEntry(

            timestamp=time.time(),

            category=category,

            value=value,

            importance=importance,

            metadata=metadata or {},

        )

        with self._lock:

            self._entries.append(entry)

            self._expire()

    # ------------------------------------------------------

    def snapshot(self) -> list[MemoryEntry]:

        with self._lock:

            self._expire()

            return list(self._entries)

    # ------------------------------------------------------

    def recent(

        self,

        limit: int = 10,

    ) -> list[MemoryEntry]:

        with self._lock:

            self._expire()

            return list(self._entries)[-limit:]

    # ------------------------------------------------------

    def latest(

        self,

        category: Optional[str] = None,

    ) -> Optional[MemoryEntry]:

        with self._lock:

            self._expire()

            for item in reversed(self._entries):

                if category is None:

                    return item

                if item.category == category:

                    return item

        return None

    # ------------------------------------------------------

    def search(

        self,

        category: str,

    ) -> list[MemoryEntry]:

        with self._lock:

            self._expire()

            return [

                e

                for e in self._entries

                if e.category == category

            ]

    # ------------------------------------------------------

    def remove(

        self,

        entry: MemoryEntry,

    ):

        with self._lock:

            try:

                self._entries.remove(entry)

            except ValueError:

                pass

    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._entries.clear()

    # ------------------------------------------------------

    def _expire(self):

        now = time.time()

        while self._entries:

            oldest = self._entries[0]

            if now - oldest.timestamp <= self.ttl:

                break

            self._entries.popleft()

    # ------------------------------------------------------

    @property
    def size(self):

        return len(self._entries)

    @property
    def empty(self):

        return self.size == 0

    # ------------------------------------------------------

    def summary(self):

        with self._lock:

            self._expire()

            return {

                "entries": len(self._entries),

                "capacity": self.capacity,

                "ttl_seconds": self.ttl,

                "latest": self.latest(),

            }

    # ------------------------------------------------------

    def __len__(self):

        return self.size

    def __bool__(self):

        return not self.empty

    def __repr__(self):

        return (

            f"WorkingMemory("

            f"entries={self.size}, "

            f"ttl={self.ttl}s)"

        )
