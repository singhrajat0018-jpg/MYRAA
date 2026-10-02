"""Financial Action Blocking — hard enforcement of READ-ONLY policy.

This module is the authoritative gate that prevents MYRAA from ever executing
trades, placing orders, or performing any write action on Groww. Every click
and navigation must pass through this blocker before execution.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlockedAction:
    """Record of a blocked financial action attempt."""

    action_type: str
    element_text: str
    url: str
    timestamp: float
    blocked_reason: str


class TradingAdvisorPolicy:
    """Policy engine that determines which Groww interactions are allowed.

    This class encodes the hard boundary: MYRAA is an advisor, not a broker.
    Any action that could result in a financial transaction is blocked.

    Thread-safe singleton — all instances share the same blocked history.
    """

    BLOCKED_ACTIONS: frozenset[str] = frozenset({
        "buy",
        "sell",
        "square off",
        "square-off",
        "cancel order",
        "cancel",
        "modify order",
        "modify",
        "submit order",
        "place order",
        "confirm order",
        "confirm",
        "pay",
        "pay now",
    })

    BLOCKED_SELECTORS: list[str] = [
        "button:has-text('Buy')",
        "button:has-text('Sell')",
        "button:has-text('Place Order')",
        "button:has-text('Submit')",
        "button:has-text('Confirm')",
        "button:has-text('Pay')",
        "[data-testid*='buy']",
        "[data-testid*='sell']",
        ".place-order-btn",
        ".submit-order-btn",
    ]

    READ_ONLY_PAGES: frozenset[str] = frozenset({
        "portfolio",
        "holdings",
        "positions",
        "watchlist",
        "charts",
        "option-chain",
        "option_chain",
        "nifty",
    })

    _instance: Optional["TradingAdvisorPolicy"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "TradingAdvisorPolicy":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._blocked_history: list[BlockedAction] = []
                    inst._history_lock = threading.Lock()
                    cls._instance = inst
        return cls._instance

    def is_blocked(self, action_text: str) -> bool:
        """Check whether an action label is a blocked financial action.

        Args:
            action_text: The text or label of the action (e.g. button text).

        Returns:
            True if the action is blocked, False otherwise.
        """
        normalised = action_text.strip().lower()
        return normalised in self.BLOCKED_ACTIONS

    def is_blocked_selector(self, selector: str) -> bool:
        """Check whether a CSS selector matches a known blocked element.

        Args:
            selector: The CSS selector string.

        Returns:
            True if the selector is in the blocked list, False otherwise.
        """
        normalised = selector.strip().lower()
        return any(normalised == blocked.lower() for blocked in self.BLOCKED_SELECTORS)

    def check_click(
        self,
        url: str,
        selector: str,
        element_text: str,
    ) -> tuple[bool, Optional[BlockedAction]]:
        """Evaluate whether a click action should be allowed.

        Checks the element text and CSS selector against blocked patterns.

        Args:
            url: The current page URL.
            selector: The CSS selector of the element to click.
            element_text: The visible text of the element.

        Returns:
            A tuple of (allowed, blocked_info). If allowed is True, blocked_info
            is None. If allowed is False, blocked_info contains details about the
            blocked action.
        """
        now = time.time()

        if self.is_blocked(element_text):
            info = BlockedAction(
                action_type="click",
                element_text=element_text,
                url=url,
                timestamp=now,
                blocked_reason=f"Element text '{element_text}' matches a blocked financial action",
            )
            self._record_block(info)
            logger.warning(
                "BLOCKED click — element_text='%s' url='%s'",
                element_text,
                url,
            )
            return False, info

        if self.is_blocked_selector(selector):
            info = BlockedAction(
                action_type="click",
                element_text=element_text,
                url=url,
                timestamp=now,
                blocked_reason=f"Selector '{selector}' matches a blocked element pattern",
            )
            self._record_block(info)
            logger.warning(
                "BLOCKED click — selector='%s' url='%s'",
                selector,
                url,
            )
            return False, info

        return True, None

    def checkNavigation(self, url: str) -> tuple[bool, str]:
        """Check whether navigation to a URL is allowed under the read-only policy.

        Read-only pages (portfolio, holdings, charts, etc.) are allowed.
        Order placement pages are blocked.

        Args:
            url: The target URL.

        Returns:
            A tuple of (allowed, reason). If allowed is True, reason is empty.
        """
        normalised = url.lower()

        order_page_indicators = [
            "order",
            "place-order",
            "checkout",
            "payment",
            "confirm-order",
            "brokerage",
        ]

        for indicator in order_page_indicators:
            if indicator in normalised:
                reason = f"URL contains order/payment page indicator '{indicator}'"
                logger.warning("BLOCKED navigation — %s url='%s'", reason, url)
                return False, reason

        for page_type in self.READ_ONLY_PAGES:
            if page_type.replace("_", "-") in normalised or page_type.replace("-", "_") in normalised:
                return True, ""

        return True, ""

    def get_blocked_history(self) -> list[BlockedAction]:
        """Return a copy of the blocked action history.

        Returns:
            List of BlockedAction records, most recent last.
        """
        with self._history_lock:
            return list(self._blocked_history)

    def _record_block(self, action: BlockedAction) -> None:
        """Record a blocked action, maintaining a bounded history of 100 entries."""
        with self._history_lock:
            self._blocked_history.append(action)
            if len(self._blocked_history) > 100:
                self._blocked_history = self._blocked_history[-100:]

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Intended for testing only."""
        with cls._lock:
            cls._instance = None
