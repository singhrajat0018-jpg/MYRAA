"""
Finance Alert Engine

Converts stock analysis into ObserverEvents.
"""

from __future__ import annotations

from dataclasses import dataclass

from desktop_agent.brain.observer.event import (
    EventSeverity,
    EventType,
    ObserverEvent,
)

from ..analysis.stock_analyzer import StockAnalysis
from ..analysis.risk_engine import RiskResult


# ==========================================================
# Alert
# ==========================================================

@dataclass(slots=True)
class FinanceAlert:

    title: str

    message: str

    severity: EventSeverity

    should_notify: bool


# ==========================================================
# Engine
# ==========================================================

class FinanceAlertEngine:

    """
    Decides whether the Brain should be notified.
    """

    def create_alert(

        self,

        analysis: StockAnalysis,

        risk: RiskResult,

    ) -> FinanceAlert:

        # ----------------------------------------
        # Strong Up
        # ----------------------------------------

        if analysis.day_change >= 8:

            return FinanceAlert(

                title=f"{analysis.symbol} is surging",

                message=(
                    f"{analysis.symbol} moved "
                    f"{analysis.day_change:.2f}% today."
                ),

                severity=EventSeverity.HIGH,

                should_notify=True,

            )

        # ----------------------------------------
        # Strong Down
        # ----------------------------------------

        if analysis.day_change <= -8:

            return FinanceAlert(

                title=f"{analysis.symbol} is falling",

                message=(
                    f"{analysis.symbol} dropped "
                    f"{abs(analysis.day_change):.2f}% today."
                ),

                severity=EventSeverity.HIGH,

                should_notify=True,

            )

        # ----------------------------------------
        # High Risk
        # ----------------------------------------

        if risk.level == "HIGH":

            return FinanceAlert(

                title=f"High Risk: {analysis.symbol}",

                message=risk.reason,

                severity=EventSeverity.CRITICAL,

                should_notify=True,

            )

        # ----------------------------------------
        # Normal
        # ----------------------------------------

        return FinanceAlert(

            title=f"{analysis.symbol}",

            message="No important market movement.",

            severity=EventSeverity.INFO,

            should_notify=False,

        )

    # ------------------------------------------------------

    def to_event(

        self,

        analysis: StockAnalysis,

        risk: RiskResult,

    ) -> ObserverEvent | None:

        alert = self.create_alert(

            analysis,

            risk,

        )

        if not alert.should_notify:

            return None

        return ObserverEvent(

            source="Finance",

            event_type=EventType.STOCK,

            title=alert.title,

            message=alert.message,

            severity=alert.severity,

            data={

                "symbol": analysis.symbol,

                "price": analysis.current_price,

                "profit": analysis.profit_loss,

                "profit_percent": analysis.profit_percent,

                "day_change": analysis.day_change,

                "risk": risk.level,

            },

        )