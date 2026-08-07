"""
MYRAA Cognitive Engine

Event Bus

Central publish/subscribe system
for execution events.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Any


class EventBus:
    """
    Lightweight event dispatcher.

    Allows different parts of MYRAA
    to communicate without direct dependency.
    """

    def __init__(self) -> None:

        self._listeners: dict[
            str,
            list[Callable]
        ] = defaultdict(list)


    # =====================================================
    # Subscribe
    # =====================================================

    def subscribe(
        self,
        event_name: str,
        callback: Callable,
    ) -> None:
        """
        Register listener for an event.
        """

        if callback not in self._listeners[event_name]:

            self._listeners[event_name].append(
                callback
            )


    # =====================================================
    # Unsubscribe
    # =====================================================

    def unsubscribe(
        self,
        event_name: str,
        callback: Callable,
    ) -> None:
        """
        Remove event listener.
        """

        if event_name not in self._listeners:

            return


        if callback in self._listeners[event_name]:

            self._listeners[event_name].remove(
                callback
            )


    # =====================================================
    # Publish
    # =====================================================

    def publish(
        self,
        event_name: str,
        event: Any = None,
    ) -> None:
        """
        Broadcast event to all listeners.
        """

        listeners = self._listeners.get(
            event_name,
            [],
        )

        for callback in listeners:

            try:

                callback(event)

            except Exception:

                # Event listeners should never
                # break execution engine.

                continue


    # =====================================================
    # Async Publish
    # =====================================================

    async def publish_async(
        self,
        event_name: str,
        event: Any = None,
    ) -> None:
        """
        Async compatible event publishing.
        """

        listeners = self._listeners.get(
            event_name,
            [],
        )

        for callback in listeners:

            try:

                result = callback(event)

                if hasattr(
                    result,
                    "__await__"
                ):

                    await result

            except Exception:

                continue


    # =====================================================
    # Utilities
    # =====================================================

    def clear(
        self,
    ) -> None:
        """
        Remove all listeners.
        """

        self._listeners.clear()


    def listener_count(
        self,
        event_name: str,
    ) -> int:
        """
        Return number of listeners.
        """

        return len(
            self._listeners.get(
                event_name,
                [],
            )
        )


    def events(
        self,
    ) -> list[str]:
        """
        Return registered event names.
        """

        return list(
            self._listeners.keys()
        )