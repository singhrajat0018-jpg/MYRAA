"""
F5 verification tests: MYRAA must verify real outcomes, never treat a tool's
"success" claim as proof.

Covers the upgraded VerificationManager (brain/verification.py):
- VERIFIED  : deterministic per-tool check passed
- FAILED    : tool claimed success but reality disagrees / no result
- UNVERIFIED: no deterministic check available
- PARTIALLY_VERIFIED: independent path evidence, no deterministic check
- timeout guard on slow verifiers
- wiring into ExecutionBrain._verify -> ExecuteResponse.meta.verification
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from desktop_agent.brain.verification import (
    VerificationManager,
    VerificationOutcome,
)
from desktop_agent.brain.executive.execution_verifier import ExecutionVerifier

ROOT = Path(__file__).resolve().parent.parent


def _workdir():
    """Avoid pytest's tmp_path (broken by an env PermissionError on this box)."""
    return Path(tempfile.mkdtemp(prefix="myraa_f5_", dir=str(ROOT)))


# ---------------------------------------------------------------------------
# VerificationManager outcome classes
# ---------------------------------------------------------------------------

def test_verified_create_file_success():
    """A real createFile leaves a file on disk; the check must VERIFY it."""
    work = _workdir()
    target = work / "verified.txt"
    try:
        target.write_text("x", encoding="utf-8")
        vm = VerificationManager()
        res = vm.verify(
            {"result": f"Created file: {target}", "path": str(target)},
            tool="createFile",
            args={"path": str(target)},
        )
        assert res.outcome is VerificationOutcome.VERIFIED
        assert res.is_verified is True
        assert any(e.passed for e in res.evidence)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_false_tool_success_detected():
    """Tool claims success but the file never appeared -> FAILED, not VERIFIED."""
    work = _workdir()
    missing = work / "never_created.txt"
    try:
        vm = VerificationManager()
        res = vm.verify(
            {"result": "Created file: OK", "path": str(missing)},
            tool="createFile",
            args={"path": str(missing)},
        )
        assert res.outcome is VerificationOutcome.FAILED
        assert res.is_verified is False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_verification_mismatch_delete_file():
    """deleteFile claims removed but the file still exists -> FAILED."""
    work = _workdir()
    target = work / "still_there.txt"
    try:
        target.write_text("x", encoding="utf-8")
        vm = VerificationManager()
        res = vm.verify(
            {"result": "Deleted"},
            tool="deleteFile",
            args={"path": str(target)},
        )
        assert res.outcome is VerificationOutcome.FAILED
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_no_result_is_failed():
    """A tool returning None can never be considered success."""
    vm = VerificationManager()
    res = vm.verify(None, tool="createFile", args={"path": "C:/x"})
    assert res.outcome is VerificationOutcome.FAILED
    assert res.is_verified is False


def test_unverifiable_tool_reports_unverified():
    """Tools without a deterministic check are UNVERIFIED, never auto-verified."""
    vm = VerificationManager()
    res = vm.verify(
        {"result": "done"},
        tool="typeText",
        args={"text": "hello"},
    )
    assert res.outcome is VerificationOutcome.UNVERIFIED
    assert res.is_verified is False


def test_partially_verified_via_reported_path():
    """No deterministic check, but the tool's reported path exists on disk."""
    work = _workdir()
    target = work / "exists.txt"
    try:
        target.write_text("x", encoding="utf-8")
        vm = VerificationManager()
        res = vm.verify(
            {"result": "done", "path": str(target)},
            tool="openFile",
            args={"path": str(target)},
        )
        assert res.outcome is VerificationOutcome.PARTIALLY_VERIFIED
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_rename_file_verified():
    """renameFile: the renamed target must exist on disk."""
    work = _workdir()
    source = work / "old.txt"
    new_name = "new.txt"
    try:
        source.write_text("x", encoding="utf-8")
        source.rename(work / new_name)
        vm = VerificationManager()
        res = vm.verify(
            {"result": "Renamed", "path": str(work / new_name)},
            tool="renameFile",
            args={"path": str(source), "new_name": new_name},
        )
        assert res.outcome is VerificationOutcome.VERIFIED
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------
# Timeout guard
# ---------------------------------------------------------------------------

class SlowVerifier(ExecutionVerifier):
    """A verifier whose deterministic check never returns promptly."""

    def _verify_slowTool(self, params, result):  # noqa: N802
        time.sleep(30)
        return super()._default(result)


def test_verification_timeout_guards_slow_verifier():
    """A hanging verifier must not hang the request; outcome = UNVERIFIED."""
    slow = SlowVerifier()
    vm = VerificationManager(verifier=slow, timeout_seconds=0.2)
    started = time.perf_counter()
    res = vm.verify(
        {"result": "done"},
        tool="slowTool",
        args={},
    )
    elapsed = time.perf_counter() - started
    assert res.outcome is VerificationOutcome.UNVERIFIED
    assert "timed out" in res.message.lower()
    assert elapsed < 5, f"Verification was not actually bounded: {elapsed:.2f}s"


def test_verifier_exception_reports_unverified():
    """A broken verifier must not crash execution; outcome = UNVERIFIED."""

    class BrokenVerifier(ExecutionVerifier):
        def _verify_badTool(self, params, result):  # noqa: N802
            raise RuntimeError("boom")

    vm = VerificationManager(verifier=BrokenVerifier())
    res = vm.verify(
        {"result": "done"},
        tool="badTool",
        args={},
    )
    assert res.outcome is VerificationOutcome.UNVERIFIED
    assert "error" in res.message.lower()


