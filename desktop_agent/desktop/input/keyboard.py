"""
MYRAA Desktop Control V3

Keyboard Controller
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pyautogui
import pyperclip

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


@dataclass
class KeyStroke:
    key: str


class KeyboardController:

    def __init__(self):

        self.default_interval = 0.02

    # -------------------------------------------------
    # BASIC KEYS
    # -------------------------------------------------

    def press(
        self,
        key: str,
        presses: int = 1,
        interval: float = 0.05,
    ) -> bool:

        pyautogui.press(
            key,
            presses=presses,
            interval=interval,
        )

        return True

    def key_down(self, key: str) -> bool:

        pyautogui.keyDown(key)

        return True

    def key_up(self, key: str) -> bool:

        pyautogui.keyUp(key)

        return True

    # -------------------------------------------------
    # TEXT
    # -------------------------------------------------

    def type_text(
        self,
        text: str,
        interval: float | None = None,
    ) -> bool:

        pyautogui.write(
            text,
            interval=interval or self.default_interval,
        )

        return True

    def paste_text(
        self,
        text: str,
    ) -> bool:

        pyperclip.copy(text)

        pyautogui.hotkey("ctrl", "v")

        return True

    def enter(self):

        return self.press("enter")

    def tab(self):

        return self.press("tab")

    def esc(self):

        return self.press("esc")

    def backspace(self):

        return self.press("backspace")

    def delete(self):

        return self.press("delete")

    def space(self):

        return self.press("space")


        # -------------------------------------------------
    # HOTKEYS
    # -------------------------------------------------

    def hotkey(self, *keys: str) -> bool:
        """
        Press multiple keys together.
        Example:
            hotkey("ctrl", "c")
            hotkey("alt", "tab")
        """
        pyautogui.hotkey(*keys)
        return True

    # -------------------------------------------------
    # COMMON SHORTCUTS
    # -------------------------------------------------

    def copy(self) -> bool:
        return self.hotkey("ctrl", "c")

    def paste(self) -> bool:
        return self.hotkey("ctrl", "v")

    def cut(self) -> bool:
        return self.hotkey("ctrl", "x")

    def undo(self) -> bool:
        return self.hotkey("ctrl", "z")

    def redo(self) -> bool:
        return self.hotkey("ctrl", "y")

    def select_all(self) -> bool:
        return self.hotkey("ctrl", "a")

    def save(self) -> bool:
        return self.hotkey("ctrl", "s")

    def find(self) -> bool:
        return self.hotkey("ctrl", "f")

    def new_tab(self) -> bool:
        return self.hotkey("ctrl", "t")

    def close_tab(self) -> bool:
        return self.hotkey("ctrl", "w")

    def reopen_tab(self) -> bool:
        return self.hotkey("ctrl", "shift", "t")

    def refresh(self) -> bool:
        return self.press("f5")

    # -------------------------------------------------
    # WINDOWS SHORTCUTS
    # -------------------------------------------------

    def run_dialog(self) -> bool:
        """Win + R"""
        return self.hotkey("win", "r")

    def task_manager(self) -> bool:
        """Ctrl + Shift + Esc"""
        return self.hotkey("ctrl", "shift", "esc")

    def file_explorer(self) -> bool:
        """Win + E"""
        return self.hotkey("win", "e")

    def lock_pc(self) -> bool:
        """Win + L"""
        return self.hotkey("win", "l")

    def desktop(self) -> bool:
        """Win + D"""
        return self.hotkey("win", "d")

    def settings(self) -> bool:
        """Win + I"""
        return self.hotkey("win", "i")

    # -------------------------------------------------
    # WINDOW NAVIGATION
    # -------------------------------------------------

    def alt_tab(self) -> bool:
        return self.hotkey("alt", "tab")

    def next_tab(self) -> bool:
        return self.hotkey("ctrl", "tab")

    def previous_tab(self) -> bool:
        return self.hotkey("ctrl", "shift", "tab")

    def close_window(self) -> bool:
        return self.hotkey("alt", "f4")

    # -------------------------------------------------
    # FUNCTION KEYS
    # -------------------------------------------------

    def function_key(self, number: int) -> bool:
        """
        Press F1-F12
        """
        if number < 1 or number > 12:
            raise ValueError("Function key must be between 1 and 12.")

        return self.press(f"f{number}")


        # -------------------------------------------------
    # HUMAN TYPING
    # -------------------------------------------------

    def human_type(
        self,
        text: str,
        min_interval: float = 0.03,
        max_interval: float = 0.08,
    ) -> bool:
        """
        Type text with human-like random delays.
        """
        import random

        for ch in text:
            pyautogui.write(
                ch,
                interval=random.uniform(
                    min_interval,
                    max_interval,
                ),
            )

        return True

    # -------------------------------------------------
    # CLIPBOARD
    # -------------------------------------------------

    def get_clipboard(self) -> str:
        """Return current clipboard text."""
        return pyperclip.paste()

    def clear_clipboard(self) -> bool:
        """Clear clipboard contents."""
        pyperclip.copy("")
        return True

    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    def key_exists(
        self,
        key: str,
    ) -> bool:
        """Check whether PyAutoGUI recognizes the key."""
        return key in pyautogui.KEYBOARD_KEYS

    def safe_press(
        self,
        key: str,
    ) -> bool:

        if not self.key_exists(key):
            raise ValueError(f"Unsupported key: {key}")

        return self.press(key)

    # -------------------------------------------------
    # HOLD MULTIPLE KEYS
    # -------------------------------------------------

    def hold_keys(
        self,
        *keys: str,
    ) -> bool:

        for key in keys:
            self.key_down(key)

        return True

    def release_keys(
        self,
        *keys: str,
    ) -> bool:

        for key in reversed(keys):
            self.key_up(key)

        return True

    # -------------------------------------------------
    # DELAYS
    # -------------------------------------------------

    def wait(
        self,
        seconds: float,
    ) -> bool:

        time.sleep(seconds)

        return True

    # -------------------------------------------------
    # SAFETY
    # -------------------------------------------------

    def emergency_stop(self) -> None:
        """Enable PyAutoGUI fail-safe."""
        pyautogui.FAILSAFE = True

    def disable_failsafe(self) -> None:
        """Disable PyAutoGUI fail-safe."""
        pyautogui.FAILSAFE = False