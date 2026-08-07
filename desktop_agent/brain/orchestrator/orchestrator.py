"""
MYRAA Cognitive Engine
Production Orchestrator V2

A modular, event-driven execution engine designed for high-throughput
parallel task execution, transactional rollback, and resilient retry policies.
"""

from __future__ import annotations

import logging
import random

import threading
import time
from desktop_agent.brain.executive.execution_report import (
    ExecutionReport,
    StepReport,
)
from desktop_agent.brain.executive.execution_monitor import ExecutionMonitor
from desktop_agent.brain.executive.execution_coordinator import (
    ExecutionCoordinator,
)
from desktop_agent.brain.executive.execution_verifier import ExecutionVerifier
from desktop_agent.brain.executive.retry_manager import RetryManager
from desktop_agent.brain.executive.recovery_manager import RecoveryManager
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from queue import PriorityQueue, Empty
from typing import Any, Callable, Dict, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desktop_agent.main import ExecuteRequest, ExecuteResponse

from ..planner.execution.execution_plan import ExecutionPlan
from ..planner.models.plan_step import PlanStep, StepStatus
from ..planner.models.action_types import ActionType
from ..runtime.action_mapper import ACTION_TO_TOOL

from .execution_context import ExecutionContext
from .execution_result import ExecutionResult
from .execution_state import ExecutionState
from .dependency_resolver import DependencyResolver
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


# ==========================================================
# Core Data Structures
# ==========================================================

@dataclass(order=True)
class ScheduledTask:
    """Wrapper for PlanStep to be used in a PriorityQueue."""
    priority: int
    step: PlanStep = field(compare=False)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior with exponential backoff."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """Calculate the delay for the given attempt number (1-indexed)."""
        delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        if self.jitter:
            delay = random.uniform(0, delay)
        return delay


# ==========================================================
# Infrastructure Services
# ==========================================================

class EventBus:
    """Thread-safe event publisher for orchestrator lifecycle events."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event: str, callback: Callable) -> None:
        """Register a callback for a specific event."""
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)

    def emit(self, event: str, **kwargs: Any) -> None:
        """Emit an event to all registered callbacks."""
        with self._lock:
            callbacks = list(self._listeners.get(event, []))
        
        for callback in callbacks:
            try:
                callback(**kwargs)
            except Exception:
                logger.exception("Event callback failed for event '%s'.", event)


class MetricsAggregator:
    """Thread-safe collector of runtime metrics."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {
            "dispatcher_calls": 0,
            "retries": 0,
            "timeouts": 0,
            "rollbacks": 0,
            "completed_steps": 0,
            "failed_steps": 0,
        }
        self._lock = threading.Lock()

    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a metric counter."""
        with self._lock:
            if metric in self._counters:
                self._counters[metric] += value
            else:
                self._counters[metric] = value

    def snapshot(self) -> Dict[str, int]:
        """Return a snapshot of current metrics."""
        with self._lock:
            return dict(self._counters)


class RollbackEngine:
    """Manages a transactional LIFO stack of completed steps for rollback."""

    def __init__(self, dispatcher: Any, event_bus: EventBus, metrics: MetricsAggregator) -> None:
        self._dispatcher = dispatcher
        self._event_bus = event_bus
        self._metrics = metrics
        self._stack: List[PlanStep] = []
        self._lock = threading.Lock()

    def push(self, step: PlanStep) -> None:
        """Push a successfully completed step onto the rollback stack."""
        if not getattr(step, "rollback_action", None):
            return
        with self._lock:
            self._stack.append(step)

    def rollback_all(self) -> None:
        """Execute rollback actions in reverse order (LIFO)."""
        with self._lock:
            steps_to_rollback = list(reversed(self._stack))
            self._stack.clear()

        for step in steps_to_rollback:
            self._execute_rollback(step)

    def _execute_rollback(self, step: PlanStep) -> None:
        from desktop_agent.main import ExecuteRequest
        """Execute the rollback action for a single step."""
        self._metrics.increment("rollbacks")
        self._event_bus.emit("on_rollback", step=step)
        logger.info("Rolling back step %s", step.id)

        try:
            rollback_params = getattr(step, "rollback_parameters", {}) or {}
            request = ExecuteRequest(
                tool=step.rollback_action,
                args=rollback_params,
            )
            self._dispatcher.dispatch(request)
        except Exception:
            logger.exception("Rollback failed for step %s. Continuing.", step.id)


