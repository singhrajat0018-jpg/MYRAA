"""
MYRAA Super-Brain — Experience & Learning (B20).

Records goal-execution experiences (outcome, verification, recovery, replan)
and derives reusable "lessons". Like AI Manager 4.1's FeedbackStore, this is an
OFFLINE-LEANING store: experiences are retained and can be exported for offline
recalibration/replay, and provide a bounded in-memory hint layer for future
plans (capability -> historically successful tool sequence).

The Super-Brain NEVER rewrites its own behavior from a single experience and
never trusts experiences over live verification. Safety/financial/system rules
always take precedence.
"""

from __future__ import annotations

import logging
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Experience:
    """One completed goal-execution experience (B20)."""

    request_id: str
    goal_text: str
    capability: str = ""
    route_decision: str = ""
    success: bool = False
    tool_sequence: List[str] = field(default_factory=list)
    outcome_message: str = ""
    verification_method: str = ""
    verified: bool = False
    recovery: str = ""
    replan_count: int = 0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    lesson: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "goal_text": self.goal_text,
            "capability": self.capability,
            "route_decision": self.route_decision,
            "success": self.success,
            "tool_sequence": list(self.tool_sequence),
            "outcome_message": self.outcome_message,
            "verification_method": self.verification_method,
            "verified": self.verified,
            "recovery": self.recovery,
            "replan_count": self.replan_count,
            "duration_ms": round(self.duration_ms, 3),
            "timestamp": self.timestamp,
            "lesson": self.lesson,
        }


class ExperienceEngine:
    """
    Bounded experience store + hint layer (B20).

    For every capability, tracks the most common SUCCESSFUL and VERIFIED tool
    sequences. A future plan can start from these hints, but each execution is
    still planned by MasterPlanner and verified live.
    """

    def __init__(self, maxlen: int = 1000, memory_2_0: Optional[Any] = None) -> None:
        self._records: Deque[Experience] = deque(maxlen=maxlen)
        self._success_seq: Dict[str, Dict[tuple, int]] = defaultdict(lambda: defaultdict(int))
        self.memory_2_0 = memory_2_0

    # ------------------------------------------------------------------

    def record(self, experience: Experience) -> None:
        """Persist (in-memory) an experience and update hint layer (B20)."""
        self._records.append(experience)

        if experience.success and experience.verified and experience.tool_sequence:
            cap = experience.capability or "unknown"
            self._success_seq[cap][tuple(experience.tool_sequence)] += 1

        self._write_memory_record(experience)

    # ------------------------------------------------------------------

    def _write_memory_record(self, experience: Experience) -> None:
        """
        Mirror the experience into Memory 2.0 as a long-term EXPERIENCE record
        (M8). Best-effort and never blocking: the in-memory store above remains
        authoritative for hinting, and a broken memory store must not break
        execution or learning.
        """
        if self.memory_2_0 is None:
            return
        try:
            from desktop_agent.brain.memory.unified_model import (
                MemoryRecord,
                MemoryType,
                MemoryScope,
                MemoryStatus,
                RetentionPolicy,
                Provenance,
            )

            cap = experience.capability or "unknown"
            outcome = experience.outcome_message or (
                "completed" if experience.success else "failed"
            )
            record = MemoryRecord(
                type=MemoryType.EXPERIENCE,
                content=f"Goal: {experience.goal_text}\n"
                        f"Tools: {', '.join(experience.tool_sequence) or 'none'}\n"
                        f"Outcome: {outcome}\nSuccess: {experience.success}",
                summary=(
                    f"Experience: {cap} -> "
                    f"{'success' if experience.success else 'failure'}"
                ),
                source="super_brain",
                importance=0.8 if experience.success else 0.6,
                confidence=0.9 if experience.verified else 0.6,
                retention_policy=RetentionPolicy.LONG_TERM,
                scope=MemoryScope.USER,
                status=MemoryStatus.ACTIVE,
                provenance=Provenance.SYSTEM_OBSERVED,
                tags={
                    "experience",
                    "success" if experience.success else "failure",
                    cap,
                },
                relations={
                    "capability": [cap],
                    "tool_sequence": list(experience.tool_sequence),
                    "verification_method": [experience.verification_method]
                    if experience.verification_method else [],
                },
                metadata={
                    "request_id": experience.request_id,
                    "verified": experience.verified,
                    "replan_count": experience.replan_count,
                    "duration_ms": experience.duration_ms,
                    "lesson": experience.lesson or "",
                },
            )
            self.memory_2_0.remember(record)
        except Exception as exc:  # noqa: BLE001
            log.warning("ExperienceEngine failed to write Memory 2.0 record: %s", exc)

    def hint_for(self, capability: str) -> List[str]:
        """
        Best historically-successful tool sequence for a capability (B20).

        Returns [] when no verified success exists for the capability.
        """
        if not capability:
            return []
        seq_counts = self._success_seq.get(capability)
        if not seq_counts:
            return []
        best_seq, _ = max(seq_counts.items(), key=lambda kv: kv[1])
        return list(best_seq)

    def success_rate(self, capability: str) -> Optional[float]:
        """Fraction of recorded experiences for capability that succeeded."""
        caps = [e for e in self._records if e.capability == capability]
        if not caps:
            return None
        return sum(1 for e in caps if e.success) / len(caps)

    # ------------------------------------------------------------------

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        recs = list(self._records)
        return [e.to_dict() for e in recs[-limit:]]

    def count(self) -> int:
        return len(self._records)

    def lessons(self) -> List[str]:
        return [e.lesson for e in self._records if e.lesson]

    def export(self, path: str) -> int:
        """Serialize all experiences to JSON (best-effort)."""
        import json
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.history(limit=100000), fh, indent=2)
        return self.count()