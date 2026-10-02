"""
MYRAA Groww Trading Advisor — Personalized Guidance Engine

Translates raw Groww portfolio data + Phase D analysis into natural language
trading guidance. User speaks Hinglish; MYRAA responds in kind.

This is the "Mere portfolio ko analyze karo" / "Ab kya karna chahiye?" brain.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from desktop_agent.finance.trading.models import (
    PortfolioPosition,
    PortfolioSnapshot,
    RiskLevel,
    TechnicalAnalysis,
    TradePlan,
    TradeRecommendation,
    TrendDirection,
)

logger = logging.getLogger(__name__)

# Indian market sector mapping
SECTOR_MAP = {
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
    "BARODABANK": "Banking", "PNB": "Banking", "BANKBARODA": "Banking",
    "RELIANCE": "Energy", "ONGC": "Energy", "NTPC": "Energy",
    "POWERGRID": "Energy", "ADANIENT": "Energy", "TATAPOWER": "Energy",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT",
    "TECHM": "IT", "LTIM": "IT", "MPHASIS": "IT", "PERSISTENT": "IT",
    "IT": "IT",
    "ITC": "FMCG", "HUL": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto",
    "HEROMOTOCO": "Auto", "TVSMOTOR": "Auto", "EICHERMOT": "Auto",
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "TATAMETAL": "Metals", "HINDALCO": "Metals", "JSWSTEEL": "Metals",
    "VEDL": "Metals", "NMDC": "Metals", "ALUMINIUM": "Metals",
    "BAJFINANCE": "Finance", "BAJAJFINSV": "Finance", "HDFCLIFE": "Finance",
    "SBILIFE": "Finance", "ICICIPRULI": "Finance", "SBICARD": "Finance",
    "ADANIPORTS": "Infrastructure", "LICI": "Insurance",
}


def _infer_sector(symbol: str) -> str:
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    return SECTOR_MAP.get(sym, "Other")


@dataclass
class PositionAdvice:
    symbol: str
    sector: str
    quantity: int
    avg_price: float
    current_price: float
    invested_value: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    day_pnl: float
    action: str  # HOLD / ADD / REDUCE / EXIT
    confidence: float
    reasoning: str
    risk_level: str
    target: float = 0.0
    stop_loss: float = 0.0


@dataclass
class PortfolioAdvice:
    overall_assessment: str
    portfolio_health: str  # STRONG / MODERATE / WEAK / CRITICAL
    total_invested: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    cash_available: float
    position_advices: List[PositionAdvice]
    sector_exposure: Dict[str, float]
    concentration_warnings: List[str]
    risk_warnings: List[str]
    next_actions: List[str]
    market_context: str
    timestamp: str = ""


@dataclass
class StockGuidance:
    symbol: str
    recommendation: str  # BUY / SELL / HOLD / WAIT / AVOID
    confidence: float
    current_price: float
    target_price: float
    stop_loss: float
    risk_reward: str
    technical_view: str
    portfolio_impact: str
    reasoning_hinglish: str
    key_levels: Dict[str, float]


class PersonalizedGuidanceEngine:
    """
    Analyzes real Groww portfolio data and generates personalized,
    portfolio-aware trading guidance in Hinglish.
    """

    def __init__(self):
        self._last_advice: Optional[PortfolioAdvice] = None
        self._guidance_count = 0

    def analyze_portfolio(self, snapshot: PortfolioSnapshot,
                          technical_data: Optional[Dict[str, TechnicalAnalysis]] = None,
                          market_context: str = "") -> PortfolioAdvice:
        """
        Generate comprehensive portfolio advice from real Groww data.
        This is the main entry point for "Mere portfolio ko analyze karo".
        """
        if not snapshot or not snapshot.positions:
            return PortfolioAdvice(
                overall_assessment="Portfolio khaali hai. Pehle kuch positions add karo.",
                portfolio_health="CRITICAL",
                total_invested=0, total_value=0, total_pnl=0, total_pnl_pct=0,
                day_pnl=0, cash_available=snapshot.cash if snapshot else 0,
                position_advices=[], sector_exposure={}, concentration_warnings=[],
                risk_warnings=["No positions in portfolio"], next_actions=["Add positions"],
                market_context=market_context,
                timestamp=datetime.utcnow().isoformat(),
            )

        position_advices = []
        sector_totals: Dict[str, float] = {}
        total_invested = 0.0
        total_value = 0.0
        total_day_pnl = 0.0

        for pos in snapshot.positions:
            invested = pos.average_price * pos.quantity
            market_val = pos.current_price * pos.quantity
            pnl = market_val - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0
            day_pnl = (pos.current_price - pos.previous_close) * pos.quantity if pos.previous_close > 0 else 0

            total_invested += invested
            total_value += market_val
            total_day_pnl += day_pnl

            sector = _infer_sector(pos.symbol)
            sector_totals[sector] = sector_totals.get(sector, 0) + market_val

            ta = technical_data.get(pos.symbol) if technical_data else None
            advice = self._advise_position(pos, ta, day_pnl, pnl_pct)
            position_advices.append(advice)

        total_pnl = total_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

        sector_exposure = {}
        for sector, val in sector_totals.items():
            sector_exposure[sector] = round(val / total_value * 100, 1) if total_value > 0 else 0

        concentration = self._check_concentration(position_advices, sector_exposure)
        risk_warnings = self._assess_risks(position_advices, sector_exposure, total_pnl_pct)
        next_actions = self._suggest_actions(position_advices, concentration, risk_warnings)

        health = self._assess_health(total_pnl_pct, len(position_advices), concentration, risk_warnings)
        assessment = self._build_overall_assessment(health, total_pnl_pct, total_day_pnl, position_advices)

        advice = PortfolioAdvice(
            overall_assessment=assessment,
            portfolio_health=health,
            total_invested=round(total_invested, 2),
            total_value=round(total_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            day_pnl=round(total_day_pnl, 2),
            cash_available=snapshot.cash,
            position_advices=position_advices,
            sector_exposure=sector_exposure,
            concentration_warnings=concentration,
            risk_warnings=risk_warnings,
            next_actions=next_actions,
            market_context=market_context,
            timestamp=datetime.utcnow().isoformat(),
        )
        self._last_advice = advice
        self._guidance_count += 1
        return advice

    def _advise_position(self, pos: PortfolioPosition,
                         ta: Optional[TechnicalAnalysis],
                         day_pnl: float, total_pnl_pct: float) -> PositionAdvice:
        invested = pos.average_price * pos.quantity
        market_val = pos.current_price * pos.quantity
        pnl = market_val - invested

        # Basic signals
        if total_pnl_pct > 15 and day_pnl > 0:
            action, confidence = "HOLD", 0.7
            reasoning = f"Accha profit ({total_pnl_pct:.1f}%) mein hai, hold karo."
        elif total_pnl_pct > 5:
            action, confidence = "HOLD", 0.65
            reasoning = f"Thoda profit ({total_pnl_pct:.1f}%) mein hai, hold karo."
        elif -5 < total_pnl_pct <= 0:
            action, confidence = "HOLD", 0.6
            reasoning = f"Halka loss ({total_pnl_pct:.1f}%) mein hai, wait karo."
        elif total_pnl_pct <= -5:
            action, confidence = "REDUCE", 0.55
            reasoning = f"Loss ({total_pnl_pct:.1f}%) badh raha hai, position chhota karo."
        else:
            action, confidence = "HOLD", 0.6
            reasoning = "Neutral zone mein hai, hold karo."

        # Technical overlay
        target = pos.current_price * 1.1
        stop_loss = pos.current_price * 0.95
        risk_level = "MEDIUM"

        if ta:
            if hasattr(ta, 'trend'):
                if ta.trend == TrendDirection.STRONG_UPTREND:
                    action = "HOLD" if action != "REDUCE" else "HOLD"
                    confidence = min(confidence + 0.1, 0.9)
                    reasoning += " Strong uptrend mein hai."
                elif ta.trend == TrendDirection.STRONG_DOWNTREND:
                    action = "REDUCE"
                    confidence = min(confidence + 0.1, 0.9)
                    reasoning += " Downtrend mein hai, risk zyada hai."
                    risk_level = "HIGH"

        return PositionAdvice(
            symbol=pos.symbol,
            sector=_infer_sector(pos.symbol),
            quantity=pos.quantity,
            avg_price=pos.average_price,
            current_price=pos.current_price,
            invested_value=round(invested, 2),
            market_value=round(market_val, 2),
            unrealized_pnl=round(pnl, 2),
            unrealized_pnl_pct=round(total_pnl_pct, 2),
            day_pnl=round(day_pnl, 2),
            action=action,
            confidence=round(confidence, 2),
            reasoning=reasoning,
            risk_level=risk_level,
            target=round(target, 2),
            stop_loss=round(stop_loss, 2),
        )

    def _check_concentration(self, advices: List[PositionAdvice],
                              sector_exposure: Dict[str, float]) -> List[str]:
        warnings = []
        total = sum(a.market_value for a in advices)
        if total <= 0:
            return warnings
        for a in advices:
            pct = a.market_value / total * 100
            if pct > 30:
                warnings.append(f"{a.symbol} ({a.sector}) portfolio ka {pct:.0f}% hai — concentration zyada hai.")
        for sector, pct in sector_exposure.items():
            if pct > 40:
                warnings.append(f"{sector} sector ka exposure {pct:.0f}% hai — sector diversification kam hai.")
        return warnings

    def _assess_risks(self, advices: List[PositionAdvice],
                       sector_exposure: Dict[str, float], total_pnl_pct: float) -> List[str]:
        warnings = []
        if total_pnl_pct < -10:
            warnings.append(f"Portfolio {total_pnl_pct:.1f}% loss mein hai — review karo.")
        if len(advices) < 3:
            warnings.append("Portfolio diversify nahi hai — 3 se kam positions.")
        if any(a.risk_level == "HIGH" for a in advices):
            high_risk = [a.symbol for a in advices if a.risk_level == "HIGH"]
            warnings.append(f"High risk positions: {', '.join(high_risk)}")
        return warnings

    def _suggest_actions(self, advices: List[PositionAdvice],
                          concentration: List[str], risk_warnings: List[str]) -> List[str]:
        actions = []
        reduce_positions = [a for a in advices if a.action == "REDUCE"]
        if reduce_positions:
            actions.append(f"Reduce karo: {', '.join(a.symbol for a in reduce_positions)}")
        if concentration:
            actions.append("Diversify karo — sector/stock concentration kam karo.")
        if risk_warnings:
            actions.append("Risk review karo — stop losses set karo ya positions chhota karo.")
        if not actions:
            actions.append("Portfolio stable hai. Hold karo aur market monitor karo.")
        return actions

    def _assess_health(self, total_pnl_pct: float, count: int,
                        concentration: List[str], risk_warnings: List[str]) -> str:
        if total_pnl_pct > 10 and not concentration and not risk_warnings:
            return "STRONG"
        if total_pnl_pct > 0 and len(concentration) <= 1:
            return "MODERATE"
        if total_pnl_pct > -10:
            return "WEAK"
        return "CRITICAL"

    def _build_overall_assessment(self, health: str, pnl_pct: float,
                                   day_pnl: float, advices: List[PositionAdvice]) -> str:
        health_msgs = {
            "STRONG": "Portfolio strong hai!",
            "MODERATE": "Portfolio theek hai, kuch improvements ho sakte hain.",
            "WEAK": "Portfolio mein kuch issues hain, dhyan do.",
            "CRITICAL": "Portfolio mein serious issues hain, action lo!",
        }
        day_msg = f" Aaj ka P&L: {'+'if day_pnl >= 0 else ''}{day_pnl:.0f} INR." if day_pnl != 0 else ""
        return f"{health_msgs.get(health, 'Unknown')} Total P&L: {pnl_pct:.1f}%." + day_msg

    def get_stock_guidance(self, symbol: str, position: Optional[PortfolioPosition],
                            ta: Optional[TechnicalAnalysis] = None) -> StockGuidance:
        """Get personalized guidance for a specific stock."""
        has_position = position is not None and position.quantity > 0
        current_price = position.current_price if position else 0
        avg_price = position.average_price if position else 0

        if has_position and avg_price > 0:
            pnl_pct = (current_price - avg_price) / avg_price * 100
            if pnl_pct > 10:
                rec, conf = "HOLD", 0.75
                view = f"Profitable position hai ({pnl_pct:.1f}%). Hold karo."
            elif pnl_pct < -5:
                rec, conf = "REDUCE", 0.6
                view = f"Loss mein hai ({pnl_pct:.1f}%). Review karo."
            else:
                rec, conf = "HOLD", 0.65
                view = "Neutral zone mein hai. Hold karo."
        else:
            rec, conf = "WAIT", 0.5
            view = "Pehle research karo, phir decide karo."

        return StockGuidance(
            symbol=symbol,
            recommendation=rec,
            confidence=conf,
            current_price=current_price,
            target_price=round(current_price * 1.1, 2) if current_price else 0,
            stop_loss=round(current_price * 0.95, 2) if current_price else 0,
            risk_reward=f"{1.0 + (conf * 0.5):.1f}:1",
            technical_view=view,
            portfolio_impact=f"Position size: {position.quantity} shares" if has_position else "No position",
            reasoning_hinglish=view,
            key_levels={"support": round(current_price * 0.97, 2) if current_price else 0,
                        "resistance": round(current_price * 1.03, 2) if current_price else 0},
        )
