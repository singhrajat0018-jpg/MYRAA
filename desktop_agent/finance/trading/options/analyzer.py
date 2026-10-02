"""
MYRAA Trading Intelligence — Options Analysis Engine

Analyzes option chains for OI distribution, PCR regime, IV percentile,
support/resistance derived from option OI walls, max pain, and generates
strategy suggestions tailored to direction and risk tolerance.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    OptionChain,
    OptionContract,
    OptionStrategy,
    OptionsAnalysis,
    TrendDirection,
)


class OptionsAnalyzer:
    """Pure-function options analysis. No network calls, no broker integration."""

    IV_HIGH_THRESHOLD = 30.0
    IV_LOW_THRESHOLD = 15.0
    PCR_BULLISH_THRESHOLD = 1.2
    PCR_BEARISH_THRESHOLD = 0.7
    OI_LOCKOUT_DAYS = 0.5  # days-to-expiry below which OI is considered "near expiry"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_chain(self, chain: OptionChain) -> OptionsAnalysis:
        if not chain.contracts:
            return OptionsAnalysis(
                symbol=chain.symbol,
                reasoning="Empty option chain — nothing to analyse",
                confidence=0.0,
            )

        pcr_oi = chain.pcr_oi
        pcr_volume = chain.pcr_volume
        max_pain = chain.max_pain
        iv_regime, iv_percentile, iv_rank = self._iv_analysis(chain)
        oi_conc_call, oi_conc_put = self._oi_concentration(chain)
        support = self._derive_support(chain)
        resistance = self._derive_resistance(chain)
        confidence = self._chain_confidence(chain, pcr_oi, iv_percentile)

        reasoning = self._build_reasoning(
            pcr_oi, pcr_volume, max_pain, iv_regime,
            support, resistance, chain,
        )

        return OptionsAnalysis(
            symbol=chain.symbol,
            pcr_oi=pcr_oi,
            pcr_volume=pcr_volume,
            max_pain=max_pain,
            iv_percentile=iv_percentile,
            iv_rank=iv_rank,
            iv_regime=iv_regime,
            oi_concentration_call=oi_conc_call,
            oi_concentration_put=oi_conc_put,
            support_from_options=support,
            resistance_from_options=resistance,
            strategy_suggestions=[],
            reasoning=reasoning,
            confidence=confidence,
            timestamp=datetime.utcnow(),
        )

    def analyze_strategy(
        self,
        symbol: str,
        chain: OptionChain,
        direction: str,
        risk_tolerance: str,
    ) -> List[OptionStrategy]:
        direction = direction.upper()
        risk_tolerance = risk_tolerance.upper()

        if not chain.contracts:
            return []

        atm_strike = self._find_atm_strike(chain)
        analysis = self._quick_analysis(chain)

        strategies: List[OptionStrategy] = []

        if direction in ("BULLISH", "LONG"):
            strategies.extend(self._bullish_strategies(chain, atm_strike, analysis, risk_tolerance))
        elif direction in ("BEARISH", "SHORT"):
            strategies.extend(self._bearish_strategies(chain, atm_strike, analysis, risk_tolerance))
        else:
            strategies.extend(self._neutral_strategies(chain, atm_strike, analysis, risk_tolerance))

        strategies = self._attach_reasoning(strategies, chain, analysis)
        return strategies

    # ------------------------------------------------------------------
    # IV Analysis
    # ------------------------------------------------------------------

    def _iv_analysis(self, chain: OptionChain) -> Tuple[str, float, float]:
        ivs = [
            c.implied_volatility
            for c in chain.contracts
            if c.implied_volatility > 0
        ]
        if not ivs:
            return "UNKNOWN", 50.0, 0.0

        avg_iv = sum(ivs) / len(ivs)
        high_iv = max(ivs)
        low_iv = min(ivs)
        iv_range = high_iv - low_iv if high_iv != low_iv else 1.0

        # Percentile of ATM IV relative to chain-wide range
        atm_iv = self._atm_iv(chain)
        if iv_range > 0:
            iv_percentile = ((atm_iv - low_iv) / iv_range) * 100.0
        else:
            iv_percentile = 50.0

        # Rank: how extreme the current IV is vs historical norms
        # Simplified: use percentile as a proxy
        iv_rank = iv_percentile

        if avg_iv > self.IV_HIGH_THRESHOLD:
            regime = "HIGH"
        elif avg_iv < self.IV_LOW_THRESHOLD:
            regime = "LOW"
        else:
            regime = "NORMAL"

        return regime, iv_percentile, iv_rank

    def _atm_iv(self, chain: OptionChain) -> float:
        atm = self._find_atm_strike(chain)
        candidates = [
            c.implied_volatility
            for c in chain.contracts
            if abs(c.strike - atm) < 0.01 and c.implied_volatility > 0
        ]
        return sum(candidates) / len(candidates) if candidates else 0.0

    # ------------------------------------------------------------------
    # OI Concentration
    # ------------------------------------------------------------------

    def _oi_concentration(
        self, chain: OptionChain
    ) -> Tuple[List[float], List[float]]:
        total_call_oi = sum(c.open_interest for c in chain.calls)
        total_put_oi = sum(c.open_interest for c in chain.puts)

        call_conc = self._strike_oi_pct(chain.calls, total_call_oi)
        put_conc = self._strike_oi_pct(chain.puts, total_put_oi)
        return call_conc, put_conc

    @staticmethod
    def _strike_oi_pct(contracts: List[OptionContract], total: int) -> List[float]:
        if total == 0:
            return []
        strike_oi: Dict[float, int] = defaultdict(int)
        for c in contracts:
            strike_oi[c.strike] += c.open_interest
        sorted_strikes = sorted(strike_oi.items(), key=lambda x: x[1], reverse=True)
        return [round((oi / total) * 100.0, 2) for _, oi in sorted_strikes[:5]]

    # ------------------------------------------------------------------
    # Support / Resistance from OI
    # ------------------------------------------------------------------

    def _derive_support(self, chain: OptionChain) -> float:
        put_walls = chain.get_oi_walls(3).get("put_walls", [])
        if not put_walls:
            return 0.0
        # Highest-oi put strike nearest to and below spot is strongest support
        below = [c for c in put_walls if c.strike < chain.underlying_price]
        if below:
            return max(c.strike for c in below)
        return min(c.strike for c in put_walls)

    def _derive_resistance(self, chain: OptionChain) -> float:
        call_walls = chain.get_oi_walls(3).get("call_walls", [])
        if not call_walls:
            return 0.0
        above = [c for c in call_walls if c.strike > chain.underlying_price]
        if above:
            return min(c.strike for c in above)
        return max(c.strike for c in call_walls)

    # ------------------------------------------------------------------
    # ATM Helpers
    # ------------------------------------------------------------------

    def _find_atm_strike(self, chain: OptionChain) -> float:
        strikes = sorted(set(c.strike for c in chain.contracts))
        if not strikes:
            return chain.underlying_price
        return min(strikes, key=lambda s: abs(s - chain.underlying_price))

    def _find_nearest_otm_call(self, chain: OptionChain, direction: int = 1) -> Optional[OptionContract]:
        """direction=1 → OTM above spot, -1 → OTM below."""
        if direction > 0:
            candidates = [c for c in chain.calls if c.strike >= chain.underlying_price]
            if not candidates:
                candidates = chain.calls
            return min(candidates, key=lambda c: c.strike) if candidates else None
        else:
            candidates = [c for c in chain.calls if c.strike <= chain.underlying_price]
            if not candidates:
                candidates = chain.calls
            return max(candidates, key=lambda c: c.strike) if candidates else None

    def _find_nearest_otm_put(self, chain: OptionChain, direction: int = -1) -> Optional[OptionContract]:
        if direction < 0:
            candidates = [c for c in chain.puts if c.strike <= chain.underlying_price]
            if not candidates:
                candidates = chain.puts
            return max(candidates, key=lambda c: c.strike) if candidates else None
        else:
            candidates = [c for c in chain.puts if c.strike >= chain.underlying_price]
            if not candidates:
                candidates = chain.puts
            return min(candidates, key=lambda c: c.strike) if candidates else None

    def _find_strike(self, chain: OptionChain, option_type: str, target_strike: float) -> Optional[OptionContract]:
        pool = chain.calls if option_type == "CE" else chain.puts
        if not pool:
            return None
        return min(pool, key=lambda c: abs(c.strike - target_strike))

    def _quick_analysis(self, chain: OptionChain) -> Dict[str, Any]:
        return {
            "pcr_oi": chain.pcr_oi,
            "pcr_volume": chain.pcr_volume,
            "max_pain": chain.max_pain,
            "spot": chain.underlying_price,
            "support": self._derive_support(chain),
            "resistance": self._derive_resistance(chain),
            "iv_regime": self._iv_analysis(chain)[0],
        }

    # ------------------------------------------------------------------
    # Strategy Generation
    # ------------------------------------------------------------------

    def _bullish_strategies(
        self,
        chain: OptionChain,
        atm: float,
        analysis: Dict[str, Any],
        risk_tolerance: str,
    ) -> List[OptionStrategy]:
        strategies: List[OptionStrategy] = []

        # Long Call — always available
        otm_call = self._find_nearest_otm_call(chain, 1)
        if otm_call:
            strategies.append(self._build_long_call(chain, otm_call))

        # Bull Call Spread — if IV is high (debit spread lowers cost)
        if analysis["iv_regime"] in ("HIGH", "NORMAL"):
            long_strike = self._find_strike(chain, "CE", atm)
            otm_strike = self._find_strike(chain, "CE", atm * 1.03)
            if long_strike and otm_strike and long_strike.strike != otm_strike.strike:
                strategies.append(self._build_bull_call_spread(chain, long_strike, otm_strike))

        # Covered Call / Protective Put require equity — skip if not provided
        # Long Straddle/Strangle only if IV is low
        if analysis["iv_regime"] == "LOW" and risk_tolerance in ("HIGH", "MEDIUM"):
            atm_call = self._find_strike(chain, "CE", atm)
            atm_put = self._find_strike(chain, "PE", atm)
            if atm_call and atm_put:
                strategies.append(self._build_long_straddle(chain, atm_call, atm_put))

        return strategies

    def _bearish_strategies(
        self,
        chain: OptionChain,
        atm: float,
        analysis: Dict[str, Any],
        risk_tolerance: str,
    ) -> List[OptionStrategy]:
        strategies: List[OptionStrategy] = []

        otm_put = self._find_nearest_otm_put(chain, -1)
        if otm_put:
            strategies.append(self._build_long_put(chain, otm_put))

        if analysis["iv_regime"] in ("HIGH", "NORMAL"):
            long_strike = self._find_strike(chain, "PE", atm)
            otm_strike = self._find_strike(chain, "PE", atm * 0.97)
            if long_strike and otm_strike and long_strike.strike != otm_strike.strike:
                strategies.append(self._build_bear_put_spread(chain, long_strike, otm_strike))

        if analysis["iv_regime"] == "LOW" and risk_tolerance in ("HIGH", "MEDIUM"):
            atm_call = self._find_strike(chain, "CE", atm)
            atm_put = self._find_strike(chain, "PE", atm)
            if atm_call and atm_put:
                strategies.append(self._build_long_straddle(chain, atm_call, atm_put))

        return strategies

    def _neutral_strategies(
        self,
        chain: OptionChain,
        atm: float,
        analysis: Dict[str, Any],
        risk_tolerance: str,
    ) -> List[OptionStrategy]:
        strategies: List[OptionStrategy] = []

        if analysis["iv_regime"] == "HIGH":
            # Sell premium — iron condor / short strangle
            otm_call = self._find_strike(chain, "CE", atm * 1.04)
            otm_put = self._find_strike(chain, "PE", atm * 0.96)
            wing_call = self._find_strike(chain, "CE", atm * 1.08)
            wing_put = self._find_strike(chain, "PE", atm * 0.92)
            if otm_call and otm_put and wing_call and wing_put:
                strategies.append(self._build_iron_condor(
                    chain, otm_put, wing_put, otm_call, wing_call,
                ))

            short_call = self._find_strike(chain, "CE", atm * 1.02)
            short_put = self._find_strike(chain, "PE", atm * 0.98)
            if short_call and short_put:
                strategies.append(self._build_short_strangle(chain, short_call, short_put))

        else:
            # Low/Normal IV — buy premium
            atm_call = self._find_strike(chain, "CE", atm)
            atm_put = self._find_strike(chain, "PE", atm)
            if atm_call and atm_put:
                strategies.append(self._build_long_straddle(chain, atm_call, atm_put))

            otm_call = self._find_strike(chain, "CE", atm * 1.02)
            otm_put = self._find_strike(chain, "PE", atm * 0.98)
            if otm_call and otm_put:
                strategies.append(self._build_long_strangle(chain, otm_call, otm_put))

        return strategies

    # ------------------------------------------------------------------
    # Strategy Builders — each returns an OptionStrategy with full Greeks
    # ------------------------------------------------------------------

    def _build_long_call(self, chain: OptionChain, contract: OptionContract) -> OptionStrategy:
        spot = chain.underlying_price
        strike = contract.strike
        premium = contract.ltp
        lot = contract.lot_size or 1

        max_loss = premium * lot
        max_profit = None  # theoretically unlimited
        breakeven = strike + premium
        capital = premium * lot
        risk_reward = float("inf") if max_profit is None else (max_profit / max_loss) if max_loss > 0 else 0.0

        return OptionStrategy(
            name="Long Call",
            direction="BULLISH",
            legs=[
                {"action": "BUY", "option_type": "CE", "strike": strike,
                 "premium": premium, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=premium,
            net_delta=contract.delta,
            net_gamma=contract.gamma,
            net_theta=contract.theta,
            net_vega=contract.vega,
            confidence=0.0,
        )

    def _build_long_put(self, chain: OptionChain, contract: OptionContract) -> OptionStrategy:
        spot = chain.underlying_price
        strike = contract.strike
        premium = contract.ltp
        lot = contract.lot_size or 1

        max_loss = premium * lot
        max_profit = (strike - premium) * lot if strike > premium else 0.0
        breakeven = strike - premium
        capital = premium * lot
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        return OptionStrategy(
            name="Long Put",
            direction="BEARISH",
            legs=[
                {"action": "BUY", "option_type": "PE", "strike": strike,
                 "premium": premium, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=risk_reward,
            net_premium=premium,
            net_delta=contract.delta,
            net_gamma=contract.gamma,
            net_theta=contract.theta,
            net_vega=contract.vega,
            confidence=0.0,
        )

    def _build_bull_call_spread(
        self,
        chain: OptionChain,
        long_leg: OptionContract,
        short_leg: OptionContract,
    ) -> OptionStrategy:
        lot = long_leg.lot_size or short_leg.lot_size or 1
        net_premium = long_leg.ltp - short_leg.ltp
        width = short_leg.strike - long_leg.strike

        max_loss = net_premium * lot
        max_profit = (width - net_premium) * lot if width > net_premium else 0.0
        breakeven = long_leg.strike + net_premium
        capital = net_premium * lot
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        net_delta = long_leg.delta - short_leg.delta
        net_gamma = long_leg.gamma - short_leg.gamma
        net_theta = long_leg.theta - short_leg.theta
        net_vega = long_leg.vega - short_leg.vega

        return OptionStrategy(
            name="Bull Call Spread",
            direction="BULLISH",
            legs=[
                {"action": "BUY", "option_type": "CE", "strike": long_leg.strike,
                 "premium": long_leg.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "SELL", "option_type": "CE", "strike": short_leg.strike,
                 "premium": short_leg.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
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
        )

    def _build_bear_put_spread(
        self,
        chain: OptionChain,
        long_leg: OptionContract,
        short_leg: OptionContract,
    ) -> OptionStrategy:
        lot = long_leg.lot_size or short_leg.lot_size or 1
        net_premium = long_leg.ltp - short_leg.ltp
        width = long_leg.strike - short_leg.strike

        max_loss = net_premium * lot
        max_profit = (width - net_premium) * lot if width > net_premium else 0.0
        breakeven = long_leg.strike - net_premium
        capital = net_premium * lot
        risk_reward = (max_profit / max_loss) if max_loss > 0 else 0.0

        net_delta = long_leg.delta - short_leg.delta
        net_gamma = long_leg.gamma - short_leg.gamma
        net_theta = long_leg.theta - short_leg.theta
        net_vega = long_leg.vega - short_leg.vega

        return OptionStrategy(
            name="Bear Put Spread",
            direction="BEARISH",
            legs=[
                {"action": "BUY", "option_type": "PE", "strike": long_leg.strike,
                 "premium": long_leg.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "SELL", "option_type": "PE", "strike": short_leg.strike,
                 "premium": short_leg.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
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
        )

    def _build_long_straddle(
        self,
        chain: OptionChain,
        call: OptionContract,
        put: OptionContract,
    ) -> OptionStrategy:
        lot = call.lot_size or put.lot_size or 1
        net_premium = call.ltp + put.ltp
        width = abs(call.strike - put.strike)

        max_profit = None  # unlimited on both sides
        max_loss = net_premium * lot
        upper_be = call.strike + net_premium
        lower_be = put.strike - net_premium
        breakeven = lower_be  # return the lower; upper is implied
        capital = net_premium * lot

        return OptionStrategy(
            name="Long Straddle",
            direction="NEUTRAL",
            legs=[
                {"action": "BUY", "option_type": "CE", "strike": call.strike,
                 "premium": call.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "BUY", "option_type": "PE", "strike": put.strike,
                 "premium": put.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            capital_required=capital,
            risk_reward=0.0,  # needs big move
            net_premium=net_premium,
            net_delta=call.delta + put.delta,
            net_gamma=call.gamma + put.gamma,
            net_theta=call.theta + put.theta,
            net_vega=call.vega + put.vega,
            confidence=0.0,
        )

    def _build_long_strangle(
        self,
        chain: OptionChain,
        call: OptionContract,
        put: OptionContract,
    ) -> OptionStrategy:
        lot = call.lot_size or put.lot_size or 1
        net_premium = call.ltp + put.ltp

        max_profit = None
        max_loss = net_premium * lot
        upper_be = call.strike + net_premium
        lower_be = put.strike - net_premium
        capital = net_premium * lot

        return OptionStrategy(
            name="Long Strangle",
            direction="NEUTRAL",
            legs=[
                {"action": "BUY", "option_type": "CE", "strike": call.strike,
                 "premium": call.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "BUY", "option_type": "PE", "strike": put.strike,
                 "premium": put.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=lower_be,
            capital_required=capital,
            risk_reward=0.0,
            net_premium=net_premium,
            net_delta=call.delta + put.delta,
            net_gamma=call.gamma + put.gamma,
            net_theta=call.theta + put.theta,
            net_vega=call.vega + put.vega,
            confidence=0.0,
        )

    def _build_short_strangle(
        self,
        chain: OptionChain,
        call: OptionContract,
        put: OptionContract,
    ) -> OptionStrategy:
        lot = call.lot_size or put.lot_size or 1
        net_premium = call.ltp + put.ltp
        width_up = call.strike - chain.underlying_price
        width_dn = chain.underlying_price - put.strike
        width = min(width_up, width_dn)

        max_profit = net_premium * lot
        max_loss = None  # theoretically unlimited
        breakeven_upper = call.strike + net_premium
        breakeven_lower = put.strike - net_premium
        capital = max(call.margin_required, put.margin_required) * lot if call.margin_required else net_premium * 10 * lot

        return OptionStrategy(
            name="Short Strangle",
            direction="NEUTRAL",
            legs=[
                {"action": "SELL", "option_type": "CE", "strike": call.strike,
                 "premium": call.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "SELL", "option_type": "PE", "strike": put.strike,
                 "premium": put.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven_lower,
            capital_required=capital,
            risk_reward=0.0,
            net_premium=net_premium,
            net_delta=-(call.delta + put.delta),
            net_gamma=-(call.gamma + put.gamma),
            net_theta=-(call.theta + put.theta),
            net_vega=-(call.vega + put.vega),
            confidence=0.0,
        )

    def _build_iron_condor(
        self,
        chain: OptionChain,
        short_put: OptionContract,
        long_put: OptionContract,
        short_call: OptionContract,
        long_call: OptionContract,
    ) -> OptionStrategy:
        lot = short_put.lot_size or short_call.lot_size or 1
        net_premium = (short_call.ltp + short_put.ltp) - (long_call.ltp + long_put.ltp)
        put_width = short_put.strike - long_put.strike
        call_width = long_call.strike - short_call.strike
        max_width = max(put_width, call_width)

        max_loss = (max_width - net_premium) * lot if max_width > net_premium else 0.0
        max_profit = net_premium * lot
        breakeven_upper = short_call.strike + net_premium
        breakeven_lower = short_put.strike - net_premium
        capital = max(short_call.margin_required, short_put.margin_required) * lot if short_call.margin_required else net_premium * 10 * lot

        return OptionStrategy(
            name="Iron Condor",
            direction="NEUTRAL",
            legs=[
                {"action": "SELL", "option_type": "PE", "strike": short_put.strike,
                 "premium": short_put.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "BUY", "option_type": "PE", "strike": long_put.strike,
                 "premium": long_put.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "SELL", "option_type": "CE", "strike": short_call.strike,
                 "premium": short_call.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
                {"action": "BUY", "option_type": "CE", "strike": long_call.strike,
                 "premium": long_call.ltp, "qty": lot, "symbol": chain.symbol,
                 "expiry": chain.expiry.isoformat()},
            ],
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven_lower,
            capital_required=capital,
            risk_reward=(max_profit / max_loss) if max_loss > 0 else 0.0,
            net_premium=net_premium,
            net_delta=(short_put.delta - long_put.delta) + (short_call.delta - long_call.delta),
            net_gamma=(short_put.gamma - long_put.gamma) + (short_call.gamma - long_call.gamma),
            net_theta=(short_put.theta - long_put.theta) + (short_call.theta - long_call.theta),
            net_vega=(short_put.vega - long_put.vega) + (short_call.vega - long_call.vega),
            confidence=0.0,
        )

    # ------------------------------------------------------------------
    # Reasoning / Confidence
    # ------------------------------------------------------------------

    def _attach_reasoning(
        self,
        strategies: List[OptionStrategy],
        chain: OptionChain,
        analysis: Dict[str, Any],
    ) -> List[OptionStrategy]:
        pcr = analysis["pcr_oi"]
        iv_regime = analysis["iv_regime"]
        spot = analysis["spot"]
        support = analysis["support"]
        resistance = analysis["resistance"]

        for s in strategies:
            conf = 0.5
            parts: List[str] = []

            # PCR bias
            if pcr > self.PCR_BULLISH_THRESHOLD and s.direction == "BULLISH":
                conf += 0.1
                parts.append(f"PCR OI bullish ({pcr:.2f})")
            elif pcr < self.PCR_BEARISH_THRESHOLD and s.direction == "BEARISH":
                conf += 0.1
                parts.append(f"PCR OI bearish ({pcr:.2f})")
            elif s.direction == "NEUTRAL":
                conf += 0.05
                parts.append(f"PCR OI neutral ({pcr:.2f})")

            # IV regime fit
            if "Spread" in s.name or s.name in ("Long Straddle", "Long Strangle"):
                if iv_regime == "LOW":
                    conf += 0.1
                    parts.append("IV regime favourable for debit strategies")
                elif iv_regime == "HIGH":
                    conf -= 0.05
                    parts.append("IV regime elevated — debit strategy may underperform")
            elif s.name in ("Short Strangle", "Iron Condor"):
                if iv_regime == "HIGH":
                    conf += 0.1
                    parts.append("IV regime favourable for premium selling")
                elif iv_regime == "LOW":
                    conf -= 0.05
                    parts.append("IV regime low — premium selling may be thin")

            # Proximity to support/resistance
            if support > 0 and s.direction == "BULLISH":
                dist = (spot - support) / spot * 100
                if dist < 2:
                    conf += 0.05
                    parts.append(f"Near option-derived support ({support:.1f})")
            if resistance > 0 and s.direction == "BEARISH":
                dist = (resistance - spot) / spot * 100
                if dist < 2:
                    conf += 0.05
                    parts.append(f"Near option-derived resistance ({resistance:.1f})")

            # Risk-reward
            if s.risk_reward > 2.0:
                conf += 0.1
                parts.append(f"Strong R:R ({s.risk_reward:.1f})")
            elif s.risk_reward > 1.0:
                conf += 0.05

            s.confidence = round(min(max(conf, 0.0), 1.0), 2)
            s.reasoning = " | ".join(parts) if parts else "Strategy generated from chain analysis"

        return strategies

    def _build_reasoning(
        self,
        pcr_oi: float,
        pcr_volume: float,
        max_pain: float,
        iv_regime: str,
        support: float,
        resistance: float,
        chain: OptionChain,
    ) -> str:
        parts: List[str] = []

        # PCR
        if pcr_oi > self.PCR_BULLISH_THRESHOLD:
            parts.append(f"PCR OI {pcr_oi:.2f} — bullish (put writers dominant)")
        elif pcr_oi < self.PCR_BEARISH_THRESHOLD:
            parts.append(f"PCR OI {pcr_oi:.2f} — bearish (call writers dominant)")
        else:
            parts.append(f"PCR OI {pcr_oi:.2f} — neutral")

        if pcr_volume != pcr_oi:
            parts.append(f"PCR volume {pcr_volume:.2f}")

        # Max pain
        spot = chain.underlying_price
        if max_pain > 0:
            diff_pct = ((max_pain - spot) / spot) * 100
            if abs(diff_pct) < 0.5:
                parts.append(f"Max pain {max_pain:.1f} — spot is at equilibrium")
            elif diff_pct > 0:
                parts.append(f"Max pain {max_pain:.1f} — {diff_pct:+.1f}% above spot (bullish pull)")
            else:
                parts.append(f"Max pain {max_pain:.1f} — {diff_pct:+.1f}% below spot (bearish pull)")

        # IV
        parts.append(f"IV regime: {iv_regime}")

        # Support / Resistance
        if support > 0:
            parts.append(f"Put OI support at {support:.1f}")
        if resistance > 0:
            parts.append(f"Call OI resistance at {resistance:.1f}")

        return " | ".join(parts)

    def _chain_confidence(
        self,
        chain: OptionChain,
        pcr_oi: float,
        iv_percentile: float,
    ) -> float:
        conf = 0.4
        # More contracts → more reliable
        n = len(chain.contracts)
        if n > 40:
            conf += 0.15
        elif n > 20:
            conf += 0.1
        elif n > 10:
            conf += 0.05

        # PCR extremes are more informative
        if pcr_oi > 1.5 or pcr_oi < 0.5:
            conf += 0.1

        # IV extremes are more informative
        if iv_percentile > 80 or iv_percentile < 20:
            conf += 0.1

        # OI walls exist
        walls = chain.get_oi_walls(1)
        if walls["call_walls"] and walls["put_walls"]:
            conf += 0.1

        return round(min(conf, 1.0), 2)
