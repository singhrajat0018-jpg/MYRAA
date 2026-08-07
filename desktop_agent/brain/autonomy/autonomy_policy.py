"""
MYRAA Autonomy Policy

Determines what MYRAA is allowed
to do autonomously.
"""

from __future__ import annotations

from .autonomy_state import (
    AutonomyMode,
    AutonomyState,
)


class AutonomyPolicy:

    """
    Decision policy for autonomous actions.
    """

    def can_observe(

        self,

        state: AutonomyState,

    ) -> bool:

        return state.running

    # -----------------------------------------------------

    def can_predict(

        self,

        state: AutonomyState,

    ) -> bool:

        return (

            state.running

            and

            state.mode != AutonomyMode.OFF

        )

    # -----------------------------------------------------

    def can_plan(

        self,

        state: AutonomyState,

    ) -> bool:

        return (

            state.running

            and

            state.mode in (

                AutonomyMode.ASSISTIVE,

                AutonomyMode.PROACTIVE,

                AutonomyMode.FULL,

            )

        )

    # -----------------------------------------------------

    def can_execute(

        self,

        state: AutonomyState,

    ) -> bool:

        return (

            state.running

            and

            state.mode == AutonomyMode.FULL

        )

    # -----------------------------------------------------

    def can_notify(

        self,

        state: AutonomyState,

    ) -> bool:

        return (

            state.running

            and

            state.mode in (

                AutonomyMode.PROACTIVE,

                AutonomyMode.FULL,

            )

        )

    # -----------------------------------------------------

    def can_learn(

        self,

        state: AutonomyState,

    ) -> bool:

        return state.running

    # -----------------------------------------------------

    def can_reflect(

        self,

        state: AutonomyState,

    ) -> bool:

        return state.running

    # -----------------------------------------------------

    def can_use_tools(

        self,

        state: AutonomyState,

    ) -> bool:

        return (

            state.mode == AutonomyMode.FULL

        )

    # -----------------------------------------------------

    def can_interrupt_user(

        self,

        state: AutonomyState,

    ) -> bool:

        return (

            state.mode == AutonomyMode.FULL

        )