"""
MYRAA Cognitive Engine
Safety Manager
"""

from __future__ import annotations

from dataclasses import dataclass

from ..semantic.semantic_models import (
    Intent,
    SemanticTask,
)


@dataclass(slots=True)
class SafetyResult:

    safe: bool

    requires_confirmation: bool

    reason: str = ""


class SafetyManager:
    """
    Determines whether a task is safe to execute.
    """

    # Dangerous intents
    DANGEROUS_INTENTS = {

        Intent.DELETE_FILE,

        Intent.SYSTEM_CONTROL,

    }

    # ---------------------------------------------------------

    def evaluate(
        self,
        task: SemanticTask,
    ) -> SafetyResult:

        if task.intent in self.DANGEROUS_INTENTS:

            return SafetyResult(

                safe=True,

                requires_confirmation=True,

                reason="Dangerous operation",

            )

        if task.confidence < 0.50:

            return SafetyResult(

                safe=False,

                requires_confirmation=False,

                reason="Low confidence",

            )

        return SafetyResult(

            safe=True,

            requires_confirmation=False,

            reason="Safe",

        )