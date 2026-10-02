"""
MYRAA Recovery Manager

Attempts recovery after retries are exhausted.

Responsibilities
----------------
• Select recovery strategy
• Execute recovery
• Report recovery status
• Support custom recovery handlers
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any


logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    Handles automatic recovery after repeated failures.
    """

    def __init__(self):

        self._handlers: dict[str, Callable[..., bool]] = {}

    # ---------------------------------------------------------

    def register(
        self,
        tool_name: str,
        handler: Callable[..., bool],
    ) -> None:
        """
        Register a custom recovery function.
        """

        self._handlers[tool_name] = handler

    # ---------------------------------------------------------

    def unregister(
        self,
        tool_name: str,
    ) -> None:

        self._handlers.pop(tool_name, None)

    # ---------------------------------------------------------

    def has_handler(
        self,
        tool_name: str,
    ) -> bool:

        return tool_name in self._handlers

    # ---------------------------------------------------------

    def recover(
        self,
        tool_name: str,
        **kwargs,
    ) -> bool:
        """
        Execute recovery.
        """

        logger.info(
            "Recovery requested for '%s'",
            tool_name,
        )

        handler = self._handlers.get(tool_name)

        if handler is not None:

            try:

                result = handler(**kwargs)

                logger.info(
                    "Recovery result: %s",
                    result,
                )

                return bool(result)

            except Exception:

                logger.exception(
                    "Recovery handler failed."
                )

                return False

        return self.default_recovery(
            tool_name,
            **kwargs,
        )

    # ---------------------------------------------------------

    def default_recovery(
        self,
        tool_name: str,
        **kwargs,
    ) -> bool:
        """
        Generic recovery behaviour.

        Returns True only on the first 2 attempts; after that, returns False
        to prevent infinite retry loops on permanently-failing tools.
        """
        # Track attempts per tool to prevent infinite loops
        if not hasattr(self, "_default_recovery_counts"):
            self._default_recovery_counts = {}

        count = self._default_recovery_counts.get(tool_name, 0) + 1
        self._default_recovery_counts[tool_name] = count

        logger.info(
            "Default recovery for %s (attempt %d/3)",
            tool_name,
            count,
        )

        if count > 3:
            logger.warning(
                "Default recovery exhausted for %s after %d attempts",
                tool_name,
                count,
            )
            self._default_recovery_counts[tool_name] = 0
            return False

        try:
            time.sleep(min(count, 2))
            return True
        except Exception:
            logger.exception("Recovery sleep failed for %s", tool_name)
            return False

    # ---------------------------------------------------------

    def clear(self):

        self._handlers.clear()

    # ---------------------------------------------------------

    def available_handlers(self):

        return list(self._handlers.keys())

    # ---------------------------------------------------------

    def summary(self) -> dict[str, Any]:

        return {
            "registered_handlers": len(
                self._handlers
            ),
            "tools": list(
                self._handlers.keys()
            ),
        }