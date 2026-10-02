"""
Hotkey manager tests (Part 4-6 restoration).

Previously a module-level script that EXECUTED THE REAL WINDOWS RUN DIALOG
(``safe_execute("run")`` → Win+R) at import time. Now a proper pytest module
covering the HotkeyManager registry contract with no real keyboard actions.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from desktop_agent.desktop.input.hotkeys import HotkeyManager


class TestHotkeyManager:

    def test_available_actions_returns_sorted_list(self):
        hotkeys = HotkeyManager()
        actions = hotkeys.available_actions()
        assert isinstance(actions, list)
        assert actions == sorted(actions)
        assert "run" in actions
        assert "copy" in actions
        assert "switch_window" in actions

    def test_has_action(self):
        hotkeys = HotkeyManager()
        assert hotkeys.has_action("run") is True
        assert hotkeys.has_action("RUN") is True
        assert hotkeys.has_action("__nope__") is False

    def test_execute_unknown_action_raises(self):
        hotkeys = HotkeyManager()
        with pytest.raises(ValueError):
            hotkeys.execute("__nope__")

    def test_safe_execute_blocks_unsafe_action(self):
        """task_manager is NOT in SAFE_ACTIONS -> must raise PermissionError."""
        hotkeys = HotkeyManager()
        with pytest.raises(PermissionError):
            hotkeys.safe_execute("task_manager")

    def test_safe_execute_dispatches_safe_action(self):
        """safe_execute("run") delegates to execute("run") — mocked so the
        real Win+R hotkey is never pressed."""
        hotkeys = HotkeyManager()
        with patch.object(
            hotkeys,
            "execute",
            return_value=True,
        ) as mock_execute:
            assert hotkeys.safe_execute("run") is True
            mock_execute.assert_called_once_with("run")

    def test_safe_actions_superset_covered(self):
        hotkeys = HotkeyManager()
        # Every safe action must exist in the registry
        for action in hotkeys.SAFE_ACTIONS:
            assert hotkeys.has_action(action) is True
