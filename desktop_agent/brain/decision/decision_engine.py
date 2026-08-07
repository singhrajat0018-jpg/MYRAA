"""
MYRAA Cognitive Engine
Decision Engine
"""

from __future__ import annotations

from .decision_result import DecisionResult
from .execution_strategy import ExecutionStrategy
from .safety import SafetyManager
from .validators import DecisionValidator

from ..semantic.semantic_models import (
    Intent,
    SemanticTask,
)


class DecisionEngine:
    """
    Converts a SemanticTask into an executable decision.
    """

    def __init__(self):

        self.validator = DecisionValidator()

        self.safety = SafetyManager()

    # ----------------------------------------------------

    def decide(
        self,
        task: SemanticTask,
        brain_context=None,
    ) -> DecisionResult:


        active_goal = None

        if brain_context is not None:
            active_goal = brain_context.metadata.get("active_goal")
        # --------------------------
        # Validation
        # --------------------------

        validation = self.validator.validate(task)

        if not validation.valid:

            return DecisionResult(
                task=task,
                strategy=ExecutionStrategy.REJECT,
                approved=False,
                confidence=0.0,
                reason=validation.reason,
            )

        # --------------------------
        # Safety
        # --------------------------

        safety = self.safety.evaluate(task)

        if not safety.safe:

            return DecisionResult(
                task=task,
                strategy=ExecutionStrategy.REJECT,
                approved=False,
                confidence=task.confidence,
                reason=safety.reason,
            )

        # --------------------------
        # Strategy Selection
        # --------------------------

        strategy = self._select_strategy(task)

        if active_goal:
            print(f"[Decision] Active Goal: {active_goal}")

        return DecisionResult(
            task=task,
            strategy=strategy,
            approved=True,
            confidence=task.confidence,
            reason="Decision successful",
            requires_confirmation=safety.requires_confirmation,
            requires_reasoning=(
                strategy == ExecutionStrategy.REASON
            ),
            requires_planning=(
                strategy == ExecutionStrategy.PLAN
            ),
        )

    # ----------------------------------------------------

    def _select_strategy(
        self,
        task: SemanticTask,
    ) -> ExecutionStrategy:

# Multi-step tasks

        if task.intent == Intent.MULTI_STEP_TASK:
            return ExecutionStrategy.PLAN

        # Vision tasks

        if task.intent == Intent.VISION:
            return ExecutionStrategy.REASON

        # Coding

        if task.intent == Intent.CODE_TASK:
            return ExecutionStrategy.REASON

        # Automation

        if task.intent == Intent.AUTOMATION:
            return ExecutionStrategy.AUTOMATION

        # File deletion

        if task.intent == Intent.DELETE_FILE:
            return ExecutionStrategy.CONFIRM

        # System operations

        if task.intent == Intent.SYSTEM_CONTROL:
            return ExecutionStrategy.CONFIRM

        # Default

        return ExecutionStrategy.DIRECT