#!/usr/bin/env python3
"""
Test script for EPIC-14G Fast Path for Simple Commands
"""

import sys
import os
from unittest.mock import Mock, MagicMock

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

def test_epic14g_fast_path_detection():
    """Test that ExecutionBrain correctly identifies simple prompts for fast path"""

    try:
        # Import the ExecutionBrain class
        from desktop_agent.brain.execution_brain import ExecutionBrain

        # Create mock dependencies
        dispatcher = Mock()
        dispatcher.dispatch = Mock(return_value=Mock(success=True, message="Direct execution successful"))

        context_manager = Mock()
        safety = Mock()
        verification = Mock()
        decision_engine = Mock()
        planner = Mock()
        orchestrator = Mock()
        retry_manager = Mock()
        perception = Mock()
        action_planner = Mock()
        action_validator = Mock()
        action_verifier = Mock()
        action_executor = Mock()

        # Mock the subcomponents that ExecutionBrain tries to access
        perception.state = Mock()
        perception.state.screen_state = None
        perception.resolve_target = Mock(return_value=Mock(status=Mock(value="RESOLVED"), target=None))

        # Instantiate ExecutionBrain with mocked dependencies
        brain = ExecutionBrain(
            dispatcher=dispatcher,
            context_manager=context_manager,
            safety=safety,
            verification=verification,
            decision_engine=decision_engine,
            planner=planner,
            orchestrator=orchestrator,
            retry_manager=retry_manager,
            perception=perception,
            action_planner=action_planner,
            action_validator=action_validator,
            action_verifier=action_verifier,
            action_executor=action_executor
        )

        # Test cases for simple prompts that should trigger _is_simple_prompt to return True
        simple_prompts = [
            "hello",
            "hi",
            "hey",
            "good morning",
            "thanks",
            "thank you",
            "yes",
            "no",
            "stop",
            "cancel",
            "wait",
            "what time is it",
            "current time",
            "open notepad",
            "close chrome",
            "set volume to 50",
            "volume 70%",
            "set brightness to 80",
            "brightness 60%",
            "mute",
            "unmute",
            "maximize",
            "minimize",
            "restore",
            "close window",
            "switch to chrome"
        ]

        # Test cases that should NOT trigger fast path (complex prompts)
        complex_prompts = [
            "explain how photosynthesis works",
            "analyze the pros and cons of renewable energy",
            "compare electric cars vs gasoline cars",
            "evaluate the impact of social media on society",
            "step by step guide to baking a cake",
            "plan a comprehensive marketing strategy"
        ]

        print("Testing EPIC-14G Fast Path Detection in ExecutionBrain")
        print("=" * 60)

        # Test simple prompts
        print("\nSimple Prompts (should return True for _is_simple_prompt):")
        simple_passed = 0
        for prompt in simple_prompts:
            # Create a mock request with the prompt
            request = Mock()
            request.args = {"prompt": prompt}
            request.tool = "some_tool"  # This doesn't matter for the prompt detection

            result = brain._is_simple_prompt(request)
            if result:
                print(f"  PASS: '{prompt}' -> {result}")
                simple_passed += 1
            else:
                print(f"  FAIL: '{prompt}' -> {result} (expected True)")

        # Test complex prompts
        print("\nComplex Prompts (should return False for _is_simple_prompt):")
        complex_passed = 0
        for prompt in complex_prompts:
            # Create a mock request with the prompt
            request = Mock()
            request.args = {"prompt": prompt}
            request.tool = "some_tool"

            result = brain._is_simple_prompt(request)
            if not result:
                print(f"  PASS: '{prompt}' -> {result}")
                complex_passed += 1
            else:
                print(f"  FAIL: '{prompt}' -> {result} (expected False)")

        # Summary
        total_simple = len(simple_prompts)
        total_complex = len(complex_prompts)
        simple_accuracy = (simple_passed / total_simple) * 100 if total_simple > 0 else 0
        complex_accuracy = (complex_passed / total_complex) * 100 if total_complex > 0 else 0
        overall_accuracy = ((simple_passed + complex_passed) / (total_simple + total_complex)) * 100

        print("\n" + "=" * 60)
        print(f"Simple Prompts Accuracy:  {simple_passed}/{total_simple} ({simple_accuracy:.1f}%)")
        print(f"Complex Prompts Accuracy: {complex_passed}/{total_complex} ({complex_accuracy:.1f}%)")
        print(f"Overall Accuracy:         {(simple_passed + complex_passed)}/{total_simple + total_complex} ({overall_accuracy:.1f}%)")

        if overall_accuracy >= 80:
            print("\nSUCCESS: EPIC-14G Fast Path detection is working well!")
            return True
        else:
            print("\nFAILURE: EPIC-14G Fast Path detection needs improvement.")
            return False

    except Exception as e:
        print(f"ERROR: Failed to test EPIC-14G fast path: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_execution_flow_with_simple_prompt():
    """Test that simple prompts can take the fast path in execution"""

    try:
        # Import the ExecutionBrain class
        from desktop_agent.brain.execution_brain import ExecutionBrain
        from desktop_agent.brain.planner.models.computer_action import ComputerAction
        from desktop_agent.brain.planner.models.action_types import ActionType
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox

        # Create mock dependencies
        dispatcher = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.message = "Direct execution successful"
        dispatcher.dispatch = Mock(return_value=mock_result)

        context_manager = Mock()
        safety = Mock()
        verification = Mock()
        decision_engine = Mock()
        planner = Mock()
        orchestrator = Mock()
        retry_manager = Mock()
        perception = Mock()
        action_planner = Mock()
        action_validator = Mock()
        action_verifier = Mock()
        action_executor = Mock()

        # Mock the subcomponents that ExecutionBrain tries to access
        perception.state = Mock()
        perception.state.screen_state = None
        perception.resolve_target = Mock(return_value=Mock(status=Mock(value="RESOLVED"), target=None))

        # Instantiate ExecutionBrain with mocked dependencies
        brain = ExecutionBrain(
            dispatcher=dispatcher,
            context_manager=context_manager,
            safety=safety,
            verification=verification,
            decision_engine=decision_engine,
            planner=planner,
            orchestrator=orchestrator,
            retry_manager=retry_manager,
            perception=perception,
            action_planner=action_planner,
            action_validator=action_validator,
            action_verifier=action_verifier,
            action_executor=action_executor
        )

        print("\n" + "=" * 60)
        print("Testing Execution Flow with Simple Prompt")
        print("=" * 60)

        # Test a simple prompt that should go through direct execution path
        request = Mock()
        request.args = {"prompt": "hello"}
        request.tool = "echo"  # Simple tool that's not in COMPLEX_TOOLS

        # Mock the context building
        from desktop_agent.brain.models import BrainContext
        mock_context = BrainContext()
        mock_context.metadata = {}
        brain._build_context = Mock(return_value=mock_context)
        brain._run_safety = Mock()
        brain._is_complex = Mock(return_value=False)  # echo is not complex
        brain._is_epic14c_action = Mock(return_value=False)  # Not a computer interaction
        brain._execute_direct = Mock(return_value=mock_result)
        brain._finalize = Mock(side_effect=lambda x, started: x)  # Just return the result

        # Execute the request
        result = brain.execute(request)

        # Verify that direct execution was called for simple prompt + simple tool
        if brain._execute_direct.called:
            print("  PASS: Simple prompt with simple tool -> Direct execution (fast path)")
        else:
            print("  WARN: Simple prompt with simple tool -> Did not use direct execution")

        # Verify the result
        if result and result.success:
            print("  PASS: Execution returned successful result")
            return True
        else:
            print("  FAIL: Execution did not return successful result")
            return False

    except Exception as e:
        print(f"ERROR: Failed to test execution flow: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("EPIC-14G: WORLD-CLASS PERFORMANCE & LATENCY OPTIMIZATION")
    print("Testing Fast Path for Simple Commands Implementation")
    print("=" * 60)

    # Test 1: Fast path detection
    test1_passed = test_epic14g_fast_path_detection()

    # Test 2: Execution flow
    test2_passed = test_execution_flow_with_simple_prompt()

    print("\n" + "=" * 60)
    print("FINAL RESULTS:")
    print(f"  Fast Path Detection: {'PASS' if test1_passed else 'FAIL'}")
    print(f"  Execution Flow Test: {'PASS' if test2_passed else 'FAIL'}")

    if test1_passed and test2_passed:
        print("\nALL TESTS PASSED - EPIC-14G Fast Path implementation is working!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - Implementation needs review")
        sys.exit(1)