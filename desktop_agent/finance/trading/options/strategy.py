"""
MYRAA Trading Intelligence — Options Strategy Engine

Evaluates individual options strategies with full payoff maths, Greeks,
capital requirements, and risk-reward.  Also provides directional ranking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models import OptionChain, OptionContract, OptionStrategy


class OptionsStrategyEngine:
    """Evaluates and ranks options strategies."""

    LOT_MULTIPLIER = 1  # NSE lot size comes from contract; this is a safety floor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_long_call(
        self,
        chain: OptionChain,
        strike: float,
        premium: Optional[float] = None,
    ) -> OptionStrategy:
        contract = self._resolve_contract(chain, "CE", strike)
        prem = premium if premium is not None else contract.ltp
        lot = self._lot(chain, contract)
        spot = chain.underlying_price

        max_loss = prem * lot
        max_profit = None  # unlimited
        breakeven = strike + prem
        capital = max_loss
        risk_reward = float("inf")

        return OptionStrategy(
            name="Long Call",
            direction="BULLISH",
            legs=[self._leg("BUY", "CE", strike, prem, lot, chain)],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=prem,
            net_delta=contract.delta,
            net_gamma=contract.gamma,
            net_theta=contract.theta,
            net_vega=contract.vega,
            confidence=0.0,
            reasoning="",
        )

    def evaluate_long_put(
        self,
        chain: OptionChain,
        strike: float,
        premium: Optional[float] = None,
    ) -> OptionStrategy:
        contract = self._resolve_contract(chain, "PE", strike)
        prem = premium if premium is not None else contract.ltp
        lot = self._lot(chain, contract)
        spot = chain.underlying_price

        max_loss = prem * lot
        max_profit = (strike - prem) * lot if strike > prem else 0.0
        breakeven = strike - prem
        capital = max_loss
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        return OptionStrategy(
            name="Long Put",
            direction="BEARISH",
            legs=[self._leg("BUY", "PE", strike, prem, lot, chain)],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=prem,
            net_delta=contract.delta,
            net_gamma=contract.gamma,
            net_theta=contract.theta,
            net_vega=contract.vega,
            confidence=0.0,
            reasoning="",
        )

    def evaluate_bull_call_spread(
        self,
        chain: OptionChain,
        long_strike: float,
        short_strike: float,
        long_premium: Optional[float] = None,
        short_premium: Optional[float] = None,
    ) -> OptionStrategy:
        long_c = self._resolve_contract(chain, "CE", long_strike)
        short_c = self._resolve_contract(chain, "CE", short_strike)
        lp = long_premium if long_premium is not None else long_c.ltp
        sp = short_premium if short_premium is not None else short_c.ltp
        lot = self._lot(chain, long_c)

        net_premium = lp - sp
        width = short_strike - long_strike
        max_loss = net_premium * lot
        max_profit = (width - net_premium) * lot if width > net_premium else 0.0
        breakeven = long_strike + net_premium
        capital = max_loss
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        net_delta = long_c.delta - short_c.delta
        net_gamma = long_c.gamma - short_c.gamma
        net_theta = long_c.theta - short_c.theta
        net_vega = long_c.vega - short_c.vega

        return OptionStrategy(
            name="Bull Call Spread",
            direction="BULLISH",
            legs=[
                self._leg("BUY", "CE", long_strike, lp, lot, chain),
                self._leg("SELL", "CE", short_strike, sp, lot, chain),
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=net_premium,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            confidence=0.0,
            reasoning="",
        )

    def evaluate_bear_put_spread(
        self,
        chain: OptionChain,
        long_strike: float,
        short_strike: float,
        long_premium: Optional[float] = None,
        short_premium: Optional[float] = None,
    ) -> OptionStrategy:
        long_p = self._resolve_contract(chain, "PE", long_strike)
        short_p = self._resolve_contract(chain, "PE", short_strike)
        lp = long_premium if long_premium is not None else long_p.ltp
        sp = short_premium if short_premium is not None else short_p.ltp
        lot = self._lot(chain, long_p)

        net_premium = lp - sp
        width = long_strike - short_strike
        max_loss = net_premium * lot
        max_profit = (width - net_premium) * lot if width > net_premium else 0.0
        breakeven = long_strike - net_premium
        capital = max_loss
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        net_delta = long_p.delta - short_p.delta
        net_gamma = long_p.gamma - short_p.gamma
        net_theta = long_p.theta - short_p.theta
        net_vega = long_p.vega - short_p.vega

        return OptionStrategy(
            name="Bear Put Spread",
            direction="BEARISH",
            legs=[
                self._leg("BUY", "PE", long_strike, lp, lot, chain),
                self._leg("SELL", "PE", short_strike, sp, lot, chain),
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=net_premium,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            confidence=0.0,
            reasoning="",
        )

    def evaluate_covered_call(
        self,
        chain: OptionChain,
        call_strike: float,
        stock_price: float,
        stock_qty: int = 1,
        call_premium: Optional[float] = None,
    ) -> OptionStrategy:
        contract = self._resolve_contract(chain, "CE", call_strike)
        cp = call_premium if call_premium is not None else contract.ltp
        lot = self._lot(chain, contract)

        stock_value = stock_price * stock_qty
        call_income = cp * lot
        net_premium = cp  # per share
        width = call_strike - stock_price

        max_profit = (width + cp) * lot if call_strike > stock_price else cp * lot
        max_loss = (stock_price - cp) * lot if stock_price > cp else 0.0
        # More precise: max loss = stock_price * lot - call_income (stock goes to zero)
        max_loss = stock_price * lot - call_income
        breakeven = stock_price - cp
        capital = stock_value  # you already own the stock
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        return OptionStrategy(
            name="Covered Call",
            direction="BULLISH",
            legs=[
                {"action": "OWN", "option_type": "STOCK", "strike": stock_price,
                 "premium": 0.0, "qty": stock_qty, "symbol": chain.symbol,
                 "expiry": "", "note": "existing position"},
                self._leg("SELL", "CE", call_strike, cp, lot, chain),
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=cp,
            net_delta=1.0 - contract.delta,  # long stock delta ≈ 1 + short call delta
            net_gamma=-contract.gamma,
            net_theta=-contract.theta,
            net_vega=-contract.vega,
            confidence=0.0,
            reasoning="",
        )

    def evaluate_protective_put(
        self,
        chain: OptionChain,
        put_strike: float,
        stock_price: float,
        stock_qty: int = 1,
        put_premium: Optional[float] = None,
    ) -> OptionStrategy:
        contract = self._resolve_contract(chain, "PE", put_strike)
        pp = put_premium if put_premium is not None else contract.ltp
        lot = self._lot(chain, contract)

        stock_value = stock_price * stock_qty
        insurance_cost = pp * lot
        max_loss = (stock_price - put_strike) * lot + insurance_cost
        max_profit = None  # unlimited upside
        breakeven = stock_price + pp
        capital = stock_value + insurance_cost
        risk_reward = 0.0  # insurance — positive R:R only if defined

        return OptionStrategy(
            name="Protective Put",
            direction="BULLISH",
            legs=[
                {"action": "OWN", "option_type": "STOCK", "strike": stock_price,
                 "premium": 0.0, "qty": stock_qty, "symbol": chain.symbol,
                 "expiry": "", "note": "existing position"},
                self._leg("BUY", "PE", put_strike, pp, lot, chain),
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=pp,
            net_delta=1.0 + contract.delta,  # long stock ≈ +1, long put delta negative
            net_gamma=contract.gamma,
            net_theta=contract.theta,
            net_vega=contract.vega,
            confidence=0.0,
            reasoning="",
        )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_strategies(
        self,
        strategies: List[OptionStrategy],
        direction: str,
        volatility: float = 0.0,
    ) -> List[OptionStrategy]:
        scored = []
        for s in strategies:
            score = self._score_strategy(s, direction, volatility)
            scored.append((score, s))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [s for _, s in scored]

    def suggest_strategies(
        self,
        chain: OptionChain,
        direction: str = "NEUTRAL",
        risk_tolerance: str = "MEDIUM",
    ) -> List[OptionStrategy]:
        """Suggest appropriate strategies based on direction and risk tolerance."""
        strategies: List[OptionStrategy] = []
        d = direction.upper()
        try:
            if d in ("BULLISH", "LONG"):
                strategies.append(self.evaluate_long_call(chain, self._at_the_money_strike(chain)))
                strategies.append(self.evaluate_bull_call_spread(chain, self._at_the_money_strike(chain)))
            elif d in ("BEARISH", "SHORT"):
                strategies.append(self.evaluate_long_put(chain, self._at_the_money_strike(chain)))
                strategies.append(self.evaluate_bear_put_spread(chain, self._at_the_money_strike(chain)))
            else:
                strategies.append(self.evaluate_long_call(chain, self._at_the_money_strike(chain)))
                strategies.append(self.evaluate_long_put(chain, self._at_the_money_strike(chain)))
        except Exception:
            pass
        return strategies

    def _at_the_money_strike(self, chain: OptionChain) -> float:
        strikes = sorted(set(c.strike for c in chain.contracts))
        spot = chain.underlying_price
        return min(strikes, key=lambda s: abs(s - spot))

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _score_strategy(
        self,
        s: OptionStrategy,
        direction: str,
        volatility: float,
    ) -> float:
        score = 0.0
        d = direction.upper()

        # Directional fit
        if d in ("BULLISH", "LONG") and s.direction == "BULLISH":
            score += 2.0
        elif d in ("BEARISH", "SHORT") and s.direction == "BEARISH":
            score += 2.0
        elif d in ("NEUTRAL", "SIDEWAYS") and s.direction == "NEUTRAL":
            score += 2.0
        else:
            score -= 1.0  # misaligned

        # Risk-reward
        if s.risk_reward > 0 and s.risk_reward != float("inf"):
            if s.risk_reward >= 3.0:
                score += 1.5
            elif s.risk_reward >= 2.0:
                score += 1.0
            elif s.risk_reward >= 1.0:
                score += 0.5
            else:
                score -= 0.5
        elif s.risk_reward == float("inf"):
            score += 0.5  # uncapped but uncertain

        # Capital efficiency — prefer lower capital
        if s.capital_required > 0:
            if s.capital_required < 10000:
                score += 0.5
            elif s.capital_required > 100000:
                score -= 0.5

        # Volatility alignment
        if volatility > 0:
            if "Spread" in s.name:
                # Debit spreads benefit from IV expansion if IV is low
                if volatility < 15:
                    score += 0.5
                elif volatility > 30:
                    score -= 0.3
            elif s.name in ("Iron Condor", "Short Strangle"):
                if volatility > 25:
                    score += 0.5
                elif volatility < 15:
                    score -= 0.5

        # Confidence
        score += s.confidence * 0.5

        return round(score, 3)

    def _resolve_contract(
        self,
        chain: OptionChain,
        option_type: str,
        strike: float,
    ) -> OptionContract:
        pool = chain.calls if option_type == "CE" else chain.puts
        if not pool:
            return OptionContract(
                symbol=chain.symbol, strike=strike,
                expiry=chain.expiry, option_type=option_type,
            )
        return min(pool, key=lambda c: abs(c.strike - strike))

    def _lot(self, chain: OptionChain, contract: OptionContract) -> int:
        if contract.lot_size > 0:
            return contract.lot_size
        # Infer from chain — all contracts for same symbol have same lot
        for c in chain.contracts:
            if c.lot_size > 0:
                return c.lot_size
        return 1

    @staticmethod
    def _leg(
        action: str,
        option_type: str,
        strike: float,
        premium: float,
        qty: int,
        chain: OptionChain,
    ) -> Dict[str, Any]:
        return {
            "action": action,
            "option_type": option_type,
            "strike": strike,
            "premium": premium,
            "qty": qty,
            "symbol": chain.symbol,
            "expiry": chain.expiry.isoformat(),
        }
