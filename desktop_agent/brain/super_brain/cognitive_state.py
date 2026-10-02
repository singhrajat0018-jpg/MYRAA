"""
MYRAA Super-Brain — Cognitive State (B1) and Task Graph (B6).

ONE authoritative, resumable representation of a running goal.

This deliberately REUSES the existing ExecutionPlan/PlanStep/StepStatus models
(desktop_agent.brain.planner.*) as the plan backbone instead of introducing a
second plan type. It ADDS the goal-level envelope that those models lack:

  goal, request, phase, verification/recovery state, world snapshot,
  memory references, confidence, cancellation/deadline state, checkpointing.

Task IDs are reused from the existing SemanticTask.task_id where present, never
duplicated.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from desktop_agent.brain.planner.execution.execution_plan import (
    ExecutionPlan,
    PlanStatus,
)
from desktop_agent.brain.planner.models.plan_step import (
    PlanStep,
    StepStatus,
)


class CognitivePhase(str, Enum):
    """High-level phase a goal is currently in (B1)."""

    RECEIVED = "received"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    REPLANNING = "replanning"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskState(str, Enum):
    """Goal-level lifecycle state (B1)."""

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationState(str, Enum):
    """How verification stands for a goal (B1/B13)."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class RecoveryState(str, Enum):
    """Recovery posture for a goal (B1/B12)."""

    NONE = "none"
    RETRYING = "retrying"
    FALLBACK = "fallback"
    REPLANNING = "replanning"
    CLARIFYING = "clarifying"
    ABORTED = "aborted"


