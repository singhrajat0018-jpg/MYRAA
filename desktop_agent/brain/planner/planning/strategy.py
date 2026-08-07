"""
MYRAA Cognitive Engine

Planning Strategy
"""

from __future__ import annotations

from enum import Enum



class PlanningStrategy(str, Enum):

    """
    Strategy used by planner.
    """


    DIRECT = "direct"


    SEQUENTIAL = "sequential"


    PARALLEL = "parallel"


    AUTOMATION = "automation"


    REASONING = "reasoning"


    CONFIRMATION = "confirmation"


    REJECT = "reject"



    @property
    def is_multi_step(
        self,
    ) -> bool:

        return self in (

            PlanningStrategy.SEQUENTIAL,

            PlanningStrategy.PARALLEL,

            PlanningStrategy.AUTOMATION,

        )



    @property
    def requires_reasoning(
        self,
    ) -> bool:

        return (
            self
            ==
            PlanningStrategy.REASONING
        )



    @property
    def requires_confirmation(
        self,
    ) -> bool:

        return (
            self
            ==
            PlanningStrategy.CONFIRMATION
        )