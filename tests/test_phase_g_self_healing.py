from __future__ import annotations
import time, os, sys, tempfile, shutil, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from desktop_agent.self_healing import (
    DiagnosticsEngine, DiagnosticResult, HealthStatus, SubsystemHealth,
    RootCauseAnalyzer, RootCause, Evidence, EvidenceType,
    HealingEngine, HealingAction, HealingResult, HealingSeverity, RepairProposal,
    SelfEngineeringEngine, EngineeringRequest, EngineeringResult, EngineeringStatus,
    PatchGenerator, PatchRecord, PatchRisk, ImpactArea,
    RegressionAnalyzer, RegressionStatus, BeforeAfter, BehavioralDiff,
    PerformanceOptimizer, OptimizationCategory, OptimizationProposal,
    SelfReflectionEngine, ReflectionRecord, TaskOutcome, OutcomeRecord,
    WorkflowOptimizer, WorkflowStep, WorkflowRecord, OptimizedWorkflow,
    ModelVersionManager, CapabilityGapDetector, ModelVersion, CapabilityGap,
    DeploymentManager, DeploymentRecord, DeploymentStage, CanaryMetrics,
    VersionManager, MYRAAVersion,
    SecurityGate, ProtectedArea, SecurityViolation,
    ResourceGuard, LoopProtectionGuard, ResourceLimits, LoopGuardConfig,
    HumanEscalation, EscalationRequest, EscalationReason,
    SelfHealingTelemetry, HealingEvent, SystemHealthSnapshot,
    SelfHealingManager,
)


def _diag(name="test_component", status=HealthStatus.HEALTHY, reason="ok"):
    return DiagnosticResult(component=name, status=status, timestamp=time.time(), reason=reason, evidence={}, confidence=0.9, recommended_action="none")


def _evidence(content="test evidence", etype=EvidenceType.ERROR_LOG):
    return Evidence(type=etype, source="test", content=content, timestamp=time.time(), weight=0.8)


class TestDiagnostics:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_health_status_values(self):
        values = [s.value for s in HealthStatus]
        assert len(values) == 6
        assert "healthy" in values
        assert "degraded" in values
        assert "failing" in values
        assert "unavailable" in values
        assert "corrupted" in values
        assert "unknown" in values

    def test_diagnostic_result_creation(self):
        r = _diag(name="disk", status=HealthStatus.DEGRADED, reason="90% full")
        d = r.to_dict()
        assert d["component"] == "disk"
        assert d["status"] == "degraded"
        assert d["reason"] == "90% full"
        assert d["confidence"] == 0.9
        assert "timestamp" in d
        assert "evidence" in d
        assert "recommended_action" in d

    def test_subsystem_health_record(self):
        sub = SubsystemHealth("cpu")
        sub.record(_diag("cpu", HealthStatus.HEALTHY))
        sub.record(_diag("cpu", HealthStatus.HEALTHY))
        sub.record(_diag("cpu", HealthStatus.HEALTHY))
        assert sub.consecutive_failures == 0
        assert len(sub.history) == 3
        assert sub.current_status == HealthStatus.HEALTHY

    def test_subsystem_is_healable(self):
        sub = SubsystemHealth("voice")
        sub.record(_diag("voice", HealthStatus.FAILING))
        sub.record(_diag("voice", HealthStatus.FAILING))
        assert sub.consecutive_failures == 2
        assert sub.current_status == HealthStatus.FAILING
        assert sub.is_healable is True

    def test_diagnostics_singleton(self):
        a = DiagnosticsEngine()
        b = DiagnosticsEngine()
        assert a is b

    def test_diagnostics_register_check(self):
        engine = DiagnosticsEngine()
        engine.register_check("mem", lambda: _diag("mem", HealthStatus.HEALTHY))
        result = engine.check_one("mem")
        assert isinstance(result, DiagnosticResult)
        assert result.component == "mem"
        assert result.status == HealthStatus.HEALTHY

    def test_diagnostics_check_all(self):
        engine = DiagnosticsEngine()
        engine.register_check("a", lambda: _diag("a", HealthStatus.HEALTHY))
        engine.register_check("b", lambda: _diag("b", HealthStatus.DEGRADED))
        engine.register_check("c", lambda: _diag("c", HealthStatus.FAILING))
        results = engine.check_all()
        assert len(results) == 3
        components = {r.component for r in results}
        assert components == {"a", "b", "c"}

    def test_diagnostics_health_summary(self):
        engine = DiagnosticsEngine()
        engine.register_check("svc", lambda: _diag("svc", HealthStatus.HEALTHY))
        engine.check_one("svc")
        summary = engine.health_summary()
        assert "overall_status" in summary
        assert "subsystems" in summary
        assert "counts" in summary
        assert summary["overall_status"] == "healthy"

    def test_diagnostics_check_exception_safety(self):
        engine = DiagnosticsEngine()
        engine.register_check("bad", (_ for _ in ()).throw(RuntimeError("boom")) if False else (_ for _ in ()))
        def _raise():
            raise RuntimeError("boom")
        engine.register_check("bad", _raise)
        result = engine.check_one("bad")
        assert result.status == HealthStatus.FAILING
        assert "RuntimeError" in result.reason

    def test_diagnostics_disable(self):
        engine = DiagnosticsEngine()
        engine.register_check("x", lambda: _diag("x", HealthStatus.HEALTHY))
        engine.enable()
        engine.disable()
        assert engine._enabled is False


