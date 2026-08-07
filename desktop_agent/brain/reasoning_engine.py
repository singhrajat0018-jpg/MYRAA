"""
MYRAA Brain

Reasoning Engine

Responsibilities
----------------
- Combines WorldModel + User Intent + Memory.
- Determines the user's current goal.
- Selects the most appropriate reasoning strategy.
- Produces a reasoning result for the Planner.

This module never executes actions directly.
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .world_model import WorldModel


# ==========================================================
# Strategy
# ==========================================================

class ReasoningStrategy(str, Enum):

    REACTIVE = "reactive"

    CONTEXTUAL = "contextual"

    GOAL_DIRECTED = "goal_directed"

    PROACTIVE = "proactive"


# ==========================================================
# Result
# ==========================================================

@dataclass(slots=True)
class ReasoningResult:

    timestamp: float

    strategy: ReasoningStrategy

    inferred_goal: str

    confidence: float

    reasoning: list[str] = field(default_factory=list)

    context: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Engine
# ==========================================================

class ReasoningEngine:

    """
    MYRAA Cognitive Layer.

    Converts perception + world state + user intent into
    semantic reasoning for the planner.
    """

    def __init__(

        self,

        world: WorldModel,

    ):

        self.world = world

    # ------------------------------------------------------

    def reason(

        self,

        user_intent: str,

        memory: Optional[Any] = None,

    ) -> ReasoningResult:

        state = self.world.state

        env = state.environment

        activity = state.activity

        strategy = self._choose_strategy(

            user_intent,

            activity.name,

        )

        goal = self._infer_goal(

            user_intent,

            activity.name,

            env.application,

        )

        reasoning = [

            f"Intent: {user_intent}",

            f"Activity: {activity.name}",

            f"Application: {env.application}",

            f"Window: {env.window}",

        ]

        context = {

            "application": env.application,

            "window": env.window,

            "screen_type": env.screen_type,

            "dialog": env.dialog_visible,

            "primary_action": env.primary_action,

            "focused_element": env.focused_element,

            "activity": activity.name,

        }

        return ReasoningResult(

            timestamp=time.time(),

            strategy=strategy,

            inferred_goal=goal,

            confidence=activity.confidence,

            reasoning=reasoning,

            context=context,

        )

    # ------------------------------------------------------

    def _choose_strategy(

        self,

        intent: str,

        activity: str,

    ) -> ReasoningStrategy:

        if intent:

            return ReasoningStrategy.GOAL_DIRECTED

        if activity != "idle":

            return ReasoningStrategy.CONTEXTUAL

        return ReasoningStrategy.REACTIVE

    # ------------------------------------------------------

    def _infer_goal(

        self,

        intent: str,

        activity: str,

        application: Optional[str],

    ) -> str:

        if intent:

            return intent

        if activity == "coding":

            return "Assist software development"

        if activity == "browsing":

            return "Assist web browsing"

        if activity == "watching_video":

            return "Assist media consumption"

        if activity == "file_management":

            return "Assist file management"

        return "Observe user activity"

    # ------------------------------------------------------

    def explain(

        self,

        result: ReasoningResult,

    ) -> str:

        return (

            f"Strategy={result.strategy.value}, "

            f"Goal={result.inferred_goal}, "

            f"Confidence={result.confidence:.2f}"

        )