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

    ):

        self.brain = brain

        self.vision = vision

        self.blackboard = brain.blackboard

        self.bridge = BrainBridge(

            brain,

            self.blackboard,

        )

    def start(self):

        """
        Starts runtime.
        """

        self.bridge.start()

        self.vision.add_state_listener(

            self.bridge.on_desktop_changed,

        )

        self.vision.start()

        log.info(

            "Runtime started."

        )
        self.brain.autonomy.start()
    # --------------------------------------------------

    def stop(self):

        self.bridge.stop()

        self.vision.stop()

        log.info(

            "Runtime stopped."

        )

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