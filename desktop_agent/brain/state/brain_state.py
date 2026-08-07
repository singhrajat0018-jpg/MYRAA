"""
MYRAA Unified Brain State

Single source of truth for the current runtime state.
"""

from __future__ import annotations

import threading
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CognitiveState(Enum):

    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    LEARNING = "learning"
    PAUSED = "paused"
    ERROR = "error"


@dataclass(slots=True)
class RuntimeSnapshot:

    # Runtime
    state: CognitiveState
    since: float

    # Goal System
    goal: Any = None
    task: Any = None
    plan: Any = None

    # Environment
    active_window: str = ""
    active_application: str = ""
    running_apps: list[str] = field(default_factory=list)

    battery_percent: int | None = None
    battery_plugged: bool = False

    internet_available: bool = False
    idle_seconds: float = 0.0

    # Attention
    attention_target: str | None = None
    focus_score: float = 1.0

    # Thinking
    confidence: float = 1.0
    uncertainty: float = 0.0

    # Background
    background_tasks: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


class BrainState:

    """
    Thread-safe runtime state.

    Stores ONLY the current state.

    No reasoning.
    No planning.
    No execution.
    """

    def __init__(self):

        self._lock = threading.RLock()

        self._snapshot = RuntimeSnapshot(

            state=CognitiveState.IDLE,

            since=time.time(),

        )

    # =====================================================

    @property
    def state(self):

        return self._snapshot.state

    # =====================================================

    def transition(
        self,
        state: CognitiveState,
    ):

        with self._lock:

            self._snapshot.state = state

            self._snapshot.since = time.time()

    # =====================================================

    def update(self, **kwargs):

        with self._lock:

            for key, value in kwargs.items():

                if hasattr(self._snapshot, key):

                    setattr(

                        self._snapshot,

                        key,

                        value,

                    )
            self._snapshot.since = time.time()
    # =====================================================

    def set_goal(
        self,
        goal,
    ):

        self.update(
            goal=goal,
        )

    # =====================================================

    def set_task(
        self,
        task,
    ):

        self.update(
            task=task,
        )

    # =====================================================

    def set_plan(
        self,
        plan,
    ):

        self.update(
            plan=plan,
        )

    # =====================================================

    def set_attention(
        self,
        target,
        score: float = 1.0,
    ):

        self.update(
            attention_target=target,
            focus_score=score,
        )

    # =====================================================

    def set_thinking(
        self,
        confidence: float,
        uncertainty: float,
    ):

        self.update(
            confidence=confidence,
            uncertainty=uncertainty,
        )
    # =====================================================

    def snapshot(self):

        with self._lock:

            return RuntimeSnapshot(

                **self._snapshot.__dict__

            )