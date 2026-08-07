"""
MYRAA Cognitive Engine

Executor Bridge

Central execution engine responsible for
executing ExecutionPlans.

This module coordinates:

- Dispatcher
- Execution Queue
- Retry Policy
- Verification Policy
- Timeout Manager
- Rollback Manager
- Event Bus
- Metrics
- Progress Tracking
- History

"""

from __future__ import annotations


from typing import Optional


from .dispatcher import Dispatcher

from .execution_context import ExecutionContext

from .execution_history import ExecutionHistory

from .execution_metrics import ExecutionMetrics

from .execution_plan import ExecutionPlan

from .execution_queue import ExecutionQueue

from .execution_result import ExecutionResult

from .event_bus import EventBus

from .progress_tracker import ProgressTracker

from .retry_policy import RetryPolicy

from .rollback_manager import RollbackManager

from .timeout_manager import TimeoutManager

from .verification_policy import VerificationPolicy

from .action_adapters.adapter_factory import AdapterFactory

from .action_adapters.adapter_executor import AdapterExecutor

from .dependency_resolver import DependencyResolver

from desktop_agent.desktop.filesystem.file_bridge import FileToolBridge


from .exceptions import (
    ExecutionError,
    InvalidPlanError,
)

from .exceptions import (
    ExecutionError,
    RetryExceededError,
)

from .exceptions import (
    ExecutionError,
    RetryExceededError,
    VerificationError,
)

from .exceptions import (
    ExecutionError,
    RetryExceededError,
    VerificationError,
    RollbackError,
)



# ==========================================================
# Executor Bridge
# ==========================================================


