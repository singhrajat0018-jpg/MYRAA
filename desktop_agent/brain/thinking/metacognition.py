"""
MYRAA Metacognition Engine

Evaluates completed cognitive cycles and
generates improvement suggestions.

This module does NOT inspect hidden reasoning.
It evaluates observable inputs, decisions,
outcomes and confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from typing import Any

from .thinking_engine import ThinkingResult


# ==========================================================
# Evaluation
# ==========================================================

class Evaluation(Enum):

    EXCELLENT = auto()

    GOOD = auto()

    ACCEPTABLE = auto()

    POOR = auto()

    FAILED = auto()


# ==========================================================
# Result
# ==========================================================

@dataclass(slots=True)
class MetacognitionResult:

    timestamp: datetime

    evaluation: Evaluation

    score: float

    strengths: list[str] = field(default_factory=list)

    weaknesses: list[str] = field(default_factory=list)

    improvements: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Engine
# ==========================================================

class Metacognition:

    """
    Self evaluation engine.
    """

    def __init__(self):

        self.history: list[MetacognitionResult] = []

    # ------------------------------------------------------

    def evaluate(

        self,

        thinking: ThinkingResult,

        execution_success: bool,

    ) -> MetacognitionResult:

        score = thinking.confidence.overall

        strengths = []

        weaknesses = []

        improvements = []

        # --------------------------
        # Confidence
        # --------------------------

        if score >= 0.90:

            strengths.append(

                "High confidence decision."

            )

        elif score < 0.50:

            weaknesses.append(

                "Low confidence."

            )

            improvements.append(

                "Collect additional evidence."

            )

        # --------------------------
        # Uncertainty
        # --------------------------

        if thinking.uncertainty.requires_clarification:

            strengths.append(

                "Ambiguity detected."

            )

        # --------------------------
        # Execution
        # --------------------------

        if execution_success:

            strengths.append(

                "Execution succeeded."

            )

        else:

            weaknesses.append(

                "Execution failed."

            )

            improvements.append(

                "Review execution strategy."

            )

        # --------------------------
        # Overall
        # --------------------------

        if execution_success and score > 0.90:

            evaluation = Evaluation.EXCELLENT

        elif execution_success:

            evaluation = Evaluation.GOOD

        elif score > 0.60:

            evaluation = Evaluation.ACCEPTABLE

        elif score > 0.30:

            evaluation = Evaluation.POOR

        else:

            evaluation = Evaluation.FAILED

        result = MetacognitionResult(

            timestamp=datetime.utcnow(),

            evaluation=evaluation,

            score=score,

            strengths=strengths,

            weaknesses=weaknesses,

            improvements=improvements,

        )

        self.history.append(result)

        return result

    # ------------------------------------------------------

    def latest(self):

        if not self.history:

            return None

        return self.history[-1]

    # ------------------------------------------------------

    def all(self):

        return list(self.history)

    # ------------------------------------------------------

    def clear(self):

        self.history.clear()