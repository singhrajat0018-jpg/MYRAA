"""
MYRAA Brain Runtime

Continuous Cognitive Loop
"""

from __future__ import annotations

import threading
import time


class BrainLoop:

    def __init__(

        self,

        brain,

        fps=2,

    ):

        self.brain = brain

        self.interval = 1.0 / fps

        self.running = False

        self.thread = None