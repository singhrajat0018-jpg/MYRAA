"""
MYRAA Super-Brain — Master Planner (B5), Capability Chaining (B8),
and Verification Strategy (B13).

Converts a Goal + AI Manager 4.1 TaskRoute into an ExecutionPlan made of
capability-stage steps with dependencies, parallelization where valid, and
explicit verification requirements.

REUSES the existing Planner/ActionBuilder/PlanOptimizer/ExecutionPlan/PlanStep.
It does NOT create a second plan type — it builds the SAME ExecutionPlan the
existing Orchestrator already executes. It adds:

  * goal-oriented, capability-chained step construction (B5/B8)
  * per-step verification strategy (what proves success?) (B13)
  * dependency edges from the AI Manager 4.1 decomposition (dependencies)
  * fallback strategy metadata (B12/B5)

Planning is pure — it never executes a step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from desktop_agent.brain.planner.planner import Planner
from desktop_agent.brain.planner.planning.action_builder import ActionBuilder
from desktop_agent.brain.planner.planning.plan_optimizer import PlanOptimizer
from desktop_agent.brain.planner.execution.execution_plan import ExecutionPlan
from desktop_agent.brain.planner.models.plan_step import PlanStep, StepStatus
from desktop_agent.brain.semantic.semantic_models import SemanticTask

from .goal import Goal

log = logging.getLogger(__name__)

# Capability-level "virtual" engines that own their tooling elsewhere (B19).
# The Master Planner treats these as stages whose execution is delegated to the
# Capability Orchestrator (mockable boundary until the engines are built).
_CAPABILITY_OWNED_STAGES = {
    "TRADING_ENGINE",
    "NX_ENGINEERING_ENGINE",
    "CREATION_ENGINE",
    "PRESENTATION_ENGINE",
    "SPREADSHEET_ENGINE",
    "RESEARCH_PIPELINE",
    "DOCUMENT_ENGINE",
    "GENERAL_INTELLIGENCE_ENGINE",
    "VOICE_ENGINE",
    "PHONE_ENGINE",
}


@dataclass
class PlanVerificationStrategy:
    """How a step's success will be proven (B13)."""

    step_id: int
    method: str = "unverified"  # deterministic | evidence | unverified
    expected: str = ""
    check_tool: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "method": self.method,
            "expected": self.expected,
            "check_tool": self.check_tool,
            "description": self.description,
        }


@dataclass
class MasterPlan:
    """A goal-oriented plan with verification strategy attached (B5/B13)."""

    plan: ExecutionPlan
    goal: Goal
    verification_strategies: List[PlanVerificationStrategy] = field(default_factory=list)
    fallback_strategy: str = ""
    capability_chain: List[str] = field(default_factory=list)
    dependencies: List[List[int]] = field(default_factory=list)
    parallelizable: List[List[int]] = field(default_factory=list)
    # Advisory learning signal (B20 closed loop): best historically-successful
    # tool sequence for this goal's capability, from ExperienceEngine. The
    # planner still builds steps deterministically; hints are observed context
    # for orchestrator/executor/telemetry, never an execution bypass.
    experience_hints: List[str] = field(default_factory=list)

    @property
    def steps(self) -> List[PlanStep]:
        return self.plan.steps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal.to_dict(),
            "capability_chain": list(self.capability_chain),
            "experience_hints": list(self.experience_hints),
            "dependencies": self.dependencies,
            "parallelizable": self.parallelizable,
            "fallback_strategy": self.fallback_strategy,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "action": getattr(s.action, "value", str(s.action)),
                    "depends_on": list(s.depends_on),
                    "requires_verification": s.requires_verification,
                    "expected_result": s.expected_result,
                    "status": s.status.value,
                    "parallel_group": s.parallel_group,
                }
                for s in self.plan.steps
            ],
            "verification_strategies": [
                v.to_dict() for v in self.verification_strategies
            ],
            "plan_status": self.plan.status.value,
        }


