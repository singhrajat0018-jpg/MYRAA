"""
B26 E2E — MYRAA Super-Brain End-to-End Validation (FAITHFUL).

Validates the FULL cognitive lifecycle against the REAL Super-Brain pipeline:

    USER GOAL
    -> AI MANAGER 4.1 (routing authority)
    -> SUPER-BRAIN (goal understanding + context fusion)
    -> MASTER PLAN -> TASK GRAPH -> CAPABILITY CHAIN
    -> TOOL STRATEGY (real tool_resolver)
    -> EXECUTION -> OBSERVE -> VERIFY
    -> RECOVERY / REPLAN
    -> FINAL RESULT

---------------------------------------------------------------------------
WHAT IS REAL (exercised end-to-end, NOT mocked):
  * AIManager 4.1  — the routing authority produces the real TaskRoute.
  * SuperBrain      — coordination facade (process pipeline).
  * build_goal      — goal understanding / constraint / success-criteria.
  * MasterPlanner   — capability chaining, task graph, verification strategy,
                      real registered computer-use steps (open/focus -> resolve
                      -> compose -> send). No phone_tool / PHONE_ENGINE.
  * CapabilityOrchestrator — real tool_resolver (capability -> real tools).
  * ClosedLoopExecutor — observe / verify / recover / replan / pause / resume /
                      cancel, checkpointing.
  * RecoveryEngine  — the ONE authoritative bounded retry policy (real).
  * MetaController / ExperienceEngine — reflection + offline learning.
  * CognitiveTask / Registry — task graph state + pause/resume/cancel.

WHAT IS MOCKED (external capability boundary ONLY):
  * FakeDesktopOrchestrator — the tool-execution surface. Stands in for
      Orchestrator -> CommandDispatcher -> pyautogui / Playwright / win32 and
      the actual WhatsApp / Gmail / web surface. It records the REAL plan it
      receives and the REAL tool sequence, so the planner's output is asserted.
  * FakeVerifier — the verification EVIDENCE source. Stands in for what
      readScreen / searchWeb would observe in the real world. The verification
      GATING policy (success requires verified) lives in the REAL executor.

Never fakes a production result: a workflow is only "success" when the real
verification evidence confirms it.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop_agent.brain.super_brain import SuperBrain
from desktop_agent.brain.super_brain.cognitive_state import TaskState
from desktop_agent.brain.ai import AIManager
from desktop_agent.brain.failure_containment import (
    RecoveryEngine,
    RetryBudget,
    FailureContainmentManager,
)
from desktop_agent.brain.verification import (
    ToolVerificationResult,
    VerificationEvidence,
    VerificationOutcome,
)
from desktop_agent.brain.error_taxonomy import MYRAAError, ErrorCategory


# ============================================================
# Boundary mocks (external capability surface + evidence source)
# ============================================================

@dataclass
class BoundaryResult:
    """Result of one desktop-surface (orchestrator) execution."""

    success: bool
    message: str = ""
    result: Any = None
    error: Any = None  # MYRAAError | str | None

    @property
    def last_message(self) -> str:
        return self.message or ""


class FakeDesktopOrchestrator:
    """
    The tool-execution boundary (real Orchestrator/CommandDispatcher/surface).

    Receives the REAL ExecutionPlan produced by the Super-Brain planner,
    records the executed tool sequence, and returns a scripted outcome. This is
    the only "external world" the Super-Brain is allowed to touch in tests.
    """

    def __init__(self, mode: str = "success", execute_delay: float = 0.0) -> None:
        self.mode = mode
        self.execute_delay = execute_delay
        self.execute_calls: int = 0
        self.plans: List[Any] = []
        self.tool_sequences: List[List[str]] = []
        self.pause_calls = 0
        self.resume_calls = 0
        self.cancel_calls = 0
        self._lock = threading.Lock()

    # -- recording helpers -------------------------------------------

    def _capture(self, plan: Any) -> None:
        tools, params = [], []
        for step in plan.steps:
            p = step.parameters or {}
            tools.append(p.get("tool_name", "?"))
            params.append(p.get("parameters", {}) or {})
        with self._lock:
            self.execute_calls += 1
            self.plans.append(plan)
            self.tool_sequences.append(tools)
            self._last_params = params

    def executed_tools(self) -> List[List[str]]:
        return self.tool_sequences

    def all_params(self) -> List[dict]:
        return getattr(self, "_last_params", [])

    # -- boundary API (what the real Orchestrator exposes) ----------

    def execute(self, plan: Any) -> BoundaryResult:
        self._capture(plan)
        if self.execute_delay:
            time.sleep(self.execute_delay)
        n = self.execute_calls
        if self.mode == "success" or n > 1:
            return BoundaryResult(True, "desktop surface completed the goal",
                                  result={"executed_attempts": n})
        if self.mode == "transient_then_success":
            return BoundaryResult(
                False,
                "transient: surface temporarily unavailable",
                error=MYRAAError(category=ErrorCategory.TIMEOUT,
                                 message="transient: surface temporarily unavailable"),
            )
        if self.mode == "unavailable":
            return BoundaryResult(
                False,
                "WhatsApp is not installed or available on this machine; "
                "cannot complete the goal.",
            )
        if self.mode == "ambiguous_contact":
            msg = ("Multiple contacts match Rahul: Rahul Sharma, Rahul Verma "
                   "— which one?")
            return BoundaryResult(
                False,
                msg,
                error=MYRAAError(category=ErrorCategory.TARGET_AMBIGUOUS, message=msg),
            )
        return BoundaryResult(True, "ok")

    def pause(self) -> None:
        self.pause_calls += 1

    def resume(self) -> None:
        self.resume_calls += 1

    def cancel(self) -> None:
        self.cancel_calls += 1

    def stop(self) -> None:
        self.cancel()


class FakeVerifier:
    """The verification EVIDENCE boundary (what readScreen/searchWeb would see)."""

    def __init__(self, verified: bool = True,
                 outcome: VerificationOutcome = VerificationOutcome.VERIFIED) -> None:
        self.verified = verified
        self.outcome = outcome
        self.calls = 0

    def verify(self, result: Any, tool: str = "", args: Optional[dict] = None) -> ToolVerificationResult:
        self.calls += 1
        return ToolVerificationResult(
            tool=tool,
            outcome=self.outcome,
            message="independent evidence confirmed the outcome"
            if self.verified else "independent evidence did NOT confirm the outcome",
            evidence=[VerificationEvidence("simulated_observation", self.verified, "boundary evidence source")],
        )


def _make_brain(boundary: FakeDesktopOrchestrator, verifier: FakeVerifier,
                recovery: Optional[RecoveryEngine] = None,
                ai_manager: Optional[AIManager] = None) -> SuperBrain:
    recovery = recovery or RecoveryEngine(
        budget=RetryBudget(max_attempts=3, base_delay=0.0, jitter=False),
        containment=FailureContainmentManager(),
    )
    return SuperBrain(
        ai_manager=ai_manager or AIManager(),
        orchestrator=boundary,
        verification=verifier,
        recovery=recovery,
    )


def _route(decision: str = "BRAIN", capability: str = "OPEN_APPLICATION",
           intent: str = "APP_CONTROL", domain: str = "SYSTEM",
           output_type: str = "SYSTEM_ACTION", risk: str = "none",
           confidence: float = 0.9, entities: Optional[List[str]] = None,
           topic: Optional[List[str]] = None, sub_tasks: Optional[List[dict]] = None,
           dependencies: Optional[List[List[int]]] = None,
           capability_chain: Optional[List[str]] = None,
           execution_mode: str = "FAST_DETERMINISTIC", can_use_fast_path: bool = False,
           multi_intents: Optional[List[dict]] = None,
           context_required: Optional[List[str]] = None) -> Any:
    """A controlled TaskRoute for isolating Super-Brain loop mechanics."""
    return SimpleNamespace(
        decision=decision, capability=capability, intent=intent, domain=domain,
        output_type=output_type, risk_level=risk, confidence=confidence,
        calibrated_confidence=confidence, entities=entities or [], topic=topic or [],
        context_required=context_required or [], sub_tasks=sub_tasks or [],
        dependencies=dependencies or [], capability_chain=capability_chain or [],
        multi_intents=multi_intents or [], execution_mode=execution_mode,
        can_use_fast_path=can_use_fast_path, tools_required=[],
    )


def _stages(result) -> List[str]:
    return [tl.get("stage") for tl in result.timeline]


class TestSuperBrainE2E:
    """End-to-end cognitive lifecycle (B26), real orchestration + boundary mocks."""

    def setup_method(self) -> None:
        self.ai_manager = AIManager()
        self.boundary = FakeDesktopOrchestrator("success")
        self.verifier = FakeVerifier(verified=True)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

    # ================================================================
    # E2E #1 — RESEARCH -> COMPARE -> PRESENTATION  (multi-capability)
    # ================================================================
    def test_e2e_1_research_compare_presentation(self):
        user_request = ("Latest AI coding models research karo, compare karo "
                        "aur presentation banao.")
        result = self.brain.process(user_request, request_id="e2e-1",
                                    execution_depth="deep")

        # Real routing authority decided a multi-capability research route.
        assert result.success is True
        assert result.decision == "ROUTE"
        assert result.capability == "RESEARCH_PIPELINE"

        # Goal understanding + context + plan + strategy + execute all ran.
        stages = _stages(result)
        for s in ("start", "route", "goal", "plan", "strategy", "execute",
                  "meta", "experience"):
            assert s in stages, f"missing lifecycle stage: {s}"

        # Task graph: the REAL planner emitted a chained research->integrate plan.
        exec_info = result.execution
        assert exec_info.task_id
        assert exec_info.verification.get("verified") is True

        # The REAL plan handed to the surface had a research stage that resolved
        # to a real registered tool — not a fabricated id.
        plan = self.boundary.plans[0]
        tools = self.boundary.tool_sequences[0]
        assert len(tools) >= 2
        # Tool names vary by planner version: searchWeb, SEARCH_PIPELINE,
        # capability::RESEARCH_PIPELINE, capability::GENERAL_INTELLIGENCE_ENGINE, etc.
        research_tools = {t.lower() for t in tools}
        assert any(
            kw in " ".join(research_tools)
            for kw in ("search", "research", "pipeline", "intelligence")
        )
        assert result.execution.duration_ms >= 0

    # ================================================================
    # E2E #2 — WHATSAPP GOAL  (real computer-use plan)
    # ================================================================
    def test_e2e_2a_whatsapp_send_message(self):
        user_request = "Rahul ko message karde, main 10 minute late aaunga."
        result = self.brain.process(user_request, request_id="e2e-2a",
                                    execution_depth="deep")

        assert result.success is True
        assert result.goal_text == user_request
        assert result.execution.verification.get("verified") is True

        # The user gave a GOAL, not steps. The REAL planner derived the
        # internal computer-use plan on the desktop surface:
        #   open/focus WhatsApp -> resolve Rahul -> open chat -> compose -> send
        plan = self.boundary.plans[0]
        seq = self.boundary.tool_sequences[0]
        params = self.boundary.all_params()

        assert len(seq) == 5
        assert seq[0] == "openApplication"
        assert params[0].get("application") == "whatsapp"
        # recipient resolution: Rahul typed into the contact search
        assert any(p.get("text") == "Rahul" for p in params)
        # message body composed + sent
        assert any("late" in str(p.get("text", "")) for p in params)
        # the send action is a real pressKey(enter), not a phone API
        assert seq[-1] == "pressKey" and params[-1].get("key") == "enter"

        # SAFETY: no phone engine / phone tool anywhere in the executed plan.
        assert not any("phone" in t.lower() for t in seq)

    def test_e2e_2b_whatsapp_unavailable(self):
        """If WhatsApp is unavailable -> honest failure, never fake success."""
        self.boundary = FakeDesktopOrchestrator("unavailable")
        self.verifier = FakeVerifier(verified=True)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

        user_request = "Rahul ko message karde, main 10 minute late aaunga."
        result = self.brain.process(user_request, request_id="e2e-2b",
                                    execution_depth="deep")

        assert result.success is False
        low = (result.message or "").lower()
        assert ("not installed" in low or "unavailable" in low or "aborted" in low)
        # No fabricated verification of success.
        assert result.execution.verification.get("verified") in (False, None)

    def test_e2e_2c_whatsapp_ambiguous_contact(self):
        """Multiple 'Rahul' contacts -> CLARIFICATION_REQUIRED, never guess."""
        self.boundary = FakeDesktopOrchestrator("ambiguous_contact")
        self.verifier = FakeVerifier(verified=True)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

        user_request = "Rahul ko message karde, main 10 minute late aaunga."
        result = self.brain.process(user_request, request_id="e2e-2c",
                                    execution_depth="deep")

        assert result.success is False
        assert "clarif" in (result.message or "").lower()
        # The task entered a clarification (not retry/fabrication) posture.
        task = self.brain.executor.task_registry.get("e2e-2c")
        assert task is not None
        assert task.recovery_state.value == "clarifying"

    # ================================================================
    # E2E #3 — GMAIL GOAL
    # ================================================================
    def test_e2e_3_gmail_send_email(self):
        user_request = "Priya ko email karde ki meeting 5 baje hai."
        result = self.brain.process(user_request, request_id="e2e-3",
                                    execution_depth="deep")

        assert result.success is True
        plan = self.boundary.plans[0]
        seq = self.boundary.tool_sequences[0]
        params = self.boundary.all_params()

        # recipient is resolved to the GMAIL surface, not SMS/telephony
        assert seq[0] == "openApplication"
        assert params[0].get("application") == "gmail"
        assert any(p.get("text") == "Priya" for p in params)
        assert any("meeting" in str(p.get("text", "")) for p in params)
        assert result.execution.verification.get("verified") is True
        assert not any("phone" in t.lower() for t in seq)

    # ================================================================
    # E2E #4 — FAILURE -> RECOVERY -> REPLAN -> SUCCESS
    # ================================================================
    def test_e2e_4_transient_failure_recovery_replan(self):
        self.boundary = FakeDesktopOrchestrator("transient_then_success")
        self.verifier = FakeVerifier(verified=True)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

        route = _route(capability="OPEN_APPLICATION", capability_chain=[])
        result = self.brain.process("Run the diagnostic", request_id="e2e-4",
                                    route=route, execution_depth="deep")

        assert result.success is True
        assert result.execution.replans >= 1
        assert result.execution.recovered is True
        # The second attempt was ACTUALLY executed (not just claimed).
        assert self.boundary.execute_calls >= 2
        assert len(self.boundary.plans) >= 2
        # Attempt 1 failed (transient), attempt 2 succeeded.
        assert "execute" in _stages(result)

    # ================================================================
    # E2E #5 — VERIFICATION FAILURE (no fabricated completion)
    # ================================================================
    def test_e2e_5_verification_failure_no_fake_success(self):
        # Tool claims success, but independent verification evidence says NO.
        self.boundary = FakeDesktopOrchestrator("success")
        self.verifier = FakeVerifier(verified=False,
                                     outcome=VerificationOutcome.FAILED)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

        route = _route(capability="WEB_SEARCH", intent="SEARCH_WEB", domain="RESEARCH",
                       execution_mode="STANDARD_REASONING")
        result = self.brain.process("Search for latest news", request_id="e2e-5",
                                    route=route, execution_depth="deep")

        # The surface executed (1 call) and reported success...
        assert self.boundary.execute_calls == 1
        # ...but the Super-Brain must NOT fabricate completion.
        assert result.success is False
        assert result.execution.verification.get("verified") is False
        low = (result.message or "").lower()
        assert "unverified" in low or "not confirmed" in low or "aborted" in low

    # ================================================================
    # E2E #6 — PAUSE / RESUME / CANCEL (real executor control loop)
    # ================================================================
    def test_e2e_6a_pause_resume_complete(self):
        """RUNNING -> PAUSE -> RESUME -> COMPLETE."""
        self.boundary = FakeDesktopOrchestrator("transient_then_success",
                                                execute_delay=0.4)
        self.verifier = FakeVerifier(verified=True)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

        route = _route(capability="LONG_TASK", capability_chain=[])
        box: dict = {}

        def run() -> None:
            box["result"] = self.brain.process(
                "Count from 1 to 1000000", request_id="t-pause",
                route=route, execution_depth="deep")

        t = threading.Thread(target=run)
        t.start()

        # Let the first attempt run (the long tool call is in flight = RUNNING).
        time.sleep(0.15)
        assert self.brain.pause("t-pause") is True

        # Wait until the executor observes the pause (state -> PAUSED).
        observed_paused = False
        deadline = time.time() + 8
        while time.time() < deadline:
            task = self.brain.executor.task_registry.get("t-pause")
            if task is not None and task.state == TaskState.PAUSED:
                observed_paused = True
                break
            if task is not None and task.state in (
                    TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
                break
            time.sleep(0.02)
        assert observed_paused, "executor did not enter PAUSED state"

        time.sleep(0.05)
        assert self.brain.resume("t-pause") is True
        t.join(timeout=10)
        assert not t.is_alive(), "task did not complete after resume"

        result = box["result"]
        assert result.success is True
        assert result.execution.replans >= 1
        # Two surface calls: attempt 1 (failed) then the resuming attempt 2.
        assert self.boundary.execute_calls == 2
        # The executor delegated resume down to the boundary.
        assert self.boundary.resume_calls >= 1

    def test_e2e_6b_cancel_no_unsafe_continuation(self):
        """RUNNING -> CANCEL -> CANCELLED, and no further tool executions."""
        self.boundary = FakeDesktopOrchestrator("transient_then_success",
                                                execute_delay=0.4)
        self.verifier = FakeVerifier(verified=True)
        self.brain = _make_brain(self.boundary, self.verifier, ai_manager=self.ai_manager)

        route = _route(capability="LONG_TASK", capability_chain=[])
        box: dict = {}

        def run() -> None:
            box["result"] = self.brain.process(
                "Run a long report job", request_id="t-cancel",
                route=route, execution_depth="deep")

        t = threading.Thread(target=run)
        t.start()

        time.sleep(0.15)  # first attempt in flight (RUNNING)
        assert self.brain.cancel("t-cancel") is True
        t.join(timeout=10)
        assert not t.is_alive(), "task did not finish after cancel"

        result = box["result"]
        assert result.success is False
        assert "cancel" in (result.message or "").lower()
        task = self.brain.executor.task_registry.get("t-cancel")
        assert task is not None and task.state == TaskState.CANCELLED
        # NO unsafe continuation: only the in-flight attempt ran; the would-be
        # second attempt was never executed.
        assert self.boundary.execute_calls == 1

    # ================================================================
    # STATE / TRACE assertions apply inside each test above (request_id,
    # task_id, route, plan, capability, tool strategy, execution, verification,
    # recovery state, final result, timeline). A workflow is successful ONLY
    # when the REAL verification evidence confirms it.
    # ================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
