"""
MYRAA Brain Bridge

Vision <-> Brain Integration Layer

Responsibilities
----------------
- Receive DesktopState from VisionManager
- Maintain latest perception snapshot
- Push perception into BrainEngine
- Notify planner when meaningful changes occur
- Publish runtime events
"""

from __future__ import annotations

import threading
import time
import logging

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from desktop_agent.brain.brain_engine import BrainEngine
from desktop_agent.brain.blackboard.blackboard import Blackboard

log = logging.getLogger(__name__)


# ==========================================================
# Runtime Perception
# ==========================================================


@dataclass(slots=True)
class RuntimePerception:

    timestamp: datetime

    desktop_state: Any

    changed: bool = False

    source: str = "vision"

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


# ==========================================================
# Brain Bridge
# ==========================================================


class BrainBridge:

    """
    Connects Vision Runtime to Brain.

    Vision
        ↓
    DesktopState
        ↓
    BrainBridge
        ↓
    Brain.update_perception()
    """

    def __init__(
        self,
        brain: BrainEngine,
        blackboard: Blackboard,
    ) -> None:

        self.brain = brain

        self.blackboard = blackboard

        self._lock = threading.RLock()

        self._latest: Optional[RuntimePerception] = None

        self._running = False

        self._frames = 0

        self._last_publish = 0.0

        log.info(
            "BrainBridge initialized."
        )

    # ------------------------------------------------------

    @property
    def latest(self) -> Optional[RuntimePerception]:

        return self._latest

    # ------------------------------------------------------

    @property
    def frame_count(self) -> int:

        return self._frames

    # ------------------------------------------------------

    @property
    def running(self) -> bool:

        return self._running

    # ------------------------------------------------------
    # Runtime Control
    # ------------------------------------------------------

    def start(self) -> None:

        """
        Enable the bridge.
        """

        with self._lock:

            if self._running:
                return

            self._running = True

            log.info(
                "BrainBridge started."
            )

    # ------------------------------------------------------

    def stop(self) -> None:

        """
        Disable the bridge.
        """

        with self._lock:

            if not self._running:
                return

            self._running = False

            log.info(
                "BrainBridge stopped."
            )

    # ------------------------------------------------------
    # Vision Entry Point
    # ------------------------------------------------------

    def update(
        self,
        desktop_state,
        *,
        changed: bool = True,
        source: str = "vision",
    ) -> None:

        """
        Called by VisionManager whenever
        a new DesktopState is available.
        """

        if not self._running:
            return

        perception = RuntimePerception(

            timestamp=datetime.now(),

            desktop_state=desktop_state,

            changed=changed,

            source=source,

        )

        with self._lock:

            self._latest = perception

            self._frames += 1

        self._publish()

    # ------------------------------------------------------
    # Blackboard Publishing
    # ------------------------------------------------------

    def _publish(self) -> None:

        """
        Publish latest perception
        to Blackboard.
        """

        if self._latest is None:
            return

        self.blackboard.write(

            "vision",

            "latest",

            self._latest,

        )

        self.blackboard.write(

            "vision",

            "desktop_state",

            self._latest.desktop_state,

        )

        self.blackboard.write(

            "runtime",

            "last_frame",

            self._frames,

        )

        self._last_publish = time.perf_counter()

        log.debug(

            "Vision frame %s published.",

            self._frames,

        )

    # ------------------------------------------------------
    # Brain Synchronization
    # ------------------------------------------------------

    def process(self) -> bool:
        """
        Push latest DesktopState into Brain.

        Returns
        -------
        bool
            True if perception was delivered.
        """
        log.info(
            "[BrainBridge] Processing perception."
        )
        if not self._running:
            return False

        perception = self._latest

        if perception is None:
            return False

        try:

            # ----------------------------------------------
            # Update Brain Perception
            # ----------------------------------------------

            if hasattr(
                self.brain,
                "update_perception",
            ):

                self.brain.update_perception(
                    perception.desktop_state,
                )

            # ----------------------------------------------
            # Blackboard copy
            # ----------------------------------------------

            self.blackboard.write(

                "brain",

                "perception",

                perception,

            )

            self.blackboard.write(

                "brain",

                "last_update",

                perception.timestamp,

            )


            # ----------------------------------------------
            # Run One Cognitive Tick
            # ----------------------------------------------

            self.brain.tick()

            log.debug(

                "Brain perception updated."

            )

            return True

        except Exception:

            log.exception(

                "Brain synchronization failed."

            )

            return False

    # ------------------------------------------------------
    # Continuous Tick
    # ------------------------------------------------------

    def tick(self) -> bool:
        """
        One runtime cycle.

        Vision
            ↓
        Blackboard
            ↓
        Brain
        """

        if not self._running:
            return False

        if self._latest is None:
            return False

        return self.process()

    # ------------------------------------------------------

    def reset(self):

        with self._lock:

            self._latest = None

            self._frames = 0

            self._last_publish = 0.0

        log.info(
            "BrainBridge reset."
        )

    # ------------------------------------------------------
    # Runtime Event Processing
    # ------------------------------------------------------

    def on_desktop_changed(
        self,
        desktop_state,
    ) -> bool:
        """
        Entry point called by VisionManager whenever
        DesktopState changes.

        VisionManager
              ↓
        BrainBridge
              ↓
        BrainEngine
        """
        log.info(
            "[Vision] DesktopState received."
        )
        if not self._running:
            return False

        self.update(

            desktop_state,

            changed=True,

            source="vision",

        )

        return self.tick()

    # ------------------------------------------------------
    # Manual Runtime Update
    # ------------------------------------------------------

    def synchronize(self) -> bool:
        """
        Force one synchronization cycle.
        """

        if self._latest is None:
            return False

        return self.process()

    # ------------------------------------------------------
    # Runtime Status
    # ------------------------------------------------------

    def statistics(self) -> dict:

        return {

            "running": self._running,

            "frames": self._frames,

            "last_publish": self._last_publish,

            "has_perception": self._latest is not None,

        }

    # ------------------------------------------------------
    # Debug
    # ------------------------------------------------------

    def dump(self):

        if self._latest is None:

            return {

                "status": "empty",

            }

        return {

            "timestamp": self._latest.timestamp,

            "source": self._latest.source,

            "changed": self._latest.changed,

            "frames": self._frames,

            "desktop_state": type(

                self._latest.desktop_state

            ).__name__,

        }

    # ------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------

    def heartbeat(self):

        """
        Called continuously by runtime.

        Keeps Brain synchronized with
        the latest DesktopState.
        """

        if not self._running:

            return

        if self._latest is None:

            return

        self.tick()

    # ------------------------------------------------------
    # Desktop Event Processing
    # ------------------------------------------------------

    def process_desktop_event(
        self,
        event: str,
        desktop_state=None,
    ):

        """
        Convert a desktop event into a
        Brain processing request.

        Examples
        --------
        "chrome_opened"

        "save_dialog"

        "download_finished"

        "button_appeared"
        """

        if not self._running:

            return None

        if not event:

            return None

        try:

            log.info(

                "Desktop Event: %s",

                event,

            )

            from desktop_agent.brain.models import BrainContext

            context = BrainContext()

            #
            # Give the Brain the complete desktop state
            #

            context.desktop_state = desktop_state

            #
            # Keep event as user-visible semantic trigger
            #

            context.desktop_event = event

            result = self.brain.process(

                event,

                context,

            )

            self.blackboard.write(

                "runtime",

                "last_result",

                result,

            )

            return result

        except Exception:

            log.exception(

                "Brain processing failed."

            )

            return None

    # ------------------------------------------------------

    def process_desktop_state(
        self,
        desktop_state,
    ):

        """
        Convert DesktopState into
        semantic desktop events.
        """
        log.info(
            "[BrainBridge] Converting DesktopState."
        )
        if desktop_state is None:

            return
        #
        # Update live perception
        #

        self.brain.update_perception(
            desktop_state
        )
        event = self._extract_event(

            desktop_state,

        )

        if event is None:

            return

        return self.process_desktop_event(
            event,
            desktop_state,
        )

    # ------------------------------------------------------

    def _extract_event(
        self,
        desktop_state,
    ):

        """
        Temporary extractor.

        Future versions will use
        VisionContext.

        For now we simply look
        for a textual event.
        """

        if hasattr(

            desktop_state,

            "event",

        ):

            return desktop_state.event

        if hasattr(

            desktop_state,

            "title",

        ):

            return desktop_state.title

        return None