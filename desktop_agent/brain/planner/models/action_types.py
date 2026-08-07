"""
MYRAA Planner

Action Type Definitions

Defines every executable planner action supported by the
Desktop Execution Engine.

All planner components should use this enum instead of
hardcoded action strings.
"""

from __future__ import annotations

from enum import Enum


class ActionType(str, Enum):
    """
    Supported planner actions.
    """

    # ---------------------------------------------------------
    # Mouse
    # ---------------------------------------------------------

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MIDDLE_CLICK = "middle_click"

    MOVE_MOUSE = "move_mouse"

    DRAG = "drag"
    DROP = "drop"

    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"

    HOVER = "hover"

    # ---------------------------------------------------------
    # Keyboard
    # ---------------------------------------------------------

    TYPE_TEXT = "type_text"

    PRESS_KEY = "press_key"

    HOTKEY = "hotkey"

    KEY_DOWN = "key_down"
    KEY_UP = "key_up"

    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------

    OPEN_APPLICATION = "open_application"

    CLOSE_APPLICATION = "close_application"

    ACTIVATE_WINDOW = "activate_window"

    MINIMIZE_WINDOW = "minimize_window"

    MAXIMIZE_WINDOW = "maximize_window"

    RESTORE_WINDOW = "restore_window"

    SWITCH_WINDOW = "switch_window"

    # ---------------------------------------------------------
    # Browser
    # ---------------------------------------------------------

    OPEN_URL = "open_url"

    NEW_TAB = "new_tab"

    CLOSE_TAB = "close_tab"

    SWITCH_TAB = "switch_tab"

    REFRESH_PAGE = "refresh_page"

    # ---------------------------------------------------------
    # Vision
    # ---------------------------------------------------------

    FIND_ELEMENT = "find_element"

    VERIFY_ELEMENT = "verify_element"

    VERIFY_SCREEN = "verify_screen"

    CAPTURE_SCREEN = "capture_screen"

    OCR_SCREEN = "ocr_screen"

    # ---------------------------------------------------------
    # Synchronization
    # ---------------------------------------------------------

    WAIT = "wait"

    WAIT_FOR_ELEMENT = "wait_for_element"

    WAIT_FOR_WINDOW = "wait_for_window"

    WAIT_FOR_SCREEN_CHANGE = "wait_for_screen_change"

    # ---------------------------------------------------------
    # System
    # ---------------------------------------------------------


    COPY = "copy"

    CUT = "cut"

    PASTE = "paste"

    UNDO = "undo"

    REDO = "redo"

    SELECT_ALL = "select_all"

    DELETE = "delete"

    # ---------------------------------------------------------
    # File System
    # ---------------------------------------------------------

    OPEN_FILE = "open_file"

    CREATE_FILE = "create_file"

    CREATE_FOLDER = "create_folder"

    DELETE_FILE = "delete_file"

    MOVE_FILE = "move_file"

    COPY_FILE = "copy_file"

    RENAME_FILE = "rename_file"

    SAVE_FILE = "save_file"

    CLOSE_FILE = "close_file"

    READ_FILE = "read_file"

    WRITE_FILE = "write_file"

    LIST_FILES = "list_files"

    FILE_EXISTS = "file_exists"

    TOOL_CALL = "tool_call"

    # ---------------------------------------------------------
    # Planner
    # ---------------------------------------------------------

    DECISION = "decision"

    BRANCH = "branch"

    LOOP = "loop"

    RETRY = "retry"

    VERIFY = "verify"

    COMPLETE = "complete"

    FAIL = "fail"

    # ---------------------------------------------------------
    # Custom
    # ---------------------------------------------------------

    CUSTOM = "custom"

    UNKNOWN = "unknown"

    @property
    def is_mouse_action(self) -> bool:
        return self in {
            self.CLICK,
            self.DOUBLE_CLICK,
            self.RIGHT_CLICK,
            self.MIDDLE_CLICK,
            self.MOVE_MOUSE,
            self.DRAG,
            self.DROP,
            self.SCROLL_UP,
            self.SCROLL_DOWN,
            self.HOVER,
        }

    @property
    def is_keyboard_action(self) -> bool:
        return self in {
            self.TYPE_TEXT,
            self.PRESS_KEY,
            self.HOTKEY,
            self.KEY_DOWN,
            self.KEY_UP,
        }

    @property
    def requires_verification(self) -> bool:
        return self in {
            self.CLICK,
            self.CREATE_FILE,
            self.CREATE_FOLDER,
            self.OPEN_FILE,
            self.SAVE_FILE,
            self.DELETE_FILE,
            self.MOVE_FILE,
            self.COPY_FILE,
            self.RENAME_FILE,
            self.WRITE_FILE,
            self.DOUBLE_CLICK,
            self.OPEN_APPLICATION,
            self.OPEN_URL,
            self.TYPE_TEXT,
            self.DELETE,
            self.PASTE,
        }

    @property
    def is_wait_action(self) -> bool:
        return self in {
            self.WAIT,
            self.WAIT_FOR_ELEMENT,
            self.WAIT_FOR_WINDOW,
            self.WAIT_FOR_SCREEN_CHANGE,
        }

    @property
    def is_terminal_action(self) -> bool:
        return self in {
            self.COMPLETE,
            self.FAIL,
        }