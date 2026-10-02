"""Groww Session Management — detect and track Groww web session state.

Inspects page content and URLs to determine whether the user is logged in,
whether login/OTP/CAPTCHA is required, and provides URL construction helpers
for common Groww pages.
"""
from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Current state of the Groww web session."""

    UNKNOWN = "unknown"
    LOGGED_IN = "logged_in"
    LOGIN_REQUIRED = "login_required"
    OTP_PENDING = "otp_pending"
    CAPTCHA_PENDING = "captcha_pending"
    TWO_FA_PENDING = "two_fa_pending"
    SESSION_EXPIRED = "session_expired"
    ERROR = "error"


class GrowwSessionManager:
    """Manages detection and tracking of Groww web session state.

    Thread-safe singleton — all callers share the same session state.

    Usage::

        mgr = GrowwSessionManager()
        state = mgr.detect_session_state(page_content, url)
        if state == SessionState.LOGIN_REQUIRED:
            # prompt user to log in
            ...
    """

    GROWW_URLS: dict[str, str] = {
        "home": "https://groww.in",
        "portfolio": "https://groww.in/portfolio",
        "holdings": "https://groww.in/portfolio/holdings",
        "positions": "https://groww.in/portfolio/positions",
        "orders": "https://groww.in/orders",
        "watchlist": "https://groww.in/watchlist",
        "charts": "https://groww.in/stocks",
        "option_chain": "https://groww.in/options",
        "nifty": "https://groww.in/stocks/nifty-50",
    }

    GROWW_DOMAINS: frozenset[str] = frozenset({
        "groww.in",
        "www.groww.in",
        "app.groww.in",
    })

    _instance: Optional["GrowwSessionManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "GrowwSessionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._state = SessionState.UNKNOWN
                    inst._last_check_url: str = ""
                    inst._last_check_time: float = 0.0
                    inst._state_lock = threading.Lock()
                    cls._instance = inst
        return cls._instance

    def detect_session_state(self, page_content: str, url: str) -> SessionState:
        """Detect the current session state from page content and URL.

        Args:
            page_content: The HTML content of the current page.
            url: The current page URL.

        Returns:
            The detected SessionState.
        """
        normalised_content = page_content.lower()
        normalised_url = url.lower()

        state = SessionState.UNKNOWN

        if self.is_login_page(normalised_content):
            if self.requires_otp(normalised_content):
                state = SessionState.OTP_PENDING
            elif self.requires_captcha(normalised_content):
                state = SessionState.CAPTCHA_PENDING
            else:
                state = SessionState.LOGIN_REQUIRED
        elif "two-factor" in normalised_content or "2fa" in normalised_content or "two factor" in normalised_content:
            state = SessionState.TWO_FA_PENDING
        elif "session expired" in normalised_content or "session timed out" in normalised_content:
            state = SessionState.SESSION_EXPIRED
        elif self.is_dashboard(normalised_content):
            state = SessionState.LOGGED_IN
        elif self.is_groww_page(url):
            state = SessionState.UNKNOWN
        else:
            state = SessionState.UNKNOWN

        with self._state_lock:
            self._state = state
            self._last_check_url = url
            self._last_check_time = time.time()

        logger.debug("Session state detected: %s (url=%s)", state.value, url)
        return state

    def build_url(self, page_type: str, symbol: str | None = None) -> str:
        """Construct a Groww URL for a given page type.

        Args:
            page_type: One of the keys in GROWW_URLS (e.g. 'portfolio', 'charts').
            symbol: Optional stock symbol to append (e.g. 'RELIANCE').

        Returns:
            The fully constructed URL.

        Raises:
            ValueError: If page_type is not a known Groww page.
        """
        if page_type not in self.GROWW_URLS:
            raise ValueError(
                f"Unknown page_type '{page_type}'. "
                f"Valid types: {', '.join(sorted(self.GROWW_URLS))}"
            )
        base = self.GROWW_URLS[page_type]
        if symbol:
            normalised_symbol = symbol.strip().lower().replace(" ", "-")
            return f"{base}/{normalised_symbol}"
        return base

    def is_groww_page(self, url: str) -> bool:
        """Check whether a URL belongs to the Groww domain.

        Args:
            url: The URL to check.

        Returns:
            True if the URL host matches a known Groww domain.
        """
        normalised = url.lower()
        return any(domain in normalised for domain in self.GROWW_DOMAINS)

    def is_login_page(self, page_content: str) -> bool:
        """Detect whether the page content is a Groww login form.

        Args:
            page_content: The HTML content (should be lowercased).

        Returns:
            True if login form elements are detected.
        """
        login_indicators = [
            "login",
            "sign in",
            "log in",
            "enter your email",
            "enter your phone",
            "phone number",
            "email address",
            "password",
            "continue with",
            "google sign",
            "otp",
        ]
        indicator_count = sum(1 for indicator in login_indicators if indicator in page_content)
        return indicator_count >= 2

    def is_dashboard(self, page_content: str) -> bool:
        """Detect whether the page content is a Groww portfolio/dashboard.

        Args:
            page_content: The HTML content (should be lowercased).

        Returns:
            True if dashboard/portfolio elements are detected.
        """
        dashboard_indicators = [
            "portfolio",
            "holdings",
            "invested",
            "current value",
            "returns",
            "p&l",
            "profit",
            "loss",
            "dashboard",
            "net worth",
            "total investment",
        ]
        indicator_count = sum(1 for indicator in dashboard_indicators if indicator in page_content)
        return indicator_count >= 3

    def requires_otp(self, page_content: str) -> bool:
        """Detect whether an OTP input is present on the page.

        Args:
            page_content: The HTML content (should be lowercased).

        Returns:
            True if OTP input elements are detected.
        """
        otp_indicators = [
            "enter otp",
            "enter the otp",
            "verification code",
            "one time password",
            "otp verification",
            "verify otp",
            "resend otp",
        ]
        return any(indicator in page_content for indicator in otp_indicators)

    def requires_captcha(self, page_content: str) -> bool:
        """Detect whether a CAPTCHA challenge is present on the page.

        Args:
            page_content: The HTML content (should be lowercased).

        Returns:
            True if CAPTCHA elements are detected.
        """
        captcha_indicators = [
            "captcha",
            "verify you are human",
            "not a robot",
            "recaptcha",
            "human verification",
            "i'm not a robot",
        ]
        return any(indicator in page_content for indicator in captcha_indicators)

    def get_session_info(self) -> dict:
        """Return current session tracking information.

        Returns:
            Dictionary with state, last_check_url, and last_check_time.
        """
        with self._state_lock:
            return {
                "state": self._state.value,
                "last_check_url": self._last_check_url,
                "last_check_time": self._last_check_time,
            }

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Intended for testing only."""
        with cls._lock:
            cls._instance = None
