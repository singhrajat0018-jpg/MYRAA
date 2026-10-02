"""
Phase 10 — FILES / PROJECTS INTEGRATION Tests

Tests for:
- Project capability integration via PROJECT_ENGINE capability
- Project creation and folder operations
- Project listing and searching
- Project info/retrieval
- Integration with existing MYRAA cognitive architecture
- End-to-end execution of project-related requests
"""

import sys
import os
import shutil

# Add the MYRAA directory to the path so desktop_agent can be found as a package
myraa_path = os.path.join(os.path.dirname(__file__))
myraa_path = os.path.normpath(myraa_path)
sys.path.insert(0, myraa_path)

from desktop_agent.brain.ai.ai_manager import AIManager
from desktop_agent.brain.super_brain.planner import MasterPlanner
from desktop_agent.brain.super_brain.goal import Goal
from desktop_agent.brain.ai.tool_resolver import resolve as resolve_tools, is_resolvable
from desktop_agent.registry import TOOLS, set_unified_dispatcher, load_all


def test_ai_manager_project_intent_recognition():
    """Test that AI Manager correctly selects PROJECT intents for project-related requests."""
    ai_manager = AIManager()

    # Test cases for project requests
    test_cases = [
        ("create a new project", "PROJECT_CREATE"),
        ("open the project", "PROJECT_OPEN"),
        ("list all projects", "PROJECT_LIST"),
        ("find the project", "PROJECT_SEARCH"),
        ("project ki jankari do", "PROJECT_INFO"),
        ("project shuru karo", "PROJECT_CREATE"),
        ("project kholo", "PROJECT_OPEN"),
        ("projects dikhao", "PROJECT_LIST"),
        ("project dhoondo", "PROJECT_SEARCH"),
        ("search for project", "PROJECT_SEARCH"),
        ("new project banayo", "PROJECT_CREATE"),
        ("open project karo", "PROJECT_OPEN"),
        ("show me projects", "PROJECT_LIST"),
        ("project details batao", "PROJECT_INFO"),
    ]

    for prompt, expected_intent_name in test_cases:
        print(f"Testing PROJECT routing: '{prompt}'")
        route = ai_manager.route(prompt)

        print(f"  Detected intent: {route.intent.name}")
        print(f"  Detected capability: {route.capability}")

        # Verify it routes to PROJECT_ENGINE capability for PROJECT intents
        assert route.capability == 'PROJECT_ENGINE', \
            f"Expected PROJECT_ENGINE capability for PROJECT intents, got {route.capability}"

        # Verify the intent is correctly detected
        assert route.intent.name == expected_intent_name, \
            f"Expected {expected_intent_name} intent, got {route.intent.name}"

    print("  PASS: AI Manager PROJECT intent recognition works")


def test_project_tool_resolution():
    """Test that PROJECT_ENGINE capability resolves to correct tools."""
    set_unified_dispatcher(True)
    load_all()

    ai_manager = AIManager()
    # Get PROJECT_ENGINE capability
    route = ai_manager.route("create a new project")
    capability_id = route.capability

    print(f"Testing tool resolution for capability: {capability_id}")

    # Get the capability object from the AI manager's registry
    capability = ai_manager._capability_registry.get(capability_id)
    assert capability is not None, f"Capability {capability_id} not found in registry"

    # Verify that the capability's required tools are resolvable
    # For PROJECT_ENGINE, we expect it to use createProjectFolder and openFolder tools
    required_tools = getattr(capability, 'required_tools', [])
    print(f"  Required tools: {required_tools}")

    # Check that each required tool is resolvable
    for tool_id in required_tools:
        assert is_resolvable(tool_id), f"Expected {tool_id} to be resolvable for capability {capability_id}"
        resolved_tools = resolve_tools(tool_id)
        print(f"  {tool_id} resolves to: {resolved_tools}")

        # Verify that resolved tools are registered in TOOLS
        for tool in resolved_tools:
            assert tool in TOOLS, f"Resolved tool {tool} is not registered in TOOLS"
            assert callable(TOOLS[tool]), f"Resolved tool {tool} is not callable"

    print("  PASS: PROJECT_ENGINE tool resolution works")


