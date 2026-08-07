"""
Goal Manager

Responsible for
- Active goal
- Goal queue
- Goal completion
"""

from collections import deque


class GoalManager:

    def __init__(self):

        self._goals = deque()

        self._active = None

        self._completed = []

        self._failed = []

        self._cancelled = []

        self._history = []

        self._paused = None

    # -------------------------------

    def push(self, goal):

        self._goals.append(goal)

        self._history.append(goal)

    # -------------------------------

    def next(self):

        if self._active is None:

            if self._goals:

                self._active = self._goals.popleft()

                if hasattr(self._active, "activate"):

                    self._active.activate()

        return self._active

    # -------------------------------

    def complete(self):

        if self._active:

            if hasattr(self._active, "complete"):

                self._active.complete()

            self._completed.append(

                self._active

            )

        self._active = None

    def fail(self):

        if self._active:

            if hasattr(self._active, "fail"):

                self._active.fail()

            self._failed.append(

                self._active

            )

        self._active = None


    def cancel(self):

        if self._active:

            if hasattr(self._active, "cancel"):

                self._active.cancel()

            self._cancelled.append(

                self._active

            )

        self._active = None


    def pause(self):

        self._paused = self._active


    def resume(self):

        self._active = self._paused

        self._paused = None

    # -------------------------------

    @property
    def active(self):

        return self._active

    @property
    def completed(self):

        return tuple(

            self._completed

        )


    @property
    def failed(self):

        return tuple(

            self._failed

        )


    @property
    def cancelled(self):

        return tuple(

            self._cancelled

        )


    @property
    def history(self):

        return tuple(

            self._history

        )