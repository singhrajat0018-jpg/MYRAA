"""
Test suite for the MYRAA_TEST_MODE + MYRAA_ALLOW_POWER_ACTIONS safety guards
in tools_pc.py.

Every test that would reach a real OS power command mocks subprocess/os.system
so the command is only asserted to have been REQUESTED — it is never executed.
"""
import os
import sys
import pytest
from unittest import mock

# Add the project root to the path so we can import desktop_agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from desktop_agent.tools_pc import _run_power


def test_shutdown_test_mode_true():
    """Test that shutdown is blocked when MYRAA_TEST_MODE=true."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'true'}):
        with mock.patch('subprocess.run') as mock_subprocess:
            result = _run_power('shutdown')
            assert result == "[TEST MODE] Power action 'shutdown' blocked. No OS power command executed."
            mock_subprocess.assert_not_called()


def test_shutdown_test_mode_1():
    """Test that shutdown is blocked when MYRAA_TEST_MODE=1."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': '1'}):
        with mock.patch('subprocess.run') as mock_subprocess:
            result = _run_power('shutdown')
            assert result == "[TEST MODE] Power action 'shutdown' blocked. No OS power command executed."
            mock_subprocess.assert_not_called()


def test_shutdown_test_mode_yes():
    """Test that shutdown is blocked when MYRAA_TEST_MODE=yes."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'yes'}):
        with mock.patch('subprocess.run') as mock_subprocess:
            result = _run_power('shutdown')
            assert result == "[TEST MODE] Power action 'shutdown' blocked. No OS power command executed."
            mock_subprocess.assert_not_called()


def test_restart_test_mode_true():
    """Test that restart is blocked when MYRAA_TEST_MODE=true."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'true'}):
        with mock.patch('subprocess.run') as mock_subprocess:
            result = _run_power('restart')
            assert result == "[TEST MODE] Power action 'restart' blocked. No OS power command executed."
            mock_subprocess.assert_not_called()


def test_sleep_test_mode_true():
    """Test that sleep is blocked when MYRAA_TEST_MODE=true."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'true'}):
        # Mock both os.system (Windows) and subprocess.run (non-Windows)
        with mock.patch('os.system') as mock_os_system, \
             mock.patch('subprocess.run') as mock_subprocess:
            result = _run_power('sleep')
            assert result == "[TEST MODE] Power action 'sleep' blocked. No OS power command executed."
            mock_os_system.assert_not_called()
            mock_subprocess.assert_not_called()


def test_lock_test_mode_true():
    """Test that lock is blocked when MYRAA_TEST_MODE=true."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'true'}):
        # Mock ctypes for lock
        with mock.patch('ctypes.windll') as mock_windll:
            result = _run_power('lock')
            assert result == "[TEST MODE] Power action 'lock' blocked. No OS power command executed."
            # The early return means the ctypes code is never reached.
            mock_windll.assert_not_called()


def test_actions_blocked_without_explicit_allow_override():
    """Power actions must be refused unless MYRAA_ALLOW_POWER_ACTIONS=1 is set.

    Even with MYRAA_TEST_MODE off, the hard opt-in guard denies execution.
    """
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'false'}):
        for action in ('shutdown', 'restart', 'sleep', 'lock'):
            with mock.patch('subprocess.run') as mock_subprocess, \
                 mock.patch('os.system') as mock_os_system:
                result = _run_power(action)
                assert "MYRAA_ALLOW_POWER_ACTIONS=1" in result
                mock_subprocess.assert_not_called()
                mock_os_system.assert_not_called()


def test_shutdown_command_requested_only_when_explicitly_allowed():
    """With MYRAA_ALLOW_POWER_ACTIONS=1 the command is REQUESTED (mocked), never run."""
    with mock.patch.dict(os.environ, {'MYRAA_TEST_MODE': 'false', 'MYRAA_ALLOW_POWER_ACTIONS': '1'}):
        with mock.patch('platform.system', return_value='Windows'):
            with mock.patch('subprocess.run') as mock_subprocess:
                result = _run_power('shutdown')
                mock_subprocess.assert_called_once_with(["shutdown", "/s", "/t", "10"], check=False)
                assert result == "Computer shutting down in 10 seconds."