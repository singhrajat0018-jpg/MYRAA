"""
MYRAA Vision V3
Semantic to UI Mapper

Maps SemanticNode roles to UIElementType for perception layer.
"""

from __future__ import annotations

from .fusion_engine import SemanticRole
from .ui_models import UIElementType


def map_semantic_role_to_ui_type(role: SemanticRole) -> UIElementType:
    """
    Map SemanticRole to UIElementType.

    This provides a canonical mapping between the internal semantic roles
    and the UI element types used in the perception layer.
    """
    mapping = {
        SemanticRole.UNKNOWN: UIElementType.UNKNOWN,
        SemanticRole.WINDOW: UIElementType.WINDOW,
        SemanticRole.PANEL: UIElementType.PANEL,
        SemanticRole.BUTTON: UIElementType.BUTTON,
        SemanticRole.ICON: UIElementType.ICON,
        SemanticRole.IMAGE: UIElementType.IMAGE,
        SemanticRole.LABEL: UIElementType.LABEL,
        SemanticRole.TEXT: UIElementType.TEXT,
        SemanticRole.TEXTBOX: UIElementType.TEXTBOX,
        SemanticRole.CHECKBOX: UIElementType.CHECKBOX,
        SemanticRole.RADIO: UIElementType.RADIO,
        SemanticRole.MENU: UIElementType.MENU,
        SemanticRole.MENU_ITEM: UIElementType.MENU_ITEM,
        SemanticRole.TAB: UIElementType.TAB,
        SemanticRole.TOOLBAR: UIElementType.TOOLBAR,
        SemanticRole.SIDEBAR: UIElementType.SIDEBAR,
        SemanticRole.HEADER: UIElementType.HEADER,
        SemanticRole.STATUSBAR: UIElementType.STATUSBAR,
        SemanticRole.LIST: UIElementType.LIST,
        SemanticRole.LIST_ITEM: UIElementType.LIST_ITEM,
        SemanticRole.TREE: UIElementType.TREE,
        SemanticRole.TREE_ITEM: UIElementType.TREE_ITEM,
        SemanticRole.TABLE: UIElementType.TABLE,
        SemanticRole.CELL: UIElementType.CELL,
        SemanticRole.LINK: UIElementType.LINK,
        SemanticRole.POPUP: UIElementType.POPUP,
        SemanticRole.DIALOG: UIElementType.DIALOG,
        SemanticRole.CONTENT: UIElementType.CONTENT,
    }

    return mapping.get(role, UIElementType.UNKNOWN)


def map_ui_type_to_semantic_role(ui_type: UIElementType) -> SemanticRole:
    """
    Map UIElementType to SemanticRole.

    Reverse mapping for when we need to convert back.
    """
    reverse_mapping = {
        UIElementType.UNKNOWN: SemanticRole.UNKNOWN,
        UIElementType.WINDOW: SemanticRole.WINDOW,
        UIElementType.PANEL: SemanticRole.PANEL,
        UIElementType.BUTTON: SemanticRole.BUTTON,
        UIElementType.ICON: SemanticRole.ICON,
        UIElementType.IMAGE: SemanticRole.IMAGE,
        UIElementType.LABEL: SemanticRole.LABEL,
        UIElementType.TEXT: SemanticRole.TEXT,
        UIElementType.TEXTBOX: SemanticRole.TEXTBOX,
        UIElementType.CHECKBOX: SemanticRole.CHECKBOX,
        UIElementType.RADIO: SemanticRole.RADIO,
        UIElementType.DROPDOWN: SemanticRole.RADIO,  # Map dropdown to radio for now
        UIElementType.MENU: SemanticRole.MENU,
        UIElementType.MENU_ITEM: SemanticRole.MENU_ITEM,
        UIElementType.TAB: SemanticRole.TAB,
        UIElementType.TOOLBAR: SemanticRole.TOOLBAR,
        UIElementType.SIDEBAR: SemanticRole.SIDEBAR,
        UIElementType.HEADER: SemanticRole.HEADER,
        UIElementType.STATUSBAR: SemanticRole.STATUSBAR,
        UIElementType.LIST: SemanticRole.LIST,
        UIElementType.LIST_ITEM: SemanticRole.LIST_ITEM,
        UIElementType.TREE: SemanticRole.TREE,
        UIElementType.TREE_ITEM: SemanticRole.TREE_ITEM,
        UIElementType.TABLE: SemanticRole.TABLE,
        UIElementType.CELL: SemanticRole.CELL,
        UIElementType.LINK: SemanticRole.LINK,
        UIElementType.POPUP: SemanticRole.POPUP,
        UIElementType.DIALOG: SemanticRole.DIALOG,
        UIElementType.CONTENT: SemanticRole.CONTENT,
        UIElementType.TEXTAREA: SemanticRole.TEXTBOX,  # Map textarea to textbox
        UIElementType.PLAYER_CONTROL: SemanticRole.ICON,  # Map player control to icon
        UIElementType.SCROLL_REGION: SemanticRole.UNKNOWN,  # No direct equivalent
        UIElementType.VIDEO: SemanticRole.IMAGE,  # Map video to image
    }

    return reverse_mapping.get(ui_type, SemanticRole.UNKNOWN)