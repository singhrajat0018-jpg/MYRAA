"""
MYRAA Super-Brain — Coordination Facade (B7/B14/B21/B24).

Top-level entry point that wires the whole Super-Brain pipeline together:

    user_request
        -> AI Manager 4.1 (ROUTING AUTHORITY, decides WHAT)
        -> Goal (build_goal)
        -> FusedContext (context gathering)
        -> MasterPlan (MasterPlanner)
        -> CapabilityOrchestrator (tool strategies)
        -> ClosedLoopExecutor (plan->execute->observe->verify->replan)
        -> MetaController (reflect + next action)
        -> ExperienceEngine (learn, offline-leaning)

REUSES existing components — it is a COORDINATION LAYER, not a second
implementation of Brain/Planner/Memory/WorldModel/Verification/Recovery.

SAFETY (B24): Super-Brain decides WHAT; PermissionManager/ValidationLayer/
confirmation flow decide WHETHER execution is authorized. Financial/system
boundaries are NEVER bypassed here.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from desktop_agent.brain.super_brain.goal import Goal, build_goal
from desktop_agent.brain.super_brain.cognitive_state import (
    CognitiveTask,
    CognitiveTaskRegistry,
)
from desktop_agent.brain.super_brain.context import ContextFusionEngine
from desktop_agent.brain.super_brain.planner import MasterPlanner
from desktop_agent.brain.super_brain.capability_orchestrator import (
    CapabilityOrchestrator,
    CapabilityEngineRegistry,
)
from desktop_agent.brain.super_brain.executor import ClosedLoopExecutor, LoopOutcome
from desktop_agent.brain.super_brain.meta_controller import MetaController
from desktop_agent.brain.super_brain.experience import Experience, ExperienceEngine
from desktop_agent.brain.super_brain.project_builder_engine import ProjectBuilderEngine


log = logging.getLogger(__name__)


@dataclass
class SuperBrainResult:
    """Final Super-Brain result for one request (B21)."""

    request_id: str
    goal_text: str
    success: bool = False
    message: str = ""
    decision: str = ""
    capability: str = ""
    execution: LoopOutcome = field(default_factory=LoopOutcome)
    context: Dict[str, Any] = field(default_factory=dict)
    tool_strategies: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    safety: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "goal_text": self.goal_text,
            "success": self.success,
            "message": self.message,
            "decision": self.decision,
            "capability": self.capability,
            "execution": self.execution.to_dict(),
            "context": self.context,
            "tool_strategies": self.tool_strategies,
            "meta": self.meta,
            "timeline": self.timeline,
            "safety": self.safety,
        }


class SuperBrain:
    """
    Coordination facade for the Super-Brain pipeline (B7).

    Parameters (all optional, all REUSED existing services):
      ai_manager        : AI Manager 4.1 (route authority)      [defaults to None]
      orchestrator      : existing Orchestrator                 [execution engine]
      verification      : existing VerificationManager          [goal verification]
      recovery          : existing RecoveryEngine               [retry/fallback]
      memory            : existing MemoryManager                [memory context]
      world_model       : existing WorldModel                   [world context]
      blackboard        : existing Blackboard                   [pub/sub]
      permission_manager: existing PermissionManager            [authorization]
      metacognition     : existing Metacognition                [reflection]
      telemetry         : existing TelemetryCollector           [observability]
    """

    def __init__(
        self,
        ai_manager: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        verification: Optional[Any] = None,
        recovery: Optional[Any] = None,
        memory: Optional[Any] = None,
        world_model: Optional[Any] = None,
        blackboard: Optional[Any] = None,
        permission_manager: Optional[Any] = None,
        metacognition: Optional[Any] = None,
        telemetry: Optional[Any] = None,
        memory_2_0: Optional[Any] = None,
    ) -> None:
        self.ai_manager = ai_manager
        self.permission_manager = permission_manager
        self.telemetry = telemetry
        self.memory_2_0 = memory_2_0

        # Sub-systems (REUSED where provided, else lightweight defaults).
        self.memory = memory
        self.world_model = world_model
        self.blackboard = blackboard

        self.goal_builder = build_goal
        self.planner = MasterPlanner()
        self.context_fusion = ContextFusionEngine(
            memory_manager=memory,
            world_model=world_model,
            memory_retrieval=getattr(memory, "retrieve", None) if memory else None,
        )
        self.engines = CapabilityEngineRegistry()
        # REGISTER PROJECT BUILDER ENGINE (Phase A)
        self.engines.register(ProjectBuilderEngine())
        self.orchestrator = CapabilityOrchestrator(
            engine_registry=self.engines,
            permission_manager=permission_manager,
        )
        self.executor = ClosedLoopExecutor(
            orchestrator=orchestrator,
            verification_manager=verification,
            recovery_engine=recovery,
            max_replans=2,
        )
        self.meta_controller = MetaController(
            metacognition=metacognition,
            telemetry=telemetry,
        )
        self.experience = ExperienceEngine(memory_2_0=memory_2_0)

        self.timeline: List[Dict[str, Any]] = []
        self.safety_log: List[Dict[str, Any]] = []

    # ================================================================
    # Main entry
    # ================================================================

    def process(
        self,
        user_request: str,
        request_id: Optional[str] = None,
        execution_depth: str = "standard",  # fast | standard | deep (B23)
        route: Optional[Any] = None,
    ) -> SuperBrainResult:
        """
        Run the full Super-Brain pipeline for one user request (B7).

        If a TaskRoute is not supplied and ai_manager is present, it is routed
        via AI Manager 4.1. If ai_manager is None (standalone/headless/test),
        the route is built as a minimal default.
        """
        rid = request_id or f"sb-{uuid.uuid4().hex[:12]}"
        timeline = [self._tl("start", user_request, request_id=rid)]

        # ------------------------------------------------------------
        # 1) ROUTE (AI Manager 4.1 is the routing authority)
        # ------------------------------------------------------------
        if route is None and self.ai_manager is not None:
            route = self._route(user_request)
            if route is None:
                route = self._default_route(user_request)
        decision = str(getattr(route, "decision", "BRAIN") or "BRAIN")
        capability = getattr(route, "capability", "") or ""

        timeline.append(self._tl("route", decision, capability=capability))

        # ------------------------------------------------------------
        # 2) GOAL (deterministic decomposition of route + request)
        # ------------------------------------------------------------
        goal = self.goal_builder(user_request, route=route)
        timeline.append(self._tl("goal", goal.action, recipient=goal.recipient))

        # ------------------------------------------------------------
        # 3) CONTEXT (world + memory, bounded)
        # ------------------------------------------------------------
        fused = self.context_fusion.fuse(goal=goal, route=route)
        context_summary = fused.to_dict()
        timeline.append(
            self._tl(
                "context",
                "fused",
                sources=1 + int(bool(fused.world_summary)) + int(bool(fused.memory)),
            )
        )

        # ------------------------------------------------------------
        # 4) CognitiveTask + MASTER PLAN
        # ------------------------------------------------------------
        task = CognitiveTask(
            task_id=goal.task_id or rid,
            request_id=rid,
            user_request=user_request,
            goal=goal.text,
            route=route,
            capability=capability,
            deadline=goal.deadline,
        )
        task.set_phase("PLANNING")
        # B20 closed loop: feed best-known verified tool sequence for this
        # capability into planning as advisory context (planner still builds
        # steps deterministically; hints never bypass execution authority).
        hints = self.experience.hint_for(capability) if capability else []
        master_plan = self.planner.create_goal_plan(goal, experience_hints=hints)
        task.plan = master_plan.plan
        task.sync_from_plan()
        timeline.append(
            self._tl("plan", "created", steps=len(master_plan.steps)),
        )

        # ------------------------------------------------------------
        # 5) TOOL STRATEGIES (capability orchestrator, B9/B18/B19)
        # ------------------------------------------------------------
        strategies = self.orchestrator.strategy_for_plan(master_plan, route)
        timeline.append(self._tl("strategy", "resolved", tools=len(strategies)))

        # ------------------------------------------------------------
        # 6) SAFETY HANDSHAKE (B24) — decide WHAT, never bypass authority
        # ------------------------------------------------------------
        safety = self._safety_handshake(task, strategies)
        if not safety["go"]:
            task.mark_failed(safety.get("reason", "not authorized"))
            task.verification_state = "BLOCKED"
            self._emit(timeline, "safety", "blocked", reason=safety.get("reason"))
            return self._result(
                rid=rid, goal=goal, success=False,
                message=safety.get("reason", "blocked"),
                decision=decision, capability=capability,
                context=context_summary,
                strategies=strategies, meta={}, timeline=timeline,
                safety=safety, task=task,
            )

        # ------------------------------------------------------------
        # 7) EXECUTE (closed loop) + 8) META + 9) EXPERIENCE
        # ------------------------------------------------------------
        execution_depth = self._resolve_depth(route, execution_depth)
        outcome = self.executor.execute(task, master_plan, execution_depth)
        timeline.append(
            self._tl("execute", "done", success=outcome.success, replans=outcome.replans),
        )

        # Meta-controller reflection (existing Metacognition).
        meta = self.meta_controller.decide(
            task,
            execution_success=outcome.success,
        )
        self.meta_controller.record_decision(meta)
        timeline.append(self._tl("meta", meta.action, reason=meta.reason))

        # Experience / learning (offline-leaning, B20).
        exp = Experience(
            request_id=rid,
            goal_text=goal.text,
            capability=capability,
            route_decision=decision,
            success=outcome.success,
            tool_sequence=[s.tool for s in strategies],
            outcome_message=outcome.message,
            verification_method=(
                list(outcome.verification.keys())[0] if outcome.verification else ""
            ),
            verified=bool(outcome.verification.get("verified")),
            recovery=str(task.recovery_state.value if task.recovery_state else ""),
            replan_count=outcome.replans,
            duration_ms=outcome.duration_ms,
            lesson=(meta.reflection or ("completed" if outcome.success else "failed")),
        )
        self.experience.record(exp)
        timeline.append(self._tl("experience", "recorded", success=outcome.success))

        # ------------------------------------------------------------
        # Return
        # ------------------------------------------------------------
        return self._result(
            rid=rid, goal=goal, success=outcome.success,
            message=outcome.message,
            decision=decision, capability=capability,
            context=context_summary, strategies=strategies,
            meta=meta.to_dict(), timeline=timeline, safety=safety,
            task=task, execution=outcome,
        )

    # ================================================================
    # Internals
    # ================================================================

    def _route(self, user_request: str) -> Optional[Any]:
        try:
            # TaskRouter pre-classification: enrich the route with
            # tool-necessity and freshness metadata.
            from desktop_agent.brain.router.task_router import TaskRouter
            _task_router = TaskRouter()
            _routing = _task_router.route(user_request)

            routed = self.ai_manager.route(user_request)
            route_obj = getattr(routed, "route", routed) or routed

            # Attach TaskRouter metadata to the route for downstream use
            if hasattr(route_obj, "metadata"):
                route_obj.metadata["task_type"] = _routing.task_type.name
                route_obj.metadata["tools_required"] = _routing.tools_required
                route_obj.metadata["freshness_required"] = _routing.freshness_required
            elif hasattr(route_obj, "__dict__"):
                if not hasattr(route_obj, "metadata"):
                    route_obj.metadata = {}
                route_obj.metadata["task_type"] = _routing.task_type.name
                route_obj.metadata["tools_required"] = _routing.tools_required
                route_obj.metadata["freshness_required"] = _routing.freshness_required

            # ── ROUTE OVERRIDE GUARD (no silent downstream override) ──
            # If TaskRouter determined tools_required=False, propagate this
            # to the route's top-level tools_required attribute so the
            # CapabilityOrchestrator pre-dispatch guard can enforce it.
            if not _routing.tools_required:
                if hasattr(route_obj, "tools_required"):
                    route_obj.tools_required = False

            # If AIManager's decision conflicts with TaskRouter (e.g. AIManager
            # wants to use a tool but TaskRouter says no tools needed), log it
            # and apply a ROUTE CHANGE with documented reason.
            ai_tools = list(getattr(route_obj, "tools_required", []) or [])
            if _routing.tools_required is False and ai_tools:
                log.info(
                    "ROUTE CHANGE: TaskRouter says tools_required=False but "
                    "AIManager suggests tools=%s. TaskRouter is authoritative. "
                    "request=%r",
                    ai_tools, user_request[:80],
                )
                if hasattr(route_obj, "tools_required"):
                    route_obj.tools_required = []

            return route_obj
        except Exception as exc:  # noqa: BLE001
            log.warning("AI Manager route failed, using default: %s", exc)
            return None

    def _default_route(self, user_request: str) -> Any:
        """Minimal default route when no AI Manager is available (tests/headless)."""
        from types import SimpleNamespace

        return SimpleNamespace(
            decision="BRAIN",
            intent="GENERAL_REQUEST",
            domain="GENERAL",
            capability="GENERAL",
            capability_chain=[],
            confidence=0.5,
            execution_mode="SIMPLE",
            risk_level="NONE",
            sub_tasks=[],
            dependencies=[],
            can_use_fast_path=True,
        )

    def _resolve_depth(self, route: Any, requested: str) -> str:
        mode = getattr(route, "execution_mode", "") or ""
        if requested != "standard":
            return requested
        if "COMPLEX" in str(mode) or "PLAN" in str(mode):
            return "deep"
        if "FAST" in str(mode) or "SIMPLE" in str(mode):
            return "fast"
        return "standard"

    def _safety_handshake(
        self,
        task: CognitiveTask,
        strategies: List[Any],
    ) -> Dict[str, Any]:
        """
        B24: Super-Brain decides WHAT; this never authorizes execution on its
        own. It flags whether any step requires the P0 confirmation flow.
        """
        requires_confirmation = any(
            getattr(s, "requires_confirmation", False) for s in strategies
        )
        if self.permission_manager is not None:
            # Delegate authorization check to the real permission system.
            try:
                authorized = self.permission_manager.check(task.capability)
                allowed = bool(authorized)
            except Exception as exc:  # noqa: BLE001
                allowed = False
        else:
            # No permission manager attached — allow for standalone/test mode.
            # The ACTUAL authorization happens at the dispatcher layer
            # (PermissionManager.check in main.py / registry.py), which is the
            # single enforcement point. This handshake is a planning-level gate.
            allowed = True
        blocked = (not allowed) or (
            requires_confirmation and self.permission_manager is None
        )
        return {
            "go": not blocked,
            "requires_confirmation": requires_confirmation,
            "permission_manager_attached": self.permission_manager is not None,
            "reason": (
                "requires confirmation but no permission manager attached"
                if blocked and requires_confirmation and self.permission_manager is None
                else "denied by permission manager" if blocked else ""
            ),
        }

    def _result(
        self,
        rid: str,
        goal: Goal,
        success: bool,
        message: str,
        decision: str,
        capability: str,
        context: Dict[str, Any],
        strategies: List[Any],
        meta: Dict[str, Any],
        timeline: List[Dict[str, Any]],
        safety: Dict[str, Any],
        task: CognitiveTask,
        execution: Optional[LoopOutcome] = None,
    ) -> SuperBrainResult:
        return SuperBrainResult(
            request_id=rid,
            goal_text=goal.text,
            success=success,
            message=message,
            decision=decision,
            capability=capability,
            execution=execution or LoopOutcome(task_id=task.task_id),
            context=context,
            tool_strategies=[s.to_dict() for s in strategies],
            meta=meta,
            timeline=timeline,
            safety=safety,
        )

    def _tl(self, stage: str, note: str, **extra: Any) -> Dict[str, Any]:
        entry = {"stage": stage, "note": note, "ts": time.time()}
        entry.update({k: v for k, v in extra.items() if v is not None})
        return entry

    def _emit(
        self,
        timeline: List[Dict[str, Any]],
        stage: str,
        note: str,
        **extra: Any,
    ) -> None:
        timeline.append(self._tl(stage, note, **extra))

    # ================================================================
    # Public API / introspection (B21 observability)
    # ================================================================

    def register_engine(self, engine: Any) -> None:
        """Register a specialized capability engine (B19 seam)."""
        self.engines.register(engine)

    def pending_goals(self) -> List[Dict[str, Any]]:
        return self.meta_controller.pending_goals()

    def schedule_goal(self, task_id: str, priority: int = 5) -> None:
        self.meta_controller.schedule(task_id, priority)

    def pause(self, task_id: str) -> bool:
        return self.executor.pause(task_id)

    def resume(self, task_id: str) -> bool:
        return self.executor.resume(task_id)

    def cancel(self, task_id: str) -> bool:
        return self.executor.cancel(task_id)

    def experience_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.experience.history(limit)

    def hints(self, capability: str) -> List[str]:
        return self.experience.hint_for(capability)

    def status(self) -> Dict[str, Any]:
        return {
            "ai_manager_attached": self.ai_manager is not None,
            "orchestrator_attached": self.executor.orchestrator is not None,
            "engines": self.engines.ids(),
            "experiences": self.experience.count(),
            "meta_decisions": len(self.meta_controller.history()),
        }