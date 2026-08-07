"""
MYRAA Confidence Engine

Calculates confidence scores for cognitive decisions.

Responsibilities
----------------
• Aggregate confidence from multiple sources
• Apply weighted scoring
• Determine execution readiness
• Recommend clarification when confidence is low
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ==========================================================
# Confidence Source
# ==========================================================

class ConfidenceSource(Enum):

    INTENT = auto()

    OCR = auto()

    VISION = auto()

    KNOWLEDGE = auto()

    MEMORY = auto()

    REASONING = auto()

    PLANNER = auto()

    EXECUTION = auto()


# ==========================================================
# Confidence Item
# ==========================================================

@dataclass(slots=True)
class ConfidenceItem:

    source: ConfidenceSource

    score: float

    weight: float = 1.0

    explanation: str = ""


# ==========================================================
# Confidence Result
# ==========================================================

@dataclass(slots=True)
class ConfidenceResult:

    overall: float

    ready_to_execute: bool

    needs_clarification: bool

    recommendation: str

    breakdown: list[ConfidenceItem] = field(
        default_factory=list,
    )


# ==========================================================
# Confidence Engine
# ==========================================================

class ConfidenceEngine:

    """
    Computes overall decision confidence.
    """

    def __init__(

        self,

        execute_threshold: float = 0.80,

        clarification_threshold: float = 0.50,

    ) -> None:

        self.execute_threshold = execute_threshold

        self.clarification_threshold = clarification_threshold

    # ------------------------------------------------------

    def evaluate(

        self,

        items: list[ConfidenceItem],

    ) -> ConfidenceResult:

        if not items:

            return ConfidenceResult(

                overall=0.0,

                ready_to_execute=False,

                needs_clarification=True,

                recommendation="No confidence data available.",

            )

        total_weight = sum(

            item.weight

            for item in items

        )

        if total_weight == 0:

            total_weight = 1.0

        score = sum(

            item.score * item.weight

            for item in items

        ) / total_weight

        score = max(

            0.0,

            min(

                score,

                1.0,

            ),

        )

        if score >= self.execute_threshold:

            recommendation = "Execute."

            execute = True

            clarify = False

        elif score < self.clarification_threshold:

            recommendation = "Ask for clarification."

            execute = False

            clarify = True

        else:

            recommendation = "Collect more evidence."

            execute = False

            clarify = False

        return ConfidenceResult(

            overall=score,

            ready_to_execute=execute,

            needs_clarification=clarify,

            recommendation=recommendation,

            breakdown=items,

        )

    # ------------------------------------------------------

    def single(

        self,

        source: ConfidenceSource,

        score: float,

        explanation: str = "",

    ) -> ConfidenceItem:

        return ConfidenceItem(

            source=source,

            score=max(0.0, min(score, 1.0)),

            explanation=explanation,

        )