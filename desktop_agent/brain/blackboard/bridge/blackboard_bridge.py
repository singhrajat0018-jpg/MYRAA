from __future__ import annotations

from desktop_agent.brain.blackboard.blackboard import Blackboard


class BlackboardBridge:

    """
    Connects external events
    to Blackboard.

    Event

        ↓

    Blackboard.write()

    """

    def __init__(

        self,

        blackboard: Blackboard,

    ):

        self.blackboard = blackboard

    def publish(

        self,

        topic: str,

        key: str,

        value,

    ):

        self.blackboard.write(

            topic,

            key,

            value,

        )