"""
MYRAA Hierarchical Goal Planner

Converts Goals into executable plans.

Responsibilities
----------------
• Break goals into sub-goals
• Create execution tree
• Track dependencies
• Estimate progress
• Produce planner-ready tasks

This module NEVER executes actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .goal import Goal


# ============================================================
# Goal Step
# ============================================================

@dataclass(slots=True)
class GoalStep:

    id: str

    title: str

    completed: bool = False

    metadata: dict = field(
        default_factory=dict,
    )


# ============================================================
# Goal Plan
# ============================================================

@dataclass(slots=True)
class GoalPlan:

    goal_id: str

    steps: list[GoalStep]

    progress: float = 0.0

    metadata: dict = field(
        default_factory=dict,
    )

    @property
    def finished(self):

        return all(

            step.completed

            for step in self.steps

        )


# ============================================================
# Goal Planner
# ============================================================

class GoalPlanner:

    """
    Converts Goals into plans.
    """

    def create_plan(

        self,

        goal: Goal,

    ) -> GoalPlan:

        steps = self._generate_steps(goal)

        return GoalPlan(

            goal_id=goal.id,

            steps=steps,

        )

    # ---------------------------------------------------------

    def update_progress(

        self,

        plan: GoalPlan,

    ) -> float:

        if not plan.steps:

            plan.progress = 1.0

            return 1.0

        completed = sum(

            step.completed

            for step in plan.steps

        )

        progress = completed / len(plan.steps)

        plan.progress = progress

        return progress

    # ---------------------------------------------------------

    def next_step(

        self,

        plan: GoalPlan,

    ) -> GoalStep | None:

        for step in plan.steps:

            if not step.completed:

                return step

        return None

    # ---------------------------------------------------------

    def complete_step(

        self,

        plan: GoalPlan,

        step_id: str,

    ) -> None:

        for step in plan.steps:

            if step.id == step_id:

                step.completed = True

                break

        self.update_progress(plan)

    # ---------------------------------------------------------

    def _generate_steps(

        self,

        goal: Goal,

    ) -> list[GoalStep]:

        """
        Rule-based planner.

        Future:

            LLM Planning
        """

        title = goal.title.lower()

        # -----------------------------------------
        # Coding Goals
        # -----------------------------------------

        if (

            "build" in title

            or

            "create" in title

            or

            "develop" in title

        ):

            return [

                GoalStep(

                    id=str(uuid4()),

                    title="Analyze goal",

                ),

                GoalStep(

                    id=str(uuid4()),

                    title="Create execution plan",

                ),

                GoalStep(

                    id=str(uuid4()),

                    title="Execute implementation",

                ),

                GoalStep(

                    id=str(uuid4()),

                    title="Verify results",

                ),

                GoalStep(

                    id=str(uuid4()),

                    title="Reflect and improve",

                ),

            ]

        # -----------------------------------------
        # Search Goals
        # -----------------------------------------

        if (

            "search" in title

            or

            "research" in title

        ):

            return [

                GoalStep(

                    id=str(uuid4()),

                    title="Search information",

                ),

                GoalStep(

                    id=str(uuid4()),

                    title="Collect sources",

                ),

                GoalStep(

                    id=str(uuid4()),

                    title="Summarize findings",

                ),

            ]

        # -----------------------------------------
        # Default
        # -----------------------------------------

        return [

            GoalStep(

                id=str(uuid4()),

                title="Analyze goal",

            ),

            GoalStep(

                id=str(uuid4()),

                title="Execute goal",

            ),

            GoalStep(

                id=str(uuid4()),

                title="Verify completion",

            ),

        ]