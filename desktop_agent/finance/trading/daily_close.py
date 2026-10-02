"""
MYRAA Trading Intelligence — Daily Market Close Analyzer

Runs at end-of-day to synthesize market data, portfolio state, and scanner
results into a structured DailyMarketCloseReport. Everything produced here
is derived from actual input data — no fabricated figures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from desktop_agent.finance.trading.models import (
    DailyMarketCloseReport,
    MarketMover,
    MarketSnapshot,
    PortfolioSnapshot,
    RiskAssessment,
    RiskLevel,
    TradeRecommendation,
)


class DailyCloseAnalyzer:
    """End-of-day market analysis. Produces a DailyMarketCloseReport from
    real market data, portfolio snapshots, and scanner results."""

    def analyze(
        self,
        market_data: Dict[str, Any],
        portfolio: Optional[PortfolioSnapshot],
        scanner_results: Dict[str, Any],
    ) -> DailyMarketCloseReport:
        """Build a DailyMarketCloseReport from concrete inputs.

        Parameters
        ----------
        market_data:
            Expected keys: ``nifty_snapshot``, ``banknifty_snapshot``,
            ``gainers`` (list of dicts), ``losers`` (list of dicts),
            ``unusual_volume`` (list of dicts).
        portfolio:
            Current PortfolioSnapshot or None.
        scanner_results:
            Expected keys: ``opportunities`` (list of dicts),
            ``risks`` (list of dicts), ``options_candidates`` (list of str).

        Returns
        -------
        DailyMarketCloseReport
            A fully populated report object. All fields are derived from the
            inputs; missing or empty inputs produce empty/default fields.
        """
        nifty_snapshot = self._parse_snapshot(market_data.get("nifty_snapshot"))
        banknifty_snapshot = self._parse_snapshot(market_data.get("banknifty_snapshot"))

        regime = self._determine_regime(nifty_snapshot, banknifty_snapshot)

        gainers = self._parse_movers(market_data.get("gainers", []))
        losers = self._parse_movers(market_data.get("losers", []))
        unusual = self._parse_movers(market_data.get("unusual_volume", []))

        portfolio_changes = self._portfolio_day_changes(portfolio)

        opportunities = self._parse_recommendations(scanner_results.get("opportunities", []))
        risks = self._parse_risk_assessments(scanner_results.get("risks", []))

        options_candidates = list(scanner_results.get("options_candidates", []))

        outlook = self._build_outlook(nifty_snapshot, regime, portfolio_changes)
        scenarios = self._build_scenarios(regime, nifty_snapshot, portfolio)

        return DailyMarketCloseReport(
            date=datetime.utcnow(),
            market_regime=regime,
            nifty_snapshot=nifty_snapshot,
            banknifty_snapshot=banknifty_snapshot,
            biggest_gainers=gainers,
            biggest_losers=losers,
            unusual_movers=unusual,
            portfolio_changes=portfolio_changes,
            top_opportunities=opportunities,
            top_risks=risks,
            nifty_outlook=outlook,
            options_setup_candidates=options_candidates,
            tomorrow_scenarios=scenarios,
        )

    # ------------------------------------------------------------------
    # internal helpers — all deterministic, no fabrication
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_snapshot(raw: Any) -> Optional[MarketSnapshot]:
        if raw is None or not isinstance(raw, dict):
            return None
        from desktop_agent.finance.trading.models import DataQuality, Exchange, MarketQuote, MarketStatus
        q = raw.get("quote", {})
        quote = MarketQuote(
            symbol=q.get("symbol", ""),
            current_price=q.get("current_price", 0.0),
            previous_close=q.get("previous_close", 0.0),
            open_price=q.get("open_price", 0.0),
            high_price=q.get("high_price", 0.0),
            low_price=q.get("low_price", 0.0),
            volume=q.get("volume", 0),
            exchange=Exchange(q.get("exchange", "NSE")),
            market_status=MarketStatus(q.get("market_status", "UNKNOWN")),
            source=q.get("source", ""),
            data_quality=DataQuality(q.get("data_quality", "UNAVAILABLE")),
        )
        return MarketSnapshot(
            symbol=raw.get("symbol", quote.symbol),
            quote=quote,
            source=raw.get("source", ""),
        )

    @staticmethod
    def _determine_regime(
        nifty: Optional[MarketSnapshot],
        banknifty: Optional[MarketSnapshot],
    ) -> str:
        if nifty is None and banknifty is None:
            return "UNKNOWN"

        changes: List[float] = []
        if nifty is not None:
            changes.append(nifty.quote.day_change_percent)
        if banknifty is not None:
            changes.append(banknifty.quote.day_change_percent)

        avg = sum(changes) / len(changes)

        if avg > 1.5:
            return "STRONG_BULL"
        if avg > 0.3:
            return "BULL"
        if avg < -1.5:
            return "STRONG_BEAR"
        if avg < -0.3:
            return "BEAR"
        return "FLAT"

    @staticmethod
    def _parse_movers(raw_list: Any) -> List[MarketMover]:
        if not isinstance(raw_list, list):
            return []
        movers: List[MarketMover] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            movers.append(
                MarketMover(
                    symbol=item.get("symbol", ""),
                    current_price=item.get("current_price", 0.0),
                    change_percent=item.get("change_percent", 0.0),
                    volume=item.get("volume", 0),
                    relative_volume=item.get("relative_volume", 0.0),
                    reason=item.get("reason", ""),
                    category=item.get("category", ""),
                )
            )
        return movers

    @staticmethod
    def _portfolio_day_changes(
        portfolio: Optional[PortfolioSnapshot],
    ) -> List[Dict[str, Any]]:
        if portfolio is None:
            return []
        changes: List[Dict[str, Any]] = []
        for pos in portfolio.positions:
            changes.append({
                "symbol": pos.symbol,
                "day_pnl": pos.day_pnl,
                "day_change_percent": pos.day_change_percent,
                "unrealized_pnl": pos.unrealized_pnl,
                "holding_days": pos.holding_duration_days,
            })
        changes.sort(key=lambda c: c["day_pnl"], reverse=True)
        return changes

    @staticmethod
    def _parse_recommendations(raw_list: Any) -> List[TradeRecommendation]:
        if not isinstance(raw_list, list):
            return []
        from desktop_agent.finance.trading.models import SignalType
        recs: List[TradeRecommendation] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            try:
                signal = SignalType(item.get("signal", "WAIT"))
            except ValueError:
                signal = SignalType.WAIT
            recs.append(
                TradeRecommendation(
                    symbol=item.get("symbol", ""),
                    signal=signal,
                    confidence=item.get("confidence", 0.0),
                    reasoning=item.get("reasoning", ""),
                    evidence=item.get("evidence", []),
                )
            )
        return recs

    @staticmethod
    def _parse_risk_assessments(raw_list: Any) -> List[RiskAssessment]:
        if not isinstance(raw_list, list):
            return []
        assessments: List[RiskAssessment] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            try:
                level = RiskLevel(item.get("risk_level", "MEDIUM"))
            except ValueError:
                level = RiskLevel.MEDIUM
            assessments.append(
                RiskAssessment(
                    symbol=item.get("symbol", ""),
                    risk_level=level,
                    risk_score=item.get("risk_score", 0.5),
                    reasoning=item.get("reasoning", ""),
                )
            )
        return assessments

    @staticmethod
    def _build_outlook(
        nifty: Optional[MarketSnapshot],
        regime: str,
        portfolio_changes: List[Dict[str, Any]],
    ) -> str:
        parts: List[str] = []
        if nifty is not None:
            chg = nifty.quote.day_change_percent
            vol = nifty.quote.volume
            parts.append(
                f"NIFTY closed at {nifty.quote.current_price:.2f} "
                f"({chg:+.2f}%) on volume {vol:,}."
            )
        parts.append(f"Market regime: {regime}.")
        if portfolio_changes:
            total_day = sum(c["day_pnl"] for c in portfolio_changes)
            parts.append(f"Portfolio day P&L: {total_day:+,.2f}.")
        return " ".join(parts)

    @staticmethod
    def _build_scenarios(
        regime: str,
        nifty: Optional[MarketSnapshot],
        portfolio: Optional[PortfolioSnapshot],
    ) -> List[str]:
        scenarios: List[str] = []
        if regime in ("STRONG_BULL", "BULL"):
            scenarios.append("Gap-up open likely; watch for profit-taking after first hour.")
            scenarios.append("Breakout continuation possible if volume sustains above average.")
        elif regime in ("STRONG_BEAR", "BEAR"):
            scenarios.append("Gap-down or flat open with selling pressure likely.")
            scenarios.append("Bounce possible near key support; avoid catching falling knives.")
        elif regime == "FLAT":
            scenarios.append("Range-bound session expected; trade index at extremes only.")
        else:
            scenarios.append("Insufficient data to form a directional scenario.")

        if nifty is not None and nifty.quote.high_price > 0 and nifty.quote.low_price > 0:
            rng = nifty.quote.high_price - nifty.quote.low_price
            scenarios.append(
                f"Yesterday's range was {rng:.2f} points. "
                f"Break above {nifty.quote.high_price:.2f} bullish, "
                f"break below {nifty.quote.low_price:.2f} bearish."
            )

        if portfolio is not None and portfolio.position_count > 0:
            scenarios.append(
                f"Portfolio has {portfolio.position_count} open position(s). "
                f"Review stops before market open."
            )
        return scenarios