class TestRootCause:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_evidence_creation(self):
        ev = _evidence("something went wrong", EvidenceType.ERROR_LOG)
        assert ev.type == EvidenceType.ERROR_LOG
        assert ev.source == "test"
        assert ev.content == "something went wrong"
        assert ev.weight == 0.8
        assert ev.timestamp > 0

    def test_root_cause_creation(self):
        ev = _evidence()
        rc = RootCause(
            cause="memory exhaustion",
            description="OOM killer invoked",
            evidence=[ev],
            confidence=0.85,
            impact="critical",
            recommended_fix="increase RAM",
            category="resource",
        )
        assert rc.cause == "memory exhaustion"
        assert rc.confidence == 0.85
        assert rc.impact == "critical"
        assert len(rc.evidence) == 1
        d = rc.to_dict()
        assert d["cause"] == "memory exhaustion"
        assert d["category"] == "resource"

    def test_analyzer_singleton(self):
        a = RootCauseAnalyzer()
        b = RootCauseAnalyzer()
        assert a is b

    def test_analyze_returns_root_cause(self):
        analyzer = RootCauseAnalyzer()
        results = [_diag("svc", HealthStatus.FAILING, "connection refused")]
        rc = analyzer.analyze(
            component="svc",
            status=HealthStatus.FAILING,
            diagnostic_results=results,
            recent_events=[],
        )
        assert isinstance(rc, RootCause)
        assert rc.confidence > 0
        assert rc.impact in ("low", "medium", "high", "critical")
        assert len(rc.evidence) > 0

    def test_gather_evidence(self):
        analyzer = RootCauseAnalyzer()
        results = [
            _diag("db", HealthStatus.FAILING, "timeout"),
            _diag("db", HealthStatus.DEGRADED, "slow queries"),
        ]
        events = [{"type": "error", "message": "connection reset", "source": "postgres"}]
        evidence = analyzer.gather_evidence("db", results, events)
        assert isinstance(evidence, list)
        assert len(evidence) >= 2
        for ev in evidence:
            assert isinstance(ev, Evidence)
            assert ev.weight > 0

    def test_analyze_pattern(self):
        analyzer = RootCauseAnalyzer()
        history = [_diag("cache", HealthStatus.FAILING, f"fail {i}") for i in range(6)]
        rc = analyzer.analyze_pattern("cache", history)
        assert rc is not None
        assert "Chronic failure" in rc.cause
        assert rc.impact == "critical"


class TestHealing:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_healing_action_values(self):
        values = [a.value for a in HealingAction]
        assert len(values) == 12
        assert "reconnect_provider" in values
        assert "restart_worker" in values
        assert "invalidate_cache" in values
        assert "cleanup_files" in values
        assert "reinit_connection" in values
        assert "retry_task" in values
        assert "replan_task" in values
        assert "restore_checkpoint" in values
        assert "restart_subsystem" in values
        assert "safe_repair" in values
        assert "rollback_code" in values
        assert "escalate_to_human" in values

    def test_healing_result_creation(self):
        hr = HealingResult(
            action=HealingAction.SAFE_REPAIR,
            success=True,
            message="repaired",
            duration_ms=12.5,
            verification_passed=True,
            rollback_performed=False,
            timestamp=time.time(),
        )
        assert hr.action == HealingAction.SAFE_REPAIR
        assert hr.success is True
        assert hr.duration_ms == 12.5
        assert hr.verification_passed is True
        assert hr.rollback_performed is False

    def test_healing_engine_singleton(self):
        a = HealingEngine()
        b = HealingEngine()
        assert a is b

    def test_heal_returns_result(self):
        engine = HealingEngine()
        result = engine.heal("test", HealingAction.INVALIDATE_CACHE, {})
        assert isinstance(result, HealingResult)
        assert result.action == HealingAction.INVALIDATE_CACHE

    def test_heal_invalidate_cache(self):
        engine = HealingEngine()
        result = engine.heal("test_cache", HealingAction.INVALIDATE_CACHE, {"cache_name": "my_cache"})
        assert result.success is True
        assert "my_cache" in result.message

    def test_heal_history(self):
        engine = HealingEngine()
        engine.heal("a", HealingAction.SAFE_REPAIR, {})
        engine.heal("b", HealingAction.INVALIDATE_CACHE, {})
        engine.heal("c", HealingAction.CLEANUP_FILES, {})
        history = engine.get_healing_history()
        assert len(history) == 3

    def test_healing_stats(self):
        engine = HealingEngine()
        engine.heal("a", HealingAction.SAFE_REPAIR, {})
        engine.heal("b", HealingAction.INVALIDATE_CACHE, {})
        stats = engine.get_healing_stats()
        assert "total_attempts" in stats
        assert "success_count" in stats or "success_rate" in stats
        assert "by_action" in stats
        assert stats["total_attempts"] >= 2

    def test_propose_repair(self):
        engine = HealingEngine()
        proposal = engine.propose_repair("voice", "intermittent disconnects")
        assert isinstance(proposal, RepairProposal)
        assert proposal.component == "voice"
        assert "disconnects" in proposal.description

    def test_repair_proposal_fields(self):
        engine = HealingEngine()
        proposal = engine.propose_repair("brain", "timeout")
        assert hasattr(proposal, "repair_id")
        assert hasattr(proposal, "component")
        assert hasattr(proposal, "risk_level")
        assert isinstance(proposal.risk_level, HealingSeverity)
        assert len(proposal.repair_id) > 0

    def test_healing_severity_values(self):
        values = [s.value for s in HealingSeverity]
        assert len(values) == 4
        assert "low" in values
        assert "medium" in values
        assert "high" in values
        assert "critical" in values


