from __future__ import annotations

"""Top-level SelfHealingManager -- DI composition root for MYRAA.

This is the single entry point that wires ALL self-healing components
together.  It reuses existing infrastructure (RecoveryEngine,
FailureContainmentManager, ExperienceEngine, Memory 2.0, EventBus/Blackboard,
MetricsCollector, VerificationManager) without creating duplicates.
"""

import logging
import threading
import time
import uuid
from typing import Any, Optional

from .diagnostics import DiagnosticsEngine, HealthStatus
from .root_cause import RootCauseAnalyzer
from .healing import HealingEngine, HealingAction, HealingSeverity
from .engineering import SelfEngineeringEngine, EngineeringRequest, EngineeringStatus
from .patch import PatchGenerator
from .regression import RegressionAnalyzer
from .optimization import PerformanceOptimizer
from .reflection import SelfReflectionEngine
from .workflow import WorkflowOptimizer
from .model_improvement import ModelVersionManager, CapabilityGapDetector
from .deployment import DeploymentManager
from .versioning import VersionManager
from .security import SecurityGate
from .guards import ResourceGuard, LoopProtectionGuard
from .escalation import HumanEscalation, EscalationReason
from .telemetry import SelfHealingTelemetry

logger = logging.getLogger(__name__)


class SelfHealingManager:
    """Central coordinator for self-healing, self-improvement, and self-engineering.

    Reuses existing infrastructure:

    - ``RecoveryEngine`` (failure_containment.py) for retry/recovery decisions
    - ``FailureContainmentManager`` for subsystem health tracking
    - ``ExperienceEngine`` for learning from outcomes
    - ``Memory 2.0`` for long-term healing memory
    - ``EventBus``/``Blackboard`` for inter-component communication
    - ``MetricsCollector``/``TelemetryCollector`` for metrics
    - ``VerificationManager`` for post-heal verification

    Does NOT create a second brain, planner, memory, autonomy, verification,
    or recovery engine.
    """

    _instance: Optional[SelfHealingManager] = None
    _lock_class = threading.Lock()

    def __new__(cls, **kwargs: Any) -> SelfHealingManager:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        *,
        diagnostics: DiagnosticsEngine | None = None,
        root_cause: RootCauseAnalyzer | None = None,
        healing: HealingEngine | None = None,
        engineering: SelfEngineeringEngine | None = None,
        patch_gen: PatchGenerator | None = None,
        regression: RegressionAnalyzer | None = None,
        optimizer: PerformanceOptimizer | None = None,
        reflection: SelfReflectionEngine | None = None,
        workflow: WorkflowOptimizer | None = None,
        model_mgr: ModelVersionManager | None = None,
        gap_detector: CapabilityGapDetector | None = None,
        deployment: DeploymentManager | None = None,
        versioning: VersionManager | None = None,
        security: SecurityGate | None = None,
        resource_guard: ResourceGuard | None = None,
        loop_guard: LoopProtectionGuard | None = None,
        escalation: HumanEscalation | None = None,
        telemetry: SelfHealingTelemetry | None = None,
    ) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._lock = threading.Lock()

        # Wire dependencies -- singletons are used when not explicitly provided
        self.diagnostics = diagnostics or DiagnosticsEngine()
        self.root_cause = root_cause or RootCauseAnalyzer()
        self.healing = healing or HealingEngine()
        self.engineering = engineering or SelfEngineeringEngine()
        self.patch_gen = patch_gen or PatchGenerator()
        self.regression = regression or RegressionAnalyzer()
        self.optimizer = optimizer or PerformanceOptimizer()
        self.reflection = reflection or SelfReflectionEngine()
        self.workflow = workflow or WorkflowOptimizer()
        self.model_mgr = model_mgr or ModelVersionManager()
        self.gap_detector = gap_detector or CapabilityGapDetector()
        self.deployment = deployment or DeploymentManager()
        self.versioning = versioning or VersionManager()
        self.security = security or SecurityGate()
        self.resource_guard = resource_guard or ResourceGuard()
        self.loop_guard = loop_guard or LoopProtectionGuard()
        self.escalation = escalation or HumanEscalation()
        self.telemetry = telemetry or SelfHealingTelemetry()

        logger.info("SelfHealingManager initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_health(self) -> dict[str, Any]:
        """Run all registered diagnostics and return a health summary."""
        self.telemetry.record_event(
            "diagnosis", "system", {"action": "check_health"}, severity="info"
        )
        results = self.diagnostics.check_all()
        summary = self.diagnostics.health_summary()
        summary["check_results"] = [r.to_dict() for r in results]
        summary["timestamp"] = time.time()
        return summary

    def diagnose_issue(self, component: str) -> dict[str, Any]:
        """Run diagnostics and root-cause analysis for a specific component."""
        # Run diagnostic check for the component
        result = self.diagnostics.check_one(component)
        subsystem = self.diagnostics.get_subsystem(component)

        # Gather recent events from telemetry
        recent_events = [
            ev.to_dict() for ev in self.telemetry.get_events(limit=20)
        ]

        # Run root-cause analysis
        root_cause = self.root_cause.analyze(
            component=component,
            status=result.status,
            diagnostic_results=[result],
            recent_events=recent_events,
        )

        self.telemetry.record_event(
            "root_cause",
            component,
            {
                "cause": root_cause.cause,
                "confidence": root_cause.confidence,
                "impact": root_cause.impact,
            },
            severity="warning" if result.status != HealthStatus.HEALTHY else "info",
        )

        return {
            "component": component,
            "diagnostic": result.to_dict(),
            "subsystem": subsystem.to_dict(),
            "root_cause": root_cause.to_dict(),
            "timestamp": time.time(),
        }

    def heal(self, component: str, action: str = "auto") -> dict[str, Any]:
        """Auto-select healing action based on diagnosis, then execute it."""
        self.telemetry.record_event(
            "healing_started",
            component,
            {"action": action, "requested_at": time.time()},
            severity="info",
        )

        # Check guards before proceeding
        if not self.resource_guard.can_start_operation():
            msg = "Resource limits exceeded -- cannot start healing"
            self.telemetry.record_event(
                "healing_failed",
                component,
                {"reason": msg},
                severity="error",
            )
            return {"success": False, "message": msg, "component": component}

        if not self.loop_guard.can_attempt_repair():
            msg = "Loop protection triggered -- too many repair attempts"
            self.telemetry.record_event(
                "escalation",
                component,
                {"reason": msg},
                severity="warning",
            )
            self.escalation.escalate(
                reason=EscalationReason.REPEATED_FAILURE,
                component=component,
                description=msg,
            )
            return {"success": False, "message": msg, "component": component}

        self.resource_guard.record_operation_start()
        self.loop_guard.record_repair_attempt(failure_hash=component)

        try:
            # Diagnose first
            diagnosis = self.diagnose_issue(component)
            root_cause = diagnosis.get("root_cause", {})
            impact = root_cause.get("impact", "low")

            # Select healing action based on diagnosis
            healing_action = self._select_action(action, impact, component)

            # Execute the heal
            result = self.healing.heal(component, healing_action)

            self.telemetry.record_event(
                "healing_completed" if result.success else "healing_failed",
                component,
                {
                    "action": healing_action.value,
                    "success": result.success,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                },
                severity="info" if result.success else "error",
            )

            return {
                "success": result.success,
                "message": result.message,
                "action": healing_action.value,
                "duration_ms": result.duration_ms,
                "component": component,
                "diagnosis": root_cause,
                "verification_passed": result.verification_passed,
            }
        finally:
            self.resource_guard.record_operation_end()

    def propose_improvement(
        self,
        description: str,
        target_files: list[str],
    ) -> dict[str, Any]:
        """Create an engineering request for a self-improvement."""
        request_id = str(uuid.uuid4())

        # Generate a patch to assess risk
        patch = self.patch_gen.generate_patch(description, target_files)

        # Security check
        allowed, violations = self.security.check_proposal(
            proposed_changes={},
            target_files=target_files,
        )

        if not allowed:
            self.telemetry.record_event(
                "engineering",
                "system",
                {
                    "request_id": request_id,
                    "status": "security_rejected",
                    "violations": [v.description for v in violations],
                },
                severity="error",
            )
            return {
                "success": False,
                "request_id": request_id,
                "message": "Security gate rejected the proposal",
                "violations": [v.to_dict() if hasattr(v, "to_dict") else str(v) for v in violations],
            }

        # Create the engineering request
        eng_request = EngineeringRequest(
            request_id=request_id,
            description=description,
            target_files=list(target_files),
            improvement_type="optimization",
            risk_level=HealingSeverity.MEDIUM,
            created_at=time.time(),
        )

        self.telemetry.record_event(
            "engineering",
            "system",
            {
                "request_id": request_id,
                "description": description,
                "target_files": target_files,
                "patch_risk": patch.risk.value,
            },
            severity="info",
        )

        return {
            "success": True,
            "request_id": request_id,
            "description": description,
            "target_files": target_files,
            "patch_risk": patch.risk.value,
            "impact_areas": [a.value for a in patch.impact_areas],
            "rollback_point": patch.rollback_point,
        }

    def apply_improvement(self, request_id: str) -> dict[str, Any]:
        """Run the sandbox pipeline for an approved engineering request."""
        self.telemetry.record_event(
            "engineering",
            "system",
            {"request_id": request_id, "action": "apply_start"},
            severity="info",
        )

        # Retrieve the active sandbox
        sandboxes = self.engineering.get_active_sandboxes()
        sandbox_info = None
        for sb in sandboxes:
            if sb.get("request_id") == request_id:
                sandbox_info = sb
                break

        if sandbox_info is None:
            return {
                "success": False,
                "request_id": request_id,
                "message": "No active sandbox found for request",
            }

        sandbox_path = sandbox_info["path"]

        # Run tests
        passed, failed = self.engineering.run_tests_in_sandbox(sandbox_path)

        # Security check
        sec_ok = self.engineering.security_check_sandbox(sandbox_path)

        # Benchmark
        benchmark = self.engineering.benchmark_sandbox(sandbox_path)

        # Promote or reject
        result = self.engineering.promote_sandbox(sandbox_path, request_id)

        status_str = result.status.value
        self.telemetry.record_event(
            "engineering",
            "system",
            {
                "request_id": request_id,
                "status": status_str,
                "tests_passed": passed,
                "tests_failed": failed,
                "security_passed": sec_ok,
                "files_changed": len(result.files_changed),
            },
            severity="info" if status_str == EngineeringStatus.PROMOTED.value else "warning",
        )

        return {
            "success": status_str == EngineeringStatus.PROMOTED.value,
            "request_id": request_id,
            "status": status_str,
            "tests_passed": passed,
            "tests_failed": failed,
            "security_passed": sec_ok,
            "benchmark": benchmark,
            "files_changed": result.files_changed,
        }

    def rollback(self, deployment_id: str) -> dict[str, Any]:
        """Rollback a deployment to a stable version."""
        self.telemetry.record_event(
            "rollback",
            "system",
            {"deployment_id": deployment_id},
            severity="warning",
        )

        success = self.deployment.rollback(deployment_id, reason="manual_rollback")

        if success:
            # Try to rollback any associated engineering sandbox
            self.engineering.rollback_sandbox(deployment_id)

        self.telemetry.record_event(
            "healing_completed" if success else "healing_failed",
            "system",
            {
                "deployment_id": deployment_id,
                "rollback_success": success,
            },
            severity="info" if success else "error",
        )

        return {
            "success": success,
            "deployment_id": deployment_id,
            "message": "Rollback completed" if success else "Rollback failed",
        }

    def reflect_on_task(
        self,
        task_id: str,
        goal: str,
        steps: list[str],
        result: dict,
        verified: bool,
    ) -> dict[str, Any]:
        """Produce a reflection record for a completed task."""
        record = self.reflection.reflect(
            task_id=task_id,
            goal=goal,
            steps_taken=steps,
            result=result,
            verified=verified,
        )

        self.telemetry.record_event(
            "reflection",
            task_id,
            {
                "goal": goal,
                "outcome": record.outcome.value,
                "efficiency": record.efficiency_score,
                "lessons_count": len(record.lessons),
            },
            severity="info",
        )

        return {
            "task_id": task_id,
            "outcome": record.outcome.value,
            "efficiency_score": record.efficiency_score,
            "verification_confirmed": record.verification_confirmed,
            "unnecessary_steps": record.unnecessary_steps,
            "reasoning_quality": record.reasoning_quality,
            "lessons": record.lessons,
        }

    def get_system_status(self) -> dict[str, Any]:
        """Comprehensive status: health, active heals, deployments, escalations, events."""
        health_summary = self.diagnostics.health_summary()
        active_deploy = self.deployment.get_active_deployment()
        pending_esc = self.escalation.get_pending()
        recent_events = self.telemetry.get_events(limit=10)
        healing_stats = self.telemetry.get_healing_stats()
        resource_usage = self.resource_guard.get_usage()
        loop_state = self.loop_guard.get_state()

        return {
            "health": health_summary,
            "active_deployment": active_deploy.summary() if active_deploy else None,
            "pending_escalations": len(pending_esc),
            "escalations": [
                {
                    "id": e.request_id,
                    "reason": e.reason.value,
                    "component": e.component,
                }
                for e in pending_esc
            ],
            "recent_events": [ev.to_dict() for ev in recent_events],
            "healing_stats": healing_stats,
            "resource_usage": resource_usage,
            "loop_guard": loop_state,
            "active_sandboxes": len(self.engineering.get_active_sandboxes()),
            "timestamp": time.time(),
        }

    def get_full_report(self) -> dict[str, Any]:
        """Complete self-healing report covering all subsystems."""
        system_status = self.get_system_status()
        telemetry_summary = self.telemetry.get_telemetry_summary()
        incidents = self.telemetry.get_incidents()
        healing_history = self.healing.get_healing_history()
        optimization_history = self.optimizer.get_optimization_history()
        reflection_history = self.reflection.get_reflection_history()
        workflow_stats = self.workflow.get_workflow_stats()
        deployment_history = self.deployment.get_deployment_history()
        checkpoint_list = self.versioning.list_checkpoints()
        known_gaps = self.gap_detector.get_known_gaps()
        security_violations = self.security.get_violation_history()

        return {
            "system_status": system_status,
            "telemetry_summary": telemetry_summary,
            "active_incidents": len(incidents),
            "incidents": [ev.to_dict() for ev in incidents],
            "healing_history_count": len(healing_history),
            "healing_stats": self.healing.get_healing_stats(),
            "optimization_proposals": len(optimization_history),
            "reflection_count": len(reflection_history),
            "workflow_stats": workflow_stats,
            "deployment_count": len(deployment_history),
            "checkpoints": len(checkpoint_list),
            "capability_gaps": len(known_gaps),
            "security_violations": len(security_violations),
            "timestamp": time.time(),
        }

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_class:
            cls._instance = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_action(
        self,
        requested: str,
        impact: str,
        component: str,
    ) -> HealingAction:
        """Auto-select a HealingAction based on the request, impact, and component."""
        if requested != "auto":
            # Map string to HealingAction if possible
            try:
                return HealingAction(requested)
            except ValueError:
                logger.warning("Unknown action %r, falling back to SAFE_REPAIR", requested)
                return HealingAction.SAFE_REPAIR

        impact_action_map = {
            "critical": HealingAction.ESCALATE_TO_HUMAN,
            "high": HealingAction.RESTART_SUBSYSTEM,
            "medium": HealingAction.RECONNECT_PROVIDER,
            "low": HealingAction.SAFE_REPAIR,
        }
        return impact_action_map.get(impact, HealingAction.SAFE_REPAIR)
