"""
MYRAA Cognitive Engine
Execution Brain

Coordinates the complete execution pipeline.

Request
    ↓
ContextManager
    ↓
SafetyManager
    ↓
DecisionEngine
    ↓
Planner
    ↓
Orchestrator
    ↓
CommandDispatcher
"""

from __future__ import annotations
from .planner.execution.execution_feedback import ExecutionFeedback
import logging
import time
from dataclasses import asdict
from typing import Any
from .runtime.retry_policy import RetryManager
from .context_manager import ContextManager
from .decision.decision_engine import DecisionEngine
from .planner.planner import Planner
from .orchestrator import Orchestrator
from .safety_manager import SafetyManager
from .verification import VerificationManager
from desktop_agent.brain.semantic.semantic_models import (
    SemanticTask,
    Intent,
)
from desktop_agent.brain.semantic.semantic_models import Intent

from .models import (
    BrainContext,
    BrainResult,
)

from .planner.execution.execution_plan import ExecutionPlan
from .decision.decision_result import DecisionResult


logger = logging.getLogger(__name__)


class ExecutionBrain:
    """
    MYRAA Execution Brain

    Responsible for executing every request received by
    the Desktop Agent.

    Pipeline

    Request
        ↓
    Context
        ↓
    Safety
        ↓
    Decision
        ↓
    Planner
        ↓
    Orchestrator
        ↓
    Dispatcher
    """

    # ---------------------------------------------------------
    # Complex tools
    # ---------------------------------------------------------

    COMPLEX_TOOLS = {

        # Coding

        "writeCodeFile",
        "editCodeFile",
        "createProject",
        "runPythonScript",

        # Browser

        "desktopBrowserSearch",
        "desktopBrowserFillForm",
        "desktopBrowserNavigate",

        # Desktop

        "desktopAutomation",
        "multiToolTask",

    }

    # ---------------------------------------------------------

    def __init__(
        self,
        dispatcher,
        *,
        context_manager: ContextManager | None = None,
        safety: SafetyManager | None = None,
        verification: VerificationManager | None = None,
        decision_engine: DecisionEngine | None = None,
        planner: Planner | None = None,
        orchestrator: Orchestrator | None = None,
        retry_manager: RetryManager | None = None,
        bridge=None,
    ) -> None:

        self.dispatcher = dispatcher
        self.context_manager = (
            context_manager
            if context_manager is not None
            else ContextManager()
        )

        self.safety = (
            safety
            if safety is not None
            else SafetyManager()
        )

        self.verification = (
            verification
            if verification is not None
            else VerificationManager()
        )

        # ==========================================================
        # Cognitive Modules
        # ==========================================================

        self.decision_engine = (
            decision_engine
            if decision_engine is not None
            else DecisionEngine()
        )

        self.planner = (
            planner
            if planner is not None
            else Planner()
        )

        # ==========================================================
        # Shared Managers
        # ==========================================================

        self.retry_manager = (
            retry_manager
            if retry_manager is not None
            else RetryManager()
        )

        # ==========================================================
        # Orchestrator
        # ==========================================================

        self.orchestrator = (
            orchestrator
            if orchestrator is not None
            else Orchestrator(
                dispatcher=dispatcher,
                retry_manager=self.retry_manager,
                bridge=bridge,
            )
        )

        # Runtime

        self.total_requests = 0

        self.successful_requests = 0

        self.failed_requests = 0

        self.started_at = time.perf_counter()

        logger.info(
            "ExecutionBrain initialized."
        )

    # =========================================================
    # Properties
    # =========================================================

    @property
    def uptime(self) -> float:

        return (
            time.perf_counter()
            - self.started_at
        )

    # ---------------------------------------------------------

    @property
    def success_rate(self) -> float:

        if self.total_requests == 0:

            return 100.0

        return (
            self.successful_requests
            / self.total_requests
        ) * 100.0

    # ---------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:

        return {

            "requests": self.total_requests,

            "successful": self.successful_requests,

            "failed": self.failed_requests,

            "success_rate": self.success_rate,

            "uptime": self.uptime,

        }

    # =========================================================
    # Runtime Helpers
    # =========================================================

    def _increment_success(self):

        self.total_requests += 1

        self.successful_requests += 1

    # ---------------------------------------------------------

    def _increment_failure(self):

        self.total_requests += 1

        self.failed_requests += 1

    # ---------------------------------------------------------

    def reset_statistics(self):

        self.total_requests = 0

        self.successful_requests = 0

        self.failed_requests = 0

        self.started_at = time.perf_counter()

    # ---------------------------------------------------------

    def _is_complex(
        self,
        tool: str,
    ) -> bool:

        return tool in self.COMPLEX_TOOLS

    # ---------------------------------------------------------

    def _log_request(
        self,
        tool: str,
        args: dict,
    ):

        logger.info(
            "Execution Request | Tool=%s Args=%s",
            tool,
            args,
        )

    # ---------------------------------------------------------

    def _log_result(
        self,
        success: bool,
        elapsed: float,
        result=None,
    ):

        logger.info(
            "Execution Finished | Success=%s Time=%.2f ms",
            success,
            elapsed * 1000,
        )

        retry = self.retry_manager.evaluate(
            success=success,
            attempt=1,
            error=None if success else getattr(result, "message", "Unknown error"),
        )

        logger.debug(
            "Retry Decision | retry=%s reason=%s",
            retry.retry,
            retry.reason,
        )
    # =========================================================
    # Context Pipeline
    # =========================================================

    def _build_context(
        self,
        request,
    ) -> BrainContext:
        """
        Create the execution context for the current request.
        """

        context = BrainContext()

        context.metadata["tool"] = request.tool
        context.metadata["args"] = request.args

        try:

            enriched = self.context_manager.build(
                request.tool,
                request.args,
            )

            if enriched is not None:
                context = enriched

        except Exception as exc:

            logger.warning(
                "ContextManager failed: %s",
                exc,
            )

        return context

    # ---------------------------------------------------------

    def _run_safety(
        self,
        request,
    ) -> None:
        """
        Execute all safety checks before planning.
        """

        self.safety.check(
            request.tool,
            request.args,
        )

    # =========================================================
    # Decision Pipeline
    # =========================================================

    def _build_decision_prompt(
        self,
        request,
    ) -> str:
        """
        Convert the tool request into natural language for the
        Decision Engine.
        """

        prompt = (
            request.args.get("prompt")
            or request.args.get("query")
            or request.args.get("text")
            or ""
        )

        if prompt:

            return prompt

        return (
            f"{request.tool} "
            f"{request.args}"
        )

    # ---------------------------------------------------------

    def _make_decision(
        self,
        request,
        context: BrainContext,
    ) -> DecisionResult:
        """
        Run the Decision Engine using SemanticTask.
        """

        logger.info(
            "DecisionEngine: tool=%s",
            request.tool,
        )

        task = SemanticTask()

        task.raw_text = request.tool

        task.normalized_text = request.tool.lower()

        task.intent = Intent.ROUTER_ACTION

        task.confidence = 1.0

        task.metadata = {

            "action": request.tool,

            "parameters": request.args,

        }

        return self.decision_engine.decide(

            task=task,

            brain_context=context,

        )
    # =========================================================
    # Planner Pipeline
    # =========================================================

    def _build_plan(
        self,
        decision: DecisionResult,
    ) -> ExecutionPlan:
        """
        Create an execution plan.
        """

        logger.info(
            "Planner.build_plan()"
        )

        plan = self.planner.create_plan(
            decision,
        )

        return plan

    # ---------------------------------------------------------

    def _optimize_plan(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionPlan:
        """
        Optimize the execution plan.
        """

        logger.info(
            "Planner.optimize()"
        )

        return self.planner.optimize(
            plan,
        )

    # ---------------------------------------------------------

    def _validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> bool:
        """
        Validate the generated plan.
        """

        if plan.is_empty:

            logger.warning(
                "Planner produced an empty plan."
            )

            return False

        valid = self.planner.validate(
            plan,
        )

        if not valid:

            logger.error(
                "Planner validation failed."
            )

        return valid

    # =========================================================
    # Verification Pipeline
    # =========================================================

    def _verify(
        self,
        result,
    ) -> None:
        """
        Verify execution results.
        """

        try:

            self.verification.verify(
                result,
            )

        except Exception as exc:

            logger.warning(
                "Verification failed: %s",
                exc,
            )

    # =========================================================
    # Plan Helpers
    # =========================================================

    def _prepare_plan(
        self,
        request,
        context: BrainContext,
    ) -> ExecutionPlan:
        """
        Complete cognitive planning pipeline.

        Request
            ↓
        Decision
            ↓
        Planner
            ↓
        Optimizer
            ↓
        Validator
        """

        decision = self._make_decision(
            request,
            context,
        )

        plan = self._build_plan(
            decision,
        )

        plan = self._optimize_plan(
            plan,
        )

        if not self._validate_plan(
            plan,
        ):

            raise RuntimeError(
                "Planner validation failed."
            )

        return plan

    # =========================================================
    # Dispatcher Pipeline
    # =========================================================

    def _execute_direct(
        self,
        request,
    ):
        """
        Execute a simple tool directly through the dispatcher.
        """

        logger.info(
            "Direct execution: %s",
            request.tool,
        )

        result = self.dispatcher.dispatch(
            request,
        )

        self._verify(
            result,
        )

        return result

    # ---------------------------------------------------------

    def _execute_plan(
        self,
        plan: ExecutionPlan,
    ):
        """
        Execute a generated execution plan.
        """

        logger.info(
            "Executing plan with %d steps.",
            len(plan.steps),
        )

        result = self.orchestrator.execute(
            plan,
        )

        self._verify(
            result,
        )

        return result

    # =========================================================
    # Execution Pipeline
    # =========================================================

    def _execute_complex(
        self,
        request,
        context: BrainContext,
    ):
        """
        Complete cognitive execution.

        Context
            ↓
        Decision
            ↓
        Planner
            ↓
        Orchestrator
        """

        plan = self._prepare_plan(
            request,
            context,
        )

        return self._execute_plan(
            plan,
        )

    # ---------------------------------------------------------

    def _execute_request(
        self,
        request,
        context: BrainContext,
    ):
        """
        Route the request to the correct execution path.
        """

        decision = self._make_decision(
            request,
            context,
        )

        plan = self._build_plan(
            decision,
        )

        return self._execute_plan(
            plan,
        )

    # =========================================================
    # Metrics
    # =========================================================

    def _record_success(self):

        self._increment_success()

    # ---------------------------------------------------------

    def _record_failure(self):

        self._increment_failure()

    # =========================================================
    # Error Handling
    # =========================================================

    def _handle_error(
        self,
        exc: Exception,
    ):
        """
        Convert unexpected exceptions into a BrainResult.
        """

        logger.exception(
            "Execution failed."
        )

        self._record_failure()

        return BrainResult(
            success=False,
            message=str(exc),
            actions=[],
            metadata={
                "exception": exc.__class__.__name__,
            },
        )

    def _build_feedback(
        self,
        result,
        elapsed: float,
    ) -> ExecutionFeedback:

        success = getattr(
            result,
            "success",
            getattr(result, "ok", False),
        )

        message = getattr(
            result,
            "message",
            "",
        )

        return ExecutionFeedback(
            success=success,
            tool="execution",
            message=message,
            duration_ms=elapsed * 1000,
            result=result,
        )
    # =========================================================
    # Result Helpers
    # =========================================================

    def _finalize(
        self,
        result,
        started: float,
    ):
        """
        Update metrics and log execution.
        """

        elapsed = (
            time.perf_counter()
            - started
        )

        success = getattr(
            result,
            "success",
            getattr(
                result,
                "ok",
                False,
            ),
        )

        feedback = self._build_feedback(
            result,
            elapsed,
        )

        logger.debug(
            "Execution feedback: %s",
            feedback,
        )

        if success:

            self._record_success()

        else:

            self._record_failure()

        self._log_result(
            success,
            elapsed,
            result,
        )

        return result

    # ---------------------------------------------------------

    def execute_plan(
        self,
        plan: ExecutionPlan,
    ):
        """
        Public helper for executing an already-built plan.
        """

        started = time.perf_counter()

        try:

            result = self._execute_plan(
                plan,
            )

            return self._finalize(
                result,
                started,
            )

        except Exception as exc:

            return self._handle_error(
                exc,
            )


        # =========================================================
    # Public API
    # =========================================================

    def execute(
        self,
        request,
    ):
        """
        Main execution entry point.

        Pipeline

        Request
            ↓
        Context
            ↓
        Safety
            ↓
        Direct Execution
              OR
        Decision
            ↓
        Planner
            ↓
        Orchestrator
            ↓
        Verification
            ↓
        Result
        """

        started = time.perf_counter()

        try:

            self._log_request(
                request.tool,
                request.args,
            )

            context = self._build_context(
                request,
            )

            self._run_safety(
                request,
            )

            result = self._execute_request(
                request,
                context,
            )

            return self._finalize(
                result,
                started,
            )

        except Exception as exc:

            return self._handle_error(
                exc,
            )

    # =========================================================
    # Diagnostics
    # =========================================================

    def health(self) -> dict[str, Any]:
        """
        Runtime health information.
        """

        return {

            "ready": self.ready,

            "dispatcher": (
                self.dispatcher is not None
            ),

            "planner": (
                self.planner is not None
            ),

            "decision_engine": (
                self.decision_engine is not None
            ),

            "orchestrator": (
                self.orchestrator is not None
            ),

            "context_manager": (
                self.context_manager is not None
            ),

            "verification": (
                self.verification is not None
            ),

            "safety": (
                self.safety is not None
            ),

            "stats": self.stats,

        }

    # ---------------------------------------------------------

    @property
    def ready(self) -> bool:
        """
        Returns True when all required components
        are available.
        """

        return all(

            (

                self.dispatcher,

                self.context_manager,

                self.safety,

                self.decision_engine,

                self.planner,

                self.orchestrator,

                self.verification,

            )

        )

    # ---------------------------------------------------------

    def shutdown(self) -> None:
        """
        Gracefully shut down the execution brain.
        """

        logger.info(
            "ExecutionBrain shutting down."
        )

        try:

            shutdown = getattr(
                self.orchestrator,
                "shutdown",
                None,
            )

            if callable(
                shutdown,
            ):

                shutdown()

        except Exception:

            logger.exception(
                "Failed to shut down orchestrator."
            )

    # ---------------------------------------------------------

    def reset(self) -> None:
        """
        Reset runtime statistics.
        """

        logger.info(
            "Resetting ExecutionBrain."
        )

        self.reset_statistics()

    # ---------------------------------------------------------

    def __repr__(
        self,
    ) -> str:

        return (

            f"{self.__class__.__name__}("

            f"requests={self.total_requests}, "

            f"success_rate={self.success_rate:.2f}%, "

            f"uptime={self.uptime:.2f}s"

            f")"

        )

    # ---------------------------------------------------------

    def __str__(
        self,
    ) -> str:

        return self.__repr__()