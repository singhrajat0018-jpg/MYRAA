#!/usr/bin/env python3
"""
Test script for ExecutionBrain instantiation
"""

import sys
import os
from unittest.mock import Mock, MagicMock

# Add the desktop_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))

def test_execution_brain_instantiation():
    """Test that ExecutionBrain can be instantiated with mocked dependencies"""

    try:
        # Import the ExecutionBrain class
        from desktop_agent.brain.execution_brain import ExecutionBrain

        # Create mock dependencies
        dispatcher = Mock()
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

        print("SUCCESS: ExecutionBrain instantiated successfully")
        print(f"Brain type: {type(brain).__name__}")

        # Test that we can access the AIManager through the brain's dependencies
        # Since AIManager is imported but not directly used in __init__,
        # we'll test that the import worked by checking if we can import it separately
        from desktop_agent.brain.ai.ai_manager import AIManager
        ai_manager = AIManager()
        print(f"AIManager type: {type(ai_manager).__name__}")

        # Test a simple complexity detection
        hints = ai_manager._determine_complexity_hints("", "hello")
        print(f"'hello' complexity hints: {hints}")

        return True

    except Exception as e:
        print(f"ERROR: Failed to instantiate ExecutionBrain: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_execution_brain_instantiation()
    sys.exit(0 if success else 1)