"""
MYRAA Vision V3
Interaction Target

Extended UIElement model for target resolution with resolution metadata.
Builds upon existing UIElement from EPIC-14A perception system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any
import time

from .ui_models import UIElement, UIElementType, BoundingBox, InteractiveType
from .screen_state import ActiveWindow


@dataclass(slots=True)
class InteractionTarget(UIElement):
    """
    Extended UIElement representing a resolved interaction target.

    Inherits all UIElement properties (id, type, text, confidence, bounds, etc.)
    and adds resolution-specific metadata for EPIC-14B target intelligence.
    """
    # Resolution metadata
    resolution_method: str = ""  # How the target was resolved (text_match, ordinal, spatial, etc.)
    reasoning: str = ""  # Human-readable explanation of resolution

    # Validity tracking
    timestamp: float = field(default_factory=time.time)  # When target was resolved
    valid: bool = True  # Whether target is still valid

    # Context information
    active_window: Optional[ActiveWindow] = None  # Active window when resolved
    application_context: str = ""  # Application name for context scoring

    # Target-specific properties
    center_point: Optional[tuple[int, int]] = None  # Preferred interaction point (may differ from geometric center)
    center_reason: str = ""  # Why this point was chosen

    def __post_init__(self):
        """Initialize computed properties after dataclass initialization."""
        super().__post_init__()

        # Set center_point to geometric center by default
        if self.center_point is None:
            self.center_point = self.bounds.center
            self.center_reason = "geometric_center"

    def is_valid(self, max_age_seconds: float = 30.0) -> bool:
        """
        Check if target is still valid based on age and screen changes.

        Args:
            max_age_seconds: Maximum age in seconds before target is considered stale

        Returns:
            True if target is valid, False otherwise
        """
        if not self.valid:
            return False

        age = time.time() - self.timestamp
        return age <= max_age_seconds

    def invalidate(self):
        """Mark target as invalid."""
        self.valid = False

    def with_updated_context(
        self,
        active_window: Optional[ActiveWindow] = None,
        application_context: str = ""
    ) -> 'InteractionTarget':
        """
        Create a copy of this target with updated context information.

        Args:
            active_window: New active window information
            application_context: New application context

        Returns:
            New InteractionTarget instance with updated context
        """
        target_copy = InteractionTarget(
            id=self.id,
            type=self.type,
            text=self.text,
            confidence=self.confidence,
            bounds=self.bounds,
            clickable=self.clickable,
            enabled=self.enabled,
            visible=self.visible,
            interactive=self.interactive,
            metadata=self.metadata.copy(),

            # Resolution metadata
            resolution_method=self.resolution_method,
            reasoning=self.reasoning,

            # Validity tracking
            timestamp=time.time(),
            valid=self.valid,

            # Context information
            active_window=active_window or self.active_window,
            application_context=application_context or self.application_context,

            # Target-specific properties
            center_point=self.center_point,
            center_reason=self.center_reason
        )

        return target_copy