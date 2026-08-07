"""
MYRAA Reasoning Trace

Stores structured reasoning traces for
debugging, reflection and learning.

This module does NOT store hidden chain-of-thought.
It stores only observable decision summaries,
evidence, assumptions and outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from uuid import uuid4


# ==========================================================
# Stage
# ==========================================================

class TraceStage(Enum):

    OBSERVATION = auto()

    INTERPRETATION = auto()

    HYPOTHESIS = auto()

    KNOWLEDGE = auto()

    DECISION = auto()

    PLANNING = auto()

    EXECUTION = auto()

    VERIFICATION = auto()

    REFLECTION = auto()


# ==========================================================
# Trace Entry
# ==========================================================

@dataclass(slots=True)
class TraceEntry:

    id: str = field(
        default_factory=lambda: str(uuid4())
    )

    stage: TraceStage = TraceStage.OBSERVATION

    timestamp: datetime = field(
        default_factory=datetime.utcnow
    )

    summary: str = ""

    confidence: float = 1.0

    evidence: list[str] = field(
        default_factory=list
    )

    assumptions: list[str] = field(
        default_factory=list
    )

    next_action: str = ""

    metadata: dict = field(
        default_factory=dict
    )


# ==========================================================
# Reasoning Trace
# ==========================================================

class ReasoningTrace:

    """
    Stores structured reasoning history.
    """

    def __init__(

        self,

        max_entries: int = 500,

    ):

        self.max_entries = max_entries

        self._entries: list[TraceEntry] = []

    # ------------------------------------------------------

    def add(

        self,

        stage: TraceStage,

        summary: str,

        confidence: float = 1.0,

        evidence: list[str] | None = None,

        assumptions: list[str] | None = None,

        next_action: str = "",

        metadata: dict | None = None,

    ) -> TraceEntry:

        entry = TraceEntry(

            stage=stage,

            summary=summary,

            confidence=confidence,

            evidence=evidence or [],

            assumptions=assumptions or [],

            next_action=next_action,

            metadata=metadata or {},

        )

        self._entries.append(entry)

        if len(self._entries) > self.max_entries:

            self._entries.pop(0)

        return entry

    # ------------------------------------------------------

    def latest(self) -> TraceEntry | None:

        if not self._entries:

            return None

        return self._entries[-1]

    # ------------------------------------------------------

    def history(self) -> list[TraceEntry]:

        return list(self._entries)

    # ------------------------------------------------------

    def clear(self):

        self._entries.clear()

    # ------------------------------------------------------

    def count(self) -> int:

        return len(self._entries)

    # ------------------------------------------------------

    def by_stage(

        self,

        stage: TraceStage,

    ) -> list[TraceEntry]:

        return [

            entry

            for entry in self._entries

            if entry.stage == stage

        ]

    # ------------------------------------------------------

    def export(self) -> list[dict]:

        output = []

        for entry in self._entries:

            output.append(

                {

                    "id": entry.id,

                    "stage": entry.stage.name,

                    "timestamp": entry.timestamp.isoformat(),

                    "summary": entry.summary,

                    "confidence": entry.confidence,

                    "evidence": entry.evidence,

                    "assumptions": entry.assumptions,

                    "next_action": entry.next_action,

                    "metadata": entry.metadata,

                }

            )

        return output