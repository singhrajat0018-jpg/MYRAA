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
from typing import Any, Optional
from .runtime.retry_policy import RetryManager
from .context_manager import ContextManager
from .decision.decision_engine import DecisionEngine
from .planner.planner import Planner
from .orchestrator import Orchestrator
from .safety_manager import SafetyManager
from .verification import VerificationManager
from .perception import Perception
from .planning.action_planner import ActionPlanner
from .execution.action_validator import ActionValidator, ValidationStatus
from .execution.action_verifier import ActionVerifier, VerificationStatus
from .execution.action_executor import ActionExecutor, ExecutionResult
from desktop_agent.brain.planner.execution.action_adapters.adapter_executor import AdapterExecutor
from desktop_agent.brain.planner.execution.action_adapters.adapter_factory import AdapterFactory
from desktop_agent.registry import ValidationLayer
from desktop_agent.brain.semantic.semantic_models import (
    SemanticTask,
    Intent,
)
from desktop_agent.brain.planner.models.action_types import ActionType
from desktop_agent.desktop.vision.interaction_target import InteractionTarget
from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType, InteractiveType
from desktop_agent.brain.planner.models.computer_action import ComputerAction
from desktop_agent.brain.latency_tracing import LatencyContext
from desktop_agent.brain.ai.ai_manager import AIManager
import re

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
        perception: Perception | None = None,
        action_planner: ActionPlanner | None = None,
        action_validator: ActionValidator | None = None,
        action_verifier: ActionVerifier | None = None,
        action_executor: ActionExecutor | None = None,
        bridge=None,
        blackboard=None,
        ai_manager=None,
    ) -> None:

        self.dispatcher = dispatcher
        self.blackboard = blackboard
        self.perception = perception or Perception()
        # Full Integration: one shared AI Manager authority injected from the
        # container; falls back to a private instance for standalone use.
        self.ai_manager = ai_manager
        self.context_manager = (
            context_manager
            if context_manager is not None
            else ContextManager(perception=self.perception)
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
        # EPIC-14C: World-Class Computer Action Execution
        # ==========================================================

        self.action_planner = action_planner or ActionPlanner()
        self.action_validator = action_validator or ActionValidator(self.perception, ValidationLayer())
        self.action_verifier = action_verifier or ActionVerifier(self.perception, ValidationLayer())
        self.action_executor = action_executor or ActionExecutor(
            self.perception,
            self.action_validator,
            self.action_verifier,
            Orchestrator(
                dispatcher=dispatcher,
                retry_manager=retry_manager,
                bridge=bridge,
            ),
            AdapterExecutor(AdapterFactory.create_registry()),
            blackboard=self.blackboard,
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
        # Orchestrator (kept for backward compatibility)
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
        tool: str = "",
        args: Optional[dict] = None,
    ):
        """
        Verify an execution result against the real world.

        Returns the ToolVerificationResult and attaches it to the result's
        meta when the result carries a meta mapping (e.g. ExecuteResponse),
        so the caller can see the outcome class + evidence.
        """

        try:

            # Unwrap the transport wrapper: verify the tool's payload, not
            # the ExecuteResponse envelope.
            payload = result
            if hasattr(result, "ok") and hasattr(result, "result"):
                payload = result.result

            verification = self.verification.verify(
                payload,
                tool=tool,
                args=args or {},
            )

            meta = getattr(
                result,
                "meta",
                None,
            )

            if isinstance(meta, dict):
                meta["verification"] = verification.to_dict()

            return verification

        except Exception as exc:

            logger.warning(
                "Verification failed: %s",
                exc,
            )

            return None

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
            tool=getattr(request, "tool", ""),
            args=getattr(request, "args", None),
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
        with LatencyContext("action_latency_execution_plan"):
            logger.info(
                "Executing plan with %d steps.",
                len(plan.steps),
            )

            result = self.orchestrator.execute(
                plan,
            )

            tool = (
                plan.steps[0].action
                if plan.steps
                else ""
            )

            self._verify(
                result,
                tool=tool,
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
        with LatencyContext("action_latency_execute_request"):
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

    # =========================================================
    # EPIC-14C: World-Class Computer Action Execution
    # =========================================================

    def _is_epic14c_action(self, request) -> bool:
        """
        Determine if a request should be handled by the EPIC-14C action execution pipeline.

        EPIC-14C handles requests that involve computer interaction with resolved targets,
        such as clicking, typing, etc. on specific UI elements.
        """
        # Check if request contains target information that indicates EPIC-14C usage
        args = request.args

        # Look for indicators that this is a target-based action
        target_indicators = [
            'target_id',
            'target_text',
            'interaction_target',
            'computer_action',
            'action_type'
        ]

        # Check if any target indicators are present in args
        for indicator in target_indicators:
            if indicator in args:
                return True

        # Also check if the tool itself is a computer interaction tool
        computer_interaction_tools = {
            'click', 'double_click', 'right_click', 'move_mouse',
            'type_text', 'press_key', 'hotkey', 'drag', 'scroll'
        }

        if request.tool in computer_interaction_tools:
            # But only if it has target-like parameters
            if any(param in args for param in ['x', 'y', 'coordinates', 'position']):
                return True

        return False

    def _execute_epic14c_action(self, request, context: BrainContext) -> BrainResult:
        """
        Execute a computer interaction action using the EPIC-14C pipeline.

        This method handles actions that operate on resolved interaction targets
        with validation, execution, and verification.
        """
        with LatencyContext("action_latency_epic14c_action"):
            started = time.perf_counter()

            try:
                # Convert request to ComputerAction
                action = self._request_to_computer_action(request)

                if action is None:
                    # Fall back to regular execution if we can't create a ComputerAction
                    return self._execute_request(request, context)

                # Execute the action using the EPIC-14C action executor
                execution_result = self.action_executor.execute_action(action, context)

                # Convert ExecutionResult to BrainResult
                brain_result = BrainResult(
                    success=execution_result.success,
                    message=execution_result.message,
                    actions=[{
                        'action_type': action.action_type.value,
                        'target_text': action.target.text,
                        'execution_time': execution_result.execution_time,
                        'retry_count': execution_result.retry_count,
                        'validation_passed': execution_result.validation_result.is_valid if execution_result.validation_result else False,
                        'verification_passed': execution_result.verification_result.is_success if execution_result.verification_result else False
                    }],
                    metadata={
                        'epic14c_execution': True,
                        'action_type': action.action_type.value,
                        'target_text': action.target.text,
                        'execution_time': execution_result.execution_time,
                        'retry_count': execution_result.retry_count
                    }
                )

                # Update metrics
                if execution_result.success:
                    self._record_success()
                else:
                    self._record_failure()

                return self._finalize(brain_result, started)

            except Exception as exc:
                logger.exception("EPIC-14C action execution failed")
                self._record_failure()
                return self._handle_error(exc)

    def _request_to_computer_action(self, request) -> Optional[ComputerAction]:
        """
        Convert a request to a ComputerAction for EPIC-14C processing.

        This method maps incoming requests to ComputerAction objects that
        contain the action type, target information, and parameters.
        """
        try:
            from ..planner.models.computer_action import ComputerAction
            from ..planner.models.action_types import ActionType
            from desktop_agent.desktop.vision.interaction_target import InteractionTarget
            from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType, InteractiveType

            args = request.args
            tool_name = request.tool

            # Map tool name to ActionType
            action_type_map = {
                'click': ActionType.CLICK,
                'double_click': ActionType.DOUBLE_CLICK,
                'right_click': ActionType.RIGHT_CLICK,
                'move_mouse': ActionType.MOVE_MOUSE,
                'type_text': ActionType.TYPE_TEXT,
                'press_key': ActionType.PRESS_KEY,
                'hotkey': ActionType.HOTKEY,
                'drag': ActionType.DRAG,
                'scroll_up': ActionType.SCROLL_UP,
                'scroll_down': ActionType.SCROLL_DOWN,
            }

            action_type = action_type_map.get(tool_name)
            if action_type is None:
                # Not a computer interaction action we handle
                return None

            # Extract target information
            target = None

            # Try to get target from various possible sources
            if 'target_id' in args:
                # We would need to look up the target by ID from perception
                # For now, create a basic target from available info
                pass
            elif 'target_text' in args:
                # Create target from text
                pass
            elif 'x' in args and 'y' in args:
                # Create target from coordinates
                x, y = args['x'], args['y']
                bounds = BoundingBox(x=x, y=y, width=1, height=1)  # Minimal bounds

                target = InteractionTarget(
                    id=f"coord_{x}_{y}",
                    type=UIElementType.UNKNOWN,
                    text=f"target_at_{x}_{y}",
                    confidence=1.0,
                    bounds=bounds,
                    clickable=True,
                    enabled=True,
                    visible=True,
                    interactive=True,
                    resolution_method="coordinate_based",
                    reasoning="Target specified by coordinates",
                    timestamp=time.time(),
                    valid=True
                )
            else:
                # Try to resolve target from description if we have perception
                if hasattr(self, 'perception') and self.perception:
                    description = args.get('description', args.get('target', ''))
                    if description:
                        screen_state = getattr(self.perception.state, 'screen_state', None)
                        if screen_state:
                            resolution_result = self.perception.resolve_target(description)
                            if resolution_result.status.value == "RESOLVED":
                                target = resolution_result.target

            # If we still don't have a target, create a minimal one for backward compatibility
            if target is None:
                target = InteractionTarget(
                    id=f"tool_{tool_name}_{int(time.time())}",
                    type=UIElementType.UNKNOWN,
                    text=f"target_for_{tool_name}",
                    confidence=0.8,  # Moderate confidence for fallback
                    bounds=BoundingBox(x=0, y=0, width=100, height=100),  # Default bounds
                    clickable=True,
                    enabled=True,
                    visible=True,
                    interactive=True,
                    resolution_method="fallback",
                    reasoning="Fallback target for tool execution",
                    timestamp=time.time(),
                    valid=True
                )

            # Create ComputerAction
            action = ComputerAction(
                action_type=action_type,
                target=target,
                parameters=args.copy(),
                validation_status=ValidationStatus.PENDING,
                verification_status=VerificationStatus.PENDING
            )

            return action

        except Exception as e:
            logger.error(f"Failed to convert request to ComputerAction: {e}")
            return None

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

    def _is_simple_prompt(self, request) -> bool:
        """
        Check if the request contains a simple prompt that can be fast-tracked.
        This implements EPIC-14G: Fast path for simple commands.
        """
        try:
            # Extract prompt from request args
            prompt = (
                request.args.get("prompt")
                or request.args.get("query")
                or request.args.get("text")
                or ""
            ).strip()

            if not prompt:
                return False

            # Use AIManager to determine if this is a simple command.
            # A route that can use the fast path (FAST_DETERMINISTIC /
            # FAST_MODEL execution mode) qualifies as simple.
            if self.ai_manager is None:
                from desktop_agent.brain.ai.ai_manager import AIManager
                self.ai_manager = AIManager()
            route = self.ai_manager.route(user_prompt=prompt)
            return bool(getattr(route, "can_use_fast_path", False))
        except Exception:
            # If there's any error in detection, fall back to normal processing
            return False

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
        Direct Execution (for simple tools)
              OR
        EPIC-14C Action Execution (for computer interaction with targets)
              OR
        Fast Path (for simple commands - EPIC-14G)
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
        with LatencyContext("action_latency_total_execution"):
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

                # EPIC-14G: Check for simple prompts that can be fast-tracked
                if self._is_simple_prompt(request):
                    # For simple prompts, try direct execution first if it's a simple tool
                    # Otherwise, we still go through the normal pipeline but with
                    # knowledge that it's simple (could optimize further in future)
                    if not self._is_complex(request.tool) and not self._is_epic14c_action(request):
                        result = self._execute_direct(request)
                        return self._finalize(result, started)
                    # For now, fall through to normal processing for simple prompts
                    # In a more advanced implementation, we could route simple prompts
                    # directly to appropriate lightweight handlers

                # Check if this is a simple tool that can be executed directly
                if not self._is_complex(request.tool) and not self._is_epic14c_action(request):
                    result = self._execute_direct(request)
                else:
                    # Check if this is a computer interaction action that should use EPIC-14C
                    if self._is_epic14c_action(request):
                        result = self._execute_epic14c_action(request, context)
                    else:
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