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

    DANGEROUS_INTENTS = {
        Intent.DELETE_FILE,
        Intent.SYSTEM_CONTROL,
        Intent.CREATE_FILE,
        Intent.MOVE_FILE,
        Intent.COPY_FILE,
        Intent.CLOSE_APPLICATION,
        Intent.AUTOMATION,
        Intent.CODE_TASK,
        Intent.MULTI_STEP_TASK,
    }

    def evaluate(self, task: SemanticTask) -> SafetyResult:

        if task.intent in self.DANGEROUS_INTENTS:
            return SafetyResult(
                safe=False,
                requires_confirmation=True,
                reason=f"Dangerous operation: {task.intent.value}",
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
