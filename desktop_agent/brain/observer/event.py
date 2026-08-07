"""
Observer Event Models

Defines the standard event format produced by all background observers.

Every observer (Stock, Battery, Weather, etc.) must emit the same
ObserverEvent object so the Brain can process events consistently.
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ==========================================================
# Event Severity
# ==========================================================

class EventSeverity(str, Enum):

    INFO = "info"

    LOW = "low"

    MEDIUM = "medium"

    HIGH = "high"

    CRITICAL = "critical"


# ==========================================================
# Event Type
# ==========================================================

class EventType(str, Enum):

    STOCK = "stock"

    BATTERY = "battery"

    INTERNET = "internet"

    WEATHER = "weather"

    PC_HEALTH = "pc_health"

    CUSTOM = "custom"


# ==========================================================
# Observer Event
# ==========================================================

@dataclass(slots=True)
class ObserverEvent:

    source: str

    event_type: EventType

    title: str

    message: str

    severity: EventSeverity = EventSeverity.INFO

    timestamp: float = field(default_factory=time.time)

    data: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    handled: bool = False

    # ------------------------------------------------------

    @property
    def is_critical(self) -> bool:

        return self.severity == EventSeverity.CRITICAL

    # ------------------------------------------------------

    @property
    def is_high_priority(self) -> bool:

        return self.severity in (
            EventSeverity.HIGH,
            EventSeverity.CRITICAL,
        )

    # ------------------------------------------------------

    def mark_handled(self) -> None:

        self.handled = True