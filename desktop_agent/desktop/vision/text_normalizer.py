"""
MYRAA Vision V3
Text Normalizer

Handles text normalization and synonym mapping for target resolution.
Provides structured, testable synonym mappings for natural language understanding.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple
from enum import Enum


class NormalizedText(str, Enum):
    """Canonical normalized text forms for common UI elements."""

    # Input/Search variations
    SEARCH_INPUT = "SEARCH_INPUT"
    TEXT_INPUT = "TEXT_INPUT"
    PASSWORD_INPUT = "PASSWORD_INPUT"

    # Action/Button variations
    PLAY_CONTROL = "PLAY_CONTROL"
    PAUSE_CONTROL = "PAUSE_CONTROL"
    STOP_CONTROL = "STOP_CONTROL"
    SUBMIT_BUTTON = "SUBMIT_BUTTON"
    CANCEL_BUTTON = "CANCEL_BUTTON"
    OK_BUTTON = "OK_BUTTON"
    CLOSE_BUTTON = "CLOSE_BUTTON"
    MENU_BUTTON = "MENU_BUTTON"
    HOME_BUTTON = "HOME_BUTTON"
    BACK_BUTTON = "BACK_BUTTON"
    FORWARD_BUTTON = "FORWARD_BUTTON"
    REFRESH_BUTTON = "REFRESH_BUTTON"
    DOWNLOAD_BUTTON = "DOWNLOAD_BUTTON"
    UPLOAD_BUTTON = "UPLOAD_BUTTON"
    SAVE_BUTTON = "SAVE_BUTTON"
    OPEN_BUTTON = "OPEN_BUTTON"
    NEW_BUTTON = "NEW_BUTTON"
    DELETE_BUTTON = "DELETE_BUTTON"
    EDIT_BUTTON = "EDIT_BUTTON"
    COPY_BUTTON = "COPY_BUTTON"
    PASTE_BUTTON = "PASTE_BUTTON"
    SEARCH_BUTTON = "SEARCH_BUTTON"
    FILTER_BUTTON = "FILTER_BUTTON"
    SORT_BUTTON = "SORT_BUTTON"

    # Navigation/Link variations
    HOME_LINK = "HOME_LINK"
    BACK_LINK = "BACK_LINK"
    FORWARD_LINK = "FORWARD_LINK"
    MENU_LINK = "MENU_LINK"
    SETTINGS_LINK = "SETTINGS_LINK"
    PROFILE_LINK = "PROFILE_LINK"
    LOGOUT_LINK = "LOGOUT_LINK"
    LOGIN_LINK = "LOGIN_LINK"
    SIGNIN_LINK = "SIGNIN_LINK"
    SIGNUP_LINK = "SIGNUP_LINK"

    # Generic UI elements
    CHECKBOX = "CHECKBOX"
    RADIO_BUTTON = "RADIO_BUTTON"
    DROPDOWN = "DROPDOWN"
    TAB = "TAB"
    LINK = "LINK"
    BUTTON = "BUTTON"
    INPUT = "INPUT"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    ICON = "ICON"


# Structured synonym mappings - keeps mappings organized and testable
SYNONYM_MAPPINGS: Dict[NormalizedText, List[str]] = {
    # Input/Search variations
    NormalizedText.SEARCH_INPUT: [
        "search bar", "search box", "search field", "search",
        "search here", "find", "lookup", "seek"
    ],

    NormalizedText.TEXT_INPUT: [
        "text box", "text field", "input box", "input field",
        "enter text", "type here", "write here"
    ],

    NormalizedText.PASSWORD_INPUT: [
        "password field", "password box", "enter password",
        "type password", "pwd field"
    ],

    # Action/Button variations
    NormalizedText.PLAY_CONTROL: [
        "play", "play button", "start", "start video", "begin",
        "play now", "▶️", "play icon"
    ],

    NormalizedText.PAUSE_CONTROL: [
        "pause", "pause button", "hold", "wait", "⏸️", "pause icon"
    ],

    NormalizedText.STOP_CONTROL: [
        "stop", "stop button", "end", "finish", "■️", "stop icon"
    ],

    NormalizedText.SUBMIT_BUTTON: [
        "submit", "submit button", "send", "send button",
        "go", "go button", "✓", "checkmark"
    ],

    NormalizedText.CANCEL_BUTTON: [
        "cancel", "cancel button", "abort", "quit", "✗", "x mark"
    ],

    NormalizedText.OK_BUTTON: [
        "ok", "okay", "ok button", "yes", "confirm", "✓"
    ],

    NormalizedText.CLOSE_BUTTON: [
        "close", "close button", "exit", "quit", "×", "x", "✕"
    ],

NormalizedText.LOGOUT_LINK: [
        "logout", "log out", "sign out", "🚪",
        "leave", "sign off"
    ],

    NormalizedText.MENU_BUTTON: [
        "menu", "menu button", "hamburger", "☰", "three lines",
        "hamburger icon", "menu icon"
    ],

    NormalizedText.HOME_BUTTON: [
        "home", "home button", "house", "🏠", "home icon",
        "start page", "main page"
    ],

    NormalizedText.BACK_BUTTON: [
        "back", "back button", "←", "arrow left", "go back",
        "previous", "back arrow"
    ],

    NormalizedText.FORWARD_BUTTON: [
        "forward", "forward button", "→", "arrow right",
        "go forward", "next", "forward arrow"
    ],

    NormalizedText.REFRESH_BUTTON: [
        "refresh", "refresh button", "reload", "⟳", "circular arrow",
        "update", "reload page"
    ],

    NormalizedText.DOWNLOAD_BUTTON: [
        "download", "download button", "save file", "⬇️", "down arrow",
        "get", "save"
    ],

    NormalizedText.UPLOAD_BUTTON: [
        "upload", "upload button", "add file", "⬆️", "up arrow",
        "attach", "send file"
    ],

    NormalizedText.SAVE_BUTTON: [
        "save", "save button", "store", "💾", "floppy disk",
        "keep", "persist"
    ],

    NormalizedText.OPEN_BUTTON: [
        "open", "open button", "launch", "start", "open file",
        "browse", "explore"
    ],

    NormalizedText.NEW_BUTTON: [
        "new", "new button", "create", "plus", "+", "add",
        "new file", "document"
    ],

    NormalizedText.DELETE_BUTTON: [
        "delete", "delete button", "remove", "trash", "🗑️",
        "del", "erase", "cancel"
    ],

    NormalizedText.EDIT_BUTTON: [
        "edit", "edit button", "modify", "change", "✎", "pencil",
        "pencil icon", "alter"
    ],

    NormalizedText.COPY_BUTTON: [
        "copy", "copy button", "duplicate", "📋", "clipboard",
        "copy text", "copy selection"
    ],

    NormalizedText.PASTE_BUTTON: [
        "paste", "paste button", "insert", "📋", "clipboard",
        "paste text", "paste selection"
    ],

    NormalizedText.SEARCH_BUTTON: [
        "search button", "search icon", "magnifying glass", "🔍",
        "find button", "lookup"
    ],

    NormalizedText.FILTER_BUTTON: [
        "filter", "filter button", "sort", "funnel", "⏚",
        "filter options", "refine"
    ],

    NormalizedText.SORT_BUTTON: [
        "sort", "sort button", "order", "arrange", "🔀",
        "sort by", "organize"
    ],

    # Navigation/Link variations
    NormalizedText.HOME_LINK: [
        "home link", "homepage", "main page", "start",
        "go home", "return home"
    ],

    NormalizedText.BACK_LINK: [
        "back link", "previous page", "go back", "return",
        "back page", "← link"
    ],

    NormalizedText.FORWARD_LINK: [
        "forward link", "next page", "go forward", "continue",
        "forward page", "→ link"
    ],

    NormalizedText.MENU_LINK: [
        "menu link", "navigation", "nav", "menu", "☰ link"
    ],

    NormalizedText.SETTINGS_LINK: [
        "settings", "settings link", "preferences", "options",
        "configure", "setup", "⚙️", "gear icon"
    ],

    NormalizedText.PROFILE_LINK: [
        "profile", "profile link", "account", "user", "👤",
        "my account", "user profile"
    ],

    NormalizedText.LOGOUT_LINK: [
        "logout", "log out", "sign out", "exit", "🚪",
        "leave", "sign off"
    ],

    NormalizedText.LOGIN_LINK: [
        "login", "log in", "sign in", "enter", "🔑",
        "enter account", "access"
    ],

    NormalizedText.SIGNIN_LINK: [
        "sign in", "signin", "login", "log in", "enter",
        "access account", "signin"
    ],

    NormalizedText.SIGNUP_LINK: [
        "sign up", "signup", "register", "create account",
        "join", "new account", "register"
    ],

    # Generic UI elements (fallback categories)
    NormalizedText.BUTTON: [
        "button", "btn", "click", "press", "tap"
    ],

    NormalizedText.INPUT: [
        "input", "field", "box", "entry", "type here"
    ],

    NormalizedText.TEXT: [
        "text", "label", "caption", "heading", "title"
    ],

    NormalizedText.IMAGE: [
        "image", "picture", "photo", "pic", "img", "visual"
    ],

    NormalizedText.ICON: [
        "icon", "symbol", "glyph", "mark", "indicator"
    ]
}

# Reverse mapping for quick lookup: synonym -> normalized form
SYNONYM_TO_NORMALIZED: Dict[str, NormalizedText] = {}

# Build reverse mapping on module import
for normalized_form, synonyms in SYNONYM_MAPPINGS.items():
    for synonym in synonyms:
        SYNONYM_TO_NORMALIZED[synonym.lower()] = normalized_form


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison by removing punctuation, extra whitespace,
    and converting to lowercase.

    Args:
        text: Input text to normalize

    Returns:
        Normalized text string
    """
    if not text:
        return ""

    # Convert to lowercase
    normalized = text.lower()

    # Remove punctuation and extra whitespace
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def get_normalized_form(text: str) -> NormalizedText:
    """
    Get the canonical normalized form for a given text description.

    Args:
        text: Input text description (e.g., "search bar", "play button")

    Returns:
        NormalizedText enum value, or NormalizedText.TEXT as fallback
    """
    if not text:
        return NormalizedText.TEXT

    normalized_input = normalize_text(text)

    # Direct lookup in synonym map
    if normalized_input in SYNONYM_TO_NORMALIZED:
        return SYNONYM_TO_NORMALIZED[normalized_input]

    # Check if any synonym is contained in the text (for partial matches)
    for synonym, normalized_form in SYNONYM_TO_NORMALIZED.items():
        if synonym in normalized_input:
            return normalized_form

    # Fallback based on common UI element detection
    text_lower = text.lower()
    if any(word in text_lower for word in ["button", "btn"]):
        return NormalizedText.BUTTON
    elif any(word in text_lower for word in ["input", "field", "box"]):
        return NormalizedText.INPUT
    elif any(word in text_lower for word in ["text", "label"]):
        return NormalizedText.TEXT
    elif any(word in text_lower for word in ["image", "picture", "photo"]):
        return NormalizedText.IMAGE
    elif any(word in text_lower for word in ["icon", "symbol"]):
        return NormalizedText.ICON
    elif any(word in text_lower for word in ["link", "href"]):
        return NormalizedText.LINK
    else:
        return NormalizedText.TEXT  # Default fallback


