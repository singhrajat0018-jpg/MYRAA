"""
Mouse tool bridge tests (Part 4-6 restoration).

Previously an async module-level script that MOVED THE REAL MOUSE at import
time (``await mouse.move_mouse(500, 300)``). Now a proper pytest module
verifying the bridge contract with the underlying MouseController mocked,
so no real cursor movement or clicks ever happen.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from desktop_agent.desktop.input.mouse_bridge import MouseToolBridge


def _run(coro):
    return asyncio.run(coro)


class TestMouseToolBridge:

    def test_construction(self):
        bridge = MouseToolBridge()
        assert bridge.mouse is not None

    def test_click_delegates_to_mouse(self):
        bridge = MouseToolBridge()
        with patch.object(
            type(bridge.mouse),
            "left_click",
            return_value=True,
        ) as mock_click:
            assert _run(bridge.click()) is True
            mock_click.assert_called_once()

    def test_click_at_coordinates(self):
        bridge = MouseToolBridge()
        with patch.object(
            type(bridge.mouse),
            "click_at",
            return_value=True,
        ) as mock_click_at:
            assert _run(bridge.click(100, 200)) is True
            mock_click_at.assert_called_once_with(100, 200)

    def test_move_mouse_delegates(self):
        bridge = MouseToolBridge()
        with patch.object(
            type(bridge.mouse),
            "move",
            return_value=True,
        ) as mock_move:
            assert _run(bridge.move_mouse(500, 300)) is True
            mock_move.assert_called_once_with(500, 300)

    def test_scroll_delegates(self):
        bridge = MouseToolBridge()
        with patch.object(
            type(bridge.mouse),
            "scroll_up",
            return_value=True,
        ) as mock_up, patch.object(
            type(bridge.mouse),
            "scroll_down",
            return_value=True,
        ) as mock_down:
            assert _run(bridge.scroll("up", 2)) is True
            mock_up.assert_called_once_with(2)
            assert _run(bridge.scroll("down", 3)) is True
            mock_down.assert_called_once_with(3)

    def test_hover_delegates(self):
        bridge = MouseToolBridge()
        with patch.object(
            type(bridge.mouse),
            "move",
            return_value=True,
        ) as mock_move:
            assert _run(bridge.hover(10, 20)) is True
            mock_move.assert_called_once_with(10, 20)

    def test_drop_returns_true(self):
        bridge = MouseToolBridge()
        assert _run(bridge.drop()) is True
