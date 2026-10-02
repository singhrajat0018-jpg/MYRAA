"""
MYRAA Cognitive Engine
Failure Classification System

Classifies verification failures for reason-driven recovery strategies in EPIC-14D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .verification_enhancements import VerificationSignal, VerificationSignalType


@dataclass
class FailureClassification:
    """
    Classifies a verification failure for reason-driven recovery.
    """
    # Primary failure category
    category: str  # e.g., "target_not_found", "action_failed", "verification_failed"

    # Specific sub-category or reason
    reason: str

    # Human-readable description
    description: str

    # Confidence in this classification (0.0 to 1.0)
    confidence: float = 1.0

    # Suggested recovery strategy
    suggested_recovery: str = ""  # e.g., "re_resolve_target", "adjust_click_point"

    # Metadata useful for recovery
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Associated verification signals that led to this classification
    associated_signals: List[VerificationSignal] = field(default_factory=list)


class FailureClassifier:
    """
    Classifies verification failures to enable reason-driven recovery.

    Analyzes verification results to determine the root cause of failure
    and suggest appropriate recovery strategies.
    """

    def __init__(self):
        """Initialize the failure classifier."""
        pass

    def classify_failure(
        self,
        verification_result: Any,  # EnhancedVerificationResult or similar
        action_type: str,
        action_parameters: Dict[str, Any],
        target_info: Optional[Dict[str, Any]] = None
    ) -> FailureClassification:
        """
        Classify a verification failure based on the verification result.

        Args:
            verification_result: Result of action verification
            action_type: Type of action that was attempted
            action_parameters: Parameters used for the action
            target_info: Information about the target (if available)

        Returns:
            FailureClassification with category, reason, and suggested recovery
        """
        # Handle case where verification succeeded (shouldn't happen in failure classification)
        if getattr(verification_result, 'is_success', False):
            return FailureClassification(
                category="no_failure",
                reason="Verification succeeded",
                description="Action verification passed",
                confidence=1.0,
                suggested_recovery="none"
            )

        # Analyze verification signals to determine failure type
        signals = getattr(verification_result, 'signals', [])
        failed_signals = [s for s in signals if not getattr(s, 'is_success', True)]

        if not failed_signals:
            # No specific signals failed - generic failure
            return FailureClassification(
                category="verification_failed",
                reason="Unknown verification failure",
                description="Action verification failed without specific signal information",
                confidence=0.5,
                suggested_recovery="retry_action",
                associated_signals=signals
            )

        # Check for specific failure patterns

        # Target not found or disappeared
        if any(getattr(s, 'signal_type', None) == VerificationSignalType.STATE_EXISTENCE and not getattr(s, 'is_success', True)
               for s in failed_signals):
            return FailureClassification(
                category="target_not_found",
                reason="Target element no longer exists",
                description="The target element could not be found in the post-action screen state",
                confidence=0.9,
                suggested_recovery="re_resolve_target",
                associated_signals=failed_signals
            )

        # Target not visible
        if any(getattr(s, 'signal_type', None) == VerificationSignalType.STATE_VISIBILITY and not getattr(s, 'is_success', True)
               for s in failed_signals):
            return FailureClassification(
                category="target_not_visible",
                reason="Target element is not visible",
                description="Target element exists but is not visible (may be obscured or off-screen)",
                confidence=0.85,
                suggested_recovery="wait_and_retry_or_scroll",
                associated_signals=failed_signals
            )

        # Target not enabled
        if any(getattr(s, 'signal_type', None) == VerificationSignalType.STATE_ENABLED and not getattr(s, 'is_success', True)
               for s in failed_signals):
            return FailureClassification(
                category="target_not_enabled",
                reason="Target element is not enabled",
                description="Target element exists but is not interactive (disabled, read-only, etc.)",
                confidence=0.8,
                suggested_recovery="wait_for_enable_or_alternative",
                associated_signals=failed_signals
            )

        # Text mismatch (for type actions)
        if any(getattr(s, 'signal_type', None) == VerificationSignalType.TEXT_MATCH and not getattr(s, 'is_success', True)
               for s in failed_signals):
            return FailureClassification(
                category="text_mismatch",
                reason="Entered text does not match expected",
                description="The text that was entered does not match the expected value",
                confidence=0.75,
                suggested_recovery="re_type_with_correction",
                associated_signals=failed_signals
            )

        # Browser-specific failures
        if any(getattr(s, 'signal_type', None) in [VerificationSignalType.URL_MATCH, VerificationSignalType.TITLE_MATCH]
               and not getattr(s, 'is_success', True) for s in failed_signals):
            return FailureClassification(
                category="browser_navigation_failed",
                reason="Browser navigation did not complete as expected",
                description="Browser did not navigate to expected URL or title did not match",
                confidence=0.8,
                suggested_recovery="retry_navigation_or_fallback",
                associated_signals=failed_signals
            )

        # Application state failures
        if any(getattr(s, 'signal_type', None) == VerificationSignalType.APPLICATION_STATE
               and not getattr(s, 'is_success', True) for s in failed_signals):
            return FailureClassification(
                category="application_state_failed",
                reason="Application state is not as expected",
                description="Application failed to start, stop, or reach expected state",
                confidence=0.85,
                suggested_recovery="relaunch_or_wait_for_application",
                associated_signals=failed_signals
            )

        # Generic action execution failure
        return FailureClassification(
            category="action_execution_failed",
            reason="Action execution failed",
            description="The action itself failed to execute properly",
            confidence=0.7,
            suggested_recovery="retry_action_with_adjustment",
            associated_signals=failed_signals
        )

    def classify_validation_failure(
        self,
        validation_result: Any,  # ValidationResult or similar
        action_type: str,
        action_parameters: Dict[str, Any]
    ) -> FailureClassification:
        """
        Classify a validation failure (pre-execution).

        Args:
            validation_result: Result of action validation
            action_type: Type of action that was attempted
            action_parameters: Parameters used for the action

        Returns:
            FailureClassification for the validation failure
        """
        # Extract validation details
        is_valid = getattr(validation_result, 'is_valid', False)
        should_re_resolve = getattr(validation_result, 'should_re_resolve', False)
        status = getattr(validation_result, 'status', None)
        message = getattr(validation_result, 'message', '')

        if is_valid:
            return FailureClassification(
                category="no_failure",
                reason="Validation succeeded",
                description="Action validation passed",
                confidence=1.0,
                suggested_recovery="none"
            )

        # Classify based on validation status
        status_str = status.value if hasattr(status, 'value') else str(status) if status else "unknown"

        if "stale" in status_str.lower() or should_re_resolve:
            return FailureClassification(
                category="target_stale",
                reason="Target is stale or outdated",
                description="Target information is too old and needs re-resolution",
                confidence=0.9,
                suggested_recovery="re_resolve_target",
                metadata={"validation_message": message}
            )
        elif "low_confidence" in status_str.lower():
            return FailureClassification(
                category="low_confidence_target",
                reason="Target confidence too low",
                description="Target resolution confidence is below threshold for safe execution",
                confidence=0.85,
                suggested_recovery="re_resolve_target_or_request_clarification",
                metadata={"validation_message": message}
            )
        elif "invalid" in status_str.lower():
            return FailureClassification(
                category="invalid_target",
                reason="Target is invalid",
                description="Target failed validation checks (bounds, visibility, etc.)",
                confidence=0.8,
                suggested_recovery="re_resolve_target",
                metadata={"validation_message": message}
            )
        elif "permission" in status_str.lower():
            return FailureClassification(
                category="permission_denied",
                reason="Action not permitted",
                description="Action is blocked by permission policies",
                confidence=0.95,
                suggested_recovery="request_user_confirmation_or_cancel",
                metadata={"validation_message": message}
            )
        else:
            return FailureClassification(
                category="validation_failed",
                reason="Action validation failed",
                description=f"Pre-execution validation failed: {message}",
                confidence=0.75,
                suggested_recovery="review_and_retry",
                metadata={"validation_message": message}
            )