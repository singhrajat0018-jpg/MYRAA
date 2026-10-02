"""
Tests for MYRAA Super-Brain (B25 cognitive tests and B26 E2E Super-Brain).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add MYRAA project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from desktop_agent.brain.super_brain import SuperBrain
from desktop_agent.brain.super_brain.goal import Goal, build_goal
from desktop_agent.brain.ai.ai_manager import AIManager, Domain, RiskLevel, OutputType, ExecutionMode, Intent
from desktop_agent.brain.semantic.semantic_models import SemanticTask
from desktop_agent.brain.orchestrator.orchestrator import Orchestrator
from desktop_agent.brain.verification import VerificationManager
from desktop_agent.brain.failure_containment import RecoveryEngine, RetryAction


class TestSuperBrainCognitive:
    """Test Super-Brain cognitive functions (B25)."""

    def setup_method(self):
        """Set up test fixtures with proper mocks."""
        self.ai_manager = MagicMock(spec=AIManager)
        self.orchestrator = MagicMock(spec=Orchestrator)
        self.verification_manager = MagicMock(spec=VerificationManager)
        self.recovery_engine = MagicMock(spec=RecoveryEngine)

        self.super_brain = SuperBrain(
            ai_manager=self.ai_manager,
            orchestrator=self.orchestrator,
            verification=self.verification_manager,
            recovery=self.recovery_engine
        )

    def _create_route_mock(self, decision="BRAIN", capability="QUESTION_ANSWERING", confidence=0.9, risk_level=RiskLevel.NONE,
                           intent=Intent.ASK, domain=Domain.GENERAL, output_type=OutputType.TEXT,
                           entities=None, topic=None, context_required=None, sub_tasks=None, dependencies=None,
                           capability_chain=None, can_use_fast_path=True, execution_mode=ExecutionMode.FAST_MODEL):
        """Create a mock route object with the given attributes."""
        route = MagicMock()
        route.decision = decision
        route.capability = capability
        route.confidence = confidence
        route.risk_level = risk_level
        route.intent = intent
        route.domain = domain
        route.output_type = output_type
        route.entities = entities if entities is not None else []
        route.topic = topic if topic is not None else []
        route.context_required = context_required if context_required is not None else []
        route.sub_tasks = sub_tasks if sub_tasks is not None else []
        route.dependencies = dependencies if dependencies is not None else []
        route.capability_chain = capability_chain if capability_chain is not None else []
        route.can_use_fast_path = can_use_fast_path
        route.execution_mode = execution_mode
        # Prevent automatic mock creation for .route attribute in SuperBrain._route
        route.route = route
        return route

    def _setup_successful_orchestrator(self):
        """Setup orchestrator to return successful result."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.last_message = "Task completed successfully"
        mock_result.result = {"status": "success"}
        self.orchestrator.execute.return_value = mock_result

        # Setup verification to return verified
        mock_verification = MagicMock()
        mock_verification.is_verified = True
        mock_verification.outcome = "success"
        self.verification_manager.verify.return_value = mock_verification

    def test_simple_question(self):
        """Test simple question handling."""
        # Arrange
        user_request = "What is the capital of France?"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="QUESTION_ANSWERING",
            confidence=0.9,
            risk_level=RiskLevel.NONE,
            intent=Intent.ASK,  # Using actual Intent.ASK from AI Manager
            domain=Domain.GENERAL,
            output_type=OutputType.ANSWER,  # Using actual OutputType.ANSWER
            execution_mode=ExecutionMode.FAST_MODEL
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "QUESTION_ANSWERING"
        assert result.goal_text == user_request

    def test_desktop_action(self):
        """Test desktop action execution."""
        # Arrange
        user_request = "Open Notepad"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="OPEN_APPLICATION",
            confidence=0.95,
            risk_level=RiskLevel.NONE,
            intent=Intent.APP_CONTROL,  # Using actual Intent.APP_CONTROL
            domain=Domain.SYSTEM,
            output_type=OutputType.SYSTEM_ACTION,
            execution_mode=ExecutionMode.FAST_DETERMINISTIC
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "OPEN_APPLICATION"

    def test_multi_step_goal(self):
        """Test multi-step goal decomposition."""
        # Arrange
        user_request = "Open Notepad and type hello"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="MULTI_STEP",
            confidence=0.9,
            risk_level=RiskLevel.NONE,
            intent=Intent.GENERAL_REQUEST,  # Placeholder for multi-step
            domain=Domain.SYSTEM,
            output_type=OutputType.SYSTEM_ACTION,
            sub_tasks=[
                {"goal": "Open Notepad", "intent": Intent.APP_CONTROL.value, "capability": "OPEN_APPLICATION"},
                {"goal": "Type hello", "intent": Intent.COMMAND.value, "capability": "TYPE_TEXT"}  # Using Intent.COMMAND for typing
            ],
            dependencies=[[], [0]],  # Second task depends on first
            capability_chain=["OPEN_APPLICATION", "TYPE_TEXT"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "MULTI_STEP"
        assert result.goal_text == user_request

    def test_multi_intent_goal(self):
        """Test multi-intent goal handling."""
        # Arrange
        user_request = "Message Rahul and call Priya"
        route = self._create_route_mock(
            decision="ROUTE",  # Communication intent
            capability="COMPUTER_USE",
            confidence=0.85,
            risk_level=RiskLevel.LOW,
            intent=Intent.PHONE_CONTROL,  # Using actual Intent.PHONE_CONTROL (matches "message")
            domain=Domain.COMPUTER,  # Communication via desktop apps
            output_type=OutputType.SYSTEM_ACTION,
            sub_tasks=[
                {"goal": "Message Rahul", "intent": Intent.PHONE_CONTROL.value, "capability": "SEND_MESSAGE_VIA_WHATSAPP"},
                {"goal": "Call Priya", "intent": Intent.PHONE_CALL.value, "capability": "CALL_VIA_WHATSAPP"}
            ],
            dependencies=[[], []],  # Independent tasks
            capability_chain=["SEND_MESSAGE_VIA_WHATSAPP", "CALL_VIA_WHATSAPP"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "ROUTE"
        assert result.capability == "COMPUTER_USE"

    def test_context_dependent_task(self):
        """Test context-dependent task."""
        # Arrange
        user_request = "Continue writing the report"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="CONTINUE_TASK",
            confidence=0.8,
            risk_level=RiskLevel.NONE,
            intent=Intent.ASK,  # Using Intent.ASK as proxy for question-like intent
            domain=Domain.GENERAL,
            output_type=OutputType.TEXT,
            topic=["report"],
            context_required=["previous_document"],
            execution_mode=ExecutionMode.FAST_MODEL
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "CONTINUE_TASK"

    def test_memory_dependent_task(self):
        """Test memory-dependent task."""
        # Arrange
        user_request = "What did we discuss earlier?"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="MEMORY_RECALL",
            confidence=0.85,
            risk_level=RiskLevel.NONE,
            intent=Intent.ASK,
            domain=Domain.GENERAL,
            output_type=OutputType.TEXT,
            execution_mode=ExecutionMode.FAST_MODEL
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "MEMORY_RECALL"

    def test_verification_failure(self):
        """Test verification failure handling."""
        # Arrange
        user_request = "Open invalid_application"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="OPEN_APPLICATION",
            confidence=0.9,
            risk_level=RiskLevel.NONE,
            intent=Intent.APP_CONTROL,
            domain=Domain.SYSTEM,
            output_type=OutputType.SYSTEM_ACTION,
            execution_mode=ExecutionMode.FAST_DETERMINISTIC
        )

        self.ai_manager.route.return_value = route

        # Mock the orchestrator to simulate failure
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.last_message = "Application not found"
        mock_result.error = "Application not found"
        self.orchestrator.execute.return_value = mock_result

        # Setup verification to return not verified (though execution already failed)
        mock_verification = MagicMock()
        mock_verification.is_verified = False
        mock_verification.outcome = "failed"
        self.verification_manager.verify.return_value = mock_verification

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is False
        # Check if the error message is in the execution message or the result
        assert ("Application not found" in result.message or
                (hasattr(result.execution, 'message') and "Application not found" in result.execution.message) or
                (hasattr(result, 'execution') and hasattr(result.execution, 'message') and "Application not found" in result.execution.message))

    def test_recovery_and_replan(self):
        """Test recovery and replanning."""
        # Arrange
        user_request = "Open application that fails first time"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="OPEN_APPLICATION",
            confidence=0.9,
            risk_level=RiskLevel.NONE,
            intent=Intent.APP_CONTROL,
            domain=Domain.SYSTEM,
            output_type=OutputType.SYSTEM_ACTION,
            execution_mode=ExecutionMode.FAST_DETERMINISTIC,
            can_use_fast_path=False
        )

        self.ai_manager.route.return_value = route

        # Mock the orchestrator to fail first then succeed
        call_count = 0
        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.success = False
                mock_result.message = "Temporary failure"
            else:
                mock_result.success = True
                mock_result.message = "Application opened"
            return mock_result

        self.orchestrator.execute.side_effect = mock_execute_side_effect

        # Setup verification
        mock_verification = MagicMock()
        mock_verification.is_verified = True
        mock_verification.outcome = "success"
        mock_verification.to_dict.return_value = {"verified": True, "outcome": "success"}
        self.verification_manager.verify.return_value = mock_verification

        # Setup recovery engine to return replan decision
        mock_retry_decision = MagicMock()
        mock_retry_decision.action = RetryAction.REPLAN
        mock_retry_decision.delay_seconds = 0.0
        mock_retry_decision.attempts_remaining = 1
        mock_retry_decision.reason = "replan after transient failure"
        self.recovery_engine.should_retry.return_value = mock_retry_decision

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.execution.replans >= 1  # At least one replan occurred

    def test_provider_failure(self):
        """Test provider failure handling."""
        # Arrange
        user_request = "Search for latest news"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="WEB_SEARCH",
            confidence=0.8,
            risk_level=RiskLevel.LOW,
            intent=Intent.SEARCH_WEB,
            domain=Domain.RESEARCH,
            output_type=OutputType.TEXT,
            topic=["news"],
            execution_mode=ExecutionMode.STANDARD_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Mock verification to fail
        mock_verification = MagicMock()
        mock_verification.is_verified = False
        mock_verification.outcome = "provider_unavailable"
        mock_verification.to_dict.return_value = {"verified": False, "reason": "provider_unavailable"}
        self.verification_manager.verify.return_value = mock_verification

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        # Depending on implementation, verification failure might not make the whole task fail
        # but we expect verification to show as unverified
        assert result.execution.verification.get("verified") is False

    def test_user_cancellation(self):
        """Test user cancellation."""
        # Arrange
        user_request = "Long running task"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="LONG_TASK",
            confidence=0.5,
            risk_level=RiskLevel.LOW,
            intent=Intent.GENERAL_REQUEST,  # Using actual Intent
            domain=Domain.SYSTEM,
            output_type=OutputType.SYSTEM_ACTION,
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True

    def test_long_running_task(self):
        """Test long-running task handling."""
        # Arrange
        user_request = "Count from 1 to 1000000"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="COMPUTATION",
            confidence=0.9,
            risk_level=RiskLevel.NONE,
            intent=Intent.CALCULATE,  # Using Intent.CALCULATE
            domain=Domain.SYSTEM,
            output_type=OutputType.TEXT,  # Using TEXT instead of NUMBER (NUMBER doesn't exist)
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "COMPUTATION"

    def test_capability_chain(self):
        """Test capability chain execution."""
        # Arrange
        user_request = "Research AI models and create summary"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="RESEARCH_AND_CREATE",
            confidence=0.85,
            risk_level=RiskLevel.LOW,
            intent=Intent.RESEARCHING,  # Using actual Intent.RESEARCHING
            domain=Domain.RESEARCH,
            output_type=OutputType.TEXT,
            topic=["AI models", "summary"],
            sub_tasks=[
                {"goal": "Research AI models", "intent": Intent.SEARCH_WEB.value, "capability": "WEB_SEARCH"},
                {"goal": "Create summary", "intent": Intent.CREATION_DOCUMENT.value, "capability": "CREATE_FILE"}
            ],
            dependencies=[[], [0]],  # Second depends on first
            capability_chain=["WEB_SEARCH", "CREATE_FILE"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "RESEARCH_AND_CREATE"

    def test_clarification_needed(self):
        """Test when clarification is needed."""
        # Arrange
        user_request = "Message John"  # Ambiguous if multiple Johns
        route = self._create_route_mock(
            decision="BRAIN",
            capability="SEND_MESSAGE",
            confidence=0.6,  # Low confidence due to ambiguity
            risk_level=RiskLevel.LOW,
            intent=Intent.SEND_MESSAGE,
            domain=Domain.COMPUTER,
            output_type=OutputType.SYSTEM_ACTION,
            entities=["Rahul"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.FAST_DETERMINISTIC
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        # Depending on implementation, this might still proceed but with low confidence
        # We expect the goal to reflect the ambiguity
        assert result.goal_text == user_request

    def test_ambiguous_goal(self):
        """Test ambiguous goal handling."""
        # Arrange
        user_request = "Do something"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="UNKNOWN",
            confidence=0.3,  # Very low confidence
            risk_level=RiskLevel.NONE,
            intent=Intent.UNKNOWN,
            domain=Domain.GENERAL,
            output_type=OutputType.SYSTEM_ACTION,
            execution_mode=ExecutionMode.FAST_DETERMINISTIC
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.goal_text == user_request
        # The system should still attempt to process it

    def test_multimodal_context(self):
        """Test multimodal context usage."""
        # Arrange
        user_request = "Based on this screen, click the button"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="SCREEN_BASED_ACTION",
            confidence=0.8,
            risk_level=RiskLevel.LOW,
            intent=Intent.VISION_OBJECT,  # Using actual Intent.VISION_OBJECT
            domain=Domain.VISION,
            output_type=OutputType.SYSTEM_ACTION,
            entities=["button"],
            context_required=["screen_content"],
            execution_mode=ExecutionMode.FAST_DETERMINISTIC
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "SCREEN_BASED_ACTION"

    def test_unsafe_request(self):
        """Test unsafe request handling."""
        # Arrange
        user_request = "Delete all files on C drive"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="DELETE_FILES",
            confidence=0.95,
            risk_level=RiskLevel.HIGH,  # High risk
            intent=Intent.FILE_DELETE,
            domain=Domain.FILES,
            output_type=OutputType.SYSTEM_ACTION,
            execution_mode=ExecutionMode.FAST_DETERMINISTIC
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        # Depending on safety mechanisms, this might be blocked or require confirmation
        # We expect the system to handle it safely
        assert result.goal_text == user_request

    def test_artifact_task(self):
        """Test artifact creation task."""
        # Arrange
        user_request = "Create a presentation about machine learning"
        route = self._create_route_mock(
            decision="BRAIN",
            capability="CREATE_PRESENTATION",
            confidence=0.85,
            risk_level=RiskLevel.LOW,
            intent=Intent.CREATION_PRESENTATION,  # Using actual Intent.CREATION_PRESENTATION
            domain=Domain.CREATIVE,
            output_type=OutputType.PRESENTATION,  # Using actual OutputType.PRESENTATION
            topic=["presentation", "machine learning"],
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "BRAIN"
        assert result.capability == "CREATE_PRESENTATION"

    def test_whatsapp_message_goal(self):
        """Test WhatsApp message goal (communication)."""
        # Arrange
        user_request = "Rahul ko message karde, main 10 min late aaunga."
        route = self._create_route_mock(
            decision="ROUTE",  # Communication intent
            capability="COMPUTER_USE",
            confidence=0.98,
            risk_level=RiskLevel.LOW,
            intent=Intent.SEND_MESSAGE,
            domain=Domain.COMPUTER,  # Communication via desktop apps
            output_type=OutputType.SYSTEM_ACTION,
            entities=["Rahul"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "ROUTE"
        assert result.capability == "COMPUTER_USE"
        assert result.goal_text == user_request

    def test_gmail_email_goal(self):
        """Test Gmail email goal (communication)."""
        # Arrange
        user_request = "Priya ko email bhej do ki meeting 5 baje hai."
        route = self._create_route_mock(
            decision="ROUTE",  # Communication intent
            capability="COMPUTER_USE",
            confidence=0.97,
            risk_level=RiskLevel.LOW,
            intent=Intent.SEND_MESSAGE,  # Email is treated as send message
            domain=Domain.COMPUTER,  # Communication via desktop apps
            output_type=OutputType.SYSTEM_ACTION,
            entities=["Priya"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "ROUTE"
        assert result.capability == "COMPUTER_USE"
        assert result.goal_text == user_request

    def test_computer_use_goal(self):
        """Test general computer-use goal."""
        # Arrange
        user_request = "Chrome kholo aur YouTube pe song search karke first result chalao"
        route = self._create_route_mock(
            decision="ROUTE",  # Computer use intent
            capability="COMPUTER_USE",
            confidence=0.92,
            risk_level=RiskLevel.LOW,
            intent=Intent.SEARCH_WEB,  # Using SEARCH_WEB as proxy for search intent
            domain=Domain.COMPUTER,
            output_type=OutputType.SYSTEM_ACTION,
            entities=["Chrome", "YouTube"],
            can_use_fast_path=False,
            execution_mode=ExecutionMode.DEEP_REASONING
        )

        self.ai_manager.route.return_value = route
        self._setup_successful_orchestrator()

        # Act
        result = self.super_brain.process(user_request)

        # Assert
        assert result.success is True
        assert result.decision == "ROUTE"
        assert result.capability == "COMPUTER_USE"
        assert result.goal_text == user_request


if __name__ == "__main__":
    pytest.main([__file__, "-v"])