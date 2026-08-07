from desktop_agent.brain.planner.execution.bootstrap import (
    ExecutionBootstrap,
)

bootstrap = ExecutionBootstrap()

registry = bootstrap.build()

print(
    "Registered Actions:",
    registry.count(),
)

print(
    registry.available_actions(),
)