"""
MYRAA Brain

Perception Layer

Responsibilities
----------------
- Receives live DesktopState from VisionManager.
- Maintains a thread-safe snapshot of the current desktop.
- Publishes perception updates to the Brain.
- Acts as the Brain's single source of truth for live desktop state.
"""

from __future__ import annotations

import copy
import threading
import time

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from desktop_agent.desktop.vision.desktop_state import DesktopState


# ==========================================================
# Perception Snapshot
# ==========================================================

@dataclass(slots=True)
class PerceptionSnapshot:
    """
    Immutable snapshot of the desktop.
    """

    timestamp: float

    state: DesktopState


# ==========================================================
# Perception
# ==========================================================

class Perception:
    """
    Brain interface to the Vision subsystem.

    VisionManager pushes DesktopState updates here.

    The Brain only communicates with this class,
    never directly with VisionManager.
    """

    def __init__(self):

        self._lock = threading.RLock()

        self._snapshot = PerceptionSnapshot(
            timestamp=0.0,
            state=DesktopState(),
        )

        self._listeners: List[
            Callable[[PerceptionSnapshot], None]
        ] = []

    # ------------------------------------------------------
    # Vision callback
    # ------------------------------------------------------

    def update(
        self,
        state: DesktopState,
    ) -> None:
        """
        Called by VisionManager whenever the desktop changes.
        """

        with self._lock:

            self._snapshot = PerceptionSnapshot(
                timestamp=time.time(),
                state=copy.deepcopy(state),
            )

        self._notify()

    # ------------------------------------------------------
    # Snapshot access
    # ------------------------------------------------------

    @property
    def snapshot(self) -> PerceptionSnapshot:
        """
        Returns the latest immutable snapshot.
        """

        with self._lock:

            return copy.deepcopy(self._snapshot)

    @property
    def state(self) -> DesktopState:

        return self.snapshot.state

    @property
    def screen(self):

        return self.state.screen_summary

    @property
    def context(self):

        return self.state.vision_context

    @property
    def application(self):

        return self.state.active_application

    @property
    def window(self):

        return self.state.active_window

    @property
    def confidence(self):

        return self.state.confidence

    @property
    def ready(self):

        return self.state.ready

    # ------------------------------------------------------
    # Event System
    # ------------------------------------------------------

    def add_listener(
        self,
        callback: Callable[[PerceptionSnapshot], None],
    ) -> None:

        self._listeners.append(callback)

    def remove_listener(
        self,
        callback,
    ) -> None:

        if callback in self._listeners:

            self._listeners.remove(callback)

    def _notify(self):

        snapshot = self.snapshot

        for listener in tuple(self._listeners):

            try:

                listener(snapshot)

            except Exception:

                pass

    # ------------------------------------------------------
    # Utilities
    # ------------------------------------------------------

    def clear(self):

        with self._lock:

            self._snapshot = PerceptionSnapshot(
                timestamp=0.0,
                state=DesktopState(),
            )

    def __bool__(self):

        return self.ready

    def __repr__(self):

        return (

            f"Perception("
            f"ready={self.ready}, "
            f"application={self.application}, "
            f"window={self.window})"

        )