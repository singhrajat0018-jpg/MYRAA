"""
MYRAA Memory Manager

Single entry point for every memory operation.
"""

from __future__ import annotations

import logging

from .working_memory import WorkingMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory
from . import persistence

log = logging.getLogger(__name__)


class MemoryManager:

    def __init__(self, store_path: str | None = None, blackboard: object | None = None):

        self.working = WorkingMemory()

        self.episodic = EpisodicMemory()

        self.semantic = SemanticMemory()

        self.blackboard = blackboard

        self._store_path = store_path or persistence.default_memory_file()

        persistence.load_memory_manager(self, self._store_path)

    # ------------------------------------------

    def _persist(self):

        """Atomically persist long-term memory to disk (never raises)."""

        persistence.save_memory_manager(self, self._store_path)

    # ------------------------------------------

    def remember_event(self, event):

        if persistence.is_sensitive_text(event):
            log.warning("[Memory] Rejected sensitive event (never stored).")
            return False

        self.working.add(event)

        self.episodic.record(event)

        self._persist()

        return True

    # ------------------------------------------

    def remember_fact(self, key, value=None):

        if persistence.is_sensitive_text(str(key)) or persistence.is_sensitive_text(value):
            log.warning("[Memory] Rejected sensitive fact (never stored).")
            return False

        self.semantic.store(key, value)

        self._persist()

        return True

    # ------------------------------------------

    def context(self):

        return {

            "working": self.working.snapshot(),

            "episodic": self.episodic.recent(),

            "semantic": self.semantic.summary(),

        }

    # ------------------------------------------

    def clear(self):

        self.working.clear()

        self.episodic.clear()

        self.semantic.clear()

        self._persist()

    def remember_reflection(

        self,

        reflection,

    ):

        if persistence.is_sensitive_text(reflection):
            log.warning("[Memory] Rejected sensitive reflection (never stored).")
            return False

        self.working.add(

            reflection,

            category="reflection",

            importance=0.8,

        )

        self.episodic.record(

            reflection,

        )

        self._persist()

        return True

    def process_reflection(self):

        if self.blackboard is None:

            return

        try:

            reflection = self.blackboard.read(

                "reflection",

                "latest",

            )
        except Exception as exc:  # noqa: BLE001
            log.debug("process_reflection read failed: %s", exc)
            return

        if reflection is None:

            return

        self.working.add(

            reflection,

            category="reflection",

        )

        self.episodic.record(

            reflection,

        )

        self._persist()