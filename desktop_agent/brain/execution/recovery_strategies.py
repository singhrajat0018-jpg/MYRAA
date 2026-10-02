"""
MYRAA Cognitive Engine
Recovery Strategies

Defines reason-driven recovery strategies for EPIC-14D verification failures.
Enhanced for EPIC-14E with recovery limits and circuit breaker patterns.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
import time
import threading


class RecoveryAction(Enum):
    """Possible recovery actions when verification fails."""
    RETRY = "retry"                           # Simple retry with same parameters
    RE_RESOLVE_TARGET = "re_resolve_target"   # Re-resolve the target before retrying
    ADJUST_PARAMETERS = "adjust_parameters"   # Modify action parameters based on failure
    FALLBACK_ACTION = "fallback_action"       # Try an alternative approach
    WAIT_AND_RETRY = "wait_and_retry"         # Wait before retrying
    REQUEST_CLARIFICATION = "request_clarification"  # Ask user for clarification
    ABORT = "abort"                           # Give up and abort the action


@dataclass
class RecoveryStrategy:
    """
    Defines a recovery strategy for a specific type of failure.
    """
    failure_category: str                    # e.g., "target_not_found", "verification_failed"
    action: RecoveryAction                   # What to do
    description: str                         # Human-readable description
    max_attempts: int = 3                    # Maximum times to apply this strategy
    delay_seconds: float = 1.0               # Delay before applying strategy
    parameters: Dict[str, Any] = None        # Strategy-specific parameters

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class RecoveryStrategyManager:
    """
    Manages recovery strategies and selects appropriate actions based on failures.
    Enhanced for EPIC-14E with recovery limits and circuit breaker patterns.
    """

    def __init__(self):
        """Initialize the recovery strategy manager with default strategies."""
        self.strategies: Dict[str, List[RecoveryStrategy]] = {}
        # Circuit breaker state tracking
        self._circuit_breaker_state: Dict[str, Dict[str, Any]] = {}
        self._circuit_breaker_lock = threading.RLock()
        # Recovery limits tracking
        self._recovery_attempts: Dict[str, int] = {}
        self._recovery_attempts_lock = threading.RLock()
        self._initialize_default_strategies()

    def _initialize_default_strategies(self):
        """Set up default recovery strategies for common failure types."""

        # Target not found or disappeared
        self.add_strategy(RecoveryStrategy(
            failure_category="target_not_found",
            action=RecoveryAction.RE_RESOLVE_TARGET,
            description="Re-resolve target as it may have moved or disappeared",
            max_attempts=3,
            delay_seconds=0.5
        ))

        # Target not visible
        self.add_strategy(RecoveryStrategy(
            failure_category="target_not_visible",
            action=RecoveryAction.WAIT_AND_RETRY,
            description="Wait for target to become visible",
            max_attempts=3,
            delay_seconds=1.0
        ))

        # Target not enabled
        self.add_strategy(RecoveryStrategy(
            failure_category="target_not_enabled",
            action=RecoveryAction.WAIT_AND_RETRY,
            description="Wait for target to become enabled",
            max_attempts=3,
            delay_seconds=1.0
        ))

        # Text mismatch
        self.add_strategy(RecoveryStrategy(
            failure_category="text_mismatch",
            action=RecoveryAction.RETRY,
            description="Retry typing with potential correction",
            max_attempts=2,
            delay_seconds=0.5
        ))

        # Browser navigation failed
        self.add_strategy(RecoveryStrategy(
            failure_category="browser_navigation_failed",
            action=RecoveryAction.FALLBACK_ACTION,
            description="Try alternative navigation approach",
            max_attempts=2,
            delay_seconds=2.0
        ))

        # Application state failed
        self.add_strategy(RecoveryStrategy(
            failure_category="application_state_failed",
            action=RecoveryAction.WAIT_AND_RETRY,
            description="Wait for application to reach expected state",
            max_attempts=3,
            delay_seconds=2.0
        ))

        # Target stale
        self.add_strategy(RecoveryStrategy(
            failure_category="target_stale",
            action=RecoveryAction.RE_RESOLVE_TARGET,
            description="Target information is outdated, re-resolve",
            max_attempts=2,
            delay_seconds=0.5
        ))

        # Low confidence target
        self.add_strategy(RecoveryStrategy(
            failure_category="low_confidence_target",
            action=RecoveryAction.REQUEST_CLARIFICATION,
            description="Target confidence too low, request clarification",
            max_attempts=1,
            delay_seconds=0.0
        ))

        # Invalid target
        self.add_strategy(RecoveryStrategy(
            failure_category="invalid_target",
            action=RecoveryAction.RE_RESOLVE_TARGET,
            description="Target failed validation, re-resolve",
            max_attempts=2,
            delay_seconds=0.5
        ))

        # Permission denied
        self.add_strategy(RecoveryStrategy(
            failure_category="permission_denied",
            action=RecoveryAction.ABORT,
            description="Action not permitted by policies",
            max_attempts=1,
            delay_seconds=0.0
        ))

        # Generic validation failed
        self.add_strategy(RecoveryStrategy(
            failure_category="validation_failed",
            action=RecoveryAction.RETRY,
            description="Retry after validation failure",
            max_attempts=2,
            delay_seconds=1.0
        ))

        # Generic action execution failed
        self.add_strategy(RecoveryStrategy(
            failure_category="action_execution_failed",
            action=RecoveryAction.RETRY,
            description="Retry action execution",
            max_attempts=3,
            delay_seconds=1.0
        ))

        # Generic verification failed
        self.add_strategy(RecoveryStrategy(
            failure_category="verification_failed",
            action=RecoveryAction.RETRY,
            description="Retry after verification failure",
            max_attempts=2,
            delay_seconds=1.0
        ))

    def add_strategy(self, strategy: RecoveryStrategy):
        """Add a recovery strategy for a failure category."""
        if strategy.failure_category not in self.strategies:
            self.strategies[strategy.failure_category] = []
        self.strategies[strategy.failure_category].append(strategy)

    def _is_circuit_breaker_open(self, failure_category: str) -> bool:
        """
        Check if circuit breaker is open for a failure category.

        Args:
            failure_category: The category of failure

        Returns:
            True if circuit breaker is open (should block recovery attempts)
        """
        with self._circuit_breaker_lock:
            breaker_state = self._circuit_breaker_state.get(failure_category, {})
            if not breaker_state:
                return False

            # Check if breaker is open and if timeout has passed
            if breaker_state.get('state') == 'open':
                open_time = breaker_state.get('opened_at', 0)
                timeout = breaker_state.get('timeout', 60.0)  # Default 60 second timeout
                if time.time() - open_time < timeout:
                    return True  # Still open
                else:
                    # Timeout passed, move to half-open state
                    breaker_state['state'] = 'half-open'
                    return False

            return False  # Closed or half-open

    def _record_failure(self, failure_category: str):
        """
        Record a failure for circuit breaker tracking.

        Args:
            failure_category: The category of failure
        """
        with self._circuit_breaker_lock:
            if failure_category not in self._circuit_breaker_state:
                self._circuit_breaker_state[failure_category] = {
                    'failure_count': 0,
                    'state': 'closed',  # closed, open, half-open
                    'opened_at': 0,
                    'timeout': 60.0,  # seconds to wait before trying half-open
                    'failure_threshold': 5,  # failures before opening circuit
                }

            state = self._circuit_breaker_state[failure_category]
            state['failure_count'] += 1

            # Open circuit breaker if threshold exceeded
            if state['state'] == 'closed' and state['failure_count'] >= state['failure_threshold']:
                state['state'] = 'open'
                state['opened_at'] = time.time()
                # Log circuit breaker opening (in real implementation, use logger)
                pass

    def _record_success(self, failure_category: str):
        """
        Record a success for circuit breaker tracking.

        Args:
            failure_category: The category of failure
        """
        with self._circuit_breaker_lock:
            if failure_category in self._circuit_breaker_state:
                state = self._circuit_breaker_state[failure_category]
                if state['state'] == 'half-open':
                    # Reset to closed on success in half-open state
                    state['state'] = 'closed'
                    state['failure_count'] = 0
                elif state['state'] == 'open':
                    # Shouldn't happen, but reset if it does
                    state['state'] = 'closed'
                    state['failure_count'] = 0

    def _increment_recovery_attempts(self, action_id: str) -> int:
        """
        Increment and return recovery attempt count for an action.

        Args:
            action_id: Unique identifier for the action

        Returns:
            Current attempt count
        """
        with self._recovery_attempts_lock:
            current = self._recovery_attempts.get(action_id, 0)
            self._recovery_attempts[action_id] = current + 1
            return self._recovery_attempts[action_id]

    def _get_recovery_attempts(self, action_id: str) -> int:
        """
        Get current recovery attempt count for an action.

        Args:
            action_id: Unique identifier for the action

        Returns:
            Current attempt count
        """
        with self._recovery_attempts_lock:
            return self._recovery_attempts.get(action_id, 0)

    def _reset_recovery_attempts(self, action_id: str):
        """
        Reset recovery attempt count for an action.

        Args:
            action_id: Unique identifier for the action
        """
        with self._recovery_attempts_lock:
            if action_id in self._recovery_attempts:
                del self._recovery_attempts[action_id]

    def get_recovery_strategy(
        self,
        failure_category: str,
        attempt_count: int,
        action_id: Optional[str] = None
    ) -> Optional[RecoveryStrategy]:
        """
        Get the appropriate recovery strategy for a failure and attempt count.
        Enhanced for EPIC-14E with circuit breaker and recovery limits.

        Args:
            failure_category: The category of failure
            attempt_count: How many times we've already attempted recovery
            action_id: Optional unique identifier for the action (for recovery limits)

        Returns:
            RecoveryStrategy if available, None if no more attempts allowed or circuit breaker open
        """
        # EPIC-14E: Check circuit breaker
        if self._is_circuit_breaker_open(failure_category):
            return None  # Circuit breaker is open, block recovery attempts

        # EPIC-14E: Check recovery limits if action_id provided
        if action_id is not None:
            recovery_attempts = self._get_recovery_attempts(action_id)
            # Define global recovery limit (could be made configurable)
            MAX_GLOBAL_RECOVERY_ATTEMPTS = 10
            if recovery_attempts >= MAX_GLOBAL_RECOVERY_ATTEMPTS:
                return None  # Exceeded global recovery limit

        if failure_category not in self.strategies:
            # Default strategy for unknown failure types
            strategies = [RecoveryStrategy(
                failure_category=failure_category,
                action=RecoveryAction.RETRY,
                description="Default retry strategy",
                max_attempts=3,
                delay_seconds=1.0
            )]
        else:
            strategies = self.strategies[failure_category]

        # Filter strategies by max attempts
        available_strategies = [
            s for s in strategies
            if attempt_count < s.max_attempts
        ]

        if not available_strategies:
            return None

        # Return the first available strategy (could be enhanced to choose best)
        return available_strategies[0]

    def apply_recovery_strategy(
        self,
        strategy: RecoveryStrategy,
        action: Any,  # ComputerAction
        context: Any,  # PlannerContext
        attempt_count: int,
        action_id: Optional[str] = None,
        failure_category: Optional[str] = None
    ) -> bool:
        """
        Apply a recovery strategy to an action.
        Enhanced for EPIC-14E with circuit breaker and recovery tracking.

        Args:
            strategy: The recovery strategy to apply
            action: The action to modify
            context: Execution context
            attempt_count: Current attempt number
            action_id: Optional unique identifier for the action (for recovery limits)
            failure_category: Optional failure category (for circuit breaker tracking)

        Returns:
            True if recovery was applied and action should be retried, False to abort
        """
        if strategy.action == RecoveryAction.ABORT:
            return False

        # Apply strategy-specific logic here
        # For now, we'll just return True to indicate retry should happen
        # In a full implementation, this would modify the action based on strategy

        # Apply delay if specified
        if strategy.delay_seconds > 0:
            time.sleep(strategy.delay_seconds)

        # Record attempt for recovery limits if action_id provided
        if action_id is not None:
            self._increment_recovery_attempts(action_id)

        # Record failure for circuit breaker tracking if failure_category provided
        if failure_category is not None:
            self._record_failure(failure_category)

        return True

    def record_recovery_success(self, failure_category: str):
        """
        Record a successful recovery for circuit breaker tracking.

        Args:
            failure_category: The category of failure that was successfully recovered from
        """
        if failure_category is not None:
            self._record_success(failure_category)