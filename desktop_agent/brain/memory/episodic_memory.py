"""
MYRAA Brain

Episodic Memory

Stores meaningful events as a timeline.

Responsibilities
----------------
- Record important events
- Maintain chronological history
- Query recent events
- Search by category
- Export timeline
"""

from __future__ import annotations

import threading
import time

from dataclasses import dataclass, field
from typing import Any, Optional


# ==========================================================
# Episode
# ==========================================================

@dataclass(slots=True)
class Episode:

    id: int

    timestamp: float

    category: str

    title: str

    description: str = ""

    importance: float = 0.5

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Episodic Memory
# ==========================================================

class EpisodicMemory:

    """
    Long-term chronological memory.
    """

    def __init__(

        self,

        max_events: int = 5000,

    ):

        self.max_events = max_events

        self._events: list[Episode] = []

        self._next_id = 1

        self._lock = threading.RLock()

    # ------------------------------------------------------

    def record(

        self,

        title: str,

        category: str = "general",

        description: str = "",

        importance: float = 0.5,

        metadata: Optional[dict] = None,

    ) -> Episode:

        with self._lock:

            episode = Episode(

                id=self._next_id,

                timestamp=time.time(),

                title=title,

                category=category,

                description=description,

                importance=importance,

                metadata=metadata or {},

            )

            self._next_id += 1

            self._events.append(episode)

            self._trim()

            return episode

    # ------------------------------------------------------

    def recent(

        self,

        limit: int = 20,

    ) -> list[Episode]:

        with self._lock:

            return self._events[-limit:]

    # ------------------------------------------------------

    def by_category(

        self,

        category: str,

    ) -> list[Episode]:

        with self._lock:

            return [

                e

                for e in self._events

                if e.category == category

            ]

    # ------------------------------------------------------

    def important(

        self,

        threshold: float = 0.8,

    ) -> list[Episode]:

        with self._lock:

            return [

                e

                for e in self._events

                if e.importance >= threshold

            ]

    # ------------------------------------------------------

    def search(

        self,

        keyword: str,

    ) -> list[Episode]:

        keyword = keyword.lower()

        with self._lock:

            return [

                e

                for e in self._events

                if keyword in e.title.lower()

                or keyword in e.description.lower()

            ]

    # ------------------------------------------------------

    def latest(self) -> Optional[Episode]:

        with self._lock:

            if not self._events:

                return None

            return self._events[-1]

    # ------------------------------------------------------

    def timeline(self) -> list[Episode]:

        with self._lock:

            return list(self._events)

    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._events.clear()

            self._next_id = 1

    # ------------------------------------------------------

    def _trim(self):

        if len(self._events) > self.max_events:

            excess = len(self._events) - self.max_events

            del self._events[:excess]

    # ------------------------------------------------------

    @property
    def size(self):

        return len(self._events)

    @property
    def empty(self):

        return self.size == 0

    # ------------------------------------------------------

    def summary(self):

        with self._lock:

            return {

                "episodes": self.size,

                "latest": self.latest(),

                "capacity": self.max_events,

            }

    # ------------------------------------------------------

    def __len__(self):

        return self.size

    def __bool__(self):

        return not self.empty

    def __repr__(self):

        return (

            f"EpisodicMemory("

            f"episodes={self.size})"

        )