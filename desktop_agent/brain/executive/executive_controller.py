from __future__ import annotations

import logging

from .execution_request import ExecutionRequest

log = logging.getLogger(__name__)


class ExecutiveController:
    """
    Final execution gate before orchestration.

    Responsibilities:
    - validate execution
    - assign priority
    - enrich metadata
    - produce ExecutionRequest
    """

    def __init__(self, planner):

        self.planner = planner

    # --------------------------------------------------

    def submit(
        self,
        plan,
    ):

        if plan is None:

            raise RuntimeError(
                "Executive received no execution plan."
            )

        priority = getattr(
            plan,
            "priority",
            1.0,
        )

        request = ExecutionRequest(

            title=str(
                getattr(
                    plan,
                    "task",
                    "Execution",
                )
            ),

            summary=f"Execute {type(plan).__name__}",

            priority=priority,

            metadata={
                "plan": plan,
            },

        )

        log.info(

            "[Executive] Plan accepted."

        )

        return request