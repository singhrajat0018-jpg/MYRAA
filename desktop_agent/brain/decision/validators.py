"""
MYRAA Cognitive Engine
Decision Validators
"""

from __future__ import annotations

from dataclasses import dataclass

from ..semantic.semantic_models import (
    EntityType,
    Intent,
    SemanticTask,
)


@dataclass(slots=True)
class ValidationResult:

    valid: bool

    reason: str = ""


class DecisionValidator:
    """
    Validates a SemanticTask before execution.
    """

    def validate(
        self,
        task: SemanticTask,
    ) -> ValidationResult:

        if task.intent == Intent.UNKNOWN:

            metadata = task.metadata or {}

            if "action" not in metadata:

                return ValidationResult(

                    False,

                    "Unknown intent",

                )

        # --------------------------------------------

        if task.intent == Intent.OPEN_APPLICATION:

            if not task.has_entity(
                EntityType.APPLICATION
            ):

                return ValidationResult(

                    False,

                    "Missing application entity",

                )

        # --------------------------------------------

        if task.intent == Intent.SEARCH_WEB:

            if not task.has_entity(
                EntityType.SEARCH_QUERY
            ):

                return ValidationResult(

                    False,

                    "Missing search query",

                )

        # --------------------------------------------

        if task.confidence < 0.50:

            return ValidationResult(

                False,

                "Confidence too low",

            )

        return ValidationResult(

            True,

            "Valid",

        )