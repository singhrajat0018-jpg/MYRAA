"""SkillOrchestrator — main execution engine for MYRAA multi-agent system.

Phase I.1: Real tool execution + World Model updates + persistent metrics + Neural routing.

Integrates: SkillRegistry, AgentPlanner, AgentSupervisor, HandoffSystem,
ConflictResolver, LoopGuard, AgentTelemetry, ToolBridge, WorldModelBridge,
MetricStore, NeuralRouter, TaskRouter.

Entry point: execute(goal, context) -> result.
"""

from __future__ import annotations

import time
import logging
import threading
from typing import Any, Dict, List, Optional

from .skill import Skill, SkillDomain, SkillState
from .worker import Worker, WorkerContract, WorkerResult, WorkerStatus
from .registry import SkillRegistry
from .planner import AgentPlanner, ExecutionPlan, PlanStep, PlanStepStatus, PlanMode
from .supervisor import AgentSupervisor, SupervisorDecision, SupervisionEvent
from .handoff import HandoffSystem, Handoff
from .conflict import ConflictResolver, Conflict, ConflictType
from .loop_protection import LoopGuard, LoopLimits
from .observability import AgentEvent, AgentTelemetry
from .tool_bridge import get_tool_bridge
from .world_model_bridge import get_world_model_bridge
from .metric_store import get_metric_store
from .neural_router import get_neural_router
from .agents import (
    CodingWorker, ResearchWorker, TradingWorker, VisionWorker,
    DesktopWorker, VerificationWorker, MemoryWorker,
    ProjectWorker, DocumentsWorker, AutomationWorker, DiagnosticsWorker,
)

logger = logging.getLogger(__name__)

# Worker class registry
_WORKER_CLASSES: Dict[str, type] = {
    "CodingWorker": CodingWorker,
    "ResearchWorker": ResearchWorker,
    "TradingWorker": TradingWorker,
    "VisionWorker": VisionWorker,
    "DesktopWorker": DesktopWorker,
    "VerificationWorker": VerificationWorker,
    "MemoryWorker": MemoryWorker,
    "ProjectWorker": ProjectWorker,
    "DocumentsWorker": DocumentsWorker,
    "AutomationWorker": AutomationWorker,
    "DiagnosticsWorker": DiagnosticsWorker,
}


