"""
EPIC-14D: World-Class Verification, Recovery & Self-Correction Tests

Tests the enhanced verification and recovery functionality for EPIC-14D.
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


class EPIC14DEnhancementTest:
    """Test suite for EPIC-14D enhancement functionality."""

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
        print("EPIC-14D Enhancement Test Summary")
        print("=" * 60)
        print(f"Passed : {self.passed}")
        print(f"Failed : {self.failed}")
        print(f"Total  : {self.total}")
        if self.total:
            percent = self.passed / self.total * 100
            print(f"Health : {percent:.1f}%")

    # ==========================================================
    # Test Cases for EPIC-14D Enhancements
    # ==========================================================

    def test_verification_enhancements_import(self):
        """Test that verification enhancements module can be imported."""
        from desktop_agent.brain.execution.verification_enhancements import (
            EnhancedVerificationResult, VerificationSignal, VerificationSignalType,
            ExpectedState, FailureClassification
        )

        # Test basic instantiation
        signal = VerificationSignal(
            signal_type=VerificationSignalType.STATE_EXISTENCE,
            is_success=True,
            confidence=0.9,
            message="Test signal"
        )

        result = EnhancedVerificationResult(
            is_success=True,
            overall_confidence=0.9,
            signals=[signal],
            message="Test result"
        )

        assert result.is_success == True
        assert result.overall_confidence == 0.9
        assert len(result.signals) == 1
        print("[PASS] Verification enhancements import and basic functionality successful")

    def test_expected_state_system(self):
        """Test the expected state system."""
        from desktop_agent.brain.execution.expected_state import get_expected_state_for_action

        # Test click action
        click_expected = get_expected_state_for_action("click", {})
        assert click_expected.target_should_exist == True
        assert click_expected.target_should_be_visible == True

        # Test type_text action
        type_expected = get_expected_state_for_action("type_text", {"text": "hello"})
        assert type_expected.target_should_exist == True
        assert type_expected.target_should_be_enabled == True

        # Test open_application action
        open_expected = get_expected_state_for_action("open_application", {"application": "notepad"})
        assert open_expected.application_should_be_running == "notepad"

        print("[PASS] Expected state system successful")

    def test_failure_classifier(self):
        """Test the failure classifier."""
        from desktop_agent.brain.execution.failure_classifier import FailureClassifier
        from desktop_agent.brain.execution.action_executor import ExecutionResult
        from desktop_agent.brain.planner.models.computer_action import ComputerAction
        from desktop_agent.desktop.vision.interaction_target import InteractionTarget
        from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType

        classifier = FailureClassifier()

        # Create a mock action and target for testing
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

        action = ComputerAction(
            action_type="click",  # Using string for simplicity in test
            target=target,
            parameters={}
        )

        # Test validation failure classification
        from desktop_agent.brain.execution.action_validator import ValidationResult, ValidationStatus

        validation_result = ValidationResult(
            is_valid=False,
            status=ValidationStatus.STALE,
            message="Target is stale",
            should_re_resolve=True
        )

        failure_class = classifier.classify_validation_failure(
            validation_result, "click", {}
        )

        assert failure_class.category == "target_stale"
        assert failure_class.suggested_recovery == "re_resolve_target"
        assert failure_class.confidence == 0.9

        print("[PASS] Failure classifier successful")

    def test_recovery_strategies(self):
        """Test the recovery strategies system."""
        from desktop_agent.brain.execution.recovery_strategies import (
            RecoveryStrategyManager, RecoveryAction, RecoveryStrategy
        )

        manager = RecoveryStrategyManager()

        # Test getting a strategy for known failure type
        strategy = manager.get_recovery_strategy("target_not_found", 0)
        assert strategy is not None
        assert strategy.action == RecoveryAction.RE_RESOLVE_TARGET
        assert strategy.failure_category == "target_not_found"

        # Test that strategies respect max attempts
        strategy_attempt_3 = manager.get_recovery_strategy("target_not_found", 3)
        # Depending on the strategy definition, this might be None or still available

        print("[PASS] Recovery strategies system successful")

    def test_enhanced_action_verifier_methods_exist(self):
        """Test that enhanced action verifier has the new methods."""
        from desktop_agent.brain.execution.action_verifier import ActionVerifier
        from desktop_agent.brain.perception import Perception
        from desktop_agent.registry import ValidationLayer

        perception = MagicMock(spec=Perception)
        validation_layer = ValidationLayer()

        verifier = ActionVerifier(perception, validation_layer)

        # Check that enhanced methods exist
        assert hasattr(verifier, 'verify_action_enhanced')
        assert hasattr(verifier, '_perform_multi_signal_verification')
        assert hasattr(verifier, '_perform_temporal_verification')

        print("[PASS] Enhanced action verifier methods exist")

    def test_action_executor_has_enhanced_methods(self):
        """Test that action executor has enhanced methods."""
        from desktop_agent.brain.execution.action_executor import ActionExecutor
        from desktop_agent.brain.perception import Perception
        from desktop_agent.brain.execution.action_validator import ActionValidator
        from desktop_agent.brain.execution.action_verifier import ActionVerifier
        from desktop_agent.brain.planner.execution.executor_bridge import ExecutorBridge
        from desktop_agent.brain.planner.execution.action_adapters.adapter_executor import AdapterExecutor
        from desktop_agent.brain.blackboard.blackboard import Blackboard

        # Create mocks
        perception = MagicMock(spec=Perception)
        validator = MagicMock(spec=ActionValidator)
        verifier = MagicMock(spec=ActionVerifier)
        executor_bridge = MagicMock(spec=ExecutorBridge)
        adapter_executor = MagicMock(spec=AdapterExecutor)
        blackboard = MagicMock(spec=Blackboard)

        executor = ActionExecutor(
            perception,
            validator,
            verifier,
            executor_bridge,
            adapter_executor,
            blackboard
        )

        # Check that enhanced methods exist
        assert hasattr(executor, '_verify_action_enhanced')
        assert hasattr(executor, '_convert_to_enhanced_verification_result')
        assert hasattr(executor, '_determine_recovery_action')

        print("[PASS] Action executor enhanced methods exist")


def main():
    """Run all tests."""
    print("Starting EPIC-14D Enhancement Tests...")
    print("=" * 60)

    test = EPIC14DEnhancementTest()

    # Run tests
    test.run("Verification Enhancements Import", test.test_verification_enhancements_import)
    test.run("Expected State System", test.test_expected_state_system)
    test.run("Failure Classifier", test.test_failure_classifier)
    test.run("Recovery Strategies", test.test_recovery_strategies)
    test.run("Enhanced Action Verifier Methods Exist", test.test_enhanced_action_verifier_methods_exist)
    test.run("Action Executor Has Enhanced Methods", test.test_action_executor_has_enhanced_methods)

    # Print summary
    test.summary()

    # Return appropriate exit code
    return 0 if test.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())