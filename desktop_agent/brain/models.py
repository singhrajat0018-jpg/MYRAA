"""
MYRAA Brain - Core Data Models

These models are shared across every brain subsystem.

Planner
Decision Engine
Memory
Context
Vision
Verification
Workflow Engine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SafetyLevel(str, Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"


class DecisionType(str, Enum):
    DIRECT = "direct"
    PLAN = "plan"
    QUESTION = "question"
    MEMORY = "memory"
    VISION = "vision"


@dataclass
class ToolAction:
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainContext:

    active_app: Optional[str] = None

    active_window: Optional[str] = None

    clipboard: Optional[str] = None

    current_folder: Optional[str] = None

    desktop_state: Optional[Any] = None

    desktop_event: Optional[str] = None

    vision_context: Optional[Any] = None

    screen_changed: bool = False

    memory: Dict[str, Any] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)

    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BrainDecision:

    goal: str

    decision_type: DecisionType

    confidence: float

    reasoning: List[str] = field(default_factory=list)

    needs_confirmation: bool = False

    # --------------------------------------------------
    # Direct tool execution (Function Call pipeline)
    # --------------------------------------------------

    action: Optional[str] = None

    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainResult:

    success: bool

    message: str

    actions: List[ToolAction] = field(default_factory=list)

    duration_ms: float = 0

    metadata: Dict[str, Any] = field(default_factory=dict)