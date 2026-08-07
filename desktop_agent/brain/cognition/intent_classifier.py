from __future__ import annotations

from .intent_type import IntentType


class IntentClassifier:

    """
    Converts reasoning results into
    cognitive intentions.
    """

    def classify(self, reasoning):

        if reasoning.should_plan:
            return IntentType.PLAN

        if reasoning.should_notify:
            return IntentType.NOTIFY

        return IntentType.REMEMBER