class TestEngineering:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_engineering_status_values(self):
        values = [s.value for s in EngineeringStatus]
        assert len(values) == 12
        assert "proposed" in values
        assert "sandbox_created" in values
        assert "modifying" in values
        assert "testing" in values
        assert "benchmarking" in values
        assert "security_check" in values
        assert "regression_test" in values
        assert "staging" in values
        assert "promoting" in values
        assert "promoted" in values
        assert "rejected" in values
        assert "rolled_back" in values

    def test_engineering_request_creation(self):
        req = EngineeringRequest(
            request_id="req-001",
            description="optimise brain pipeline",
            target_files=["brain.py"],
            improvement_type="performance",
            risk_level=HealingSeverity.MEDIUM,
            created_at=time.time(),
        )
        assert req.request_id == "req-001"
        assert req.improvement_type == "performance"
        assert req.risk_level == HealingSeverity.MEDIUM

    def test_engineering_result_creation(self):
        res = EngineeringResult(
            request_id="req-002",
            status=EngineeringStatus.PROMOTED,
            sandbox_path="/tmp/sb",
            files_changed=["a.py"],
            tests_passed=5,
            tests_failed=0,
            benchmark_before={"time": 100},
            benchmark_after={"time": 80},
            security_passed=True,
            regression_passed=True,
            rollback_point="/tmp/rollback",
            timestamp=time.time(),
        )
        assert res.status == EngineeringStatus.PROMOTED
        assert res.tests_passed == 5
        assert res.security_passed is True

    def test_engine_singleton(self):
        a = SelfEngineeringEngine()
        b = SelfEngineeringEngine()
        assert a is b

    def test_create_sandbox(self):
        engine = SelfEngineeringEngine()
        req = EngineeringRequest(
            request_id="sb-test-1",
            description="test sandbox",
            target_files=[],
            improvement_type="refactor",
            risk_level=HealingSeverity.LOW,
            created_at=time.time(),
        )
        path = engine.create_sandbox(req)
        assert isinstance(path, str)
        assert len(path) > 0

    def test_sandbox_directory_exists(self):
        engine = SelfEngineeringEngine()
        req = EngineeringRequest(
            request_id="sb-test-2",
            description="test dir",
            target_files=[],
            improvement_type="refactor",
            risk_level=HealingSeverity.LOW,
            created_at=time.time(),
        )
        path = engine.create_sandbox(req)
        assert os.path.isdir(path)

    def test_security_check_safe_code(self):
        engine = SelfEngineeringEngine()
        req = EngineeringRequest(
            request_id="sb-safe",
            description="safe code",
            target_files=[],
            improvement_type="refactor",
            risk_level=HealingSeverity.LOW,
            created_at=time.time(),
        )
        path = engine.create_sandbox(req)
        safe_file = os.path.join(path, "safe.py")
        with open(safe_file, "w") as f:
            f.write("x = 1\nprint(x)\n")
        assert engine.security_check_sandbox(path) is True

    def test_security_check_dangerous_code(self):
        engine = SelfEngineeringEngine()
        req = EngineeringRequest(
            request_id="sb-danger",
            description="dangerous code",
            target_files=[],
            improvement_type="refactor",
            risk_level=HealingSeverity.LOW,
            created_at=time.time(),
        )
        path = engine.create_sandbox(req)
        danger_file = os.path.join(path, "bad.py")
        with open(danger_file, "w") as f:
            f.write("eval('malicious')\n")
        assert engine.security_check_sandbox(path) is False

    def test_engineering_result_has_fields(self):
        res = EngineeringResult(
            request_id="r1",
            status=EngineeringStatus.REJECTED,
            sandbox_path=None,
            files_changed=[],
            tests_passed=0,
            tests_failed=1,
            benchmark_before=None,
            benchmark_after=None,
            security_passed=False,
            regression_passed=False,
            rollback_point=None,
            timestamp=time.time(),
        )
        assert hasattr(res, "request_id")
        assert hasattr(res, "status")
        assert hasattr(res, "tests_passed")

    def test_engineering_status_enum(self):
        assert EngineeringStatus.PROMOTED.value == "promoted"
        assert EngineeringStatus.REJECTED.value == "rejected"
        assert EngineeringStatus.ROLLED_BACK.value == "rolled_back"


class TestPatch:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_patch_risk_values(self):
        values = [r.value for r in PatchRisk]
        assert len(values) == 4
        assert "low" in values
        assert "medium" in values
        assert "high" in values
        assert "critical" in values

    def test_impact_area_values(self):
        values = [a.value for a in ImpactArea]
        assert len(values) == 10
        assert "core" in values
        assert "brain" in values
        assert "memory" in values
        assert "trading" in values
        assert "vision" in values
        assert "voice" in values
        assert "tools" in values
        assert "ui" in values
        assert "security" in values
        assert "performance" in values

    def test_patch_record_creation(self):
        pr = PatchRecord(
            patch_id="p-001",
            reason="optimise query",
            files_changed=["brain.py"],
            risk=PatchRisk.MEDIUM,
            tests_added=["test_brain.py"],
            benchmark_result=None,
            status="proposed",
            rollback_point="abc123",
            created_at=time.time(),
            impact_areas=[ImpactArea.BRAIN],
        )
        assert pr.patch_id == "p-001"
        assert pr.risk == PatchRisk.MEDIUM
        assert ImpactArea.BRAIN in pr.impact_areas

    def test_patch_generator_singleton(self):
        a = PatchGenerator()
        b = PatchGenerator()
        assert a is b

    def test_analyze_impact(self):
        gen = PatchGenerator()
        areas = gen.analyze_impact(["desktop_agent/brain/brain.py"])
        assert isinstance(areas, list)
        assert ImpactArea.BRAIN in areas

    def test_scan_security_issues_code(self):
        gen = PatchGenerator()
        issues = gen._scan_for_security_issues("eval('x')")
        assert isinstance(issues, list)
        assert len(issues) > 0

    def test_scan_clean_code(self):
        gen = PatchGenerator()
        issues = gen._scan_for_security_issues("x = 1\nreturn x")
        assert isinstance(issues, list)
        assert len(issues) == 0

    def test_patch_record_has_fields(self):
        pr = PatchRecord(
            patch_id="p-002",
            reason="fix bug",
            files_changed=[],
            risk=PatchRisk.LOW,
            tests_added=[],
            benchmark_result=None,
            status="applied",
            rollback_point="def456",
            created_at=time.time(),
            impact_areas=[],
        )
        assert hasattr(pr, "patch_id")
        assert hasattr(pr, "risk")
        assert hasattr(pr, "rollback_point")


