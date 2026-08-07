from __future__ import annotations

import logging
from .intent_type import IntentType
log = logging.getLogger(__name__)


class CognitiveCycle:
    """
    Executes one background cognitive cycle.

    No execution.
    Only thinking.
    """

    def __init__(self, brain):

        self.brain = brain

    def run(self):
        print("[Cognitive] run()")
        log.debug("Running cognitive cycle...")

        self.review_goal()

        self.review_events()

        self.reflect()

        while True:

            item = self.brain.attention.next()

            if item is None:
                break

            self.process_attention(item)

    def review_goal(self):

        goal = self.brain.current_goal()

        if goal:

            log.debug("Active goal: %s", goal)

    def review_events(self):

        events = self.brain.working_memory.snapshot.events.recent_events

        if events:

            log.debug("Recent events: %d", len(events))

    def reflect(self):

        # Reflection integration
        pass

    def process_attention(self, item):
        print("[Attention]", item.title)
        try:

            result = self.brain.reasoning_pipeline.analyze(item)

            log.info(
                "[Reasoning] %s (confidence=%.2f)",
                result.summary,
                result.confidence,
            )

            intent = self.brain.intent_classifier.classify(result)

            self.dispatch(intent, result)

        except Exception:

            log.exception(
                "Cognitive reasoning failed."
            )

    def notify(self, result):

        key = result.summary

        if not self.brain.cognitive_state.should_notify(key):
            return

        self.brain.cognitive_state.mark_notified(key)

        log.info(
            "[Notify] %s",
            result.summary,
        )

    def plan(self, request):

        if not self.brain.cognitive_state.should_plan(
            request.title
        ):
            return

        self.brain.cognitive_state.mark_planned(
            request.title
        )

        log.info(
            "[Executive] Planning: %s",
            request.summary,
        )

        plan = self.brain.planner.create_plan(request)

        if plan is None:
            return

        result = self.brain.executor.execute(plan)

        self.brain.reflection.learn(
            plan,
            result,
        )

        log.info(
            "[Execution] success=%s steps=%d",
            result.success,
            result.completed_steps,
        )

        # Next phase:
        # plan = self.brain.planner.create_plan(request)

    def dispatch(self, intent, result):

        if intent == IntentType.REMEMBER:
            return self._remember(result)

        if intent == IntentType.NOTIFY:
            return self.notify(result)

        if intent == IntentType.PLAN:

            request = self.brain.executive.submit(result)

            return self.plan(request)

        if intent == IntentType.ACT:

            request = self.brain.executive.submit(result)

            return self.execute(request)

    def _remember(self, result):
        """
        Event already stored in memory.
        Nothing else to do.
        """
        return

    def execute(self, request):

        log.info(
            "[Execution] %s",
            request.summary,
        )

        # TODO:
        # self.brain.execution.execute(request)