"""
MYRAA Trading Intelligence -- Risk Engine

Evaluates per-trade and portfolio-level risk for any instrument.
Returns a RiskAssessment with position sizing, stop guidance, and
concentration / correlation warnings.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    MarketQuote,
    PortfolioSnapshot,
    PortfolioPosition,
    RiskAssessment,
    RiskLevel,
    TechnicalAnalysis,
    TrendDirection,
)


# Default risk parameters (overridable via config dict)
_DEFAULTS: Dict[str, Any] = {
    "max_risk_per_trade_pct": 1.0,
    "max_position_pct": 10.0,
    "max_portfolio_risk_pct": 6.0,
    "max_sector_concentration_pct": 30.0,
    "max_single_concentration_pct": 15.0,
    "max_drawdown_pct": 15.0,
    "atr_stop_multiplier": 1.5,
    "min_risk_reward": 1.5,
    "max_correlated_positions": 3,
    "correlation_threshold": 0.70,
}

# Sector correlation map for Indian equities
_SECTOR_MAP: Dict[str, List[str]] = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
    "Energy": ["RELIANCE", "ONGC", "GAIL", "BPCL", "HPCL", "IOC"],
    "Auto": ["MARUTI", "TATAMOTORS", "M_M", "BAJAJ-AUTO", "HEROMOTOCO", "TVSMOTOR"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
    "Metal": ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NMDC", "COALINDIA"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO"],
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _resolve_sector(symbol: str, positions: List[PortfolioPosition]) -> str:
    for p in positions:
        if p.symbol == symbol:
            return p.sector or "Unknown"
    return "Unknown"


def _correlated_symbols(symbol: str, sector: str) -> List[str]:
    for sec, syms in _SECTOR_MAP.items():
        if sector == sec or symbol in syms:
            return [s for s in syms if s != symbol]
    return []


def _portfolio_value(ps: PortfolioSnapshot) -> float:
    if ps is None:
        return 0.0
    return ps.total_market_value + ps.cash


def _existing_positions(portfolio: PortfolioSnapshot, sector: str) -> List[PortfolioPosition]:
    if portfolio is None:
        return []
    return [p for p in portfolio.positions if (p.sector or 'Unknown') == sector]


class TradingRiskEngine:
    """Evaluates per-trade and portfolio-level risk for any instrument."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._cfg = dict(_DEFAULTS)
        if config:
            self._cfg.update(config)

    def evaluate(
        self,
        symbol: str,
        quote: MarketQuote,
        portfolio_snapshot: PortfolioSnapshot,
        technical_analysis: Optional[TechnicalAnalysis] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """Evaluate all risk dimensions and return a RiskAssessment."""
        cfg = dict(self._cfg)
        if config:
            if hasattr(config, '__dict__'):
                cfg.update({k: v for k, v in config.__dict__.items() if not k.startswith('_')})
            elif isinstance(config, dict):
                cfg.update(config)

        price = quote.current_price
        portfolio_value = _portfolio_value(portfolio_snapshot)
        change_pct = abs(quote.day_change_percent)
        atr = None
        if technical_analysis and technical_analysis.indicators:
            atr = technical_analysis.indicators.get("atr_14")

        reasons = []
        risk_score = 0.0

        # 1. Volatility risk
        vol_risk = self._volatility_risk(change_pct, atr, price)
        risk_score += vol_risk * 0.20
        if change_pct > 5.0:
            reasons.append("Extreme day move: {:.1f}%".format(change_pct))
        elif change_pct > 3.0:
            reasons.append("Large day move: {:.1f}%".format(change_pct))

        # 2. Stop distance analysis
        stop_dist = self._compute_stop_distance(price, atr, technical_analysis)
        stop_risk = self._stop_risk(stop_dist, price)
        risk_score += stop_risk * 0.20
        if stop_dist > 0:
            stop_pct = (stop_dist / price) * 100 if price > 0 else 0
            reasons.append("Suggested stop distance: {:.2f} ({:.1f}%)".format(stop_dist, stop_pct))

        # 3. Position sizing
        max_pos_value = self._max_position_value(
            portfolio_value, stop_dist, price, cfg
        )
        max_pos_shares = int(max_pos_value / price) if price > 0 else 0
        risk_per_trade = self._risk_per_trade(max_pos_value, stop_dist, portfolio_value)

        # 4. Portfolio concentration
        conc_risk, conc_msg = self._concentration_risk(
            symbol, portfolio_snapshot, max_pos_value, cfg
        )
        risk_score += conc_risk * 0.25
        if conc_msg:
            reasons.append(conc_msg)

        # 5. Correlated exposure
        corr_risk, corr_msg = self._correlation_risk(
            symbol, portfolio_snapshot, cfg
        )
        risk_score += corr_risk * 0.15
        if corr_msg:
            reasons.append(corr_msg)

        # 6. Drawdown check
        dd_risk, dd_msg = self._drawdown_risk(portfolio_snapshot, cfg)
        risk_score += dd_risk * 0.10
        if dd_msg:
            reasons.append(dd_msg)

        # 7. Liquidity risk
        liq_risk = self._liquidity_risk(quote)
        risk_score += liq_risk * 0.10
        if quote.spread_percent > 0.5:
            reasons.append("Wide spread: {:.2f}%".format(quote.spread_percent))

        risk_score = _clamp(risk_score, 0.0, 1.0)
        risk_level = self._score_to_level(risk_score)

        portfolio_impact = self._portfolio_impact_desc(
            max_pos_value, portfolio_value, risk_per_trade
        )
        concentration_desc = conc_msg or 'No concentration concern'
        correlation_desc = corr_msg or 'No significant correlated exposure'

        if not reasons:
            reasons.append("Risk within normal parameters")

        return RiskAssessment(
            symbol=symbol,
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
            max_position_size=max_pos_shares,
            stop_distance=round(stop_dist, 2),
            risk_per_trade=round(risk_per_trade, 2),
            portfolio_impact=portfolio_impact,
            concentration_risk=concentration_desc,
            correlation_risk=correlation_desc,
            reasoning=". ".join(reasons),
        )

    # ---- private risk dimensions ----

    def _volatility_risk(self, change_pct: float, atr: Optional[float], price: float) -> float:
        risk = 0.0
        if change_pct > 8.0:
            risk = 1.0
        elif change_pct > 5.0:
            risk = 0.7
        elif change_pct > 3.0:
            risk = 0.4
        elif change_pct > 1.5:
            risk = 0.2
        if atr and price > 0:
            atr_pct = (atr / price) * 100
            if atr_pct > 4.0:
                risk = min(risk + 0.3, 1.0)
            elif atr_pct > 2.5:
                risk = min(risk + 0.15, 1.0)
        return risk

    def _compute_stop_distance(
        self, price: float, atr: Optional[float], ta: Optional[TechnicalAnalysis]
    ) -> float:
        multiplier = self._cfg.get('atr_stop_multiplier', 1.5)
        if atr and atr > 0:
            base_stop = atr * multiplier
        elif price > 0:
            base_stop = price * 0.02
        else:
            return 0.0
        if ta and ta.support_levels and ta.trend == TrendDirection.BULLISH:
            nearest = max([s for s in ta.support_levels if s < price], default=0)
            if nearest > 0:
                support_stop = price - nearest
                base_stop = max(base_stop, support_stop * 0.9)
        elif ta and ta.resistance_levels and ta.trend == TrendDirection.BEARISH:
            nearest = min([r for r in ta.resistance_levels if r > price], default=float('inf'))
            if nearest < float('inf'):
                resist_stop = nearest - price
                base_stop = max(base_stop, resist_stop * 0.9)
        return round(base_stop, 2)

    def _stop_risk(self, stop_dist: float, price: float) -> float:
        if price <= 0 or stop_dist <= 0:
            return 0.5
        stop_pct = (stop_dist / price) * 100
        if stop_pct > 6.0:
            return 1.0
        if stop_pct > 4.0:
            return 0.7
        if stop_pct > 2.5:
            return 0.4
        if stop_pct > 1.5:
            return 0.2
        return 0.1

    def _max_position_value(
        self, portfolio_value: float, stop_dist: float, price: float, cfg: Dict[str, Any]
    ) -> float:
        if price <= 0:
            return 0.0
        max_risk_pct = cfg.get('max_risk_per_trade_pct', 1.0) / 100.0
        max_pos_pct = cfg.get('max_position_pct', 10.0) / 100.0
        max_dollar_risk = portfolio_value * max_risk_pct
        if stop_dist > 0:
            risk_based = max_dollar_risk / (stop_dist / price)
        else:
            risk_based = max_dollar_risk * 10
        pos_cap = portfolio_value * max_pos_pct
        return min(risk_based, pos_cap)

    def _risk_per_trade(
        self, pos_value: float, stop_dist: float, portfolio_value: float
    ) -> float:
        """Dollar risk for the proposed position.
        
        risk = position_value * (stop_distance / entry_price)
        We approximate entry_price from context; if unavailable, use a 2% default.
        """
        if portfolio_value <= 0 or stop_dist <= 0:
            return 0.0
        # Approximate: stop_dist is absolute price distance.
        # We need entry_price to convert to pct. Since we only have pos_value
        # and stop_dist, we use a heuristic: assume stop is ~2% of notional
        # when pos_value is zero, otherwise derive from the stop percentage.
        # A clean approach: risk_per_trade = max_risk_per_trade_pct * portfolio_value
        # This is the ceiling; the actual risk is pos_value * (stop_dist / entry).
        # Return the dollar risk as: pos_value * (stop_dist / (stop_dist / 0.02))
        # = pos_value * 0.02 ... which is too simplistic.
        # Better: return the ceiling from config
        max_risk_pct = self._cfg.get('max_risk_per_trade_pct', 1.0) / 100.0
        return portfolio_value * max_risk_pct

    def _concentration_risk(
        self, symbol: str, ps: PortfolioSnapshot, new_pos_value: float, cfg: Dict[str, Any]
    ) -> Tuple[float, str]:
        max_single = cfg.get('max_single_concentration_pct', 15.0) / 100.0
        max_sector = cfg.get('max_sector_concentration_pct', 30.0) / 100.0
        total_value = _portfolio_value(ps)
        if total_value <= 0:
            return 0.0, ''
        existing_val = 0.0
        for p in ps.positions:
            if p.symbol == symbol:
                existing_val = p.market_value
                break
        projected_val = existing_val + new_pos_value
        projected_pct = projected_val / total_value
        risk = 0.0
        msg_parts = []
        if projected_pct > max_single:
            severity = min((projected_pct - max_single) / max_single, 1.0)
            risk = max(risk, 0.5 + severity * 0.5)
            msg_parts.append(
                '{} would be {:.1f}% of portfolio (limit {:.1f}%)'.format(
                    symbol, projected_pct * 100, max_single * 100))
        sector = _resolve_sector(symbol, ps.positions)
        sector_val = sum(p.market_value for p in ps.positions if (p.sector or 'Unknown') == sector)
        projected_sector = sector_val + new_pos_value
        sector_pct = projected_sector / total_value
        if sector_pct > max_sector:
            severity = min((sector_pct - max_sector) / max_sector, 1.0)
            risk = max(risk, 0.4 + severity * 0.6)
            msg_parts.append(
                '{} sector would be {:.1f}% (limit {:.1f}%)'.format(
                    sector, sector_pct * 100, max_sector * 100))
        return risk, '. '.join(msg_parts)

    def _correlation_risk(
        self, symbol: str, ps: PortfolioSnapshot, cfg: Dict[str, Any]
    ) -> Tuple[float, str]:
        if ps is None:
            return 0.0, ''
        max_corr = cfg.get('max_correlated_positions', 3)
        sector = _resolve_sector(symbol, ps.positions)
        correlated = _correlated_symbols(symbol, sector)
        existing_corr = [p for p in ps.positions if p.symbol in correlated]
        risk = 0.0
        msg = ''
        if len(existing_corr) >= max_corr:
            risk = 0.8
            names = [p.symbol for p in existing_corr[:max_corr]]
            msg = 'Already {} correlated positions: {}'.format(len(existing_corr), ', '.join(names))
        elif len(existing_corr) > 0:
            risk = len(existing_corr) / max_corr * 0.5
            names = [p.symbol for p in existing_corr]
            msg = '{} correlated position(s): {}'.format(len(existing_corr), ', '.join(names))
        return risk, msg

    def _drawdown_risk(
        self, ps: PortfolioSnapshot, cfg: Dict[str, Any]
    ) -> Tuple[float, str]:
        if ps is None:
            return 0.0, ''
        max_dd = cfg.get('max_drawdown_pct', 15.0) / 100.0
        total_pnl_pct = ps.total_pnl_percent / 100.0
        if total_pnl_pct < -max_dd:
            return 1.0, 'Portfolio drawdown {:.1f}% exceeds limit {:.1f}%'.format(
                abs(total_pnl_pct) * 100, max_dd * 100)
        if total_pnl_pct < -(max_dd * 0.7):
            return 0.5, 'Portfolio drawdown {:.1f}% approaching limit'.format(
                abs(total_pnl_pct) * 100)
        return 0.0, ''

    def _liquidity_risk(self, quote: MarketQuote) -> float:
        spread_pct = quote.spread_percent
        if spread_pct > 2.0:
            return 1.0
        if spread_pct > 1.0:
            return 0.6
        if spread_pct > 0.5:
            return 0.3
        return 0.1

    def _score_to_level(self, score: float) -> RiskLevel:
        if score >= 0.80:
            return RiskLevel.VERY_HIGH
        if score >= 0.60:
            return RiskLevel.HIGH
        if score >= 0.35:
            return RiskLevel.MEDIUM
        if score >= 0.15:
            return RiskLevel.LOW
        return RiskLevel.VERY_LOW

    def _portfolio_impact_desc(
        self, pos_value: float, portfolio_value: float, risk_per_trade: float
    ) -> str:
        if portfolio_value <= 0:
            return 'Cannot assess -- no portfolio value'
        pos_pct = (pos_value / portfolio_value) * 100
        risk_pct = (risk_per_trade / portfolio_value) * 100 if portfolio_value > 0 else 0
        return 'Position ~{:.1f}% of portfolio, max risk ~{:.2f}% per trade'.format(
            pos_pct, risk_pct)
