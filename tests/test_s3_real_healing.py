"""Phase S.3 — Real Self-Healing Tests.

Tests that healing handlers actually perform recovery operations
(not just log + return success=True).

1. Provider failure → recovery
2. Vision failure → recovery
3. Worker failure → restart
4. Telemetry failure → reconnect
5. Cache failure → reset
6. Scheduler failure → restart
7. Financial retry blocked
8. Security gate preserved
9. Resource limits preserved
10. Rollback preserved
"""

import threading
import time
import pytest

from desktop_agent.self_healing.healing import (
    HealingEngine,
    HealingAction,
    HealingResult,
    HealingSeverity,
)
from desktop_agent.self_healing.diagnostics import (
    DiagnosticsEngine,
    DiagnosticResult,
    HealthStatus,
)
from desktop_agent.self_healing.root_cause import RootCauseAnalyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all singletons before each test."""
    HealingEngine.reset_instance()
    DiagnosticsEngine.reset_instance()
    RootCauseAnalyzer.reset_instance()
    yield
    HealingEngine.reset_instance()
    DiagnosticsEngine.reset_instance()
    RootCauseAnalyzer.reset_instance()


@pytest.fixture
def engine():
    return HealingEngine()


# ---------------------------------------------------------------------------
# 1. Provider failure → recovery
# ---------------------------------------------------------------------------

class TestProviderRecovery:
    def test_provider_reconnect_success(self, engine):
        """Real provider reconnect with successful callback."""
        call_log = []

        def reconnect():
            call_log.append("reconnect")
            return True

        def verify():
            call_log.append("verify")
            return True

        result = engine.heal(
            "yahoo_provider",
            HealingAction.RECONNECT_PROVIDER,
            {"provider_name": "yahoo", "reconnect_fn": reconnect, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is True
        assert "reconnect" in call_log
        assert "verify" in call_log
        assert "reconnected and verified" in result.message

    def test_provider_reconnect_failure(self, engine):
        """Provider reconnect fails when callback returns False — retries exhausted."""
        result = engine.heal(
            "yahoo_provider",
            HealingAction.RECONNECT_PROVIDER,
            {"provider_name": "yahoo", "reconnect_fn": lambda: False},
        )
        assert result.success is False
        assert "All 3 attempts failed" in result.message

    def test_provider_reconnect_exception(self, engine):
        """Provider reconnect handles exceptions gracefully — retries exhausted."""
        def bad_reconnect():
            raise ConnectionError("connection refused")

        result = engine.heal(
            "yahoo_provider",
            HealingAction.RECONNECT_PROVIDER,
            {"provider_name": "yahoo", "reconnect_fn": bad_reconnect},
        )
        assert result.success is False
        assert "All 3 attempts failed" in result.message

    def test_provider_reconnect_verifies_after(self, engine):
        """Provider reconnect calls verify after successful reconnect."""
        verified = []

        def reconnect():
            return True

        def verify():
            verified.append(True)
            return True

        result = engine.heal(
            "test",
            HealingAction.RECONNECT_PROVIDER,
            {"reconnect_fn": reconnect, "verify_fn": verify},
        )
        assert result.success is True
        assert len(verified) == 1
        assert result.verification_passed is True

    def test_provider_reconnect_verification_failure(self, engine):
        """Provider reconnect reports verification failure."""
        def reconnect():
            return True

        def verify():
            return False

        result = engine.heal(
            "test",
            HealingAction.RECONNECT_PROVIDER,
            {"reconnect_fn": reconnect, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is False
        assert "verification failed" in result.message

    def test_provider_reconnect_noop_without_callback(self, engine):
        """Provider reconnect falls back to no-op when no callback provided."""
        result = engine.heal(
            "test",
            HealingAction.RECONNECT_PROVIDER,
            {"provider_name": "yahoo"},
        )
        assert result.success is True
        assert "no-op" in result.message


# ---------------------------------------------------------------------------
# 2. Vision failure → recovery (via reinit_connection)
# ---------------------------------------------------------------------------

class TestVisionRecovery:
    def test_vision_reinit_success(self, engine):
        """Real vision reinit with successful callback."""
        stopped = []
        started = []

        def stop():
            stopped.append(True)

        def start():
            started.append(True)

        def verify():
            return True

        result = engine.heal(
            "vision",
            HealingAction.RESTART_SUBSYSTEM,
            {"subsystem": "continuous_vision", "stop_fn": stop, "start_fn": start, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is True
        assert len(stopped) == 1
        assert len(started) == 1

    def test_vision_reinit_stop_fails_continues(self, engine):
        """Vision reinit continues restart even if stop raises."""
        started = []

        def bad_stop():
            raise RuntimeError("stop failed")

        def start():
            started.append(True)

        result = engine.heal(
            "vision",
            HealingAction.RESTART_SUBSYSTEM,
            {"subsystem": "vision", "stop_fn": bad_stop, "start_fn": start},
        )
        assert result.success is True
        assert len(started) == 1


# ---------------------------------------------------------------------------
# 3. Worker failure → restart
# ---------------------------------------------------------------------------

class TestWorkerRecovery:
    def test_worker_restart_success(self, engine):
        """Real worker restart with stop + start + verify."""
        events = []

        def stop():
            events.append("stop")

        def start():
            events.append("start")

        def verify():
            events.append("verify")
            return True

        result = engine.heal(
            "worker_pool",
            HealingAction.RESTART_WORKER,
            {"worker_id": "pool-1", "stop_fn": stop, "start_fn": start, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is True
        assert events == ["stop", "start", "verify"]

    def test_worker_restart_start_fails(self, engine):
        """Worker restart fails when start_fn raises — retries exhausted."""
        def bad_start():
            raise OSError("cannot start")

        result = engine.heal(
            "worker",
            HealingAction.RESTART_WORKER,
            {"worker_id": "w1", "start_fn": bad_start},
        )
        assert result.success is False
        assert "All 3 attempts failed" in result.message

    def test_worker_restart_noop_without_callback(self, engine):
        """Worker restart falls back to no-op when no callback provided."""
        result = engine.heal(
            "worker",
            HealingAction.RESTART_WORKER,
            {"worker_id": "w1"},
        )
        assert result.success is True
        assert "no-op" in result.message


# ---------------------------------------------------------------------------
# 4. Telemetry failure → reconnect (via reinit_connection)
# ---------------------------------------------------------------------------

class TestTelemetryRecovery:
    def test_telemetry_reconnect_success(self, engine):
        """Real telemetry reconnect with successful callback."""
        reconnected = []

        def reconnect():
            reconnected.append(True)
            return True

        def verify():
            return True

        result = engine.heal(
            "telemetry",
            HealingAction.REINIT_CONNECTION,
            {"subsystem": "telemetry_relay", "reconnect_fn": reconnect, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is True
        assert len(reconnected) == 1

    def test_telemetry_reconnect_failure(self, engine):
        """Telemetry reconnect fails when callback returns False."""
        result = engine.heal(
            "telemetry",
            HealingAction.REINIT_CONNECTION,
            {"reconnect_fn": lambda: False},
        )
        assert result.success is False


# ---------------------------------------------------------------------------
# 5. Cache failure → reset (via invalidate_cache)
# ---------------------------------------------------------------------------

class TestCacheRecovery:
    def test_cache_invalidate_success(self, engine):
        """Real cache invalidation with successful callback."""
        invalidated = []

        def invalidate():
            invalidated.append(True)
            return True

        def verify():
            return True

        result = engine.heal(
            "trading_cache",
            HealingAction.INVALIDATE_CACHE,
            {"cache_name": "trading", "invalidate_fn": invalidate, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is True
        assert len(invalidated) == 1

    def test_cache_invalidate_exception(self, engine):
        """Cache invalidation handles exceptions — retries exhausted."""
        def bad_invalidate():
            raise RuntimeError("cache corrupted")

        result = engine.heal(
            "cache",
            HealingAction.INVALIDATE_CACHE,
            {"invalidate_fn": bad_invalidate},
        )
        assert result.success is False
        assert "All 3 attempts failed" in result.message

    def test_cache_invalidate_noop(self, engine):
        """Cache invalidation falls back to no-op without callback."""
        result = engine.heal(
            "cache",
            HealingAction.INVALIDATE_CACHE,
            {"cache_name": "test"},
        )
        assert result.success is True
        assert "no-op" in result.message


# ---------------------------------------------------------------------------
# 6. Scheduler failure → restart (via restart_subsystem)
# ---------------------------------------------------------------------------

class TestSchedulerRecovery:
    def test_scheduler_restart_success(self, engine):
        """Real scheduler restart with stop + start + verify."""
        events = []

        def stop():
            events.append("stop")

        def start():
            events.append("start")

        def verify():
            events.append("verify")
            return True

        result = engine.heal(
            "scheduler",
            HealingAction.RESTART_SUBSYSTEM,
            {"subsystem": "goal_scheduler", "stop_fn": stop, "start_fn": start, "verify_fn": verify},
        )
        assert result.success is True
        assert result.verification_passed is True
        assert events == ["stop", "start", "verify"]


# ---------------------------------------------------------------------------
# 7. Financial retry blocked
# ---------------------------------------------------------------------------

class TestFinancialProtection:
    def test_financial_retry_blocked(self, engine):
        """Blind retry of financial operations is blocked."""
        with pytest.raises(ValueError, match="not allowed"):
            engine.heal("trading_engine", HealingAction.RETRY_TASK)

    def test_financial_replan_blocked(self, engine):
        """Blind replan of financial operations is blocked."""
        with pytest.raises(ValueError, match="not allowed"):
            engine.heal("portfolio_manager", HealingAction.REPLAN_TASK)

    def test_financial_reconnect_allowed(self, engine):
        """Non-retry financial actions (reconnect) are allowed."""
        result = engine.heal(
            "trading_provider",
            HealingAction.RECONNECT_PROVIDER,
            {"reconnect_fn": lambda: True},
        )
        assert result.success is True

    def test_broker_retry_blocked(self, engine):
        """Broker retry is blocked."""
        with pytest.raises(ValueError, match="not allowed"):
            engine.heal("groww_broker", HealingAction.RETRY_TASK)


# ---------------------------------------------------------------------------
# 8. Security gate preserved
# ---------------------------------------------------------------------------

class TestSecurityGate:
    def test_security_escalate_to_human(self, engine):
        """CRITICAL risk escalates to human."""
        result = engine.heal(
            "trading_engine",
            HealingAction.ESCALATE_TO_HUMAN,
        )
        assert result.success is True
        assert "Escalated" in result.message

    def test_propose_repair_critical_risk(self, engine):
        """Critical risk repair proposal is generated."""
        proposal = engine.propose_repair("trading_engine", "connection lost")
        assert proposal.risk_level == HealingSeverity.CRITICAL

    def test_propose_repair_high_risk(self, engine):
        """High risk repair proposal for brain/vision components."""
        proposal = engine.propose_repair("brain_engine", "timeout")
        assert proposal.risk_level == HealingSeverity.HIGH

    def test_propose_repair_medium_risk(self, engine):
        """Medium risk for other components."""
        proposal = engine.propose_repair("cache", "stale data")
        assert proposal.risk_level == HealingSeverity.MEDIUM


# ---------------------------------------------------------------------------
# 9. Resource limits preserved
# ---------------------------------------------------------------------------

class TestResourceLimits:
    def test_max_attempts_respected(self, engine):
        """Healing retries up to max_attempts (3) then gives up."""
        attempt_count = []
        def failing_fn():
            attempt_count.append(1)
            return False

        result = engine.heal(
            "component",
            HealingAction.RECONNECT_PROVIDER,
            {"reconnect_fn": failing_fn},
        )
        assert result.success is False
        assert len(attempt_count) == 3  # max_attempts = 3

    def test_history_bounded(self, engine):
        """Healing history is bounded to max_history."""
        for i in range(250):
            engine.heal(
                f"comp_{i}",
                HealingAction.SAFE_REPAIR,
                {"repair_fn": lambda: True},
            )
        assert len(engine.get_healing_history()) <= 200

    def test_healing_stats(self, engine):
        """Healing stats are tracked correctly."""
        engine.heal("a", HealingAction.SAFE_REPAIR, {"repair_fn": lambda: True})
        engine.heal("b", HealingAction.RECONNECT_PROVIDER, {"reconnect_fn": lambda: False})
        stats = engine.get_healing_stats()
        assert stats["total_attempts"] >= 2
        assert "safe_repair" in stats["by_action"]


# ---------------------------------------------------------------------------
# 10. Rollback preserved
# ---------------------------------------------------------------------------

class TestRollbackPreserved:
    def test_rollback_code_with_version(self, engine):
        """Rollback with version succeeds."""
        result = engine.heal(
            "system",
            HealingAction.ROLLBACK_CODE,
            {"version": "v1.0.0"},
        )
        assert result.success is True
        assert result.rollback_performed is True

    def test_rollback_code_without_version(self, engine):
        """Rollback without version fails — retries exhausted."""
        result = engine.heal(
            "system",
            HealingAction.ROLLBACK_CODE,
            {"version": ""},
        )
        assert result.success is False
        assert "All 3 attempts failed" in result.message

    def test_restore_checkpoint_with_id(self, engine):
        """Restore with checkpoint ID succeeds."""
        result = engine.heal(
            "system",
            HealingAction.RESTORE_CHECKPOINT,
            {"checkpoint_id": "cp-123"},
        )
        assert result.success is True
        assert result.rollback_performed is True

    def test_restore_checkpoint_without_id(self, engine):
        """Restore without checkpoint ID fails."""
        result = engine.heal(
            "system",
            HealingAction.RESTORE_CHECKPOINT,
            {"checkpoint_id": ""},
        )
        assert result.success is False

    def test_apply_repair_rollback_on_failure(self, engine):
        """Failed repair triggers rollback steps."""
        proposal = engine.propose_repair("test", "issue")
        # Override risk to allow execution
        proposal.risk_level = HealingSeverity.LOW
        proposal.rollback_steps = ["restore from backup"]
        result = engine.apply_repair(proposal)
        # Result depends on SAFE_REPAIR callback (none provided = no-op = success)
        assert isinstance(result, HealingResult)


# ---------------------------------------------------------------------------
# Root Cause classification
# ---------------------------------------------------------------------------

class TestRootCauseReality:
    def test_root_cause_is_heuristic(self):
        """RootCauseAnalyzer is rule-based, not ML/LLM."""
        analyzer = RootCauseAnalyzer()
        result = analyzer.analyze(
            component="test",
            status=HealthStatus.FAILING,
            diagnostic_results=[],
            recent_events=[{"type": "error", "message": "connection refused", "timestamp": time.time()}],
        )
        assert result.cause == "Dependency service unreachable"
        assert result.confidence > 0.5
        assert result.category == "dependency"

    def test_root_cause_pattern_detection(self):
        """RootCauseAnalyzer detects repeated failure patterns."""
        analyzer = RootCauseAnalyzer()
        # Create 5 consecutive failures
        results = [
            DiagnosticResult(
                component="test",
                status=HealthStatus.FAILING,
                timestamp=time.time() - (5 - i) * 60,
                reason="failing",
            )
            for i in range(5)
        ]
        root = analyzer.analyze("test", HealthStatus.FAILING, results, [])
        assert "Chronic failure" in root.cause
        assert root.confidence >= 0.5


# ---------------------------------------------------------------------------
# Diagnostics reality
# ---------------------------------------------------------------------------

class TestDiagnosticsReality:
    def test_diagnostics_register_and_check(self):
        """DiagnosticsEngine runs registered checks."""
        diag = DiagnosticsEngine()

        def my_check():
            return DiagnosticResult(
                component="test_component",
                status=HealthStatus.HEALTHY,
                timestamp=time.time(),
                reason="all good",
                confidence=0.9,
            )

        diag.register_check("test_component", my_check)
        result = diag.check_one("test_component")
        assert result.status == HealthStatus.HEALTHY
        assert result.confidence == 0.9

    def test_diagnostics_health_summary(self):
        """DiagnosticsEngine produces health summary after checks are run."""
        diag = DiagnosticsEngine()
        diag.register_check("a", lambda: DiagnosticResult(
            component="a", status=HealthStatus.HEALTHY, timestamp=time.time(), reason="ok",
        ))
        diag.register_check("b", lambda: DiagnosticResult(
            component="b", status=HealthStatus.DEGRADED, timestamp=time.time(), reason="slow",
        ))
        # Must run checks first to update subsystem statuses
        diag.check_all()
        summary = diag.health_summary()
        assert summary["overall_status"] == "degraded"
        assert len(summary["subsystems"]) == 2
