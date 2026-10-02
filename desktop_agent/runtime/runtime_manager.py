"""
MYRAA Runtime Manager

Connects

Vision
↓

Brain

↓

Desktop
"""

from __future__ import annotations

import logging

import threading

import time

from desktop_agent.runtime.brain_bridge import BrainBridge
from desktop_agent.desktop.vision.vision_manager import VisionManager
from desktop_agent.brain.brain_engine import BrainEngine
from desktop_agent.brain.blackboard.blackboard import Blackboard

log = logging.getLogger(__name__)


class RuntimeManager:

    def __init__(

        self,

        brain: BrainEngine,

        vision: VisionManager,

        memory_2_0=None,

        consolidation_interval: float = 60.0,

        screen_share=None,

    ):

        self.brain = brain

        self.vision = vision

        self.screen_share = screen_share

        self.blackboard = brain.blackboard

        # Memory 2.0 consolidation store (M7). When provided, the runtime runs a
        # periodic consolidation pass promoting WORKING → EPISODIC → SEMANTIC.
        self.memory_2_0 = memory_2_0

        self.consolidation_interval = consolidation_interval

        self._consolidation_running = False

        self._consolidation_thread = None

        self._consolidation_lock = threading.RLock()

        self.bridge = BrainBridge(

            brain,

            self.blackboard,

        )

    def start(self):

        """
        Starts runtime.

        VisionManager's vision loop reads from ScreenShareEngine,
        builds enriched DesktopState, and publishes to BrainBridge.
        """

        self.bridge.start()

        self.vision.add_state_listener(

            self.bridge.on_desktop_changed,

        )

        self.vision.start(screen_share=self.screen_share)

        log.info(

            "Runtime started."

        )
        self.brain.autonomy.start()
        self._start_consolidation()
    # --------------------------------------------------

    def stop(self):

        self._stop_consolidation()

        self.bridge.stop()

        self.vision.stop()

        log.info(

            "Runtime stopped."

        )

    # --------------------------------------------------
    # Memory 2.0 Consolidation (M7)
    # --------------------------------------------------

    def _start_consolidation(self):

        """Start the periodic consolidation background thread (daemon)."""

        if self.memory_2_0 is None:

            return

        with self._consolidation_lock:

            if self._consolidation_running:

                return

            self._consolidation_running = True

            self._consolidation_thread = threading.Thread(

                target=self._consolidation_loop,

                daemon=True,

                name="MYRAA-Consolidation",

            )

            self._consolidation_thread.start()

            log.info(

                "Memory consolidation loop started (every %ss).",

                self.consolidation_interval,

            )

    def _stop_consolidation(self):

        with self._consolidation_lock:

            self._consolidation_running = False

            thread = self._consolidation_thread

            self._consolidation_thread = None

        if thread is not None and thread.is_alive():

            thread.join(timeout=2.0)

    def _consolidation_loop(self):

        """Daemon loop: run a consolidation pass every interval seconds."""

        while True:

            with self._consolidation_lock:

                if not self._consolidation_running:

                    return

            try:

                self.consolidate_now()

            except Exception:

                log.exception("[Runtime] Memory consolidation pass failed.")

            time.sleep(self.consolidation_interval)

    def consolidate_now(self) -> dict:

        """Run one consolidation pass synchronously and return its stats."""

        if self.memory_2_0 is None:

            return {"working_to_episodic": 0, "episodic_to_semantic": 0}

        return self.memory_2_0.consolidate()

    # --------------------------------------------------
    # Status
    # --------------------------------------------------

    @property
    def running(self) -> bool:

        return (

            self.bridge.running

            and self.vision.is_running

        )

    # --------------------------------------------------

    def statistics(self):

        return {

            "runtime": self.running,

            "vision": self.vision.statistics,

            "bridge": self.bridge.statistics(),

        }

    # --------------------------------------------------

    def health(self):

        return {

            "runtime": self.running,

            "vision": self.vision.healthy,

            "bridge_frames": self.bridge.frame_count,

        }

    # --------------------------------------------------

    def restart(self):

        self.stop()

        self.start()

    # --------------------------------------------------
    # Context Manager
    # --------------------------------------------------

    def __enter__(self):

        self.start()

        return self

    # --------------------------------------------------

    def __exit__(

        self,

        exc_type,

        exc,

        tb,

    ):

        self.stop()