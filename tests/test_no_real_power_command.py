"""
Global safety regression: no automated test may ever execute a real
system-power command.

conftest.py installs a session-wide guard over subprocess.* and os.system that
fails any test the instant a real power command is attempted, and records every
attempt. This module:
  1. verifies the guard itself detects the known power command shapes,
  2. verifies the global test-mode guard is active for the whole suite,
  3. asserts the recorded power-command attempts list is empty (backstop).
"""
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import _POWER_CALLS, _is_power_command
from desktop_agent import tools_pc


def test_guard_detects_windows_power_commands():
    assert _is_power_command(["shutdown", "/s", "/t", "10"])
    assert _is_power_command(["shutdown", "/r", "/t", "5"])
    assert _is_power_command(["shutdown", "/a"])
    assert _is_power_command("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")


def test_guard_detects_cross_platform_and_shell_power_commands():
    assert _is_power_command(["shutdown", "-r", "now"])
    assert _is_power_command(["shutdown", "-h", "now"])
    assert _is_power_command(["systemctl", "suspend"])
    assert _is_power_command("powershell -Command Stop-Computer -Force")
    assert _is_power_command("powershell -Command Restart-Computer")
    assert _is_power_command("shutdown.exe /s /t 0")


def test_guard_does_not_block_benign_process_commands():
    assert not _is_power_command(["taskkill", "/IM", "notepad.exe"])
    assert not _is_power_command(["explorer", "C:\\temp"])
    assert not _is_power_command("python -m pytest tests")
    assert not _is_power_command(["node", "server.ts"])


def test_guard_intercepts_subprocess_run():
    from conftest import _guard, _guarded_run
    saved = list(_POWER_CALLS)
    try:
        # Benign commands pass the guard check untouched.
        _guard(["echo", "hello"])
        _guard("python -m pytest tests")
        # Power commands are blocked BEFORE any real process could start.
        with pytest.raises(AssertionError):
            _guard(["shutdown", "/s", "/t", "10"])
        with pytest.raises(AssertionError):
            _guarded_run(["shutdown", "/s", "/t", "10"])
    finally:
        # These were deliberate detection checks, not real attempts.
        _POWER_CALLS[:] = saved


def test_global_test_mode_is_enforced():
    assert os.environ.get("MYRAA_TEST_MODE", "").lower() in ("1", "true", "yes")


def test_power_tool_source_contains_both_guards():
    src = open(tools_pc.__file__, encoding="utf-8").read()
    assert "MYRAA_TEST_MODE" in src
    assert "MYRAA_ALLOW_POWER_ACTIONS" in src


def test_no_real_power_command_was_attempted():
    """Backstop: the session-wide power guard must not have caught anything."""
    assert _POWER_CALLS == [], (
        "A real system-power command was attempted during the test session: "
        f"{_POWER_CALLS}"
    )