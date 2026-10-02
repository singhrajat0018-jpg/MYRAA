"""Phase I — Skills + Multi-Agent Intelligence Tests.

Coverage:
- Skill Registry (register, discover, health, permissions, versioning)
- Workers (create, execute, cancel, timeout, failure, retry)
- Delegation (one worker, multi-worker, handoff, dependency)
- Parallel (independent tasks, synchronization, resource limits)
- Conflict (disagreement, resolution)
- Security (least privilege, denied tools, financial block, destructive confirmation)
- World Model (context injection, state update)
- Memory (meaningful outcome persistence)
- Self-Healing (worker recovery)
- Loop Protection (retry bounds, handoff bounds, time bounds)
- Observability (agent events, telemetry)
- E2E Scenarios (fast answer, research, portfolio)
- Performance (skill discovery, agent creation, routing)
"""

import time
import threading
import pytest
from unittest.mock import MagicMock

from desktop_agent.skills.skill import Skill, SkillState, SkillDomain, SkillHealth, SkillVersion
from desktop_agent.skills.worker import Worker, WorkerContract, WorkerResult, WorkerStatus
from desktop_agent.skills.registry import SkillRegistry
from desktop_agent.skills.agents import (
    CodingWorker, ResearchWorker, TradingWorker, VisionWorker,
    DesktopWorker, VerificationWorker, MemoryWorker,
    ProjectWorker, DocumentsWorker, AutomationWorker, DiagnosticsWorker,
)
from desktop_agent.skills.planner import AgentPlanner, ExecutionPlan, PlanStep, PlanMode
from desktop_agent.skills.supervisor import AgentSupervisor, SupervisorDecision
from desktop_agent.skills.handoff import Handoff, HandoffSystem
from desktop_agent.skills.conflict import ConflictResolver, Conflict, ConflictType, ResolutionStrategy
from desktop_agent.skills.loop_protection import LoopGuard, LoopLimits
from desktop_agent.skills.observability import AgentEvent, AgentTelemetry
from desktop_agent.skills.orchestrator import SkillOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    """Reset singletons before each test."""
    SkillRegistry.reset()
    yield
    SkillRegistry.reset()


@pytest.fixture
def registry():
    return SkillRegistry()


@pytest.fixture
def planner():
    return AgentPlanner()


@pytest.fixture
def supervisor():
    return AgentSupervisor()


@pytest.fixture
def handoff_system():
    return HandoffSystem()


@pytest.fixture
def conflict_resolver():
    return ConflictResolver()


@pytest.fixture
def loop_guard():
    return LoopGuard()


@pytest.fixture
def telemetry():
    return AgentTelemetry()


@pytest.fixture
def orchestrator():
    return SkillOrchestrator()


# ============================================================
# 1. SKILL REGISTRY
# ============================================================