def is_synonym_match(text1: str, text2: str) -> bool:
    """
    Check if two text descriptions are synonymous based on our mappings.

    Args:
        text1: First text description
        text2: Second text description

    Returns:
        True if texts are considered synonymous, False otherwise
    """
    if not text1 or not text2:
        return False

    norm1 = get_normalized_form(text1)
    norm2 = get_normalized_form(text2)

    return norm1 == norm2


def get_all_synonyms(normalized_form: NormalizedText) -> List[str]:
    """
    Get all synonyms for a given normalized form.

    Args:
        normalized_form: NormalizedText enum value

    Returns:
        List of synonymous phrases
    """
    return SYNONYM_MAPPINGS.get(normalized_form, []).copy()


# Hindi/Hinglish ordinal mappings
HINDI_ORDINAL_MAP: Dict[str, int] = {
    "pehla": 1, "pehla wala": 1,
    "doosra": 2, "doosra wala": 2, "dusra": 2, "dusra wala": 2,
    "teesra": 3, "teesra wala": 3, "tesra": 3, "tesra wala": 3,
    "chautha": 4, "chautha wala": 4,
    "paanchva": 5, "paanchva wala": 5, "panchva": 5, "panchva wala": 5
}

# English ordinal mappings
ENGLISH_ORDINAL_MAP: Dict[str, int] = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5
}

# Combined ordinal map
ORDINAL_MAP: Dict[str, int] = {**HINDI_ORDINAL_MAP, **ENGLISH_ORDINAL_MAP}


def extract_ordinal(text: str) -> Optional[int]:
    """
    Extract ordinal number from text description.

    Args:
        text: Input text that may contain ordinal reference

    Returns:
        Ordinal number (1-based) if found, None otherwise
    """
    if not text:
        return None

    text_lower = text.lower().strip()

    # Direct lookup
    if text_lower in ORDINAL_MAP:
        return ORDINAL_MAP[text_lower]

    # Check for ordinals as part of larger text
    for ordinal_word, ordinal_num in ORDINAL_MAP.items():
        if ordinal_word in text_lower:
            # Make sure it's a word boundary match to avoid false positives
            # Simple check: if surrounded by spaces or at beginning/end
            pattern = r'(?:^|\s)' + re.escape(ordinal_word) + r'(?:\s|$)'
            if re.search(pattern, text_lower):
                return ordinal_num

    return None