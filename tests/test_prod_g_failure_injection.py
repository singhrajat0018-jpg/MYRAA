"""G Production Closure — Controlled Failure Injection + Recovery Verification.

Verifies the DETECT → DIAGNOSE → RECOVER → VERIFY cycle.
Tests:
1. Failure detection via DiagnosticsEngine
2. Root cause analysis via RootCauseAnalyzer
3. Healing execution via HealingEngine
4. Verification after healing
5. Loop protection (too many repairs)
6. Resource guard (resource limits)
7. Financial operation protection (no blind retry)
8. Sandbox/security/regression pipeline
9. Deployment rollback
10. Telemetry recording
11. Self-reflection on task outcome
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock

from desktop_agent.self_healing.diagnostics import (
    DiagnosticsEngine, DiagnosticResult, HealthStatus, SubsystemHealth,
)
from desktop_agent.self_healing.healing import (
    HealingEngine, HealingAction, HealingSeverity, HealingResult,
)
from desktop_agent.self_healing.root_cause import RootCauseAnalyzer
from desktop_agent.self_healing.guards import ResourceGuard, LoopProtectionGuard, ResourceLimits, LoopGuardConfig
from desktop_agent.self_healing.escalation import HumanEscalation, EscalationReason
from desktop_agent.self_healing.telemetry import SelfHealingTelemetry
from desktop_agent.self_healing.security import SecurityGate
from desktop_agent.self_healing.engineering import EngineeringStatus
from desktop_agent.self_healing.deployment import DeploymentManager, DeploymentStage
from desktop_agent.self_healing.reflection import SelfReflectionEngine


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_singletons():
    DiagnosticsEngine.reset_instance()
    HealingEngine.reset_instance()
    ResourceGuard.reset_instance()
    LoopProtectionGuard.reset_instance()
    SecurityGate.reset_instance()
    yield
    DiagnosticsEngine.reset_instance()
    HealingEngine.reset_instance()
    ResourceGuard.reset_instance()
    LoopProtectionGuard.reset_instance()
    SecurityGate.reset_instance()


# ============================================================
# 1. DETECT — DiagnosticsEngine finds failures
# ============================================================

class TestDetect:

    def test_detect_healthy_system(self):
        DiagnosticsEngine.reset_instance()
        diag = DiagnosticsEngine()
        result = DiagnosticResult(
            component="test_sys",
            status=HealthStatus.HEALTHY,
            timestamp=time.time(),
            reason="All clear",
            confidence=1.0,
        )
        diag.register_check("test_sys", lambda: result)
        results = diag.check_all()
        assert len(results) == 1
        assert results[0].status == HealthStatus.HEALTHY

    def test_detect_failing_component(self):
        DiagnosticsEngine.reset_instance()
        diag = DiagnosticsEngine()
        result = DiagnosticResult(
            component="broken_sys",
            status=HealthStatus.FAILING,
            timestamp=time.time(),
            reason="Service crashed",
            confidence=0.9,
            recommended_action="Restart service",
        )
        diag.register_check("broken_sys", lambda: result)
        results = diag.check_all()
        assert results[0].status == HealthStatus.FAILING
        assert results[0].recommended_action == "Restart service"

    def test_detect_check_exception(self):
        DiagnosticsEngine.reset_instance()
        diag = DiagnosticsEngine()
        def bad_check():
            raise RuntimeError("check crashed")
        diag.register_check("bad", bad_check)
        result = diag.check_one("bad")
        assert result.status == HealthStatus.FAILING
        assert "RuntimeError" in result.reason

    def test_detect_overall_status(self):
        DiagnosticsEngine.reset_instance()
        diag = DiagnosticsEngine()
        diag.register_check("ok1", lambda: DiagnosticResult(
            component="ok1", status=HealthStatus.HEALTHY,
            timestamp=time.time(), reason="ok", confidence=1.0))
        diag.register_check("fail1", lambda: DiagnosticResult(
            component="fail1", status=HealthStatus.FAILING,
            timestamp=time.time(), reason="fail", confidence=1.0))
        diag.check_all()
        summary = diag.health_summary()
        assert summary["overall_status"] in ("failing", "degraded")

    def test_consecutive_failures_tracked(self):
        DiagnosticsEngine.reset_instance()
        diag = DiagnosticsEngine()
        diag.register_check("flaky", lambda: DiagnosticResult(
            component="flaky", status=HealthStatus.FAILING,
            timestamp=time.time(), reason="fail", confidence=1.0))
        diag.check_one("flaky")
        diag.check_one("flaky")
        sub = diag.get_subsystem("flaky")
        assert sub.consecutive_failures == 2
        assert sub.is_healable

    def test_no_check_registered(self):
        DiagnosticsEngine.reset_instance()
        diag = DiagnosticsEngine()
        result = diag.check_one("nonexistent")
        assert result.status == HealthStatus.UNAVAILABLE


# ============================================================
# 2. DIAGNOSE — Root Cause Analysis
# ============================================================

class TestDiagnose:

    def test_root_cause_analysis(self):
        rca = RootCauseAnalyzer()
        result = DiagnosticResult(
            component="neural_engine",
            status=HealthStatus.FAILING,
            timestamp=time.time(),
            reason="Model inference timeout",
            confidence=0.8,
        )
        cause = rca.analyze(
            component="neural_engine",
            status=HealthStatus.FAILING,
            diagnostic_results=[result],
            recent_events=[],
        )
        assert cause is not None
        assert hasattr(cause, "cause")
        assert hasattr(cause, "confidence")

    def test_root_cause_healthy_component(self):
        rca = RootCauseAnalyzer()
        result = DiagnosticResult(
            component="memory",
            status=HealthStatus.HEALTHY,
            timestamp=time.time(),
            reason="All clear",
            confidence=1.0,
        )
        cause = rca.analyze(
            component="memory",
            status=HealthStatus.HEALTHY,
            diagnostic_results=[result],
            recent_events=[],
        )
        assert cause.confidence >= 0.0


# ============================================================
# 3. RECOVER — Healing Actions
# ============================================================

class TestRecover:

    def test_safe_repair(self):
        engine = HealingEngine()
        result = engine.heal("test_component", HealingAction.SAFE_REPAIR)
        assert result.success
        assert result.action == HealingAction.SAFE_REPAIR
        assert result.duration_ms >= 0

    def test_reconnect_provider(self):
        engine = HealingEngine()
        result = engine.heal("ollama", HealingAction.RECONNECT_PROVIDER,
                             context={"provider_name": "ollama"})
        assert result.success

    def test_invalidate_cache(self):
        engine = HealingEngine()
        result = engine.heal("brain_cache", HealingAction.INVALIDATE_CACHE,
                             context={"cache_name": "brain_cache"})
        assert result.success

    def test_restart_subsystem(self):
        engine = HealingEngine()
        result = engine.heal("vision", HealingAction.RESTART_SUBSYSTEM,
                             context={"subsystem": "vision"})
        assert result.success

    def test_escalate_to_human(self):
        engine = HealingEngine()
        result = engine.heal("broker", HealingAction.ESCALATE_TO_HUMAN)
        assert result.success
        assert "escalated" in result.message.lower() or "human" in result.message.lower()

    def test_rollback_code_with_version(self):
        engine = HealingEngine()
        result = engine.heal("code", HealingAction.ROLLBACK_CODE,
                             context={"version": "1.0.0"})
        assert result.success

    def test_rollback_code_without_version(self):
        engine = HealingEngine()
        result = engine.heal("code", HealingAction.ROLLBACK_CODE,
                             context={"version": ""})
        assert not result.success

    def test_restore_checkpoint_with_id(self):
        engine = HealingEngine()
        result = engine.heal("state", HealingAction.RESTORE_CHECKPOINT,
                             context={"checkpoint_id": "cp_001"})
        assert result.success
        assert result.rollback_performed

    def test_restore_checkpoint_without_id(self):
        engine = HealingEngine()
        result = engine.heal("state", HealingAction.RESTORE_CHECKPOINT,
                             context={"checkpoint_id": ""})
        assert not result.success

    def test_healing_history_recorded(self):
        engine = HealingEngine()
        engine.heal("comp1", HealingAction.SAFE_REPAIR)
        engine.heal("comp2", HealingAction.INVALIDATE_CACHE)
        history = engine.get_healing_history()
        assert len(history) == 2
        stats = engine.get_healing_stats()
        assert stats["total_attempts"] == 2
        assert stats["success_rate"] == 1.0


# ============================================================
# 4. VERIFY — Post-Heal Verification
# ============================================================

class TestVerify:

    def test_verify_heal_returns_bool(self):
        engine = HealingEngine()
        verified = engine.verify_heal("component", expected_status="healthy")
        assert isinstance(verified, bool)

    def test_apply_repair_with_verification(self):
        engine = HealingEngine()
        from desktop_agent.self_healing.healing import RepairProposal
        proposal = RepairProposal(
            repair_id="test_repair",
            component="test_sys",
            description="Fix test_sys",
            risk_level=HealingSeverity.LOW,
            validation_steps=["Check health"],
            rollback_steps=["Restore"],
        )
        result = engine.apply_repair(proposal)
        assert result.success
        assert result.verification_passed


# ============================================================
# 5. LOOP PROTECTION
# ============================================================

class TestLoopProtection:

    def test_loop_guard_blocks_after_max_attempts(self):
        LoopProtectionGuard.reset_instance()
        config = LoopGuardConfig(max_repair_attempts=3)
        guard = LoopProtectionGuard(config)
        assert guard.can_attempt_repair()
        guard.record_repair_attempt("comp")
        guard.record_repair_attempt("comp")
        guard.record_repair_attempt("comp")
        assert not guard.can_attempt_repair()

    def test_loop_guard_state(self):
        LoopProtectionGuard.reset_instance()
        config = LoopGuardConfig(max_repair_attempts=5)
        guard = LoopProtectionGuard(config)
        guard.record_repair_attempt("a")
        guard.record_repair_attempt("a")
        state = guard.get_state()
        assert "repair_attempts" in state
        assert state["repair_attempts"] == 2


# ============================================================
# 6. RESOURCE GUARD
# ============================================================

class TestResourceGuard:

    def test_resource_guard_allows_when_clear(self):
        ResourceGuard.reset_instance()
        limits = ResourceLimits(max_concurrent_heals=3)
        guard = ResourceGuard(limits)
        with patch("desktop_agent.self_healing.guards._get_resource_usage",
                   return_value={"cpu_pct": 10.0, "memory_mb": 100, "disk_mb": 100, "threads": 5}):
            assert guard.can_start_operation()
            guard.record_operation_start()
            guard.record_operation_end()

    def test_resource_guard_blocks_when_full(self):
        ResourceGuard.reset_instance()
        limits = ResourceLimits(max_concurrent_heals=2)
        guard = ResourceGuard(limits)
        with patch("desktop_agent.self_healing.guards._get_resource_usage",
                   return_value={"cpu_pct": 10.0, "memory_mb": 100, "disk_mb": 100, "threads": 5}):
            guard.record_operation_start()
            guard.record_operation_start()
            assert not guard.can_start_operation()
            guard.record_operation_end()

    def test_resource_guard_usage(self):
        ResourceGuard.reset_instance()
        limits = ResourceLimits(max_concurrent_heals=5)
        guard = ResourceGuard(limits)
        usage = guard.get_usage()
        assert isinstance(usage, dict)


# ============================================================
# 7. FINANCIAL OPERATION PROTECTION
# ============================================================

class TestFinancialProtection:

    def test_blind_retry_blocked(self):
        engine = HealingEngine()
        with pytest.raises(ValueError, match="financial"):
            engine.heal("trading_engine", HealingAction.RETRY_TASK)

    def test_blind_replan_blocked(self):
        engine = HealingEngine()
        with pytest.raises(ValueError, match="financial"):
            engine.heal("portfolio_manager", HealingAction.REPLAN_TASK)

    def test_non_financial_repair_allowed(self):
        engine = HealingEngine()
        result = engine.heal("vision_module", HealingAction.RETRY_TASK)
        assert result.success


# ============================================================
# 8. SANDBOX / SECURITY / REGRESSION PIPELINE
# ============================================================

class TestSandboxPipeline:

    def test_propose_improvement(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        result = c.self_healing.propose_improvement(
            description="Optimize memory lookup",
            target_files=["desktop_agent/brain/memory/unified_manager.py"],
        )
        assert result["success"]
        assert "request_id" in result
        assert "patch_risk" in result

    def test_security_gate_rejects_dangerous(self):
        SecurityGate.reset_instance()
        sg = SecurityGate()
        allowed, violations = sg.check_proposal(
            proposed_changes={"malicious.py": "eval('import os; os.system(\"rm -rf /\")')"},
            target_files=["desktop_agent/main.py"],
        )
        assert not allowed or len(violations) > 0

    def test_security_gate_allows_safe(self):
        SecurityGate.reset_instance()
        sg = SecurityGate()
        allowed, violations = sg.check_proposal(
            proposed_changes={"brain.py": "log.info('improved logging')"},
            target_files=["desktop_agent/brain/brain_engine.py"],
        )
        assert allowed


# ============================================================
# 9. DEPLOYMENT / ROLLBACK
# ============================================================

class TestDeployment:

    def test_deployment_rollback(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        dm = c.self_healing.deployment
        result = c.self_healing.rollback("nonexistent_deploy")
        assert isinstance(result, dict)
        assert "success" in result

    def test_deployment_record(self):
        from desktop_agent.self_healing.deployment import DeploymentRecord, DeploymentStage
        record = DeploymentRecord(
            deployment_id="dep_001",
            version="1.0.0",
            stage=DeploymentStage.STABLE,
            started_at=time.time(),
        )
        summary = record.summary()
        assert summary["deployment_id"] == "dep_001"
        assert summary["stage"] == "stable"


# ============================================================
# 10. TELEMETRY RECORDING
# ============================================================

class TestTelemetry:

    def test_telemetry_record_event(self):
        tel = SelfHealingTelemetry()
        tel.record_event("healing_started", "test_component", {"key": "val"}, severity="info")
        events = tel.get_events(limit=10)
        assert len(events) >= 1

    def test_telemetry_healing_stats(self):
        tel = SelfHealingTelemetry()
        stats = tel.get_healing_stats()
        assert isinstance(stats, dict)

    def test_telemetry_summary(self):
        tel = SelfHealingTelemetry()
        summary = tel.get_telemetry_summary()
        assert isinstance(summary, dict)

    def test_telemetry_incidents(self):
        tel = SelfHealingTelemetry()
        incidents = tel.get_incidents()
        assert isinstance(incidents, list)


# ============================================================
# 11. SELF-REFLECTION
# ============================================================

class TestSelfReflection:

    def test_reflect_on_task(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        result = c.self_healing.reflect_on_task(
            task_id="task_001",
            goal="Analyze RELIANCE stock",
            steps=["fetch_quote", "run_indicators", "generate_report"],
            result={"status": "completed", "confidence": 0.85},
            verified=True,
        )
        assert "task_id" in result
        assert "outcome" in result
        assert "efficiency_score" in result


# ============================================================
# 12. FULL CYCLE: DETECT → DIAGNOSE → RECOVER → VERIFY
# ============================================================

class TestFullCycle:

    def test_full_healing_cycle(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        mgr = c.self_healing

        # 1. DETECT — run diagnostics
        health = mgr.check_health()
        assert "health" in health or "overall_status" in health

        # 2. DIAGNOSE — diagnose a component
        diagnosis = mgr.diagnose_issue("brain_engine")
        assert "component" in diagnosis
        assert "diagnostic" in diagnosis
        assert "root_cause" in diagnosis

        # 3. RECOVER — heal it
        heal_result = mgr.heal("test_component", action="auto")
        assert isinstance(heal_result, dict)
        assert "success" in heal_result

        # 4. VERIFY — get system status
        status = mgr.get_system_status()
        assert "health" in status
        assert "healing_stats" in status

    def test_full_report(self):
        from desktop_agent.core.application_container import ApplicationContainer
        c = ApplicationContainer()
        report = c.self_healing.get_full_report()
        assert "system_status" in report
        assert "healing_history_count" in report
        assert "reflection_count" in report
        assert "security_violations" in report