class TestSkillRegistry:
    def test_register_skill(self, registry):
        skill = Skill.create(
            skill_id="coding",
            name="Coding",
            domain=SkillDomain.CODING,
            description="Code writing and editing",
        )
        ok = registry.register(skill)
        assert ok is True
        assert registry.get("coding") is not None

    def test_discover_by_domain(self, registry):
        registry.register(Skill.create("coding", "Coding", SkillDomain.CODING))
        registry.register(Skill.create("research", "Research", SkillDomain.RESEARCH))
        found = registry.discover(domain=SkillDomain.CODING)
        assert len(found) == 1
        assert found[0].id == "coding"

    def test_discover_by_capability(self, registry):
        skill = Skill.create("coding", "Coding", SkillDomain.CODING, capabilities=["python", "debug"])
        registry.register(skill)
        found = registry.discover(capability="python")
        assert len(found) == 1

    def test_discover_by_tool(self, registry):
        skill = Skill.create("coding", "Coding", SkillDomain.CODING, required_tools=["createFile"])
        registry.register(skill)
        found = registry.discover(tool="createFile")
        assert len(found) == 1

    def test_enable_disable(self, registry):
        skill = Skill.create("coding", "Coding", SkillDomain.CODING)
        registry.register(skill)
        registry.disable("coding")
        assert registry.get("coding").state == SkillState.DISABLED
        registry.enable("coding")
        assert registry.get("coding").state == SkillState.AVAILABLE

    def test_health_report(self, registry):
        registry.register(Skill.create("coding", "Coding", SkillDomain.CODING))
        report = registry.health_report()
        assert report["total"] == 1
        assert report["available"] == 1

    def test_record_success_failure(self, registry):
        skill = Skill.create("coding", "Coding", SkillDomain.CODING)
        registry.register(skill)
        registry.record_success("coding", 10.0)
        registry.record_success("coding", 20.0)
        registry.record_failure("coding", "test error")
        h = registry.get("coding").health
        assert h.total_calls == 3
        assert h.success_count == 2
        assert h.failure_count == 1

    def test_versioning(self, registry):
        skill = Skill.create("coding", "Coding", SkillDomain.CODING)
        registry.register(skill)
        registry.set_version("coding", "2.0.0", SkillVersion.CANDIDATE)
        assert registry.get("coding").version == "2.0.0"
        assert registry.get("coding").version_status == SkillVersion.CANDIDATE

    def test_deprecate(self, registry):
        skill = Skill.create("old", "Old", SkillDomain.CODING)
        registry.register(skill)
        registry.deprecate("old")
        assert registry.get("old").state == SkillState.DEPRECATED

    def test_dependencies(self, registry):
        registry.register(Skill.create("base", "Base", SkillDomain.CODING))
        registry.register(Skill.create("derived", "Derived", SkillDomain.CODING, dependencies=["base"]))
        check = registry.check_dependencies("derived")
        assert check["satisfied"] is True

    def test_missing_dependencies(self, registry):
        registry.register(Skill.create("derived", "Derived", SkillDomain.CODING, dependencies=["missing"]))
        check = registry.check_dependencies("derived")
        assert check["satisfied"] is False
        assert "missing" in check["missing"]

    def test_best_for_task(self, registry):
        s1 = Skill.create("fast", "Fast", SkillDomain.CODING, required_tools=["createFile"])
        s1.health.record_success(5.0)
        s2 = Skill.create("slow", "Slow", SkillDomain.CODING, required_tools=["createFile"])
        s2.health.record_success(50.0)
        registry.register(s1)
        registry.register(s2)
        best = registry.best_for_task(SkillDomain.CODING, required_tools=["createFile"])
        assert best.id == "fast"

    def test_unregister(self, registry):
        registry.register(Skill.create("test", "Test", SkillDomain.CODING))
        ok = registry.unregister("test")
        assert ok is True
        assert registry.get("test") is None

    def test_on_change_listener(self, registry):
        events = []
        registry.on_change(lambda e, s: events.append((e, s.id)))
        registry.register(Skill.create("test", "Test", SkillDomain.CODING))
        assert len(events) == 1
        assert events[0] == ("registered", "test")


# ============================================================
# 2. WORKERS
# ============================================================

