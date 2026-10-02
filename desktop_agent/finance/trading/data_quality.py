"""
MYRAA Trading Intelligence — Data Quality Layer (Part 23)

Every decision must consider timestamp, source, stale state, missing fields,
provider disagreement, market closed/open status.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .models import (
    DataQuality,
    DataLabel,
    MarketQuote,
    MarketStatus,
    OHLCV,
    FundamentalSnapshot,
)

logger = logging.getLogger(__name__)

# Freshness thresholds in seconds
FRESH_LIVE = 30
FRESH_RECENT = 300
FRESH_ACCEPTABLE = 900
STALE_THRESHOLD = 3600

# Indian market hours (IST)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


@dataclass
class QualityCheck:
    quality: DataQuality
    score: float
    issues: List[str]
    recommendations: List[str]


class DataQualityLayer:
    """Validates market data freshness, completeness, and consistency."""

    def __init__(self, stale_threshold: float = STALE_THRESHOLD):
        self._stale_threshold = stale_threshold

    def check_quote(self, quote: MarketQuote) -> QualityCheck:
        issues: List[str] = []
        recommendations: List[str] = []
        score = 1.0

        age = (datetime.utcnow() - quote.timestamp).total_seconds()

        if age < FRESH_LIVE:
            quality = DataQuality.LIVE
        elif age < FRESH_RECENT:
            quality = DataQuality.FRESH
        elif age < FRESH_ACCEPTABLE:
            quality = DataQuality.STALE
            issues.append(f"Quote is {age:.0f}s old")
            recommendations.append("Consider using fresher data")
            score -= 0.3
        else:
            quality = DataQuality.UNAVAILABLE
            issues.append(f"Quote is too old ({age:.0f}s)")
            recommendations.append("Do not use for trading decisions")
            score = 0.0

        if quote.current_price <= 0:
            issues.append("Current price is zero/negative")
            score = 0.0
            quality = DataQuality.UNAVAILABLE

        if quote.previous_close <= 0:
            issues.append("Previous close is zero/negative")
            score -= 0.2

        if quote.open_price <= 0 and quote.volume > 0:
            issues.append("Open price missing despite volume")
            score -= 0.1

        if quote.high_price > 0 and quote.low_price > 0:
            if quote.high_price < quote.low_price:
                issues.append("High < Low — data inconsistency")
                score -= 0.4

        if quote.high_price > 0 and quote.current_price > 0:
            if quote.current_price > quote.high_price * 1.001:
                issues.append("Current price above day high")
                score -= 0.1

        if quote.low_price > 0 and quote.current_price > 0:
            if quote.current_price < quote.low_price * 0.999:
                issues.append("Current price below day low")
                score -= 0.1

        if quote.volume < 0:
            issues.append("Negative volume")
            score -= 0.3

        if not quote.source:
            issues.append("No data source specified")
            score -= 0.05

        return QualityCheck(
            quality=quality,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def check_ohlcv_bars(self, bars: List[OHLCV], expected_count: int = 20) -> QualityCheck:
        issues: List[str] = []
        recommendations: List[str] = []
        score = 1.0

        if not bars:
            return QualityCheck(
                quality=DataQuality.UNAVAILABLE,
                score=0.0,
                issues=["No OHLCV data"],
                recommendations=["Fetch historical data"],
            )

        if len(bars) < expected_count:
            coverage = len(bars) / expected_count
            score -= (1.0 - coverage) * 0.3
            issues.append(f"Only {len(bars)}/{expected_count} bars available")
            recommendations.append("Results may be less reliable with limited data")

        gaps = 0
        for i in range(1, len(bars)):
            delta = (bars[i].timestamp - bars[i - 1].timestamp).total_seconds()
            if delta > 86400 * 2:
                gaps += 1
        if gaps > 0:
            score -= gaps * 0.05
            issues.append(f"Found {gaps} time gaps in data")

        for bar in bars:
            if bar.high < bar.low and bar.high > 0 and bar.low > 0:
                issues.append(f"Bar at {bar.timestamp}: high < low")
                score -= 0.1

        if bars:
            latest = bars[-1]
            age = (datetime.utcnow() - latest.timestamp).total_seconds()
            if age > self._stale_threshold:
                issues.append(f"Latest bar is {age:.0f}s old")
                score -= 0.2
                recommendations.append("Data may be stale")

        if score >= 0.8:
            quality = DataQuality.FRESH
        elif score >= 0.5:
            quality = DataQuality.STALE
        else:
            quality = DataQuality.DEGRADED

        return QualityCheck(
            quality=quality,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def check_fundamentals(self, data: FundamentalSnapshot) -> QualityCheck:
        issues: List[str] = []
        recommendations: List[str] = []
        score = 1.0

        if data.label == DataLabel.UNAVAILABLE:
            return QualityCheck(
                quality=DataQuality.UNAVAILABLE,
                score=0.0,
                issues=["Fundamental data unavailable"],
                recommendations=["Cannot perform fundamental analysis"],
            )

        if data.label == DataLabel.STALE:
            score -= 0.3
            issues.append("Fundamental data is stale")
            recommendations.append("Verify with latest earnings report")

        fields_checked = 0
        fields_present = 0
        important_fields = [
            "pe_ratio", "pb_ratio", "revenue", "net_income",
            "roe", "debt_to_equity", "market_cap"
        ]
        for f in important_fields:
            fields_checked += 1
            if getattr(data, f, None) is not None:
                fields_present += 1

        if fields_checked > 0:
            coverage = fields_present / fields_checked
            if coverage < 0.3:
                score -= 0.4
                issues.append(f"Only {fields_present}/{fields_checked} key fields present")
                recommendations.append("Fundamental analysis will be limited")
            elif coverage < 0.6:
                score -= 0.2

        quality = DataQuality.FRESH if score >= 0.7 else DataQuality.DEGRADED

        return QualityCheck(
            quality=quality,
            score=max(0.0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def is_market_open(self) -> bool:
        now = datetime.utcnow()
        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute
        open_minutes = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MINUTE
        close_minutes = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE
        return open_minutes <= current_minutes <= close_minutes

    def get_market_status(self) -> MarketStatus:
        now = datetime.utcnow()
        hour = now.hour
        minute = now.minute
        current_minutes = hour * 60 + minute
        open_minutes = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MINUTE
        close_minutes = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE

        if now.weekday() >= 5:
            return MarketStatus.HOLIDAY

        if current_minutes < open_minutes:
            return MarketStatus.PRE_OPEN
        elif open_minutes <= current_minutes <= close_minutes:
            return MarketStatus.OPEN
        elif close_minutes < current_minutes <= close_minutes + 30:
            return MarketStatus.POST_CLOSE
        else:
            return MarketStatus.CLOSED

    def degraded_analysis_notice(self, quality: DataQuality) -> str:
        if quality == DataQuality.LIVE:
            return ""
        elif quality == DataQuality.FRESH:
            return ""
        elif quality == DataQuality.STALE:
            return "Note: Analysis based on slightly stale data. Verify before trading."
        elif quality == DataQuality.DEGRADED:
            return "Warning: Analysis degraded due to data quality issues. Do not use as sole basis for trades."
        else:
            return "Error: Cannot perform analysis — data unavailable."
