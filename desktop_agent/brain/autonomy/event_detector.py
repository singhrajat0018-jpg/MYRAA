"""
MYRAA Event Detector

Converts observations into semantic events.

Responsibilities
----------------
• Detect battery events
• Detect idle events
• Detect application events
• Detect network events
• Detect system events

No reasoning.

No planning.

No execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from .observation_engine import Observation


# ==========================================================
# Event Type
# ==========================================================

class EventType(Enum):

    BATTERY_LOW = auto()

    BATTERY_CHARGING = auto()

    USER_IDLE = auto()

    USER_ACTIVE = auto()

    INTERNET_LOST = auto()

    INTERNET_RESTORED = auto()

    APPLICATION_STARTED = auto()

    APPLICATION_CLOSED = auto()

    HIGH_CPU = auto()

    HIGH_MEMORY = auto()

    OBSERVATION = auto()


# ==========================================================
# Event
# ==========================================================

@dataclass(slots=True)
class Event:

    type: EventType

    timestamp: datetime

    description: str

    confidence: float = 1.0

    metadata: dict = field(
        default_factory=dict,
    )


# ==========================================================
# Event Detector
# ==========================================================

class EventDetector:

    """
    Detects runtime events.

    Stateless decision maker.

    Input:
        Observation

    Output:
        Events
    """

    def __init__(self):

        self.previous = None
        self.high_cpu = False
        self.high_memory = False
        self.user_idle = False

    # ------------------------------------------------------

    def detect(

        self,

        observation: Observation,

    ) -> list[Event]:

        events: list[Event] = []

        # --------------------------------------------
        # Battery
        # --------------------------------------------

        if (

            observation.battery_percent is not None

            and

            observation.battery_percent <= 15

            and

            not observation.battery_plugged

        ):

            events.append(

                Event(

                    EventType.BATTERY_LOW,

                    datetime.utcnow(),

                    "Battery level is critically low.",

                )

            )

        # --------------------------------------------
        # CPU
        # --------------------------------------------

        if observation.cpu_percent >= 90:

            if not self.high_cpu:

                self.high_cpu = True

                events.append(
                    Event(
                        EventType.HIGH_CPU,
                        datetime.utcnow(),
                        "CPU usage is very high.",
                        metadata={
                            "cpu": observation.cpu_percent
                        },
                    )
                )

        else:

            self.high_cpu = False

        # --------------------------------------------
        # RAM
        # --------------------------------------------

        if observation.ram_percent >= 90:

            if not self.high_memory:

                self.high_memory = True

                events.append(
                    Event(
                        EventType.HIGH_MEMORY,
                        datetime.utcnow(),
                        "Memory usage is very high.",
                        metadata={
                            "ram": observation.ram_percent
                        },
                    )
                )

        else:

            self.high_memory = False

        # --------------------------------------------
        # Internet
        # --------------------------------------------

        if self.previous is not None:

            if (

                self.previous.internet_available

                and

                not observation.internet_available

            ):

                events.append(

                    Event(

                        EventType.INTERNET_LOST,

                        datetime.utcnow(),

                        "Internet connection lost.",

                    )

                )

            elif (

                not self.previous.internet_available

                and

                observation.internet_available

            ):

                events.append(

                    Event(

                        EventType.INTERNET_RESTORED,

                        datetime.utcnow(),

                        "Internet connection restored.",

                    )

                )

        # --------------------------------------------
        # User Idle
        # --------------------------------------------

        if observation.idle_seconds >= 300:

            if not self.user_idle:

                self.user_idle = True

                events.append(
                    Event(
                        EventType.USER_IDLE,
                        datetime.utcnow(),
                        "User has been idle.",
                    )
                )

        else:

            self.user_idle = False
        # --------------------------------------------
        # Application Start / Close
        # --------------------------------------------

        if self.previous is not None:

            previous_apps = set(
                self.previous.running_apps
            )

            current_apps = set(
                observation.running_apps
            )

            started = current_apps - previous_apps

            closed = previous_apps - current_apps

            for app in started:

                events.append(

                    Event(

                        EventType.APPLICATION_STARTED,

                        datetime.utcnow(),

                        f"{app} started.",

                        metadata={

                            "application": app

                        },

                    )

                )

            for app in closed:

                events.append(

                    Event(

                        EventType.APPLICATION_CLOSED,

                        datetime.utcnow(),

                        f"{app} closed.",

                        metadata={

                            "application": app

                        },

                    )

                )

        # --------------------------------------------

        self.previous = observation

        return events