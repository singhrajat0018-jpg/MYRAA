"""
MYRAA Cognitive Engine
Action Executor

Executes computer actions with closed-loop act→observe→verify functionality.
Enhanced for EPIC-14D with failure classification, reason-driven recovery,
and self-correction capabilities.
"""

from __future__ import annotations

import time
import logging
import random
from typing import Optional, Tuple, Any, Dict, List
from dataclasses import dataclass

from ..planner.models.computer_action import ComputerAction, ValidationStatus, VerificationStatus
from ..planner.models.models import PlannerContext
from .action_validator import ActionValidator, ValidationResult
from .action_verifier import ActionVerifier, VerificationResult
from ..perception import Perception
from desktop_agent.brain.blackboard.blackboard import Blackboard
from desktop_agent.brain.planner.execution.executor_bridge import ExecutorBridge
from desktop_agent.brain.planner.execution.action_adapters.adapter_executor import AdapterExecutor
from desktop_agent.brain.planner.models.action_types import ActionType
from .verification_enhancements import EnhancedVerificationResult, VerificationSignalType
from .expected_state import get_expected_state_for_action
from .failure_classifier import FailureClassifier
from .recovery_strategies import RecoveryStrategy, RecoveryAction, RecoveryStrategyManager
from desktop_agent.brain import metrics


logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of action execution."""
    success: bool
    action: ComputerAction
    message: str
    execution_time: float = 0.0
    validation_result: Optional[ValidationResult] = None
    verification_result: Optional[VerificationResult] = None
    retry_count: int = 0

    def __post_init__(self):
        if self.validation_result is None:
            self.validation_result = ValidationResult(False, ValidationStatus.INVALID, "Not validated")
        if self.verification_result is None:
            self.verification_result = VerificationResult(False, VerificationStatus.PENDING, "Not verified")


class ActionExecutor:
    """
    Executes computer actions with closed-loop act→observe→verify functionality.

    Implements the EPIC-14C execution pipeline:
    1. Validate action (pre-execution checks)
    2. Execute action (through existing adapter system)
    3. Verify action (post-execution checks)
    4. Handle retries and re-resolution as needed
    """

    def __init__(
        self,
        perception: Perception,
        validator: ActionValidator,
        verifier: ActionVerifier,
        executor_bridge: ExecutorBridge,
        adapter_executor: AdapterExecutor,
        blackboard: Blackboard
    ):
        """
        Initialize the action executor.

        Args:
            perception: Perception layer for screen state access
            validator: Action validator for pre-execution checks
            verifier: Action verifier for post-execution checks
            executor_bridge: Executor bridge for running actions
            adapter_executor: Adapter executor for tool execution
            blackboard: Blackboard for state management and idempotency
        """
        self.perception = perception
        self.validator = validator
        self.verifier = verifier
        self.executor_bridge = executor_bridge
        self.adapter_executor = adapter_executor
        self.blackboard = blackboard
        self.logger = logging.getLogger(__name__)

        # Execution settings
        self.max_retries = 3
        self.retry_delay_base = 1.0  # Base delay for exponential backoff
        self.action_timeout = 30.0   # Timeout for action execution

        # EPIC-14E: Recovery system with circuit breaker and recovery limits
        self.recovery_manager = RecoveryStrategyManager()
        # Global limit for recovery attempts per action (to prevent infinite recovery loops)
        self._max_global_recovery_attempts = 10

    def execute_action(
        self,
        action: ComputerAction,
        context: Optional[PlannerContext] = None
    ) -> ExecutionResult:
        """
        Execute a computer action with closed-loop act→observe→verify functionality.
        Enhanced for EPIC-14D with failure classification, reason-driven recovery,
        and self-correction capabilities.
        Enhanced for EPIC-14E with idempotency protection.

        Args:
            action: The computer action to execute
            context: Optional planner context for additional validation/verification

        Returns:
            ExecutionResult containing the outcome of the action execution
        """
        start_time = time.time()
        self.logger.info(f"Executing action: {action.action_type.value} on target {action.target.text}")

        # Generate idempotency key for this action
        action_id = f"{action.action_type.value}:{action.target.id}"
        task_id = getattr(context, 'task_id', 'unknown') if context else 'unknown'
        # EPIC-14E: Get task deadline for time budgeting
        task_deadline = getattr(context, 'task_deadline', None) if context else None

        # Check for idempotency - if this action has already been executed, return cached result
        idempotent_result = self.blackboard.get_idempotency_result(action_id, task_id)
        if idempotent_result[0]:
            self.logger.info(f"Action {action_id} is idempotent, returning cached result")
            result = ExecutionResult(
                success=True,
                action=action,
                message="Action already executed (idempotent)",
                execution_time=0.0,
                verification_result=VerificationResult(True, VerificationStatus.VERIFIED_SUCCESS, "Idempotent execution"),
                retry_count=action.retry_count
            )
            # If we had a cached result, we could use it here
            return result

        # Initialize result
        result = ExecutionResult(
            success=False,
            action=action,
            message="Execution not started",
            execution_time=0.0
        )

        try:
            # Initialize recovery systems
            failure_classifier = FailureClassifier()
            # EPIC-14E: Track if action had any failure requiring recovery
            action_had_failure = False

            # Loop for retries with enhanced recovery logic
            for attempt in range(self.max_retries + 1):
                # EPIC-14E: Check task deadline before each attempt
                if task_deadline is not None and time.time() >= task_deadline:
                    result.success = False
                    result.message = f"Task deadline exceeded"
                    result.execution_time = time.time() - start_time
                    return result

                action.retry_count = attempt
                self.logger.debug(f"Action execution attempt {attempt + 1}/{self.max_retries + 1}")

                # Step 1: Validate action (OBSERVE → RESOLVE → VALIDATE)
                validation_start = time.time()
                validation_result = self._validate_action(action, context)
                validation_time = time.time() - validation_start

                # Record validation metrics
                from desktop_agent.brain import metrics
                metrics.increment_counter(f"validations_{action_type_str}_{'success' if validation_result.is_valid else 'failure'}")
                metrics.add_to_histogram(f"validation_latency_{action_type_str}", validation_time)

                if not validation_result.is_valid:
                    # Validation failed - classify and apply recovery strategy
                    # Record failure for action_execution subsystem
                    from desktop_agent.brain.failure_containment import failure_containment_manager
                    failure_containment_manager.record_failure('action_execution')

                    failure_class = failure_classifier.classify_validation_failure(
                        validation_result, action.action_type, action.parameters
                    )

                    # Mark that this action had a failure requiring recovery
                    action_had_failure = True

                    # Non-retryable validation failures: abort immediately.
                    # E.g., permission denied, unknown target, invalid parameters.
                    _NON_RETRYABLE_VALIDATION = (
                        "permission", "denied", "unauthorized",
                        "unknown tool", "not registered",
                    )
                    val_msg = (getattr(validation_result, 'message', '') or '').lower()
                    is_non_retryable_val = any(pat in val_msg for pat in _NON_RETRYABLE_VALIDATION)
                    if is_non_retryable_val:
                        self.logger.error(
                            "Non-retryable validation failure (zero retries): %s",
                            validation_result.message)
                        result.success = False
                        result.message = f"Non-retryable validation: {validation_result.message}"
                        result.validation_result = validation_result
                        result.failure_classification = failure_class
                        result.recovery_action_attempted = "abort"
                        result.execution_time = time.time() - start_time
                        result.retry_count = attempt
                        return result

                    # Generate action ID for recovery tracking
                    action_id = f"{action.action_type.value}:{action.target.id}"
                    recovery_action = self._determine_recovery_action(
                        failure_class, attempt, action, context, action_id=action_id
                    )

                    if recovery_action == RecoveryAction.RETRY and attempt < self.max_retries:
                        self.logger.info(f"Validation failed, will retry: {validation_result.message}")
                        action.prepare_for_retry()
                        time.sleep(self._calculate_retry_delay(attempt))
                        continue
                    elif recovery_action == RecoveryAction.RE_RESOLVE_TARGET and attempt < self.max_retries:
                        self.logger.info(f"Validation failed, will re-resolve target and retry: {validation_result.message}")
                        # Invalidate target to force re-resolution
                        action.target.invalidate()
                        action.prepare_for_retry()
                        time.sleep(self._calculate_retry_delay(attempt))
                        continue
                    else:
                        # Max retries reached or no recovery possible
                        result.success = False
                        result.message = f"Validation failed after {attempt + 1} attempts: {validation_result.message}"
                        result.validation_result = validation_result
                        result.failure_classification = failure_class
                        result.recovery_action_attempted = recovery_action.value if hasattr(recovery_action, 'value') else str(recovery_action)
                        result.execution_time = time.time() - start_time
                        result.retry_count = attempt
                        return result

                # Validation passed
                result.validation_result = validation_result

                # Step 2: Execute action (ACT)
                execution_start = time.time()
                execution_result = self._execute_action_internal(action, context)
                execution_time = time.time() - execution_start

                # Record execution metrics
                from desktop_agent.brain import metrics
                metrics.increment_counter(f"actions_{action_type_str}_{'success' if execution_result['success'] else 'failure'}")
                metrics.add_to_histogram(f"action_latency_{action_type_str}", execution_time)

                if not execution_result.success:
                    # Execution failed - classify and apply recovery strategy
                    error_msg = execution_result.get('error', 'Unknown execution error')

                    # Non-retryable errors: configuration/contract errors must
                    # terminate immediately (zero retries).  These indicate a
                    # bug in the planner/tool-selection, not a transient fault.
                    _NON_RETRYABLE_PATTERNS = (
                        "unknown tool", "unknown_tool", "not found",
                        "invalid tool", "not registered", "permission denied",
                        "authorization", "unauthorized",
                    )
                    error_lower = error_msg.lower()
                    is_non_retryable = any(pat in error_lower for pat in _NON_RETRYABLE_PATTERNS)

                    failure_class = failure_classifier.classify_validation_failure(
                        type('obj', (object,), {
                            'is_valid': False,
                            'should_re_resolve': False,
                            'status': type('obj', (object,), {'value': 'execution_failed'})(),
                            'message': error_msg
                        }),
                        action.action_type,
                        action.parameters
                    )

                    # Mark that this action had a failure requiring recovery
                    action_had_failure = True

                    # Configuration/contract errors: abort immediately, no retries.
                    if is_non_retryable:
                        self.logger.error(
                            "Non-retryable execution error (zero retries): %s", error_msg)
                        result.success = False
                        result.message = f"Non-retryable error: {error_msg}"
                        result.execution_time = time.time() - start_time
                        result.retry_count = attempt
                        result.failure_classification = failure_class
                        result.recovery_action_attempted = "abort"
                        return result

                    # Generate action ID for recovery tracking
                    action_id = f"{action.action_type.value}:{action.target.id}"
                    recovery_action = self._determine_recovery_action(
                        failure_class, attempt, action, context, action_id=action_id
                    )

                    if recovery_action == RecoveryAction.RETRY and attempt < self.max_retries:
                        self.logger.info(f"Execution failed, will retry: {error_msg}")
                        action.prepare_for_retry()
                        time.sleep(self._calculate_retry_delay(attempt))
                        continue
                    else:
                        # Max retries reached or no recovery possible
                        result.success = False
                        result.message = f"Execution failed after {attempt + 1} attempts: {execution_result.get('error', 'Unknown error')}"
                        result.execution_time = time.time() - start_time
                        result.retry_count = attempt
                        result.failure_classification = failure_class
                        result.recovery_action_attempted = recovery_action.value if hasattr(recovery_action, 'value') else str(recovery_action)
                        return result

                # Execution succeeded
                action.mark_as_executed(execution_result)

                # Step 3: Verify action (OBSERVE → VERIFY)
                verification_start = time.time()
                verification_result = self._verify_action_enhanced(action, context)
                verification_time = time.time() - verification_start

                # Record verification metrics
                from desktop_agent.brain import metrics
                metrics.increment_counter(f"verifications_{action_type_str}_{'success' if verification_result.is_success else 'failure'}")
                metrics.add_to_histogram(f"verification_latency_{action_type_str}", verification_time)

                if not verification_result.is_success:
                    # Verification failed - classify and apply recovery strategy
                    failure_class = failure_classifier.classify_failure(
                        verification_result, action.action_type, action.parameters
                    )

                    # Generate action ID for recovery tracking
                    action_id = f"{action.action_type.value}:{action.target.id}"
                    recovery_action = self._determine_recovery_action(
                        failure_class, attempt, action, context, action_id=action_id
                    )

                    if recovery_action == RecoveryAction.RETRY and attempt < self.max_retries:
                        self.logger.info(f"Verification failed, will retry: {verification_result.message}")
                        action.prepare_for_retry()
                        time.sleep(self._calculate_retry_delay(attempt))
                        continue
                    elif recovery_action == RecoveryAction.RE_RESOLVE_TARGET and attempt < self.max_retries:
                        self.logger.info(f"Verification failed, will re-resolve target and retry: {verification_result.message}")
                        # Invalidate target to force re-resolution
                        action.target.invalidate()
                        action.prepare_for_retry()
                        time.sleep(self._calculate_retry_delay(attempt))
                        continue
                    elif recovery_action == RecoveryAction.FALLBACK_ACTION and attempt < self.max_retries:
                        self.logger.info(f"Verification failed, will try fallback action: {verification_result.message}")
                        # Try fallback action - for now, we'll just retry with original action
                        # In a full implementation, this would try an alternative approach
                        action.prepare_for_retry()
                        time.sleep(self._calculate_retry_delay(attempt))
                        continue
                    else:
                        # Max retries reached or no recovery possible
                        result.success = False
                        result.message = f"Verification failed after {attempt + 1} attempts: {verification_result.message}"
                        result.execution_time = time.time() - start_time
                        result.validation_result = validation_result
                        # Convert enhanced verification result to legacy format for compatibility
                        if hasattr(verification_result, 'to_legacy_result'):
                            result.verification_result = verification_result.to_legacy_result()
                        else:
                            result.verification_result = verification_result
                        result.failure_classification = failure_class
                        result.recovery_action_attempted = recovery_action.value if hasattr(recovery_action, 'value') else str(recovery_action)
                        result.retry_count = attempt
                        return result

                # Verification passed - success!
                result.success = True
                result.message = f"Action executed and verified successfully on attempt {attempt + 1}"
                result.execution_time = time.time() - start_time
                result.validation_result = validation_result
                # Convert enhanced verification result to legacy format for compatibility
                if hasattr(verification_result, 'to_legacy_result'):
                    result.verification_result = verification_result.to_legacy_result()
                else:
                    result.verification_result = verification_result
                result.retry_count = attempt
                return result

            # This shouldn't be reached due to the loop logic, but just in case
            result.success = False
            result.message = "Action execution failed after all retries"
            result.execution_time = time.time() - start_time
            return result

        except Exception as e:
            self.logger.error(f"Error during action execution: {e}", exc_info=True)
            result.success = False
            result.message = f"Execution error: {str(e)}"
            result.execution_time = time.time() - start_time
            return result

    def _validate_action(
        self,
        action: ComputerAction,
        context: Optional[PlannerContext]
    ) -> ValidationResult:
        """Validate action using the action validator."""
        return self.validator.validate_action(action, context)

    def _execute_action_internal(
        self,
        action: ComputerAction,
        context: Optional[PlannerContext]
    ) -> Dict[str, Any]:
        """
        Execute action through the existing adapter system.

        Converts ComputerAction to the format expected by the executor bridge.
        """
        try:
            # Convert ComputerAction to PlanStep-like format for the executor
            from desktop_agent.brain.planner.models.plan_step import PlanStep
            from desktop_agent.brain.planner.models.models import StepStatus

            # Create a temporary plan step for execution
            step = PlanStep(
                id=int(time.time() * 1000000) % 1000000,  # Generate unique ID
                name=f"{action.action_type.value}_{action.target.text[:20]}",
                action=action.action_type,
                description=f"EPIC-14C action: {action.action_type.value} on {action.target.text}",
                parameters=action.parameters.copy(),
                status=StepStatus.PENDING
            )

            # Add validated click point if available from validation
            if "validated_click_point" in action.parameters:
                step.parameters.update({
                    "x": action.parameters["validated_click_point"][0],
                    "y": action.parameters["validated_click_point"][1]
                })

            # Execute through the adapter executor
            # The adapter executor expects action_type and parameters
            result = self.adapter_executor.execute(
                action.action_type,
                step.parameters
            )

            # The adapter executor returns a dict or raises an exception
            if isinstance(result, dict) and "error" not in result:
                return {"success": True, "result": result}
            else:
                error_msg = result.get("error", "Unknown execution error") if isinstance(result, dict) else str(result)
                return {"success": False, "error": error_msg}

        except Exception as e:
            self.logger.error(f"Error in internal action execution: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _verify_action(
        self,
        action: ComputerAction,
        context: Optional[PlannerContext]
    ) -> VerificationResult:
        """Verify action using the action verifier."""
        return self.verifier.verify_action(action, context)

    def _verify_action_enhanced(
        self,
        action: ComputerAction,
        context: Optional[PlannerContext]
    ) -> Any:
        """
        Verify action using enhanced verification with multi-signal analysis.
        Falls back to legacy verifier if enhanced verification not available.
        """
        # Try to get screen state before and after for enhanced verification
        screen_state_before = None
        screen_state_after = None

        try:
            # Get screen state after action (we need before state too for comparison)
            # For now, we'll use the verifier's approach and enhance it
            legacy_result = self.verifier.verify_action(action, context)

            # If we have an enhanced verifier, use it
            if hasattr(self.verifier, 'verify_action_enhanced'):
                return self.verifier.verify_action_enhanced(action, context)
            else:
                # Convert legacy result to enhanced format
                return self._convert_to_enhanced_verification_result(
                    legacy_result, action, context
                )
        except Exception as e:
            self.logger.error(f"Error in enhanced verification: {e}", exc_info=True)
            # Fall back to legacy verification
            return self.verifier.verify_action(action, context)

    def _convert_to_enhanced_verification_result(
        self,
        legacy_result: VerificationResult,
        action: ComputerAction,
        context: Optional[PlannerContext]
    ) -> Any:
        """
        Convert a legacy VerificationResult to an EnhancedVerificationResult.
        """
        # Import locally to avoid circular dependencies
        from .verification_enhancements import EnhancedVerificationResult, VerificationSignal

        # Create basic signals from legacy result
        signals = []

        if legacy_result.is_success:
            signals.append(VerificationSignal(
                signal_type=VerificationSignalType.STATE_EXISTENCE,
                is_success=True,
                confidence=0.8,
                message="Legacy verification succeeded"
            ))
        else:
            signals.append(VerificationSignal(
                signal_type=VerificationSignalType.STATE_EXISTENCE,
                is_success=False,
                confidence=0.7,
                message=legacy_result.message
            ))

        # Create enhanced result
        enhanced_result = EnhancedVerificationResult(
            is_success=legacy_result.is_success,
            overall_confidence=0.75 if legacy_result.is_success else 0.6,
            signals=signals,
            message=legacy_result.message,
            verification_time=getattr(legacy_result, 'verification_time', 0.0)
        )

        return enhanced_result

    def _determine_recovery_action(
        self,
        failure_class: Any,
        attempt: int,
        action: ComputerAction,
        context: Optional[PlannerContext],
        action_id: Optional[str] = None
    ) -> Any:
        """
        Determine what recovery action to take based on failure classification.
        Enhanced for EPIC-14E with recovery limits and circuit breaker awareness.
        """
        # Import locally to avoid circular dependencies
        from .recovery_strategies import RecoveryAction

        # If we've exhausted retries, don't recover
        if attempt >= self.max_retries:
            return RecoveryAction.ABORT

        # Check if this is a destructive/high-risk action that should not be auto-retried
        # Import ActionType locally to avoid circular imports
        from ..planner.models.action_types import ActionType
        if action.action_type in [ActionType.DELETE_FILE, ActionType.EXECUTE_POWER_ACTION]:
            # Don't auto-retry destructive actions as they require explicit confirmation
            return RecoveryAction.ABORT

        # Use the failure classifier's suggested recovery
        suggested = getattr(failure_class, 'suggested_recovery', '').lower()

        # Map suggested recovery to our RecoveryAction enum for backward compatibility
        if 're_resolve' in suggested or 're-resolve' in suggested:
            recovery_action = RecoveryAction.RE_RESOLVE_TARGET
        elif 'adjust' in suggested or 'parameter' in suggested:
            recovery_action = RecoveryAction.ADJUST_PARAMETERS
        elif 'fallback' in suggested:
            recovery_action = RecoveryAction.FALLBACK_ACTION
        elif 'wait' in suggested:
            recovery_action = RecoveryAction.WAIT_AND_RETRY
        elif 'abort' in suggested or 'cancel' in suggested:
            recovery_action = RecoveryAction.ABORT
        else:
            # Default to retry for most failures
            recovery_action = RecoveryAction.RETRY

        # EPIC-14E: Apply circuit breaker and recovery limits through recovery manager
        # Get the appropriate strategy from our enhanced recovery manager
        failure_category = getattr(failure_class, 'category', 'unknown')
        strategy = self.recovery_manager.get_recovery_strategy(
            failure_category,
            attempt,
            action_id
        )

        if strategy is not None:
            return strategy.action
        else:
            # If no strategy available (circuit breaker open or limit exceeded), abort
            return RecoveryAction.ABORT

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt using exponential backoff."""
        if attempt < 0:
            return 0.0
        delay = self.retry_delay_base * (2 ** attempt)
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0.1, 0.3) * delay
        return delay + jitter

    def execute_action_plan(
        self,
        actions: list[ComputerAction],
        context: Optional[PlannerContext] = None
    ) -> list[ExecutionResult]:
        """
        Execute a list of computer actions sequentially.

        Args:
            actions: List of computer actions to execute
            context: Optional planner context

        Returns:
            List of ExecutionResults for each action
        """
        results = []
        for action in actions:
            self.logger.info(f"Executing action {len(results) + 1}/{len(actions)}: {action.action_type.value}")
            result = self.execute_action(action, context)
            results.append(result)

            # If an action fails critically, we might want to stop
            if not result.success and action.action_type in [
                ActionType.DELETE_FILE,
                ActionType.EXECUTE_POWER_ACTION
            ]:
                self.logger.warning("Critical action failed, stopping action plan execution")
                break

        return results