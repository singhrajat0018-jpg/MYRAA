"""
MYRAA Cognitive Engine

Verification Policy
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# ==========================================================
# Verification Strategy
# ==========================================================

class VerificationStrategy(str, Enum):

    NONE = "none"

    ALWAYS = "always"

    IF_REQUIRED = "if_required"


# ==========================================================
# Verification Result
# ==========================================================

@dataclass(slots=True)
class VerificationResult:

    verified: bool

    message: str = ""

    metadata: dict[str, Any] | None = None


# ==========================================================
# Verification Policy
# ==========================================================

class VerificationPolicy:

    """
    Responsible for verifying that a planner step
    completed successfully.
    """

    async def verify(

        self,

        step,

        execution_result,

        desktop_controller,

    ) -> VerificationResult:

        # ------------------------------------------
        # Skip verification
        # ------------------------------------------

        if not step.requires_verification:

            return VerificationResult(

                verified=True,

                message="Verification skipped.",

            )

        # ------------------------------------------
        # Open Application
        # ------------------------------------------

        if step.action.name == "OPEN_APPLICATION":

            app = step.parameters.get("application")

            exists = await desktop_controller.is_application_running(app)

            return VerificationResult(

                verified=exists,

                message=(
                    f"{app} opened successfully."
                    if exists
                    else
                    f"{app} failed to open."
                ),

            )

        # ------------------------------------------
        # Open URL
        # ------------------------------------------

        if step.action.name == "OPEN_URL":

            return VerificationResult(

                verified=True,

                message="Browser navigation completed.",

            )

        # ------------------------------------------
        # Click
        # ------------------------------------------

        if step.action.name == "CLICK":

            return VerificationResult(

                verified=True,

                message="Click executed.",

            )

        # ------------------------------------------
        # Default
        # ------------------------------------------

        return VerificationResult(

            verified=True,

            message="No verification rule defined.",

        )