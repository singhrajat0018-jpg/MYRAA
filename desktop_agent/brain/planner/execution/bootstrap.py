"""
MYRAA Execution Bootstrap

Registers all desktop action handlers.
"""

from __future__ import annotations

from .action_registry import ActionRegistry

from desktop_agent.desktop.input.mouse_bridge import (
    MouseToolBridge,
)

from desktop_agent.desktop.filesystem.file_bridge import (
    FileToolBridge,
)

from desktop_agent.desktop.applications.application_bridge import (
    ApplicationBridge,
)

from ..models.action_types import ActionType


class ExecutionBootstrap:

    def __init__(self):

        self.registry = ActionRegistry()

        self.mouse = MouseToolBridge()

        self.files = FileToolBridge()

        self.apps = ApplicationBridge()

    # --------------------------------------------------

    def build(self):

        self._register_mouse()

        self._register_files()

        self._register_apps()

        return self.registry

    # --------------------------------------------------

    def _register_mouse(self):

        self.registry.register(

            ActionType.CLICK,

            self.mouse.click,

        )

        self.registry.register(

            ActionType.DOUBLE_CLICK,

            self.mouse.double_click,

        )

        self.registry.register(

            ActionType.RIGHT_CLICK,

            self.mouse.right_click,

        )

        self.registry.register(

            ActionType.MOVE_MOUSE,

            self.mouse.move_mouse,

        )

        self.registry.register(

            ActionType.SCROLL,

            self.mouse.scroll,

        )

    # --------------------------------------------------
    # Mouse
    # --------------------------------------------------

    def _register_mouse(self):

        self.registry.register(
            ActionType.CLICK,
            self.mouse.click,
        )

        self.registry.register(
            ActionType.DOUBLE_CLICK,
            self.mouse.double_click,
        )

        self.registry.register(
            ActionType.RIGHT_CLICK,
            self.mouse.right_click,
        )

        self.registry.register(
            ActionType.MIDDLE_CLICK,
            self.mouse.middle_click,
        )

        self.registry.register(
            ActionType.MOVE_MOUSE,
            self.mouse.move_mouse,
        )

        self.registry.register(
            ActionType.DRAG,
            self.mouse.drag,
        )

        self.registry.register(
            ActionType.DROP,
            self.mouse.drop,
        )

        self.registry.register(
            ActionType.SCROLL_UP,
            lambda amount=1: self.mouse.scroll(
                "up",
                amount,
            ),
        )

        self.registry.register(
            ActionType.SCROLL_DOWN,
            lambda amount=1: self.mouse.scroll(
                "down",
                amount,
            ),
        )

        self.registry.register(
            ActionType.HOVER,
            self.mouse.hover,
        )

    # --------------------------------------------------
    # Applications
    # --------------------------------------------------

    def _register_apps(self):

        self.registry.register(
            ActionType.OPEN_APPLICATION,
            self.apps.open_application,
        )

        self.registry.register(
            ActionType.CLOSE_APPLICATION,
            self.apps.close_application,
        )

        self.registry.register(
            ActionType.ACTIVATE_WINDOW,
            self.apps.activate_window,
        )

        self.registry.register(
            ActionType.MINIMIZE_WINDOW,
            self.apps.minimize_window,
        )

        self.registry.register(
            ActionType.MAXIMIZE_WINDOW,
            self.apps.maximize_window,
        )

        self.registry.register(
            ActionType.RESTORE_WINDOW,
            self.apps.restore_window,
        )

    # --------------------------------------------------
    # File System
    # --------------------------------------------------

    def _register_files(self):

        self.registry.register(
            ActionType.CREATE_FILE,
            self.files.create_file,
        )

        self.registry.register(
            ActionType.CREATE_FOLDER,
            self.files.create_folder,
        )

        self.registry.register(
            ActionType.DELETE_FILE,
            self.files.delete_file,
        )

        self.registry.register(
            ActionType.MOVE_FILE,
            self.files.move_file,
        )

        self.registry.register(
            ActionType.COPY_FILE,
            self.files.copy_file,
        )

        self.registry.register(
            ActionType.OPEN_FILE,
            self.files.open_file,
        )

        self.registry.register(
            ActionType.SAVE_FILE,
            self.files.save_file,
        )

        self.registry.register(
            ActionType.READ_FILE,
            self.files.read_file,
        )

        self.registry.register(
            ActionType.RENAME_FILE,
            self.files.rename_file,
        )

        self.registry.register(
            ActionType.LIST_FILES,
            self.files.list_files,
        )