from __future__ import annotations

from .route_result import RouteResult
from . import command_patterns as p
import re

class IntentRouter:

    def route(self, text: str) -> RouteResult:
        print(f"[ROUTER] Input: {repr(text)}")
        
        text = text.strip().lower()

        # Remove punctuation at the end
        text = re.sub(r"[.!?,;:]+$", "", text)

        match = p.YOUTUBE_SEARCH_PATTERN.match(text)

        if match:

            query = match.group(1).strip()

            print("[ROUTER] Matched: YOUTUBE SEARCH")

            return RouteResult(

                handled=True,

                action="searchYouTube",

                parameters={

                    "query": query,

                },

            )

        if p.BROWSER_BACK_PATTERN.match(text):

            return RouteResult(
                handled=True,
                action="desktopBrowserGoBack",
                parameters={},
            )

        if p.BROWSER_FORWARD_PATTERN.match(text):

            return RouteResult(
                handled=True,
                action="desktopBrowserGoForward",
                parameters={},
            )

        if p.BROWSER_CLOSE_TAB_PATTERN.match(text):

            return RouteResult(
                handled=True,
                action="desktopBrowserCloseTab",
                parameters={},
            )

        if p.BROWSER_SCROLL_DOWN_PATTERN.match(text):

            return RouteResult(
                handled=True,
                action="desktopBrowserScroll",
                parameters={
                    "direction": "down",
                },
            )

        if p.BROWSER_SCROLL_UP_PATTERN.match(text):

            return RouteResult(
                handled=True,
                action="desktopBrowserScroll",
                parameters={
                    "direction": "up",
                },
            )

        if p.YOUTUBE_PATTERN.match(text):
            print("[ROUTER] Matched: YOUTUBE")
            return RouteResult(
                handled=True,
                action="openWebsite",
                parameters={
                    "url": "https://www.youtube.com",
                },
            )

        if p.CHROME_PATTERN.match(text):
            print("[ROUTER] Matched: CHROME")
            return RouteResult(
                handled=True,
                action="openApplication",
                parameters={
                    "name": "Google Chrome",
                },
            )

        if p.NOTEPAD_PATTERN.match(text):
            print("[ROUTER] Matched: NOTEPAD")
            return RouteResult(
                handled=True,
                action="openApplication",
                parameters={
                    "name": "Notepad",
                },
            )

        if p.VSCODE_PATTERN.match(text):
            print("[ROUTER] Matched: VSCODE")
            return RouteResult(
                handled=True,
                action="openApplication",
                parameters={
                    "name": "Visual Studio Code",
                },
            )

        if p.DESKTOP_PATTERN.match(text):
            print("[ROUTER] Matched: DESKTOP")
            return RouteResult(
                handled=True,
                action="openFolder",
                parameters={
                    "name": "Desktop",
                },
            )

        if p.DOWNLOADS_PATTERN.match(text):
            print("[ROUTER] Matched: DOWNLOADS")
            return RouteResult(
                handled=True,
                action="openFolder",
                parameters={
                    "name": "Downloads",
                },
            )
        print("[ROUTER] No match")
        return RouteResult()