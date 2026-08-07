"""
MYRAA Integration Test

Tests complete dependency chain.
"""

from desktop_agent.brain.planner.execution.bootstrap import (
    ExecutionBootstrap,
)

from desktop_agent.brain.planner.execution.dispatcher import (
    Dispatcher,
)

from desktop_agent.brain.orchestrator.orchestrator import (
    Orchestrator,
)

from desktop_agent.brain.planner.planner import (
    Planner,
)

from desktop_agent.brain.blackboard.blackboard import (
    Blackboard,
)

from desktop_agent.brain.brain_engine import (
    BrainEngine,
)


def main():

    print("\n========== Integration Test ==========\n")

    blackboard = Blackboard()

    planner = Planner(
        blackboard=blackboard,
    )

    print("Planner OK")

    registry = ExecutionBootstrap().build()

    print(
        "Registry:",
        registry.count(),
        "actions",
    )

    dispatcher = Dispatcher(
        registry,
    )

    print("Dispatcher OK")

    orchestrator = Orchestrator(
        dispatcher,
    )

    print("Orchestrator OK")

    brain = BrainEngine(

        orchestrator=orchestrator,

        planner=planner,

    )

    print("Brain OK")

    print("\nSUCCESS")


if __name__ == "__main__":

    main()