class TestRegression:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_regression_status_values(self):
        values = [s.value for s in RegressionStatus]
        assert len(values) == 5
        assert "no_regression" in values
        assert "minor_regression" in values
        assert "major_regression" in values
        assert "behavior_change" in values
        assert "unknown" in values

    def test_before_after_creation(self):
        ba = BeforeAfter(
            metric_name="latency",
            before_value=100.0,
            after_value=120.0,
            unit="ms",
            change_pct=20.0,
            status=RegressionStatus.MINOR_REGRESSION,
        )
        assert ba.metric_name == "latency"
        assert ba.before_value == 100.0
        assert ba.after_value == 120.0
        assert ba.status == RegressionStatus.MINOR_REGRESSION

    def test_behavioral_diff_creation(self):
        bd = BehavioralDiff(
            goal="open notepad",
            old_behavior="opened notepad",
            new_behavior="opened notepad successfully",
            identical=False,
            latency_change_ms=5.0,
            regression_status=RegressionStatus.MINOR_REGRESSION,
        )
        assert bd.goal == "open notepad"
        assert bd.identical is False
        assert bd.latency_change_ms == 5.0

    def test_analyzer_singleton(self):
        a = RegressionAnalyzer()
        b = RegressionAnalyzer()
        assert a is b

    def test_compare_results(self):
        analyzer = RegressionAnalyzer()
        results = analyzer.compare_results({"latency": 100.0}, {"latency": 120.0})
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].metric_name == "latency"
        assert results[0].before_value == 100.0
        assert results[0].after_value == 120.0
        assert isinstance(results[0], BeforeAfter)

    def test_detect_no_regression(self):
        analyzer = RegressionAnalyzer()
        results = analyzer.compare_results({"latency": 100.0}, {"latency": 100.0})
        worst = analyzer.detect_regression(results)
        assert worst == RegressionStatus.NO_REGRESSION

    def test_detect_major_regression(self):
        analyzer = RegressionAnalyzer()
        results = analyzer.compare_results({"latency": 100.0}, {"latency": 200.0})
        worst = analyzer.detect_regression(results)
        assert worst == RegressionStatus.MAJOR_REGRESSION

    def test_check_test_results(self):
        analyzer = RegressionAnalyzer()
        ok, reason = analyzer.check_test_results(10, 0, 10, 0)
        assert ok is True
        assert "no regression" in reason.lower() or "stable" in reason.lower()


class TestOptimization:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_optimization_category_values(self):
        values = [c.value for c in OptimizationCategory]
        assert len(values) == 10
        assert "slow_model" in values
        assert "slow_tool" in values
        assert "excessive_context" in values
        assert "repeated_work" in values
        assert "cache_miss" in values
        assert "serialization" in values
        assert "blocking_io" in values
        assert "unnecessary_llm" in values
        assert "bad_concurrency" in values
        assert "memory_pressure" in values

    def test_optimization_proposal_creation(self):
        prop = OptimizationProposal(
            proposal_id="opt-1",
            category=OptimizationCategory.SLOW_MODEL,
            component="gemini",
            description="model is slow",
            estimated_impact="high",
            estimated_risk="medium",
            evidence=[{"latency": 5000}],
        )
        assert prop.proposal_id == "opt-1"
        assert prop.category == OptimizationCategory.SLOW_MODEL
        assert prop.estimated_impact == "high"

    def test_optimizer_singleton(self):
        a = PerformanceOptimizer()
        b = PerformanceOptimizer()
        assert a is b

    def test_analyze_bottlenecks(self):
        optimizer = PerformanceOptimizer()
        telemetry = {
            "slow_models": [{"model": "gemini-flash", "latency_ms": 8000}],
            "slow_tools": [{"tool": "screenshot", "latency_ms": 3000}],
            "context_tokens": 10000,
            "cache_misses": 15,
            "blocking_io_count": 7,
            "unnecessary_llm_calls": 5,
            "memory_mb": 600,
            "concurrency_issues": 3,
            "serialization_ms": 150,
        }
        proposals = optimizer.analyze_bottlenecks(telemetry)
        assert isinstance(proposals, list)
        assert len(proposals) >= 3
        for p in proposals:
            assert isinstance(p, OptimizationProposal)
            assert len(p.proposal_id) > 0

    def test_prioritize(self):
        optimizer = PerformanceOptimizer()
        low = OptimizationProposal(
            proposal_id="l", category=OptimizationCategory.CACHE_MISS,
            component="cache", description="", estimated_impact="low",
            estimated_risk="low", evidence=[],
        )
        high = OptimizationProposal(
            proposal_id="h", category=OptimizationCategory.SLOW_MODEL,
            component="model", description="", estimated_impact="high",
            estimated_risk="low", evidence=[],
        )
        sorted_props = optimizer.prioritize([low, high])
        assert sorted_props[0].estimated_impact == "high"
        assert sorted_props[1].estimated_impact == "low"

    def test_optimization_history(self):
        optimizer = PerformanceOptimizer()
        prop = optimizer.propose_optimization(
            component="runtime",
            category=OptimizationCategory.MEMORY_PRESSURE,
            evidence=[{"memory_mb": 1024}],
        )
        optimizer.record_optimization(prop, "applied")
        history = optimizer.get_optimization_history()
        assert len(history) == 1
        assert history[0]["result"] == "applied"
        assert history[0]["proposal_id"] == prop.proposal_id


