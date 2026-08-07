"""
MYRAA Observation Engine

Collects information about the current
environment.

This module NEVER makes decisions.

Responsibilities
----------------
• Observe desktop
• Observe user activity
• Observe system state
• Observe time
• Observe running applications

Decision making belongs to:
    Reasoning Engine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import psutil


# ============================================================
# Observation
# ============================================================

@dataclass(slots=True)
class Observation:

    timestamp: datetime

    cpu_percent: float

    ram_percent: float

    battery_percent: int | None

    battery_plugged: bool

    active_window: str = ""

    running_apps: list[str] = field(
        default_factory=list,
    )

    idle_seconds: float = 0.0

    internet_available: bool = False

    clipboard_text: str = ""

    metadata: dict = field(
        default_factory=dict,
    )


# ============================================================
# Observation Engine
# ============================================================

class ObservationEngine:

    """
    Collects runtime observations.

    NO reasoning.

    NO planning.

    NO execution.
    """

    def __init__(self):

        self.last_observation = None

    # --------------------------------------------------------

    def observe(self) -> Observation:

        battery = psutil.sensors_battery()

        observation = Observation(

            timestamp=datetime.utcnow(),

            cpu_percent=psutil.cpu_percent(),

            ram_percent=psutil.virtual_memory().percent,

            battery_percent=(
                battery.percent
                if battery
                else None
            ),

            battery_plugged=(
                battery.power_plugged
                if battery
                else False
            ),

            active_window=self.get_active_window(),

            running_apps=self.get_running_apps(),

            idle_seconds=self.get_idle_seconds(),

            internet_available=self.internet_available(),

            clipboard_text=self.get_clipboard(),

        )

        self.last_observation = observation

        return observation

    # --------------------------------------------------------

    def get_running_apps(
        self,
    ) -> list[str]:

        apps = []

        for proc in psutil.process_iter(

            ["name"]

        ):

            try:

                name = proc.info["name"]

                if name:

                    apps.append(name)

            except Exception:

                continue

        return sorted(

            list(set(apps))

        )

    # --------------------------------------------------------

    def get_active_window(
        self,
    ) -> str:

        """
        Placeholder.

        Will later use:
            pywin32
        """

        return ""

    # --------------------------------------------------------

    def get_idle_seconds(
        self,
    ) -> float:

        """
        Placeholder.

        Later:

        Windows Idle API
        """

        return 0.0

    # --------------------------------------------------------

    def internet_available(
        self,
    ) -> bool:

        import socket

        try:

            socket.create_connection(

                ("8.8.8.8", 53),

                timeout=1,

            )

            return True

        except OSError:

            return False

    # --------------------------------------------------------

    def get_clipboard(
        self,
    ) -> str:

        """
        Placeholder.

        Will use:
            pyperclip
        """

        return ""