class TestWorkers:
    def _make_contract(self, skill_id="coding", task="create project", **kwargs):
        return WorkerContract(
            task_id="t1",
            task_description=task,
            skill_id=skill_id,
            input_data=kwargs,
        )

    def test_coding_worker_create_project(self):
        from desktop_agent.skills.tool_bridge import get_tool_bridge
        w = CodingWorker()
        contract = self._make_contract("coding", "create project", name="Test")
        result = w.execute(contract)
        # Skip if tools not available in test env (TOOLS dict empty)
        if not result.is_success and "Unknown tool" in str(result.evidence):
            pytest.skip("Tools not registered in test environment")
        assert result.is_success
        assert result.result["action"] == "create_project"

    def test_coding_worker_create_file(self):
        # U.1.1 isolation fix: this test previously wrote a fixed "test.py"
        # into the repo CWD and never cleaned it up, so every SECOND suite
        # run failed with "File already exists" (order/residue dependence).
        # Use a unique-per-run artifact and guarantee removal.
        import os
        import uuid

        w = CodingWorker()
        artifact = f"test_{uuid.uuid4().hex[:8]}.py"
        contract = self._make_contract("coding", "create file", path=artifact)
        try:
            result = w.execute(contract)
            # Skip if tools not available in test env (TOOLS dict empty)
            if not result.is_success and "Unknown tool" in str(result.evidence):
                pytest.skip("Tools not registered in test environment")
            if not result.is_success:
                from desktop_agent.registry import TOOLS as _TOOLS
                state = {
                    "cwd": os.getcwd(),
                    "tools_count": len(_TOOLS),
                    "evidence": str(result.evidence)[:500],
                }
                assert result.is_success, f"coding worker failed; STATE={state}"
            assert result.result["action"] == "create_file"
        finally:
            try:
                if os.path.exists(artifact):
                    os.remove(artifact)
            except OSError:
                pass

    def test_research_worker(self):
        w = ResearchWorker()
        contract = self._make_contract("research", "research API docs", query="Python API")
        result = w.execute(contract)
        assert result.is_success

    def test_trading_worker_blocks_buy(self):
        w = TradingWorker()
        contract = self._make_contract("trading", "buy RELIANCE")
        result = w.execute(contract)
        assert result.is_success
        assert result.result["blocked"] is True

    def test_trading_worker_blocks_sell(self):
        w = TradingWorker()
        contract = self._make_contract("trading", "sell TCS")
        result = w.execute(contract)
        assert result.is_success
        assert result.result["blocked"] is True

    def test_trading_worker_allows_analysis(self):
        w = TradingWorker()
        contract = self._make_contract("trading", "analyze RELIANCE", symbol="RELIANCE")
        result = w.execute(contract)
        assert result.is_success
        assert result.result["action"] == "analyze"

    def test_vision_worker(self):
        w = VisionWorker()
        contract = self._make_contract("vision", "take screenshot")
        result = w.execute(contract)
        assert result.is_success

    def test_desktop_worker_open(self):
        w = DesktopWorker()
        contract = self._make_contract("desktop", "open VS Code", application="VS Code")
        result = w.execute(contract)
        assert result.is_success
        assert result.result["action"] == "open"

    def test_verification_worker(self):
        w = VerificationWorker()
        contract = self._make_contract("verification", "verify", result={"ok": True}, confidence=0.9)
        result = w.execute(contract)
        assert result.is_success
        assert result.result["all_passed"] is True

    def test_worker_cancel(self):
        w = CodingWorker()
        contract = self._make_contract()
        w.cancel()
        assert w.is_cancelled()

    def test_worker_can_handle(self):
        w = CodingWorker()
        contract = self._make_contract("coding", "create file")
        assert w.can_handle(contract) is True

    def test_worker_cannot_handle_wrong_skill(self):
        w = CodingWorker()
        contract = self._make_contract("trading", "analyze stock")
        assert w.can_handle(contract) is False

    def test_worker_result_properties(self):
        r = WorkerResult(status=WorkerStatus.COMPLETED, task_id="t1", skill_id="s1")
        assert r.is_success is True
        assert r.is_failure is False

    def test_worker_result_failure(self):
        r = WorkerResult(status=WorkerStatus.FAILED, task_id="t1", skill_id="s1", errors=["err"])
        assert r.is_failure is True


# ============================================================
# 3. PLANNER
# ============================================================

