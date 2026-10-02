"""
MYRAA Brain

Semantic Memory

Stores long-term knowledge.

Unlike episodic memory, semantic memory stores
facts instead of events.
"""

from __future__ import annotations

import threading
import time

from dataclasses import dataclass, field
from typing import Any, Optional


# ==========================================================
# Knowledge Record
# ==========================================================

@dataclass(slots=True)
class Knowledge:

    key: str

    value: Any

    confidence: float = 1.0

    source: str = "brain"

    created_at: float = field(default_factory=time.time)

    updated_at: float = field(default_factory=time.time)

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Semantic Memory
# ==========================================================

class SemanticMemory:

    """
    Long-term knowledge storage.
    """

    def __init__(self, max_facts: int = 10000):

        self._knowledge: dict[str, Knowledge] = {}
        self._max_facts = max_facts

        self._lock = threading.RLock()

    # ------------------------------------------------------

    def store(

        self,

        key: str,

        value: Any,

        confidence: float = 1.0,

        source: str = "brain",

        metadata: Optional[dict] = None,

    ) -> Knowledge:

        with self._lock:

            if key in self._knowledge:

                item = self._knowledge[key]

                item.value = value

                item.confidence = confidence

                item.updated_at = time.time()

                item.source = source

                if metadata:

                    item.metadata.update(metadata)

                return item

            # If we're at capacity, remove the oldest entry (simple FIFO eviction)
            if len(self._knowledge) >= self._max_facts:
                # Remove the oldest item based on created_at timestamp
                oldest_key = min(self._knowledge.keys(),
                               key=lambda k: self._knowledge[k].created_at)
                del self._knowledge[oldest_key]

            item = Knowledge(

                key=key,

                value=value,

                confidence=confidence,

                source=source,

                metadata=metadata or {},

            )

            self._knowledge[key] = item

            return item

    # ------------------------------------------------------

    def get(

        self,

        key: str,

        default=None,

    ):

        with self._lock:

            item = self._knowledge.get(key)

            if item is None:

                return default

            return item.value

    # ------------------------------------------------------

    def knowledge(

        self,

        key: str,

    ) -> Optional[Knowledge]:

        with self._lock:

            return self._knowledge.get(key)

    # ------------------------------------------------------

    def exists(

        self,

        key: str,

    ) -> bool:

        return key in self._knowledge

    # ------------------------------------------------------

    def remove(

        self,

        key: str,

    ):

        with self._lock:

            self._knowledge.pop(key, None)

    # ------------------------------------------------------

    def search(

        self,

        text: str,

    ) -> list[Knowledge]:

        text = text.lower()

        with self._lock:

            return [

                k

                for k in self._knowledge.values()

                if text in k.key.lower()

                or text in str(k.value).lower()

            ]

    # ------------------------------------------------------

    def summary(self):

        with self._lock:

            return {

                "facts": len(self._knowledge),

                "keys": list(self._knowledge.keys()),

            }

    # ------------------------------------------------------

    def snapshot(self):

        with self._lock:

            return dict(self._knowledge)

    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._knowledge.clear()

    # ------------------------------------------------------

    def __len__(self):

        return len(self._knowledge)

    def __contains__(

        self,

        key,

    ):

        return key in self._knowledge

    def __repr__(self):

        return (

            f"SemanticMemory("

            f"facts={len(self)})"

        )