# ==========================================================
# Execution Engines
# ==========================================================

class RetryEngine:
    """Handles retry logic, backoff, and cancellation-aware sleeping."""

    def __init__(self, policy: RetryPolicy, cancel_event: threading.Event) -> None:
        self._policy = policy
        self._cancel_event = cancel_event

    def execute_with_retry(
        self,
        step: PlanStep,
        dispatch_fn: Callable[[PlanStep], ExecuteResponse],
        event_bus: EventBus,
        metrics: MetricsAggregator,
    ) -> ExecuteResponse:
        from desktop_agent.main import ExecuteResponse
        """Execute a dispatch function, applying retry logic on failure."""
        attempt = 0
        response = ExecuteResponse(ok=False, tool=step.action, error="No execution attempted.")

        while attempt <= self._policy.max_retries:
            if self._cancel_event.is_set():
                return ExecuteResponse(ok=False, tool=step.action, error="Cancelled before dispatch.")

            response = dispatch_fn(step)

            if response.ok:
                return response

            if attempt == self._policy.max_retries:
                logger.error("Step %s failed permanently after %s attempts.", step.id, attempt)
                break

            attempt += 1
            delay = self._policy.calculate_delay(attempt)
            
            metrics.increment("retries")
            event_bus.emit(
                "on_retry",
                step=step,
                retry=attempt,
                max_retries=self._policy.max_retries,
                delay=delay,
                response=response,
            )
            
            logger.warning(
                "Retry %s/%s for step %s in %.2fs",
                attempt, self._policy.max_retries, step.id, delay
            )
            
            # Cancellation-aware sleep
            if self._cancel_event.wait(delay):
                return ExecuteResponse(ok=False, tool=step.action, error="Cancelled during retry delay.")

        return response


class TimeoutEngine:
    """Wraps dispatch calls with timeout protection."""

    def __init__(self, executor: ThreadPoolExecutor, cancel_event: threading.Event) -> None:
        self._executor = executor
        self._cancel_event = cancel_event

    def execute_with_timeout(
        self,
        step: PlanStep,
        dispatch_fn: Callable[[PlanStep], ExecuteResponse],
        event_bus: EventBus,
        metrics: MetricsAggregator,
    ) -> ExecuteResponse:
        from desktop_agent.main import ExecuteResponse
        """Execute a dispatch function, enforcing a timeout."""
        if step.timeout <= 0:
            return dispatch_fn(step)

        future = self._executor.submit(dispatch_fn, step)
        try:
            return future.result(timeout=step.timeout)
        except TimeoutError:
            future.cancel()
            metrics.increment("timeouts")
            event_bus.emit("on_timeout", step=step, timeout=step.timeout)
            logger.error("Step %s timed out after %.2fs", step.id, step.timeout)
            return ExecuteResponse(
                ok=False,
                tool=step.action,
                error=f"Timed out after {step.timeout} seconds.",
            )
        except Exception as exc:
            logger.exception("TimeoutEngine wrapper failed for step %s.", step.id)
            return ExecuteResponse(ok=False, tool=step.action, error=str(exc))