class TestReflection:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_task_outcome_values(self):
        values = [o.value for o in TaskOutcome]
        assert len(values) == 6
        assert "success" in values
        assert "partial_success" in values
        assert "failure" in values
        assert "timeout" in values
        assert "rolled_back" in values
        assert "unknown" in values

    def test_reflection_record_creation(self):
        rr = ReflectionRecord(
            task_id="t-1",
            goal="open browser",
            outcome=TaskOutcome.SUCCESS,
            efficiency_score=0.9,
            verification_confirmed=True,
            unnecessary_steps=[],
            reasoning_quality="correct",
            lessons=["good pattern"],
            timestamp=time.time(),
        )
        assert rr.task_id == "t-1"
        assert rr.outcome == TaskOutcome.SUCCESS
        assert rr.efficiency_score == 0.9
        assert rr.reasoning_quality == "correct"

    def test_outcome_record_creation(self):
        or_ = OutcomeRecord(
            goal="search web",
            action="searchWeb",
            outcome="success",
            quality=0.85,
            lesson="use specific queries",
            timestamp=time.time(),
        )
        assert or_.goal == "search web"
        assert or_.quality == 0.85
        assert or_.lesson == "use specific queries"

    def test_reflection_engine_singleton(self):
        a = SelfReflectionEngine()
        b = SelfReflectionEngine()
        assert a is b

    def test_reflect_on_task(self):
        engine = SelfReflectionEngine()
        record = engine.reflect(
            task_id="t-2",
            goal="create file",
            steps_taken=["createFile"],
            result={"status": "success", "expected_steps": 1},
            verified=True,
        )
        assert isinstance(record, ReflectionRecord)
        assert record.outcome == TaskOutcome.SUCCESS
        assert record.efficiency_score >= 0.0
        assert record.efficiency_score <= 1.0
        assert record.verification_confirmed is True

    def test_record_outcome(self):
        engine = SelfReflectionEngine()
        rec = engine.record_outcome(
            goal="open app",
            action="openApplication",
            outcome="success",
            quality=0.9,
            lesson="use full path",
        )
        outcomes = engine.get_outcomes(limit=10)
        assert len(outcomes) >= 1
        assert outcomes[-1].goal == "open app"
        assert outcomes[-1].lesson == "use full path"

    def test_get_lessons_for_domain(self):
        engine = SelfReflectionEngine()
        engine.record_outcome("browse site", "openWebsite", "success", 0.9, "handle redirects for web")
        engine.record_outcome("read file", "readFile", "success", 0.8, "check file size first")
        lessons = engine.get_lessons_for_domain("web")
        assert len(lessons) >= 1
        assert any("web" in l.lower() for l in lessons)

    def test_efficiency_score_range(self):
        engine = SelfReflectionEngine()
        record = engine.reflect(
            task_id="t-3",
            goal="test goal",
            steps_taken=["s1", "s2"],
            result={"status": "success", "expected_steps": 2},
            verified=True,
        )
        assert 0.0 <= record.efficiency_score <= 1.0


class TestWorkflow:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_workflow_step_creation(self):
        ws = WorkflowStep(name="search", duration_ms=150.0, success=True, tool_used="searchWeb")
        assert ws.name == "search"
        assert ws.duration_ms == 150.0
        assert ws.success is True
        assert ws.tool_used == "searchWeb"

    def test_workflow_record_creation(self):
        steps = [
            WorkflowStep("search", 100.0, True),
            WorkflowStep("summarize", 50.0, True),
        ]
        wr = WorkflowRecord(
            workflow_id="wf-1",
            name="research_task",
            steps=steps,
            total_duration_ms=150.0,
            success=True,
            llm_calls=2,
            search_calls=1,
            repeated_steps=[],
            timestamp=time.time(),
        )
        assert wr.workflow_id == "wf-1"
        assert wr.total_duration_ms == 150.0
        assert wr.llm_calls == 2
        assert wr.success is True

    def test_workflow_optimizer_singleton(self):
        a = WorkflowOptimizer()
        b = WorkflowOptimizer()
        assert a is b

    def test_record_workflow(self):
        optimizer = WorkflowOptimizer()
        steps = [
            WorkflowStep("init", 10.0, True),
            WorkflowStep("process", 30.0, True),
            WorkflowStep("done", 5.0, True),
        ]
        rec = optimizer.record_workflow("my_flow", steps, llm_calls=1, search_calls=0)
        assert isinstance(rec, WorkflowRecord)
        assert rec.name == "my_flow"
        assert rec.total_duration_ms == 45.0
        assert rec.success is True

    def test_analyze_patterns(self):
        optimizer = WorkflowOptimizer()
        steps1 = [WorkflowStep("fetch", 50.0, True), WorkflowStep("process", 30.0, True)]
        steps2 = [WorkflowStep("fetch", 60.0, True), WorkflowStep("process", 35.0, True)]
        steps3 = [WorkflowStep("fetch", 55.0, True), WorkflowStep("process", 32.0, True)]
        optimizer.record_workflow("analyze", steps1, 1, 0)
        optimizer.record_workflow("analyze", steps2, 1, 0)
        optimizer.record_workflow("analyze", steps3, 1, 0)
        patterns = optimizer.analyze_patterns("analyze")
        assert "total_runs" in patterns
        assert patterns["total_runs"] == 3
        assert "success_rate" in patterns
        assert "avg_duration_ms" in patterns

    def test_workflow_stats(self):
        optimizer = WorkflowOptimizer()
        steps = [WorkflowStep("a", 10.0, True), WorkflowStep("b", 20.0, True)]
        optimizer.record_workflow("flow_x", steps, 2, 1)
        optimizer.record_workflow("flow_x", steps, 2, 1)
        stats = optimizer.get_workflow_stats()
        assert isinstance(stats, dict)
        assert "flow_x" in stats
        assert stats["flow_x"]["total_runs"] == 2
        assert stats["flow_x"]["success_rate"] == 1.0


