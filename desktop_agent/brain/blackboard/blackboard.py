"""
MYRAA Blackboard

Central communication hub for the Brain.

Every cognitive module communicates
through the Blackboard.
"""

from __future__ import annotations

from typing import Any

from .working_blackboard import WorkingBlackboard
from .event_bus import EventBus


class Blackboard:
    """
    Central Brain Blackboard.
    """

    def __init__(self) -> None:

        self.memory = WorkingBlackboard()

        self.events = EventBus()

    # =====================================================
    # Memory API
    # =====================================================

    def write(

        self,

        channel: str,

        key: str,

        value: Any,

    ) -> None:

        self.memory.write(

            channel,

            key,

            value,

        )

        self.events.publish(

            f"{channel}.{key}.updated",

            channel=channel,

            key=key,

            value=value,

        )

    # -----------------------------------------------------

    def read(

        self,

        channel: str,

        key: str,

        default=None,

    ):

        return self.memory.read(

            channel,

            key,

            default,

        )

    # -----------------------------------------------------

    def channel(

        self,

        channel: str,

    ):

        return self.memory.channel(

            channel,

        )

    # -----------------------------------------------------

    def update_context(

        self,

        **kwargs,

    ):

        self.memory.update_context(

            **kwargs,

        )

        self.events.publish(

            "context.updated",

            **kwargs,

        )

    # -----------------------------------------------------

    def context(self):

        return self.memory.context

    # -----------------------------------------------------

    def snapshot(self):

        return self.memory.snapshot()

    # =====================================================
    # Event API
    # =====================================================

    def publish(

        self,

        event: str,

        **payload,

    ):

        return self.events.publish(

            event,

            **payload,

        )

    # -----------------------------------------------------

    def subscribe(

        self,

        event: str,

        callback,

    ):

        self.events.subscribe(

            event,

            callback,

        )

    # -----------------------------------------------------

    def unsubscribe(

        self,

        event: str,

        callback,

    ):

        self.events.unsubscribe(

            event,

            callback,

        )

    # =====================================================
    # Utility
    # =====================================================

    def clear(self):

        self.memory.clear()

        self.events.clear()

    # -----------------------------------------------------

    def channels(self):

        return self.memory.channels()