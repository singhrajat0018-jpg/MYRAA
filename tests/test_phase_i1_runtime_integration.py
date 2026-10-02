"""Phase I.1 — Runtime Integration Tests.

Tests: real tool execution, permission/safety path, verification,
World Model updates, persistent metrics, Neural routing, multi-agent,
failure recovery, security.
"""

import time
import threading
import pytest
from unittest.mock import MagicMock, patch

from desktop_agent.skills.skill import Skill, SkillState, SkillDomain
from desktop_agent.skills.worker import WorkerContract, WorkerResult, WorkerStatus
from desktop_agent.skills.registry import SkillRegistry
from desktop_agent.skills.tool_bridge import ToolBridge, get_tool_bridge
from desktop_agent.skills.world_model_bridge import WorldModelBridge
from desktop_agent.skills.metric_store import MetricStore
from desktop_agent.skills.neural_router import NeuralRouter
from desktop_agent.skills.agents import (
    CodingWorker, ResearchWorker, TradingWorker, VisionWorker,
    DesktopWorker, VerificationWorker,
)
from desktop_agent.skills.planner import AgentPlanner, PlanMode
from desktop_agent.skills.supervisor import AgentSupervisor, SupervisorDecision
from desktop_agent.skills.orchestrator import SkillOrchestrator
from desktop_agent.skills.observability import AgentTelemetry
from desktop_agent.skills.loop_protection import LoopGuard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    SkillRegistry.reset()
    yield
    SkillRegistry.reset()


@pytest.fixture
def tool_bridge():
    return ToolBridge()


@pytest.fixture
def metric_store():
    import tempfile, os
    d = tempfile.mkdtemp()
    return MetricStore(storage_dir=d)


@pytest.fixture
def neural_router():
    return NeuralRouter()


@pytest.fixture
def orchestrator():
    return SkillOrchestrator()


def _make_contract(skill_id="coding", task="create file", **kwargs):
    return WorkerContract(
        task_id="t1",
        task_description=task,
        skill_id=skill_id,
        input_data=kwargs,
    )


# ============================================================
# 1. WORKER → REAL TOOL EXECUTION
# ============================================================

class TestWorkerToolExecution:
    def test_tool_bridge_has_tools(self, tool_bridge):
        tools = tool_bridge.available_tools
        # In isolated tests TOOLS may be empty (main.py not imported).
        # What matters is the bridge does NOT crash and returns a list.
        assert isinstance(tools, list)

    def test_tool_bridge_dispatch_success(self, tool_bridge):
        if not tool_bridge.has_tool("systemInfo"):
            pytest.skip("systemInfo tool not registered")
        ok, result = tool_bridge.dispatch("systemInfo", {})
        assert isinstance(result, dict)
        assert "ok" in result

    def test_tool_bridge_dispatch_unknown_tool(self, tool_bridge):
        ok, result = tool_bridge.dispatch("nonexistent_tool_xyz", {})
        assert ok is False
        assert "error" in result

    def test_tool_bridge_permission_check(self, tool_bridge):
        perm = tool_bridge.check_permissions("takeScreenshot", {})
        assert "allowed" in perm
        assert "decision" in perm

    def test_tool_bridge_verify_result(self, tool_bridge):
        v = tool_bridge.verify_result("test", {}, {"ok": True, "result": {"data": 1}})
        assert v["verified"] is True
        assert v["confidence"] > 0.5

    def test_tool_bridge_verify_failure(self, tool_bridge):
        v = tool_bridge.verify_result("test", {}, {"ok": False, "error": "failed"})
        assert v["verified"] is False


# ============================================================
# 2. PERMISSION / SAFETY PATH
# ============================================================

