"""
MYRAA Thinking Engine

Central cognitive thinking coordinator.

Pipeline

Observation
    ↓
Reasoning Trace
    ↓
Hypothesis
    ↓
Confidence
    ↓
Uncertainty
    ↓
Decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from desktop_agent.brain.blackboard.blackboard import Blackboard

from .reasoning_trace import (
    ReasoningTrace,
    TraceStage,
)

from .hypothesis_engine import (
    HypothesisEngine,
    Hypothesis,
)

from .confidence_engine import (
    ConfidenceEngine,
    ConfidenceItem,
    ConfidenceSource,
)

from .uncertainty_engine import (
    UncertaintyEngine,
    UncertaintyResult,
)


# ==========================================================
# Thinking Result
# ==========================================================

@dataclass(slots=True)
class ThinkingResult:

    observation: str

    hypotheses: list[Hypothesis]

    confidence: Any

    uncertainty: UncertaintyResult

    selected_hypothesis: Hypothesis | None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


# ==========================================================
# Thinking Engine
# ==========================================================

class ThinkingEngine:

    """
    Central cognitive reasoning coordinator.
    """

    def __init__(

        self,

        blackboard: Blackboard,

    ):

        self.blackboard = blackboard

        self.trace = ReasoningTrace()

        self.hypothesis = HypothesisEngine()

        self.confidence = ConfidenceEngine()

        self.uncertainty = UncertaintyEngine()

    # ------------------------------------------------------

    def think(

        self,

        observation: str,

        required_fields: dict[str, object],

        confidence_inputs: list[ConfidenceItem],

    ) -> ThinkingResult:

        # ---------------------------------------------
        # Trace
        # ---------------------------------------------

        self.trace.add(

            stage=TraceStage.OBSERVATION,

            summary=observation,

        )

        # ---------------------------------------------
        # Hypotheses
        # ---------------------------------------------

        hypotheses = self.hypothesis.generate(

            observation,

        )

        best = self.hypothesis.best(

            hypotheses,

        )

        self.trace.add(

            stage=TraceStage.HYPOTHESIS,

            summary=best.title if best else "None",

        )

        # ---------------------------------------------
        # Confidence
        # ---------------------------------------------

        confidence = self.confidence.evaluate(

            confidence_inputs,

        )

        self.trace.add(

            stage=TraceStage.DECISION,

            summary=confidence.recommendation,

            confidence=confidence.overall,

        )

        # ---------------------------------------------
        # Uncertainty
        # ---------------------------------------------

        uncertainty = self.uncertainty.evaluate(

            confidence=confidence.overall,

            required_fields=required_fields,

        )

        self.trace.add(

            stage=TraceStage.PLANNING,

            summary=uncertainty.level.name,

            confidence=confidence.overall,

        )

        result = ThinkingResult(

            observation=observation,

            hypotheses=hypotheses,

            confidence=confidence,

            uncertainty=uncertainty,

            selected_hypothesis=best,

        )

        # ---------------------------------------------
        # Blackboard
        # ---------------------------------------------

        self.blackboard.write(

            "thinking",

            "latest",

            result,

        )

        self.blackboard.write(

            "reasoning",

            "trace",

            self.trace.latest(),

        )

        return result

    # ------------------------------------------------------

    def latest_trace(self):

        return self.trace.latest()

    # ------------------------------------------------------

    def history(self):

        return self.trace.history()