"""
MYRAA Desktop Control V3

Hotkey Manager

High-level keyboard actions.

Planner
    ↓
HotkeyManager
    ↓
KeyboardController
"""

from __future__ import annotations

from .keyboard import KeyboardController


class HotkeyManager:

    def __init__(self):

        self.keyboard = KeyboardController()

        self.registry = self._build_registry()

    # -------------------------------------------------
    # CLIPBOARD
    # -------------------------------------------------

    def copy(self):

        return self.keyboard.copy()

    def paste(self):

        return self.keyboard.paste()

    def cut(self):

        return self.keyboard.cut()

    def undo(self):

        return self.keyboard.undo()

    def redo(self):

        return self.keyboard.redo()

    def select_all(self):

        return self.keyboard.select_all()

    # -------------------------------------------------
    # TABS
    # -------------------------------------------------

    def new_tab(self):

        return self.keyboard.new_tab()

    def close_tab(self):

        return self.keyboard.close_tab()

    def reopen_tab(self):

        return self.keyboard.reopen_tab()

    def next_tab(self):

        return self.keyboard.next_tab()

    def previous_tab(self):

        return self.keyboard.previous_tab()

    def refresh(self):

        return self.keyboard.refresh()

        # -------------------------------------------------
    # WINDOWS
    # -------------------------------------------------

    def open_run(self):

        return self.keyboard.run_dialog()

    def open_file_explorer(self):

        return self.keyboard.file_explorer()

    def show_desktop(self):

        return self.keyboard.desktop()

    def open_settings(self):

        return self.keyboard.settings()

    def open_task_manager(self):

        return self.keyboard.task_manager()

    # -------------------------------------------------
    # WINDOW NAVIGATION
    # -------------------------------------------------

    def switch_window(self):

        return self.keyboard.alt_tab()

    def close_window(self):

        return self.keyboard.close_window()

    # -------------------------------------------------
    # FUNCTION KEYS
    # -------------------------------------------------

    def press_f1(self):

        return self.keyboard.function_key(1)

    def press_f2(self):

        return self.keyboard.function_key(2)

    def press_f3(self):

        return self.keyboard.function_key(3)

    def press_f4(self):

        return self.keyboard.function_key(4)

    def press_f5(self):

        return self.keyboard.function_key(5)

    def press_f6(self):

        return self.keyboard.function_key(6)

    def press_f7(self):

        return self.keyboard.function_key(7)

    def press_f8(self):

        return self.keyboard.function_key(8)

    def press_f9(self):

        return self.keyboard.function_key(9)

    def press_f10(self):

        return self.keyboard.function_key(10)

    def press_f11(self):

        return self.keyboard.function_key(11)

    def press_f12(self):

        return self.keyboard.function_key(12)

    # -------------------------------------------------
    # CUSTOM
    # -------------------------------------------------

    def execute_hotkey(self, *keys: str):

        return self.keyboard.hotkey(*keys)

        # -------------------------------------------------
    # ACTION REGISTRY
    # -------------------------------------------------

    def _build_registry(self):

        return {
            # Clipboard
            "copy": self.copy,
            "paste": self.paste,
            "cut": self.cut,
            "undo": self.undo,
            "redo": self.redo,
            "select_all": self.select_all,

            # Browser Tabs
            "new_tab": self.new_tab,
            "close_tab": self.close_tab,
            "reopen_tab": self.reopen_tab,
            "next_tab": self.next_tab,
            "previous_tab": self.previous_tab,
            "refresh": self.refresh,

            # Windows
            "run": self.open_run,
            "explorer": self.open_file_explorer,
            "settings": self.open_settings,
            "desktop": self.show_desktop,
            "task_manager": self.open_task_manager,

            # Navigation
            "switch_window": self.switch_window,
        }

    # -------------------------------------------------
    # EXECUTION
    # -------------------------------------------------

    def execute(self, action: str):

        registry = self._build_registry()

        action = action.lower().strip()

        if action not in registry:
            raise ValueError(f"Unknown hotkey action: {action}")

        return registry[action]()

    # -------------------------------------------------
    # INFORMATION
    # -------------------------------------------------

    def available_actions(self):

        return sorted(self._build_registry().keys())

    def has_action(self, action: str):

        return action.lower() in self._build_registry()

    # -------------------------------------------------
    # SAFE ACTIONS
    # -------------------------------------------------

    SAFE_ACTIONS = {
        "copy",
        "paste",
        "undo",
        "redo",
        "new_tab",
        "close_tab",
        "next_tab",
        "previous_tab",
        "refresh",
        "switch_window",
        "explorer",
        "run",
        "settings",
        "desktop",
    }

    def safe_execute(self, action: str):

        action = action.lower().strip()

        if action not in self.SAFE_ACTIONS:
            raise PermissionError(
                f"Blocked unsafe hotkey action: {action}"
            )

        return self.execute(action)