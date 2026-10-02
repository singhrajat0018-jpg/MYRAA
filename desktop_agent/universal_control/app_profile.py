"""App profiles: known application capabilities and control strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AppCapability(Enum):
    KEYBOARD_SHORTCUTS = "keyboard_shortcuts"
    MENU_SYSTEM = "menu_system"
    CONTEXT_MENUS = "context_menus"
    DRAG_DROP = "drag_drop"
    FORM_FILLING = "form_filling"
    TAB_NAVIGATION = "tab_navigation"
    TREE_NAVIGATION = "tree_navigation"
    SEARCH = "search"
    VOICE = "voice"
    SCRIPTING = "scripting"
    COMMAND_PALETTE = "command_palette"
    API_ACCESS = "api_access"
    AUTOMATION = "automation"


class ControlStrategy(Enum):
    KEYBOARD_FIRST = "keyboard_first"
    MOUSE_FIRST = "mouse_first"
    ACCESSIBILITY_FIRST = "accessibility_first"
    OCR_FIRST = "ocr_first"
    API_FIRST = "api_first"
    HYBRID = "hybrid"


@dataclass
class AppProfile:
    app_name: str
    display_name: str
    capabilities: list[AppCapability] = field(default_factory=list)
    preferred_strategy: ControlStrategy = ControlStrategy.HYBRID
    known_shortcuts: dict[str, str] = field(default_factory=dict)
    menu_structure: dict[str, list[str]] = field(default_factory=dict)
    common_elements: list[str] = field(default_factory=list)
    confidence: float = 0.8
    notes: str = ""

    def has_capability(self, cap: AppCapability) -> bool:
        return cap in self.capabilities

    def get_shortcut(self, action: str) -> Optional[str]:
        return self.known_shortcuts.get(action)


DEFAULT_PROFILES = {
    "chrome": AppProfile(
        app_name="chrome", display_name="Google Chrome",
        capabilities=[AppCapability.TAB_NAVIGATION, AppCapability.SEARCH,
                      AppCapability.CONTEXT_MENUS],
        preferred_strategy=ControlStrategy.KEYBOARD_FIRST,
        known_shortcuts={"new_tab": "ctrl+t", "close_tab": "ctrl+w",
                         "reload": "ctrl+r", "devtools": "f12",
                         "address_bar": "ctrl+l", "find": "ctrl+f"},
    ),
    "notepad": AppProfile(
        app_name="notepad", display_name="Notepad",
        capabilities=[AppCapability.KEYBOARD_SHORTCUTS],
        preferred_strategy=ControlStrategy.KEYBOARD_FIRST,
        known_shortcuts={"new": "ctrl+n", "open": "ctrl+o",
                         "save": "ctrl+s", "find": "ctrl+f"},
    ),
    "vscode": AppProfile(
        app_name="vscode", display_name="Visual Studio Code",
        capabilities=[AppCapability.KEYBOARD_SHORTCUTS, AppCapability.COMMAND_PALETTE,
                      AppCapability.TAB_NAVIGATION, AppCapability.TREE_NAVIGATION],
        preferred_strategy=ControlStrategy.KEYBOARD_FIRST,
        known_shortcuts={"command_palette": "ctrl+shift+p",
                         "quick_open": "ctrl+p", "terminal": "ctrl+`",
                         "save": "ctrl+s", "find": "ctrl+f"},
    ),
    "explorer": AppProfile(
        app_name="explorer", display_name="File Explorer",
        capabilities=[AppCapability.TREE_NAVIGATION, AppCapability.DRAG_DROP,
                      AppCapability.CONTEXT_MENUS, AppCapability.SEARCH],
        preferred_strategy=ControlStrategy.MOUSE_FIRST,
    ),
    "excel": AppProfile(
        app_name="excel", display_name="Microsoft Excel",
        capabilities=[AppCapability.KEYBOARD_SHORTCUTS, AppCapability.FORM_FILLING,
                      AppCapability.DRAG_DROP, AppCapability.SEARCH],
        preferred_strategy=ControlStrategy.KEYBOARD_FIRST,
        known_shortcuts={"new": "ctrl+n", "save": "ctrl+s",
                         "bold": "ctrl+b", "find": "ctrl+f"},
    ),
    "word": AppProfile(
        app_name="word", display_name="Microsoft Word",
        capabilities=[AppCapability.KEYBOARD_SHORTCUTS, AppCapability.FORM_FILLING,
                      AppCapability.DRAG_DROP, AppCapability.SEARCH],
        preferred_strategy=ControlStrategy.KEYBOARD_FIRST,
        known_shortcuts={"new": "ctrl+n", "save": "ctrl+s",
                         "bold": "ctrl+b", "find": "ctrl+f"},
    ),
    "teams": AppProfile(
        app_name="teams", display_name="Microsoft Teams",
        capabilities=[AppCapability.KEYBOARD_SHORTCUTS, AppCapability.SEARCH,
                      AppCapability.VOICE],
        preferred_strategy=ControlStrategy.HYBRID,
    ),
}


class AppProfileRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._profiles = dict(DEFAULT_PROFILES)
        return cls._instance

    def get(self, app_name: str) -> Optional[AppProfile]:
        return self._profiles.get(app_name.lower())

    def register(self, profile: AppProfile):
        self._profiles[profile.app_name.lower()] = profile

    def all_profiles(self) -> dict[str, AppProfile]:
        return dict(self._profiles)

    def find_profile(self, hint: str) -> Optional[AppProfile]:
        hint_lower = hint.lower()
        for name, profile in self._profiles.items():
            if hint_lower in name or hint_lower in profile.display_name.lower():
                return profile
        return None