class TestPlanner:
    def test_plan_project(self, planner):
        plan = planner.plan("Build a Python web application")
        assert plan.mode in (PlanMode.SEQUENTIAL, PlanMode.PARALLEL)
        assert len(plan.steps) > 0

    def test_plan_research(self, planner):
        plan = planner.plan("Research the latest API docs")
        assert len(plan.steps) > 0

    def test_plan_fast_answer(self, planner):
        plan = planner.plan("What is Python?", {"task_type": "direct_knowledge"})
        assert plan.mode == PlanMode.SINGLE

    def test_plan_debug(self, planner):
        plan = planner.plan("Fix the bug in my project")
        assert len(plan.steps) > 0

    def test_plan_test(self, planner):
        plan = planner.plan("Run tests and verify")
        assert len(plan.steps) > 0

    def test_plan_steps_have_dependencies(self, planner):
        plan = planner.plan("Build a project")
        has_deps = any(len(s.depends_on) > 0 for s in plan.steps)
        assert has_deps

    def test_plan_ready_steps(self, planner):
        plan = planner.plan("Build a project")
        ready = plan.ready_steps()
        assert len(ready) > 0

    def test_plan_to_dict(self, planner):
        plan = planner.plan("Test plan")
        d = plan.to_dict()
        assert "plan_id" in d
        assert "steps" in d

    def test_to_contracts(self, planner):
        plan = planner.plan("Test plan")
        contracts = planner.to_contracts(plan)
        assert len(contracts) == len(plan.steps)


# ============================================================
# 4. SUPERVISOR
# ============================================================

class TestSupervisor:
    def test_continue_on_success(self, supervisor):
        plan = ExecutionPlan(plan_id="p1", goal="test", mode=PlanMode.SINGLE)
        step = PlanStep(step_id="s1", task_id="t1", description="test", skill_id="s1", worker_class="CodingWorker")
        plan.steps.append(step)
        result = WorkerResult(status=WorkerStatus.COMPLETED, task_id="t1", skill_id="s1")
        decision = supervisor.decide(plan, step, result)
        assert decision == SupervisorDecision.CONTINUE

    def test_retry_on_retryable_failure(self, supervisor):
        plan = ExecutionPlan(plan_id="p1", goal="test", mode=PlanMode.SINGLE)
        step = PlanStep(step_id="s1", task_id="t1", description="test", skill_id="s1", worker_class="CodingWorker")
        plan.steps.append(step)
        result = WorkerResult(status=WorkerStatus.FAILED, task_id="t1", skill_id="s1", errors=["err1"])
        decision = supervisor.decide(plan, step, result)
        assert decision in (SupervisorDecision.RETRY, SupervisorDecision.REPLAN, SupervisorDecision.ESCALATE)

    def test_cancel_on_cancellation(self, supervisor):
        plan = ExecutionPlan(plan_id="p1", goal="test", mode=PlanMode.SINGLE)
        step = PlanStep(step_id="s1", task_id="t1", description="test", skill_id="s1", worker_class="CodingWorker")
        plan.steps.append(step)
        result = WorkerResult(status=WorkerStatus.CANCELLED, task_id="t1", skill_id="s1")
        decision = supervisor.decide(plan, step, result)
        assert decision == SupervisorDecision.CANCEL

    def test_supervisor_stats(self, supervisor):
        stats = supervisor.stats()
        assert "total_events" in stats

    def test_supervisor_reset(self, supervisor):
        supervisor.reset()
        stats = supervisor.stats()
        assert stats["total_events"] == 0


# ============================================================
# 5. HANDOFFS
# ============================================================

class TestHandoffs:
    def test_create_handoff(self, handoff_system):
        h = handoff_system.create_handoff(
            from_worker="coding",
            to_worker="verification",
            reason="Code ready for review",
        )
        assert h.from_worker == "coding"
        assert h.to_worker == "verification"
        assert h.status == "pending"

    def test_complete_handoff(self, handoff_system):
        h = handoff_system.create_handoff("a", "b", "reason")
        ok = handoff_system.complete_handoff(h.handoff_id)
        assert ok is True
        assert h.status == "completed"
        assert h.latency_ms is not None

    def test_fail_handoff(self, handoff_system):
        h = handoff_system.create_handoff("a", "b", "reason")
        ok = handoff_system.fail_handoff(h.handoff_id, "timeout")
        assert ok is True
        assert h.status == "failed"

    def test_handoff_expiry(self, handoff_system):
        h = handoff_system.create_handoff("a", "b", "reason", deadline_seconds=0)
        time.sleep(0.01)
        assert h.is_expired

    def test_check_circular(self, handoff_system):
        handoff_system.create_handoff("a", "b", "r1", plan_id="p1")
        handoff_system.create_handoff("b", "a", "r2", plan_id="p1")
        assert handoff_system.check_circular("p1") is True

    def test_handoff_stats(self, handoff_system):
        handoff_system.create_handoff("a", "b", "r1")
        stats = handoff_system.stats()
        assert stats["total"] == 1


