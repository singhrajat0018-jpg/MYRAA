"""
MYRAA Brain

Perception Layer

Responsibilities
----------------
- Receives live DesktopState from VisionManager.
- Builds ScreenState for structured perception understanding.
- Maintains a thread-safe snapshot of the current desktop and screen state.
- Publishes perception updates to the Brain.
- Acts as the Brain's single source of truth for live desktop state.
"""

from __future__ import annotations

import copy
import logging
import threading
import time

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from desktop_agent.desktop.vision.desktop_state import DesktopState
from desktop_agent.desktop.vision.screen_state_builder import screen_state_builder
from desktop_agent.desktop.vision.screen_state import ScreenState
from desktop_agent.desktop.vision.target_resolver import TargetResolver
from desktop_agent.desktop.vision.target_resolution_result import TargetResolutionResult
from desktop_agent.desktop.vision.target_resolution_result import TargetResolutionStatus
from desktop_agent.desktop.vision.target_resolution_context import TargetResolutionContext
from desktop_agent.brain import metrics
from desktop_agent.brain.latency_tracing import LatencyContext


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

        self._screen_state_snapshot: Optional[ScreenState] = None
        self._target_resolver: Optional[TargetResolver] = None

        self._listeners: List[
            Callable[[PerceptionSnapshot], None]
        ] = []
        # Change detection for perception update optimization
        self._last_processed_state: Optional[DesktopState] = None
        self._last_processed_time: float = 0.0
        self._max_process_interval: float = 0.1  # 100ms - max time between perception updates

    # ------------------------------------------------------
    # Vision callback
    # ------------------------------------------------------

    def update(
        self,
        state: DesktopState,
    ) -> None:
        """
        Called by VisionManager whenever the desktop changes.
        Implements change detection to reduce unnecessary processing.
        """
        current_time = time.time()

        # Check if we should skip this update based on time interval and state changes
        time_since_last_update = current_time - self._last_processed_time

        # Always process if it's been too long since last update (max_interval)
        if time_since_last_update < self._max_process_interval and self._last_processed_state is not None:
            # Check if the state has changed significantly
            if self._states_are_similar(state, self._last_processed_state):
                # Skip processing - state hasn't changed enough to warrant update
                return

        with LatencyContext("action_latency_perception_update"):
            # Record success for perception subsystem
            from desktop_agent.brain.failure_containment import failure_containment_manager
            failure_containment_manager.record_success('perception')

            # Build ScreenState from DesktopState for structured perception
            screen_state = screen_state_builder.build_screen_state(state)

            with self._lock:

                # Attach ScreenState to DesktopState for backward compatibility
                state.screen_state = screen_state

                self._snapshot = PerceptionSnapshot(
                    timestamp=time.time(),
                    state=copy.deepcopy(state),
                )

                # Initialize target resolver on first update
                if self._target_resolver is None:
                    self._target_resolver = TargetResolver()

                # Update last processed state
                self._last_processed_state = copy.deepcopy(state)
                self._last_processed_time = current_time

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

    @property
    def screen_state(self):
        """Get the current ScreenState for structured perception."""
        return getattr(self.state, 'screen_state', None)

    def resolve_target(self, description: str) -> TargetResolutionResult:
        """
        Resolve a target description using the current screen state.
        Implements simple caching to avoid re-resolving identical targets.
        """
        # Simple cache for recent target resolutions
        if not hasattr(self, '_target_resolution_cache'):
            self._target_resolution_cache = {}
            self._cache_max_size = 10

        cache_key = description.strip().lower()
        current_time = time.time()

        # Check cache first
        if cache_key in self._target_resolution_cache:
            cached_result, cache_time = self._target_resolution_cache[cache_key]
            # Return cached result if it's less than 5 seconds old
            if current_time - cache_time < 5.0:
                return cached_result

        with LatencyContext("action_latency_target_resolution"):
            if not self._target_resolver:
                # Initialize resolver if not already done
                self._target_resolver = TargetResolver()

            screen_state = self.screen_state
            if not screen_state:
                result = TargetResolutionResult(
                    status=TargetResolutionStatus.UNRESOLVED,
                    reason="No screen state available for target resolution"
                )
            else:
                # Create context from current perception state
                from desktop_agent.desktop.vision.target_resolution_result import TargetResolutionContext
                context = TargetResolutionContext(
                    active_window=getattr(screen_state, 'active_window', None),
                    application=getattr(self.state, 'active_application', ''),
                    timestamp=screen_state.timestamp
                )

                result = self._target_resolver.resolve_target(description, screen_state, context)

            # Cache the result
            if len(self._target_resolution_cache) >= self._cache_max_size:
                # Remove oldest entry
                oldest_key = min(self._target_resolution_cache.keys(),
                               key=lambda k: self._target_resolution_cache[k][1])
                del self._target_resolution_cache[oldest_key]

            self._target_resolution_cache[cache_key] = (result, current_time)

            return result

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

    def _states_are_similar(self, state1: DesktopState, state2: DesktopState) -> bool:
        """
        Compare two DesktopState objects to determine if they are similar enough
        to skip perception processing.
        Returns True if states are similar (can skip), False if different (should process).
        """
        try:
            # Check basic properties that change frequently
            if state1.active_application != state2.active_application:
                return False
            if state1.active_window_title != state2.active_window_title:
                return False
            if state1.confidence != state2.confidence:
                return False

            # Check window position and size (allow small tolerance)
            if abs((state1.active_window_left or 0) - (state2.active_window_left or 0)) > 5:
                return False
            if abs((state1.active_window_top or 0) - (state2.active_window_top or 0)) > 5:
                return False
            if abs((state1.active_window_width or 0) - (state2.active_window_width or 0)) > 10:
                return False
            if abs((state1.active_window_height or 0) - (state2.active_window_height or 0)) > 10:
                return False

            # Check mouse position (allow small tolerance)
            if abs((state1.mouse_x or 0) - (state2.mouse_x or 0)) > 5:
                return False
            if abs((state1.mouse_y or 0) - (state2.mouse_y or 0)) > 5:
                return False

            # If we get here, states are similar enough to skip processing
            return True
        except Exception:
            # If comparison fails, process the update to be safe
            return False

    def __bool__(self):

        return self.ready

    def __repr__(self):

        return (

            f"Perception("
            f"ready={self.ready}, "
            f"application={self.application}, "
            f"window={self.window})"

        )