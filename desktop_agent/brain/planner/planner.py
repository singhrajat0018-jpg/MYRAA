"""
MYRAA Cognitive Engine

Planner
"""

from __future__ import annotations

from .execution.execution_plan import ExecutionPlan
from desktop_agent.brain.blackboard.blackboard import Blackboard
from .planning.action_builder import ActionBuilder
from .planning.plan_optimizer import PlanOptimizer
import logging

log = logging.getLogger(__name__)

from ..decision.decision_result import DecisionResult
from ..semantic.semantic_models import (
    Intent,
    SemanticTask,
    EntityType,
)


class Planner:
    """
    Converts a SemanticTask into an executable ExecutionPlan.
    """
    def __init__(
        self,
        blackboard: Blackboard | None = None
    ) -> None:

        self.builder = ActionBuilder()

        self.optimizer = PlanOptimizer()

        self.blackboard = blackboard

    # =====================================================
    # Public
    # =====================================================

    def create_plan(self, decision):

        # --------------------------------------------------
        # New BrainDecision fast path
        # --------------------------------------------------

        if hasattr(decision, "action"):

            log.info(">>>> Planner.create_plan() [BrainDecision]")

            plan = self.build_action_plan(

                decision.action,

                getattr(decision, "parameters", {}),

            )

            if self.blackboard:

                self.blackboard.write(

                    "planning",

                    "latest",

                    plan,

                )

            return plan

        # --------------------------------------------------
        # Legacy DecisionResult path
        # --------------------------------------------------

        task = decision.task

        print("\n========== PLANNER DEBUG ==========")
        print("Decision type :", type(decision))
        print("Task          :", task)
        print("Intent        :", task.intent)
        print("Metadata      :", task.metadata)
        print("===================================")

        log.info(">>>> Planner.create_plan() [DecisionResult]")

        plan = ExecutionPlan(task=task)

        print("=" * 60)
        print("Decision Approved :", decision.approved)
        print("Decision Reason   :", decision.reason)
        print("Intent            :", decision.task.intent)
        print("Confidence        :", decision.task.confidence)
        print("=" * 60)

        if self.blackboard:

            self.blackboard.write(

                "planning",

                "latest",

                plan,

            )

        self._build_plan(task, plan)

        optimized = self.optimizer.optimize(plan)

        if self.blackboard:

            self.blackboard.write(

                "planning",

                "latest",

                optimized,

            )
        print("\n========== PLAN DEBUG ==========")
        print("Steps:", len(optimized.steps))
        for s in optimized.steps:
            print(
                s.id,
                s.action,
                s.parameters,
            )
        print("================================")
        return optimized

    # =====================================================
    # Builder
    # =====================================================

    def _build_plan(
        self,
        task: SemanticTask,
        plan: ExecutionPlan,
    ) -> None:
        print("\n========== BUILD PLAN ==========")
        print(task.metadata)
        print("================================")
        intent = task.intent

        # -------------------------------------------------
        # Structured function-call actions
        # -------------------------------------------------

        action = task.metadata.get("action")
        parameters = task.metadata.get("parameters", {})

        if action:

            print("\n========== PLANNER ==========")
            print("Action     :", action)
            print("Parameters :", parameters)
            print("=============================\n")

            plan.add_step(
                self.builder.tool_call(
                    tool_name=action,
                    parameters=parameters,
                )
            )

            return     

        # -------------------------------------------------
        # Applications
        # -------------------------------------------------

        if intent == Intent.OPEN_APPLICATION:

            application = (
                task.get_entity(EntityType.APPLICATION)
                or task.goal
                or task.raw_text
            )

            plan.add_step(

                self.builder.open_application(
                    application,
                )
            )

            return

        if intent == Intent.CLOSE_APPLICATION:

            application = (
                task.get_entity(EntityType.APPLICATION)
                or task.goal
                or task.raw_text
            )
            
            plan.add_step(

                self.builder.close_application(
                    application,
                )
            )

            return

        # -------------------------------------------------
        # Web
        # -------------------------------------------------

        if intent == Intent.SEARCH_WEB:

            query = (
                task.get_entity(EntityType.SEARCH_QUERY)
                or task.goal
                or task.raw_text
            )

            plan.add_step(
                self.builder.open_url(
                    f"https://www.google.com/search?q={query}"
                )
            )

            return

        # -------------------------------------------------
        # Chat
        # -------------------------------------------------

        if intent in (
            Intent.CHAT,
            Intent.QUESTION,
        ):

            return

        # -------------------------------------------------
        # Unknown
        # -------------------------------------------------

        plan.successful = False

        plan.reason = (
            f"No planner available for intent: {intent.value}"
        )