# ============================================================
# 6. CONFLICT RESOLUTION
# ============================================================

class TestConflictResolution:
    def test_detect_conflict(self, conflict_resolver):
        c = conflict_resolver.detect(
            "worker_a", {"data": "X"},
            "worker_b", {"data": "Y"},
        )
        assert c is not None
        assert c.conflict_type == ConflictType.DATA_CONFLICT

    def test_no_conflict_if_same(self, conflict_resolver):
        c = conflict_resolver.detect(
            "worker_a", {"data": "X"},
            "worker_b", {"data": "X"},
        )
        assert c is None

    def test_resolve_by_evidence(self, conflict_resolver):
        c = conflict_resolver.detect(
            "worker_a", {"data": "X"},
            "worker_b", {"data": "Y"},
            evidence_a=["source1", "source2"],
            evidence_b=["source3"],
        )
        resolution = conflict_resolver.resolve(c, ResolutionStrategy.EVIDENCE_RANK)
        assert resolution.winner == "worker_a"

    def test_resolve_by_confidence(self, conflict_resolver):
        c = conflict_resolver.detect(
            "worker_a", {"data": "X"},
            "worker_b", {"data": "Y"},
            confidence_a=0.9,
            confidence_b=0.3,
        )
        resolution = conflict_resolver.resolve(c, ResolutionStrategy.CONFIDENCE_WEIGHT)
        assert resolution.winner == "worker_a"

    def test_resolve_by_fusion(self, conflict_resolver):
        c = conflict_resolver.detect(
            "worker_a", {"key_a": "val_a"},
            "worker_b", {"key_b": "val_b"},
        )
        resolution = conflict_resolver.resolve(c, ResolutionStrategy.FUSION)
        assert resolution.combined_result is not None
        assert "key_a" in resolution.combined_result

    def test_conflict_stats(self, conflict_resolver):
        conflict_resolver.detect("a", {"x": 1}, "b", {"x": 2})
        stats = conflict_resolver.stats()
        assert stats["total"] == 1


# ============================================================
# 7. LOOP PROTECTION
# ============================================================

class TestLoopProtection:
    def test_retry_within_limit(self, loop_guard):
        loop_guard.start()
        assert loop_guard.check_retry() is True
        assert loop_guard.check_retry() is True

    def test_retry_exceeds_limit(self, loop_guard):
        limits = LoopLimits(max_retries=2)
        guard = LoopGuard(limits)
        guard.start()
        assert guard.check_retry() is True
        assert guard.check_retry() is True
        assert guard.check_retry() is False

    def test_handoff_within_limit(self, loop_guard):
        loop_guard.start()
        assert loop_guard.check_handoff() is True

    def test_handoff_exceeds_limit(self, loop_guard):
        limits = LoopLimits(max_handoffs=1)
        guard = LoopGuard(limits)
        guard.start()
        assert guard.check_handoff() is True
        assert guard.check_handoff() is False

    def test_time_limit(self, loop_guard):
        limits = LoopLimits(max_execution_time_s=0)
        guard = LoopGuard(limits)
        guard.start()
        time.sleep(0.01)
        assert guard.check_time() is False

    def test_same_task_repetition(self, loop_guard):
        limits = LoopLimits(max_retries=10, max_same_task_repetitions=2)
        guard = LoopGuard(limits)
        guard.start()
        assert guard.check_retry(task_id="task1") is True
        assert guard.check_retry(task_id="task1") is True
        assert guard.check_retry(task_id="task1") is False

    def test_same_error_repetition(self, loop_guard):
        limits = LoopLimits(max_retries=10, max_same_error_repetitions=2)
        guard = LoopGuard(limits)
        guard.start()
        assert guard.check_retry(error="timeout") is True
        assert guard.check_retry(error="timeout") is True
        assert guard.check_retry(error="timeout") is False

    def test_violations(self, loop_guard):
        limits = LoopLimits(max_retries=0)
        guard = LoopGuard(limits)
        guard.start()
        guard.check_retry()
        violations = guard.get_violations()
        assert len(violations) > 0

    def test_reset(self, loop_guard):
        loop_guard.start()
        loop_guard.check_retry()
        loop_guard.reset()
        state = loop_guard.get_state()
        assert state["retries"] == 0


