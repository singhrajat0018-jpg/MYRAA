"""
MYRAA Cognitive Engine
Enhanced Verification Models

Extends the EPIC-14C verification system with multi-signal verification,
expected state validation, and enhanced result tracking for EPIC-14D.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class VerificationSignalType(Enum):
    """Types of verification signals that can be combined."""
    STATE_EXISTENCE = "state_existence"      # Target element still exists
    STATE_VISIBILITY = "state_visibility"    # Target element is visible
    STATE_ENABLED = "state_enabled"          # Target element is enabled
    TEXT_MATCH = "text_match"                # Entered text matches expected
    URL_MATCH = "url_match"                  # Browser URL matches expected
    TITLE_MATCH = "title_match"              # Browser title matches expected
    VISUAL_STATE = "visual_state"            # Overall visual state unchanged
    APPLICATION_STATE = "application_state"   # Application running/not running
    WINDOW_FOCUS = "window_focus"            # Correct window has focus
    TEMPORAL_STABILITY = "temporal_stability" # State stable over time


@dataclass
class VerificationSignal:
    """Individual verification signal with confidence score."""
    signal_type: VerificationSignalType
    is_success: bool
    confidence: float  # 0.0 to 1.0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnhancedVerificationResult:
    """
    Enhanced verification result supporting multi-signal verification.

    Combines multiple verification signals into a unified result with
    weighted confidence scoring and detailed failure analysis.
    """
    # Overall result
    is_success: bool
    overall_confidence: float  # Weighted average of signal confidences

    # Individual signals
    signals: List[VerificationSignal] = field(default_factory=list)

    # Legacy compatibility
    message: str = ""
    verification_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Failure analysis
    failure_signals: List[VerificationSignal] = field(default_factory=list)
    failure_reason: str = ""

    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if self.metadata is None:
            self.metadata = {}

        # Update failure signals based on unsuccessful signals
        self.failure_signals = [s for s in self.signals if not s.is_success]

        # Set failure reason if not provided and we have failures
        if not self.failure_reason and self.failure_signals:
            failed_types = [s.signal_type.value for s in self.failure_signals]
            self.failure_reason = f"Failed signals: {', '.join(failed_types)}"

        # Calculate overall confidence if not set
        if self.overall_confidence == 0.0 and self.signals:
            # Weighted average - could be customized based on signal importance
            total_confidence = sum(s.confidence for s in self.signals)
            self.overall_confidence = total_confidence / len(self.signals)

    def add_signal(self, signal: VerificationSignal):
        """Add a verification signal to the result."""
        self.signals.append(signal)
        # Recalculate derived fields
        self.__post_init__()

    def get_signal(self, signal_type: VerificationSignalType) -> Optional[VerificationSignal]:
        """Get a specific signal by type."""
        for signal in self.signals:
            if signal.signal_type == signal_type:
                return signal
        return None

    def signal_succeeded(self, signal_type: VerificationSignalType) -> bool:
        """Check if a specific signal type succeeded."""
        signal = self.get_signal(signal_type)
        return signal is not None and signal.is_success

    def signal_failed(self, signal_type: VerificationSignalType) -> bool:
        """Check if a specific signal type failed."""
        signal = self.get_signal(signal_type)
        return signal is not None and not signal.is_success


@dataclass
class ExpectedState:
    """
    Defines expected state after an action execution.

    Used for verification to check if the actual state matches expectations.
    """
    # State expectations
    target_should_exist: bool = True
    target_should_be_visible: bool = True
    target_should_be_enabled: bool = True
    target_text_should_match: Optional[str] = None

    # Browser expectations
    browser_url_should_contain: Optional[str] = None
    browser_title_should_contain: Optional[str] = None
    browser_should_be_visible: bool = True

    # Application expectations
    application_should_be_running: Optional[str] = None
    application_should_not_be_running: Optional[str] = None

    # Window expectations
    window_should_be_active: Optional[str] = None
    window_should_not_be_active: Optional[str] = None

    # Temporal expectations (for delayed verification)
    verify_after_delay_seconds: float = 0.0
    max_verification_attempts: int = 3
    verification_retry_delay: float = 0.5

    # Verification weights (importance of each check)
    weights: Dict[VerificationSignalType, float] = field(default_factory=lambda: {
        VerificationSignalType.STATE_EXISTENCE: 0.25,
        VerificationSignalType.STATE_VISIBILITY: 0.20,
        VerificationSignalType.STATE_ENABLED: 0.15,
        VerificationSignalType.TEXT_MATCH: 0.15,
        VerificationSignalType.URL_MATCH: 0.10,
        VerificationSignalType.TITLE_MATCH: 0.10,
        VerificationSignalType.APPLICATION_STATE: 0.05
    })


@dataclass
class FailureClassification:
    """
    Classifies verification failures for reason-driven recovery.
    """
    # Failure category
    category: str  # e.g., "target_not_found", "action_failed", "verification_timeout"

    # Specific failure reason
    reason: str

    # Suggested recovery strategy
    suggested_recovery: str  # e.g., "re_resolve_target", "adjust_parameters", "fallback_action"

    # Confidence in classification (0.0 to 1.0)
    confidence: float = 1.0

    # Metadata for recovery
    metadata: Dict[str, Any] = field(default_factory=dict)