@dataclass
class CognitiveTask:
    """
    Authoritative state for one running goal (B1).

    It holds an ExecutionPlan (the existing plan representation) plus the
    goal-level envelope the rest of MYRAA needs for long-horizon work.
    """

    # -- identity (reuses existing ids, never duplicated) ---------------
    task_id: str = ""
    request_id: str = ""
    user_request: str = ""

    # -- goal understanding (B2) ---------------------------------------
    goal: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    success_criteria: List[str] = field(default_factory=list)
    deadline: Optional[float] = None

    # -- lifecycle ------------------------------------------------------
    state: TaskState = TaskState.PENDING
    phase: CognitivePhase = CognitivePhase.RECEIVED

    # -- plan -----------------------------------------------------------
    plan: Optional[ExecutionPlan] = None
    completed_steps: List[str] = field(default_factory=list)
    pending_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    current_step_id: Optional[str] = None

    # -- routing (AI Manager 4.1 output) -------------------------------
    route: Optional[Any] = None
    capability: str = ""
    capability_chain: List[str] = field(default_factory=list)

    # -- context / world ------------------------------------------------
    context_snapshot: Optional[Any] = None
    world_state: Optional[Any] = None
    memory_refs: List[str] = field(default_factory=list)

    # -- verification / recovery / confidence ---------------------------
    verification_state: VerificationState = VerificationState.PENDING
    recovery_state: RecoveryState = RecoveryState.NONE
    confidence: float = 0.0
    last_observation: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    replan_count: int = 0

    # -- timing ---------------------------------------------------------
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # -- metadata --------------------------------------------------------
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = time.time()

    # ------------------------------------------------------------------
    # Phase/state helpers
    # ------------------------------------------------------------------

    def set_phase(self, phase: CognitivePhase) -> None:
        self.phase = phase
        self.touch()

    def mark_active(self) -> None:
        self.state = TaskState.ACTIVE
        self.set_phase(CognitivePhase.EXECUTING)

    def mark_paused(self) -> None:
        self.state = TaskState.PAUSED
        self.set_phase(CognitivePhase.PAUSED)

    def mark_completed(self) -> None:
        self.state = TaskState.COMPLETED
        self.set_phase(CognitivePhase.COMPLETED)

    def mark_failed(self, error: str = "") -> None:
        self.state = TaskState.FAILED
        self.set_phase(CognitivePhase.FAILED)
        if error:
            self.error = error

    def mark_cancelled(self) -> None:
        self.state = TaskState.CANCELLED
        self.set_phase(CognitivePhase.CANCELLED)

    # ------------------------------------------------------------------
    # Plan bookkeeping
    # ------------------------------------------------------------------

    def sync_from_plan(self) -> None:
        """Reconcile completed/pending/failed step ids from the plan."""
        plan = self.plan
        if plan is None:
            return
        self.completed_steps = [
            s.id for s in plan.steps if s.status == StepStatus.COMPLETED
        ]
        self.failed_steps = [
            s.id for s in plan.steps if s.status == StepStatus.FAILED
        ]
        self.pending_steps = [
            s.id for s in plan.steps
            if s.status in (
                StepStatus.PENDING,
                StepStatus.READY,
                StepStatus.WAITING,
                StepStatus.BLOCKED,
            )
        ]
        active = plan.active_step
        self.current_step_id = getattr(active, "id", None)
        self.touch()

    def progress(self) -> float:
        if self.plan is None or not self.plan.steps:
            return 0.0
        return self.plan.completed_steps / len(self.plan.steps)

    # ------------------------------------------------------------------
    # Checkpointing (B16 long-horizon support)
    # ------------------------------------------------------------------

    def checkpoint(self) -> Dict[str, Any]:
        """Serializable checkpoint for pause/resume (B16/B22)."""
        plan_state = None
        if self.plan is not None:
            plan_state = {
                "status": self.plan.status.value,
                "current_step_index": self.plan.current_step_index,
                "steps": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "status": s.status.value,
                        "verified": s.verified,
                        "error": s.error,
                        "retries": s.retries,
                    }
                    for s in self.plan.steps
                ],
            }
        return {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "user_request": self.user_request,
            "goal": self.goal,
            "state": self.state.value,
            "phase": self.phase.value,
            "capability": self.capability,
            "capability_chain": list(self.capability_chain),
            "completed_steps": list(self.completed_steps),
            "failed_steps": list(self.failed_steps),
            "current_step_id": self.current_step_id,
            "verification_state": self.verification_state.value,
            "recovery_state": self.recovery_state.value,
            "confidence": self.confidence,
            "replan_count": self.replan_count,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "plan": plan_state,
        }

    @classmethod
    def from_checkpoint(cls, data: Dict[str, Any]) -> "CognitiveTask":
        """Rebuild a task from a checkpoint (B16 resume)."""
        task = cls(
            task_id=data.get("task_id", ""),
            request_id=data.get("request_id", ""),
            user_request=data.get("user_request", ""),
            goal=data.get("goal", ""),
            state=TaskState(data.get("state", "pending")),
            phase=CognitivePhase(data.get("phase", "received")),
            capability=data.get("capability", ""),
            capability_chain=list(data.get("capability_chain", [])),
            completed_steps=list(data.get("completed_steps", [])),
            failed_steps=list(data.get("failed_steps", [])),
            current_step_id=data.get("current_step_id"),
            verification_state=VerificationState(
                data.get("verification_state", "pending")
            ),
            recovery_state=RecoveryState(data.get("recovery_state", "none")),
            confidence=data.get("confidence", 0.0),
            replan_count=data.get("replan_count", 0),
            error=data.get("error"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
        # Restore plan (step statuses/current index) when available.
        plan_state = data.get("plan")
        if plan_state and task.plan is not None:
            task.plan.status = PlanStatus(plan_state.get("status", "pending"))
            task.plan.current_step_index = plan_state.get("current_step_index", 0)
            task.plan.reset()
            for saved, step in zip(plan_state.get("steps", []), task.plan.steps):
                step.status = StepStatus(saved.get("status", "pending"))
                step.verified = saved.get("verified", False)
                step.error = saved.get("error")
                step.retries = saved.get("retries", 0)
        return task

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "user_request": self.user_request,
            "goal": self.goal,
            "state": self.state.value,
            "phase": self.phase.value,
            "capability": self.capability,
            "capability_chain": list(self.capability_chain),
            "progress": self.progress(),
            "completed_steps": list(self.completed_steps),
            "pending_steps": list(self.pending_steps),
            "failed_steps": list(self.failed_steps),
            "current_step_id": self.current_step_id,
            "verification_state": self.verification_state.value,
            "recovery_state": self.recovery_state.value,
            "confidence": self.confidence,
            "error": self.error,
            "replan_count": self.replan_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class CognitiveTaskRegistry:
    """
    Thread-safe registry of active/past CognitiveTasks (B16 long-horizon).

    Provides pause/resume/cancel/status by task_id and keeps a bounded history
    of completed tasks so goal-level state survives step boundaries.
    """

    def __init__(self, max_history: int = 200) -> None:
        self._lock = threading.RLock()
        self._active: Dict[str, CognitiveTask] = {}
        self._history: Dict[str, CognitiveTask] = {}
        self._max_history = max_history

    # ------------------------------------------------------------------

    def put(self, task: CognitiveTask) -> None:
        with self._lock:
            self._active[task.task_id] = task

    def get(self, task_id: str) -> Optional[CognitiveTask]:
        with self._lock:
            return self._active.get(task_id) or self._history.get(task_id)

    def active(self) -> List[CognitiveTask]:
        with self._lock:
            return list(self._active.values())

    def history(self) -> List[CognitiveTask]:
        with self._lock:
            return list(self._history.values())

    def archive(self, task: CognitiveTask) -> None:
        """Move a finished task into history (bounded)."""
        with self._lock:
            self._active.pop(task.task_id, None)
            self._history[task.task_id] = task
            if len(self._history) > self._max_history:
                # Drop oldest by creation time.
                oldest = min(
                    self._history, key=lambda k: self._history[k].created_at
                )
                self._history.pop(oldest, None)

    def remove(self, task_id: str) -> None:
        with self._lock:
            self._active.pop(task_id, None)
            self._history.pop(task_id, None)

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active": [
                    t.to_dict() for t in self._active.values()
                ],
                "history": [
                    t.to_dict() for t in self._history.values()
                ],
                "active_count": len(self._active),
                "history_count": len(self._history),
            }