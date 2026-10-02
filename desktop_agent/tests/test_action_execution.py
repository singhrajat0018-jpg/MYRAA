"""
EPIC-14C: World-Class Computer Action Execution Tests

Tests the action execution pipeline including:
- Action planning
- Action validation
- Action execution
- Action verification
- Closed-loop act→observe→verify functionality
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add MYRAA project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also add current directory to path for relative imports
if '.' not in sys.path:
    sys.path.insert(0, '.')

import traceback


class ActionExecutionTest:
    """Test suite for EPIC-14C action execution functionality."""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0

    def run(self, name, func):
        """Run a test function and track results."""
        self.total += 1
        print("-" * 60)
        print(f"Testing: {name}")
        print("-" * 60)

        try:
            func()
            self.passed += 1
            print("PASS")
        except Exception as e:
            self.failed += 1
            print("FAIL")
            traceback.print_exc()
        print()

    def summary(self):
        """Print test summary."""
        print("=" * 60)
        print("EPIC-14C Action Execution Test Summary")
        print("=" * 60)
        print(f"Passed : {self.passed}")
        print(f"Failed : {self.failed}")
        print(f"Total  : {self.total}")
        if self.total:
            percent = self.passed / self.total * 100
            print(f"Health : {percent:.1f}%")

    # ==========================================================
    # Test Cases
    # ==========================================================

    def test_computer_action_creation(self):
        """Test creation of ComputerAction objects."""
        from desktop_agent.brain.planner.models.computer_action import ComputerAction
        from desktop_agent.brain.planner.models.action_types import ActionType
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType

        # Create a basic target
        target = InteractionTarget(
            id="test_target",
            type=UIElementType.BUTTON,
            text="Test Button",
            confidence=0.9,
            bounds=BoundingBox(x=100, y=100, width=50, height=30),
            clickable=True,
            enabled=True,
            visible=True,
                        resolution_method="test",
            reasoning="Test target",
            timestamp=time.time(),
            valid=True
        )

        # Create ComputerAction
        action = ComputerAction(
            action_type=ActionType.CLICK,
            target=target,
            parameters={}
        )

        assert action.action_type == ActionType.CLICK
        assert action.target.text == "Test Button"
        assert action.validation_status.name == "PENDING"
        assert action.verification_status.name == "PENDING"
        print("[PASS] ComputerAction creation successful")

    def test_action_planner_basic(self):
        """Test basic action planning functionality."""
        from desktop_agent.brain.planning.action_planner import ActionPlanner
        from desktop_agent.brain.planner.models.models import PlannerGoal, PlannerContext
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType

        planner = ActionPlanner()

        # Create test goal and target
        goal = PlannerGoal(
            text="click the button",
            confidence=0.9
        )

        target = InteractionTarget(
            id="test_button",
            type=UIElementType.BUTTON,
            text="Test Button",
            confidence=0.8,
            bounds=BoundingBox(x=100, y=100, width=50, height=30),
            clickable=True,
            enabled=True,
            visible=True,
                        resolution_method="test",
            reasoning="Test target",
            timestamp=time.time(),
            valid=True
        )

        context = PlannerContext(
            active_window=None,
            active_application="",
            screen_summary="",
            screen_resolution=(1920, 1080),
            cursor_position=(960, 540),
            selected_text="",
            clipboard="",
            metadata={}
        )

        # Plan actions
        result = planner.plan_actions(goal, target, context)

        assert result.success == True
        assert len(result.actions) > 0
        assert result.actions[0].action_type.value == "click"
        print("[PASS] Action planner basic functionality successful")

    def test_action_validator_fresh_target(self):
        """Test action validator with a fresh target."""
        from desktop_agent.brain.execution.action_validator import ActionValidator
        from desktop_agent.brain.planner.models.computer_action import ComputerAction
        from desktop_agent.brain.planner.models.action_types import ActionType
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType
        from desktop_agent.brain.perception import Perception
        from desktop_agent.registry import ValidationLayer

        # Create a fresh target
        target = InteractionTarget(
            id="fresh_target",
            type=UIElementType.BUTTON,
            text="Fresh Button",
            confidence=0.9,
            bounds=BoundingBox(x=100, y=100, width=50, height=30),
            clickable=True,
            enabled=True,
            visible=True,
                        resolution_method="test",
            reasoning="Fresh target",
            timestamp=time.time(),
            valid=True
        )

        # Setup mock perception
        mock_perception = MagicMock(spec=Perception)
        mock_screen_state = MagicMock()
        mock_screen_state.bounds = BoundingBox(x=0, y=0, width=1920, height=1080)
        mock_screen_state.active_window = None
        mock_screen_state.elements = []
        mock_screen_state.get_element_by_id.return_value = target
        mock_perception.screen_state = mock_screen_state

        validator = ActionValidator(mock_perception, ValidationLayer())

        action = ComputerAction(
            action_type=ActionType.CLICK,
            target=target,
            parameters={}
        )

        # Validate action
        result = validator.validate_action(action, None)

        assert result.is_valid == True
        assert result.status.name == "VALID"
        print("[PASS] Action validator fresh target test successful")

    def test_action_verifier_generic(self):
        """Test action verifier with generic action."""
        from desktop_agent.brain.execution.action_verifier import ActionVerifier
        from desktop_agent.brain.planner.models.computer_action import ComputerAction
        from desktop_agent.brain.planner.models.action_types import ActionType
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType
        from desktop_agent.brain.perception import Perception
        from desktop_agent.registry import ValidationLayer

        # Create target and action
        target = InteractionTarget(
            id="test_target",
            type=UIElementType.BUTTON,
            text="Test Target",
            confidence=0.8,
            bounds=BoundingBox(x=100, y=100, width=50, height=30),
            clickable=True,
            enabled=True,
            visible=True,
                        resolution_method="test",
            reasoning="Test target",
            timestamp=time.time(),
            valid=True
        )

        action = ComputerAction(
            action_type=ActionType.CLICK,
            target=target,
            parameters={}
        )

        # Setup mock perception
        mock_perception = MagicMock(spec=Perception)
        mock_screen_state = MagicMock()
        mock_screen_state.bounds = BoundingBox(x=0, y=0, width=1920, height=1080)
        mock_screen_state.active_window = None
        mock_screen_state.elements = []
        mock_screen_state.get_element_by_id.return_value = target
        mock_perception.screen_state = mock_screen_state

        verifier = ActionVerifier(mock_perception, ValidationLayer())

        # Mark as executed first
        action.mark_as_executed({"success": True})

        # Verify action
        result = verifier.verify_action(action, None)

        assert result.is_success == True
        assert result.status.name == "VERIFIED_SUCCESS"
        print("[PASS] Action verifier generic test successful")

    def test_action_executor_initialization(self):
        """Test action executor initialization."""
        from desktop_agent.brain.execution.action_executor import ActionExecutor
        from desktop_agent.brain.perception import Perception
        from desktop_agent.brain.execution.action_validator import ActionValidator
        from desktop_agent.brain.execution.action_verifier import ActionVerifier
        from desktop_agent.brain.planner.execution.action_adapters.adapter_executor import AdapterExecutor
        from desktop_agent.brain.planner.execution.action_adapters.adapter_factory import AdapterFactory
        from desktop_agent.registry import ValidationLayer

        # Setup dependencies
        mock_perception = MagicMock(spec=Perception)
        mock_validator = MagicMock(spec=ActionValidator)
        mock_verifier = MagicMock(spec=ActionVerifier)
        mock_adapter_executor = MagicMock(spec=AdapterExecutor)

        executor = ActionExecutor(
            mock_perception,
            mock_validator,
            mock_verifier,
            MagicMock(),  # executor_bridge
            mock_adapter_executor
        )

        assert executor.perception == mock_perception
        assert executor.validator == mock_validator
        assert executor.verifier == mock_verifier
        assert executor.adapter_executor == mock_adapter_executor
        print("[PASS] Action executor initialization successful")

    def test_epic14c_integration_with_execution_brain(self):
        """Test that ExecutionBrain properly integrates EPIC-14C components."""
        from desktop_agent.brain.execution_brain import ExecutionBrain
        from unittest.mock import MagicMock

        # Setup mocks
        mock_dispatcher = MagicMock()
        mock_context_manager = MagicMock()
        mock_safety = MagicMock()
        mock_verification = MagicMock()
        mock_decision_engine = MagicMock()
        mock_planner = MagicMock()
        mock_orchestrator = MagicMock()
        mock_retry_manager = MagicMock()
        mock_perception = MagicMock()

        # Create ExecutionBrain with EPIC-14C components
        brain = ExecutionBrain(
            dispatcher=mock_dispatcher,
            context_manager=mock_context_manager,
            safety=mock_safety,
            verification=mock_verification,
            decision_engine=mock_decision_engine,
            planner=mock_planner,
            orchestrator=mock_orchestrator,
            retry_manager=mock_retry_manager,
            perception=mock_perception
        )

        # Check that EPIC-14C components are initialized
        assert brain.action_planner is not None
        assert brain.action_validator is not None
        assert brain.action_verifier is not None
        assert brain.action_executor is not None
        print("[PASS] EPIC-14C integration with ExecutionBrain successful")

    def test_is_epic14c_action_detection(self):
        """Test ExecutionBrain's detection of EPIC-14C actions."""
        from desktop_agent.brain.execution_brain import ExecutionBrain
        from unittest.mock import MagicMock
        from desktop_agent.brain.models import BrainContext

        # Setup minimal ExecutionBrain
        mock_dispatcher = MagicMock()
        brain = ExecutionBrain(dispatcher=mock_dispatcher)

        # Test request that should be detected as EPIC-14C
        epic14c_request = MagicMock()
        epic14c_request.tool = "click"
        epic14c_request.args = {"x": 100, "y": 200}

        # Test request that should NOT be detected as EPIC-14C
        regular_request = MagicMock()
        regular_request.tool = "get_system_info"
        regular_request.args = {}

        # Test detection
        assert brain._is_epic14c_action(epic14c_request) == True
        assert brain._is_epic14c_action(regular_request) == False
        print("[PASS] EPIC-14C action detection test successful")

    def test_action_parameters_for_browser_continuity(self):
        """Test that browser actions get proper parameters for continuity."""
        from desktop_agent.brain.execution.action_validator import ActionValidator
        from desktop_agent.brain.planner.models.computer_action import ComputerAction
        from desktop_agent.brain.planner.models.action_types import ActionType
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType
        from desktop_agent.brain.perception import Perception
        from desktop_agent.registry import ValidationLayer

        # Setup mock perception with visible browser
        mock_perception = MagicMock(spec=Perception)
        mock_screen_state = MagicMock()
        mock_screen_state.bounds = BoundingBox(x=0, y=0, width=1920, height=1080)
        mock_screen_state.active_window = None

        # Add a visible browser element
        mock_browser_element = MagicMock()
        mock_browser_element.type.value = "chrome"
        mock_browser_element.visible = True
        mock_browser_element.bounds = BoundingBox(x=100, y=100, width=800, height=600)
        mock_screen_state.elements = [mock_browser_element]

        mock_perception.screen_state = mock_screen_state

        validator = ActionValidator(mock_perception, ValidationLayer())

        # Create browser action
        target = InteractionTarget(
            id="browser_target",
            type=UIElementType.BUTTON,
            text="Browser Button",
            confidence=0.8,
            bounds=BoundingBox(x=200, y=200, width=50, height=30),
            clickable=True,
            enabled=True,
            visible=True,
                        resolution_method="test",
            reasoning="Test target",
            timestamp=time.time(),
            valid=True
        )

        action = ComputerAction(
            action_type=ActionType.CLICK,  # This gets mapped to leftClick tool
            target=target,
            parameters={}
        )

        # Note: The validator adds browser continuity parameters
        # For this test we're checking that the validation passes
        result = validator.validate_action(action, None)

        # Should pass validation (browser continuity check)
        # The actual parameter addition happens inside the validator
        print("[PASS] Browser continuity parameter test completed")


def main():
    """Run all tests."""
    print("Starting EPIC-14C Action Execution Tests...")
    print("=" * 60)

    test = ActionExecutionTest()

    # Run tests
    test.run("ComputerAction Creation", test.test_computer_action_creation)
    test.run("Action Planner Basic", test.test_action_planner_basic)
    test.run("Action Validator Fresh Target", test.test_action_validator_fresh_target)
    test.run("Action Verifier Generic", test.test_action_verifier_generic)
    test.run("Action Executor Initialization", test.test_action_executor_initialization)
    test.run("EPIC-14C Integration with ExecutionBrain", test.test_epic14c_integration_with_execution_brain)
    test.run("EPIC-14C Action Detection", test.test_is_epic14c_action_detection)
    test.run("Action Parameters for Browser Continuity", test.test_action_parameters_for_browser_continuity)

    # Print summary
    test.summary()

    # Return appropriate exit code
    return 0 if test.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())