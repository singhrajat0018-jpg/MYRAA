"""
MYRAA Uncertainty Engine

Determines whether the Brain has
sufficient information to proceed.

Responsibilities
----------------
• Detect ambiguity
• Detect missing information
• Decide whether clarification is required
• Estimate uncertainty level
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


# ==========================================================
# Uncertainty Level
# ==========================================================

class UncertaintyLevel(Enum):

    NONE = auto()

    LOW = auto()

    MEDIUM = auto()

    HIGH = auto()


# ==========================================================
# Result
# ==========================================================

@dataclass(slots=True)
class UncertaintyResult:

    level: UncertaintyLevel

    requires_clarification: bool

    missing_information: list[str] = field(
        default_factory=list,
    )

    clarification_question: str = ""

    confidence: float = 1.0


# ==========================================================
# Engine
# ==========================================================

class UncertaintyEngine:

    """
    Detects ambiguity.
    """

    def __init__(self):

        self.minimum_confidence = 0.75

    # ------------------------------------------------------

    def evaluate(

        self,

        *,

        confidence: float,

        required_fields: dict[str, object],

    ) -> UncertaintyResult:

        missing = []

        for field, value in required_fields.items():

            if value is None:

                missing.append(field)

                continue

            if isinstance(value, str):

                if not value.strip():

                    missing.append(field)

                    continue

            if isinstance(value, (list, tuple, dict)):

                if len(value) == 0:

                    missing.append(field)

                    continue

        if confidence < 0.40:

            level = UncertaintyLevel.HIGH

        elif confidence < self.minimum_confidence:

            level = UncertaintyLevel.MEDIUM

        elif missing:

            level = UncertaintyLevel.LOW

        else:

            level = UncertaintyLevel.NONE

        clarify = (

            level != UncertaintyLevel.NONE

            or

            bool(missing)

        )

        question = ""

        if clarify and missing:

            question = self._build_question(missing)

        return UncertaintyResult(

            level=level,

            requires_clarification=clarify,

            missing_information=missing,

            clarification_question=question,

            confidence=confidence,

        )

    # ------------------------------------------------------

    def _build_question(

        self,

        missing: list[str],

    ) -> str:

        if len(missing) == 1:

            return (

                f"Please specify the "

                f"{missing[0]}."

            )

        return (

            "Please provide: "

            + ", ".join(missing)

        )

    # ------------------------------------------------------

    def can_execute(

        self,

        result: UncertaintyResult,

    ) -> bool:

        return (

            not result.requires_clarification

        )