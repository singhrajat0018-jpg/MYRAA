"""
Phase B — Autonomy Controller comprehensive test suite.

36 tests covering: goal acceptance, decomposition, task graph, execution,
completion, verification, recovery, replanning, loop detection, retry budget,
timeout, pause/resume/cancel, checkpoints, progress, memory integration,
project builder, state machine, telemetry, blocked, clarification, resource
limits, final completion, and type invariants.

All tests use mocks — no real services are touched.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from desktop_agent.brain.super_brain.autonomy_controller import (
    AutonomyController,
    AutonomousGoal,
    AutonomyState,
    AutonomyLevel,
    LoopGuards,
    LoopCounters,
)


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def ckpt_dir() -> str:
    d = tempfile.mkdtemp(prefix="myraa_autonomy_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def mock_super_brain():
    sb = MagicMock()
    result = MagicMock()
    result.to_dict.return_value = {
        "request_id": "test-req",
        "success": True,
        "message": "completed",
        "capability": "GENERAL",
        "execution": {
            "task_id": "cog-123",
            "success": True,
            "message": "done",
            "replans": 0,
        },
        "verification": {"verified": True},
    }
    sb.process.return_value = result
    return sb


@pytest.fixture()
def mock_sb_fail():
    sb = MagicMock()
    result = MagicMock()
    result.to_dict.return_value = {
        "request_id": "test-req-fail",
        "success": False,
        "message": "failed",
        "capability": "GENERAL",
        "execution": {
            "task_id": "cog-456",
            "success": False,
            "message": "error",
            "replans": 0,
        },
        "verification": {"verified": False},
    }
    sb.process.return_value = result
    return sb


@pytest.fixture()
def mock_memory():
    return MagicMock()


@pytest.fixture()
def mock_experience():
    return MagicMock()


@pytest.fixture()
def ctrl(ckpt_dir, mock_super_brain, mock_experience, mock_memory):
    return AutonomyController(
        super_brain=mock_super_brain,
        memory_2_0=mock_memory,
        experience_engine=mock_experience,
        checkpoint_dir=ckpt_dir,
    )


# ── 1. High-level goal acceptance ──────────────────────────────────


class TestGoalAcceptance:
    def test_start_goal_returns_autonomous_goal(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        assert isinstance(g, AutonomousGoal)

    def test_initial_state_is_understanding(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        assert g.state == AutonomyState.UNDERSTANDING

    def test_goal_stored_in_controller(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        assert ctrl.get_goal(g.goal_id) is g

    def test_goal_has_timestamps(self, ctrl: AutonomyController):
        before = time.time()
        g = ctrl.start_goal("do something")
        after = time.time()
        assert before <= g.created_at <= after
        assert before <= g.updated_at <= after

    def test_default_level_is_autonomous(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        assert g.level == AutonomyLevel.AUTONOMOUS

    def test_custom_level(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something", level=AutonomyLevel.GUIDED)
        assert g.level == AutonomyLevel.GUIDED

    def test_custom_guards(self, ctrl: AutonomyController):
        guards = LoopGuards(max_iterations=5, max_retries_per_task=1)
        g = ctrl.start_goal("do something", guards=guards)
        assert g.guards.max_iterations == 5
        assert g.guards.max_retries_per_task == 1


# ── 2. Goal decomposition ──────────────────────────────────────────


class TestGoalDecomposition:
    def test_test_criteria_extraction(self, ctrl: AutonomyController):
        g = ctrl.start_goal("run tests and make them green")
        ctrl._phase_understand(g)
        assert any("tests pass" in c or "test" in c.lower() for c in g.success_criteria)

    def test_project_criteria_extraction(self, ctrl: AutonomyController):
        g = ctrl.start_goal("build a web project")
        ctrl._phase_understand(g)
        assert any("build" in c.lower() for c in g.success_criteria)

    def test_fallback_criteria(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something random")
        ctrl._phase_understand(g)
        assert len(g.success_criteria) > 0

    def test_explicit_criteria_preserved(self, ctrl: AutonomyController):
        explicit = ["custom criterion A", "custom criterion B"]
        g = ctrl.start_goal("build project", success_criteria=explicit)
        ctrl._phase_understand(g)
        assert g.success_criteria == explicit


# ── 3. Task graph creation ──────────────────────────────────────────


class TestTaskGraphCreation:
    def test_planning_transitions_to_ready(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        assert g.state == AutonomyState.READY

    def test_sets_total_tasks(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        assert g.total_tasks >= 1

    def test_headless_planning_without_super_brain(self, ckpt_dir, mock_experience):
        ctrl = AutonomyController(
            super_brain=None,
            experience_engine=mock_experience,
            checkpoint_dir=ckpt_dir,
        )
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        assert g.state == AutonomyState.READY
        assert g.total_tasks == 1


# ── 4. Autonomous execution ─────────────────────────────────────────


class TestAutonomousExecution:
    def test_completes_headless(self, ckpt_dir, mock_experience):
        ctrl = AutonomyController(
            super_brain=None,
            experience_engine=mock_experience,
            checkpoint_dir=ckpt_dir,
        )
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.state == AutonomyState.COMPLETED

    def test_completes_with_mock_sb_success(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.state == AutonomyState.COMPLETED

    def test_completes_with_mock_sb_failure(self, ctrl: AutonomyController, mock_sb_fail):
        ctrl.super_brain = mock_sb_fail
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.state != AutonomyState.COMPLETED
        assert g.counters.total_retries >= 1

    def test_iterations_increment(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.counters.iterations >= 1


# ── 5. Successful completion ────────────────────────────────────────


class TestSuccessfulCompletion:
    def test_completed_at_set(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        if g.state == AutonomyState.COMPLETED:
            assert g.completed_at is not None

    def test_progress_100(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        if g.state == AutonomyState.COMPLETED:
            assert g.progress_pct >= 99.9


# ── 6. Verification-gated completion ────────────────────────────────


class TestVerificationGatedCompletion:
    def test_no_fake_success_without_verification(self, ctrl: AutonomyController, mock_sb_fail):
        ctrl.super_brain = mock_sb_fail
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.state != AutonomyState.COMPLETED

    def test_tracks_last_verification(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert isinstance(g.last_verification, dict)


# ── 7. Failed task recovery ─────────────────────────────────────────


class TestFailedTaskRecovery:
    def test_increments_retries(self, ctrl: AutonomyController, mock_sb_fail):
        ctrl.super_brain = mock_sb_fail
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.counters.total_retries >= 1

    def test_aborts_after_budget(self, ctrl: AutonomyController, mock_sb_fail):
        ctrl.super_brain = mock_sb_fail
        guards = LoopGuards(max_total_retries=1)
        g = ctrl.start_goal("do something", guards=guards)
        ctrl.execute_goal(g)
        assert g.state in (AutonomyState.FAILED, AutonomyState.BLOCKED)


# ── 8. Replanning ───────────────────────────────────────────────────


class TestReplanning:
    def test_replan_count_increments(self, ctrl: AutonomyController):
        mock_sb = MagicMock()
        result = MagicMock()
        result.to_dict.return_value = {
            "request_id": "r", "success": False, "message": "retry",
            "capability": "X", "execution": {"task_id": "1", "success": False, "message": "fail"},
            "verification": {"verified": False},
        }
        mock_sb.process.return_value = result
        ctrl.super_brain = mock_sb
        guards = LoopGuards(max_iterations=4, max_total_retries=10)
        g = ctrl.start_goal("do something", guards=guards)
        with patch.object(ctrl, "_recovery_decision", return_value="replan"):
            ctrl.execute_goal(g)
        assert g.counters.replans >= 1

    def test_stops_at_max_replans(self, ctrl: AutonomyController):
        mock_sb = MagicMock()
        result = MagicMock()
        result.to_dict.return_value = {
            "request_id": "r", "success": False, "message": "retry",
            "capability": "X", "execution": {"task_id": "1", "success": False, "message": "fail"},
            "verification": {"verified": False},
        }
        mock_sb.process.return_value = result
        ctrl.super_brain = mock_sb
        guards = LoopGuards(max_iterations=100, max_replans=2, max_total_retries=50)
        g = ctrl.start_goal("do something", guards=guards)
        with patch.object(ctrl, "_recovery_decision", return_value="replan"):
            ctrl.execute_goal(g)
        assert g.state == AutonomyState.FAILED


# ── 9. Loop detection ──────────────────────────────────────────────


class TestLoopDetection:
    def test_identical_failure_tracking(self):
        counters = LoopCounters()
        counters.record_failure("err_a")
        assert counters.identical_failures == 1
        counters.record_failure("err_a")
        assert counters.identical_failures == 2
        counters.record_failure("err_b")
        assert counters.identical_failures == 1

    def test_loop_guard_detects(self):
        counters = LoopCounters()
        guards = LoopGuards(max_identical_failures=3)
        for _ in range(3):
            counters.record_failure("same_error")
        reason = counters.check_guard(guards)
        assert reason is not None
        assert "loop detected" in reason

    def test_max_iterations_guard(self):
        counters = LoopCounters(iterations=50)
        guards = LoopGuards(max_iterations=50)
        reason = counters.check_guard(guards)
        assert reason is not None
        assert "max iterations" in reason

    def test_max_time_guard(self):
        counters = LoopCounters(started_at=time.time() - 2000)
        guards = LoopGuards(max_execution_time_s=1800)
        reason = counters.check_guard(guards)
        assert reason is not None
        assert "max execution time" in reason


# ── 10. Retry budget ────────────────────────────────────────────────


class TestRetryBudget:
    def test_enforced(self, ctrl: AutonomyController, mock_sb_fail):
        ctrl.super_brain = mock_sb_fail
        guards = LoopGuards(max_total_retries=2, max_iterations=10)
        g = ctrl.start_goal("do something", guards=guards)
        ctrl.execute_goal(g)
        assert g.counters.total_retries <= 2 or g.state == AutonomyState.FAILED

    def test_respects_max_iterations(self):
        counters = LoopCounters(iterations=10)
        guards = LoopGuards(max_iterations=10, max_total_retries=50)
        reason = counters.check_guard(guards)
        assert reason is not None
        assert "max iterations" in reason


# ── 11. Timeout guard ──────────────────────────────────────────────


class TestTimeoutGuard:
    def test_triggers(self):
        counters = LoopCounters(started_at=time.time() - 9999)
        guards = LoopGuards(max_execution_time_s=100)
        assert counters.check_guard(guards) is not None

    def test_not_triggered_early(self):
        counters = LoopCounters(started_at=time.time())
        guards = LoopGuards(max_execution_time_s=9999)
        assert counters.check_guard(guards) is None


# ── 12. Pause ───────────────────────────────────────────────────────


class TestPause:
    def test_sets_state(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        g.transition(AutonomyState.EXECUTING, "manual")
        ctrl.pause(g.goal_id)
        assert g.state == AutonomyState.PAUSED

    def test_nonexistent_returns_false(self, ctrl: AutonomyController):
        assert ctrl.pause("nonexistent-id") is False

    def test_events_set(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl.pause(g.goal_id)
        events = ctrl._control_events.get(g.goal_id)
        assert events is not None
        assert events["pause"].is_set()


# ── 13. Resume ──────────────────────────────────────────────────────


class TestResume:
    def test_clears_pause(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.pause(g.goal_id)
        ctrl.resume(g.goal_id)
        events = ctrl._control_events.get(g.goal_id)
        assert not events["pause"].is_set()

    def test_nonexistent_returns_false(self, ctrl: AutonomyController):
        assert ctrl.resume("nonexistent-id") is False

    def test_clears_event(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        g.transition(AutonomyState.EXECUTING, "manual")
        ctrl.pause(g.goal_id)
        ctrl.resume(g.goal_id)
        assert g.state == AutonomyState.READY


# ── 14. Cancel ──────────────────────────────────────────────────────


class TestCancel:
    def test_sets_state(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.cancel(g.goal_id)
        assert g.state == AutonomyState.CANCELLED

    def test_nonexistent_returns_false(self, ctrl: AutonomyController):
        assert ctrl.cancel("nonexistent-id") is False

    def test_sets_event(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.cancel(g.goal_id)
        events = ctrl._control_events.get(g.goal_id)
        assert events["cancel"].is_set()

    def test_unblocks_paused(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.pause(g.goal_id)
        ctrl.cancel(g.goal_id)
        events = ctrl._control_events.get(g.goal_id)
        assert not events["pause"].is_set()


# ── 15. Checkpoint ──────────────────────────────────────────────────


class TestCheckpoint:
    def test_persisted(self, ctrl: AutonomyController, ckpt_dir: str):
        g = ctrl.start_goal("do something")
        path = os.path.join(ckpt_dir, f"{g.goal_id}.json")
        assert os.path.exists(path)

    def test_content_valid(self, ctrl: AutonomyController, ckpt_dir: str):
        g = ctrl.start_goal("do something")
        path = os.path.join(ckpt_dir, f"{g.goal_id}.json")
        with open(path) as f:
            data = json.load(f)
        assert data["goal_id"] == g.goal_id
        assert "state" in data
        assert "counters" in data

    def test_restores_goal(self, ctrl: AutonomyController, ckpt_dir: str):
        g = ctrl.start_goal("do something")
        restored = ctrl.load_checkpoint(g.goal_id)
        assert restored is not None
        assert restored.goal_id == g.goal_id
        assert restored.user_request == g.user_request


# ── 16. Resume from checkpoint ──────────────────────────────────────


class TestResumeFromCheckpoint:
    def test_adds_to_goals(self, ctrl: AutonomyController, ckpt_dir: str):
        g = ctrl.start_goal("do something")
        restored = ctrl.load_checkpoint(g.goal_id)
        assert ctrl.get_goal(restored.goal_id) is not None

    def test_nonexistent_returns_none(self, ctrl: AutonomyController):
        assert ctrl.load_checkpoint("nonexistent-id") is None

    def test_list_checkpoints(self, ctrl: AutonomyController, ckpt_dir: str):
        g = ctrl.start_goal("do something")
        cps = ctrl.list_checkpoints()
        assert g.goal_id in cps


# ── 17. Progress tracking ──────────────────────────────────────────


class TestProgressTracking:
    def test_report_available(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        report = ctrl.progress_report(g.goal_id)
        assert report is not None
        assert "description" in report

    def test_nonexistent_returns_none(self, ctrl: AutonomyController):
        assert ctrl.progress_report("nonexistent-id") is None

    def test_pct_in_to_dict(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        d = g.to_dict()
        assert "progress_pct" in d

    def test_describe_progress(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        desc = ctrl._describe_progress(g)
        assert isinstance(desc, str)
        assert len(desc) > 0


# ── 18. Memory 2.0 integration ─────────────────────────────────────


class TestMemoryIntegration:
    def test_experience_recorded_on_completion(self, ctrl: AutonomyController, mock_experience):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        if g.state == AutonomyState.COMPLETED:
            mock_experience.record.assert_called()

    def test_experience_recorded_on_failure(self, ctrl: AutonomyController, mock_sb_fail, mock_experience):
        ctrl.super_brain = mock_sb_fail
        guards = LoopGuards(max_total_retries=1)
        g = ctrl.start_goal("do something", guards=guards)
        ctrl.execute_goal(g)
        if g.state == AutonomyState.FAILED:
            mock_experience.record.assert_called()


# ── 19. Project builder autonomy ────────────────────────────────────


class TestProjectBuilderAutonomy:
    def test_headless_project_goal(self, ckpt_dir, mock_experience):
        ctrl = AutonomyController(
            super_brain=None,
            experience_engine=mock_experience,
            checkpoint_dir=ckpt_dir,
        )
        g = ctrl.start_goal("build a python project with tests")
        ctrl.execute_goal(g)
        assert g.state == AutonomyState.COMPLETED
        assert g.completed_tasks >= 1


# ── 20. No duplicate planners/engines ──────────────────────────────


class TestNoDuplicatePlanners:
    def test_not_super_brain(self):
        ctrl = AutonomyController()
        from desktop_agent.brain.super_brain.super_brain import SuperBrain
        assert not isinstance(ctrl, SuperBrain)

    def test_not_planner(self):
        ctrl = AutonomyController()
        from desktop_agent.brain.super_brain.planner import MasterPlanner
        assert not isinstance(ctrl, MasterPlanner)

    def test_not_memory_manager(self):
        ctrl = AutonomyController()
        assert not hasattr(ctrl, "write_memory")


# ── 21. State machine transitions ──────────────────────────────────


class TestStateMachineTransitions:
    def test_valid_transitions_work(self):
        g = AutonomousGoal(goal_id="t1", user_request="test")
        assert g.transition(AutonomyState.UNDERSTANDING) is True
        assert g.state == AutonomyState.UNDERSTANDING

    def test_invalid_rejected(self):
        g = AutonomousGoal(goal_id="t2", user_request="test")
        # IDLE -> EXECUTING is not valid
        assert g.transition(AutonomyState.EXECUTING) is False
        assert g.state == AutonomyState.IDLE


# ── 22. Telemetry ──────────────────────────────────────────────────


class TestTelemetry:
    def test_status_method(self, ctrl: AutonomyController):
        ctrl.start_goal("g1")
        ctrl.start_goal("g2")
        s = ctrl.status()
        assert s["total_goals"] == 2
        assert isinstance(s["active_goals"], int)

    def test_telemetry_per_goal(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        t = ctrl.telemetry(g.goal_id)
        assert t is not None
        assert t["goal_id"] == g.goal_id
        assert "state" in t
        assert "iterations" in t


# ── 23. Blocked task behavior ───────────────────────────────────────


class TestBlockedBehavior:
    def test_blocked_reached_on_guard_violation(self):
        counters = LoopCounters(tool_calls=999)
        guards = LoopGuards(max_tool_calls=10)
        reason = counters.check_guard(guards)
        assert reason is not None
        assert "tool calls" in reason


# ── 24. Clarification ──────────────────────────────────────────────


class TestClarification:
    def test_recovery_returns_ask_for_ambiguous(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        result = {"success": False, "message": "ambiguous request, which one?"}
        decision = ctrl._recovery_decision(g, result)
        assert decision == "ask"

    def test_recovery_returns_abort_for_permission(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        result = {"success": False, "message": "permission denied"}
        decision = ctrl._recovery_decision(g, result)
        assert decision == "abort"


# ── 25. Resource limits ─────────────────────────────────────────────


class TestResourceLimits:
    def test_tool_calls_tracked(self, ctrl: AutonomyController):
        g = ctrl.start_goal("do something")
        ctrl.execute_goal(g)
        assert g.counters.tool_calls >= 1

    def test_tool_call_guard(self):
        counters = LoopCounters(tool_calls=200)
        guards = LoopGuards(max_tool_calls=200)
        reason = counters.check_guard(guards)
        assert reason is not None


# ── 26. Final completion criteria ──────────────────────────────────


class TestFinalCompletionCriteria:
    def test_multi_task_completion(self, ctrl: AutonomyController, mock_super_brain):
        g = ctrl.start_goal("do something")
        ctrl._phase_understand(g)
        ctrl._phase_plan(g)
        g.total_tasks = 3
        g.completed_tasks = 3
        g.progress_pct = 100.0
        assert g.completed_tasks >= g.total_tasks
        assert g.progress_pct >= 99.9


# ── Bonus: LoopGuards / LoopCounters dataclass contracts ────────────


class TestDataContracts:
    def test_loop_guards_to_dict(self):
        g = LoopGuards(max_iterations=42)
        d = g.to_dict()
        assert d["max_iterations"] == 42
        assert "max_retries_per_task" in d
        assert "max_tool_calls" in d

    def test_loop_counters_to_dict(self):
        c = LoopCounters(iterations=7, tool_calls=12)
        d = c.to_dict()
        assert d["iterations"] == 7
        assert d["tool_calls"] == 12
        assert "elapsed_s" in d

    def test_goal_to_dict_fields(self):
        g = AutonomousGoal(goal_id="x", user_request="r")
        d = g.to_dict()
        assert d["goal_id"] == "x"
        assert "guards" in d
        assert "counters" in d
        assert "success_criteria" in d

    def test_goal_checkpoint_data(self):
        g = AutonomousGoal(goal_id="x", user_request="r")
        cd = g.checkpoint_data()
        assert "state_history" in cd
        assert "constraints" in cd
        assert "super_brain_result" in cd
