"""ConflictResolver — detects and resolves worker conflicts for MYRAA.

When workers disagree, the system: detect → collect evidence → rank → resolve.
Never silently picks one side.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    DATA_CONFLICT = "data_conflict"      # Workers produced different data
    APPROACH_CONFLICT = "approach_conflict"  # Workers suggest different approaches
    FACT_CONFLICT = "fact_conflict"      # Workers disagree on facts
    PRIORITY_CONFLICT = "priority_conflict"  # Workers disagree on priorities


class ResolutionStrategy(str, Enum):
    EVIDENCE_RANK = "evidence_rank"      # Rank by evidence strength
    CONFIDENCE_WEIGHT = "confidence_weight"  # Weight by confidence
    RECENT_WINS = "recent_wins"          # Trust more recent results
    SUPERVISOR_DECIDES = "supervisor_decides"  # Escalate to supervisor
    FUSION = "fusion"                    # Combine both results


@dataclass
class Conflict:
    """Detected conflict between workers."""
    conflict_id: str
    conflict_type: ConflictType
    worker_a: str
    worker_b: str
    claim_a: Dict[str, Any]
    claim_b: Dict[str, Any]
    evidence_a: List[str] = field(default_factory=list)
    evidence_b: List[str] = field(default_factory=list)
    confidence_a: float = 0.5
    confidence_b: float = 0.5
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: Optional["Resolution"] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "worker_a": self.worker_a,
            "worker_b": self.worker_b,
            "confidence_a": self.confidence_a,
            "confidence_b": self.confidence_b,
            "resolved": self.resolved,
            "resolution": self.resolution.to_dict() if self.resolution else None,
        }


@dataclass
class Resolution:
    """Resolution for a conflict."""
    strategy: ResolutionStrategy
    winner: Optional[str] = None
    combined_result: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "winner": self.winner,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


class ConflictResolver:
    """Detects and resolves worker conflicts.

    Strategies: evidence_rank, confidence_weight, recent_wins, supervisor_decides, fusion.
    """

    def __init__(self) -> None:
        self._conflicts: List[Conflict] = []
        self._lock = threading.Lock()
        self._counter = 0

    def detect(
        self,
        worker_a: str,
        claim_a: Dict[str, Any],
        worker_b: str,
        claim_b: Dict[str, Any],
        conflict_type: ConflictType = ConflictType.DATA_CONFLICT,
        evidence_a: Optional[List[str]] = None,
        evidence_b: Optional[List[str]] = None,
        confidence_a: float = 0.5,
        confidence_b: float = 0.5,
    ) -> Optional[Conflict]:
        """Detect if two worker outputs conflict."""
        # Simple conflict detection: if claims differ, it's a conflict
        if claim_a == claim_b:
            return None

        with self._lock:
            self._counter += 1
            conflict = Conflict(
                conflict_id=f"conflict-{self._counter:04d}",
                conflict_type=conflict_type,
                worker_a=worker_a,
                worker_b=worker_b,
                claim_a=claim_a,
                claim_b=claim_b,
                evidence_a=evidence_a or [],
                evidence_b=evidence_b or [],
                confidence_a=confidence_a,
                confidence_b=confidence_b,
            )
            self._conflicts.append(conflict)
            logger.warning(
                "Conflict detected: %s vs %s (type: %s)",
                worker_a, worker_b, conflict_type.value,
            )
            return conflict

    def resolve(
        self,
        conflict: Conflict,
        strategy: ResolutionStrategy = ResolutionStrategy.EVIDENCE_RANK,
    ) -> Resolution:
        """Resolve a conflict using the given strategy."""
        if strategy == ResolutionStrategy.EVIDENCE_RANK:
            resolution = self._resolve_by_evidence(conflict)
        elif strategy == ResolutionStrategy.CONFIDENCE_WEIGHT:
            resolution = self._resolve_by_confidence(conflict)
        elif strategy == ResolutionStrategy.RECENT_WINS:
            resolution = self._resolve_by_recency(conflict)
        elif strategy == ResolutionStrategy.FUSION:
            resolution = self._resolve_by_fusion(conflict)
        else:
            resolution = Resolution(
                strategy=ResolutionStrategy.SUPERVISOR_DECIDES,
                reasoning="Escalated to supervisor for manual resolution",
                confidence=0.0,
            )

        conflict.resolved = True
        conflict.resolution = resolution
        return resolution

    def _resolve_by_evidence(self, conflict: Conflict) -> Resolution:
        """Resolve by evidence strength (more evidence wins)."""
        score_a = len(conflict.evidence_a) * conflict.confidence_a
        score_b = len(conflict.evidence_b) * conflict.confidence_b

        if score_a > score_b:
            winner = conflict.worker_a
            reasoning = f"Worker A has stronger evidence (score: {score_a:.2f} vs {score_b:.2f})"
        elif score_b > score_a:
            winner = conflict.worker_b
            reasoning = f"Worker B has stronger evidence (score: {score_b:.2f} vs {score_a:.2f})"
        else:
            winner = None
            reasoning = "Evidence strength equal, requires fusion"

        return Resolution(
            strategy=ResolutionStrategy.EVIDENCE_RANK,
            winner=winner,
            reasoning=reasoning,
            confidence=max(conflict.confidence_a, conflict.confidence_b),
        )

    def _resolve_by_confidence(self, conflict: Conflict) -> Resolution:
        """Resolve by confidence score."""
        if conflict.confidence_a > conflict.confidence_b:
            winner = conflict.worker_a
            reasoning = f"Worker A has higher confidence ({conflict.confidence_a:.2f} vs {conflict.confidence_b:.2f})"
        else:
            winner = conflict.worker_b
            reasoning = f"Worker B has higher confidence ({conflict.confidence_b:.2f} vs {conflict.confidence_a:.2f})"

        return Resolution(
            strategy=ResolutionStrategy.CONFIDENCE_WEIGHT,
            winner=winner,
            reasoning=reasoning,
            confidence=max(conflict.confidence_a, conflict.confidence_b),
        )

    def _resolve_by_recency(self, conflict: Conflict) -> Resolution:
        """Resolve by recency — more recent wins (placeholder)."""
        return Resolution(
            strategy=ResolutionStrategy.RECENT_WINS,
            winner=conflict.worker_a,
            reasoning="Recency-based resolution (placeholder)",
            confidence=0.5,
        )

    def _resolve_by_fusion(self, conflict: Conflict) -> Resolution:
        """Combine both results."""
        combined = {}
        combined.update(conflict.claim_a)
        combined.update(conflict.claim_b)

        return Resolution(
            strategy=ResolutionStrategy.FUSION,
            combined_result=combined,
            reasoning="Combined both worker outputs",
            confidence=(conflict.confidence_a + conflict.confidence_b) / 2,
        )

    def get_unresolved(self) -> List[Conflict]:
        with self._lock:
            return [c for c in self._conflicts if not c.resolved]

    def get_all(self) -> List[Conflict]:
        with self._lock:
            return list(self._conflicts)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            conflicts = list(self._conflicts)
        return {
            "total": len(conflicts),
            "resolved": sum(1 for c in conflicts if c.resolved),
            "unresolved": sum(1 for c in conflicts if not c.resolved),
        }