def test_super_brain_planner_project_goals():
    """Test that Super-Brain planner correctly creates goals from AI Manager routes for project requests."""
    ai_manager = AIManager()
    planner = MasterPlanner()

    # Test goal creation from AI Manager output for project requests
    test_prompts = [
        "create a new project",
        "open the project",
        "list all projects",
        "find the project",
    ]

    for prompt in test_prompts:
        print(f"Testing planner with project goal: '{prompt}'")
        # Get AI Manager route
        route = ai_manager.route(prompt)

        # Create goal from route (this is what Super-Brain does)
        goal = Goal(
            text=prompt,
            intent=route.intent,
            domain=route.domain,
            capability=route.capability,
            output_type=route.output_type,
            confidence=route.confidence
        )

        # Create plan from goal
        plan = planner.create_goal_plan(goal, route)

        print(f"  Goal text: {goal.text}")
        print(f"  Goal intent: {goal.intent.name if goal.intent else None}")
        print(f"  Goal capability: {goal.capability}")
        print(f"  Plan has {len(plan.steps)} steps")

        # Verify that project goals have PROJECT_ENGINE capability
        if route.intent.name.startswith('PROJECT_'):
            assert goal.capability == 'PROJECT_ENGINE', \
                f"Expected PROJECT_ENGINE capability in goal, got {goal.capability}"

    print("  PASS: Super-Brain planner project integration works")


def test_capability_orchestrator_project_integration():
    """Test that Capability Orchestrator correctly handles PROJECT_ENGINE capability requests."""
    # Set up unified dispatcher to load tools
    set_unified_dispatcher(True)
    load_all()

    ai_manager = AIManager()
    from desktop_agent.brain.super_brain.capability_orchestrator import CapabilityOrchestrator
    orchestrator = CapabilityOrchestrator()

    # Test capability orchestration for project requests
    test_prompts = [
        "create a new project",
        "open the project",
    ]

    for prompt in test_prompts:
        print(f"Testing orchestrator with: '{prompt}'")
        # Get AI Manager route
        route = ai_manager.route(prompt)

        # Create a mock goal (simulating what Super-Brain would create)
        goal = Goal(
            text=prompt,
            intent=route.intent,
            domain=route.domain,
            capability=route.capability,
            output_type=route.output_type,
            confidence=route.confidence
        )

        # Get tool strategy from orchestrator
        strategy = orchestrator.strategy_for(route.capability, goal, route)

        print(f"  Capability: {route.capability}")
        print(f"  Selected tool: {strategy.tool}")
        print(f"  Tool why: {strategy.why}")

        # Verify the tool strategy is for a real registered tool or canonical ID
        # For project operations, we expect it to use project tools
        assert is_resolvable(strategy.tool) or strategy.tool in ['createProjectFolder', 'openFolder'], \
            f"Expected resolvable tool or project tool, got {strategy.tool}"

        # Verify that resolved tools include actual project/tools files tools
        resolved_tools = resolve_tools(strategy.tool) if is_resolvable(strategy.tool) else [strategy.tool]
        print(f"  Resolved to real tools: {resolved_tools}")

        # Verify that resolved tools are registered in TOOLS
        for tool in resolved_tools:
            assert tool in TOOLS, f"Tool {tool} is not registered in TOOLS"
            assert callable(TOOLS[tool]), f"Tool {tool} is not callable"

    print("  PASS: Capability orchestrator project integration works")


def test_project_tool_execution():
    """Test that project tools execute correctly through the unified system."""
    # Set up unified dispatcher
    set_unified_dispatcher(True)
    load_all()

    # Test that we can execute project tools through the unified system
    # These are the tools used for PROJECT_ENGINE capability
    test_cases = [
        ("createProjectFolder", {"path": "test_phase10_project", "scaffold_standard": True}),  # Creates project with standard structure
        ("openFolder", {"path": "test_phase10_project"}),  # Opens the project folder
    ]

    for tool_name, args in test_cases:
        print(f"Testing unified execution for: {tool_name}")
        if tool_name in TOOLS:
            # This should return a standardized response format
            result = TOOLS[tool_name](args)

            # Should return a standardized response format
            assert isinstance(result, dict), f"Result for {tool_name} is not a dict"
            assert "ok" in result, f"Result for {tool_name} missing 'ok' field"
            assert "tool" in result, f"Result for {tool_name} missing 'tool' field"
            assert result["tool"] == tool_name, f"Result tool name mismatch"
            assert "meta" in result, f"Result for {tool_name} missing 'meta' field"
            assert "duration_ms" in result["meta"], f"Result meta missing duration_ms"

            print(f"  Result: ok={result['ok']}, tool={result['tool']}")
        else:
            print(f"  SKIP: {tool_name} not available in test environment")

    # Clean up test project
    test_project_path = os.path.join(os.getcwd(), "test_phase10_project")
    if os.path.exists(test_project_path):
        shutil.rmtree(test_project_path)
        print(f"  Cleaned up test project: {test_project_path}")

    print("  PASS: Unified tool execution with project strategy works")


def run_all_tests():
    """Run all Phase 10 files/projects integration tests."""
    print("=" * 70)
    print("Phase 10 — FILES / PROJECTS INTEGRATION Tests")
    print("=" * 70)

    tests = [
        test_ai_manager_project_intent_recognition,
        test_project_tool_resolution,
        test_super_brain_planner_project_goals,
        test_capability_orchestrator_project_integration,
        test_project_tool_execution,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)