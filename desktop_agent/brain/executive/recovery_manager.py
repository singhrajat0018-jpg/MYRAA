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
        """

        logger.info(
            "Using default recovery for %s",
            tool_name,
        )

        try:

            # Small cooldown before next attempt
            time.sleep(1)

            return True

        except Exception:

            logger.exception(
                "Default recovery failed."
            )

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