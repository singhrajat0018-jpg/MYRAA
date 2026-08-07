import logging

from .execution_context import ExecutionContext
from .execution_result import ExecutionResult
from .step_executor import StepExecutor

log = logging.getLogger(__name__)


class Executor:

    def __init__(self, tool_router):

        self.tool_router = tool_router

        self.step_executor = StepExecutor(tool_router)

    def execute(self, plan):

        context = ExecutionContext()

        plan.start()

        for index, step in enumerate(plan.steps):

            try:

                ok = self.step_executor.execute(
                    step,
                    context,
                )

            except Exception as ex:

                log.exception(
                    "Execution crashed."
                )

                plan.fail(str(ex))

                return ExecutionResult(

                    success=False,

                    plan_title=getattr(plan.task, "goal", ""),

                    completed_steps=index,

                    total_steps=plan.total_steps,

                    failed_step=index,

                    reason=str(ex),

                    execution_time=plan.execution_time,
                )

            if not ok:

                plan.fail(
                    f"Step {index} failed"
                )

                return ExecutionResult(

                    success=False,

                    plan_title=getattr(plan.task, "goal", ""),

                    completed_steps=index,

                    total_steps=plan.total_steps,

                    failed_step=index,

                    reason=plan.reason,

                    execution_time=plan.execution_time,
                )

        plan.complete()

        return ExecutionResult(

            success=True,

            plan_title=getattr(plan.task, "goal", ""),

            completed_steps=plan.total_steps,

            total_steps=plan.total_steps,

            execution_time=plan.execution_time,
        )