class ExecutionScheduler:
    """Manages the ready queue and resolves dependencies."""

    def __init__(
        self,
        plan: ExecutionPlan,
        dependency_resolver: DependencyResolver,
        progress_tracker: ProgressTracker,
    ) -> None:
        self._plan = plan
        self._resolver = dependency_resolver
        self._tracker = progress_tracker
        self._queue: PriorityQueue[ScheduledTask] = PriorityQueue()
        self._condition = threading.Condition()
        self._running_steps = 0
        self._is_closed = False

    def initialize(self) -> None:
        """Evaluate the initial plan and enqueue ready steps."""
        with self._condition:
            for step in self._plan.steps:
                if self._is_step_ready(step):
                    self._enqueue_step(step)
            self._condition.notify_all()

    def _is_step_ready(self, step: PlanStep) -> bool:
        """Check if a step is pending and its dependencies are met."""
        if step.status != StepStatus.PENDING:
            return False
        return self._resolver.can_execute(step, self._plan)

    def _enqueue_step(self, step: PlanStep) -> None:
        """Add a step to the priority queue."""
        # Default priority to 100 if not specified
        priority = getattr(step, "priority", 100)
        self._queue.put(ScheduledTask(priority=priority, step=step))

    def get_next_step(self, timeout: Optional[float] = None) -> Optional[PlanStep]:
        """
        Get the next ready step. Blocks if queue is empty but steps are running.
        Returns None if no more steps can be executed (deadlock or completion).
        """
        with self._condition:
            while True:
                if self._is_closed:
                    return None
                    
                try:
                    # Use a short timeout to allow re-evaluation if needed
                    task = self._queue.get(timeout=0.1)
                    self._running_steps += 1
                    return task.step
                except Empty:
                    # Queue is empty. Are we done, or just waiting for deps?
                    if self._running_steps == 0:
                        # No running steps and queue empty -> Execution finished or deadlocked
                        return None
                    
                    # Wait for a running step to finish and unblock new ones
                    if not self._condition.wait(timeout=timeout):
                        # Timed out waiting
                        return None

    def notify_step_completion(self, step: PlanStep) -> None:
        """Signal that a step has finished and re-evaluate pending steps."""
        with self._condition:
            self._running_steps -= 1
            
            # If failed, we might close the scheduler to prevent new executions
            if step.status == StepStatus.FAILED:
                self._is_closed = True
                self._condition.notify_all()
                return

            # Re-evaluate pending steps to see if they are now ready
            for pending_step in self._plan.steps:
                if pending_step.status == StepStatus.PENDING and self._is_step_ready(pending_step):
                    self._enqueue_step(pending_step)
            
            self._condition.notify_all()

    def has_remaining_work(self) -> bool:
        """Check if there are steps in the queue or currently running."""
        with self._condition:
            return not self._queue.empty() or self._running_steps > 0


