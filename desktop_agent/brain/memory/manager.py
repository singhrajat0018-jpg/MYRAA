"""
MYRAA Memory Manager

Single entry point for every memory operation.
"""

from __future__ import annotations

from .working_memory import WorkingMemory
from .episodic_memory import EpisodicMemory
from .semantic_memory import SemanticMemory


class MemoryManager:

    def __init__(self):

        self.working = WorkingMemory()

        self.episodic = EpisodicMemory()

        self.semantic = SemanticMemory()

    # ------------------------------------------

    def remember_event(self, event):

        self.working.add(event)

        self.episodic.record(event)

    # ------------------------------------------

    def remember_fact(self, fact):

        self.semantic.store(fact)

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

    def remember_reflection(

        self,

        reflection,

    ):

        self.working.add(

            reflection,

            category="reflection",

            importance=0.8,

        )

        self.episodic.record(

            reflection,

        )

    def process_reflection(self):

        reflection = self.blackboard.read(

            "reflection",

            "latest",

        )

        if reflection is None:

            return

        self.working.add(

            reflection,

            category="reflection",

        )