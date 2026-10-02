"""
Mouse controller tests (Part 4-6 restoration).

Previously a module-level script that MOVED THE REAL MOUSE at import time.
Now a proper pytest module that tests the MouseController contract without
performing destructive desktop input. Real mouse movement requires a live
session; it is covered by the interactive/manual probe, not automated tests.
"""

from __future__ import annotations

import pytest

from desktop_agent.desktop.input.mouse import MouseController, MousePosition


class TestMouseController:

    def test_position_returns_mouse_position(self):
        mouse = MouseController()
        pos = mouse.position()
        assert isinstance(pos, MousePosition)
        assert hasattr(pos, "x")
        assert hasattr(pos, "y")

    def test_screen_size_returns_positive_dimensions(self):
        mouse = MouseController()
        width, height = mouse.screen_size()
        assert width > 0
        assert height > 0

    def test_is_inside_screen(self):
        mouse = MouseController()
        width, height = mouse.screen_size()
        assert mouse.is_inside_screen(0, 0) is True
        assert mouse.is_inside_screen(width - 1, height - 1) is True
        assert mouse.is_inside_screen(-1, 10) is False
        assert mouse.is_inside_screen(10, -1) is False
        assert mouse.is_inside_screen(width + 5, 10) is False
        assert mouse.is_inside_screen(10, height + 5) is False

    def test_validate_position_uses_is_inside_screen(self):
        mouse = MouseController()
        width, height = mouse.screen_size()
        assert mouse.validate_position(width // 2, height // 2) is True
        assert mouse.validate_position(-50, -50) is False

    def test_safe_move_rejects_out_of_bounds(self):
        """safe_move must NOT touch the real mouse for invalid coordinates."""
        mouse = MouseController()
        assert mouse.safe_move(-100, -100) is False

    def test_emergency_stop_keeps_failsafe_enabled(self):
        mouse = MouseController()
        mouse.emergency_stop()
        import pyautogui
        assert pyautogui.FAILSAFE is True
