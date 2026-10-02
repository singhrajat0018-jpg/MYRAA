"""AgentSupervisor — Super-Brain supervision for worker execution.

Supervises workers: continue, retry, replan, cancel, escalate.
Uses existing Self-Healing for worker recovery.
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .worker import Worker, WorkerContract, WorkerResult, WorkerStatus
from .planner import ExecutionPlan, PlanStep, PlanStepStatus, PlanMode

logger = logging.getLogger(__name__)


class SupervisorDecision(str, Enum):
    CONTINUE = "continue"
    RETRY = "retry"
    REPLAN = "replan"
    CANCEL = "cancel"
    ESCALATE = "escalate"
    VERIFY = "verify"
    SKIP = "skip"


@dataclass
class SupervisionEvent:
    """Event emitted by supervisor during execution."""
    event_type: str  # step_started, step_completed, step_failed, decision, escalated
    plan_id: str
    step_id: str
    decision: Optional[SupervisorDecision] = None
    result: Optional[WorkerResult] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentSupervisor:
    """Supervises worker execution with structured decision-making.

    Super-Brain remains the single cognitive authority.
    Supervisor decides: continue, retry, replan, cancel, escalate, verify.
    """

    def __init__(
        self,
        max_retries: int = 3,
        max_replans: int = 2,
        escalation_threshold: float = 0.3,
    ) -> None:
        self.max_retries = max_retries
        self.max_replans = max_replans
        self.escalation_threshold = escalation_threshold
        self._events: List[SupervisionEvent] = []
        self._lock = threading.Lock()
        self._replan_count: Dict[str, int] = {}
        self._retry_counts: Dict[str, int] = {}
        self._listeners: List[Callable[[SupervisionEvent], None]] = []

    def decide(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        result: WorkerResult,
    ) -> SupervisorDecision:
        """Make a supervision decision based on step result."""
        key = f"{plan.plan_id}:{step.step_id}"

        if result.is_success:
            return SupervisorDecision.CONTINUE

        if result.status == WorkerStatus.CANCELLED:
            return SupervisorDecision.CANCEL

        if result.status == WorkerStatus.TIMED_OUT:
            return self._handle_timeout(plan, step, result, key)

        if result.is_failure:
            return self._handle_failure(plan, step, result, key)

        return SupervisorDecision.ESCALATE

    def _handle_timeout(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        result: WorkerResult,
        key: str,
    ) -> SupervisorDecision:
        """Handle worker timeout."""
        retries = self._retry_counts.get(key, 0)
        if retries < self.max_retries:
            self._retry_counts[key] = retries + 1
            self._emit_event("timeout_retry", plan.plan_id, step.step_id,
                           decision=SupervisorDecision.RETRY)
            return SupervisorDecision.RETRY

        return self._escalate_or_replan(plan, step, key)

    def _handle_failure(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        result: WorkerResult,
        key: str,
    ) -> SupervisorDecision:
        """Handle worker failure."""
        # Check if error is retryable
        if result.is_retryable:
            retries = self._retry_counts.get(key, 0)
            if retries < self.max_retries:
                self._retry_counts[key] = retries + 1
                self._emit_event("failure_retry", plan.plan_id, step.step_id,
                               decision=SupervisorDecision.RETRY)
                return SupervisorDecision.RETRY

        return self._escalate_or_replan(plan, step, key)

    def _escalate_or_replan(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
        key: str,
    ) -> SupervisorDecision:
        """Decide between replan and escalate."""
        replans = self._replan_count.get(plan.plan_id, 0)

        if replans < self.max_replans:
            self._replan_count[plan.plan_id] = replans + 1
            self._emit_event("replan", plan.plan_id, step.step_id,
                           decision=SupervisorDecision.REPLAN)
            return SupervisorDecision.REPLAN

        # Escalate to human
        self._emit_event("escalate", plan.plan_id, step.step_id,
                       decision=SupervisorDecision.ESCALATE)
        return SupervisorDecision.ESCALATE

    def on_event(self, callback: Callable[[SupervisionEvent], None]) -> None:
        self._listeners.append(callback)

    def _emit_event(
        self,
        event_type: str,
        plan_id: str,
        step_id: str,
        decision: Optional[SupervisorDecision] = None,
        result: Optional[WorkerResult] = None,
    ) -> None:
        event = SupervisionEvent(
            event_type=event_type,
            plan_id=plan_id,
            step_id=step_id,
            decision=decision,
            result=result,
        )
        with self._lock:
            self._events.append(event)
        for cb in self._listeners:
            try:
                cb(event)
            except Exception:
                pass

    def get_events(self, plan_id: Optional[str] = None) -> List[SupervisionEvent]:
        with self._lock:
            if plan_id:
                return [e for e in self._events if e.plan_id == plan_id]
            return list(self._events)

    def reset(self, plan_id: Optional[str] = None) -> None:
        with self._lock:
            if plan_id:
                self._replan_count.pop(plan_id, None)
                self._events = [e for e in self._events if e.plan_id != plan_id]
            else:
                self._replan_count.clear()
                self._retry_counts.clear()
                self._events.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            events = list(self._events)
        decisions = {}
        for e in events:
            if e.decision:
                decisions[e.decision.value] = decisions.get(e.decision.value, 0) + 1
        return {
            "total_events": len(events),
            "decisions": decisions,
            "replan_counts": dict(self._replan_count),
            "retry_counts": dict(self._retry_counts),
        }
