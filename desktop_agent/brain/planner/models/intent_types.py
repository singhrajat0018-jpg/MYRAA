from enum import Enum


class IntentType(str, Enum):
    OPEN_APPLICATION = "open_application"
    CLOSE_APPLICATION = "close_application"
    WEB_SEARCH = "web_search"
    OPEN_URL = "open_url"
    FILE_OPERATION = "file_operation"
    DESKTOP_ACTION = "desktop_action"
    KEYBOARD_ACTION = "keyboard_action"
    MOUSE_ACTION = "mouse_action"
    SYSTEM_CONTROL = "system_control"
    INFORMATION = "information"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"