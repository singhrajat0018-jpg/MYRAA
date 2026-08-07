from __future__ import annotations

from .reasoning_result import ReasoningResult
from .hypothesis import Hypothesis


class ReasoningPipeline:
    """
    High-level reasoning coordinator.

    Uses the existing ReasoningEngine instead of replacing it.
    """

    def __init__(self, engine):

        self.engine = engine

    def analyze(self, attention_item):

        event = attention_item.payload

        hypothesis = self._build_hypothesis(event)

        result = ReasoningResult()

        result.summary = hypothesis.explanation

        result.confidence = hypothesis.confidence

        if hypothesis.confidence >= 0.75:

            result.should_notify = True

        if hypothesis.confidence >= 0.90:

            result.should_plan = True

        return result

    def _build_hypothesis(self, event):

        return Hypothesis(
            title=getattr(event, "title", "Unknown"),
            confidence=0.80,
            explanation=getattr(event, "message", ""),
        )