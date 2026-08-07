"""
MYRAA Initiative Engine

Determines whether MYRAA should
take initiative.

This module NEVER executes actions.

It only creates initiatives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from .prediction_engine import Prediction
from .event_detector import Event


# ==========================================================
# Initiative Type
# ==========================================================

class InitiativeType(Enum):

    NOTIFY = auto()

    SUGGEST = auto()

    REMIND = auto()

    PLAN = auto()

    EXECUTE = auto()

    IGNORE = auto()


# ==========================================================
# Initiative
# ==========================================================

@dataclass(slots=True)
class Initiative:

    type: InitiativeType

    title: str

    description: str

    confidence: float

    priority: int = 5

    metadata: dict = field(default_factory=dict)


# ==========================================================
# Initiative Engine
# ==========================================================

class InitiativeEngine:

    """
    Converts Events & Predictions
    into initiatives.

    No execution.
    """

    def __init__(self):

        self.minimum_confidence = 0.70

    # ------------------------------------------------------

    def generate(

        self,

        events: list[Event],

        predictions: list[Prediction],

    ) -> list[Initiative]:

        initiatives = []

        # ----------------------------------------------
        # Events
        # ----------------------------------------------

        for event in events:

            initiatives.extend(

                self._event_to_initiative(event)

            )

        # ----------------------------------------------
        # Predictions
        # ----------------------------------------------

        for prediction in predictions:

            initiatives.extend(

                self._prediction_to_initiative(

                    prediction

                )

            )

        initiatives.sort(

            key=lambda x: (

                x.priority,

                x.confidence,

            ),

            reverse=True,

        )

        return initiatives

    # ------------------------------------------------------

    def _event_to_initiative(

        self,

        event: Event,

    ) -> list[Initiative]:

        output = []

        name = event.type.name

        if name == "BATTERY_LOW":

            output.append(

                Initiative(

                    type=InitiativeType.NOTIFY,

                    title="Battery Low",

                    description="Battery is running low.",

                    confidence=1.0,

                    priority=10,

                )

            )

        elif name == "HIGH_CPU":

            output.append(

                Initiative(

                    type=InitiativeType.SUGGEST,

                    title="High CPU Usage",

                    description="Suggest closing heavy applications.",

                    confidence=0.95,

                    priority=8,

                )

            )

        elif name == "HIGH_MEMORY":

            output.append(

                Initiative(

                    type=InitiativeType.SUGGEST,

                    title="Memory Usage",

                    description="Suggest freeing memory.",

                    confidence=0.90,

                    priority=8,

                )

            )

        return output

    # ------------------------------------------------------

    def _prediction_to_initiative(

        self,

        prediction: Prediction,

    ) -> list[Initiative]:

        output = []

        if prediction.confidence < self.minimum_confidence:

            return output

        name = prediction.type.name

        if name == "USER_START_CODING":

            output.append(

                Initiative(

                    type=InitiativeType.PLAN,

                    title="Coding Session",

                    description="Prepare coding environment.",

                    confidence=prediction.confidence,

                    priority=6,

                )

            )

        elif name == "BATTERY_LOW":

            output.append(

                Initiative(

                    type=InitiativeType.REMIND,

                    title="Charge Laptop",

                    description="Battery may run out soon.",

                    confidence=prediction.confidence,

                    priority=9,

                )

            )

        return output