class SkillOrchestrator:
    """Main execution engine for MYRAA multi-agent system.

    Phase I.1: Real tool execution + World Model updates + persistent metrics + Neural routing.
    """

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        planner: Optional[AgentPlanner] = None,
        supervisor: Optional[AgentSupervisor] = None,
        handoff_system: Optional[HandoffSystem] = None,
        conflict_resolver: Optional[ConflictResolver] = None,
        loop_guard: Optional[LoopGuard] = None,
        telemetry: Optional[AgentTelemetry] = None,
    ) -> None:
        self._registry = registry or SkillRegistry()
        self._planner = planner or AgentPlanner(self._registry)
        self._supervisor = supervisor or AgentSupervisor()
        self._handoffs = handoff_system or HandoffSystem()
        self._conflicts = conflict_resolver or ConflictResolver()
        self._loop_guard = loop_guard or LoopGuard()
        self._telemetry = telemetry or AgentTelemetry()
        self._tool_bridge = get_tool_bridge()
        self._world_model_bridge = get_world_model_bridge()
        self._metric_store = get_metric_store()
        self._neural_router = get_neural_router()
        self._lock = threading.Lock()
        self._active_plans: Dict[str, ExecutionPlan] = {}
        self._active_workers: Dict[str, Worker] = {}

        # Wire supervisor events to telemetry
        self._supervisor.on_event(self._on_supervision_event)

        logger.info("SkillOrchestrator initialised (Phase I.1)")

    def execute(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a goal through the skill system.

        Flow:
        1. TaskRouter determines if multi-agent is needed
        2. AgentPlanner creates execution plan
        3. Workers execute plan steps
        4. Supervisor manages execution
        5. Handoffs coordinate workers
        6. Conflicts are resolved
        7. Results are verified
        8. World Model is updated
        """
        ctx = context or {}
        task_type = ctx.get("task_type", "general")
        start = time.perf_counter()

        # Fast path: simple tasks avoid multi-agent overhead
        if task_type in ("conversation", "direct_knowledge", "fast_answer"):
            return self._fast_path(goal, ctx)

        # Multi-agent path
        self._loop_guard.start()

        # Create execution plan
        plan = self._planner.plan(goal, ctx)

        with self._lock:
            self._active_plans[plan.plan_id] = plan

        self._telemetry.record_started(
            agent_id=plan.plan_id,
            task_id=plan.plan_id,
            skill_id=task_type,
        )

        try:
            # Execute plan
            if plan.mode == PlanMode.SINGLE:
                result = self._execute_single(plan)
            elif plan.mode == PlanMode.PARALLEL:
                result = self._execute_parallel(plan)
            else:
                result = self._execute_sequential(plan)

            latency_ms = (time.perf_counter() - start) * 1000

            self._telemetry.record_completed(
                agent_id=plan.plan_id,
                task_id=plan.plan_id,
                skill_id=task_type,
                latency_ms=latency_ms,
                result_summary=str(result.get("status", "")),
            )

            return result

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._telemetry.record_failed(
                agent_id=plan.plan_id,
                task_id=plan.plan_id,
                skill_id=task_type,
                errors=[str(exc)],
            )
            return {
                "status": "error",
                "error": str(exc),
                "plan_id": plan.plan_id,
                "latency_ms": latency_ms,
            }
        finally:
            with self._lock:
                self._active_plans.pop(plan.plan_id, None)

    def _fast_path(self, goal: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fast path for simple tasks — no multi-agent overhead."""
        return {
            "status": "completed",
            "mode": "fast",
            "result": {"answer": goal},
            "evidence": ["Fast path: no agents needed"],
            "latency_ms": 0.0,
        }

    def _execute_single(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute a single-agent plan."""
        step = plan.next_step()
        if step is None:
            return {"status": "completed", "plan_id": plan.plan_id}

        worker = self._create_worker(step.worker_class)
        if worker is None:
            return {"status": "error", "error": f"Unknown worker: {step.worker_class}"}

        contract = WorkerContract(
            task_id=step.task_id,
            task_description=step.description,
            skill_id=step.skill_id,
            input_data=step.input_data,
            timeout_seconds=step.timeout_seconds,
            retry_budget=step.retry_budget,
            priority=step.priority,
            depends_on=step.depends_on,
        )

        result = self._execute_worker(worker, contract, plan, step)
        return {
            "status": "completed" if result.is_success else "failed",
            "plan_id": plan.plan_id,
            "result": result.to_dict(),
        }

    def _execute_sequential(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute plan steps sequentially, respecting dependencies."""
        results: List[Dict[str, Any]] = []
        max_iterations = len(plan.steps) * 5  # safety bound
        iteration = 0

        while not plan.is_complete() and not plan.has_failures():
            iteration += 1
            if iteration > max_iterations:
                logger.warning("Sequential execution exceeded max iterations")
                break

            step = plan.next_step()
            if step is None:
                break

            if not self._loop_guard.check_all():
                return {
                    "status": "failed",
                    "error": "Loop protection triggered",
                    "violations": self._loop_guard.get_violations(),
                    "plan_id": plan.plan_id,
                }

            # Skip steps that exhausted retry budget
            if step.retries_used >= step.retry_budget and step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.FAILED
                continue

            worker = self._create_worker(step.worker_class)
            if worker is None:
                step.status = PlanStepStatus.FAILED
                continue

            contract = WorkerContract(
                task_id=step.task_id,
                task_description=step.description,
                skill_id=step.skill_id,
                input_data=step.input_data,
                timeout_seconds=step.timeout_seconds,
                retry_budget=step.retry_budget,
                priority=step.priority,
                depends_on=step.depends_on,
            )

            result = self._execute_worker(worker, contract, plan, step)
            results.append(result.to_dict())

        return {
            "status": "completed" if plan.is_complete() else "failed",
            "plan_id": plan.plan_id,
            "results": results,
        }

    def _execute_parallel(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Execute independent plan steps in parallel."""
        import concurrent.futures

        results: List[Dict[str, Any]] = []
        max_workers = 4
        max_iterations = len(plan.steps) * 5  # safety bound
        iteration = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: Dict[concurrent.futures.Future, PlanStep] = {}

            while not plan.is_complete():
                iteration += 1
                if iteration > max_iterations:
                    logger.warning("Parallel execution exceeded max iterations")
                    break

                ready = plan.ready_steps()
                if not ready:
                    break

                for step in ready:
                    if not self._loop_guard.check_all():
                        break

                    # Skip steps that exhausted retry budget
                    if step.retries_used >= step.retry_budget and step.status == PlanStepStatus.PENDING:
                        step.status = PlanStepStatus.FAILED
                        continue

                    # Skip already running steps
                    if step.status == PlanStepStatus.RUNNING:
                        continue

                    worker = self._create_worker(step.worker_class)
                    if worker is None:
                        step.status = PlanStepStatus.FAILED
                        continue

                    contract = WorkerContract(
                        task_id=step.task_id,
                        task_description=step.description,
                        skill_id=step.skill_id,
                        input_data=step.input_data,
                        timeout_seconds=step.timeout_seconds,
                        retry_budget=step.retry_budget,
                        priority=step.priority,
                        depends_on=step.depends_on,
                    )

                    step.status = PlanStepStatus.RUNNING
                    future = executor.submit(self._execute_worker, worker, contract, plan, step)
                    futures[future] = step

                # Wait for at least one to complete
                done, _ = concurrent.futures.wait(
                    futures.keys(),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )

                for future in done:
                    step = futures.pop(future)
                    try:
                        result = future.result()
                        results.append(result.to_dict())
                    except Exception as exc:
                        results.append({"error": str(exc), "step": step.step_id})

        return {
            "status": "completed" if plan.is_complete() else "failed",
            "plan_id": plan.plan_id,
            "results": results,
        }

    def _execute_worker(
        self,
        worker: Worker,
        contract: WorkerContract,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> WorkerResult:
        """Execute a single worker with supervision, metrics, verification, and world model update."""
        step.status = PlanStepStatus.RUNNING

        with self._lock:
            self._active_workers[worker.worker_id] = worker

        try:
            self._telemetry.record_started(
                agent_id=worker.worker_id,
                task_id=contract.task_id,
                skill_id=contract.skill_id,
            )

            start = time.perf_counter()
            result = worker.execute(contract)
            latency_ms = (time.perf_counter() - start) * 1000
            result.latency_ms = latency_ms

            # Record metrics
            if result.is_success:
                self._metric_store.record_success(contract.skill_id, latency_ms)
                self._registry.record_success(contract.skill_id, latency_ms)
            else:
                error_msg = "; ".join(result.errors) if result.errors else "worker_failure"
                self._metric_store.record_failure(contract.skill_id, error_msg)
                self._registry.record_failure(contract.skill_id, error_msg)

            # Verification
            verification = self._tool_bridge.verify_result(
                tool_name=contract.skill_id,
                args=contract.input_data,
                result={"ok": result.is_success, "result": result.result, "error": "; ".join(result.errors)},
            )

            # Supervisor decision
            decision = self._supervisor.decide(plan, step, result)

            if decision == SupervisorDecision.CONTINUE:
                step.status = PlanStepStatus.COMPLETED
                step.result = result.to_dict()

                # World Model update (after verified completion)
                if verification.get("verified", False):
                    self._world_model_bridge.update_after_worker(
                        worker_id=worker.worker_id,
                        skill_id=contract.skill_id,
                        task_description=contract.task_description,
                        result={"ok": True, "result": result.result},
                        verification=verification,
                        artifacts=result.artifacts,
                    )
            elif decision == SupervisorDecision.RETRY:
                step.retries_used += 1
                if step.retries_used >= step.retry_budget:
                    step.status = PlanStepStatus.FAILED
                else:
                    step.status = PlanStepStatus.PENDING
            elif decision == SupervisorDecision.REPLAN:
                step.status = PlanStepStatus.FAILED
            elif decision == SupervisorDecision.ESCALATE:
                step.status = PlanStepStatus.FAILED
                self._telemetry.record_escalated(
                    worker.worker_id, contract.task_id, "supervisor_escalation"
                )
            elif decision == SupervisorDecision.CANCEL:
                step.status = PlanStepStatus.FAILED
                self._telemetry.record_cancelled(worker.worker_id, contract.task_id)

            self._telemetry.record_completed(
                agent_id=worker.worker_id,
                task_id=contract.task_id,
                skill_id=contract.skill_id,
                latency_ms=latency_ms,
            )

            return result

        except Exception as exc:
            step.status = PlanStepStatus.FAILED
            self._telemetry.record_failed(
                agent_id=worker.worker_id,
                task_id=contract.task_id,
                skill_id=contract.skill_id,
                errors=[str(exc)],
            )
            return WorkerResult(
                status=WorkerStatus.FAILED,
                task_id=contract.task_id,
                skill_id=contract.skill_id,
                errors=[str(exc)],
            )
        finally:
            with self._lock:
                self._active_workers.pop(worker.worker_id, None)

    def _create_worker(self, worker_class: str) -> Optional[Worker]:
        """Create a worker by class name."""
        cls = _WORKER_CLASSES.get(worker_class)
        if cls:
            return cls()
        logger.warning("Unknown worker class: %s", worker_class)
        return None

    def _on_supervision_event(self, event: SupervisionEvent) -> None:
        """Forward supervision events to telemetry."""
        if event.event_type == "escalate":
            self._telemetry.record_escalated(
                event.step_id, event.plan_id, "supervisor_escalation"
            )

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel an active plan."""
        with self._lock:
            plan = self._active_plans.get(plan_id)
            if plan:
                for step in plan.steps:
                    if step.status == PlanStepStatus.RUNNING:
                        step.status = PlanStepStatus.FAILED
                self._telemetry.record_cancelled(plan_id, plan_id)
                return True
        return False

    def health(self) -> Dict[str, Any]:
        """Orchestrator health metrics."""
        return {
            "registry": self._registry.count(),
            "active_plans": len(self._active_plans),
            "active_workers": len(self._active_workers),
            "telemetry": self._telemetry.summary(),
            "handoffs": self._handoffs.stats(),
            "conflicts": self._conflicts.stats(),
            "loop_guard": self._loop_guard.get_state(),
        }

    def reset(self) -> None:
        """Reset orchestrator state."""
        with self._lock:
            self._active_plans.clear()
            self._active_workers.clear()
        self._loop_guard.reset()
        self._supervisor.reset()
        self._telemetry.reset()
