from __future__ import annotations
import logging

from .route_result import RouteResult
from . import command_patterns as p
import re

log = logging.getLogger(__name__)

class IntentRouter:

    def route(self, text: str) -> RouteResult:
        log.debug("Input: %r", text)
        
        text = text.strip().lower()

        # Remove punctuation at the end
        text = re.sub(r"[.!?,;:]+$", "", text)

        match = p.YOUTUBE_SEARCH_PATTERN.match(text)

        if match:

            query = match.group(1).strip()

            log.debug("Matched: YOUTUBE SEARCH")

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
            log.debug("Matched: YOUTUBE")
            return RouteResult(
                handled=True,
                action="openWebsite",
                parameters={
                    "url": "https://www.youtube.com",
                },
            )

        if p.CHROME_PATTERN.match(text):
            log.debug("Matched: CHROME")
            return RouteResult(
                handled=True,
                action="openApplication",
                parameters={
                    "name": "Google Chrome",
                },
            )

        if p.NOTEPAD_PATTERN.match(text):
            log.debug("Matched: NOTEPAD")
            return RouteResult(
                handled=True,
                action="openApplication",
                parameters={
                    "name": "Notepad",
                },
            )

        if p.VSCODE_PATTERN.match(text):
            log.debug("Matched: VSCODE")
            return RouteResult(
                handled=True,
                action="openApplication",
                parameters={
                    "name": "Visual Studio Code",
                },
            )

        if p.DESKTOP_PATTERN.match(text):
            log.debug("Matched: DESKTOP")
            return RouteResult(
                handled=True,
                action="openFolder",
                parameters={
                    "name": "Desktop",
                },
            )

        if p.DOWNLOADS_PATTERN.match(text):
            log.debug("Matched: DOWNLOADS")
            return RouteResult(
                handled=True,
                action="openFolder",
                parameters={
                    "name": "Downloads",
                },
            )

        # --------------------------------------------------------------
        # Generic website open (single authority resolver).
        # "open gmail", "visit reddit", "go to chatgpt",
        # "open youtube in my browser" -> OPEN_URL with the canonical URL.
        # Applications above keep precedence, so "open chrome" stays an app.
        # --------------------------------------------------------------
        site = self._resolve_website(text)
        if site:
            log.debug("Matched: OPEN_WEBSITE %s", site)
            return RouteResult(
                handled=True,
                action="openWebsite",
                parameters={"url": site},
            )

        log.debug("No match")
        return RouteResult()

    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_website(text: str) -> str | None:
        """Resolve a website-open command through the ONE website resolver.

        The site table lives only in desktop_agent.tools_websites; this method
        never keeps its own copy of any alias.
        """
        match = p.OPEN_WEBSITE_PATTERN.match(text)
        if not match:
            return None
        candidate = p.BROWSER_CLAUSE_PATTERN.sub("", match.group(1)).strip()
        candidate = candidate.strip(" .,!?\"'")
        if not candidate:
            return None
        try:
            from desktop_agent.tools_websites import resolve_site
        except Exception:  # pragma: no cover - import guard
            return None
        return resolve_site(candidate)