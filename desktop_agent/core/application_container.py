"""
MYRAA Application Container

Single composition root for the entire application.

Creates every long-lived singleton exactly once.
"""

from __future__ import annotations

from desktop_agent.brain.blackboard.blackboard import Blackboard
from desktop_agent.brain.decision.decision_engine import DecisionEngine
from desktop_agent.brain.execution_brain import ExecutionBrain
from desktop_agent.brain.planner.planner import Planner

from desktop_agent.brain.planner.execution.bootstrap import (
    ExecutionBootstrap,
)

from desktop_agent.brain.planner.execution.dispatcher import (
    Dispatcher,
)

from desktop_agent.brain.orchestrator.orchestrator import (
    Orchestrator,
)

from desktop_agent.brain.brain_engine import (
    BrainEngine,
)

from desktop_agent.desktop.vision.vision_manager import (
    VisionManager,
)

from desktop_agent.runtime.runtime_manager import (
    RuntimeManager,
)


class ApplicationContainer:

    def __init__(self, dispatcher=None):

        self._external_dispatcher = dispatcher

        self._build()

    # --------------------------------------------------

    def _build(self):

        self.blackboard = Blackboard()

        from desktop_agent.brain.context_manager import ContextManager

        self.context_manager = ContextManager()

        self.planner = Planner(
            blackboard=self.blackboard,
        )

        self.decision = DecisionEngine()

        if self._external_dispatcher is not None:

            self.dispatcher = self._external_dispatcher

        else:

            registry = ExecutionBootstrap().build()

            self.dispatcher = Dispatcher(registry)

        self.orchestrator = Orchestrator(
            self.dispatcher,
        )

        self.brain_engine = BrainEngine(
            orchestrator=self.orchestrator,
            planner=self.planner,
            decision_engine=self.decision,
        )

        self.vision = VisionManager()

        self.runtime = RuntimeManager(
            brain=self.brain_engine,
            vision=self.vision,
        )

        #
        # Execution Brain
        #

        self.execution_brain = ExecutionBrain(

            dispatcher=self.dispatcher,

            planner=self.planner,

            orchestrator=self.orchestrator,

            decision_engine=self.decision,

            context_manager=self.context_manager,

        )