"""
Goal Memory
"""

from __future__ import annotations

from .goal import Goal


class GoalMemory:

    """
    Stores all goals.
    """

    def __init__(self):

        self.goals: dict[str, Goal] = {}

    def add(

        self,

        goal: Goal,

    ):

        self.goals[goal.id] = goal

    def remove(

        self,

        goal_id: str,

    ):

        self.goals.pop(

            goal_id,

            None,

        )

    def get(

        self,

        goal_id: str,

    ) -> Goal | None:

        return self.goals.get(goal_id)

    def active(self):

        return [

            g

            for g in self.goals.values()

            if not g.finished

        ]

    def completed(self):

        return [

            g

            for g in self.goals.values()

            if g.finished

        ]

    def all(self):

        return list(

            self.goals.values()

        )

    def clear(self):

        self.goals.clear()