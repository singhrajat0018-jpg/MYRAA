#!/usr/bin/env python3
"""
Phase 8 — Browser / Web Automation Integration Tests

Tests for:
- End-to-end browser integration flow: GOAL → SUPER-BRAIN PLAN → BROWSER CAPABILITY →
  CAPABILITY REGISTRY → TOOL RESOLUTION → UNIFIED TOOL EXECUTION → BROWSER OBSERVATION →
  VERIFICATION → RECOVER/REPLAN → RESULT
- Goal-based browser requests without requiring step-by-step click instructions
- Support for existing browser capabilities: open applications, navigate, click, type,
  search, scroll, tabs
"""

import sys
import os

# Add the MYRAA directory to the path so desktop_agent can be found as a package
myraa_path = os.path.join(os.path.dirname(__file__), '..')
myraa_path = os.path.normpath(myraa_path)
print(f"Adding to path: {myraa_path}")
sys.path.insert(0, myraa_path)
print(f"Sys path: {sys.path[:3]}")

from desktop_agent.brain.ai.ai_manager import AIManager, Domain, Intent
from desktop_agent.brain.super_brain.planner import MasterPlanner, Goal
from desktop_agent.brain.super_brain.capability_orchestrator import CapabilityOrchestrator
from desktop_agent.brain.ai.tool_resolver import resolve, is_resolvable
from desktop_agent.registry import TOOLS, set_unified_dispatcher, load_all


def test_ai_manager_browser_capability_selection():
    """Test that AI Manager 4.1 correctly selects BROWSER_ENGINE capability for browser requests."""
    ai_manager = AIManager()

    # Test cases for browser requests - using phrases that should trigger browser intents
    test_cases = [
        # WEB_NAVIGATION: general browsing/navigation
        ("internet kholo", Domain.COMPUTER, Intent.WEB_NAVIGATION),

        # SEARCH_WEB: general web search
        ("search karo", Domain.COMPUTER, Intent.SEARCH_WEB),

        # SEARCH_GOOGLE: Google specific search
        ("Google search karo", Domain.COMPUTER, Intent.SEARCH_GOOGLE),

        # SEARCH_YOUTUBE: YouTube specific search
        ("YouTube search karo", Domain.COMPUTER, Intent.SEARCH_YOUTUBE),

        # SEARCH_GITHUB: GitHub specific search
        ("GitHub search karo", Domain.COMPUTER, Intent.SEARCH_GITHUB),
    ]

    for prompt, expected_domain, expected_intent in test_cases:
        print(f"Testing: '{prompt}'")
        signals = ai_manager._extract_task_signals(ai_manager._normalize_hinglish(prompt))
        print(f"  Signals - entities: {signals.entities}, topic: {signals.topic}, object: {signals.object}, action: {signals.action}")
        domain_candidates = ai_manager._detect_domain_candidates(signals)
        best_domain = max(domain_candidates, key=lambda x: x.confidence)
        intent_candidates = ai_manager._get_intent_candidates(prompt, signals, best_domain.domain)
        best_intent = intent_candidates[0] if intent_candidates else None

        # For multi-intent requests, we might get different results, but let's check the primary intent
        if best_intent:
            print(f"  Detected domain: {best_domain.domain.name} (expected: {expected_domain.name})")
            print(f"  Detected intent: {best_intent.intent.name} (expected: {expected_intent.name})")

            # Check capability selection
            output_type = ai_manager._classify_output_type(prompt.lower(), signals, best_intent.intent, best_domain.domain)
            capability_candidate = ai_manager._capability_for(best_domain.domain, best_intent.intent, output_type, signals)
            print(f"  Selected capability: {capability_candidate.capability.capability_id}")

            # Verify that browser-related intents route to BROWSER_ENGINE capability
            if expected_intent in [Intent.WEB_NAVIGATION, Intent.SEARCH_WEB, Intent.SEARCH_GOOGLE, Intent.SEARCH_GITHUB]:
                assert capability_candidate.capability.capability_id == 'BROWSER_ENGINE', \
                    f"Expected BROWSER_ENGINE capability for {expected_intent.name}, got {capability_candidate.capability.capability_id}"

    print("  PASS: AI Manager browser capability selection works")


