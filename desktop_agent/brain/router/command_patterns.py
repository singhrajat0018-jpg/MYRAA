from __future__ import annotations

import re

YOUTUBE_PATTERN = re.compile(
    r"^(open|launch)\s+(youtube)$",
    re.IGNORECASE,
)

CHROME_PATTERN = re.compile(
    r"^(open|launch)\s+(chrome|google chrome)$",
    re.IGNORECASE,
)

NOTEPAD_PATTERN = re.compile(
    r"^(open|launch)\s+(notepad)$",
    re.IGNORECASE,
)

VSCODE_PATTERN = re.compile(
    r"^(open|launch)\s+(vs code|visual studio code|code)$",
    re.IGNORECASE,
)

DESKTOP_PATTERN = re.compile(
    r"^(open)\s+desktop$",
    re.IGNORECASE,
)

DOWNLOADS_PATTERN = re.compile(
    r"^(open)\s+downloads$",
    re.IGNORECASE,
)

YOUTUBE_SEARCH_PATTERN = re.compile(
    r"^(?:search\s+(?:on\s+)?youtube|youtube\s+search)\s+(.+)$",
    re.IGNORECASE,
)

BROWSER_BACK_PATTERN = re.compile(
    r"^(go back|back)$",
    re.IGNORECASE,
)

BROWSER_FORWARD_PATTERN = re.compile(
    r"^(go forward|forward)$",
    re.IGNORECASE,
)

BROWSER_CLOSE_TAB_PATTERN = re.compile(
    r"^(close tab|close current tab)$",
    re.IGNORECASE,
)

BROWSER_SCROLL_DOWN_PATTERN = re.compile(
    r"^(scroll down)$",
    re.IGNORECASE,
)

BROWSER_SCROLL_UP_PATTERN = re.compile(
    r"^(scroll up)$",
    re.IGNORECASE,
)