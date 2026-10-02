"""Fast path: bypass the full brain pipeline for known simple patterns.

Handles: "open X", "search Y", "what time is it", simple file reads, etc.
Sub-millisecond decision + direct tool dispatch.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class FastPathResult:
    matched: bool
    tool_name: str = ""
    args: dict = None
    confidence: float = 0.0
    decision_ms: float = 0.0

    def __post_init__(self):
        if self.args is None:
            self.args = {}


def _site_url(raw: str):
    """Resolve a spoken name through the ONE website table (tools_websites)."""
    try:
        from desktop_agent.tools_websites import resolve_site
    except Exception:  # pragma: no cover - import guard for standalone use
        return None
    return resolve_site(raw)


def _open_tool(m) -> str:
    """'open youtube' is a WEBSITE; 'open notepad' is an APPLICATION."""
    return "openWebsite" if _site_url(m.group(1)) else "openApplication"


def _open_arg(m) -> dict:
    url = _site_url(m.group(1))
    return {"url": url} if url else {"application": m.group(1)}


def _site_tool(m) -> str:
    return "openWebsite"


def _site_arg(m) -> dict:
    """Prefer the canonical URL for a known site, else pass the raw target."""
    return {"url": _site_url(m.group(1)) or m.group(1)}


PATTERNS = [
    # "open youtube" / "open notepad" — site vs application decided by the ONE
    # website resolver, never by a route that would send YouTube to the
    # application launcher.
    (r"^open (.+?)\s+in\s+(?:my|the|a)\s+browser$", _open_tool, _open_arg, 0.9),
    (r"^open (.+)$", _open_tool, _open_arg, 0.9),
    (r"^launch (.+)$", _open_tool, _open_arg, 0.9),
    (r"^open website (.+)$", _site_tool, _site_arg, 0.85),
    (r"^go to (.+)$", _site_tool, _site_arg, 0.8),
    (r"^visit (.+)$", _site_tool, _site_arg, 0.8),
    (r"^search (?:for )?(.+)$", "searchWeb", lambda m: {"query": m.group(1)}, 0.85),
    (r"^google (.+)$", "searchGoogle", lambda m: {"query": m.group(1)}, 0.9),
    (r"^youtube (.+)$", "searchYouTube", lambda m: {"query": m.group(1)}, 0.9),
    (r"^what time", "currentDateTime", lambda m: {}, 0.95),
    (r"^what.?s the time", "currentDateTime", lambda m: {}, 0.95),
    (r"^volume up$", "volumeUp", lambda m: {}, 0.95),
    (r"^volume down$", "volumeDown", lambda m: {}, 0.95),
    (r"^mute$", "muteToggle", lambda m: {}, 0.9),
    (r"^take a screenshot$", "takeScreenshot", lambda m: {}, 0.95),
    (r"^screenshot$", "takeScreenshot", lambda m: {}, 0.95),
    (r"^copy$", "copySelected", lambda m: {}, 0.9),
    (r"^paste$", "pasteClipboard", lambda m: {}, 0.9),
    (r"^minimize$", "minimizeWindow", lambda m: {}, 0.85),
    (r"^maximize$", "maximizeWindow", lambda m: {}, 0.85),
    (r"^close (?:window|app)$", "closeWindow", lambda m: {}, 0.8),
    (r"^switch to (.+)$", "switchApplication", lambda m: {"application": m.group(1)}, 0.85),
    (r"^list files$", "listFiles", lambda m: {}, 0.8),
    (r"^read file (.+)$", "readFile", lambda m: {"path": m.group(1)}, 0.85),
]


class FastPath:
    """Fast pattern matching for known simple commands."""

    def __init__(self, custom_patterns: Optional[list] = None):
        self._patterns = custom_patterns or PATTERNS

    def match(self, command: str) -> FastPathResult:
        start = time.perf_counter()
        normalized = command.strip().lower()
        for pattern, tool_name, arg_fn, confidence in self._patterns:
            m = re.match(pattern, normalized, re.IGNORECASE)
            if m:
                # A callable tool_name lets a pattern choose the tool from the
                # captured value (website vs application) at match time.
                resolved_tool = tool_name(m) if callable(tool_name) else tool_name
                elapsed = (time.perf_counter() - start) * 1000
                return FastPathResult(
                    matched=True, tool_name=resolved_tool,
                    args=arg_fn(m), confidence=confidence,
                    decision_ms=elapsed,
                )
        elapsed = (time.perf_counter() - start) * 1000
        return FastPathResult(matched=False, decision_ms=elapsed)

    def add_pattern(self, pattern: str, tool_name: str, arg_fn, confidence: float = 0.8):
        self._patterns.append((pattern, tool_name, arg_fn, confidence))

    def match_count(self) -> int:
        return len(self._patterns)
