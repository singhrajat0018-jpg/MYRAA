"""
MYRAA Cognitive Engine
Decision Result
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .execution_strategy import ExecutionStrategy
from ..semantic.semantic_models import SemanticTask


@dataclass(slots=True)
class DecisionResult:
    """
    Output produced by the Decision Engine.
    """

    task: SemanticTask

    strategy: ExecutionStrategy

    approved: bool = True

    confidence: float = 1.0

    reason: str = ""

    selected_skill: str | None = None

    requires_confirmation: bool = False

    requires_reasoning: bool = False

    requires_planning: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)