class TestModelImprovement:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_model_version_creation(self):
        mv = ModelVersion(
            model_id="m1",
            version="v1.0",
            benchmark_scores={"acc": 0.9},
            accuracy=0.9,
            latency_ms=100.0,
            resource_usage={"mem": 512},
            failure_rate=0.01,
            domains=["nlp"],
            validated_at=time.time(),
            status="candidate",
        )
        assert mv.model_id == "m1"
        assert mv.version == "v1.0"
        assert mv.accuracy == 0.9
        assert mv.status == "candidate"

    def test_capability_gap_creation(self):
        cg = CapabilityGap(
            capability="timeout_handling",
            description="Repeated timeout failures",
            evidence=[{"task": "fetch"}],
            severity="high",
            suggested_fix="Increase timeout",
            timestamp=time.time(),
        )
        assert cg.capability == "timeout_handling"
        assert cg.severity == "high"
        assert len(cg.evidence) == 1

    def test_model_version_manager_singleton(self):
        a = ModelVersionManager()
        b = ModelVersionManager()
        assert a is b

    def test_register_and_get_version(self):
        mgr = ModelVersionManager()
        mv = mgr.register_version("m1", "v1.0", {"accuracy": 0.9})
        assert mv.model_id == "m1"
        assert mv.version == "v1.0"
        retrieved = mgr.get_version("m1", "v1.0")
        assert retrieved is mv

    def test_promote_version(self):
        mgr = ModelVersionManager()
        v1 = mgr.register_version("m1", "v1.0", {"accuracy": 0.8})
        v2 = mgr.register_version("m1", "v2.0", {"accuracy": 0.9})
        mgr.promote_version("m1", "v1.0")
        assert v1.status == "active"
        assert mgr.promote_version("m1", "v2.0") is True
        assert v2.status == "active"
        assert v1.status == "retired"

    def test_compare_versions(self):
        mgr = ModelVersionManager()
        mgr.register_version("m1", "v1.0", {"accuracy": 0.8, "latency_ms": 100})
        mgr.register_version("m1", "v2.0", {"accuracy": 0.9, "latency_ms": 80})
        result = mgr.compare_versions("m1", "v1.0", "v2.0")
        assert isinstance(result, dict)
        assert "accuracy_delta" in result
        assert result["accuracy_delta"] == 0.1

    def test_gap_detector_singleton(self):
        a = CapabilityGapDetector()
        b = CapabilityGapDetector()
        assert a is b

    def test_detect_gaps(self):
        detector = CapabilityGapDetector()
        failures = [
            {"success": False, "error": "timeout occurred", "task": "fetch"},
            {"success": False, "error": "timeout occurred", "task": "fetch2"},
        ]
        gaps = detector.detect_gaps(failures)
        assert isinstance(gaps, list)
        assert len(gaps) >= 1
        assert all(isinstance(g, CapabilityGap) for g in gaps)


class TestDeployment:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_deployment_stage_values(self):
        values = [s.value for s in DeploymentStage]
        assert len(values) == 4
        assert "stable" in values
        assert "candidate" in values
        assert "canary" in values
        assert "retired" in values

    def test_deployment_record_creation(self):
        record = DeploymentRecord(
            deployment_id="dep-1",
            version="v1.0",
            stage=DeploymentStage.CANDIDATE,
            started_at=time.time(),
            metrics={"cpu": 50},
            health_status="pending",
            rollback_count=0,
            max_rollbacks=3,
            code_path="/tmp/v1",
            canary_metrics=[],
        )
        assert record.deployment_id == "dep-1"
        assert record.version == "v1.0"
        assert record.stage == DeploymentStage.CANDIDATE
        assert record.code_path == "/tmp/v1"

    def test_canary_metrics_creation(self):
        cm = CanaryMetrics(
            error_rate=0.01,
            latency_p50=50.0,
            latency_p99=200.0,
            success_rate=0.99,
            memory_mb=256.0,
            sample_count=1000,
        )
        assert cm.error_rate == 0.01
        assert cm.success_rate == 0.99
        assert cm.sample_count == 1000

    def test_deployment_manager_singleton(self):
        a = DeploymentManager()
        b = DeploymentManager()
        assert a is b

    def test_create_candidate(self):
        mgr = DeploymentManager()
        record = mgr.create_candidate("v1", "/tmp")
        assert record.version == "v1"
        assert record.stage == DeploymentStage.CANDIDATE
        assert record.code_path == "/tmp"

    def test_promote_to_canary(self):
        mgr = DeploymentManager()
        record = mgr.create_candidate("v1", "/tmp")
        assert mgr.promote_to_canary(record.deployment_id) is True
        assert record.stage == DeploymentStage.CANARY

    def test_should_rollback_high_error(self):
        mgr = DeploymentManager()
        record = mgr.create_candidate("v1", "/tmp")
        mgr.promote_to_canary(record.deployment_id)
        cm = CanaryMetrics(
            error_rate=0.1,
            latency_p50=50.0,
            latency_p99=200.0,
            success_rate=0.99,
            memory_mb=256.0,
            sample_count=100,
        )
        mgr.record_canary_metrics(record.deployment_id, cm)
        should_rb, _ = mgr.should_rollback(record.deployment_id)
        assert should_rb is True

    def test_should_not_rollback_healthy(self):
        mgr = DeploymentManager()
        record = mgr.create_candidate("v1", "/tmp")
        mgr.promote_to_canary(record.deployment_id)
        cm = CanaryMetrics(
            error_rate=0.01,
            latency_p50=50.0,
            latency_p99=100.0,
            success_rate=0.99,
            memory_mb=256.0,
            sample_count=100,
        )
        mgr.record_canary_metrics(record.deployment_id, cm)
        should_rb, _ = mgr.should_rollback(record.deployment_id)
        assert should_rb is False


