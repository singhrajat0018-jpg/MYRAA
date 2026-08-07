from desktop_agent.core.application_container import ApplicationContainer

container = ApplicationContainer()

print("Planner ID           :", id(container.planner))
print("Execution Planner ID :", id(container.execution_brain.planner))

print("Decision ID          :", id(container.decision))
print("Execution Decision ID:", id(container.execution_brain.decision_engine))

print("Orchestrator ID      :", id(container.orchestrator))
print("Execution Orch ID    :", id(container.execution_brain.orchestrator))

print("\nExecutionContainer OK")