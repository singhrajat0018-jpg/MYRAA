"""
Keyboard controller tests (Part 4-6 restoration).

Previously a module-level script that OPENED NOTEPAD and TYPED at import
time. Now a proper pytest module covering the KeyboardController contract.
All real key/typing side effects are mocked so tests are deterministic and
never touch the live desktop. Live typing is covered by manual probes only.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from desktop_agent.desktop.input.keyboard import KeyboardController


class TestKeyboardController:

    def test_construction(self):
        kbd = KeyboardController()
        assert kbd.default_interval == 0.02

    def test_key_exists(self):
        kbd = KeyboardController()
        assert kbd.key_exists("enter") is True
        assert kbd.key_exists("a") is True
        assert kbd.key_exists("f1") is True
        assert kbd.key_exists("__not_a_real_key__") is False

    def test_function_key_valid_range_presses_f_key(self):
        kbd = KeyboardController()
        with patch.object(
            type(kbd),
            "press",
            return_value=True,
        ) as mock_press:
            assert kbd.function_key(1) is True
            mock_press.assert_called_once_with("f1")

    def test_function_key_out_of_range_raises(self):
        kbd = KeyboardController()
        with pytest.raises(ValueError):
            kbd.function_key(0)
        with pytest.raises(ValueError):
            kbd.function_key(13)

    def test_safe_press_rejects_unknown_key(self):
        kbd = KeyboardController()
        with pytest.raises(ValueError):
            kbd.safe_press("__not_a_real_key__")

    def test_safe_press_accepts_valid_key(self):
        kbd = KeyboardController()
        with patch.object(
            type(kbd),
            "press",
            return_value=True,
        ) as mock_press:
            assert kbd.safe_press("a") is True
            mock_press.assert_called_once_with("a")

    def test_type_text_delegates_to_pyautogui_write(self):
        kbd = KeyboardController()
        with patch("pyautogui.write") as mock_write:
            assert kbd.type_text("hello") is True
            mock_write.assert_called_once()

    def test_get_clipboard_returns_string(self):
        kbd = KeyboardController()
        with patch("pyperclip.paste", return_value=""):
            value = kbd.get_clipboard()
            assert isinstance(value, str)
