"""
Safe power-action guard tests.

Verifies classification, permission, confirmation gating, and simulated
execution for every power action WITHOUT ever executing a real OS command.

Every OS-facing call (subprocess.run / os.system) is mocked; tests assert the
command WOULD have been requested, never that it ran.
"""
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_agent.tools_pc import _run_power
from desktop_agent.tools_confirmation import DANGEROUS_ACTIONS
from desktop_agent.config.permissions import (
    TOOL_CATEGORIES,
    TOOL_OVERRIDES,
    SYSTEM_CRITICAL,
)
from desktop_agent.registry import PermissionManager
from desktop_agent.main import CommandDispatcher


class MockExecuteRequest:
    def __init__(self, tool: str, args: dict | None = None):
        self.tool = tool
        self.args = args or {}


# ---------------------------------------------------------------------------
# Classification & permission model
# ---------------------------------------------------------------------------


def test_power_tools_classified_system_critical():
    assert TOOL_CATEGORIES["requestPowerAction"] == SYSTEM_CRITICAL
    assert TOOL_CATEGORIES["executePowerAction"] == SYSTEM_CRITICAL


def test_power_tools_policy_stays_allow_for_internal_token_flow():
    # The internal two-step token flow (tools_confirmation) is the single gate,
    # so the permission policy is intentionally left "allow".
    assert TOOL_OVERRIDES["requestPowerAction"] == "allow"
    assert TOOL_OVERRIDES["executePowerAction"] == "allow"
    for tool in ("requestPowerAction", "executePowerAction"):
        decision = PermissionManager.check(tool, {"action": "shutdown"})
        assert decision.allowed is True
        assert decision.category == SYSTEM_CRITICAL


def test_dangerous_actions_are_whitelisted_only():
    # hibernate/logoff are NOT power tools by design -> they must be refused.
    assert "hibernate" not in DANGEROUS_ACTIONS
    assert "logoff" not in DANGEROUS_ACTIONS


# ---------------------------------------------------------------------------
# Simulated execution — no real OS command ever runs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", sorted(DANGEROUS_ACTIONS))
def test_run_power_simulated_in_test_mode(action):
    """MYRAA_TEST_MODE=true -> simulated result, no OS call."""
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "true"}):
        with mock.patch("subprocess.run") as run, \
             mock.patch("os.system") as system:
            result = _run_power(action)
            assert result == f"[TEST MODE] Power action '{action}' blocked. No OS power command executed."
            run.assert_not_called()
            system.assert_not_called()


@pytest.mark.parametrize("action", sorted(DANGEROUS_ACTIONS))
def test_run_power_blocked_without_allow_override(action):
    """No MYRAA_ALLOW_POWER_ACTIONS -> hard opt-in guard denies, no OS call."""
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false"}):
        with mock.patch("subprocess.run") as run, \
             mock.patch("os.system") as system:
            result = _run_power(action)
            assert "MYRAA_ALLOW_POWER_ACTIONS=1" in result
            run.assert_not_called()
            system.assert_not_called()


def test_run_power_shutdown_command_requested_when_allowed():
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("desktop_agent.tools_pc.subprocess.run") as run, \
             mock.patch("desktop_agent.tools_pc.os.system") as system:
            result = _run_power("shutdown")
            assert result == "Computer shutting down in 10 seconds."
            run.assert_called_once_with(["shutdown", "/s", "/t", "10"], check=False)
            system.assert_not_called()


def test_run_power_restart_command_requested_when_allowed():
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("desktop_agent.tools_pc.subprocess.run") as run, \
             mock.patch("desktop_agent.tools_pc.os.system") as system:
            result = _run_power("restart")
            assert result == "Computer restarting in 5 seconds."
            run.assert_called_once_with(["shutdown", "/r", "/t", "5"], check=False)
            system.assert_not_called()