class ExecutorBridge:
    """
    MYRAA Execution Engine.

    Converts ExecutionPlans into
    real desktop operations.
    """


    # ======================================================
    # Constructor
    # ======================================================


    def __init__(

        self,

        dispatcher: Dispatcher,

        

        execution_queue: ExecutionQueue,

        dependency_resolver: DependencyResolver,

        retry_policy: RetryPolicy,

        verification_policy: VerificationPolicy,

        timeout_manager: TimeoutManager,

        rollback_manager: RollbackManager,

        event_bus: EventBus,

        metrics: ExecutionMetrics,

        progress_tracker: ProgressTracker,

        history: ExecutionHistory,

    ) -> None:


        # --------------------------------------------------
        # Core Execution Services
        # --------------------------------------------------

        self.dispatcher = dispatcher

        from desktop_agent.desktop.input.mouse_bridge import MouseToolBridge


        mouse_tools = MouseToolBridge()

        file_tools = FileToolBridge()


        self.adapter_registry = AdapterFactory.create_registry(
            mouse_tools=mouse_tools,
            file_tools=file_tools

        )

        self.adapter_executor = AdapterExecutor(
            self.adapter_registry

        )

        self.execution_queue = execution_queue


        self.dependency_resolver = dependency_resolver

        self.retry_policy = retry_policy

        self.verification_policy = verification_policy

        self.timeout_manager = timeout_manager

        self.rollback_manager = rollback_manager

        self.event_bus = event_bus

        self.metrics = metrics

        self.progress_tracker = progress_tracker

        self.history = history



        # --------------------------------------------------
        # Runtime State
        # --------------------------------------------------

        self.context = ExecutionContext()


        self.current_plan: Optional[
            ExecutionPlan
        ] = None


        self.current_step = None


        self.last_result: Optional[
            ExecutionResult
        ] = None



        # --------------------------------------------------
        # Engine Flags
        # --------------------------------------------------

        self.running = False

        self.paused = False

        self.cancelled = False

        self.shutdown_requested = False



    # ======================================================
    # State Properties
    # ======================================================


    @property
    def is_running(
        self,
    ) -> bool:

        return self.running



    @property
    def is_paused(
        self,
    ) -> bool:

        return self.paused



    @property
    def is_cancelled(
        self,
    ) -> bool:

        return self.cancelled



    @property
    def active_plan(
        self,
    ) -> Optional[ExecutionPlan]:

        return self.current_plan



    # ======================================================
    # Runtime Reset
    # ======================================================


    def reset(
        self,
    ) -> None:
        """
        Reset engine state before
        new execution.
        """


        self.context = ExecutionContext()


        self.current_plan = None


        self.current_step = None


        self.last_result = None



        self.running = False

        self.paused = False

        self.cancelled = False

        self.shutdown_requested = False



        self.execution_queue.clear()

        self.rollback_manager.clear()


    # ======================================================
    # Public Execution API
    # ======================================================


    async def execute_plan(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        """
        Main execution entry point.

        Receives an ExecutionPlan and
        starts execution lifecycle.
        """


        try:

            self.reset()


            self._validate_plan(
                plan
            )


            self.current_plan = plan


            self.running = True


            self._initialize_execution(
                plan
            )


            self.event_bus.publish(
                "execution_started",
                plan,
            )


            self.metrics.start()


            self.event_bus.publish(

                "progress_updated",

                self.progress_tracker.get_state(),

            )


            result = await self._run_execution()


            self.last_result = result

            # --------------------------------------------------
            # Save Execution History
            # --------------------------------------------------

            self._record_execution_history(
                result
)


            self.metrics.finish()


            self.event_bus.publish(

                "progress_updated",

                self.progress_tracker.get_state(),

            )


            self.event_bus.publish(

                "execution_completed",

                {

                    "result": result,

                    "metrics": self.metrics,

                },

            )

            self.event_bus.publish(

                "execution_history_saved",

                self.get_execution_summary(),

            )


            return result



        except Exception as exc:


            await self._handle_failure(
                exc
            )


            error_result = ExecutionResult(

                success=False,

                error_message=str(exc),

            )


            self.last_result = error_result

            self._record_execution_history(

                error_result

            )


            self.event_bus.publish(

                "execution_failed",

                error_result,

            )


            return error_result


        finally:


            self.running = False



    # ======================================================
    # Plan Validation
    # ======================================================


    def _validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> None:
        """
        Validate execution plan
        before running.
        """


        if plan is None:

            raise InvalidPlanError(
                "Execution plan is empty"
            )



        if plan.is_empty:

            raise InvalidPlanError(
                "Execution plan has no steps"
            )



        if self.dependency_resolver.has_cycle(
            plan
        ):

            raise InvalidPlanError(
                "Circular dependency detected"
            )



    # ======================================================
    # Execution Initialization
    # ======================================================


    def _initialize_execution(
        self,
        plan: ExecutionPlan,
    ) -> None:
        """
        Prepare runtime state.
        """


        self.context.plan = plan


        self.context.total_steps = len(
            plan.steps
        )


        self.context.current_step = 0



        self.execution_queue.load(
            plan
        )


        self.progress_tracker.reset(
            total=len(
                plan.steps
            )
        )



        self.metrics.reset()

    # ======================================================
    # Execution Runner
    # ======================================================


    async def _run_execution(
        self,
    ) -> ExecutionResult:
        """
        Main execution scheduler.

        Controls:
        - queue processing
        - dependency validation
        - step lifecycle
        """

        completed = 0

        failed = 0


        while self.execution_queue.has_next():


            # ----------------------------------------------
            # Cancellation Check
            # ----------------------------------------------

            if self.cancelled:

                break



            # ----------------------------------------------
            # Shutdown Check
            # ----------------------------------------------

            if self.shutdown_requested:

                break



            # ----------------------------------------------
            # Pause Handling
            # ----------------------------------------------

            if self.paused:

                continue



            # ----------------------------------------------
            # Get Next Step
            # ----------------------------------------------

            step = (
                self.execution_queue.next()
            )


            if step is None:

                break



            self.current_step = step


            self.context.current_step = (
                step.id
            )



            try:

                # ------------------------------------------
                # Dependency Validation
                # ------------------------------------------

                self.dependency_resolver.validate(

                    step,

                    self.current_plan,

                )



                # ------------------------------------------
                # Step Started Event
                # ------------------------------------------

                self.event_bus.publish(

                    "step_started",

                    step,

                )


                # ------------------------------------------
                # Actual Execution
                # PART-4
                # ------------------------------------------

                await self._execute_step(
                    step
                )


                completed += 1



                # ------------------------------------------
                # Mark Completed
                # ------------------------------------------

                self.execution_queue.mark_completed(
                    step
                )


                # ------------------------------------------
                # Refresh Queue
                # ------------------------------------------

                self.execution_queue.refresh(

                    self.current_plan

                )


            except Exception as exc:


                failed += 1


                self.event_bus.publish(

                    "step_failed",

                    {
                        "step": step,

                        "error": str(exc),

                    },

                )


                # Step failure handling
                # Retry system comes in PART-5


                break



        return ExecutionResult(

            success=(
                failed == 0
            ),

            verified=(
                self.last_result.verified
                if self.last_result
                else False
            ),

            completed_steps=completed,

            failed_steps=failed,

            value=(
                self.last_result.value
                if self.last_result
                else None
            ),

            metadata=(
                self.last_result.metadata
                if self.last_result
                else {}
            ),

        )
    

    # ======================================================
    # Single Step Execution
    # ======================================================


    async def _execute_step(
        self,
        step,
    ) -> ExecutionResult:
        """
        Execute one PlanStep.

        Flow:

        PlanStep
            |
            ▼
        TimeoutManager
            |
            ▼
        Dispatcher
            |
            ▼
        ExecutionResult
        """
        print(
            "RUNNING STEP:",
            step.name,
            step.action
        )

        step.start()

        self.event_bus.publish(

            "step_started",

            step,

        )


        self.current_step = step



        try:


            # --------------------------------------------------
            # Execute Dispatcher With Timeout
            # --------------------------------------------------

            result = await self._execute_with_retry(
                step
)



            self.last_result = result



            # --------------------------------------------------
            # Result Validation
            # --------------------------------------------------

            if not result.success:


                step.fail(

                    result.error_message

                    or

                    "Execution failed"

                )


                raise ExecutionError(

                    result.error_message

                    or

                    "Step execution failed"

                )



            # --------------------------------------------------
            # Verification
            # --------------------------------------------------

            verified = await self._verify_step(

                step,

                result,

            )

            result.verified = True if verified else False



            if not verified:

                step.fail(
                    "Verification failed"
                )

                raise VerificationError(

                    f"Step {step.id} verification failed"

                )



            # --------------------------------------------------
            # Step Completed
            # --------------------------------------------------

            step.complete()


            self.progress_tracker.increment()


            self.metrics.record_success(
                step,
                result,
            )


            self.event_bus.publish(

                "progress_updated",

                self.progress_tracker.get_state(),

            )


            self.event_bus.publish(

                "step_completed",

                {

                    "step": step,

                    "result": result,

                },

            )

            self.rollback_manager.register(
                step
            )



            # --------------------------------------------------
            # History
            # --------------------------------------------------

            self.history.record(

                step,

                result,

            )



            # --------------------------------------------------
            # Metrics
            # --------------------------------------------------

            self.metrics.record_success(

                step,

                result,

            )



            # --------------------------------------------------
            # Event
            # --------------------------------------------------

            self.event_bus.publish(

                "step_completed",

                {

                    "step": step,

                    "result": result,

                },

            )

            print(
                "FINAL STEP RESULT:",
                result
            )


            return result



        except Exception as exc:


            print(
                "EXECUTION STEP ERROR:",
                repr(exc)
            )


            step.fail(

                str(exc)

            )

            self.progress_tracker.update(

                self.context.current_step,

                self.context.total_steps,

            )


            self.event_bus.publish(

                "step_failed",

                {

                    "step": step,

                    "error": str(exc),

                },

            )


            self.history.record_failure(

                step,

                ExecutionResult(

                    success=False,

                    error=str(exc),

                ),

            )


            self.metrics.record_failure(

                step,

                exc,

            )


            raise



    # ======================================================
    # Verification Engine
    # ======================================================


    async def _verify_step(
        self,
        step,
        result: ExecutionResult,
    ) -> bool:
        """
        Verify executed action.

        Uses VerificationPolicy.
        """


        self.event_bus.publish(

            "verification_started",

            step,

        )


        verification = await self.verification_policy.verify(

            step,

            result,

        )


        if verification.verified:


            result.verified = True


            self.metrics.record_verification_success()


            self.event_bus.publish(

                "verification_completed",

                {

                    "step": step,

                    "verified": True,

                },

            )


            return True



        self.metrics.record_verification_failure()



        self.event_bus.publish(

            "verification_failed",

            {

                "step": step,

                "message": verification.message,

            },

        )


        return False


    # ======================================================
    # Retry Execution Engine
    # ======================================================


    async def _execute_with_retry(
        self,
        step,
    ) -> ExecutionResult:
        """
        Execute step with retry support.
        """


        last_error = None


        while True:


            try:


                # ------------------------------------------
                # Retry Attempt Event
                # ------------------------------------------

                if step.retries > 0:

                    self.event_bus.publish(

                        "retry_started",

                        {
                            "step": step,

                            "attempt": step.retries,

                        },

                    )



                # ------------------------------------------
                # Execute With Timeout
                # ------------------------------------------

                result = await self.timeout_manager.execute_step(

                    step,

                    self.adapter_executor.execute,

                    step.action,

                    step.parameters,

                )


                # ------------------------------------------
                # Success
                # ------------------------------------------

                if result.success:

                    return result



                last_error = result.error_message



            except Exception as exc:


                last_error = str(exc)



            # ----------------------------------------------
            # Retry Check
            # ----------------------------------------------

            if not self.retry_policy.should_retry(
                step
            ):


                raise RetryExceededError(

                    step.retries,

                    last_error

                    or

                    "Execution failed"

                )



            # ----------------------------------------------
            # Prepare Retry
            # ----------------------------------------------

            step.retry()



            self.metrics.record_retry(
                step
            )


            self.event_bus.publish(

                "retry_completed",

                {
                    "step": step,

                    "attempt": step.retries,

                },

            )

    # ======================================================
    # Failure Recovery
    # ======================================================


    async def _handle_failure(
        self,
        error: Exception,
    ) -> None:
        """
        Handles failed execution recovery.
        """


        self.event_bus.publish(

            "rollback_started",

            {

                "error": str(error)

            },

        )


        try:


            await self.rollback_manager.rollback(

                self.current_plan

            )



            self.metrics.record_rollback()



            self.event_bus.publish(

                "rollback_completed",

                self.current_plan,

            )



        except Exception as rollback_error:


            self.event_bus.publish(

                "rollback_failed",

                {

                    "error": str(
                        rollback_error
                    )

                },

            )


            raise RollbackError(

                str(rollback_error)

            )


    # ======================================================
    # Execution History
    # ======================================================


    def _record_execution_history(
        self,
        result: ExecutionResult,
    ) -> None:
        """
        Store final execution result.

        Used for:
        - debugging
        - analytics
        - future learning
        """


        if self.current_plan is None:

            return



        if self.current_step:

            self.history.record(

                self.current_step,

                result,

            )


    # ======================================================
    # Execution Statistics
    # ======================================================


    def get_execution_summary(
        self,
    ) -> dict:
        """
        Returns execution summary.
        """


        return {


            "running":
                self.running,


            "current_step":
                (
                    self.current_step.id

                    if self.current_step

                    else None
                ),


            "total_steps":
                (
                    len(
                        self.current_plan.steps
                    )

                    if self.current_plan

                    else 0
                ),


            "last_success":
                (
                    self.last_result.success

                    if self.last_result

                    else None
                ),


            "history_count":
                self.history.count(),


        }

    # ======================================================
    # Execution Control
    # ======================================================


    def pause(
        self,
    ) -> None:
        """
        Pause current execution.
        """


        if not self.running:

            return


        self.paused = True


        self.event_bus.publish(

            "execution_paused",

            self.current_step,

        )



    # ------------------------------------------------------


    def resume(
        self,
    ) -> None:
        """
        Resume execution.
        """


        if not self.running:

            return


        self.paused = False


        self.event_bus.publish(

            "execution_resumed",

            self.current_step,

        )



    # ------------------------------------------------------


    def cancel(
        self,
    ) -> None:
        """
        Cancel current execution.
        """


        self.cancelled = True


        self.event_bus.publish(

            "execution_cancelled",

            self.current_plan,

        )



    # ======================================================
    # Shutdown
    # ======================================================


    async def shutdown(
        self,
    ) -> None:
        """
        Graceful engine shutdown.
        """


        self.shutdown_requested = True


        self.cancelled = True



        self.execution_queue.clear()


        self.rollback_manager.clear()



        self.event_bus.publish(

            "execution_shutdown",

            None,

        )



    # ======================================================
    # Cleanup
    # ======================================================


    def cleanup(
        self,
    ) -> None:
        """
        Cleanup runtime resources.
        """


        self.current_step = None


        self.current_plan = None


        self.last_result = None


        self.running = False


        self.paused = False


        self.cancelled = False


        self.shutdown_requested = False



    # ======================================================
    # Runtime Status
    # ======================================================


    def status(
        self,
    ) -> dict:
        """
        Return current engine status.
        """


        return {


            "running":
                self.running,


            "paused":
                self.paused,


            "cancelled":
                self.cancelled,


            "current_step":
                (
                    self.current_step.id

                    if self.current_step

                    else None
                ),


            "plan_active":
                self.current_plan is not None,


            "progress":
                self.progress_tracker.percentage,


        }