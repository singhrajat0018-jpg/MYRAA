from ..planner.models.action_types import ActionType

ACTION_TO_TOOL = {
    ActionType.OPEN_APPLICATION: "openApplication",
    ActionType.CLOSE_APPLICATION: "closeApplication",
    ActionType.OPEN_URL: "openWebsite",

    ActionType.TYPE_TEXT: "typeText",
    ActionType.PRESS_KEY: "pressKey",
    ActionType.HOTKEY: "hotkey",

    ActionType.CLICK: "leftClick",
    ActionType.DOUBLE_CLICK: "doubleClick",
    ActionType.RIGHT_CLICK: "rightClick",

    ActionType.CAPTURE_SCREEN: "takeScreenshot",
}