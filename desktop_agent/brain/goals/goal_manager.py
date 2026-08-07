"""
MYRAA Goal Manager
"""

from __future__ import annotations

from uuid import uuid4

from .goal import (
    Goal,
    GoalStatus,
    GoalType,
)

from .goal_memory import GoalMemory
from desktop_agent.brain.blackboard.blackboard import Blackboard
from .goal_priority import GoalPriority


class GoalManager:
    """
    Central manager for all goals.
    """

    def __init__(

        self,

        blackboard: Blackboard | None = None,

    ):

        self.memory = GoalMemory()

        self.priority_engine = GoalPriority()

        self.blackboard = blackboard

    # -----------------------------------------------------

    def create_goal(

        self,

        title: str,

        description: str = "",

        goal_type: GoalType = GoalType.USER,

        priority: float = 0.5,

        confidence: float = 1.0,

        metadata: dict | None = None,

    ) -> Goal:

        goal = Goal(

            id=str(uuid4()),

            title=title,

            description=description,

            goal_type=goal_type,

            priority=priority,

            confidence=confidence,

            metadata=metadata or {},

        )
        self.blackboard.write(

            "goal",

            goal.id,

            goal,

        )
        self.blackboard.write(

            "goal",

            "active",

            goal,

        )

        self.memory.add(goal)

        return goal

    # -----------------------------------------------------

    def activate(

        self,

        goal_id: str,

    ) -> Goal | None:

        goal = self.memory.get(goal_id)

        if goal is None:

            return None

        goal.activate()

        return goal

    # -----------------------------------------------------

    def complete(

        self,

        goal_id: str,

    ) -> Goal | None:

        goal = self.memory.get(goal_id)

        if goal is None:

            return None

        goal.complete()

        return goal

    # -----------------------------------------------------

    def fail(

        self,

        goal_id: str,

    ) -> Goal | None:

        goal = self.memory.get(goal_id)

        if goal is None:

            return None

        goal.fail()

        return goal

    # -----------------------------------------------------

    def cancel(

        self,

        goal_id: str,

    ) -> Goal | None:

        goal = self.memory.get(goal_id)

        if goal is None:

            return None

        goal.cancel()

        return goal

    # -----------------------------------------------------

    def active_goals(self):

        goals = self.memory.active()

        goals.sort(

            key=lambda g: self.priority_engine.calculate(g),

            reverse=True,

        )

        return goals

    # -----------------------------------------------------

    def next_goal(self) -> Goal | None:

        goals = self.active_goals()

        if not goals:

            return None

        return goals[0]

    # -----------------------------------------------------

    def all_goals(self):

        return self.memory.all()