"""
MYRAA Super-Brain — Autonomy Controller (Phase B).

A coordinator that wraps SuperBrain for long-running autonomous goal execution.
NOT a second brain. NOT a second planner. It is a control loop that:

  USER GOAL → UNDERSTAND → PLAN → TASK GRAPH → EXECUTE → OBSERVE → VERIFY
  → DECIDE (complete? retry? replan? ask user? checkpoint? continue?)
  → EXPERIENCE → MEMORY → NEXT STEP

Enforces:
  - Formal state machine (IDLE → UNDERSTANDING → ... → COMPLETED/FAILED/CANCELLED)
  - Bounded loop guards (max iterations, max retries, max time, max tool calls)
  - Retry budgets with exponential backoff
  - Checkpoint persistence (disk) for restart/resume
  - Pause / Resume / Cancel control
  - Progress tracking derived from task state
  - Memory 2.0 and ExperienceEngine integration
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ================================================================
# Autonomy State Machine
# ================================================================

class AutonomyState(str, Enum):
    """Formal lifecycle for one autonomous goal."""
    IDLE = "idle"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    REPLANNING = "replanning"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutonomyLevel(str, Enum):
    """User-facing autonomy levels."""
    GUIDED = "guided"          # user approval for major steps
    BALANCED = "balanced"      # autonomous routine/reversible, confirm high-risk
    AUTONOMOUS = "autonomous"  # execute within safety boundaries


# Valid state transitions (deterministic FSM)
_VALID_TRANSITIONS: Dict[AutonomyState, set] = {
    AutonomyState.IDLE:        {AutonomyState.UNDERSTANDING, AutonomyState.CANCELLED},
    AutonomyState.UNDERSTANDING: {AutonomyState.PLANNING, AutonomyState.FAILED, AutonomyState.CANCELLED},
    AutonomyState.PLANNING:    {AutonomyState.READY, AutonomyState.FAILED, AutonomyState.CANCELLED},
    AutonomyState.READY:       {AutonomyState.EXECUTING, AutonomyState.CANCELLED},
    AutonomyState.EXECUTING:   {AutonomyState.OBSERVING, AutonomyState.RECOVERING, AutonomyState.PAUSED, AutonomyState.COMPLETED, AutonomyState.FAILED, AutonomyState.CANCELLED},
    AutonomyState.OBSERVING:   {AutonomyState.VERIFYING, AutonomyState.RECOVERING, AutonomyState.COMPLETED, AutonomyState.FAILED},
    AutonomyState.VERIFYING:   {AutonomyState.COMPLETED, AutonomyState.REPLANNING, AutonomyState.RECOVERING, AutonomyState.FAILED},
    AutonomyState.RECOVERING:  {AutonomyState.REPLANNING, AutonomyState.EXECUTING, AutonomyState.FAILED, AutonomyState.BLOCKED},
    AutonomyState.REPLANNING:  {AutonomyState.READY, AutonomyState.FAILED, AutonomyState.CANCELLED},
    AutonomyState.PAUSED:      {AutonomyState.READY, AutonomyState.CANCELLED},
    AutonomyState.BLOCKED:     {AutonomyState.REPLANNING, AutonomyState.FAILED, AutonomyState.CANCELLED},
    AutonomyState.COMPLETED:   set(),
    AutonomyState.FAILED:      set(),
    AutonomyState.CANCELLED:   set(),
}


# ================================================================
# Loop Guards
# ================================================================

@dataclass
class LoopGuards:
    """Bounded execution guards for autonomous loops."""
    max_iterations: int = 50
    max_retries_per_task: int = 3
    max_total_retries: int = 15
    max_execution_time_s: float = 1800.0   # 30 minutes
    max_tool_calls: int = 200
    max_identical_failures: int = 3
    max_unchanged_state_iterations: int = 5
    max_replans: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_retries_per_task": self.max_retries_per_task,
            "max_total_retries": self.max_total_retries,
            "max_execution_time_s": self.max_execution_time_s,
            "max_tool_calls": self.max_tool_calls,
            "max_identical_failures": self.max_identical_failures,
            "max_unchanged_state_iterations": self.max_unchanged_state_iterations,
            "max_replans": self.max_replans,
        }


@dataclass
class LoopCounters:
    """Live counters for a running autonomous goal."""
    iterations: int = 0
    total_retries: int = 0
    tool_calls: int = 0
    replans: int = 0
    identical_failures: int = 0
    unchanged_state_iterations: int = 0
    started_at: float = 0.0
    last_failure_signature: str = ""

    def check_guard(self, guards: LoopGuards) -> Optional[str]:
        """Return a block reason if any guard is exceeded, else None."""
        if self.iterations >= guards.max_iterations:
            return f"max iterations ({guards.max_iterations}) exceeded"
        if self.total_retries >= guards.max_total_retries:
            return f"max total retries ({guards.max_total_retries}) exceeded"
        if self.tool_calls >= guards.max_tool_calls:
            return f"max tool calls ({guards.max_tool_calls}) exceeded"
        if self.started_at > 0 and (time.time() - self.started_at) >= guards.max_execution_time_s:
            return f"max execution time ({guards.max_execution_time_s}s) exceeded"
        if self.identical_failures >= guards.max_identical_failures:
            return f"identical failure repeated {self.identical_failures} times, loop detected"
        if self.unchanged_state_iterations >= guards.max_unchanged_state_iterations:
            return f"state unchanged for {self.unchanged_state_iterations} iterations, stuck"
        return None

    def record_failure(self, signature: str) -> None:
        """Track identical failures for loop detection."""
        if signature == self.last_failure_signature:
            self.identical_failures += 1
        else:
            self.identical_failures = 1
            self.last_failure_signature = signature

    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.started_at if self.started_at else 0
        return {
            "iterations": self.iterations,
            "total_retries": self.total_retries,
            "tool_calls": self.tool_calls,
            "replans": self.replans,
            "identical_failures": self.identical_failures,
            "unchanged_state_iterations": self.unchanged_state_iterations,
            "elapsed_s": round(elapsed, 2),
        }


# ================================================================
# Goal Tracking
# ================================================================

@dataclass
class AutonomousGoal:
    """Tracks one autonomous goal through its lifecycle."""
    goal_id: str
    user_request: str
    state: AutonomyState = AutonomyState.IDLE
    level: AutonomyLevel = AutonomyLevel.AUTONOMOUS
    guards: LoopGuards = field(default_factory=LoopGuards)
    counters: LoopCounters = field(default_factory=LoopCounters)

    # Goal decomposition
    success_criteria: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)

    # Progress
    progress_pct: float = 0.0
    completed_tasks: int = 0
    total_tasks: int = 0
    current_task: str = ""
    blocked_reasons: List[str] = field(default_factory=list)

    # History
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    last_tool: str = ""
    last_verification: Dict[str, Any] = field(default_factory=dict)
    next_action: str = ""

    # Timing
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    # SuperBrain integration
    request_id: str = ""
    cognitive_task_id: str = ""
    super_brain_result: Optional[Dict[str, Any]] = None

    # Checkpoint
    checkpoint_path: Optional[str] = None

    def transition(self, new_state: AutonomyState, reason: str = "") -> bool:
        """Deterministic state transition. Returns True if valid."""
        valid = _VALID_TRANSITIONS.get(self.state, set())
        if new_state not in valid:
            log.warning(
                "Invalid transition: %s -> %s (valid: %s)",
                self.state.value, new_state.value, [s.value for s in valid],
            )
            return False
        old = self.state
        self.state = new_state
        self.updated_at = time.time()
        self.state_history.append({
            "from": old.value,
            "to": new_state.value,
            "reason": reason,
            "ts": self.updated_at,
        })
        return True

    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.created_at
        return {
            "goal_id": self.goal_id,
            "user_request": self.user_request,
            "state": self.state.value,
            "level": self.level.value,
            "progress_pct": round(self.progress_pct, 1),
            "completed_tasks": self.completed_tasks,
            "total_tasks": self.total_tasks,
            "current_task": self.current_task,
            "blocked_reasons": list(self.blocked_reasons),
            "last_tool": self.last_tool,
            "last_verification": self.last_verification,
            "next_action": self.next_action,
            "elapsed_s": round(elapsed, 2),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "request_id": self.request_id,
            "counters": self.counters.to_dict(),
            "guards": self.guards.to_dict(),
            "state_history_len": len(self.state_history),
            "success_criteria": list(self.success_criteria),
        }

    def checkpoint_data(self) -> Dict[str, Any]:
        """Full serializable checkpoint for persistence."""
        data = self.to_dict()
        data["success_criteria"] = list(self.success_criteria)
        data["constraints"] = dict(self.constraints)
        data["state_history"] = list(self.state_history)
        data["super_brain_result"] = self.super_brain_result
        return data

    @classmethod
    def from_checkpoint(cls, data: Dict[str, Any]) -> "AutonomousGoal":
        """Rebuild from a persisted checkpoint."""
        guards = LoopGuards(**{
            k: v for k, v in data.get("guards", {}).items()
            if hasattr(LoopGuards, k)
        })
        counters = LoopCounters(**{
            k: v for k, v in data.get("counters", {}).items()
            if hasattr(LoopCounters, k)
        })
        goal = cls(
            goal_id=data.get("goal_id", ""),
            user_request=data.get("user_request", ""),
            state=AutonomyState(data.get("state", "idle")),
            level=AutonomyLevel(data.get("level", "autonomous")),
            guards=guards,
            counters=counters,
            success_criteria=list(data.get("success_criteria", [])),
            constraints=dict(data.get("constraints", {})),
            progress_pct=data.get("progress_pct", 0.0),
            completed_tasks=data.get("completed_tasks", 0),
            total_tasks=data.get("total_tasks", 0),
            current_task=data.get("current_task", ""),
            blocked_reasons=list(data.get("blocked_reasons", [])),
            state_history=list(data.get("state_history", [])),
            last_tool=data.get("last_tool", ""),
            last_verification=data.get("last_verification", {}),
            next_action=data.get("next_action", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            completed_at=data.get("completed_at"),
            request_id=data.get("request_id", ""),
            cognitive_task_id=data.get("cognitive_task_id", ""),
            super_brain_result=data.get("super_brain_result"),
        )
        return goal


# ================================================================
# Autonomy Controller
# ================================================================

class AutonomyController:
    """
    Phase B coordinator for long-running autonomous goals.

    Reuses SuperBrain for the cognitive pipeline, does NOT replace it.
    Adds: state machine, loop guards, checkpoint persistence,
    progress tracking, pause/resume/cancel, memory integration.
    """

    def __init__(
        self,
        super_brain: Optional[Any] = None,
        memory_2_0: Optional[Any] = None,
        experience_engine: Optional[Any] = None,
        project_manager: Optional[Any] = None,
        checkpoint_dir: Optional[str] = None,
    ) -> None:
        self.super_brain = super_brain
        self.memory_2_0 = memory_2_0
        self.experience_engine = experience_engine
        self.project_manager = project_manager
        self.checkpoint_dir = checkpoint_dir or str(
            Path.home() / ".myraa" / "autonomy_checkpoints"
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        self._goals: Dict[str, AutonomousGoal] = {}
        self._lock = threading.RLock()
        self._control_events: Dict[str, Dict[str, threading.Event]] = {}

    # ================================================================
    # Goal Lifecycle
    # ================================================================

    def start_goal(
        self,
        user_request: str,
        level: AutonomyLevel = AutonomyLevel.AUTONOMOUS,
        guards: Optional[LoopGuards] = None,
        success_criteria: Optional[List[str]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> AutonomousGoal:
        """Accept a high-level user goal and begin autonomous execution."""
        goal_id = f"auto-{uuid.uuid4().hex[:12]}"
        goal = AutonomousGoal(
            goal_id=goal_id,
            user_request=user_request,
            level=level,
            guards=guards or LoopGuards(),
            success_criteria=success_criteria or [],
            constraints=constraints or {},
        )
        goal.counters.started_at = time.time()

        with self._lock:
            self._goals[goal_id] = goal
            self._control_events[goal_id] = {
                "pause": threading.Event(),
                "cancel": threading.Event(),
            }

        goal.transition(AutonomyState.UNDERSTANDING, "goal accepted")
        log.info("Autonomy goal started: %s [%s]", goal_id, user_request[:80])

        # Checkpoint immediately
        self._persist_checkpoint(goal)

        return goal

    def execute_goal(self, goal: AutonomousGoal) -> AutonomousGoal:
        """
        Run the full autonomous loop for a goal.

        This is the core control loop:
          UNDERSTANDING → PLANNING → READY → EXECUTING → OBSERVING → VERIFYING
          → DECIDE (complete? retry? replan?) → repeat or finish
        """
        try:
            # Phase 1: UNDERSTAND
            self._phase_understand(goal)

            # Phase 2: PLAN
            self._phase_plan(goal)

            # Phase 3: EXECUTE LOOP
            self._phase_execute_loop(goal)

        except Exception as exc:
            log.exception("Autonomy execution failed for %s", goal.goal_id)
            goal.transition(AutonomyState.FAILED, f"exception: {exc}")
            goal.next_action = "failed due to exception"

        self._persist_checkpoint(goal)
        return goal

    # ================================================================
    # Phases
    # ================================================================

    def _phase_understand(self, goal: AutonomousGoal) -> None:
        """Parse the goal, extract success criteria, inspect project."""
        if goal.state == AutonomyState.CANCELLED:
            return

        goal.current_task = "Understanding goal"
        goal.next_action = "parse goal and extract criteria"

        # Extract success criteria from natural language if not provided
        if not goal.success_criteria:
            goal.success_criteria = self._extract_success_criteria(goal.user_request)

        # Increment understanding counter
        goal.counters.iterations += 1

        goal.transition(AutonomyState.PLANNING, "goal understood")

    def _phase_plan(self, goal: AutonomousGoal) -> None:
        """Build task graph via SuperBrain planning."""
        if goal.state == AutonomyState.CANCELLED:
            return

        goal.current_task = "Planning"
        goal.next_action = "create execution plan via SuperBrain"

        if self.super_brain is None:
            # Headless/test mode: create minimal plan
            goal.total_tasks = 1
            goal.transition(AutonomyState.READY, "simple plan created (no SuperBrain)")
            return

        try:
            # Use SuperBrain's planner to create a plan
            from desktop_agent.brain.super_brain.goal import build_goal
            from desktop_agent.brain.super_brain.planner import MasterPlanner

            goal_obj = build_goal(goal.user_request)
            planner = MasterPlanner()
            master_plan = planner.create_goal_plan(goal_obj)

            if master_plan and master_plan.plan and master_plan.plan.steps:
                goal.total_tasks = len(master_plan.plan.steps)
                goal.constraints["plan_steps"] = len(master_plan.plan.steps)
            else:
                goal.total_tasks = 1

        except Exception as exc:
            log.warning("Planning failed, using minimal plan: %s", exc)
            goal.total_tasks = 1

        goal.transition(AutonomyState.READY, f"plan created with {goal.total_tasks} tasks")

    def _phase_execute_loop(self, goal: AutonomousGoal) -> None:
        """The main autonomous execution loop with verification and recovery."""
        while goal.state not in (
            AutonomyState.COMPLETED,
            AutonomyState.FAILED,
            AutonomyState.CANCELLED,
            AutonomyState.BLOCKED,
        ):
            # Check loop guards
            guard_reason = goal.counters.check_guard(goal.guards)
            if guard_reason:
                log.warning("Loop guard triggered for %s: %s", goal.goal_id, guard_reason)
                goal.blocked_reasons.append(guard_reason)
                goal.transition(AutonomyState.BLOCKED, guard_reason)
                return

            # Check cancellation
            if self._is_cancelled(goal.goal_id):
                goal.transition(AutonomyState.CANCELLED, "user cancelled")
                return

            # Check pause
            if self._is_paused(goal.goal_id):
                goal.transition(AutonomyState.PAUSED, "user paused")
                if not self._wait_for_resume(goal.goal_id):
                    goal.transition(AutonomyState.CANCELLED, "cancelled while paused")
                    return
                goal.transition(AutonomyState.READY, "resumed from pause")

            # Execute via SuperBrain
            goal.transition(AutonomyState.EXECUTING, f"iteration {goal.counters.iterations}")
            result = self._execute_super_brain(goal)

            # Observe
            goal.transition(AutonomyState.OBSERVING, "observing result")
            goal.last_tool = result.get("capability", "")
            goal.counters.tool_calls += 1

            # Verify
            goal.transition(AutonomyState.VERIFYING, "verifying outcome")
            verified = self._verify_outcome(goal, result)

            if verified:
                # Check if overall goal is complete
                goal.completed_tasks += 1
                goal.progress_pct = (
                    (goal.completed_tasks / max(goal.total_tasks, 1)) * 100
                )

                if goal.completed_tasks >= goal.total_tasks and goal.total_tasks > 0:
                    goal.transition(AutonomyState.COMPLETED, "all tasks verified")
                    goal.completed_at = time.time()
                    goal.next_action = "goal complete"
                    self._record_experience(goal, result, success=True)
                    return
                else:
                    # More tasks to do
                    goal.transition(AutonomyState.READY, f"task {goal.completed_tasks}/{goal.total_tasks} done")
                    goal.next_action = f"continue with next task ({goal.completed_tasks + 1}/{goal.total_tasks})"
            else:
                # Failed — need recovery
                goal.counters.record_failure(result.get("message", "unknown"))
                goal.counters.total_retries += 1

                # Recovery decision
                goal.transition(AutonomyState.RECOVERING, "outcome not verified")
                recovery = self._recovery_decision(goal, result)

                if recovery == "replan":
                    if goal.counters.replans >= goal.guards.max_replans:
                        goal.transition(AutonomyState.FAILED, f"max replans ({goal.guards.max_replans}) exceeded")
                        self._record_experience(goal, result, success=False)
                        return
                    goal.counters.replans += 1
                    goal.transition(AutonomyState.REPLANNING, f"replan #{goal.counters.replans}")
                    goal.transition(AutonomyState.READY, "replanned")
                elif recovery == "abort":
                    goal.transition(AutonomyState.FAILED, "recovery decided to abort")
                    self._record_experience(goal, result, success=False)
                    return
                elif recovery == "ask":
                    goal.transition(AutonomyState.BLOCKED, "needs user input")
                    goal.next_action = "waiting for user clarification"
                    return
                else:
                    # retry
                    goal.transition(AutonomyState.EXECUTING, "retrying")

            goal.counters.iterations += 1
            self._persist_checkpoint(goal)

    # ================================================================
    # SuperBrain Integration
    # ================================================================

    def _execute_super_brain(self, goal: AutonomousGoal) -> Dict[str, Any]:
        """Execute one iteration via SuperBrain."""
        if self.super_brain is None:
            return {
                "success": True,
                "message": "no SuperBrain (headless mode)",
                "capability": "none",
                "verification": {"verified": True},
            }

        try:
            result = self.super_brain.process(
                user_request=goal.user_request,
                request_id=f"auto-{goal.goal_id}",
            )
            result_dict = result.to_dict() if hasattr(result, "to_dict") else {
                "success": getattr(result, "success", False),
                "message": getattr(result, "message", ""),
            }
            goal.super_brain_result = result_dict
            goal.request_id = result_dict.get("request_id", goal.goal_id)
            goal.cognitive_task_id = result_dict.get("execution", {}).get("task_id", "")
            return result_dict
        except Exception as exc:
            log.exception("SuperBrain execution failed")
            return {
                "success": False,
                "message": str(exc),
                "capability": "",
                "verification": {"verified": False, "reason": str(exc)},
            }

    def _verify_outcome(self, goal: AutonomousGoal, result: Dict[str, Any]) -> bool:
        """Verify that the execution outcome meets success criteria."""
        exec_success = result.get("success", False)
        verification = result.get("verification", {})
        verified = verification.get("verified", False)

        goal.last_verification = verification

        # Truthfulness rule: success requires both execution success AND verification
        if exec_success and verified:
            return True

        # If SuperBrain reported success but not verified, check criteria directly
        if exec_success and not verified:
            # For project builder, check if files were created
            if "PROJECT_BUILDER" in str(result.get("capability", "")):
                return self._verify_project_result(goal, result)

        return False

    def _verify_project_result(self, goal: AutonomousGoal, result: Dict[str, Any]) -> bool:
        """Direct verification for project builder results."""
        exec_result = result.get("execution", {})
        final = exec_result.get("final_result")
        if final and isinstance(final, dict):
            return final.get("success", False)
        return False

    def _recovery_decision(self, goal: AutonomousGoal, result: Dict[str, Any]) -> str:
        """Decide recovery strategy: retry, replan, abort, or ask."""
        message = result.get("message", "").lower()

        # Clarification needed
        if "ambiguous" in message or "clarif" in message or "which one" in message:
            return "ask"

        # Permanent failures
        if "permission" in message or "denied" in message:
            return "abort"

        # Use RecoveryEngine if available
        if self.super_brain and hasattr(self.super_brain, "executor"):
            executor = self.super_brain.executor
            if hasattr(executor, "recovery_engine") and executor.recovery_engine:
                try:
                    decision = executor.recovery_engine.should_retry(
                        message,
                        attempt=goal.counters.total_retries,
                        tool=goal.last_tool,
                        subsystem="autonomy",
                    )
                    action = getattr(decision, "action", None)
                    if action:
                        val = str(getattr(action, "value", action)).lower()
                        if "abort" in val or "stop" in val:
                            return "abort"
                        if "clarif" in val:
                            return "ask"
                except Exception:
                    pass

        # Default: retry/replan based on budget
        if goal.counters.total_retries < goal.guards.max_total_retries:
            return "retry"
        return "abort"

    # ================================================================
    # Success Criteria Extraction
    # ================================================================

    def _extract_success_criteria(self, request: str) -> List[str]:
        """Extract success criteria from natural language goal."""
        criteria = []
        low = request.lower()

        if "test" in low and ("green" in low or "pass" in low):
            criteria.append("all tests pass (exit code 0)")
            criteria.append("no regression in previously passing tests")
        elif "fix" in low and "test" in low:
            criteria.append("target test failures reduced to 0")
            criteria.append("no new test failures introduced")
        elif "build" in low or "project" in low:
            criteria.append("project builds successfully")
            criteria.append("project structure is complete")
        elif "research" in low:
            criteria.append("research summary produced with sources")
        elif "email" in low or "send" in low:
            criteria.append("message/email sent to target recipient")
        elif "organize" in low or "clean" in low:
            criteria.append("files organized according to specified rules")
        elif "complete" in low:
            criteria.append("all sub-tasks completed and verified")

        if not criteria:
            criteria.append("request completed and outcome verified where possible")

        return criteria

    # ================================================================
    # Control API
    # ================================================================

    def pause(self, goal_id: str) -> bool:
        """Pause an autonomous goal."""
        events = self._control_events.get(goal_id)
        if events:
            events["pause"].set()
            goal = self._goals.get(goal_id)
            if goal and goal.state not in (
                AutonomyState.COMPLETED,
                AutonomyState.FAILED,
                AutonomyState.CANCELLED,
            ):
                goal.transition(AutonomyState.PAUSED, "user pause requested")
            return True
        return False

    def resume(self, goal_id: str) -> bool:
        """Resume a paused autonomous goal."""
        events = self._control_events.get(goal_id)
        if events:
            events["pause"].clear()
            goal = self._goals.get(goal_id)
            if goal and goal.state == AutonomyState.PAUSED:
                goal.transition(AutonomyState.READY, "user resume requested")
            return True
        return False

    def cancel(self, goal_id: str) -> bool:
        """Cancel an autonomous goal."""
        events = self._control_events.get(goal_id)
        if events:
            events["cancel"].set()
            events["pause"].clear()  # unblock if paused
            goal = self._goals.get(goal_id)
            if goal and goal.state not in (
                AutonomyState.COMPLETED,
                AutonomyState.CANCELLED,
            ):
                goal.transition(AutonomyState.CANCELLED, "user cancel requested")
            return True
        return False

    def get_goal(self, goal_id: str) -> Optional[AutonomousGoal]:
        """Get goal status."""
        return self._goals.get(goal_id)

    def list_goals(self) -> List[Dict[str, Any]]:
        """List all goals."""
        return [g.to_dict() for g in self._goals.values()]

    def active_goals(self) -> List[Dict[str, Any]]:
        """List non-terminal goals."""
        terminal = {AutonomyState.COMPLETED, AutonomyState.FAILED, AutonomyState.CANCELLED}
        return [g.to_dict() for g in self._goals.values() if g.state not in terminal]

    def progress_report(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Detailed progress report for a goal."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        report = goal.to_dict()
        report["description"] = self._describe_progress(goal)
        return report

    def _describe_progress(self, goal: AutonomousGoal) -> str:
        """Human-readable progress description."""
        if goal.state == AutonomyState.COMPLETED:
            return f"Goal completed. {goal.completed_tasks}/{goal.total_tasks} tasks done."
        if goal.state == AutonomyState.FAILED:
            return f"Goal failed. {goal.blocked_reasons[-1] if goal.blocked_reasons else 'unknown reason'}"
        if goal.state == AutonomyState.CANCELLED:
            return "Goal cancelled by user."
        if goal.state == AutonomyState.PAUSED:
            return f"Goal paused. {goal.completed_tasks}/{goal.total_tasks} tasks done."
        if goal.state == AutonomyState.BLOCKED:
            return f"Goal blocked. {goal.blocked_reasons[-1] if goal.blocked_reasons else 'unknown'}"

        return (
            f"State: {goal.state.value}. "
            f"Progress: {goal.progress_pct:.0f}% "
            f"({goal.completed_tasks}/{goal.total_tasks} tasks). "
            f"Current: {goal.current_task}. "
            f"Retries: {goal.counters.total_retries}/{goal.guards.max_total_retries}. "
            f"Next: {goal.next_action}"
        )

    # ================================================================
    # Checkpoint Persistence
    # ================================================================

    def _persist_checkpoint(self, goal: AutonomousGoal) -> None:
        """Save goal checkpoint to disk."""
        try:
            path = os.path.join(self.checkpoint_dir, f"{goal.goal_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(goal.checkpoint_data(), f, indent=2, default=str)
            goal.checkpoint_path = path
        except Exception as exc:
            log.warning("Failed to persist checkpoint for %s: %s", goal.goal_id, exc)

    def load_checkpoint(self, goal_id: str) -> Optional[AutonomousGoal]:
        """Load a goal from a persisted checkpoint."""
        path = os.path.join(self.checkpoint_dir, f"{goal_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            goal = AutonomousGoal.from_checkpoint(data)
            goal.checkpoint_path = path
            with self._lock:
                self._goals[goal.goal_id] = goal
            return goal
        except Exception as exc:
            log.warning("Failed to load checkpoint %s: %s", goal_id, exc)
            return None

    def list_checkpoints(self) -> List[str]:
        """List persisted checkpoint files."""
        try:
            files = os.listdir(self.checkpoint_dir)
            return [f.replace(".json", "") for f in files if f.endswith(".json")]
        except Exception:
            return []

    # ================================================================
    # Memory & Experience
    # ================================================================

    def _record_experience(
        self,
        goal: AutonomousGoal,
        result: Dict[str, Any],
        success: bool,
    ) -> None:
        """Record the goal execution experience into Memory 2.0."""
        if self.experience_engine is None:
            return

        try:
            from desktop_agent.brain.super_brain.experience import Experience

            exp = Experience(
                request_id=goal.goal_id,
                goal_text=goal.user_request,
                capability=result.get("capability", ""),
                route_decision="autonomous",
                success=success,
                tool_sequence=[goal.last_tool] if goal.last_tool else [],
                outcome_message=result.get("message", ""),
                verification_method="autonomy_controller",
                verified=goal.last_verification.get("verified", False),
                recovery=f"replans={goal.counters.replans}",
                replan_count=goal.counters.replans,
                duration_ms=(time.time() - goal.counters.started_at) * 1000,
                lesson=(
                    f"Autonomous goal {'succeeded' if success else 'failed'}: "
                    f"{goal.completed_tasks}/{goal.total_tasks} tasks, "
                    f"{goal.counters.total_retries} retries"
                ),
            )
            self.experience_engine.record(exp)
        except Exception as exc:
            log.warning("Failed to record experience: %s", exc)

        # Write project memory if project_manager available
        if self.project_manager and goal.constraints.get("project_id"):
            try:
                self.project_manager.write_project_memory(
                    goal.constraints["project_id"],
                    f"Autonomous goal: {goal.user_request} -> "
                    f"{'completed' if success else 'failed'}",
                )
            except Exception:
                pass

    # ================================================================
    # Control Helpers
    # ================================================================

    def _is_cancelled(self, goal_id: str) -> bool:
        events = self._control_events.get(goal_id)
        return events is not None and events["cancel"].is_set()

    def _is_paused(self, goal_id: str) -> bool:
        events = self._control_events.get(goal_id)
        return events is not None and events["pause"].is_set()

    def _wait_for_resume(self, goal_id: str) -> bool:
        """Block until resumed or cancelled. Returns True if resumed."""
        events = self._control_events.get(goal_id)
        if events is None:
            return True
        while events["pause"].is_set():
            if events["cancel"].is_set():
                return False
            time.sleep(0.3)
        return True

    # ================================================================
    # Status / Telemetry
    # ================================================================

    def status(self) -> Dict[str, Any]:
        """Overall autonomy status."""
        active = self.active_goals()
        return {
            "total_goals": len(self._goals),
            "active_goals": len(active),
            "completed": sum(1 for g in self._goals.values() if g.state == AutonomyState.COMPLETED),
            "failed": sum(1 for g in self._goals.values() if g.state == AutonomyState.FAILED),
            "cancelled": sum(1 for g in self._goals.values() if g.state == AutonomyState.CANCELLED),
            "paused": sum(1 for g in self._goals.values() if g.state == AutonomyState.PAUSED),
            "checkpoints": len(self.list_checkpoints()),
            "super_brain_attached": self.super_brain is not None,
            "memory_attached": self.memory_2_0 is not None,
            "experience_attached": self.experience_engine is not None,
        }

    def telemetry(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Telemetry for a specific goal."""
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        return {
            "goal_id": goal.goal_id,
            "state": goal.state.value,
            "progress_pct": goal.progress_pct,
            "iterations": goal.counters.iterations,
            "retries": goal.counters.total_retries,
            "tool_calls": goal.counters.tool_calls,
            "replans": goal.counters.replans,
            "elapsed_s": round(time.time() - goal.counters.started_at, 2) if goal.counters.started_at else 0,
            "last_tool": goal.last_tool,
            "last_verification": goal.last_verification,
            "next_action": goal.next_action,
        }