class ExecutionWorker:

    def __init__(
        self,
        scheduler,
        dispatcher,
        retry_engine,
        timeout_engine,
        rollback_engine,
        event_bus,
        metrics,
        progress_tracker,
        pause_event,
        cancel_event,
        execution_coordinator,
        bridge=None,
    ):

        self.bridge = bridge
        self._scheduler = scheduler
        self._dispatcher = dispatcher
        self._retry_engine = retry_engine
        self._timeout_engine = timeout_engine
        self._rollback_engine = rollback_engine
        self._event_bus = event_bus
        self._metrics = metrics
        self._tracker = progress_tracker
        self._pause_event = pause_event
        self._cancel_event = cancel_event
        self.execution_coordinator = execution_coordinator
    def run(self) -> None:
        """Main worker loop."""
        while not self._cancel_event.is_set():
            # Block while paused
            if self._pause_event.is_set():
                if self._cancel_event.wait(0.1):
                    break
                continue

            step = self._scheduler.get_next_step(timeout=0.5)
            if step is None:
                if not self._scheduler.has_remaining_work():
                    break
                continue

            self._process_step(step)

    def _process_step(self, step: PlanStep) -> None:
        print("\n========== WORKER START ==========")
        print("Step:", step)
        print("Action:", step.action)
        print("Parameters:", step.parameters)
        print("==================================")
        from desktop_agent.main import ExecuteRequest, ExecuteResponse
        """Execute the full lifecycle of a single step."""
        self._event_bus.emit("before_step", step=step)
        if self.bridge:

            self.bridge.publish(

                "execution",

                "current_step",

                step,

            )
        step.start()

        # ==========================================================
        # Execution Report
        # ==========================================================

        report = self.execution_coordinator.create_report(
            task_id=str(step.id),
            task_name=step.name,
        )

        logger.debug(
            "Execution started: %s",
            report.task,
        )
        # ==========================================================
        # Execution Intelligence
        # ==========================================================

        try:
            # Define the raw dispatch logic
            def dispatch(s: PlanStep) -> ExecuteResponse:
                print(">>>> INSIDE dispatch")
                print("\n========== DISPATCH ==========")
                print("Action:", s.action)
                print("Parameters:", s.parameters)
                print("==============================")
                self._metrics.increment("dispatcher_calls")

                # -------------------------------------------------
                # Generic desktop tool execution
                # -------------------------------------------------

                if s.action == ActionType.CUSTOM:

                    print("\n========== ORCHESTRATOR ==========")
                    print(s.parameters)
                    print("=================================\n")

                    req = ExecuteRequest(
                        tool=s.parameters["tool_name"],
                        args=s.parameters.get("parameters", {}),
                    )
                    print("Calling dispatcher...")

                    response = self._dispatcher.dispatch(req)

                    print("\n========== DISPATCH RESPONSE ==========")
                    print("OK      :", response.ok)
                    print("TOOL    :", response.tool)
                    print("ERROR   :", response.error)
                    print("META    :", response.meta)
                    print("RESULT  :", response.result)
                    print("=======================================\n")

                    return response

                    
                   

                # -------------------------------------------------
                # Existing action mapping
                # -------------------------------------------------

                tool = ACTION_TO_TOOL.get(s.action)

                if tool is None:
                    raise RuntimeError(
                        f"No tool mapping for action {s.action}"
                    )

                req = ExecuteRequest(
                    tool=tool,
                    args=s.parameters,
                )

                return self._dispatcher.dispatch(req)   

            # Wrap with timeout, then wrap with retry
            def execute_dispatch(s: PlanStep) -> ExecuteResponse:
                print(">>>> INSIDE execute_dispatch")
                return self._timeout_engine.execute_with_timeout(
                    s, dispatch, self._event_bus, self._metrics
                )
            print(">>>> BEFORE RETRY ENGINE")

            response = self._retry_engine.execute_with_retry(
                step,
                execute_dispatch,
                self._event_bus,
                self._metrics,
            )

            verification = self.execution_coordinator.verify(
                tool=response.tool,
                parameters=step.parameters,
                result=response,
                report=report,
            )

                # -------------------------------------------------
                # Preserve tool output for Brain Memory
                # -------------------------------------------------

            try:

                if getattr(response, "meta", None):
                    report.metadata.update(response.meta)

                if (
                    isinstance(response.result, dict)
                    and response.result
                ):
                    report.metadata.update(response.result)

            except Exception:
                logger.exception(
                    "Failed to transfer execution metadata."
                )

            report.verified = verification.success
            if response.ok and verification.success:
                step.complete()
                report.summary = "Execution completed."

                
                self._metrics.increment("completed_steps")
                self._rollback_engine.push(step)
                self._event_bus.emit("after_step", step=step, response=response)
                if self.bridge:

                    self.bridge.publish(

                        "execution",

                        "latest",

                        report,

                    )
                self.execution_coordinator.complete(
                    report,
                    verification.message,
                )
            else:
                self.execution_coordinator.fail(
                    report,
                    report.error,
                )
                step.fail(response.error or "Unknown execution error.")
                self._metrics.increment("failed_steps")
                self._event_bus.emit("on_failure", step=step, error=response.error)
            if self.bridge:

                self.bridge.publish(

                    "execution",

                    "failure",

                    report,

                )
               

                recovered = self.execution_coordinator.recover(
                    tool_name=response.tool,
                    parameters=step.parameters,
                    report=report,
                )

                if recovered:

                    report.recovery_used = True
                    report.recovery_strategy = "default"

                    logger.info(
                        "Recovery completed."
                    )

                    logger.info(
                        "Recovery succeeded for %s",
                        response.tool,
                    )

                else:

                    logger.warning(
                        "Recovery failed for %s",
                        response.tool,
                    )

                self._cancel_event.set()

                if recovered:

                    logger.info(
                        "Recovery succeeded for %s",
                        response.tool,
                    )

                else:

                    logger.warning(
                        "Recovery failed for %s",
                        response.tool,
                    )
                self._cancel_event.set()  # Halt further execution on failure
                

        except Exception:
            import traceback
            traceback.print_exc()
            raise
        finally:

            self.execution_coordinator.finish(
                report,
            )

            self._scheduler.notify_step_completion(
                step,
            )


# ==========================================================
# Orchestrator (Facade)
# ==========================================================

