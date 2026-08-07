from desktop_agent.core.application_container import (
    ApplicationContainer,
)

container = ApplicationContainer()

print("Blackboard :", id(container.blackboard))
print("Planner    :", id(container.planner))
print("Brain      :", id(container.brain_engine))
print("Runtime    :", id(container.runtime))

print("\nApplicationContainer OK")