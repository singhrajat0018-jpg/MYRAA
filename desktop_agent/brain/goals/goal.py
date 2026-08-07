"""
MYRAA Goal Model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class GoalStatus(Enum):

    CREATED = auto()

    QUEUED = auto()

    ACTIVE = auto()

    WAITING = auto()

    COMPLETED = auto()

    FAILED = auto()

    CANCELLED = auto()


class GoalType(Enum):

    USER = auto()

    SYSTEM = auto()

    AUTONOMOUS = auto()

    LEARNING = auto()

    MAINTENANCE = auto()


@dataclass(slots=True)
class Goal:

    id: str

    title: str

    description: str = ""

    goal_type: GoalType = GoalType.USER

    status: GoalStatus = GoalStatus.CREATED

    priority: float = 0.5

    confidence: float = 1.0

    created_at: datetime = field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = field(
        default_factory=datetime.utcnow
    )

    deadline: datetime | None = None

    parent_goal: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    progress: float = 0.0

    def activate(self):

        self.status = GoalStatus.ACTIVE

        self.updated_at = datetime.utcnow()

    def complete(self):

        self.progress = 1.0

        self.status = GoalStatus.COMPLETED

        self.updated_at = datetime.utcnow()

    def fail(self):

        self.status = GoalStatus.FAILED

        self.updated_at = datetime.utcnow()

    def cancel(self):

        self.status = GoalStatus.CANCELLED

        self.updated_at = datetime.utcnow()

    @property
    def finished(self):

        return self.status in (

            GoalStatus.COMPLETED,

            GoalStatus.CANCELLED,

            GoalStatus.FAILED,

        )