class Orchestrator:
    """
    Orchestrator V2: Production execution engine facade.
    
    Coordinates the execution of an ExecutionPlan using a pool of workers,
    advanced scheduling, and transactional rollback.
    """

    def __init__(
        self,
        dispatcher,
        *,
        max_workers: int = 4,
        retry_manager: RetryManager | None = None,
        bridge=None,
    ):
        self._dispatcher = dispatcher
        self._max_workers = max_workers

        # Infrastructure
        self._event_bus = EventBus()
        self._metrics = MetricsAggregator()
        self._dependency_resolver = DependencyResolver()
        self._progress_tracker = ProgressTracker()
        self.bridge = bridge
        # Concurrency Primitives
        self._pause_event = threading.Event()
        self._cancel_event = threading.Event()
        self._state_lock = threading.Lock()
        self.execution_monitor = ExecutionMonitor()

        self.execution_verifier = ExecutionVerifier()

        self.retry_manager = (
            retry_manager
            if retry_manager is not None
            else RetryManager()
        )

        self.recovery_manager = RecoveryManager()
        self.execution_coordinator = ExecutionCoordinator(
            execution_monitor=self.execution_monitor,
            execution_verifier=self.execution_verifier,
            retry_manager=self.retry_manager,
            recovery_manager=self.recovery_manager,
            reflection_engine=None,
            working_memory=None,
        )
        
        # Context
        self._context: Optional[ExecutionContext] = None
        self._current_state: ExecutionState = ExecutionState.PENDING

    # ----------------------------------------------------------
    # Public API: Context & Configuration
    # ----------------------------------------------------------

    def create_context(self, plan: ExecutionPlan) -> ExecutionContext:
        """Initialize a new execution context."""
        self._context = ExecutionContext(plan=plan)
        return self._context

    def on(self, event: str, callback: Callable) -> None:
        """Subscribe to an orchestrator event."""
        self._event_bus.subscribe(event, callback)

    # ----------------------------------------------------------
    # Public API: Execution Control
    # ----------------------------------------------------------

    def execute(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        """Execute the current plan synchronously and return the result."""
        self._cancel_event.clear()
        self._pause_event.clear()
        
        self.create_context(plan)
    
        self._set_state(ExecutionState.RUNNING)
        self._event_bus.emit("before_plan", plan=self._context.plan)

        # Initialize engines
        rollback_engine = RollbackEngine(self._dispatcher, self._event_bus, self._metrics)
        retry_engine = RetryEngine(RetryPolicy(), self._cancel_event)
        
        # We use a dedicated executor for dispatch calls to isolate timeouts
        dispatch_executor = ThreadPoolExecutor(
            max_workers=self._max_workers * 2,
            thread_name_prefix="MYRAA-Dispatch"
        )
        timeout_engine = TimeoutEngine(dispatch_executor, self._cancel_event)

        # Initialize scheduler
        scheduler = ExecutionScheduler(
            self._context.plan,
            self._dependency_resolver,
            self._progress_tracker
        )
        scheduler.initialize()

        # Initialize and start workers
        worker_executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="MYRAA-Worker"
        )

        workers = [
                ExecutionWorker(
                    scheduler=scheduler,
                    dispatcher=self._dispatcher,
                    retry_engine=retry_engine,
                    timeout_engine=timeout_engine,
                    rollback_engine=rollback_engine,
                    event_bus=self._event_bus,
                    metrics=self._metrics,
                    progress_tracker=self._progress_tracker,
                    pause_event=self._pause_event,
                    cancel_event=self._cancel_event,
                    execution_coordinator=self.execution_coordinator,
                    bridge=self.bridge,
                )
            for _ in range(self._max_workers)
        ]

        for worker in workers:
            future = worker_executor.submit(worker.run)

            try:
                future.result()
            except Exception:
                import traceback
                traceback.print_exc()

        # Wait for workers to complete
        worker_executor.shutdown(wait=True)
        dispatch_executor.shutdown(wait=True)

        # Determine final result
        success = not self._cancel_event.is_set() and self._progress_tracker.failed_steps(self._context.plan) == 0

        if not success and self._cancel_event.is_set() and self._current_state != ExecutionState.CANCELLED:
            # If cancelled due to failure, trigger rollback
            rollback_engine.rollback_all()
            self._set_state(ExecutionState.FAILED)
        elif success:
            self._set_state(ExecutionState.COMPLETED)
        else:
            self._set_state(ExecutionState.FAILED)

        self._event_bus.emit("after_plan", plan=self._context.plan, success=success)

        error_msg = None

        if not success:
            error_msg = "Execution failed or was cancelled."

            print("\n========== EXECUTION FAILED ==========")

            print("Failed steps:",
                self._progress_tracker.failed_steps(
                    self._context.plan
                ))

            for step in self._context.plan.steps:
                print(
                    "STEP:",
                    step.name,
                    "STATUS:",
                    step.status,
                    "ERROR:",
                    step.error
                )    


        completed_steps = [
            step
            for step in self._context.plan.steps
            if step.status == StepStatus.COMPLETED
        ]

        last_action = ""
        last_tool = ""
        last_message = ""

        if completed_steps:
            last_step = completed_steps[-1]

            last_action = last_step.action
            last_tool = ACTION_TO_TOOL.get(last_step.action, "")
            last_message = "Execution completed successfully"                

        return ExecutionResult(
            success=success,
            state=self._current_state,
            completed_steps=self._progress_tracker.completed_steps(
                self._context.plan
            ),
            total_steps=len(self._context.plan.steps),
            elapsed_time=0.0,
            errors=[error_msg] if error_msg else [],

            last_action=last_action,
            last_tool=last_tool,
            last_message=last_message,
        )           

    def pause(self) -> None:
        """Pause the orchestrator. Running steps will complete, but no new steps will start."""
        self._pause_event.set()
        self._set_state(ExecutionState.PAUSED)
        self._event_bus.emit("on_pause")
        logger.info("Orchestrator paused.")

    def resume(self) -> None:
        """Resume the orchestrator if paused."""
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._set_state(ExecutionState.RUNNING)
            self._event_bus.emit("on_resume")
            logger.info("Orchestrator resumed.")

    def cancel(self) -> None:
        """Request a graceful cancellation of the orchestrator."""
        self._cancel_event.set()
        self._set_state(ExecutionState.CANCELLED)
        self._event_bus.emit("on_cancel")
        logger.info("Orchestrator cancellation requested.")


    def reset(
        self,
        plan: ExecutionPlan,
    ) -> None:

        self._context = ExecutionContext(
            plan=plan
        )

        self._cancel_event.clear()
        self._pause_event.clear()

        self._set_state(
            ExecutionState.PENDING
        )

    def statistics(
        self,
        plan: ExecutionPlan,
    ) -> Dict[str, Any]:

        return self.get_execution_statistics()


    def report(
        self,
        plan: ExecutionPlan,
    ) -> Dict[str, Any]:

        return {
            "state": self.state.name,
            "metrics": self.get_metrics(),
            "progress": self.get_progress(),
            "statistics": self.get_execution_statistics(),
        }

    # ----------------------------------------------------------
    # Public API: Diagnostics
    # ----------------------------------------------------------

    @property
    def state(self) -> ExecutionState:
        """Return the current execution state."""
        with self._state_lock:
            return self._current_state

    @property
    def is_running(self) -> bool:
        return self.state == ExecutionState.RUNNING

    @property
    def is_paused(self) -> bool:
        return self.state == ExecutionState.PAUSED

    @property
    def is_cancelled(self) -> bool:
        return self.state == ExecutionState.CANCELLED

    def get_metrics(self) -> Dict[str, int]:
        """Return a snapshot of current runtime metrics."""
        return self._metrics.snapshot()

    def get_progress(self) -> float:
        """Return completion percentage (0.0 to 1.0)."""
        if not self._context:
            return 0.0
        return self._progress_tracker.progress(self._context.plan)

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Return detailed execution statistics."""
        if not self._context:
            return {}
        
        plan = self._context.plan
        return {
            "total_steps": len(plan.steps),
            "completed_steps": self._progress_tracker.completed_steps(plan),
            "failed_steps": self._progress_tracker.failed_steps(plan),
            "remaining_steps": self._progress_tracker.remaining_steps(plan),
            "metrics": self.get_metrics(),
            "state": self.state.name,
        }

    # ----------------------------------------------------------
    # Internal Helpers
    # ----------------------------------------------------------

    def _set_state(self, state: ExecutionState) -> None:
        """Thread-safe state update."""
        with self._state_lock:
            self._current_state = state
            if self._context:
                self._context.state = state