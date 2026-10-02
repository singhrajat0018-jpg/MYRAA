"""
MYRAA Autonomous Loop

Runs the continuous cognitive cycle.

Observe
↓

Detect
↓

Predict
↓

Initiative
↓

Planner
↓

Execution

↓

Reflection

↓

Learning
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from desktop_agent.brain.blackboard.blackboard import Blackboard
from .autonomy_state import AutonomyState
from .autonomy_policy import AutonomyPolicy
from .initiative_adapter import InitiativeAdapter
from .observation_engine import ObservationEngine
from .event_detector import EventDetector
from .prediction_engine import PredictionEngine
from .initiative_engine import InitiativeEngine, InitiativeType
from .initiative_manager import InitiativeManager

class AutonomyLoop:

    """
    Continuous cognitive loop.
    """

    def __init__(

        self,

        brain=None,

        planner=None,

        execution_coordinator=None,

        reflection_engine=None,

        learning_engine=None,

        fps: float = 2.0,

        blackboard: Blackboard | None = None,

        config=None,

    ) -> None:

        enabled = True

        if config is not None:

            enabled = getattr(

                config,

                "autonomous",

                True,

            )

        self.state = AutonomyState(

            enabled=enabled,

        )

        self.policy = AutonomyPolicy()

        self.observer = ObservationEngine()

        self.detector = EventDetector()

        self.predictor = PredictionEngine()

        self.initiative = InitiativeEngine()

        self.planner = planner

        self.execution = execution_coordinator

        self.reflection = reflection_engine

        self.learning = learning_engine

        self.fps = max(fps, 0.1)

        self.running = False

        self.blackboard = blackboard

        self.thread = None

        self.config = config

        self.adapter = InitiativeAdapter()

        self.initiative_manager = InitiativeManager()

        self.brain = brain
    # --------------------------------------------------------

    def start(self):

        if self.running:

            return

        self.running = True

        self.thread = threading.Thread(

            target=self._loop,

            daemon=True,

            name="MYRAA-Autonomy",

        )

        self.thread.start()

    # --------------------------------------------------------

    def stop(self):

        self.running = False

    # --------------------------------------------------------

    def pause(self):

        self.state.paused = True

    # --------------------------------------------------------

    def resume(self):

        self.state.paused = False

    # --------------------------------------------------------

    def _loop(self):

        delay = 1.0 / self.fps

        while self.running:

            start = time.perf_counter()

            self.cycle()

            elapsed = time.perf_counter() - start

            remaining = delay - elapsed

            if remaining > 0:

                time.sleep(remaining)

    # --------------------------------------------------------

    def cycle(self):

        if not self.policy.can_observe(
            self.state,
        ):
            return

        observation = self.observer.observe()

        self.blackboard.write(

            "observation",

            "latest",

            observation,

        )

        self.state.observations += 1

        events = self.detector.detect(
            observation,
        )

        self.blackboard.write(

            "events",

            "latest",

            events,

        )

        self.state.events_detected += len(events)

        if (
            self.config
            and getattr(
                self.config,
                "prediction_enabled",
                False,
            )
        ):

            predictions = self.predictor.predict(
                observation,
                events,
            )

            self.blackboard.write(

                "prediction",

                "latest",

                predictions,

            )

        else:

            predictions = []

        self.state.predictions += len(
            predictions
        )

        initiatives = self.initiative.generate(

            events,

            predictions,

        )
        self.blackboard.write(

            "initiative",

            "latest",

            initiatives,

        )
        #
        # Send initiatives into Brain
        #

        for initiative in initiatives:

            if not self.initiative_manager.allow(
                initiative,
            ):
                continue

            # Safety gate: block EXECUTE-type initiatives in autonomous mode
            # unless the policy explicitly allows execution.
            if initiative.type == InitiativeType.EXECUTE:
                if not self.policy.can_execute(self.state):
                    import logging
                    logging.getLogger(__name__).warning(
                        "[Autonomy] BLOCKED EXECUTE initiative (mode=%s): %s",
                        self.state.mode,
                        initiative.description,
                    )
                    continue

            task = self.adapter.convert(
                initiative,
            )

            if task is None:
                continue

            try:
                print("[Autonomy] Sending task to Brain")
                accepted = self.brain.autonomy_manager.submit(
                    initiative
                )

                if not accepted:
                    continue

                self.brain.set_goal(
                    initiative.description
                )
                print("[Autonomy] Brain finished")
                self.state.plans_created += 1

            except Exception as e:

                import logging
                logging.getLogger(__name__).exception("[Autonomy] Brain processing failed: %s", e)
        # ----------------------------------------------
        # Reflection
        # ----------------------------------------------

        if (

            self.reflection

            and

            self.policy.can_reflect(
                self.state,
            )

        ):

            try:

                self.reflection.reflect(

                    observation,

                    events,

                    predictions,

                )

                self.state.reflections += 1

            except Exception as e:

                import logging
                logging.getLogger(__name__).exception("[Autonomy] Reflection failed: %s", e)

        # ----------------------------------------------
        # Learning
        # ----------------------------------------------

        if (

            self.learning

            and

            self.policy.can_learn(
                self.state,
            )

        ):

            try:

                self.learning.learn(

                    observation,

                    events,

                    predictions,

                )

                self.state.learning_events += 1

            except Exception as e:

                import logging
                logging.getLogger(__name__).exception("[Autonomy] Learning failed: %s", e)

        self.state.cycles += 1

        self.state.last_cycle = datetime.utcnow()