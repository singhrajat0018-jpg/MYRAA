"""
MYRAA Trading Intelligence — Paper Trading Engine

Simulated order execution for strategy validation. All trades are
recorded to disk and never interact with any live broker.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.models import PaperTrade


_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_TRADES_FILE = _DATA_DIR / "paper_trades.json"


def _dt_from_iso(raw: Optional[str]) -> Optional[datetime]:
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _record_to_trade(rec: Dict[str, Any]) -> PaperTrade:
    return PaperTrade(
        trade_id=rec.get("trade_id", ""),
        symbol=rec.get("symbol", ""),
        direction=rec.get("direction", ""),
        entry_price=rec.get("entry_price", 0.0),
        quantity=rec.get("quantity", 0.0),
        entry_date=_dt_from_iso(rec.get("entry_date")) or datetime.utcnow(),
        exit_price=rec.get("exit_price", 0.0),
        exit_date=_dt_from_iso(rec.get("exit_date")),
        stop_loss=rec.get("stop_loss", 0.0),
        target=rec.get("target", 0.0),
        status=rec.get("status", "OPEN"),
        pnl=rec.get("pnl", 0.0),
        pnl_percent=rec.get("pnl_percent", 0.0),
        notes=rec.get("notes", ""),
        thesis_id=rec.get("thesis_id", ""),
    )


class PaperTrader:
    """Simulated trade execution engine.

    Opens and closes paper trades, persists them to JSON, and computes
    performance statistics. No live broker interaction occurs at any point.
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        self._file_path = Path(file_path) if file_path else _TRADES_FILE
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        if not self._file_path.exists():
            return []
        try:
            with open(self._file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, records: List[Dict[str, Any]]) -> None:
        with open(self._file_path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)

    def _find_idx(self, records: List[Dict[str, Any]], trade_id: str) -> Optional[int]:
        for i, r in enumerate(records):
            if r.get("trade_id") == trade_id:
                return i
        return None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        stop_loss: float = 0.0,
        target: float = 0.0,
        thesis_id: str = "",
        notes: str = "",
    ) -> PaperTrade:
        """Open a new paper trade.

        Parameters
        ----------
        symbol:
            Ticker symbol (e.g. "RELIANCE").
        direction:
            "LONG" or "SHORT".
        entry_price:
            Price at which the simulated entry occurs.
        quantity:
            Number of shares / lots.
        stop_loss:
            Stop-loss price (informational).
        target:
            Target price (informational).
        thesis_id:
            Optional link to a TradeThesis.
        notes:
            Free-form notes.

        Returns
        -------
        PaperTrade
            The newly created and persisted paper trade.
        """
        trade = PaperTrade(
            trade_id=f"PT-{uuid.uuid4().hex[:8]}",
            symbol=symbol.upper(),
            direction=direction.upper(),
            entry_price=entry_price,
            quantity=quantity,
            entry_date=datetime.utcnow(),
            stop_loss=stop_loss,
            target=target,
            status="OPEN",
            thesis_id=thesis_id,
            notes=notes,
        )

        records = self._load()
        records.append(trade.to_dict())
        self._save(records)
        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        notes: str = "",
    ) -> Optional[PaperTrade]:
        """Close an open paper trade at the given exit price.

        Returns the updated trade or ``None`` if the trade was not found.
        """
        records = self._load()
        idx = self._find_idx(records, trade_id)
        if idx is None:
            return None

        trade = _record_to_trade(records[idx])
        if trade.status != "OPEN":
            return trade

        trade.close(exit_price)
        if notes:
            trade.notes = notes

        records[idx] = trade.to_dict()
        self._save(records)
        return trade

    def get_open_trades(self) -> List[PaperTrade]:
        """Return all currently open paper trades."""
        records = self._load()
        return [
            _record_to_trade(r)
            for r in records
            if r.get("status") == "OPEN"
        ]

    def get_closed_trades(self) -> List[PaperTrade]:
        """Return all closed paper trades, most recent first."""
        records = self._load()
        closed = [
            _record_to_trade(r)
            for r in records
            if r.get("status") == "CLOSED"
        ]
        closed.sort(
            key=lambda t: t.exit_date or t.entry_date,
            reverse=True,
        )
        return closed

    def get_stats(self) -> Dict[str, Any]:
        """Compute aggregate performance statistics across all closed trades.

        Returns
        -------
        dict
            Keys: total_trades, winning_trades, losing_trades,
            win_rate, avg_win, avg_loss, avg_win_r, avg_loss_r,
            expectancy, profit_factor, max_win, max_loss, total_pnl.
        """
        closed = self.get_closed_trades()
        total = len(closed)
        if total == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "avg_win_r": 0.0,
                "avg_loss_r": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0,
                "total_pnl": 0.0,
            }

        winners = [t for t in closed if t.pnl > 0]
        losers = [t for t in closed if t.pnl < 0]
        breakeven = [t for t in closed if t.pnl == 0]

        win_count = len(winners)
        loss_count = len(losers)
        win_rate = win_count / total if total > 0 else 0.0

        avg_win = sum(t.pnl for t in winners) / win_count if win_count > 0 else 0.0
        avg_loss = sum(t.pnl for t in losers) / loss_count if loss_count > 0 else 0.0

        avg_win_r_pct = sum(t.pnl_percent for t in winners) / win_count if win_count > 0 else 0.0
        avg_loss_r_pct = sum(t.pnl_percent for t in losers) / loss_count if loss_count > 0 else 0.0

        total_win = sum(t.pnl for t in winners)
        total_loss = abs(sum(t.pnl for t in losers))
        profit_factor = total_win / total_loss if total_loss > 0 else float("inf") if total_win > 0 else 0.0

        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

        max_win = max((t.pnl for t in winners), default=0.0)
        max_loss = min((t.pnl for t in losers), default=0.0)
        total_pnl = sum(t.pnl for t in closed)

        return {
            "total_trades": total,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "breakeven_trades": len(breakeven),
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_win_r": round(avg_win_r_pct, 2),
            "avg_loss_r": round(avg_loss_r_pct, 2),
            "expectancy": round(expectancy, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
            "max_win": round(max_win, 2),
            "max_loss": round(max_loss, 2),
            "total_pnl": round(total_pnl, 2),
        }
