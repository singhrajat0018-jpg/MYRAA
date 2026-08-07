"""
MYRAA Hypothesis Engine

Generates and ranks possible explanations
before planning or execution.

Responsibilities
----------------
• Generate multiple hypotheses
• Rank by confidence
• Update confidence from evidence
• Return best hypothesis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ==========================================================
# Hypothesis Type
# ==========================================================

class HypothesisType(Enum):

    USER_INTENT = auto()

    SYSTEM_STATE = auto()

    APPLICATION = auto()

    ERROR = auto()

    KNOWLEDGE = auto()

    UNKNOWN = auto()


# ==========================================================
# Hypothesis
# ==========================================================

@dataclass(slots=True)
class Hypothesis:

    title: str

    hypothesis_type: HypothesisType

    confidence: float = 0.5

    evidence: list[str] = field(default_factory=list)

    missing_information: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Hypothesis Engine
# ==========================================================

class HypothesisEngine:

    """
    Creates and evaluates hypotheses.
    """

    def __init__(self):

        self._history: list[Hypothesis] = []

    # ------------------------------------------------------

    def generate(

        self,

        observation: str,

    ) -> list[Hypothesis]:

        text = observation.lower()

        hypotheses: list[Hypothesis] = []

        # ------------------------------------------
        # Laptop Slow
        # ------------------------------------------

        if "slow" in text:

            hypotheses.extend([

                Hypothesis(

                    title="High CPU usage",

                    hypothesis_type=HypothesisType.SYSTEM_STATE,

                    confidence=0.70,

                ),

                Hypothesis(

                    title="High memory usage",

                    hypothesis_type=HypothesisType.SYSTEM_STATE,

                    confidence=0.65,

                ),

                Hypothesis(

                    title="Background Windows Update",

                    hypothesis_type=HypothesisType.SYSTEM_STATE,

                    confidence=0.45,

                ),

                Hypothesis(

                    title="Disk nearly full",

                    hypothesis_type=HypothesisType.SYSTEM_STATE,

                    confidence=0.40,

                ),

            ])

        # ------------------------------------------
        # Open Project
        # ------------------------------------------

        elif "project" in text:

            hypotheses.extend([

                Hypothesis(

                    title="Open MYRAA project",

                    hypothesis_type=HypothesisType.USER_INTENT,

                    confidence=0.45,

                ),

                Hypothesis(

                    title="Open Attendance App",

                    hypothesis_type=HypothesisType.USER_INTENT,

                    confidence=0.40,

                ),

                Hypothesis(

                    title="Open Recent Project",

                    hypothesis_type=HypothesisType.USER_INTENT,

                    confidence=0.35,

                ),

            ])

        # ------------------------------------------
        # Default
        # ------------------------------------------

        if not hypotheses:

            hypotheses.append(

                Hypothesis(

                    title="Unknown",

                    hypothesis_type=HypothesisType.UNKNOWN,

                    confidence=0.20,

                )

            )

        hypotheses.sort(

            key=lambda h: h.confidence,

            reverse=True,

        )

        self._history.extend(hypotheses)

        return hypotheses

    # ------------------------------------------------------

    def update(

        self,

        hypothesis: Hypothesis,

        *,

        evidence: str,

        delta: float,

    ) -> Hypothesis:

        hypothesis.evidence.append(

            evidence,

        )

        hypothesis.confidence += delta

        hypothesis.confidence = max(

            0.0,

            min(

                hypothesis.confidence,

                1.0,

            ),

        )

        return hypothesis

    # ------------------------------------------------------

    def best(

        self,

        hypotheses: list[Hypothesis],

    ) -> Hypothesis | None:

        if not hypotheses:

            return None

        return max(

            hypotheses,

            key=lambda h: h.confidence,

        )

    # ------------------------------------------------------

    def history(self) -> list[Hypothesis]:

        return list(self._history)

    # ------------------------------------------------------

    def clear(self):

        self._history.clear()