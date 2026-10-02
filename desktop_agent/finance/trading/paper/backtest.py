"""
MYRAA Trading Intelligence — Backtest Foundation

Deterministic backtesting engine. Accepts historical OHLCV bars and a
user-supplied strategy function, simulates trades, and produces a
BacktestResult with full performance metrics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from desktop_agent.finance.trading.models import (
    BacktestResult,
    OHLCV,
    PaperTrade,
    Timeframe,
)


class Backtester:
    """Event-driven backtesting engine.

    The user provides a strategy function that inspects a slice of bars
    and returns entry signals. The backtester walks the bar series,
    opens/closes paper trades at the specified prices, and computes
    aggregate statistics.

    Strategy function signature::

        def strategy_fn(
            bars: List[OHLCV],
            idx: int,
        ) -> List[Tuple[int, str, float, float]]
            # Returns list of (bar_index, direction, stop_loss, target)
            # direction is "LONG" or "SHORT"
    """

    def run(
        self,
        symbol: str,
        bars: List[OHLCV],
        strategy_fn: Callable[[List[OHLCV], int], List[Tuple[int, str, float, float]]],
        timeframe: str = "1D",
        strategy_name: str = "custom",
        initial_capital: float = 100_000.0,
    ) -> BacktestResult:
        """Run a backtest over the supplied bars.

        Parameters
        ----------
        symbol:
            Ticker symbol for labeling.
        bars:
            Chronologically ordered OHLCV bars.
        strategy_fn:
            Callable that receives the full bar list and the current index,
            and returns a list of (entry_idx, direction, stop, target).
        timeframe:
            Human-readable timeframe label.
        strategy_name:
            Name used in the result.
        initial_capital:
            Starting capital (not yet used for sizing; reserved).

        Returns
        -------
        BacktestResult
            Fully computed result with trade list and stats.
        """
        if not bars:
            return BacktestResult(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow(),
            )

        trades: List[PaperTrade] = []
        open_positions: List[Dict] = []
        equity_curve: List[float] = [initial_capital]

        for i in range(len(bars)):
            bar = bars[i]

            # --- check stops / targets on open positions ---
            still_open: List[Dict] = []
            for pos in open_positions:
                hit_stop = False
                hit_target = False

                if pos["direction"] == "LONG":
                    if bar.low <= pos["stop_loss"]:
                        hit_stop = True
                    if bar.high >= pos["target"]:
                        hit_target = True
                else:  # SHORT
                    if bar.high >= pos["stop_loss"]:
                        hit_stop = True
                    if bar.low <= pos["target"]:
                        hit_target = True

                if hit_stop:
                    exit_price = pos["stop_loss"]
                    trade = PaperTrade(
                        trade_id=pos["trade_id"],
                        symbol=symbol,
                        direction=pos["direction"],
                        entry_price=pos["entry_price"],
                        quantity=pos["quantity"],
                        entry_date=pos["entry_date"],
                        exit_price=exit_price,
                        exit_date=bar.timestamp,
                        stop_loss=pos["stop_loss"],
                        target=pos["target"],
                        status="CLOSED",
                    )
                    if pos["direction"] == "LONG":
                        trade.pnl = (exit_price - pos["entry_price"]) * pos["quantity"]
                        trade.pnl_percent = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
                    else:
                        trade.pnl = (pos["entry_price"] - exit_price) * pos["quantity"]
                        trade.pnl_percent = ((pos["entry_price"] - exit_price) / pos["entry_price"]) * 100
                    trades.append(trade)
                    equity_curve.append(equity_curve[-1] + trade.pnl)
                elif hit_target:
                    exit_price = pos["target"]
                    trade = PaperTrade(
                        trade_id=pos["trade_id"],
                        symbol=symbol,
                        direction=pos["direction"],
                        entry_price=pos["entry_price"],
                        quantity=pos["quantity"],
                        entry_date=pos["entry_date"],
                        exit_price=exit_price,
                        exit_date=bar.timestamp,
                        stop_loss=pos["stop_loss"],
                        target=pos["target"],
                        status="CLOSED",
                    )
                    if pos["direction"] == "LONG":
                        trade.pnl = (exit_price - pos["entry_price"]) * pos["quantity"]
                        trade.pnl_percent = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
                    else:
                        trade.pnl = (pos["entry_price"] - exit_price) * pos["quantity"]
                        trade.pnl_percent = ((pos["entry_price"] - exit_price) / pos["entry_price"]) * 100
                    trades.append(trade)
                    equity_curve.append(equity_curve[-1] + trade.pnl)
                else:
                    still_open.append(pos)

            open_positions = still_open

            # --- query strategy for new entries ---
            try:
                signals = strategy_fn(bars, i)
            except Exception:
                signals = []

            if not isinstance(signals, list):
                signals = []

            for sig in signals:
                if not isinstance(sig, (tuple, list)) or len(sig) < 4:
                    continue
                entry_idx, direction, stop, target = sig
                direction = str(direction).upper()
                if direction not in ("LONG", "SHORT"):
                    continue
                if stop <= 0 or target <= 0:
                    continue
                if entry_idx != i:
                    continue

                entry_price = bar.close
                quantity = 1.0  # simplified sizing
                trade_id = f"BT-{len(trades) + len(open_positions) + 1:05d}"

                open_positions.append({
                    "trade_id": trade_id,
                    "direction": direction,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "entry_date": bar.timestamp,
                    "stop_loss": stop,
                    "target": target,
                })

        # --- force-close any remaining open positions at last bar close ---
        last_bar = bars[-1]
        for pos in open_positions:
            exit_price = last_bar.close
            trade = PaperTrade(
                trade_id=pos["trade_id"],
                symbol=symbol,
                direction=pos["direction"],
                entry_price=pos["entry_price"],
                quantity=pos["quantity"],
                entry_date=pos["entry_date"],
                exit_price=exit_price,
                exit_date=last_bar.timestamp,
                stop_loss=pos["stop_loss"],
                target=pos["target"],
                status="CLOSED",
                notes="Force-closed at end of backtest",
            )
            if pos["direction"] == "LONG":
                trade.pnl = (exit_price - pos["entry_price"]) * pos["quantity"]
                trade.pnl_percent = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
            else:
                trade.pnl = (pos["entry_price"] - exit_price) * pos["quantity"]
                trade.pnl_percent = ((pos["entry_price"] - exit_price) / pos["entry_price"]) * 100
            trades.append(trade)
            equity_curve.append(equity_curve[-1] + trade.pnl)

        # --- build result ---
        result = BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            start_date=bars[0].timestamp,
            end_date=bars[-1].timestamp,
            trades=trades,
        )
        result.calculate_stats()
        result.max_drawdown = self._max_drawdown(equity_curve)
        result.sharpe_ratio = self._sharpe_ratio(equity_curve)
        return result

    # ------------------------------------------------------------------
    # metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _max_drawdown(equity_curve: List[float]) -> float:
        """Compute max drawdown percentage from an equity curve."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (peak - val) / peak
                if dd > max_dd:
                    max_dd = dd
        return round(max_dd * 100, 2)

    @staticmethod
    def _sharpe_ratio(
        equity_curve: List[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """Annualized Sharpe ratio from equity curve (daily assumption)."""
        if len(equity_curve) < 2:
            return 0.0
        returns: List[float] = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]
            if prev != 0:
                returns.append((equity_curve[i] - prev) / prev)
        if not returns:
            return 0.0
        mean_r = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0.0
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std = var ** 0.5
        if std == 0:
            return 0.0
        daily_rf = risk_free_rate / periods_per_year
        return round(((mean_r - daily_rf) / std) * (periods_per_year ** 0.5), 2)


# Type alias for strategy functions
StrategyFn = Callable[[List[OHLCV], int], List[Tuple[int, str, float, float]]]