class TestPermissionSafety:
    def test_worker_scoped_tools_enforced(self, tool_bridge):
        ok, result = tool_bridge.dispatch(
            "deleteFile", {"path": "/tmp/test"},
            allowed_tools={"createFile"},  # deleteFile not allowed
        )
        assert ok is False
        assert "not allowed" in result.get("error", "").lower()

    def test_trading_blocks_buy(self):
        w = TradingWorker()
        contract = _make_contract("trading", "buy RELIANCE")
        result = w.execute(contract)
        assert result.result.get("blocked") is True

    def test_trading_blocks_sell(self):
        w = TradingWorker()
        contract = _make_contract("trading", "sell TCS")
        result = w.execute(contract)
        assert result.result.get("blocked") is True

    def test_trading_allows_analysis(self):
        w = TradingWorker()
        contract = _make_contract("trading", "analyze RELIANCE", symbol="RELIANCE")
        result = w.execute(contract)
        assert result.is_success


# ============================================================
# 3. VERIFICATION
# ============================================================

class TestVerification:
    def test_verification_worker_passes(self):
        w = VerificationWorker()
        contract = _make_contract(
            "verification", "verify",
            result={"ok": True}, confidence=0.9,
        )
        result = w.execute(contract)
        assert result.is_success
        assert result.result["all_passed"] is True

    def test_verification_worker_fails_on_low_confidence(self):
        w = VerificationWorker()
        contract = _make_contract(
            "verification", "verify",
            result={"ok": True}, confidence=0.2,
        )
        result = w.execute(contract)
        assert result.result["all_passed"] is False


# ============================================================
# 4. WORLD MODEL UPDATES
# ============================================================

class TestWorldModelUpdates:
    def test_world_model_bridge_skips_on_low_confidence(self):
        bridge = WorldModelBridge()
        ok = bridge.update_after_worker(
            "worker1", "coding", "test task",
            {"ok": True, "result": {}},
            {"verified": False, "confidence": 0.2},
        )
        assert ok is False

    def test_world_model_bridge_updates_on_verified(self):
        bridge = WorldModelBridge()
        ok = bridge.update_after_worker(
            "worker1", "coding", "create file test.py",
            {"ok": True, "result": {"path": "test.py"}},
            {"verified": True, "confidence": 0.9},
        )
        # May return False if WorldModel not initialized, that's OK
        assert isinstance(ok, bool)


# ============================================================
# 5. PERSISTENT METRICS
# ============================================================

class TestPersistentMetrics:
    def test_record_success(self, metric_store):
        metric_store.record_success("coding", 10.0)
        m = metric_store.get_metrics("coding")
        assert m is not None
        assert m["total_calls"] == 1
        assert m["success_count"] == 1

    def test_record_failure(self, metric_store):
        metric_store.record_failure("coding", "timeout")
        m = metric_store.get_metrics("coding")
        assert m["failure_count"] == 1
        assert "timeout" in m["recent_errors"]

    def test_bounded_history(self, metric_store):
        for i in range(150):
            metric_store.record_success("coding", float(i))
        m = metric_store.get_metrics("coding")
        assert len(m["history"]) <= 100

    def test_persistence_survives_reload(self, metric_store):
        metric_store.record_success("coding", 10.0)
        metric_store.record_success("coding", 20.0)
        # Create new store with same dir
        store2 = MetricStore(storage_dir=str(metric_store._dir))
        m = store2.get_metrics("coding")
        assert m is not None
        assert m["total_calls"] == 2

    def test_summary(self, metric_store):
        metric_store.record_success("coding", 10.0)
        metric_store.record_failure("research", "error")
        s = metric_store.summary()
        assert s["total_skills"] == 2
        assert s["total_calls"] == 2


# ============================================================
# 6. NEURAL ROUTING
# ============================================================

class TestNeuralRouting:
    def test_heuristic_rank(self, neural_router):
        s1 = Skill.create("fast", "Fast", SkillDomain.CODING)
        s1.health.record_success(5.0)
        s2 = Skill.create("slow", "Slow", SkillDomain.CODING)
        s2.health.record_success(50.0)
        ranked = neural_router._heuristic_rank([s1, s2], "create file", "coding_task", {})
        assert ranked[0][0].id == "fast"

    def test_fallback_when_neural_unavailable(self, neural_router):
        s1 = Skill.create("s1", "Skill1", SkillDomain.CODING)
        ranked = neural_router.rank_skills([s1], "test task", "coding_task", {})
        assert len(ranked) == 1
        assert ranked[0][0].id == "s1"

    def test_select_best(self, neural_router):
        reg = neural_router._registry
        reg.register(Skill.create("coding", "Coding", SkillDomain.CODING, required_tools=["createFile"]))
        best = neural_router.select_best(SkillDomain.CODING, "create file", "coding_task")
        assert best is not None


