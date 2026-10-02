"""
MYRAA Brain

World Model

Maintains MYRAA's internal understanding of the current
desktop environment.

The WorldModel is NOT Vision.

Vision tells MYRAA WHAT it sees.

WorldModel tells MYRAA WHAT IT MEANS.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from dataclasses import dataclass, field
from typing import Optional

from .perception import PerceptionSnapshot


# ==========================================================
# User Activity
# ==========================================================

@dataclass(slots=True)
class UserActivity:

    name: str = "idle"

    confidence: float = 0.0

    started_at: float = field(default_factory=time.time)

    metadata: dict = field(default_factory=dict)


# ==========================================================
# Environment
# ==========================================================

@dataclass(slots=True)
class EnvironmentState:

    application: Optional[str] = None

    window: Optional[str] = None

    screen_type: Optional[str] = None

    primary_action: Optional[str] = None

    dialog_visible: bool = False

    focused_element: Optional[str] = None

    confidence: float = 0.0


# ==========================================================
# World State
# ==========================================================

@dataclass(slots=True)
class WorldState:

    timestamp: float

    environment: EnvironmentState

    activity: UserActivity

    metadata: dict = field(default_factory=dict)


# ==========================================================
# World Model
# ==========================================================

class WorldModel:

    """
    Converts Perception into a semantic world model.

    This becomes the Brain's understanding of
    the user's current desktop situation.
    """

    def __init__(
        self,
        history_size: int = 12,
        history_ttl: float = 600.0,
    ):

        self._lock = threading.RLock()

        self._state = WorldState(

            timestamp=0.0,

            environment=EnvironmentState(),

            activity=UserActivity(),

        )

        # EPIC-BRAIN B3: bounded, timestamped, invalidatable, confidence-aware
        # history. We keep the LATEST state plus a small bounded history window
        # (never unlimited screen history). Each entry is TTL-invalidatable.
        self._history_size = history_size
        self._history_ttl = history_ttl
        self._history: deque = deque(maxlen=history_size)

    def update(

        self,

        snapshot: PerceptionSnapshot,

    ):

        with self._lock:

            desktop = snapshot.state

            summary = desktop.screen_summary

            env = EnvironmentState(

                application=desktop.active_application,

                window=desktop.active_window,

                confidence=desktop.confidence,

            )

            if summary:

                env.screen_type = summary.screen_type.value

                env.primary_action = summary.primary_action

                env.dialog_visible = summary.dialog

                env.focused_element = summary.focused_element

            activity = self._infer_activity(env)

            self._state = WorldState(

                timestamp=snapshot.timestamp,

                environment=env,

                activity=activity,

            )

            self._history.append(self._state)

    # ------------------------------------------------------

    def _infer_activity(

        self,

        env: EnvironmentState,

    ) -> UserActivity:

        # Safe extraction of app and window - handle both string and dict types
        app_value = env.application
        if isinstance(app_value, dict):
            app = str(app_value.get('title', '') or app_value.get('name', '')).lower()
        else:
            app = (app_value or "").lower()

        window_value = env.window
        if isinstance(window_value, dict):
            window = str(window_value.get('title', '') or window_value.get('name', '')).lower()
        else:
            window = (window_value or "").lower()

        if "code" in app or "visual studio" in app:

            return UserActivity(

                name="coding",

                confidence=0.95,

            )

        if "chrome" in app:

            if "youtube" in window:

                return UserActivity(

                    name="watching_video",

                    confidence=0.90,

                )

            return UserActivity(

                name="browsing",

                confidence=0.80,

            )

        if "explorer" in app:

            return UserActivity(

                name="file_management",

                confidence=0.85,

            )

        if env.dialog_visible:

            return UserActivity(

                name="handling_dialog",

                confidence=0.95,

            )

        return UserActivity(

            name="idle",

            confidence=0.50,

        )

    # ------------------------------------------------------

    @property
    def state(self):

        with self._lock:

            return self._state

    @property
    def environment(self):

        return self.state.environment

    @property
    def activity(self):

        return self.state.activity

    # ------------------------------------------------------

    def summary(self):

        env = self.environment

        act = self.activity

        return {

            "application": env.application,

            "window": env.window,

            "screen_type": env.screen_type,

            "primary_action": env.primary_action,

            "activity": act.name,

            "activity_confidence": act.confidence,

            "dialog": env.dialog_visible,

            "focused_element": env.focused_element,

            "confidence": self.confidence,

            "stale": self.is_stale(),

            "history_length": len(self.history()),

        }

    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._state = WorldState(

                timestamp=0.0,

                environment=EnvironmentState(),

                activity=UserActivity(),

            )

            self._history.clear()

    # ------------------------------------------------------
    # EPIC-BRAIN B3: bounded, timestamped, invalidatable history

    def history(self) -> list:

        """Recent world states (oldest first), TTL-invalidated."""

        with self._lock:

            now = time.time()

            fresh = [
                s for s in self._history
                if now - s.timestamp <= self._history_ttl
            ]
            return list(fresh)

    def history_since(self, timestamp: float) -> list:

        """World states newer than the given epoch timestamp."""

        return [s for s in self.history() if s.timestamp > timestamp]

    def is_stale(self, max_age: float = 30.0) -> bool:

        """True when the latest world state is older than max_age seconds."""

        with self._lock:
            now = time.time()
            if self._state.timestamp <= 0:
                return True
            return (now - self._state.timestamp) > max_age

    def invalidate(self) -> None:

        """Invalidate the current world state (e.g. on explicit desktop change)."""

        with self._lock:
            self._state.timestamp = 0.0
            self._state.metadata["invalidated_at"] = time.time()

    @property
    def confidence(self) -> float:

        """Confidence of the latest world state."""

        env = self.environment
        act = self.activity
        if env is None:
            return 0.0
        return round(min(env.confidence or 0.0, act.confidence or 0.0), 4)

    # ------------------------------------------------------

    def __repr__(self):

        env = self.environment

        act = self.activity

        return (

            "WorldModel("

            f"app={env.application}, "

            f"activity={act.name}, "

            f"window={env.window})"

        )