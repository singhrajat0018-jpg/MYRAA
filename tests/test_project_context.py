from desktop_agent.core.app_context import registry

brain = registry.get("project_brain")

ctx = brain.describe("MYRAA")

print("\n=== Project Context ===")
print(ctx)

print("\n=== Languages ===")
print(brain.languages("MYRAA"))

print("\n=== Frameworks ===")
print(brain.frameworks("MYRAA"))

print("\n=== Entry Points ===")
print(brain.entry_points("MYRAA"))