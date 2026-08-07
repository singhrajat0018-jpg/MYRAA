"""
MYRAA Cognitive Engine

Executor Bridge Integration Test
"""

from __future__ import annotations

import asyncio


from ..executor_bridge import ExecutorBridge

from ..dispatcher import Dispatcher

from ..action_registry import ActionRegistry

from ..execution_queue import ExecutionQueue

from ..dependency_resolver import DependencyResolver

from ..retry_policy import RetryPolicy

from ..verification_policy import VerificationPolicy

from ..timeout_manager import TimeoutManager

from ..rollback_manager import RollbackManager

from ..event_bus import EventBus

from ..execution_metrics import ExecutionMetrics

from ..progress_tracker import ProgressTracker

from ..execution_history import ExecutionHistory

from ..execution_plan import ExecutionPlan

from ...models.plan_step import PlanStep

from ...models.action_types import ActionType

from ....semantic.semantic_models import SemanticTask



# ==========================================================
# Dummy Desktop Action
# ==========================================================


async def open_application(
    application: str,
):

    print(
        f"[ACTION] Opening {application}"
    )


    return {

        "application": application,

        "status": "opened"

    }



# ==========================================================
# Dummy Verification
# ==========================================================


class DummyVerification:


    async def verify(
        self,
        step,
        result,
    ):

        class VerificationResult:

            verified = True

            success = True

            message = "Verified successfully"


        return VerificationResult()


# ==========================================================
# Create Executor
# ==========================================================


def create_executor():


    registry = ActionRegistry()



    registry.register(

        ActionType.OPEN_APPLICATION,

        open_application,

    )



    dispatcher = Dispatcher(
        registry
    )



    dependency_resolver = DependencyResolver()



    queue = ExecutionQueue(

        dependency_resolver

    )



    executor = ExecutorBridge(

        dispatcher=dispatcher,

        execution_queue=queue,

        dependency_resolver=dependency_resolver,

        retry_policy=RetryPolicy(),

        verification_policy=DummyVerification(),

        timeout_manager=TimeoutManager(),

        rollback_manager=RollbackManager(),

        event_bus=EventBus(),

        metrics=ExecutionMetrics(),

        progress_tracker=ProgressTracker(),

        history=ExecutionHistory(),

    )


    return executor



# ==========================================================
# Test
# ==========================================================


async def test_executor_bridge():


    print(
        "\n=============================="
    )

    print(
        " MYRAA EXECUTOR BRIDGE TEST "
    )

    print(
        "==============================\n"
    )



    executor = create_executor()



    task = SemanticTask(

        raw_text="open notepad",

        goal="open notepad"

    )



    plan = ExecutionPlan(

        task=task

    )



    plan.add_step(

        PlanStep(

            id=1,

            name="Open Notepad",

            action=ActionType.OPEN_APPLICATION,

            parameters={

                "application":
                    "notepad"

            },

        )

    )

    plan.add_step(

        PlanStep(

            id=2,

            name="Type Hello MYRAA",

            action=ActionType.TYPE_TEXT,

            parameters={

                "text":
                    "Hello MYRAA"

            },

        )

    )

    result = await executor.execute_plan(

        plan

    )



    print(
        "\n------------------------------"
    )

    print(
        "RESULT"
    )

    print(
        result
    )

    print(
        "------------------------------"
    )



    assert result.success is True

    assert result.completed_steps == 2



    print(
        "\nTEST PASSED ✅"
    )



# ==========================================================
# Runner
# ==========================================================


if __name__ == "__main__":


    asyncio.run(

        test_executor_bridge()

    )


   