class TestVersioning:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_myraaversion_creation(self):
        mv = MYRAAVersion(
            version_id="v1",
            git_commit="abc123",
            created_at=time.time(),
            description="First version",
            phase="brain_development",
            test_results={"passed": 10},
            files_changed=["a.py", "b.py"],
            rollback_available=False,
        )
        assert mv.version_id == "v1"
        assert mv.git_commit == "abc123"
        assert mv.phase == "brain_development"
        assert len(mv.files_changed) == 2

    def test_version_manager_singleton(self):
        a = VersionManager()
        b = VersionManager()
        assert a is b

    def test_create_checkpoint(self):
        mgr = VersionManager()
        cp = mgr.create_checkpoint("cp1", "Initial checkpoint")
        assert cp.version_id == "cp1"
        assert cp.description == "Initial checkpoint"
        retrieved = mgr.get_checkpoint("cp1")
        assert retrieved is cp

    def test_list_checkpoints(self):
        mgr = VersionManager()
        mgr.create_checkpoint("cp1", "First")
        mgr.create_checkpoint("cp2", "Second")
        mgr.create_checkpoint("cp3", "Third")
        checkpoints = mgr.list_checkpoints()
        assert len(checkpoints) == 3

    def test_mark_rollback_available(self):
        mgr = VersionManager()
        mgr.create_checkpoint("cp1", "First")
        mgr.mark_rollback_available("cp1")
        assert mgr.can_rollback("cp1") is True

    def test_record_test_results(self):
        mgr = VersionManager()
        mgr.create_checkpoint("cp1", "First")
        mgr.record_test_results("cp1", {"passed": 10, "failed": 0})
        cp = mgr.get_checkpoint("cp1")
        assert cp.test_results["passed"] == 10
        assert cp.test_results["failed"] == 0


class TestSecurity:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_protected_area_values(self):
        values = [a.value for a in ProtectedArea]
        assert len(values) == 8
        assert "broker_trading" in values
        assert "secret_storage" in values

    def test_security_violation_creation(self):
        sv = SecurityViolation(
            area=ProtectedArea.SECRET_STORAGE,
            description="Secret detected",
            proposed_action="introduce_secret",
            blocked=True,
            timestamp=time.time(),
        )
        assert sv.area == ProtectedArea.SECRET_STORAGE
        assert sv.blocked is True

    def test_security_gate_singleton(self):
        a = SecurityGate()
        b = SecurityGate()
        assert a is b

    def test_scan_code_clean(self):
        gate = SecurityGate()
        secrets = gate.scan_code_for_secrets("x = 1\nreturn x")
        dangerous = gate.scan_code_for_dangerous_patterns("x = 1\nreturn x")
        assert len(secrets) == 0
        assert len(dangerous) == 0

    def test_scan_code_dangerous(self):
        gate = SecurityGate()
        dangerous = gate.scan_code_for_dangerous_patterns("eval('bad')")
        assert len(dangerous) > 0

    def test_scan_code_secrets(self):
        gate = SecurityGate()
        secrets = gate.scan_code_for_secrets("GEMINI_API_KEY = 'sk-123'")
        assert len(secrets) > 0


class TestGuards:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_resource_limits_creation(self):
        rl = ResourceLimits()
        assert rl.max_cpu_pct == 80.0
        assert rl.max_memory_mb == 2048.0
        assert rl.max_threads == 20

    def test_loop_guard_config_creation(self):
        config = LoopGuardConfig()
        assert config.max_repair_attempts == 5
        assert config.same_failure_threshold == 3

    def test_resource_guard_singleton(self):
        a = ResourceGuard()
        b = ResourceGuard()
        assert a is b

    def test_loop_guard_singleton(self):
        a = LoopProtectionGuard()
        b = LoopProtectionGuard()
        assert a is b

    def test_loop_guard_can_attempt(self):
        guard = LoopProtectionGuard()
        assert guard.can_attempt_repair() is True

    def test_loop_guard_max_attempts(self):
        guard = LoopProtectionGuard()
        for _ in range(5):
            guard.record_repair_attempt()
        assert guard.can_attempt_repair() is False

    def test_loop_guard_same_failure(self):
        guard = LoopProtectionGuard()
        guard.record_repair_attempt("fail1")
        guard.record_repair_attempt("fail1")
        guard.record_repair_attempt("fail1")
        assert guard.is_loop_detected() is True

    def test_loop_guard_reset(self):
        guard = LoopProtectionGuard()
        guard.record_repair_attempt("fail1")
        guard.record_repair_attempt("fail1")
        guard.record_repair_attempt("fail1")
        assert guard.is_loop_detected() is True
        guard.reset()
        assert guard.can_attempt_repair() is True
        assert guard.is_loop_detected() is False


