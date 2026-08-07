from __future__ import annotations

from collections import deque


class GoalScheduler:

    """
    Schedules multiple goals.

    Highest priority goal is executed first.
    """

    def __init__(self):

        self.queue = deque()

    # ----------------------------

    def add(self, goal):

        if goal not in self.queue:

            self.queue.append(goal)

    # ----------------------------

    def next(self):

        if self.queue:

            return self.queue[0]

        return None

    # ----------------------------

    def complete(self):

        if self.queue:

            self.queue.popleft()

    # ----------------------------

    def clear(self):

        self.queue.clear()

    # ----------------------------

    def __len__(self):

        return len(self.queue)