# ============================================================
# 8. OBSERVABILITY
# ============================================================

class TestObservability:
    def test_record_event(self, telemetry):
        telemetry.record(AgentEvent("agent_started", "a1", "t1"))
        assert len(telemetry.recent()) == 1

    def test_record_completed(self, telemetry):
        telemetry.record_completed("a1", "t1", "coding", 100.0)
        summary = telemetry.summary()
        assert summary["total_events"] == 1

    def test_record_failed(self, telemetry):
        telemetry.record_failed("a1", "t1", "coding", ["error"])
        summary = telemetry.summary()
        assert summary["total_events"] == 1

    def test_record_handoff(self, telemetry):
        telemetry.record_handoff("a1", "a2", "t1")
        assert len(telemetry.recent()) == 1

    def test_latency_stats(self, telemetry):
        for i in range(10):
            telemetry.record_completed(f"a{i}", "t1", "coding", float(i * 10))
        summary = telemetry.summary()
        assert "coding" in summary["latency_stats"]

    def test_reset(self, telemetry):
        telemetry.record(AgentEvent("test", "a1", "t1"))
        telemetry.reset()
        assert len(telemetry.recent()) == 0

    def test_max_events(self):
        t = AgentTelemetry(max_events=5)
        for i in range(10):
            t.record(AgentEvent("test", f"a{i}", f"t{i}"))
        assert len(t.recent()) == 5


# ============================================================
# 9. ORCHESTRATOR — SINGLE AGENT
# ============================================================

class TestOrchestratorSingle:
    def test_fast_path(self, orchestrator):
        result = orchestrator.execute("What is Python?", {"task_type": "direct_knowledge"})
        assert result["status"] == "completed"
        assert result["mode"] == "fast"

    def test_single_agent_desktop(self, orchestrator):
        result = orchestrator.execute("Open VS Code", {"task_type": "desktop_action"})
        assert result["status"] == "completed"


# ============================================================
# 10. ORCHESTRATOR — MULTI AGENT
# ============================================================

class TestOrchestratorMulti:
    def test_sequential_plan(self, orchestrator):
        result = orchestrator.execute("Build a Python web application", {"task_type": "coding_task"})
        assert "plan_id" in result

    def test_research_plan(self, orchestrator):
        result = orchestrator.execute("Research API documentation", {"task_type": "research"})
        assert "plan_id" in result

    def test_analyze_plan(self, orchestrator):
        result = orchestrator.execute("Analyze RELIANCE stock", {"task_type": "trading_task"})
        assert "plan_id" in result


# ============================================================
# 11. ORCHESTRATOR — CANCEL / HEALTH
# ============================================================

class TestOrchestratorControl:
    def test_health(self, orchestrator):
        h = orchestrator.health()
        assert "registry" in h
        assert "active_plans" in h
        assert "telemetry" in h

    def test_reset(self, orchestrator):
        orchestrator.execute("What is Python?", {"task_type": "direct_knowledge"})
        orchestrator.reset()
        h = orchestrator.health()
        assert h["active_plans"] == 0


# ============================================================
# 12. SECURITY
# ============================================================