# ---------------------------------------------------------------------------
# Existing machinery compatibility (audit: reuse, don't duplicate engines)
# ---------------------------------------------------------------------------

def test_existing_action_verifier_behavior_preserved():
    """F5 must not disturb the EPIC-14C ActionVerifier used by ActionExecutor."""
    from unittest.mock import MagicMock
    from desktop_agent.brain.execution.action_verifier import ActionVerifier
    from desktop_agent.brain.perception import Perception
    from desktop_agent.brain.planner.models.computer_action import ComputerAction, VerificationStatus
    from desktop_agent.brain.planner.models.action_types import ActionType
    from desktop_agent.desktop.vision.interaction_target import InteractionTarget
    from desktop_agent.desktop.vision.ui_models import BoundingBox, UIElementType
    from desktop_agent.registry import ValidationLayer

    target = InteractionTarget(
        id="f5_target",
        type=UIElementType.BUTTON,
        text="F5 Target",
        confidence=0.8,
        bounds=BoundingBox(x=100, y=100, width=50, height=30),
        clickable=True,
        enabled=True,
        visible=True,
        resolution_method="test",
        reasoning="F5 compat test",
    )
    action = ComputerAction(
        action_type=ActionType.CLICK,
        target=target,
        parameters={},
    )

    mock_perception = MagicMock(spec=Perception)
    mock_screen_state = MagicMock()
    mock_screen_state.bounds = BoundingBox(x=0, y=0, width=1920, height=1080)
    mock_screen_state.active_window = None
    mock_screen_state.elements = []
    mock_screen_state.get_element_by_id.return_value = target
    mock_perception.screen_state = mock_screen_state

    verifier = ActionVerifier(mock_perception, ValidationLayer())
    verifier.stable_state_check_delay = 0.0
    action.mark_as_executed({"success": True})

    result = verifier.verify_action(action, None)

    assert result.is_success is True
    assert result.status.name == "VERIFIED_SUCCESS"


def test_existing_verification_manager_compat_single_arg():
    """The original verify(result) call must still work (tool defaults to '')."""
    vm = VerificationManager()
    res = vm.verify({"result": "done", "path": "C:/nonexistent_f5_xyz"})
    assert res is not None
    assert res.outcome is VerificationOutcome.UNVERIFIED
    assert res.is_verified is False


# ---------------------------------------------------------------------------
# ExecutionBrain wiring
# ---------------------------------------------------------------------------

def _make_execution_brain():
    from desktop_agent.brain.execution_brain import ExecutionBrain
    from desktop_agent.brain.context_manager import ContextManager
    from desktop_agent.brain.perception import Perception
    from desktop_agent.brain.planning.action_planner import ActionPlanner
    from desktop_agent.brain.execution.action_validator import ActionValidator
    from desktop_agent.brain.execution.action_verifier import ActionVerifier
    from desktop_agent.registry import ValidationLayer

    perception = Perception()

    return ExecutionBrain(
        dispatcher=None,
        context_manager=ContextManager(perception=perception),
        perception=perception,
        action_planner=ActionPlanner(),
        action_validator=ActionValidator(perception, ValidationLayer()),
        action_verifier=ActionVerifier(perception, ValidationLayer()),
    )


def test_execute_direct_attaches_verification_meta():
    """ExecutionBrain._execute_direct must attach verification to result.meta."""
    brain = _make_execution_brain()
    work = _workdir()
    target = work / "meta_verified.txt"
    try:
        target.write_text("x", encoding="utf-8")

        class FakeRequest:
            tool = "createFile"
            args = {"path": str(target)}

        class FakeResult:
            ok = True
            result = {"result": "Created", "path": str(target)}
            meta = {}

        verification = brain._verify(
            FakeResult(),
            tool=FakeRequest.tool,
            args=FakeRequest.args,
        )
        assert verification is not None
        assert verification.outcome is VerificationOutcome.VERIFIED
        assert "verification" in FakeResult.meta
        assert FakeResult.meta["verification"]["outcome"] == "verified"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_execute_direct_attaches_failure_meta():
    """A tool that lies (claims success, no file) must surface FAILED in meta."""
    brain = _make_execution_brain()
    work = _workdir()
    target = work / "lie.txt"
    try:
        class FakeResult:
            ok = True
            result = {"result": "Created", "path": str(target)}
            meta = {}

        verification = brain._verify(
            FakeResult(),
            tool="createFile",
            args={"path": str(target)},
        )
        assert verification.outcome is VerificationOutcome.FAILED
        assert FakeResult.meta["verification"]["outcome"] == "failed"
        assert FakeResult.meta["verification"]["verified"] is False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_verify_unwraps_execute_response_payload():
    """The wrapper's .result payload is what gets verified, not the envelope."""
    brain = _make_execution_brain()
    work = _workdir()
    target = work / "unwrapped.txt"
    try:
        target.write_text("x", encoding="utf-8")

        class FakeResult:
            ok = True
            result = {"result": "Created", "path": str(target)}
            meta = {}

        verification = brain._verify(
            FakeResult(),
            tool="createFile",
            args={"path": str(target)},
        )
        assert verification.outcome is VerificationOutcome.VERIFIED
    finally:
        shutil.rmtree(work, ignore_errors=True)