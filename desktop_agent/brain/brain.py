"""
MYRAA Brain

The Brain is the central intelligence layer.

Responsibilities

User Input
    ↓
Decision Engine
    ↓
Planner
    ↓
Orchestrator
    ↓
BrainResult
"""

from __future__ import annotations

from typing import Optional
from .semantic.semantic_parser import SemanticParser
# remove RuleBased provider usage

from .decision.decision_engine import DecisionEngine
from .planner.planner import Planner
from .orchestrator.orchestrator import Orchestrator
from .models import (
    BrainContext,
    BrainResult,
)
from .decision.decision_result import DecisionResult
from .brain_engine import BrainEngine
import logging

log = logging.getLogger(__name__)

class Brain:
    def __init__(
        self,
        dispatcher,
        *,
        brain_engine=None,
        orchestrator=None,
    ):
        self.dispatcher = dispatcher

        self.orchestrator = (
            orchestrator
            if orchestrator is not None
            else Orchestrator(dispatcher)
        )

        self.brain_engine = (
            brain_engine
            if brain_engine is not None
            else BrainEngine(
                orchestrator=self.orchestrator,
            )
        )

    # ------------------------------------------------------------------
    # Legacy compatibility API
    #
    # Older modules may still call Brain.process().
    # Internally everything is delegated to Brain.run().
    # ------------------------------------------------------------------

    def process(self, text, context=None):
        """
        Legacy compatibility wrapper.

        All cognitive processing now lives inside BrainEngine.
        """
        self.complete_goal()

        self.autonomy_manager.complete()
        log.info(">>>> Brain.process() delegated")
        return self.run(text, context)
       
    # ---------------------------------------------------------
    # Decision Only
    # ---------------------------------------------------------

    def decide(self, text, context=None):
        semantic = self.brain_engine.semantic_parser.parse(
            text,
            context,
        )

        return self.brain_engine.decision.decide(
            semantic
        )

    # ---------------------------------------------------------
    # Planning Only
    # ---------------------------------------------------------

    def plan(self, decision):
        return self.brain_engine.planner.create_plan(decision)

    # ---------------------------------------------------------
    # Execute Existing Plan
    # ---------------------------------------------------------

    def execute(
        self,
        plan,
    ) -> BrainResult:

        return self.orchestrator.execute(
            plan
        )

    # ---------------------------------------------------------
    # Convenience API
    # ---------------------------------------------------------

    def ask(
        self,
        text: str,
    ) -> BrainResult:

        return self.process(text)

    # ---------------------------------------------------------
    # Reset
    # ---------------------------------------------------------
    def reset(
        self,
        plan,
    ):

        self.orchestrator.reset(plan)

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------
    def statistics(
        self,
        plan,
    ):

        return self.orchestrator.statistics(
            plan
        )

    # ---------------------------------------------------------
    # Execution Report
    # ---------------------------------------------------------

    def report(
        self,
        plan,
    ):

        return self.orchestrator.report(
            plan
        )

        # ---------------------------------------------------------
    # Before Decision Hook
    # ---------------------------------------------------------

    def before_decision(
        self,
        text: str,
    ) -> None:
        """
        Hook called before the Decision Engine.
        Override or extend if needed.
        """
        pass

    # ---------------------------------------------------------
    # After Decision Hook
    # ---------------------------------------------------------

    def after_decision(
        self,
        decision: DecisionResult,
    ) -> None:
        """
        Hook called after the Decision Engine.
        """
        pass

    # ---------------------------------------------------------
    # Before Execution Hook
    # ---------------------------------------------------------

    def before_execution(
        self,
        plan,
    ) -> None:
        """
        Hook called before executing an ExecutionPlan.
        """
        pass

    # ---------------------------------------------------------
    # After Execution Hook
    # ---------------------------------------------------------

    def after_execution(
        self,
        result: BrainResult,
    ) -> None:
        """
        Hook called after execution finishes.
        """
        pass

    # ---------------------------------------------------------
    # Enhanced Process Pipeline
    # ---------------------------------------------------------

    def run(self, text, context=None):

        log.info(">>>> Brain.run() called")
        return self.brain_engine.process(
            text=text,
            context=context,
        )

    # ---------------------------------------------------------
    # Execution History
    # ---------------------------------------------------------

    def history(self):

        if not hasattr(self, "_history"):
            self._history = []

        return self._history

    def add_history(
        self,
        text: str,
        result: BrainResult,
    ):

        self.history().append({

            "input": text,

            "success": result.success,

            "message": result.message,

            "metadata": result.metadata,

        })

    # ---------------------------------------------------------
    # Last Result
    # ---------------------------------------------------------

    def last_result(self):

        history = self.history()

        if not history:
            return None

        return history[-1]

    # ---------------------------------------------------------
    # Clear History
    # ---------------------------------------------------------

    def clear_history(self):

        self.history().clear()

    # ---------------------------------------------------------
    # Debug Mode
    # ---------------------------------------------------------

    def enable_debug(self):

        self.debug = True

    def disable_debug(self):

        self.debug = False

    def is_debug(self):

        return getattr(
            self,
            "debug",
            False,
        )

    # ---------------------------------------------------------
    # Performance Timer
    # ---------------------------------------------------------

    def timed_run(
        self,
        text: str,
        context: Optional[BrainContext] = None,
    ):

        import time

        start = time.perf_counter()

        result = self.run(
            text,
            context,
        )

        elapsed = time.perf_counter() - start

        result.metadata["execution_time"] = elapsed

        return result

        # ---------------------------------------------------------
    # Event Broadcasting
    # ---------------------------------------------------------

    def register_event_handler(
        self,
        event: str,
        callback,
    ) -> None:

        if not hasattr(self, "_event_handlers"):
            self._event_handlers = {}

        self._event_handlers.setdefault(
            event,
            [],
        ).append(callback)

    def emit(
        self,
        event: str,
        **kwargs,
    ) -> None:

        handlers = getattr(
            self,
            "_event_handlers",
            {},
        )

        for callback in handlers.get(event, []):

            try:
                callback(**kwargs)

            except Exception:
                pass

    # ---------------------------------------------------------
    # Session State
    # ---------------------------------------------------------

    def session(self):

        if not hasattr(self, "_session"):

            self._session = {}

        return self._session

    def set_state(
        self,
        key,
        value,
    ):

        self.session()[key] = value

    def get_state(
        self,
        key,
        default=None,
    ):

        return self.session().get(
            key,
            default,
        )

    def clear_state(self):

        self.session().clear()

    # ---------------------------------------------------------
    # Health Report
    # ---------------------------------------------------------

    def health(self):

        return {

            "decision_engine": self.brain_engine.decision is not None,

            "planner": self.brain_engine.planner is not None,

            "orchestrator": self.orchestrator is not None,

            "dispatcher": self.dispatcher is not None,

            "history": len(self.history()),

            "debug": self.is_debug(),

        }

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------

    def configure(
        self,
        **kwargs,
    ):

        if not hasattr(self, "_config"):

            self._config = {}

        self._config.update(kwargs)

    def config(
        self,
        key=None,
    ):

        cfg = getattr(
            self,
            "_config",
            {},
        )

        if key is None:
            return cfg

        return cfg.get(key)

    # ---------------------------------------------------------
    # Module Registry
    # ---------------------------------------------------------

    def register_module(
        self,
        name: str,
        module,
    ):

        if not hasattr(self, "_modules"):

            self._modules = {}

        self._modules[name] = module

    def module(
        self,
        name: str,
    ):

        return getattr(
            self,
            "_modules",
            {},
        ).get(name)

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    def diagnostics(self):

        return {

            "health": self.health(),

            "configuration": self.config(),

            "modules": list(

                getattr(
                    self,
                    "_modules",
                    {},
                ).keys()

            ),

            "events": list(

                getattr(
                    self,
                    "_event_handlers",
                    {},
                ).keys()

            ),

        }

    # ---------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------

    def shutdown(self):

        self.emit("shutdown")

        self.clear_state()

        self.clear_history()

    # ---------------------------------------------------------
    # Restart
    # ---------------------------------------------------------

    def restart(self):

        dispatcher = self.dispatcher

        self.shutdown()

        self.__init__(dispatcher)

    # ---------------------------------------------------------
    # Representation
    # ---------------------------------------------------------

    def __repr__(self):

        return (
            "<Brain "
            f"history={len(self.history())} "
            f"debug={self.is_debug()}>"
        )
    