def test_super_brain_planner_browser_integration():
    """Test that Super-Brain planner correctly creates goals from AI Manager routes for browser requests."""
    ai_manager = AIManager()
    planner = MasterPlanner()

    # Test goal creation from AI Manager output for browser requests
    test_prompts = [
        "website kholo",
        "web pe jao",
        "search karo",
        "Google search karo",
        "YouTube search karo",
        "GitHub search karo"
    ]

    for prompt in test_prompts:
        print(f"Testing planner with: '{prompt}'")
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
        print(f"  Goal domain: {goal.domain.name if goal.domain else None}")
        print(f"  Goal capability: {goal.capability}")
        print(f"  Plan has {len(plan.steps)} steps")

        # Verify that browser goals have BROWSER_ENGINE capability
        if route.intent in [Intent.WEB_NAVIGATION, Intent.SEARCH_WEB, Intent.SEARCH_GOOGLE, Intent.SEARCH_GITHUB]:
            assert goal.capability == 'BROWSER_ENGINE', \
                f"Expected BROWSER_ENGINE capability in goal, got {goal.capability}"

    print("  PASS: Super-Brain planner browser integration works")


def test_capability_orchestrator_browser_integration():
    """Test that Capability Orchestrator correctly converts AI Manager routes to tool strategies for browser requests."""
    # Set up unified dispatcher to load tools
    set_unified_dispatcher(True)
    load_all()

    ai_manager = AIManager()
    orchestrator = CapabilityOrchestrator()

    # Test capability orchestration for browser requests
    test_prompts = [
        "website kholo",
        "search karo",
        "Google search karo",
        "YouTube search karo",
        "GitHub search karo"
    ]

    for prompt in test_prompts:
        print(f"Testing orchestrator with: '{prompt}'")
        # Get AI Manager route
        route = ai_manager.route(prompt)

        # Create a mock goal (simulating what Super-Brain would create)
        from desktop_agent.brain.super_brain.planner import Goal
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
        print(f"  Requires confirmation: {strategy.requires_confirmation}")

        # INVARIANT: strategy.tool must be a REAL registered tool name.
        #
        # This test previously asserted strategy.tool == 'browser_tool' (the
        # canonical capability id). That was the documented production defect:
        # a canonical id leaking out of the orchestrator reaches the
        # CommandDispatcher, which only knows registered tool names, producing
        # the runtime error "Unknown tool 'browser_tool'". The orchestrator now
        # resolves canonical ids to concrete registered tools, so this test
        # locks in the FIXED contract.
        from desktop_agent.brain.ai.tool_resolver import CANONICAL_TOOL_RESOLVER

        assert strategy.tool, "orchestrator must always select a tool"
        assert strategy.tool in TOOLS, (
            f"strategy.tool '{strategy.tool}' is not a registered tool — a "
            f"canonical id must never reach the dispatcher"
        )
        assert callable(TOOLS[strategy.tool]), f"Tool {strategy.tool} is not callable"
        assert strategy.tool not in CANONICAL_TOOL_RESOLVER, \
            f"strategy.tool '{strategy.tool}' is a canonical id, not a registered tool"

        # BROWSER_ENGINE must resolve to one of the real browser tools.
        browser_tools = resolve('browser_tool')
        assert strategy.tool in browser_tools, \
            f"expected a browser tool for {prompt!r}, got {strategy.tool}"

        # The canonical id itself still resolves to the full browser tool set.
        expected_browser_tools = [
            "desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
            "desktopBrowserCloseTab", "desktopBrowserSearch", "desktopBrowserClick",
            "desktopBrowserType", "desktopBrowserFillForm", "desktopBrowserGoBack",
            "desktopBrowserGoForward", "desktopBrowserScroll"
        ]
        print(f"  Resolved to real tools: {browser_tools}")

        for tool in expected_browser_tools:
            assert tool in browser_tools, f"Expected browser tool {tool} not found in resolved tools: {browser_tools}"
            assert is_resolvable(tool), f"Tool {tool} is not resolvable"
            assert tool in TOOLS, f"Tool {tool} is not registered in TOOLS"
            assert callable(TOOLS[tool]), f"Tool {tool} is not callable"

    print("  PASS: Capability orchestrator browser integration works")


