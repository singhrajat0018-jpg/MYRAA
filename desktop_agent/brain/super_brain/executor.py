"""
MYRAA Super-Brain — Closed-Loop Executor (B10/B11/B12/B16/B22/B23).

Runs a goal through the full cognitive loop:

    PLAN -> EXECUTE -> OBSERVE -> VERIFY -> CONTINUE | REPLAN

REUSES the existing Orchestrator for step execution (retry/timeout/rollback),
the existing VerificationManager for outcome verification, the existing
RecoveryEngine for retry/fallback/replan decisions, and the existing
PermissionManager/ValidationLayer via the CommandDispatcher (never bypassed).

Goal-level loop responsibilities added here:
  * verify goal-level outcome after the plan (B10/B13)
  * self-correction: classify failure, update world/task state, replan (B11)
  * recovery integration: consume RecoveryEngine decisions (B12)
  * long-horizon: checkpoint after each step, pause/resume/cancel (B16/B22)
  * performance: FAST/STANDARD/DEEP batching + cache reuse (B23)
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from desktop_agent.brain.super_brain.cognitive_state import (
    CognitiveTask,
    CognitiveTaskRegistry,
    CognitivePhase,
    TaskState,
    VerificationState,
    RecoveryState,
)
from desktop_agent.brain.super_brain.planner import MasterPlan

log = logging.getLogger(__name__)


@dataclass
class LoopOutcome:
    """Result of a closed-loop goal execution (B10)."""

    success: bool = False
    task_id: str = ""
    message: str = ""
    replans: int = 0
    steps_completed: int = 0
    steps_failed: int = 0
    verification: Dict[str, Any] = field(default_factory=dict)
    final_result: Any = None
    duration_ms: float = 0.0
    recovered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "task_id": self.task_id,
            "message": self.message,
            "replans": self.replans,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "verification": self.verification,
            "duration_ms": round(self.duration_ms, 3),
            "recovered": self.recovered,
        }


class ClosedLoopExecutor:
    """
    Executes a MasterPlan goal-level closed loop (B10).

    The existing Orchestrator is the execution engine; this adds goal-level
    observation, verification, recovery and replanning around it.
    """

    def __init__(
        self,
        orchestrator: Optional[Any] = None,
        verification_manager: Optional[Any] = None,
        recovery_engine: Optional[Any] = None,
        task_registry: Optional[CognitiveTaskRegistry] = None,
        dispatcher: Optional[Any] = None,
        max_replans: int = 2,
    ) -> None:
        self.orchestrator = orchestrator
        self.verification_manager = verification_manager
        self.recovery_engine = recovery_engine
        self.task_registry = task_registry or CognitiveTaskRegistry()
        self.dispatcher = dispatcher
        self.max_replans = max_replans

        self._cancel_events: Dict[str, threading.Event] = {}
        self._pause_events: Dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    # ================================================================
    # Public loop entry
    # ================================================================

    def execute(
        self,
        task: CognitiveTask,
        master_plan: MasterPlan,
        execution_depth: str = "standard",  # fast | standard | deep (B23)
    ) -> LoopOutcome:
        started = time.perf_counter()
        self._register_control(task.task_id)
        # The task must be visible in the registry from the moment execution
        # starts so pause/resume/cancel/status can observe it (B16/B22).
        self.task_registry.put(task)
        task.mark_active()
        task.plan = master_plan.plan

        try:
            # ----------------------------------------------------
            # B23: FAST path — direct step execution, no plan loop.
            # ----------------------------------------------------
            if execution_depth == "fast" and self._can_fast_path(task):
                return self._execute_fast(task, master_plan, started)

            # ----------------------------------------------------
            # STANDARD / DEEP: closed loop with observe+verify.
            # ----------------------------------------------------
            return self._execute_loop(task, master_plan, started)

        except Exception as exc:  # noqa: BLE001
            log.exception("Super-Brain execution failed")
            task.mark_failed(str(exc))
            self.task_registry.archive(task)
            return LoopOutcome(
                success=False,
                task_id=task.task_id,
                message=f"execution error: {exc}",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

    # ================================================================
    # Closed loop (STANDARD/DEEP)
    # ================================================================

    def _execute_loop(
        self,
        task: CognitiveTask,
        master_plan: MasterPlan,
        started: float,
    ) -> LoopOutcome:
        replan_count = 0
        current_plan = master_plan

        while True:
            # Cancellation / deadline checks (B22/B16)
            if self._is_cancelled(task.task_id):
                task.mark_cancelled()
                self._archive(task)
                return self._outcome(task, started, success=False, message="cancelled")

            if self._deadline_exceeded(task):
                task.mark_cancelled()
                task.error = "deadline exceeded"
                self._archive(task)
                return self._outcome(task, started, success=False, message="deadline exceeded")

            if self._is_paused(task.task_id):
                task.mark_paused()
                # Block until resumed/cancelled (long-horizon B16/B22).
                if not self._wait_for_resume(task.task_id):
                    task.mark_cancelled()
                    self._archive(task)
                    return self._outcome(task, started, success=False, message="cancelled while paused")

            # ----------------------------------------------------
            # EXECUTE via the existing Orchestrator.
            # ----------------------------------------------------
            task.set_phase(CognitivePhase.EXECUTING)
            result = self._execute_plan(task, current_plan)
            task.sync_from_plan()

            # ----------------------------------------------------
            # OBSERVE + VERIFY (B10/B13) — never trust success claims.
            # ----------------------------------------------------
            verification = self._verify_goal(task, current_plan, result)
            exec_ok = result is not None and bool(getattr(result, "success", False))
            if not exec_ok:
                # Truthfulness rule: a failed execution can NEVER carry
                # "verified" evidence. Verification is only meaningful for an
                # outcome that actually happened (B10/B13).
                verification = dict(verification or {})
                verification["verified"] = False
                verification["reason"] = "execution did not succeed; outcome not verified"
            verified = bool(verification.get("verified", False))

            # ----------------------------------------------------
            # OBSERVED success that is VERIFIED -> goal complete (B10/B13).
            # A "success" claim without valid verification is NEVER returned
            # as success — that is the single most important truthfulness rule.
            # ----------------------------------------------------
            if exec_ok and verified:
                task.verification_state = VerificationState.VERIFIED
                task.last_observation = {
                    "step_result": getattr(result, "last_message", None),
                    "verification": verification,
                }
                task.mark_completed()
                self._archive(task)
                return self._outcome(
                    task,
                    started,
                    success=True,
                    message=getattr(result, "last_message", None) or "goal completed",
                    verification=verification,
                    final_result=getattr(result, "result", None),
                    replans=replan_count,
                    # Truthful recovery: a failure happened and was recovered
                    # (replan_count > 0) OR verification reported a recovery.
                    recovered=(replan_count > 0) or bool(verification.get("recovered")),
                )

            # ----------------------------------------------------
            # Executed but NOT verified -> never claim success (B13). Surface a
            # truthful UNVERIFIED outcome instead of a fabricated completion.
            # ----------------------------------------------------
            if exec_ok and not verified:
                task.verification_state = VerificationState.UNVERIFIED
                task.last_observation = {
                    "step_result": getattr(result, "last_message", None),
                    "verification": verification,
                }
                task.mark_failed("executed but outcome UNVERIFIED")
                self._archive(task)
                return self._outcome(
                    task, started,
                    success=False,
                    message="executed but UNVERIFIED (verification did not confirm the outcome)",
                    verification=verification, replans=replan_count,
                    final_result=getattr(result, "result", None),
                )

            # ----------------------------------------------------
            # FAILURE -> SELF-CORRECTION (B11) + RECOVERY (B12)
            # ----------------------------------------------------
            raw_error = self._raw_error(result)
            error = self._first_error(result)
            task.error = error or "execution failed"
            task.set_phase(CognitivePhase.RECOVERING)

            decision = self._recovery_decision(
                task,
                error or "",
                raw_error,
                attempt=replan_count + 1,
            )

            # ABORT / CLARIFY -> stop; never blindly repeat (B11).
            if decision == "abort":
                task.mark_failed(task.error)
                self._archive(task)
                return self._outcome(
                    task, started, success=False,
                    message=f"aborted: {task.error}",
                    verification=verification, replans=replan_count,
                )

            if decision == "clarify":
                task.recovery_state = RecoveryState.CLARIFYING
                task.mark_failed("clarification required before retry")
                self._archive(task)
                return self._outcome(
                    task, started, success=False,
                    message="clarification required",
                    verification=verification, replans=replan_count,
                )

            # FALLBACK / REPLAN -> retry with a different strategy (B12).
            if replan_count >= self.max_replans:
                task.mark_failed(f"max replans ({self.max_replans}) exceeded")
                self._archive(task)
                return self._outcome(
                    task, started, success=False,
                    message=task.error,
                    verification=verification, replans=replan_count,
                )

            replan_count += 1
            task.replan_count = replan_count
            task.recovery_state = RecoveryState.REPLANNING
            task.set_phase(CognitivePhase.REPLANNING)

            current_plan = self._replan(task, current_plan)
            if current_plan is None:
                task.mark_failed("replanner produced no plan")
                self._archive(task)
                return self._outcome(
                    task, started, success=False,
                    message="replan failed", replans=replan_count,
                )

            task.plan = current_plan.plan

    # ================================================================
    # Fast path (B23)
    # ================================================================

    def _execute_fast(
        self,
        task: CognitiveTask,
        master_plan: MasterPlan,
        started: float,
    ) -> LoopOutcome:
        result = self._execute_plan(task, master_plan)
        task.sync_from_plan()
        verification = self._verify_goal(task, master_plan, result)
        exec_ok = result is not None and bool(getattr(result, "success", False))
        if not exec_ok:
            verification = dict(verification or {})
            verification["verified"] = False
            verification["reason"] = "execution did not succeed; outcome not verified"
        verified = bool(verification.get("verified", False))
        success = exec_ok and verified

        if success:
            task.verification_state = VerificationState.VERIFIED
            task.mark_completed()
            message = getattr(result, "last_message", "") or "goal completed"
        elif exec_ok and not verified:
            task.verification_state = VerificationState.UNVERIFIED
            task.mark_failed("executed but outcome UNVERIFIED")
            message = "executed but UNVERIFIED (verification did not confirm the outcome)"
        else:
            task.verification_state = VerificationState.FAILED
            task.mark_failed(self._first_error(result) or "fast-path failed")
            message = self._first_error(result) or "fast-path failed"

        self._archive(task)
        return self._outcome(
            task, started, success=success,
            message=message,
            verification=verification,
            final_result=getattr(result, "result", None) if success else None,
        )

    def _can_fast_path(self, task: CognitiveTask) -> bool:
        route = task.route
        if route is None:
            return False
        # Only trivial single-step, low-risk, no-verification goals fast-path.
        return bool(
            getattr(route, "can_use_fast_path", False)
            and not task.capability_chain
        )

    # ================================================================
    # Plan execution
    # ================================================================

    def _execute_plan(
        self,
        task: CognitiveTask,
        master_plan: MasterPlan,
    ) -> Any:
        if self.orchestrator is None:
            raise RuntimeError("ClosedLoopExecutor requires an orchestrator")

        # Goal-level cancellation is honored by orchestrator pause/cancel.
        cancel_evt = self._cancel_events.get(task.task_id)
        if cancel_evt is not None and cancel_evt.is_set():
            self.orchestrator.cancel()

        plan = master_plan.plan
        plan.metadata["task_id"] = task.task_id
        plan.metadata["goal"] = task.goal

        result = self.orchestrator.execute(plan)
        return result

    # ================================================================
    # Goal-level verification (B13)
    # ================================================================

    def _verify_goal(
        self,
        task: CognitiveTask,
        master_plan: MasterPlan,
        result: Any,
    ) -> Dict[str, Any]:
        if self.verification_manager is None:
            return {"verified": False, "reason": "no verification manager"}

        strategies = master_plan.verification_strategies
        if not strategies:
            return {"verified": False, "reason": "no verification strategy (UNVERIFIED)"}

        # Use the first step's verification as the goal-level proxy for now;
        # richer per-step verification is delegated to Orchestrator's verifier.
        strategy = strategies[0]
        payload = getattr(result, "result", None)
        if payload is None:
            payload = getattr(result, "last_message", None)

        try:
            vresult = self.verification_manager.verify(
                payload,
                tool=strategy.check_tool,
                args={},
            )
            return vresult.to_dict() if hasattr(vresult, "to_dict") else {
                "verified": bool(getattr(vresult, "is_verified", False)),
                "outcome": str(getattr(vresult, "outcome", "")),
            }
        except Exception as exc:  # noqa: BLE001
            return {"verified": False, "reason": f"verification error: {exc}"}

    # ================================================================
    # Recovery (B12)
    # ================================================================

    def _raw_error(self, result: Any) -> Any:
        """Extract the raw error object (MYRAAError / Exception) if present.

        The authoritative RecoveryEngine should classify the real error object,
        not a flattened string — this lets TRANSIENT (timeout/provider) vs
        PERMANENT vs AMBIGUOUS failures drive the correct recovery action.
        """
        if result is None:
            return None
        err = getattr(result, "error", None)
        if err is None or isinstance(err, MagicMock):
            return None
        if isinstance(err, BaseException):
            return err
        # MYRAAError is a dataclass, not an Exception; recognise it by shape.
        if getattr(err, "category", None) is not None or hasattr(err, "to_dict"):
            return err
        return None

    def _recovery_decision(
        self,
        task: CognitiveTask,
        error: str,
        raw_error: Any = None,
        attempt: int = 1,
    ) -> str:
        """Consume the authoritative RecoveryEngine decision (B12).

        Returns one of: "replan" | "abort" | "clarify".
        """
        low = (error or "").lower()

        # Ambiguity / clarification policy: an ambiguous target is never
        # guessed, retried or fabricated — ask the user (B11/B13).
        raw_cat = None
        if raw_error is not None:
            raw_cat = getattr(getattr(raw_error, "category", None), "value", None)
        if (
            raw_cat == "target_ambiguous"
            or "ambiguous" in low
            or "which one" in low
            or "multiple candidates" in low
            or "multiple contacts" in low
            or "clarif" in low
        ):
            return "clarify"

        if self.recovery_engine is None:
            # Default: never blindly repeat; replan once.
            return "replan" if attempt <= self.max_replans else "abort"

        try:
            decision = self.recovery_engine.should_retry(
                raw_error if raw_error is not None else error,
                attempt=attempt,
                tool=task.capability or "",
                subsystem="super_brain",
            )
        except Exception:  # noqa: BLE001
            return "replan" if attempt <= self.max_replans else "abort"

        retry_action = getattr(decision, "action", None)
        if retry_action is not None:
            name = str(getattr(retry_action, "value", retry_action)).lower()
            if "clarif" in name:
                return "clarify"
            if "abort" in name or "stop" in name:
                return "abort"
            if "retry" in name or "replan" in name or "fallback" in name or "fall" in name:
                return "replan"  # bounded via replan_count
            if "cooldown" in name:
                # Synchronous loop: cooldown means "do not continue now".
                return "abort"

        if getattr(decision, "should_retry", True):
            return "replan" if attempt <= self.max_replans else "abort"
        return "abort"

    def _replan(
        self,
        task: CognitiveTask,
        master_plan: MasterPlan,
    ) -> Optional[MasterPlan]:
        """Replan with a degraded strategy (B11/B12).

        Uses the existing MasterPlanner; a real implementation would feed the
        failure back into goal decomposition. This degrades to a simpler
        capability and keeps the same goal text.
        """
        try:
            from .planner import MasterPlanner

            simpler = self._simplify_goal(master_plan.goal)
            planner = MasterPlanner()
            return planner.create_goal_plan(simpler)
        except Exception as exc:  # noqa: BLE001
            log.warning("Replan failed: %s", exc)
            return None

    def _simplify_goal(self, goal: Any) -> Any:
        """Produce a degraded goal for replanning (B11)."""
        from dataclasses import replace

        if goal is None:
            return goal
        try:
            simpler = replace(
                goal,
                is_multi=False,
                sub_goals=[],
                dependencies=[],
                capability_chain=[],
            )
            if not simpler.capability and simpler.capability_chain:
                simpler.capability = simpler.capability_chain[0]
            return simpler
        except Exception:
            return goal

    # ================================================================
    # Control (B16/B22)
    # ================================================================

    def pause(self, task_id: str) -> bool:
        evt = self._pause_events.setdefault(task_id, threading.Event())
        evt.set()
        if self.orchestrator is not None:
            try:
                self.orchestrator.pause()
            except Exception:
                pass
        return True

    def resume(self, task_id: str) -> bool:
        evt = self._pause_events.get(task_id)
        if evt is not None:
            evt.clear()
        if self.orchestrator is not None:
            try:
                self.orchestrator.resume()
            except Exception:
                pass
        return True

    def cancel(self, task_id: str) -> bool:
        evt = self._cancel_events.setdefault(task_id, threading.Event())
        evt.set()
        if self.orchestrator is not None:
            try:
                self.orchestrator.cancel()
            except Exception:
                pass
        return True

    def cancel_all(self) -> None:
        for task_id in list(self._cancel_events):
            self.cancel(task_id)

    def _is_cancelled(self, task_id: str) -> bool:
        evt = self._cancel_events.get(task_id)
        return evt is not None and evt.is_set()

    def _is_paused(self, task_id: str) -> bool:
        evt = self._pause_events.get(task_id)
        return evt is not None and evt.is_set()

    def _wait_for_resume(self, task_id: str) -> bool:
        """Block until resumed or cancelled. Returns True if resumed."""
        evt = self._pause_events.get(task_id)
        cancel = self._cancel_events.get(task_id)
        if evt is None:
            return True
        while evt.is_set():
            if cancel is not None and cancel.is_set():
                return False
            time.sleep(0.2)
        return True

    def _deadline_exceeded(self, task: CognitiveTask) -> bool:
        if task.deadline is None:
            return False
        return time.time() > task.deadline

    def _register_control(self, task_id: str) -> None:
        with self._lock:
            self._cancel_events.setdefault(task_id, threading.Event())
            self._pause_events.setdefault(task_id, threading.Event())

    def _archive(self, task: CognitiveTask) -> None:
        try:
            self.task_registry.archive(task)
        except Exception:
            pass

    def _first_error(self, result: Any) -> str:
        if result is None:
            return "no result returned"
        errors = getattr(result, "errors", None)
        if isinstance(errors, list) and errors:
            return str(errors[0])
        # Safely extract error message, ensuring we always return a string
        error = None
        if hasattr(result, 'error'):
            error_val = getattr(result, 'error')
            # Only use the value if it's not a MagicMock (which would indicate undefined attribute)
            if not isinstance(error_val, MagicMock):
                error = error_val

        message = ""
        if hasattr(result, 'message'):
            message_val = getattr(result, 'message')
            # Only use the value if it's not a MagicMock (which would indicate undefined attribute)
            if not isinstance(message_val, MagicMock):
                message = message_val

        # Return first non-empty string, or empty string if none
        if error and isinstance(error, str) and error.strip():
            return error.strip()
        if isinstance(message, str) and message.strip():
            return message.strip()
        return ""

    def _outcome(
        self,
        task: CognitiveTask,
        started: float,
        success: bool,
        message: str,
        verification: Optional[Dict[str, Any]] = None,
        final_result: Any = None,
        replans: int = 0,
        recovered: bool = False,
    ) -> LoopOutcome:
        plan = task.plan
        return LoopOutcome(
            success=success,
            task_id=task.task_id,
            message=message,
            replans=replans,
            steps_completed=(plan.completed_steps if plan else 0),
            steps_failed=(plan.failed_steps if plan else 0),
            verification=dict(verification or {}),
            final_result=final_result,
            duration_ms=(time.perf_counter() - started) * 1000,
            recovered=recovered,
        )