def test_run_power_sleep_command_requested_when_allowed():
    # Windows sleep uses os.system("rundll32.exe powrprof.dll,SetSuspendState ...")
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("desktop_agent.tools_pc.subprocess.run") as run, \
             mock.patch("desktop_agent.tools_pc.os.system") as system:
            result = _run_power("sleep")
            assert result == "Computer going to sleep."
            system.assert_called_once()
            assert "SetSuspendState" in system.call_args[0][0]
            run.assert_not_called()


def test_run_power_lock_command_requested_when_allowed():
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("ctypes.windll.user32") as user32, \
             mock.patch("desktop_agent.tools_pc.subprocess.run") as run:
            result = _run_power("lock")
            assert result == "Computer locked."
            user32.LockWorkStation.assert_called_once()
            run.assert_not_called()


# ---------------------------------------------------------------------------
# Confirmation token flow — token creation is NOT human confirmation
# ---------------------------------------------------------------------------


def test_request_power_action_mints_token_without_executing():
    with mock.patch("subprocess.run") as run, \
         mock.patch("os.system") as system:
        req = MockExecuteRequest("requestPowerAction", {"action": "shutdown"})
        resp = CommandDispatcher.dispatch(req)
        assert resp.ok is True
        assert resp.result["requires_confirmation"] is True
        assert resp.result.get("action") == "shutdown"
        assert resp.result.get("token")
        run.assert_not_called()
        system.assert_not_called()


def test_execute_power_action_requires_valid_token():
    # No token at all -> refused before any OS interaction.
    with mock.patch("subprocess.run") as run, \
         mock.patch("os.system") as system:
        req = MockExecuteRequest("executePowerAction", {"action": "shutdown"})
        resp = CommandDispatcher.dispatch(req)
        assert resp.ok is False
        assert "token" in resp.error.lower()
        run.assert_not_called()
        system.assert_not_called()


def test_execute_power_action_rejects_wrong_action_token():
    token_req = MockExecuteRequest("requestPowerAction", {"action": "shutdown"})
    token_resp = CommandDispatcher.dispatch(token_req)
    token = token_resp.result["token"]

    with mock.patch("subprocess.run") as run, \
         mock.patch("os.system") as system:
        req = MockExecuteRequest(
            "executePowerAction",
            {"action": "restart", "execute_token": token},
        )
        resp = CommandDispatcher.dispatch(req)
        assert resp.ok is False
        run.assert_not_called()
        system.assert_not_called()


def test_execute_power_action_valid_token_requests_command_without_executing():
    token_req = MockExecuteRequest("requestPowerAction", {"action": "shutdown"})
    token_resp = CommandDispatcher.dispatch(token_req)
    token = token_resp.result["token"]

    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("desktop_agent.tools_pc.subprocess.run") as run, \
             mock.patch("desktop_agent.tools_pc.os.system") as system:
            req = MockExecuteRequest(
                "executePowerAction",
                {"action": "shutdown", "execute_token": token},
            )
            resp = CommandDispatcher.dispatch(req)
            assert resp.ok is True
            assert resp.result.get("action") == "shutdown"
            run.assert_called_once_with(["shutdown", "/s", "/t", "10"], check=False)
            system.assert_not_called()


# ---------------------------------------------------------------------------
# Unsupported power actions (hibernate/logoff) are refused safely
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["hibernate", "logoff"])
def test_unsupported_power_actions_refused(action):
    with mock.patch("subprocess.run") as run, \
         mock.patch("os.system") as system:
        req = MockExecuteRequest("executePowerAction", {"action": action})
        resp = CommandDispatcher.dispatch(req)
        assert resp.ok is False
        assert "Unknown power action" in resp.error
        run.assert_not_called()
        system.assert_not_called()


@pytest.mark.parametrize("action", ["hibernate", "logoff"])
def test_run_power_unsupported_action_raises(action):
    with mock.patch.dict(os.environ, {"MYRAA_TEST_MODE": "false", "MYRAA_ALLOW_POWER_ACTIONS": "1"}):
        with mock.patch("subprocess.run") as run, \
             mock.patch("os.system") as system:
            from desktop_agent.registry import ToolError
            with pytest.raises(ToolError):
                _run_power(action)
            run.assert_not_called()
            system.assert_not_called()