class TestEscalation:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_escalation_reason_values(self):
        values = [r.value for r in EscalationReason]
        assert len(values) == 11

    def test_escalation_request_creation(self):
        req = EscalationRequest(
            request_id="req1",
            reason=EscalationReason.HIGH_UNCERTAINTY,
            component="voice",
            description="Low confidence",
            evidence=[{"key": "val"}],
            options=["retry", "skip"],
            recommended_option="retry",
            timestamp=time.time(),
            resolved=False,
            resolution=None,
        )
        assert req.request_id == "req1"
        assert req.reason == EscalationReason.HIGH_UNCERTAINTY
        assert req.resolved is False

    def test_human_escalation_singleton(self):
        a = HumanEscalation()
        b = HumanEscalation()
        assert a is b

    def test_escalate(self):
        he = HumanEscalation()
        req = he.escalate(
            reason=EscalationReason.HIGH_UNCERTAINTY,
            component="test",
            description="Test escalation",
        )
        assert isinstance(req, EscalationRequest)
        assert req.reason == EscalationReason.HIGH_UNCERTAINTY

    def test_resolve(self):
        he = HumanEscalation()
        req = he.escalate(
            reason=EscalationReason.HIGH_UNCERTAINTY,
            component="test",
            description="Test escalation",
        )
        assert he.resolve(req.request_id, "resolved") is True
        assert req.resolved is True

    def test_should_escalate_low_confidence(self):
        he = HumanEscalation()
        assert he.should_escalate(EscalationReason.HIGH_UNCERTAINTY, 0.3) is True


class TestTelemetry:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_healing_event_creation(self):
        ev = HealingEvent(
            event_id="ev1",
            event_type="healing_completed",
            component="voice",
            details={"ok": True},
            timestamp=time.time(),
            severity="info",
        )
        assert ev.event_id == "ev1"
        assert ev.event_type == "healing_completed"
        assert ev.severity == "info"

    def test_system_health_snapshot_creation(self):
        snap = SystemHealthSnapshot(
            timestamp=time.time(),
            overall_status="healthy",
            subsystems={"voice": {"status": "ok"}},
            active_incidents=0,
            healing_in_progress=0,
            last_heal_time=None,
            total_heals_today=5,
            success_rate_today=0.8,
        )
        assert snap.overall_status == "healthy"
        assert snap.total_heals_today == 5

    def test_self_healing_telemetry_singleton(self):
        a = SelfHealingTelemetry()
        b = SelfHealingTelemetry()
        assert a is b

    def test_record_event(self):
        tel = SelfHealingTelemetry()
        ev = tel.record_event(
            event_type="healing_completed",
            component="voice",
            details={"ok": True},
            severity="info",
        )
        assert isinstance(ev, HealingEvent)
        events = tel.get_events()
        assert ev in events

    def test_get_events_filtered(self):
        tel = SelfHealingTelemetry()
        tel.record_event("healing_completed", "voice", {"ok": True}, "info")
        tel.record_event("healing_failed", "voice", {"ok": False}, "error")
        tel.record_event("healing_completed", "voice", {"ok": True}, "info")
        completed = tel.get_events(event_type="healing_completed")
        assert all(e.event_type == "healing_completed" for e in completed)
        assert len(completed) == 2

    def test_healing_stats(self):
        tel = SelfHealingTelemetry()
        tel.record_event("healing_completed", "voice", {"ok": True}, "info")
        tel.record_event("healing_failed", "voice", {"ok": False}, "error")
        stats = tel.get_healing_stats()
        assert isinstance(stats, dict)
        assert "total_events" in stats
        assert "by_type" in stats


class TestManager:
    def setup_method(self):
        DiagnosticsEngine.reset_instance()
        RootCauseAnalyzer.reset_instance()
        HealingEngine.reset_instance()
        SelfEngineeringEngine.reset_instance()
        PatchGenerator.reset_instance()
        RegressionAnalyzer.reset_instance()
        PerformanceOptimizer.reset_instance()
        SelfReflectionEngine.reset_instance()
        WorkflowOptimizer.reset_instance()
        ModelVersionManager.reset_instance()
        CapabilityGapDetector.reset_instance()
        DeploymentManager.reset_instance()
        VersionManager.reset_instance()
        SecurityGate.reset_instance()
        ResourceGuard.reset_instance()
        LoopProtectionGuard.reset_instance()
        HumanEscalation.reset_instance()
        SelfHealingTelemetry.reset_instance()
        SelfHealingManager.reset_instance()

    def test_self_healing_manager_singleton(self):
        a = SelfHealingManager()
        b = SelfHealingManager()
        assert a is b

    def test_check_health(self):
        mgr = SelfHealingManager()
        result = mgr.check_health()
        assert isinstance(result, dict)
        assert "overall_status" in result

    def test_diagnose_issue(self):
        mgr = SelfHealingManager()
        result = mgr.diagnose_issue("test")
        assert isinstance(result, dict)
        assert "component" in result
        assert result["component"] == "test"

    def test_get_system_status(self):
        mgr = SelfHealingManager()
        result = mgr.get_system_status()
        assert isinstance(result, dict)
        assert "health" in result

    def test_get_full_report(self):
        mgr = SelfHealingManager()
        result = mgr.get_full_report()
        assert isinstance(result, dict)
        assert "system_status" in result

    def test_manager_records_telemetry(self):
        mgr = SelfHealingManager()
        mgr.check_health()
        events = mgr.telemetry.get_events()
        assert len(events) > 0
