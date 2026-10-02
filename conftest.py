"""MYRAA pytest root configuration (EPIC-09 + power-action safety).

Ensures the repository root is importable so the ``desktop_agent`` package
resolves regardless of the cwd pytest is launched from. Tests in this suite are
deterministic unit/integration tests that never touch the network, a live LLM,
or the desktop — providers/AIManager are mocked.

Safety hardening (power-action audit remediation):

1. ``MYRAA_TEST_MODE=true`` is forced for every test (and restored afterwards),
   so ``desktop_agent.tools_pc._run_power`` refuses to execute real OS power
   commands during automated runs.
2. A session-wide guard wraps ``subprocess.*`` and ``os.system``. Any attempt to
   run a real system-power command (shutdown/restart/sleep/hibernate/logoff/…)
   fails the test immediately and records the attempt. Tests must verify the
   command WOULD have been requested (mocks/spies), never execute it.
"""

from __future__ import annotations

import os
import subprocess as _subprocess
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Redirect pytest temp directory away from the system %TEMP% (which may be
# locked or permission-denied) to a project-local path.
import tempfile as _tempfile
_local_tmp = os.path.join(_REPO_ROOT, "tmp", "pytest-temp")
os.makedirs(_local_tmp, exist_ok=True)
os.environ["TEMP"] = _local_tmp
os.environ["TMP"] = _local_tmp
_tempfile.tempdir = None  # reset cached value so gettempdir() picks up new TEMP

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

for _secret_name in ("TAVILY_API_KEY",):
    os.environ[_secret_name] = ""

collect_ignore = [
    "tests/test_clipboard.py",
    "tests/test_config.py",
    "tests/test_filesystem.py",
    "tests/test_finance.py",
    "tests/test_keyboard.py",
    "tests/test_mouse.py",
    "tests/test_screenshot.py",
    "tests/test_windows.py",
    "tests/test_phase_4_provider_intelligence.py",
    "tests/test_f7_recovery.py",
    "tests/test_f8_telemetry.py",
    "tests/test_f9_health.py",
    "tests/test_f10_e2e.py",
    "tests/test_phase_e_performance.py",
    "tests/test_phase_g_self_healing.py",
    "tests/test_phase5_capability_routing.py",
    "tests/bench_models.py",
    "tests/test_fastpath.py",
    "desktop_agent/brain/planner/execution/tests/test_executor_bridge.py",
    "desktop_agent/brain/planner/execution/tests/test_file_adapter.py",
]


# ---------------------------------------------------------------------------
# Power-command guard
# ---------------------------------------------------------------------------

# Substrings that identify an OS power command regardless of casing. "restart"
# is intentionally absent as a bare token (it may appear in harmless names);
# Windows/Linux restart power commands all contain "shutdown" or "systemctl",
# which are matched above.
_POWER_PATTERNS = (
    "shutdown",
    "poweroff",
    "halt",
    "hibernate",
    "logoff",
    "suspend",
    "reboot",
    "powrprof",
    "setsuspendstate",
    "exitwindowsex",
    "initiatesystemshutdown",
    "stop-computer",
    "restart-computer",
)


def _cmd_to_string(command) -> str:
    if isinstance(command, str):
        return command
    if isinstance(command, (list, tuple)):
        return " ".join(str(part) for part in command)
    return str(command)


def _is_power_command(command) -> bool:
    lowered = _cmd_to_string(command).lower()
    return any(pattern in lowered for pattern in _POWER_PATTERNS)


# Every real power command attempted during the session (should stay empty).
_POWER_CALLS: list[str] = []


def _guard(command) -> None:
    if _is_power_command(command):
        _POWER_CALLS.append(_cmd_to_string(command))
        raise AssertionError(
            "[POWER GUARD] A real system-power command was attempted during "
            f"tests: {_cmd_to_string(command)!r}. Tests must mock/simulate power "
            "actions; they may never execute them. The OS was NOT touched."
        )


_REAL_SUBPROCESS_RUN = _subprocess.run
_REAL_SUBPROCESS_POPEN = _subprocess.Popen
_REAL_SUBPROCESS_CALL = _subprocess.call
_REAL_SUBPROCESS_CHECK_CALL = _subprocess.check_call
_REAL_SUBPROCESS_CHECK_OUTPUT = _subprocess.check_output
_REAL_OS_SYSTEM = os.system


def _guarded_run(*args, **kwargs):
    _guard(args[0] if args else "")
    return _REAL_SUBPROCESS_RUN(*args, **kwargs)


def _guarded_popen(*args, **kwargs):
    _guard(args[0] if args else "")
    return _REAL_SUBPROCESS_POPEN(*args, **kwargs)


def _guarded_call(*args, **kwargs):
    _guard(args[0] if args else "")
    return _REAL_SUBPROCESS_CALL(*args, **kwargs)


def _guarded_check_call(*args, **kwargs):
    _guard(args[0] if args else "")
    return _REAL_SUBPROCESS_CHECK_CALL(*args, **kwargs)


def _guarded_check_output(*args, **kwargs):
    _guard(args[0] if args else "")
    return _REAL_SUBPROCESS_CHECK_OUTPUT(*args, **kwargs)


def _guarded_system(command):
    _guard(command)
    return _REAL_OS_SYSTEM(command)


@pytest.fixture(autouse=True)
def _force_myraa_test_mode():
    """Force MYRAA_TEST_MODE=true for every test; restore after."""
    previous = os.environ.get("MYRAA_TEST_MODE")
    os.environ["MYRAA_TEST_MODE"] = "true"
    yield
    if previous is None:
        os.environ.pop("MYRAA_TEST_MODE", None)
    else:
        os.environ["MYRAA_TEST_MODE"] = previous


@pytest.fixture(scope="session", autouse=True)
def _power_command_guard():
    """Wrap subprocess/os.system for the whole session to block real power commands."""
    _POWER_CALLS.clear()
    _subprocess.run = _guarded_run
    _subprocess.Popen = _guarded_popen
    _subprocess.call = _guarded_call
    _subprocess.check_call = _guarded_check_call
    _subprocess.check_output = _guarded_check_output
    os.system = _guarded_system
    try:
        yield
    finally:
        _subprocess.run = _REAL_SUBPROCESS_RUN
        _subprocess.Popen = _REAL_SUBPROCESS_POPEN
        _subprocess.call = _REAL_SUBPROCESS_CALL
        _subprocess.check_call = _REAL_SUBPROCESS_CHECK_CALL
        _subprocess.check_output = _REAL_SUBPROCESS_CHECK_OUTPUT
        os.system = _REAL_OS_SYSTEM

# ---------------------------------------------------------------------------
# U.1.1: test isolation guard — deterministic cwd across tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_cwd_after_test():
    """Restore the working directory after every test.

    Any test that os.chdir()s without restoring would silently redirect
    relative-path tool calls (createFile "test.py", project builders, file
    workers) for every test that runs afterwards. This guard makes suite
    order irrelevant for cwd state.
    """
    original_cwd = os.getcwd()
    try:
        yield
    finally:
        try:
            os.chdir(original_cwd)
        except OSError:
            pass
