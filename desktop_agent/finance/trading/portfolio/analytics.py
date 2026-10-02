"""
MYRAA Trading Intelligence — Portfolio Analytics

Computes position weights, sector allocation, concentration risk,
portfolio-aware trade recommendations, and daily P&L.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    MarketQuote,
    PortfolioPosition,
    PortfolioSnapshot,
    SignalType,
    TrendDirection,
)


class PortfolioAnalytics:
    """Pure-function portfolio analytics. No persistence, no network."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(
        self,
        holdings: List[Dict[str, Any]],
        quotes: Dict[str, MarketQuote],
    ) -> PortfolioSnapshot:
        positions: List[PortfolioPosition] = []
        for h in holdings:
            sym = h.get("symbol", "")
            qty = float(h.get("quantity", 0))
            avg_price = float(h.get("average_price", 0))
            sector = h.get("sector", "")
            exchange_str = h.get("exchange", "NSE")

            quote = quotes.get(sym)
            current = quote.current_price if quote else avg_price
            prev_close = quote.previous_close if quote else avg_price

            from ..models import Exchange, InstrumentType
            try:
                ex = Exchange(exchange_str)
            except ValueError:
                ex = Exchange.NSE

            pos = PortfolioPosition(
                symbol=sym,
                quantity=qty,
                average_price=avg_price,
                current_price=current,
                previous_close=prev_close,
                exchange=ex,
                sector=sector,
                instrument_type=InstrumentType.EQUITY,
                entry_date=datetime.fromisoformat(h["entry_date"]) if "entry_date" in h else datetime.utcnow(),
                notes=h.get("notes", ""),
            )
            positions.append(pos)

        cash = float(holdings[0].get("cash", 0.0)) if holdings else 0.0

        snap = PortfolioSnapshot(positions=positions, cash=cash)
        # Weights are computed lazily via concentration/allocation properties.
        # Enrich positions with computed weight for easy downstream use.
        total_mv = snap.total_market_value
        if total_mv > 0:
            for p in snap.positions:
                # Patch weight onto the position dataclass (weight property is static 0.0 in model)
                object.__setattr__(p, "_weight_pct", (p.market_value / total_mv) * 100)

        return snap

    def check_concentration(
        self,
        snapshot: PortfolioSnapshot,
        max_single: float = 25.0,
        max_sector: float = 40.0,
    ) -> List[str]:
        warnings: List[str] = []
        total_mv = snapshot.total_market_value
        if total_mv == 0:
            return ["Portfolio has no market-value positions"]

        # Single position concentration
        for p in snapshot.positions:
            pct = (p.market_value / total_mv) * 100
            if pct > max_single:
                warnings.append(
                    f"{p.symbol} is {pct:.1f}% of portfolio (limit {max_single}%)"
                )

        # Sector concentration
        sector_values: Dict[str, float] = {}
        for p in snapshot.positions:
            sec = p.sector or "Unknown"
            sector_values[sec] = sector_values.get(sec, 0.0) + p.market_value

        for sec, val in sector_values.items():
            pct = (val / total_mv) * 100
            if pct > max_sector:
                warnings.append(
                    f"Sector '{sec}' is {pct:.1f}% of portfolio (limit {max_sector}%)"
                )

        # Cash drag
        cash_pct = (snapshot.cash / (total_mv + snapshot.cash)) * 100 if (total_mv + snapshot.cash) > 0 else 0.0
        if cash_pct > 50:
            warnings.append(f"Cash drag: {cash_pct:.1f}% of total portfolio is cash")
        elif cash_pct < 2 and total_mv > 0:
            warnings.append(f"Minimal cash buffer: {cash_pct:.1f}% — limited dry powder")

        # Overall portfolio size
        total_value = snapshot.total_portfolio_value
        if total_value < 50000:
            warnings.append(
                f"Small portfolio (₹{total_value:,.0f}) — options strategies may need larger capital"
            )

        return warnings

    def portfolio_aware_recommendation(
        self,
        symbol: str,
        signal: SignalType,
        confidence: float,
        snapshot: PortfolioSnapshot,
    ) -> Dict[str, Any]:
        total_mv = snapshot.total_market_value
        total_value = snapshot.total_portfolio_value

        # Find existing position
        existing = None
        for p in snapshot.positions:
            if p.symbol == symbol:
                existing = p
                break

        warnings: List[str] = []
        adjusted_confidence = confidence
        adjusted_signal = signal
        action_notes: List[str] = []

        if existing and total_mv > 0:
            existing_pct = (existing.market_value / total_mv) * 100

            if signal == SignalType.BUY:
                if existing_pct > 25:
                    adjusted_confidence *= 0.5
                    warnings.append(
                        f"Already {existing_pct:.1f}% in {symbol} — adding concentration risk"
                    )
                    adjusted_signal = SignalType.WATCH
                    action_notes.append("Consider reducing position or waiting for pullback")
                elif existing_pct > 15:
                    adjusted_confidence *= 0.8
                    warnings.append(f"Moderate existing exposure ({existing_pct:.1f}%)")
                    action_notes.append("Add only on significant dip to manage total risk")

            elif signal == SignalType.SELL:
                # SELL with existing position — confirm exit
                pnl_pct = existing.unrealized_pnl_percent
                if pnl_pct > 0:
                    action_notes.append(f"Lock in +{pnl_pct:.1f}% gain on existing position")
                else:
                    action_notes.append(f"Exit at {pnl_pct:.1f}% loss — review stop discipline")

            elif signal == SignalType.HOLD:
                action_notes.append(f"Holding {existing_pct:.1f}% — maintain position")

        elif signal == SignalType.BUY and not existing:
            # New position sizing suggestion
            max_allocation = 20.0  # max % of portfolio for a single new position
            if total_value > 0:
                max_amount = total_value * (max_allocation / 100)
                action_notes.append(f"Suggested max allocation: ₹{max_amount:,.0f} ({max_allocation}% of portfolio)")

            # Check sector overlap
            incoming_sector = self._infer_sector(symbol)
            if incoming_sector:
                sector_pct = self._sector_exposure(snapshot, incoming_sector)
                if sector_pct > 35:
                    warnings.append(
                        f"Sector '{incoming_sector}' already {sector_pct:.1f}% — diversify"
                    )
                    adjusted_confidence *= 0.7

        # Diversification score
        n_positions = snapshot.position_count
        if n_positions > 0 and n_positions < 5:
            warnings.append(f"Portfolio has only {n_positions} position(s) — consider diversifying")

        return {
            "symbol": symbol,
            "original_signal": signal.value,
            "adjusted_signal": adjusted_signal.value,
            "original_confidence": round(confidence, 2),
            "adjusted_confidence": round(min(max(adjusted_confidence, 0.0), 1.0), 2),
            "warnings": warnings,
            "action_notes": action_notes,
            "portfolio_context": {
                "total_value": round(total_value, 2),
                "positions": n_positions,
                "cash": round(snapshot.cash, 2),
                "existing_position": {
                    "quantity": existing.quantity,
                    "avg_price": existing.average_price,
                    "pnl_pct": round(existing.unrealized_pnl_percent, 2),
                } if existing else None,
            },
        }

    def calculate_day_pnl(
        self,
        snapshot: PortfolioSnapshot,
        previous_prices: Dict[str, float],
    ) -> Dict[str, Any]:
        total_day_pnl = 0.0
        position_pnl: List[Dict[str, Any]] = []

        for p in snapshot.positions:
            prev = previous_prices.get(p.symbol, p.previous_close)
            if prev <= 0:
                prev = p.average_price  # fallback

            day_pnl = p.quantity * (p.current_price - prev)
            day_pnl_pct = ((p.current_price - prev) / prev * 100) if prev > 0 else 0.0
            total_day_pnl += day_pnl

            position_pnl.append({
                "symbol": p.symbol,
                "quantity": p.quantity,
                "previous_price": round(prev, 2),
                "current_price": round(p.current_price, 2),
                "day_pnl": round(day_pnl, 2),
                "day_pnl_percent": round(day_pnl_pct, 2),
                "contribution_pct": 0.0,  # filled below
            })

        total_mv = snapshot.total_market_value if snapshot.total_market_value > 0 else 1.0
        for pp in position_pnl:
            pp["contribution_pct"] = round((pp["day_pnl"] / total_mv) * 100, 2) if total_mv > 0 else 0.0

        # Sort by absolute P&L impact
        position_pnl.sort(key=lambda x: abs(x["day_pnl"]), reverse=True)

        # Aggregate stats
        winners = sum(1 for p in position_pnl if p["day_pnl"] > 0)
        losers = sum(1 for p in position_pnl if p["day_pnl"] < 0)
        unchanged = sum(1 for p in position_pnl if p["day_pnl"] == 0)

        return {
            "date": datetime.utcnow().isoformat(),
            "total_day_pnl": round(total_day_pnl, 2),
            "total_day_pnl_percent": round(
                (total_day_pnl / snapshot.total_invested * 100) if snapshot.total_invested > 0 else 0.0,
                2,
            ),
            "winners": winners,
            "losers": losers,
            "unchanged": unchanged,
            "positions": position_pnl,
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sector_exposure(snapshot: PortfolioSnapshot, sector: str) -> float:
        total_mv = snapshot.total_market_value
        if total_mv == 0:
            return 0.0
        sector_mv = sum(
            p.market_value for p in snapshot.positions
            if (p.sector or "Unknown") == sector
        )
        return (sector_mv / total_mv) * 100

    @staticmethod
    def _infer_sector(symbol: str) -> str:
        """Heuristic sector mapping for common NSE symbols. Returns empty if unknown."""
        symbol_upper = symbol.upper().replace(".NS", "").replace(".BO", "")
        banking = {"HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "PNB", "CANBK"}
        it = {"TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "Mphasis", "COFORGE", "Persistent", "KPITTECH"}
        fmcg = {"HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "COLPAL", "EMAMILTD", "GODREJCP", "TATACONSUM"}
        auto = {"MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR", "ASHOKLEY", "BALKRISIND", "MRF"}
        pharma = {"SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "IPCALAB", "LUPIN", "TORNTPHARM", "AUROPHARMA", "ALKEM", "GLENMARK"}
        energy = {"RELIANCE", "ONGC", "IOC", "BPCL", "HINDPETRO", "GAIL", "POWERGRID", "NTPC", "TATAPOWER", "ADANIGREEN"}
        metals = {"TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NMDC", "COALINDIA", "HINDZINC", "NATIONALUM", "JINDALSTEL", "SAIL"}
        finance = {"BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "ICICIPRULI", "SBILIFE", "LICI", "CHOLAFIN", "MUTHOOTFIN", "MANAPPURAM", "SHRIRAMFIN"}

        for s in banking:
            if symbol_upper == s:
                return "Banking"
        for s in it:
            if symbol_upper == s:
                return "IT"
        for s in fmcg:
            if symbol_upper == s:
                return "FMCG"
        for s in auto:
            if symbol_upper == s:
                return "Automobile"
        for s in pharma:
            if symbol_upper == s:
                return "Pharma"
        for s in energy:
            if symbol_upper == s:
                return "Energy"
        for s in metals:
            if symbol_upper == s:
                return "Metals"
        for s in finance:
            if symbol_upper == s:
                return "Financial Services"
        return ""
