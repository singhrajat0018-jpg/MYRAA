from __future__ import annotations

from .models import CognitiveDecision
from .policy import CognitivePolicy
from .priority import Priority


class CognitiveEvaluator:

    """
    Decides how MYRAA should react to observer events.
    """

    def evaluate(self, event) -> CognitiveDecision:

        priority = CognitivePolicy.priority_for(event)

        decision = CognitiveDecision()

        decision.priority = priority

        decision.store_memory = True

        if priority >= Priority.HIGH:

            decision.notify_user = True

            decision.trigger_reasoning = True

        if priority >= Priority.CRITICAL:

            decision.trigger_planner = True

        return decision