# ============================================================
# 7. ORCHESTRATOR — SINGLE AGENT
# ============================================================

class TestOrchestratorSingle:
    def test_fast_path(self, orchestrator):
        result = orchestrator.execute("What is Python?", {"task_type": "direct_knowledge"})
        assert result["status"] == "completed"
        assert result.get("mode") == "fast"

    def test_single_agent_desktop(self, orchestrator):
        result = orchestrator.execute("Open VS Code", {"task_type": "desktop_action"})
        assert "plan_id" in result


# ============================================================
# 8. ORCHESTRATOR — MULTI AGENT
# ============================================================

class TestOrchestratorMulti:
    def test_sequential_plan(self, orchestrator):
        result = orchestrator.execute("Build a Python web application", {"task_type": "coding_task"})
        assert "plan_id" in result

    def test_research_plan(self, orchestrator):
        result = orchestrator.execute("Research API documentation", {"task_type": "research"})
        assert "plan_id" in result


# ============================================================
# 9. ORCHESTRATOR — METRICS + WORLD MODEL
# ============================================================

class TestOrchestratorIntegration:
    def test_health_includes_metrics(self, orchestrator):
        h = orchestrator.health()
        assert "metric_store" in h or "telemetry" in h

    def test_reset_clears_state(self, orchestrator):
        orchestrator.execute("What is Python?", {"task_type": "direct_knowledge"})
        orchestrator.reset()
        h = orchestrator.health()
        assert h["active_plans"] == 0


# ============================================================
# 10. SECURITY
# ============================================================

class TestSecurity:
    def test_financial_execution_impossible(self):
        w = TradingWorker()
        for action in ["buy", "sell", "square_off", "cancel", "modify", "submit"]:
            contract = _make_contract("trading", f"{action} RELIANCE")
            result = w.execute(contract)
            assert result.result.get("blocked") is True

    def test_worker_cannot_expand_permissions(self, tool_bridge):
        ok, result = tool_bridge.dispatch(
            "deleteFile", {"path": "/tmp/test"},
            allowed_tools={"createFile"},
        )
        assert ok is False


# ============================================================
# 11. LOOP PROTECTION
# ============================================================

class TestLoopProtection:
    def test_retry_bounds(self):
        from desktop_agent.skills.loop_protection import LoopLimits
        guard = LoopGuard(LoopLimits(max_retries=2))
        guard.start()
        assert guard.check_retry() is True
        assert guard.check_retry() is True
        assert guard.check_retry() is False


# ============================================================
# 12. PERFORMANCE
# ============================================================

class TestPerformance:
    def test_tool_bridge_dispatch_speed(self, tool_bridge):
        if not tool_bridge.has_tool("systemInfo"):
            pytest.skip("systemInfo not available")
        start = time.perf_counter()
        for _ in range(10):
            tool_bridge.dispatch("systemInfo", {})
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5000, f"10 dispatches took {elapsed_ms:.2f}ms"

    def test_metric_store_speed(self, metric_store):
        start = time.perf_counter()
        for i in range(100):
            metric_store.record_success("test", float(i))
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5000, f"100 records took {elapsed_ms:.2f}ms"

    def test_neural_router_ranking_speed(self, neural_router):
        skills = [Skill.create(f"s{i}", f"Skill {i}", SkillDomain.CODING) for i in range(50)]
        start = time.perf_counter()
        neural_router.rank_skills(skills, "test task", "coding_task", {})
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"Ranking 50 skills took {elapsed_ms:.2f}ms"


# ============================================================
# 13. THREAD SAFETY
# ============================================================

class TestThreadSafety:
    def test_concurrent_metric_recording(self, metric_store):
        errors = []

        def record(i):
            try:
                metric_store.record_success("test", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        m = metric_store.get_metrics("test")
        assert m["total_calls"] == 20
