"""
MYRAA Autonomous State

Represents the current autonomous
state of the Brain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class AutonomyMode(Enum):

    OFF = auto()

    PASSIVE = auto()

    ASSISTIVE = auto()

    PROACTIVE = auto()

    FULL = auto()


@dataclass(slots=True)
class AutonomyState:
    """
    Runtime autonomous state.
    """

    enabled: bool = False

    mode: AutonomyMode = AutonomyMode.PASSIVE

    started_at: datetime = field(
        default_factory=datetime.utcnow
    )

    last_cycle: datetime | None = None

    cycles: int = 0

    observations: int = 0

    events_detected: int = 0

    plans_created: int = 0

    actions_executed: int = 0

    reflections: int = 0

    predictions: int = 0

    learning_events: int = 0

    idle: bool = False

    sleeping: bool = False

    paused: bool = False

    busy: bool = False

    current_goal: str = ""

    current_activity: str = ""

    confidence: float = 1.0

    # -----------------------------------------------------

    @property
    def running(self) -> bool:

        return (

            self.enabled

            and

            not self.paused

            and

            not self.sleeping

        )

    # -----------------------------------------------------

    def reset_statistics(self):

        self.cycles = 0

        self.observations = 0

        self.events_detected = 0

        self.plans_created = 0

        self.actions_executed = 0

        self.reflections = 0

        self.predictions = 0

        self.learning_events = 0