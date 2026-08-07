from __future__ import annotations

from datetime import datetime

from .cooldown import Cooldown
from .cognitive_state import CognitiveState


class CognitiveStateManager:

    def __init__(self):

        self.state = CognitiveState()

    def should_notify(self, key: str):

        if self.state.last_event_key != key:

            return True

        return Cooldown.expired(
            self.state.last_notification,
            Cooldown.NOTIFICATION,
        )

    def mark_notified(self, key: str):

        self.state.last_event_key = key

        self.state.last_notification = datetime.utcnow()

        self.state.notification_count += 1

    def should_plan(self, key: str):

        if self.state.last_event_key != key:

            return True

        return Cooldown.expired(
            self.state.last_plan,
            Cooldown.PLANNER,
        )

    def mark_planned(self, key: str):

        self.state.last_event_key = key

        self.state.last_plan = datetime.utcnow()

        self.state.plan_count += 1