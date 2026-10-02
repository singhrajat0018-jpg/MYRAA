"""
MYRAA Trading Intelligence — Fundamental Analysis (Part 6)

Analyze revenue, earnings, margins, debt, ROE/ROCE, valuation, growth quality.
Do not fabricate unavailable values. Label ACTUAL / ESTIMATED / UNAVAILABLE.
"""

from __future__ import annotations

from typing import Optional

from ..models import FundamentalAnalysis, FundamentalSnapshot, DataLabel


class FundamentalAnalyzer:

    def analyze(self, data: FundamentalSnapshot) -> FundamentalAnalysis:
        if data.label == DataLabel.UNAVAILABLE:
            return FundamentalAnalysis(
                symbol=data.symbol,
                reasoning="Fundamental data unavailable",
                confidence=0.0,
                data_label=DataLabel.UNAVAILABLE,
            )

        valuation = self._assess_valuation(data)
        growth = self._assess_growth(data)
        health = self._assess_financial_health(data)
        earnings = self._assess_earnings_quality(data)

        conf = 0.5
        if data.pe_ratio is not None:
            conf += 0.1
        if data.roe is not None:
            conf += 0.1
        if data.revenue_growth is not None:
            conf += 0.1
        if data.debt_to_equity is not None:
            conf += 0.1

        parts = []
        if valuation:
            parts.append(f"Valuation: {valuation}")
        if growth:
            parts.append(f"Growth: {growth}")
        if health:
            parts.append(f"Health: {health}")
        if earnings:
            parts.append(f"Earnings: {earnings}")

        details = {}
        for attr in ["pe_ratio", "pb_ratio", "eps", "roe", "roce", "debt_to_equity",
                       "revenue_growth", "net_margin", "operating_margin", "current_ratio",
                       "dividend_yield", "market_cap", "beta", "free_cash_flow"]:
            val = getattr(data, attr, None)
            if val is not None:
                details[attr] = val

        return FundamentalAnalysis(
            symbol=data.symbol,
            valuation=valuation,
            growth_quality=growth,
            financial_health=health,
            earnings_quality=earnings,
            details=details,
            reasoning=" | ".join(parts) if parts else "Limited fundamental data",
            confidence=min(conf, 1.0),
            data_label=data.label,
        )

    def _assess_valuation(self, data: FundamentalSnapshot) -> str:
        parts = []
        if data.pe_ratio is not None:
            if data.pe_ratio < 0:
                parts.append(f"P/E negative ({data.pe_ratio:.1f}) — possible losses")
            elif data.pe_ratio < 15:
                parts.append(f"P/E cheap ({data.pe_ratio:.1f})")
            elif data.pe_ratio < 25:
                parts.append(f"P/E fair ({data.pe_ratio:.1f})")
            else:
                parts.append(f"P/E expensive ({data.pe_ratio:.1f})")
        if data.pb_ratio is not None:
            if data.pb_ratio < 1:
                parts.append(f"P/B below book ({data.pb_ratio:.2f})")
            elif data.pb_ratio > 5:
                parts.append(f"P/B premium ({data.pb_ratio:.2f})")
        return ". ".join(parts) if parts else ""

    def _assess_growth(self, data: FundamentalSnapshot) -> str:
        parts = []
        if data.revenue_growth is not None:
            if data.revenue_growth > 20:
                parts.append(f"Strong revenue growth ({data.revenue_growth:.1f}%)")
            elif data.revenue_growth > 10:
                parts.append(f"Moderate revenue growth ({data.revenue_growth:.1f}%)")
            elif data.revenue_growth < 0:
                parts.append(f"Revenue declining ({data.revenue_growth:.1f}%)")
        if data.net_margin is not None:
            if data.net_margin > 15:
                parts.append(f"Healthy margins ({data.net_margin:.1f}%)")
            elif data.net_margin < 5:
                parts.append(f"Thin margins ({data.net_margin:.1f}%)")
        return ". ".join(parts) if parts else ""

    def _assess_financial_health(self, data: FundamentalSnapshot) -> str:
        parts = []
        if data.debt_to_equity is not None:
            if data.debt_to_equity > 2:
                parts.append(f"High leverage (D/E {data.debt_to_equity:.2f})")
            elif data.debt_to_equity < 0.5:
                parts.append(f"Low leverage (D/E {data.debt_to_equity:.2f})")
        if data.current_ratio is not None:
            if data.current_ratio < 1:
                parts.append(f"Liquidity risk (CR {data.current_ratio:.2f})")
            elif data.current_ratio > 2:
                parts.append(f"Strong liquidity (CR {data.current_ratio:.2f})")
        if data.roe is not None:
            if data.roe > 20:
                parts.append(f"Excellent ROE ({data.roe:.1f}%)")
            elif data.roe > 10:
                parts.append(f"Good ROE ({data.roe:.1f}%)")
        if data.roce is not None:
            if data.roce > 20:
                parts.append(f"Strong ROCE ({data.roce:.1f}%)")
        return ". ".join(parts) if parts else ""

    def _assess_earnings_quality(self, data: FundamentalSnapshot) -> str:
        parts = []
        if data.eps is not None:
            if data.eps < 0:
                parts.append("Negative EPS — possible losses")
            elif data.eps > 0:
                parts.append(f"Positive EPS ({data.eps:.2f})")
        if data.free_cash_flow is not None and data.free_cash_flow < 0:
            parts.append("Negative free cash flow")
        if data.dividend_yield is not None and data.dividend_yield > 3:
            parts.append(f"Decent dividend yield ({data.dividend_yield:.1f}%)")
        return ". ".join(parts) if parts else ""
