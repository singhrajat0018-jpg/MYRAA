"""
MYRAA Vision V3
Target Resolution Result

Result model for target resolution operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any
import time


class TargetResolutionStatus(str, Enum):
    """Status of target resolution operation."""
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    STALE = "stale"


@dataclass(slots=True)
class TargetResolutionResult:
    """
    Result of a target resolution operation.

    Contains the outcome of resolving a target description against a ScreenState.
    """
    status: TargetResolutionStatus = TargetResolutionStatus.UNRESOLVED
    target: Optional[Any] = None  # Will be InteractionTarget when resolved
    candidates: List[Any] = field(default_factory=list)  # Alternative candidates
    confidence: float = 0.0
    reason: str = ""
    timestamp: float = field(default_factory=time.time)
    resolution_method: str = ""

    def is_successful(self) -> bool:
        """Return True if resolution was successful (RESOLVED status)."""
        return self.status == TargetResolutionStatus.RESOLVED

    def is_ambiguous(self) -> bool:
        """Return True if resolution resulted in ambiguity."""
        return self.status == TargetResolutionStatus.AMBIGUOUS

    def is_unresolved(self) -> bool:
        """Return True if resolution failed to find a target."""
        return self.status == TargetResolutionStatus.UNRESOLVED

    def is_stale(self) -> bool:
        """Return True if the resolved target is stale."""
        return self.status == TargetResolutionStatus.STALE