"""
MYRAA Cognitive Engine
Computer Action Model

Represents a computer action to be executed on a resolved InteractionTarget.
Builds upon existing planner models and EPIC-14B InteractionTarget.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from enum import Enum

from .action_types import ActionType
from desktop_agent.desktop.vision.interaction_target import InteractionTarget


class ValidationStatus(str, Enum):
    """Validation status for computer actions."""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"
    LOW_CONFIDENCE = "low_confidence"


class VerificationStatus(str, Enum):
    """Verification status for computer actions."""
    PENDING = "pending"
    VERIFIED_SUCCESS = "verified_success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    TARGET_CHANGED = "target_changed"
    VERIFICATION_ERROR = "verification_error"


@dataclass(slots=True)
class ComputerAction:
    """
    Represents a computer action to be executed on a resolved InteractionTarget.

    Combines planner ActionType with EPIC-14B InteractionTarget to create
    executable actions with built-in validation and verification capabilities.
    """

    # =========================================================
    # Core Action Identity
    # =========================================================

    action_type: ActionType
    """The type of action to perform (click, type_text, etc.)"""

    target: InteractionTarget
    """The resolved interaction target to act upon"""

    # =========================================================
    # Action Parameters
    # =========================================================

    parameters: Dict[str, Any] = field(default_factory=dict)
    """Action-specific parameters (text to type, key to press, etc.)"""

    # =========================================================
    # Validation Metadata
    # =========================================================

    validation_status: ValidationStatus = ValidationStatus.PENDING
    """Status of pre-execution validation"""

    validation_message: str = ""
    """Human-readable message about validation result"""

    validation_timestamp: float = field(default_factory=time.time)
    """When validation was last performed"""

    # =========================================================
    # Execution Metadata
    # =========================================================

    executed: bool = False
    """Whether the action has been executed"""

    execution_timestamp: Optional[float] = None
    """When the action was executed"""

    execution_result: Optional[Dict[str, Any]] = None
    """Result from the action execution"""

    # =========================================================
    # Verification Metadata
    # =========================================================

    verification_status: VerificationStatus = VerificationStatus.PENDING
    """Status of post-execution verification"""

    verification_message: str = ""
    """Human-readable message about verification result"""

    verification_timestamp: Optional[float] = None
    """When verification was last performed"""

    expected_outcome: str = ""
    """Description of expected outcome for verification"""

    actual_outcome: str = ""
    """Description of actual outcome observed"""

    # =========================================================
    # Context and Tracking
    # =========================================================

    timestamp: float = field(default_factory=time.time)
    """When this action was created"""

    retry_count: int = 0
    """Number of times this action has been retried"""

    max_retries: int = 3
    """Maximum number of retries allowed"""

    timeout: float = 30.0
    """Timeout for action execution in seconds"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata for tracking and debugging"""

    def __post_init__(self):
        """Initialize computed properties after dataclass initialization."""
        # Ensure target has a center point if not set
        if self.target.center_point is None:
            self.target.center_point = self.target.bounds.center
            self.target.center_reason = "geometric_center"

    def is_valid_for_execution(self, max_target_age: float = 30.0) -> bool:
        """
        Check if this action is valid for execution based on target freshness
        and validation status.

        Args:
            max_target_age: Maximum age in seconds before target is considered stale

        Returns:
            True if action is valid for execution, False otherwise
        """
        # Check if target is still valid
        if not self.target.is_valid(max_target_age):
            self.validation_status = ValidationStatus.STALE
            self.validation_message = f"Target is stale (age: {time.time() - self.target.timestamp:.1f}s)"
            return False

        # Check validation status
        if self.validation_status == ValidationStatus.INVALID:
            return False

        if self.validation_status == ValidationStatus.LOW_CONFIDENCE:
            return False

        # Target is fresh and validation passed
        return True

    def mark_as_executed(self, result: Optional[Dict[str, Any]] = None):
        """Mark the action as executed."""
        self.executed = True
        self.execution_timestamp = time.time()
        self.execution_result = result or {}

    def mark_as_verified(self, status: VerificationStatus, message: str = "",
                        expected: str = "", actual: str = ""):
        """Mark the action as verified with the given status."""
        self.verification_status = status
        self.verification_message = message
        self.verification_timestamp = time.time()
        self.expected_outcome = expected
        self.actual_outcome = actual

    def can_retry(self) -> bool:
        """Check if this action can be retried."""
        return self.retry_count < self.max_retries

    def prepare_for_retry(self):
        """Prepare the action for a retry attempt."""
        self.retry_count += 1
        self.validation_status = ValidationStatus.PENDING
        self.validation_message = ""
        self.execution_timestamp = None
        self.execution_result = None
        self.verification_status = VerificationStatus.PENDING
        self.verification_message = ""
        self.verification_timestamp = None
        self.expected_outcome = ""
        self.actual_outcome = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the action to a dictionary representation."""
        return {
            "action_type": self.action_type.value,
            "target_id": self.target.id,
            "target_text": self.target.text,
            "target_confidence": self.target.confidence,
            "target_bounds": {
                "x": self.target.bounds.x,
                "y": self.target.bounds.y,
                "width": self.target.bounds.width,
                "height": self.target.bounds.height,
                "center": self.target.bounds.center
            },
            "target_center_point": self.target.center_point,
            "target_resolution_method": self.target.resolution_method,
            "target_reasoning": self.target.reasoning,
            "parameters": self.parameters,
            "validation_status": self.validation_status.value,
            "validation_message": self.validation_message,
            "validation_timestamp": self.validation_timestamp,
            "executed": self.executed,
            "execution_timestamp": self.execution_timestamp,
            "execution_result": self.execution_result,
            "verification_status": self.verification_status.value,
            "verification_message": self.verification_message,
            "verification_timestamp": self.verification_timestamp,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "metadata": self.metadata
        }