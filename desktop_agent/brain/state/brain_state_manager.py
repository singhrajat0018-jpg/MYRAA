"""
MYRAA Brain State Manager

Owns and updates the live BrainState.
"""

from __future__ import annotations

from .brain_state import (

    BrainState,

    CognitiveState,

)


class BrainStateManager:

    """
    Central coordinator for BrainState.

    Every subsystem updates the state
    through this manager.
    """

    def __init__(self):

        self.state = BrainState()

    # =====================================================

    def snapshot(self):

        return self.state.snapshot()

    # =====================================================

    def transition(

        self,

        state: CognitiveState,

    ):

        self.state.transition(state)

    # =====================================================

    def update_goal(

        self,

        goal,

    ):

        self.state.update(

            goal=goal,

        )

    # =====================================================

    def update_task(

        self,

        task,

    ):

        self.state.update(

            task=task,

        )

    # =====================================================

    def update_plan(

        self,

        plan,

    ):

        self.state.update(

            plan=plan,

        )

    # =====================================================

    def update_observation(

        self,

        observation,

    ):

        self.state.update(

            active_window=observation.active_window,

            running_apps=observation.running_apps,

            battery_percent=observation.battery_percent,

            battery_plugged=observation.battery_plugged,

            internet_available=observation.internet_available,

            idle_seconds=observation.idle_seconds,

        )

    # =====================================================

    def update_attention(

        self,

        target,

        score=1.0,

    ):

        self.state.update(

            attention_target=target,

            focus_score=score,

        )

    # =====================================================

    def update_thinking(

        self,

        confidence,

        uncertainty,

    ):

        self.state.update(

            confidence=confidence,

            uncertainty=uncertainty,

        )

    # =====================================================

    def add_background_task(

        self,

        task,

    ):

        snapshot = self.state.snapshot()

        tasks = list(

            snapshot.background_tasks

        )

        if task not in tasks:

            tasks.append(task)

            self.state.update(

                background_tasks=tasks,

            )

    # =====================================================

    def remove_background_task(

        self,

        task,

    ):

        snapshot = self.state.snapshot()

        tasks = [

            t

            for t in snapshot.background_tasks

            if t != task

        ]

        self.state.update(

            background_tasks=tasks,

        )