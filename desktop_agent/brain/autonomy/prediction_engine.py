"""
MYRAA Prediction Engine

Predicts future user/system events based on observations.

Responsibilities
----------------
• Predict battery drain
• Predict user activity
• Predict application usage
• Predict idle state
• Predict internet availability

No execution.

No planning.

No reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto

from .event_detector import Event
from .observation_engine import Observation


# ==========================================================
# Prediction Type
# ==========================================================

class PredictionType(Enum):

    BATTERY_LOW = auto()

    USER_RETURNING = auto()

    USER_START_CODING = auto()

    APPLICATION_LIKELY = auto()

    INTERNET_RECOVERY = auto()

    HIGH_CPU = auto()

    HIGH_MEMORY = auto()

    UNKNOWN = auto()


# ==========================================================
# Prediction
# ==========================================================

@dataclass(slots=True)
class Prediction:

    type: PredictionType

    confidence: float

    description: str

    expected_time: datetime | None = None

    metadata: dict = field(default_factory=dict)


# ==========================================================
# Prediction Engine
# ==========================================================

class PredictionEngine:

    """
    Generates predictions.

    Input

        Observation
        Events

    Output

        Predictions
    """

    def __init__(self):

        self.history: list[Observation] = []

    # ---------------------------------------------------------

    def predict(

        self,

        observation: Observation,

        events: list[Event],

    ) -> list[Prediction]:

        predictions: list[Prediction] = []

        self.history.append(observation)

        if len(self.history) > 100:

            self.history.pop(0)

        # -------------------------------------------------
        # Battery
        # -------------------------------------------------

        if (

            observation.battery_percent is not None

            and

            observation.battery_percent <= 20

            and

            not observation.battery_plugged

        ):

            predictions.append(

                Prediction(

                    type=PredictionType.BATTERY_LOW,

                    confidence=0.95,

                    description="Battery will require charging soon.",

                    expected_time=datetime.utcnow()
                    + timedelta(minutes=20),

                )

            )

        # -------------------------------------------------
        # High CPU
        # -------------------------------------------------

        if observation.cpu_percent >= 85:

            predictions.append(

                Prediction(

                    type=PredictionType.HIGH_CPU,

                    confidence=0.80,

                    description="High CPU usage may continue.",

                )

            )

        # -------------------------------------------------
        # High RAM
        # -------------------------------------------------

        if observation.ram_percent >= 85:

            predictions.append(

                Prediction(

                    type=PredictionType.HIGH_MEMORY,

                    confidence=0.80,

                    description="Memory usage likely to remain high.",

                )

            )

        # -------------------------------------------------
        # Coding Session
        # -------------------------------------------------

        apps = {

            app.lower()

            for app in observation.running_apps

        }

        if (

            "code.exe" in apps

            or "devenv.exe" in apps

            or "pycharm64.exe" in apps

        ):

            predictions.append(

                Prediction(

                    type=PredictionType.USER_START_CODING,

                    confidence=0.90,

                    description="User is likely in a coding session.",

                )

            )

        # -------------------------------------------------
        # User Idle
        # -------------------------------------------------

        if observation.idle_seconds >= 300:

            predictions.append(

                Prediction(

                    type=PredictionType.USER_RETURNING,

                    confidence=0.65,

                    description="User may return shortly.",

                    expected_time=datetime.utcnow()
                    + timedelta(minutes=5),

                )

            )

        return predictions