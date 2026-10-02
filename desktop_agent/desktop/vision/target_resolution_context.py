"""
MYRAA Vision V3
Target Resolution Context

Context information for target resolution operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time

from .screen_state import ActiveWindow


@dataclass
class TargetResolutionContext:
    """
    Context information for target resolution.

    Provides application/window context and temporal information
    to improve resolution accuracy.
    """
    active_window: Optional[ActiveWindow] = None
    application: str = ""
    timestamp: float = field(default_factory=time.time)
    max_target_age: float = 30.0  # Maximum age in seconds for target validity