"""
Stock Observer

Observes the user's portfolio through FinanceService.

The observer itself contains no finance business logic.
"""

from __future__ import annotations

import logging

from .base_observer import BaseObserver
from ..event import ObserverEvent

from desktop_agent.finance.finance_service import FinanceService

logger = logging.getLogger(__name__)


class StockObserver(BaseObserver):
    """
    Observer responsible for monitoring the user's
    investment portfolio.

    All finance processing is delegated to FinanceService.
    """

    def __init__(
        self,
        finance_service: FinanceService,
    ) -> None:

        super().__init__("StockObserver")

        self._finance_service = finance_service

    # ---------------------------------------------------------

    def poll(self) -> list[ObserverEvent]:
        """
        Poll the finance service for new portfolio events.
        """

        try:
            return self._finance_service.process()

        except Exception:
            logger.exception(
                "StockObserver polling failed."
            )
            return []