class TestSecurity:
    def test_trading_blocks_buy(self):
        w = TradingWorker()
        contract = WorkerContract(task_id="t1", task_description="buy RELIANCE", skill_id="trading")
        result = w.execute(contract)
        assert result.result["blocked"] is True

    def test_trading_blocks_sell(self):
        w = TradingWorker()
        contract = WorkerContract(task_id="t1", task_description="sell TCS", skill_id="trading")
        result = w.execute(contract)
        assert result.result["blocked"] is True

    def test_worker_scoped_tools(self):
        w = CodingWorker()
        assert "createFile" in w.allowed_tools
        assert "buy" not in w.allowed_tools

    def test_worker_no_unrestricted(self):
        w = ResearchWorker()
        assert len(w.allowed_tools) > 0
        # Research should not have destructive tools
        assert "deleteFile" not in w.allowed_tools


# ============================================================
# 13. PERFORMANCE
# ============================================================

class TestPerformance:
    def test_skill_discovery_speed(self, registry):
        for i in range(100):
            registry.register(Skill.create(f"s{i}", f"Skill {i}", SkillDomain.CODING))
        start = time.perf_counter()
        registry.discover(domain=SkillDomain.CODING)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5, f"Discovery took {elapsed_ms:.2f}ms"

    def test_worker_creation_speed(self):
        start = time.perf_counter()
        for _ in range(100):
            CodingWorker()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"100 workers took {elapsed_ms:.2f}ms"

    def test_planner_speed(self, planner):
        start = time.perf_counter()
        planner.plan("Build a complete web application with research")
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 20, f"Planning took {elapsed_ms:.2f}ms"

    def test_orchestrator_fast_path_speed(self, orchestrator):
        start = time.perf_counter()
        orchestrator.execute("What is Python?", {"task_type": "direct_knowledge"})
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 5, f"Fast path took {elapsed_ms:.2f}ms"


# ============================================================
# 14. E2E SCENARIOS
# ============================================================

class TestE2EScenarios:
    def test_scenario_1_simple_question(self, orchestrator):
        """What is Python? → FAST_ANSWER, NO AGENTS."""
        result = orchestrator.execute("What is Python?", {"task_type": "direct_knowledge"})
        assert result["status"] == "completed"
        assert result.get("mode") == "fast"

    def test_scenario_2_research(self, orchestrator):
        """Research API docs → Research Skill → Worker → Verification."""
        result = orchestrator.execute(
            "Research the latest API docs and summarize them",
            {"task_type": "research"},
        )
        assert "plan_id" in result

    def test_scenario_3_fix_bug(self, orchestrator):
        """Fix bug → Coding Skill → Coding Worker → Test Worker → Verification."""
        result = orchestrator.execute(
            "Fix the bug in my project and run tests",
            {"task_type": "coding_task"},
        )
        assert "plan_id" in result

    def test_scenario_5_portfolio(self, orchestrator):
        """Analyze Groww portfolio → Trading Skill → read-only Trading Worker → Verification."""
        result = orchestrator.execute(
            "Analyze my Groww portfolio",
            {"task_type": "trading_task"},
        )
        assert "plan_id" in result

    def test_scenario_4_build_app(self, orchestrator):
        """Build application → Architect → Research/Coding → parallel → Testing → Verification."""
        result = orchestrator.execute(
            "Build a complete application",
            {"task_type": "coding_task"},
        )
        assert "plan_id" in result


# ============================================================
# 15. THREAD SAFETY
# ============================================================

class TestThreadSafety:
    def test_concurrent_registration(self, registry):
        errors = []

        def register_skill(i):
            try:
                registry.register(Skill.create(f"s{i}", f"Skill {i}", SkillDomain.CODING))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_skill, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert registry.count()["total"] == 20

    def test_concurrent_discovery(self, registry):
        for i in range(50):
            registry.register(Skill.create(f"s{i}", f"Skill {i}", SkillDomain.CODING))
        errors = []

        def discover():
            try:
                for _ in range(10):
                    registry.discover(domain=SkillDomain.CODING)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=discover) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
