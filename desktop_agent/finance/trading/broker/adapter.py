"""
MYRAA Trading Intelligence — Broker Adapter (READ-ONLY)

Provides a uniform interface to query account data, positions, and orders
from a connected broker. Execution methods are explicitly stubbed and
raise ``NotImplementedError`` — MYRAA never places live orders.

Security: This adapter never stores passwords, API secrets, or auth
tokens. Credentials are expected to be supplied at call time or read
from environment variables by the concrete implementation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.models import PortfolioPosition, PortfolioSnapshot


class BrokerAdapter:
    """Read-only broker interface.

    Intended to be subclassed for a specific broker (Zerodha, Groww, etc.).
    The base class returns empty/default data and refuses all execution.

    Security contract
    -----------------
    - Never stores passwords, API secrets, or auth tokens as attributes.
    - Never writes credentials to disk or logs.
    - Execution methods always raise NotImplementedError.
    """

    def __init__(self, broker_name: str = "unknown") -> None:
        self.broker_name = broker_name

    def is_connected(self) -> bool:
        """Check if broker is connected. Base implementation returns False."""
        return False

    # ------------------------------------------------------------------
    # read-only methods (safe to call)
    # ------------------------------------------------------------------

    def get_account(self) -> Dict[str, Any]:
        """Return account summary.

        Returns
        -------
        dict
            Keys: broker, balance, margin_used, margin_available,
            realized_pnl, unrealized_pnl, last_updated.
            All values are zero/empty in the base implementation.
        """
        return {
            "broker": self.broker_name,
            "balance": 0.0,
            "margin_used": 0.0,
            "margin_available": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "collateral": 0.0,
            "last_updated": datetime.utcnow().isoformat(),
        }

    def get_positions(self) -> List[PortfolioPosition]:
        """Return current open positions.

        Returns an empty list in the base implementation.
        """
        return []

    def get_orders(self) -> List[Dict[str, Any]]:
        """Return today's orders (filled, pending, cancelled, rejected).

        Returns an empty list in the base implementation.
        """
        return []

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Return the status of a specific order.

        Returns a not-found dict in the base implementation.
        """
        return {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "message": "No order matching this ID was found.",
            "broker": self.broker_name,
        }

    def sync_portfolio(self) -> PortfolioSnapshot:
        """Sync and return a full PortfolioSnapshot.

        In the base implementation returns an empty snapshot.
        Subclasses should fetch live positions, compute current prices,
        and populate the snapshot.
        """
        return PortfolioSnapshot(
            positions=[],
            cash=0.0,
            timestamp=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # execution methods — ALWAYS REFUSE
    # ------------------------------------------------------------------

    def prepare_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        order_type: str = "MARKET",
        price: float = 0.0,
        stop_loss: float = 0.0,
        target: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Prepare an order for execution.

        MYRAA does not execute live orders. This method exists only as a
        placeholder for future READ-ONLY order validation (e.g. checking
        margin, lot sizes) if ever needed.

        Raises
        ------
        NotImplementedError
            Always. MYRAA is an advisor, not an executor.
        """
        raise NotImplementedError(
            "Not wired to live broker — MYRAA never places orders. "
            "This is a safety boundary."
        )

    def execute_order(self, prepared_order: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a previously prepared order.

        Raises
        ------
        NotImplementedError
            Always. MYRAA never executes trades.
        """
        raise NotImplementedError(
            "Not wired to live broker — MYRAA never places orders. "
            "This is a safety boundary."
        )

    def verify_order(self, order_id: str) -> Dict[str, Any]:
        """Verify that an order was executed correctly.

        Raises
        ------
        NotImplementedError
            Always. MYRAA never places orders.
        """
        raise NotImplementedError(
            "Not wired to live broker — MYRAA never places orders. "
            "This is a safety boundary."
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order.

        Raises
        ------
        NotImplementedError
            Always. MYRAA never interacts with order systems.
        """
        raise NotImplementedError(
            "Not wired to live broker — MYRAA never places orders. "
            "This is a safety boundary."
        )
