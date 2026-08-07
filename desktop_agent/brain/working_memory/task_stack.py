"""
Simple task stack for Working Memory.
"""

from __future__ import annotations


class TaskStack:

    def __init__(self):

        self._stack = []

        self._history = []

    def push(self, task):

        self._stack.append(task)

    def pop(self):

        if not self._stack:
            return None

        task = self._stack.pop()

        self._history.append(task)

        return task

    def current(self):

        if not self._stack:
            return None

        return self._stack[-1]

    def clear(self):

        self._stack.clear()

    def history(self):

        return list(self._history)