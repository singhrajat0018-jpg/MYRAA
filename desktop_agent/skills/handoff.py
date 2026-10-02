"""Handoff — formal worker-to-worker handoff for MYRAA.

Every handoff is explicit: from_agent, to_agent, reason, context,
artifacts, evidence, confidence, deadline.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Handoff:
    """Formal handoff between workers."""
    handoff_id: str
    from_worker: str
    to_worker: str
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    deadline_seconds: float = 60.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "pending"  # pending, accepted, completed, failed, expired

    @property
    def latency_ms(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.created_at) * 1000
        return None

    @property
    def is_expired(self) -> bool:
        if self.completed_at:
            return False
        return (time.time() - self.created_at) > self.deadline_seconds

    def complete(self) -> None:
        self.completed_at = time.time()
        self.status = "completed"

    def fail(self, reason: str = "") -> None:
        self.completed_at = time.time()
        self.status = "failed"
        self.evidence.append(f"Handoff failed: {reason}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "from_worker": self.from_worker,
            "to_worker": self.to_worker,
            "reason": self.reason,
            "context_keys": list(self.context.keys()),
            "artifacts_count": len(self.artifacts),
            "evidence": self.evidence,
            "confidence": self.confidence,
            "deadline_seconds": self.deadline_seconds,
            "status": self.status,
            "latency_ms": self.latency_ms,
        }


class HandoffSystem:
    """Manages worker-to-worker handoffs.

    Tracks: pending, accepted, completed, failed, expired.
    Detects: circular handoffs, expired handoffs.
    """

    def __init__(self, max_chain_depth: int = 10) -> None:
        self._handoffs: Dict[str, Handoff] = {}
        self._chains: Dict[str, List[str]] = {}  # plan_id -> [handoff_ids]
        self._max_chain_depth = max_chain_depth
        self._lock = threading.Lock()
        self._counter = 0

    def create_handoff(
        self,
        from_worker: str,
        to_worker: str,
        reason: str,
        context: Dict[str, Any] = None,
        artifacts: List[Dict[str, Any]] = None,
        evidence: List[str] = None,
        confidence: float = 0.5,
        deadline_seconds: float = 60.0,
        plan_id: str = "",
    ) -> Handoff:
        """Create a new handoff."""
        with self._lock:
            self._counter += 1
            handoff = Handoff(
                handoff_id=f"ho-{self._counter:04d}",
                from_worker=from_worker,
                to_worker=to_worker,
                reason=reason,
                context=context or {},
                artifacts=artifacts or [],
                evidence=evidence or [],
                confidence=confidence,
                deadline_seconds=deadline_seconds,
            )
            self._handoffs[handoff.handoff_id] = handoff

            # Track chain
            if plan_id:
                if plan_id not in self._chains:
                    self._chains[plan_id] = []
                self._chains[plan_id].append(handoff.handoff_id)

            # Check chain depth
            chain = self._chains.get(plan_id, [])
            if len(chain) > self._max_chain_depth:
                logger.warning(
                    "Handoff chain depth %d exceeds max %d for plan %s",
                    len(chain), self._max_chain_depth, plan_id,
                )

            logger.info(
                "Handoff created: %s -> %s (reason: %s)",
                from_worker, to_worker, reason,
            )
            return handoff

    def accept_handoff(self, handoff_id: str) -> bool:
        handoff = self._handoffs.get(handoff_id)
        if handoff and handoff.status == "pending":
            handoff.status = "accepted"
            return True
        return False

    def complete_handoff(self, handoff_id: str) -> bool:
        handoff = self._handoffs.get(handoff_id)
        if handoff and handoff.status in ("pending", "accepted"):
            handoff.complete()
            return True
        return False

    def fail_handoff(self, handoff_id: str, reason: str = "") -> bool:
        handoff = self._handoffs.get(handoff_id)
        if handoff:
            handoff.fail(reason)
            return True
        return False

    def check_circular(self, plan_id: str) -> bool:
        """Check if a plan has circular handoffs (any worker appears twice in chain)."""
        chain = self._chains.get(plan_id, [])
        seen = set()
        for hid in chain:
            h = self._handoffs.get(hid)
            if h:
                # Check if this creates a cycle: target was already seen as source
                # or source was already seen as target
                if h.to_worker in seen or h.from_worker in seen:
                    return True
                seen.add(h.from_worker)
                seen.add(h.to_worker)
        return False

    def expire_stale(self) -> int:
        """Expire stale handoffs."""
        expired = 0
        with self._lock:
            for handoff in self._handoffs.values():
                if handoff.status == "pending" and handoff.is_expired:
                    handoff.status = "expired"
                    expired += 1
        return expired

    def get_pending(self) -> List[Handoff]:
        with self._lock:
            return [h for h in self._handoffs.values() if h.status == "pending"]

    def get_chain(self, plan_id: str) -> List[Handoff]:
        chain_ids = self._chains.get(plan_id, [])
        return [self._handoffs[hid] for hid in chain_ids if hid in self._handoffs]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            handoffs = list(self._handoffs.values())
        return {
            "total": len(handoffs),
            "pending": sum(1 for h in handoffs if h.status == "pending"),
            "completed": sum(1 for h in handoffs if h.status == "completed"),
            "failed": sum(1 for h in handoffs if h.status == "failed"),
            "expired": sum(1 for h in handoffs if h.status == "expired"),
            "chains": len(self._chains),
        }