class MasterPlanner:
    """
    Goal-oriented planner on top of the existing Planner (B5).

    Uses the existing ActionBuilder to emit CUSTOM tool-call steps that the
    existing Orchestrator -> CommandDispatcher path already executes.
    """

    def __init__(
        self,
        planner: Optional[Planner] = None,
        action_builder: Optional[ActionBuilder] = None,
        optimizer: Optional[PlanOptimizer] = None,
    ) -> None:
        self.planner = planner if planner is not None else Planner()
        self.builder = action_builder if action_builder is not None else ActionBuilder()
        self.optimizer = optimizer if optimizer is not None else PlanOptimizer()

    # ================================================================
    # Public
    # ================================================================

    def create_goal_plan(
        self,
        goal: Goal,
        route: Optional[Any] = None,
        experience_hints: Optional[List[str]] = None,
    ) -> MasterPlan:
        """
        Build a capability-chained ExecutionPlan from a Goal (B5/B8/B13).

        When the AI Manager 4.1 route already decomposed the request into
        sub-tasks with dependencies (capability chain), that structure is
        reused. Otherwise a simple single-capability plan is built.

        experience_hints (B20 closed loop): advisory best-known tool sequence
        from ExperienceEngine. Recorded on the plan as observed context only;
        step construction below is unchanged.
        """
        semantic = SemanticTask()
        semantic.raw_text = goal.text
        semantic.normalized_text = goal.text.lower()
        semantic.intent = self._intent_for_goal(goal)
        semantic.confidence = goal.confidence or 0.5
        semantic.metadata["action"] = goal.action or ""

        plan = ExecutionPlan(task=semantic)
        plan.metadata["capability"] = goal.capability
        plan.metadata["capability_chain"] = list(goal.capability_chain)
        plan.metadata["goal"] = goal.text
        plan.metadata["experience_hints"] = list(experience_hints or [])

        verification_strategies: List[PlanVerificationStrategy] = []
        step_of_goal: List[Dict[str, Any]] = list(goal.sub_goals)

        # ------------------------------------------------------------
        # Multi-goal / capability chain path (B8) — reuse AI Manager 4.1
        # decomposition (sub_tasks + dependencies).
        # ------------------------------------------------------------
        if step_of_goal and goal.is_multi:
            index_of_step: Dict[int, int] = {}
            for i, sub in enumerate(step_of_goal):
                step = self.builder.tool_call(
                    tool_name=self._tool_for_capability(
                        sub.get("capability") or goal.capability
                    ),
                    parameters={
                        "goal": sub.get("goal", ""),
                        "intent": sub.get("intent", ""),
                        "capability": sub.get("capability", ""),
                        "output_type": sub.get("output_type", ""),
                    },
                )
                step.name = f"{sub.get('capability', 'step')}: {sub.get('goal', '')[:60]}"
                step.depends_on = list(goal.dependencies[i]) if i < len(goal.dependencies) else []
                plan.add_step(step)
                index_of_step[i] = step.id

                strategy = self._verification_strategy(
                    step.id,
                    goal,
                    sub.get("capability", ""),
                )
                verification_strategies.append(strategy)
                step.expected_result = strategy.expected

            # Remap dependencies (indices in goal.dependencies are goal-indexed).
            for i, step in enumerate(plan.steps):
                step.depends_on = [
                    index_of_step[dep] for dep in goal.dependencies[i]
                    if dep in index_of_step
                ]

            plan.estimated_steps = len(plan.steps)
            self._mark_parallelizable(plan)

        # ------------------------------------------------------------
        # Simple goal path: one capability stage (B5).
        # ------------------------------------------------------------
        else:
            # Communication goals (message/call/email) route through the
            # desktop surface (WhatsApp Desktop/Web, Gmail) as goal-based
            # computer-use steps with REAL registered tools. No phone_tool.
            computer_use_steps = self._computer_use_steps(goal)
            if computer_use_steps:
                for cu in computer_use_steps:
                    step = self.builder.tool_call(
                        tool_name=cu["tool"],
                        parameters=cu["parameters"],
                    )
                    step.name = f"{cu['name']}: {goal.text[:60]}"
                    step.description = cu.get("why", "")
                    step.expected_result = cu.get("expected", "")
                    plan.add_step(step)
                    strategy = self._verification_strategy(
                        step.id, goal, goal.capability)
                    if cu.get("verify"):
                        strategy = PlanVerificationStrategy(
                            step_id=step.id,
                            method="evidence",
                            expected=cu["verify"],
                            check_tool="readScreen",
                            description="desktop screen checked for outcome (B13)",
                        )
                    verification_strategies.append(strategy)
            else:
                tool = self._tool_for_capability(goal.capability)
                step = self.builder.tool_call(
                    tool_name=tool,
                    parameters={
                        "goal": goal.text,
                        "intent": goal.intent or "",
                        "capability": goal.capability or "",
                        "output_type": goal.output_type or "",
                        "recipient": goal.recipient,
                        "message": goal.message,
                        "expected_output": goal.expected_output,
                        "success_criteria": list(goal.success_criteria),
                    },
                )
                step.name = f"{goal.capability or 'CAPABILITY'}: {goal.text[:60]}"
                plan.add_step(step)

                strategy = self._verification_strategy(step.id, goal, goal.capability)
                verification_strategies.append(strategy)
                step.expected_result = strategy.expected

        # ------------------------------------------------------------
        # Finalize + fallback strategy (B5/B12)
        # ------------------------------------------------------------
        optimized = self.optimizer.optimize(plan)

        return MasterPlan(
            plan=optimized,
            goal=goal,
            verification_strategies=verification_strategies,
            fallback_strategy=self._fallback_for(goal.capability),
            capability_chain=list(goal.capability_chain),
            dependencies=[list(s.depends_on) for s in optimized.steps],
            parallelizable=self._compute_parallelizable(optimized),
            experience_hints=list(plan.metadata.get("experience_hints") or []),
        )

    # ================================================================
    # Verification strategy (B13)
    # ================================================================

    def _verification_strategy(
        self,
        step_id: int,
        goal: Goal,
        capability: str,
    ) -> PlanVerificationStrategy:
        """Decide how success will be proven for a step (B13)."""
        cap = capability or goal.capability or ""
        text = (goal.text or "").lower()

        if cap == "RESEARCH_PIPELINE":
            return PlanVerificationStrategy(
                step_id=step_id,
                method="evidence",
                expected=goal.expected_output or "synthesized, cited answer",
                check_tool="searchWeb",
                description="evidence retrieved + answer synthesized",
            )
        if cap == "GENERAL_INTELLIGENCE_ENGINE":
            # GENERAL_INTELLIGENCE_ENGINE must NOT use searchWeb.
            # A general request should be answered directly by the model.
            return PlanVerificationStrategy(
                step_id=step_id,
                method="unverified",
                expected=goal.expected_output or "direct model response",
                check_tool="",
                description="direct model response — no web search",
            )
        if cap in ("TRADING_ENGINE", "FINANCIAL_ENGINE"):
            return PlanVerificationStrategy(
                step_id=step_id,
                method="evidence",
                expected="analysis/report grounded in market data",
                check_tool="searchWeb",
                description="advisory analysis produced; no execution",
            )
        if cap in ("DOCUMENT_ENGINE", "CREATION_ENGINE", "PRESENTATION_ENGINE",
                   "SPREADSHEET_ENGINE", "CODING_ENGINE"):
            return PlanVerificationStrategy(
                step_id=step_id,
                method="deterministic",
                expected=goal.expected_output or "artifact exists with expected contents",
                check_tool="searchFiles",
                description="artifact existence/content verified (B13)",
            )
        if "send" in goal.action or "message" in text:
            return PlanVerificationStrategy(
                step_id=step_id,
                method="evidence",
                expected="message appears in target conversation as sent",
                check_tool="readScreen",
                description="target conversation checked for sent message (B13)",
            )
        if "open" in goal.action or "open" in text:
            return PlanVerificationStrategy(
                step_id=step_id,
                method="deterministic",
                expected="target application/window is open and visible",
                check_tool="systemInfo",
                description="process/window existence checked (B13)",
            )
        return PlanVerificationStrategy(
            step_id=step_id,
            method="unverified",
            expected="request completed",
            check_tool="",
            description="deterministic verification not available; outcome UNVERIFIED",
        )

    # ================================================================
    # Helpers
    # ================================================================

    # ================================================================
    # Computer-use flow (B18) — communication goals on the desktop
    # ================================================================

    def _computer_use_steps(self, goal: Goal) -> List[Dict[str, Any]]:
        """Build executable desktop steps for a communication goal.

        Message/call/email goals route to the Windows desktop surface
        (WhatsApp Desktop/Web, Gmail) using ONLY real registered tools:
        openApplication -> typeText -> pressKey -> readScreen.

        SAFETY: no phone_tool, no SMS/telephony APIs, no fake success. If the
        surface cannot be produced (no recipient, no message), no steps are
        returned and the goal falls through to the generic path.
        """
        action = (goal.action or "").lower()
        text = (goal.text or "").lower()
        if "send" not in action and "message" not in text and "call" not in text:
            return []
        if not goal.recipient:
            return []

        app = "whatsapp"
        if "gmail" in action or "email" in action or "gmail" in text:
            app = "gmail"
        elif "telegram" in action or "telegram" in text:
            app = "telegram"
        elif "slack" in action or "slack" in text:
            app = "slack"

        message = goal.message or text
        is_call = "call" in text or "phone" in text or "dial" in text
        steps = [
            {
                "tool": "openApplication",
                "name": "OPEN_DESKTOP_APP",
                "parameters": {"application": app, "goal": goal.text},
                "why": f"open/focus {app} on the Windows desktop",
                "expected": f"{app} application is open and focused",
            },
            {
                "tool": "typeText",
                "name": "SEARCH_RECIPIENT",
                "parameters": {"text": goal.recipient, "goal": goal.text},
                "why": "search for the target contact in the app",
                "expected": "contact search performed",
            },
            {
                "tool": "pressKey",
                "name": "SELECT_CONTACT",
                "parameters": {"key": "enter", "goal": goal.text},
                "why": "select the top search result to open the conversation",
                "expected": "conversation with target contact opened",
            },
        ]
        if not is_call:
            steps += [
                {
                    "tool": "typeText",
                    "name": "COMPOSE_MESSAGE",
                    "parameters": {"text": message, "goal": goal.text},
                    "why": "type the message body into the composer",
                    "expected": "message body typed",
                },
                {
                    "tool": "pressKey",
                    "name": "SEND_MESSAGE",
                    "parameters": {"key": "enter", "goal": goal.text},
                    "why": "send the composed message in the conversation",
                    "expected": "message sent to target conversation",
                    "verify": "message appears in target conversation as sent",
                },
            ]
        else:
            steps.append({
                "tool": "pressKey",
                "name": "START_CALL",
                "parameters": {"key": "enter", "goal": goal.text},
                "why": "start the call with the selected contact via the app UI",
                "expected": "call initiated with target contact",
                "verify": "call window/state visible for the target contact",
            })
        return steps

    def _fallback_for(self, capability: str) -> str:
        cap = capability or ""
        if cap in ("RESEARCH_PIPELINE",):
            return "fallback research provider -> general LLM reasoning"
        if cap in ("TRADING_ENGINE", "FINANCIAL_ENGINE"):
            return "advisory fallback: present known data with uncertainty, never trade"
        if cap in ("CODING_ENGINE", "DOCUMENT_ENGINE", "CREATION_ENGINE",
                   "PRESENTATION_ENGINE", "SPREADSHEET_ENGINE"):
            return "replan artifact construction with alternative tool"
        return "replan with simpler capability or clarify"

    def _tool_for_capability(self, capability: str) -> str:
        cap = capability or ""
        # GENERAL_INTELLIGENCE_ENGINE: must NOT produce a tool step.
        # A general request is answered directly by the model.
        if cap == "GENERAL_INTELLIGENCE_ENGINE":
            return "direct_response"
        # Capability-owned engines: use a canonical marker tool; the Capability
        # Orchestrator resolves these to real tools or the engine boundary.
        if cap in _CAPABILITY_OWNED_STAGES:
            return f"capability::{cap}"
        if cap in ("COMPUTER_USE_ENGINE", "DESKTOP_ENGINE"):
            return "desktopAutomation"
        if cap in ("FILES_ENGINE", "FILE_MANAGEMENT_ENGINE"):
            return "multiToolTask"
        return "multiToolTask"

    def _intent_for_goal(self, goal: Goal) -> Any:
        from desktop_agent.brain.semantic.semantic_models import Intent

        action = (goal.action or "").lower()
        if "send" in action:
            return Intent.SEND_MESSAGE
        if "create" in action or "bana" in (goal.text or "").lower():
            return Intent.CREATE_FILE
        if "open" in action:
            return Intent.OPEN_APPLICATION
        if goal.is_multi:
            return Intent.MULTI_STEP_TASK
        return Intent.QUESTION

    def _mark_parallelizable(self, plan: ExecutionPlan) -> None:
        """Group independent chain steps into parallel groups (B5/B6)."""
        groups: Dict[tuple, List[int]] = {}
        for step in plan.steps:
            if not step.depends_on:
                groups.setdefault((), []).append(step.id)
        if len(groups.get((), [])) > 1:
            group_id = 1
            for sid in groups[()]:
                for step in plan.steps:
                    if step.id == sid:
                        step.parallel_group = group_id
                        break
                group_id += 1

    def _compute_parallelizable(self, plan: ExecutionPlan) -> List[List[int]]:
        from collections import defaultdict

        groups: Dict[int, List[int]] = defaultdict(list)
        for step in plan.steps:
            if step.parallel_group is not None and not step.depends_on:
                groups[step.parallel_group].append(step.id)
        return [sorted(ids) for ids in groups.values() if len(ids) > 1]