def test_browser_tool_resolution_chain():
    """Test the complete chain: BROWSER_ENGINE capability -> tool resolution -> real registered tools."""
    # Set up unified dispatcher to load tools
    set_unified_dispatcher(True)
    load_all()

    # Test that BROWSER_ENGINE capability maps to browser_tool via the tool resolver
    from desktop_agent.brain.ai.tool_resolver import CANONICAL_TOOL_RESOLVER

    print("Testing browser tool resolution chain:")
    print(f"  browser_tool resolves to: {resolve('browser_tool')}")

    # Verify that browser_tool maps to actual registered browser tools
    browser_tool_mapping = resolve('browser_tool')
    expected_tools = [
        "desktopBrowserOpen", "desktopBrowserNavigate", "desktopBrowserOpenTab",
        "desktopBrowserCloseTab", "desktopBrowserSearch", "desktopBrowserClick",
        "desktopBrowserType", "desktopBrowserFillForm", "desktopBrowserGoBack",
        "desktopBrowserGoForward", "desktopBrowserScroll"
    ]

    for tool in expected_tools:
        assert tool in browser_tool_mapping, f"Expected tool {tool} not found in browser_tool mapping"
        assert tool in TOOLS, f"Tool {tool} is not registered in TOOLS"
        assert callable(TOOLS[tool]), f"Tool {tool} is not callable"

    print("  PASS: Browser tool resolution chain works")


def test_unified_tool_execution_with_browser_strategy():
    """Test that unified tool execution works with Super-Brain generated browser tool strategies."""
    # Set up unified dispatcher
    set_unified_dispatcher(True)
    load_all()

    # Test that we can execute browser tools through the unified system
    # We'll test a few safe browser tools that don't require actual network or UI interaction in test environment
    test_cases = [
        ("desktopBrowserSearch", {"query": "test"}),  # This should work in test environment
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

    print("  PASS: Unified tool execution with browser strategy works")


def test_end_to_end_browser_flow():
    """Test the complete end-to-end flow for a browser request."""
    print("Testing end-to-end browser flow...")

    # Set up unified dispatcher for tool execution
    set_unified_dispatcher(True)
    load_all()

    # 1. AI Manager processes the goal
    ai_manager = AIManager()
    prompt = "search karo"
    print(f"  1. Processing prompt: '{prompt}'")

    route = ai_manager.route(prompt)
    print(f"     -> Domain: {route.domain.name}")
    print(f"     -> Intent: {route.intent.name}")
    print(f"     -> Capability: {route.capability}")
    print(f"     -> Execution mode: {route.execution_mode.name}")

    # 2. Super-Brain creates a plan (simulated)
    from desktop_agent.brain.super_brain.planner import Goal, MasterPlanner
    planner = MasterPlanner()
    goal = Goal(
        text=prompt,
        intent=route.intent,
        domain=route.domain,
        capability=route.capability,
        output_type=route.output_type,
        confidence=route.confidence
    )
    plan = planner.create_goal_plan(goal, route)
    print(f"  2. Super-Brain plan created with {len(plan.steps)} steps")

    # 3. Capability Orchestrator creates tool strategy
    orchestrator = CapabilityOrchestrator()
    # For simplicity, we'll use the goal directly
    strategy = orchestrator.strategy_for(route.capability, goal, route)
    print(f"  3. Tool strategy: {strategy.tool} ({strategy.why})")

    # 4. Tool resolution to real registered tools
    assert is_resolvable(strategy.tool), f"Tool {strategy.tool} should be resolvable"
    resolved_tools = resolve(strategy.tool)
    print(f"  4. Resolved to tools: {resolved_tools}")

    # 5. Unified tool execution (we'll test this doesn't crash)
    # Use the first resolved tool for testing
    if resolved_tools:
        test_tool = resolved_tools[0]
        if test_tool in TOOLS:
            print(f"  5. Testing unified execution of {test_tool}")
            # For safety, we'll use a tool that's safe to test
            if test_tool == "desktopBrowserSearch":
                result = TOOLS[test_tool]({"query": "test"})
                assert isinstance(result, dict)
                assert "ok" in result
                assert "tool" in result
                print(f"     -> Execution result: ok={result['ok']}")

    print("  PASS: End-to-end browser flow works")


def run_all_tests():
    """Run all Phase 8 browser integration tests."""
    print("=" * 70)
    print("Phase 8 — Browser / Web Automation Integration Tests")
    print("=" * 70)

    tests = [
        test_ai_manager_browser_capability_selection,
        test_super_brain_planner_browser_integration,
        test_capability_orchestrator_browser_integration,
        test_browser_tool_resolution_chain,
        test_unified_tool_execution_with_browser_strategy,
        test_end_to_end_browser_flow,
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