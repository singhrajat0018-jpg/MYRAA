"""
MYRAA Blackboard Subscriptions

Maintains event subscriptions.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable


class Subscriptions:

    """
    Stores all event listeners.
    """

    def __init__(self):

        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    # ---------------------------------------------------------

    def subscribe(

        self,

        event: str,

        callback: Callable,

    ) -> None:

        if callback not in self._listeners[event]:

            self._listeners[event].append(callback)

    # ---------------------------------------------------------

    def unsubscribe(

        self,

        event: str,

        callback: Callable,

    ) -> None:

        if event not in self._listeners:

            return

        try:

            self._listeners[event].remove(callback)

        except ValueError:

            pass

    # ---------------------------------------------------------

    def listeners(

        self,

        event: str,

    ) -> list[Callable]:

        return list(

            self._listeners.get(

                event,

                [],

            )

        )

    # ---------------------------------------------------------

    def clear(self):

        self._listeners.clear()

    # ---------------------------------------------------------

    def count(self) -> int:

        return sum(

            len(v)

            for v in self._listeners.values()

        )