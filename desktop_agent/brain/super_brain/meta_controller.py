"""
MYRAA Super-Brain — Meta-Controller (B15).

Monitors goal execution, consumes Metacognition results from the existing
Metacognition engine, and decides whether to continue, replan, or seek help.
Also handles cross-goal sequencing (schedule/priority) so long-horizon goals do
not starve reactive user requests.

The existing Metacognition.evaluate() is the reflection authority; this
controller only APPLIES its output to execution flow + telemetry.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class MetaDecision:
    """Decision from the meta-controller (B15)."""

    action: str              # continue | replan | clarify | help | handoff | finish
    confidence: float = 0.0
    reflection: str = ""
    suggested_route: str = ""
    reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "reflection": self.reflection,
            "suggested_route": self.suggested_route,
            "reason": self.reason,
            "created_at": self.created_at,
        }


@dataclass
class GoalTicket:
    """A scheduled goal with priority (B15)."""

    task_id: str
    priority: int
    created_at: float = field(default_factory=time.time)

    def __lt__(self, other: "GoalTicket") -> bool:
        return self.priority < other.priority


class MetaController:
    """
    Watches execution and applies metacognition + goal scheduling (B15).

    REUSES the existing Metacognition.evaluate(thinking, execution_success)
    engine for reflection. Never overrides the SafetyManager / PermissionManager.
    """

    def __init__(
        self,
        metacognition: Optional[Any] = None,
        telemetry: Optional[Any] = None,
    ) -> None:
        self.metacognition = metacognition
        self.telemetry = telemetry
        self._queue: List[GoalTicket] = []
        self._decisions: List[MetaDecision] = []
        self._last_eval: Dict[str, Any] = {}

    # ------------------------------------------------------------------

    def decide(
        self,
        task: Any,
        execution_success: bool,
        reflection_text: str = "",
    ) -> MetaDecision:
        """
        Evaluate how the goal is going and pick the next control action (B15).
        """
        confidence = getattr(task, "confidence", 0.0) or 0.0
        replans = getattr(task, "replan_count", 0) or 0

        # ------------------------------------------------------------------
        # 1) Metacognition reflection (existing engine).
        # ------------------------------------------------------------------
        meta: Dict[str, Any] = {}
        if self.metacognition is not None:
            try:
                thinking = getattr(task, "thinking", None)
                if thinking is None and hasattr(self.metacognition, "latest"):
                    latest = self.metacognition.latest()
                    thinking = latest if latest is not None else None
                if thinking is not None:
                    mresult = self.metacognition.evaluate(
                        thinking, execution_success=execution_success,
                    )
                    if mresult is not None:
                        meta = (
                            mresult.to_dict()
                            if hasattr(mresult, "to_dict")
                            else dict(mresult)
                        )
            except Exception as exc:  # noqa: BLE001
                log.debug("metacognition evaluate skipped: %s", exc)
        self._last_eval = meta
        reflection = meta.get("reflection", "") or reflection_text or ""

        # ------------------------------------------------------------------
        # 2) Route/confidence guidance (existing ResponseRouter aware).
        # ------------------------------------------------------------------
        route = getattr(task, "route", None)
        if route is not None:
            decision = getattr(route, "decision", None)
            # AI Manager already decided a terminal destination.
            if decision in ("LOCAL_FAST", "BRAIN", "RESEARCH", "MEMORY"):
                return MetaDecision(
                    action="handoff",
                    confidence=max(confidence, 0.9),
                    reflection=reflection,
                    suggested_route=str(decision),
                    reason="AI Manager 4.1 terminal route decision",
                )

        # ------------------------------------------------------------------
        # 3) Low-confidence / uncertainty -> clarify.
        # ------------------------------------------------------------------
        if confidence < 0.35:
            return MetaDecision(
                action="clarify",
                confidence=confidence,
                reflection=reflection,
                reason="low calibrated confidence, ask user",
            )

        # ------------------------------------------------------------------
        # 4) Repeated failures -> replan or seek help.
        # ------------------------------------------------------------------
        if not execution_success:
            if replans >= 2:
                return MetaDecision(
                    action="help",
                    confidence=confidence,
                    reflection=reflection,
                    reason="repeated replan failures, seek user guidance",
                )
            return MetaDecision(
                action="replan",
                confidence=confidence,
                reflection=reflection,
                reason="execution failed, replan",
            )

        # ------------------------------------------------------------------
        # 5) Success -> finish.
        # ------------------------------------------------------------------
        return MetaDecision(
            action="finish",
            confidence=confidence,
            reflection=reflection,
            reason="goal verified complete",
        )

    # ------------------------------------------------------------------
    # Goal scheduling (cross-goal sequencing, B15)
    # ------------------------------------------------------------------

    def schedule(self, task_id: str, priority: int = 5) -> None:
        """Queue a long-horizon goal at a priority (B15)."""
        self._queue.append(GoalTicket(task_id=task_id, priority=priority))
        self._queue.sort()

    def next_goal(self) -> Optional[str]:
        """Pop the highest-priority scheduled goal, if any."""
        if not self._queue:
            return None
        return self._queue.pop(0).task_id

    def pending_goals(self) -> List[Dict[str, Any]]:
        return [
            {"task_id": t.task_id, "priority": t.priority}
            for t in self._queue
        ]

    # ------------------------------------------------------------------
    # Records / telemetry (B15 observability)
    # ------------------------------------------------------------------

    def record_decision(self, decision: MetaDecision) -> None:
        self._decisions.append(decision)
        if self.telemetry is not None:
            try:
                self.telemetry.record_event(
                    event_type="super_brain.meta_decision",
                    event_data={
                        "action": decision.action,
                        "confidence": decision.confidence,
                        "reason": decision.reason,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("telemetry skipped: %s", exc)

    def history(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._decisions]

    def last_eval(self) -> Dict[str, Any]:
        return dict(self._last_eval)