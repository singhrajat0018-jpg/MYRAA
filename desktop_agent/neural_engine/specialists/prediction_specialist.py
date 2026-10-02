"""Prediction/Forecasting Neural Specialist — Phase F.

Flow:
Historical data + current state → Prediction Neural Model
→ regime forecast / risk assessment / resource prediction → ContextFusion → Super-Brain

All predictions are probabilistic. No output is ever presented as certainty.
"""

from __future__ import annotations

import math
import time
import threading
from typing import Any, Optional
from dataclasses import dataclass, field

from ..model_contract import (
    ModelSpec, ModelResult, InferenceRequest, ModelDomain, ModelModality,
    LatencyClass, ModelDeployment, ModelStatus,
)


@dataclass(frozen=True)
class PredictionResult:
    """Structured prediction output — always probabilistic."""
    prediction: str
    confidence: float
    uncertainty: float
    horizon: str
    supporting_evidence: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)


class PredictionSpecialist:
    """Prediction/forecasting specialist for market regimes, risk, resources, and duration."""

    SPEC = ModelSpec(
        model_id="prediction_specialist_v1",
        domain=ModelDomain.PREDICTION,
        version="1.0.0",
        modality=ModelModality.STRUCTURED,
        capabilities=[
            "market_regime_forecast",
            "project_risk_assessment",
            "task_duration_estimate",
            "system_degradation_forecast",
            "resource_usage_forecast",
        ],
        input_schema={
            "historical_data": "list[dict]",
            "current_state": "dict",
            "context": "dict",
        },
        output_schema={
            "prediction": "PredictionResult",
            "confidence": "float",
            "uncertainty": "float",
        },
        latency_class=LatencyClass.FAST,
        deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 128},
        provider="local",
        confidence_support=True,
        uncertainty_support=True,
        description="Probabilistic prediction specialist. All outputs include uncertainty bounds.",
    )

    def __init__(self):
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0
        self._lock = threading.Lock()

    @property
    def model_id(self) -> str:
        return self.SPEC.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    @property
    def health_score(self) -> float:
        return self._health_score

    def inference(self, request: InferenceRequest) -> ModelResult:
        start = time.perf_counter()
        with self._lock:
            self._total_calls += 1

        try:
            historical = request.context.get("historical_data", [])
            current = request.context.get("current_state", {})
            context = request.context.get("context", {})

            result = self._route_prediction(historical, current, context)

            elapsed = (time.perf_counter() - start) * 1000
            self._update_health(True)

            return ModelResult(
                model_id=self.model_id,
                output=result,
                confidence=result.confidence,
                uncertainty=result.uncertainty,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="prediction_specialist",
                version=self.SPEC.version,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            with self._lock:
                self._failures += 1
            self._update_health(False)
            return ModelResult(
                model_id=self.model_id,
                output=PredictionResult(
                    prediction="error",
                    confidence=0.0,
                    uncertainty=1.0,
                    horizon="none",
                    risk_factors=[f"Prediction failed: {e}"],
                ),
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="prediction_specialist_error",
                warnings=[str(e)],
                version=self.SPEC.version,
            )

    def _route_prediction(
        self, historical: list[dict], current: dict, context: dict
    ) -> PredictionResult:
        prediction_type = context.get("prediction_type", "regime")

        if prediction_type == "regime":
            return self._regime_transition(historical, current, context)
        elif prediction_type == "risk":
            return self._risk_assessment(historical, current, context)
        elif prediction_type == "resource":
            return self._resource_forecast(historical, current, context)
        elif prediction_type == "duration":
            return self._duration_estimate(historical, current, context)
        else:
            return self._regime_transition(historical, current, context)

    # ── trend analysis (building block) ────────────────────────────────

    def _trend_analysis(self, values: list[float]) -> dict[str, Any]:
        """Basic linear trend extrapolation from a numeric series.

        Returns slope, intercept, r², projected next value, and confidence.
        """
        n = len(values)
        if n < 2:
            return {
                "slope": 0.0,
                "intercept": values[0] if values else 0.0,
                "r_squared": 0.0,
                "projected": values[-1] if values else 0.0,
                "confidence": 0.1,
                "trend": "insufficient_data",
            }

        xs = list(range(n))
        sum_x = sum(xs)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(xs, values))
        sum_x2 = sum(x * x for x in xs)

        denom = n * sum_x2 - sum_x * sum_x
        if abs(denom) < 1e-12:
            return {
                "slope": 0.0,
                "intercept": sum_y / n,
                "r_squared": 0.0,
                "projected": values[-1],
                "confidence": 0.2,
                "trend": "flat",
            }

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        y_mean = sum_y / n
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, values))
        r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))

        projected = intercept + slope * n

        if r_squared > 0.8:
            trend = "strong_up" if slope > 0 else "strong_down"
            confidence = min(0.85, 0.5 + r_squared * 0.35)
        elif r_squared > 0.4:
            trend = "up" if slope > 0 else "down"
            confidence = min(0.65, 0.3 + r_squared * 0.35)
        else:
            trend = "flat"
            confidence = 0.2

        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "projected": projected,
            "confidence": confidence,
            "trend": trend,
        }

    # ── market regime transition ───────────────────────────────────────

    def _regime_transition(
        self, historical: list[dict], current: dict, context: dict
    ) -> PredictionResult:
        """Forecast next market regime with transition probabilities."""
        prices = [d.get("price", 0) for d in historical if "price" in d]
        if not prices:
            return PredictionResult(
                prediction="unknown",
                confidence=0.0,
                uncertainty=1.0,
                horizon="none",
                risk_factors=["No price history available"],
            )

        trend = self._trend_analysis(prices)
        returns = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        volatility = self._stddev(returns) if returns else 0.0
        avg_price = sum(prices) / len(prices)
        rel_vol = volatility / avg_price if avg_price else 0.0

        current_regime = current.get("regime", "unknown")
        if current_regime == "unknown":
            if rel_vol > 0.03:
                current_regime = "volatile"
            elif trend["trend"] in ("strong_up", "up"):
                current_regime = "bull"
            elif trend["trend"] in ("strong_down", "down"):
                current_regime = "bear"
            else:
                current_regime = "sideways"

        transitions = {
            "bull":   {"bull": 0.5, "sideways": 0.3, "bear": 0.2},
            "bear":   {"bear": 0.5, "sideways": 0.3, "bull": 0.2},
            "sideways": {"bull": 0.35, "bear": 0.35, "sideways": 0.3},
            "volatile": {"volatile": 0.4, "bull": 0.3, "bear": 0.3},
        }
        probs = transitions.get(current_regime, {"sideways": 0.5, "bull": 0.25, "bear": 0.25})

        if rel_vol > 0.04:
            probs["volatile"] = max(probs.get("volatile", 0), 0.35)
            total = sum(probs.values())
            probs = {k: v / total for k, v in probs.items()}

        best = max(probs, key=probs.get)
        confidence = probs[best]
        uncertainty = 1.0 - confidence

        evidence = [
            f"Trend: {trend['trend']} (slope={trend['slope']:.4f}, r²={trend['r_squared']:.3f})",
            f"Volatility (abs): {volatility:.4f}, relative: {rel_vol:.4f}",
            f"Current regime: {current_regime}",
        ]
        risk_factors = []
        if uncertainty > 0.6:
            risk_factors.append("High regime uncertainty — transition likely")
        if rel_vol > 0.05:
            risk_factors.append(f"Elevated volatility (rel_vol={rel_vol:.4f})")
        if trend["r_squared"] < 0.3:
            risk_factors.append("Weak trend signal — regime boundaries unclear")

        horizon = context.get("horizon", "short_term")
        prediction_str = (
            f"Expected regime: {best} (prob={confidence:.2f}); "
            f"alternatives: {', '.join(f'{k}={v:.2f}' for k, v in probs.items() if k != best)}"
        )

        return PredictionResult(
            prediction=prediction_str,
            confidence=confidence,
            uncertainty=uncertainty,
            horizon=horizon,
            supporting_evidence=evidence,
            risk_factors=risk_factors,
        )

    # ── project / task risk assessment ─────────────────────────────────

    def _risk_assessment(
        self, historical: list[dict], current: dict, context: dict
    ) -> PredictionResult:
        """Score project/task risk from historical completion data."""
        tasks = historical if historical else [current]
        completed = [t for t in tasks if t.get("status") == "completed"]
        overdue = [t for t in tasks if t.get("status") == "overdue"]
        in_progress = [t for t in tasks if t.get("status") == "in_progress"]

        total = max(1, len(tasks))
        on_time_rate = len(completed) / total
        overdue_rate = len(overdue) / total

        durations = [
            t.get("actual_duration", t.get("estimated_duration", 0))
            for t in completed
            if t.get("actual_duration") or t.get("estimated_duration")
        ]
        estimates = [
            t.get("estimated_duration", 0)
            for t in completed
            if t.get("estimated_duration")
        ]
        avg_actual = sum(durations) / len(durations) if durations else 0
        avg_est = sum(estimates) / len(estimates) if estimates else 0
        estimation_bias = (avg_actual / avg_est - 1.0) if avg_est > 0 else 0.0

        blockers = current.get("blockers", [])
        dependency_count = current.get("dependency_count", 0)
        complexity = current.get("complexity", 3)  # 1-5 scale

        risk_score = 0.0
        risk_score += overdue_rate * 0.35
        risk_score += max(0, estimation_bias) * 0.2
        risk_score += min(1.0, len(blockers) / 5) * 0.2
        risk_score += min(1.0, dependency_count / 10) * 0.1
        risk_score += (complexity / 5) * 0.15
        risk_score = max(0.0, min(1.0, risk_score))

        confidence = min(0.9, 0.3 + on_time_rate * 0.4 + (1 - risk_score) * 0.2)
        uncertainty = 1.0 - confidence

        if risk_score > 0.7:
            level = "HIGH"
        elif risk_score > 0.4:
            level = "MEDIUM"
        else:
            level = "LOW"

        evidence = [
            f"On-time rate: {on_time_rate:.2%}",
            f"Overdue rate: {overdue_rate:.2%}",
            f"Estimation bias: {estimation_bias:+.2%}" if estimates else "No estimation history",
            f"Blockers: {len(blockers)}, Dependencies: {dependency_count}",
            f"Complexity: {complexity}/5",
        ]
        risk_factors = []
        if overdue_rate > 0.2:
            risk_factors.append(f"High overdue rate ({overdue_rate:.0%})")
        if estimation_bias > 0.15:
            risk_factors.append(f"Systematic under-estimation ({estimation_bias:+.0%})")
        if len(blockers) > 2:
            risk_factors.append(f"Multiple blockers ({len(blockers)})")
        if complexity > 4:
            risk_factors.append("High complexity")

        return PredictionResult(
            prediction=f"Risk level: {level} (score={risk_score:.2f})",
            confidence=confidence,
            uncertainty=uncertainty,
            horizon="current_task",
            supporting_evidence=evidence,
            risk_factors=risk_factors,
        )

    # ── system resource forecast ───────────────────────────────────────

    def _resource_forecast(
        self, historical: list[dict], current: dict, context: dict
    ) -> PredictionResult:
        """Predict resource usage from historical utilization data."""
        cpu = [d.get("cpu_pct", 0) for d in historical if "cpu_pct" in d]
        mem = [d.get("memory_pct", 0) for d in historical if "memory_pct" in d]
        disk = [d.get("disk_pct", 0) for d in historical if "disk_pct" in d]

        predictions = {}
        confidences = []

        for name, series in [("cpu", cpu), ("memory", mem), ("disk", disk)]:
            if len(series) < 3:
                predictions[name] = {
                    "current": series[-1] if series else 0,
                    "trend": "insufficient_data",
                    "projected": series[-1] if series else 0,
                }
                confidences.append(0.15)
                continue

            trend = self._trend_analysis(series)
            projected = max(0, min(100, trend["projected"]))
            predictions[name] = {
                "current": series[-1],
                "trend": trend["trend"],
                "slope_per_step": trend["slope"],
                "projected": projected,
                "r_squared": trend["r_squared"],
            }
            confidences.append(trend["confidence"])

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.15
        uncertainty = 1.0 - avg_conf

        evidence = []
        risk_factors = []
        for name, pred in predictions.items():
            evidence.append(
                f"{name}: current={pred.get('current', 0):.1f}%, "
                f"projected={pred.get('projected', 0):.1f}%, "
                f"trend={pred.get('trend', '?')}"
            )
            if pred.get("projected", 0) > 85:
                risk_factors.append(f"{name.upper()} projected above 85% — potential degradation")
            if pred.get("r_squared", 0) > 0.7 and pred.get("slope_per_step", 0) > 0:
                risk_factors.append(f"{name.upper()} shows consistent growth trend")

        cpu_proj = predictions.get("cpu", {}).get("projected", 0)
        mem_proj = predictions.get("memory", {}).get("projected", 0)
        if cpu_proj > 90 or mem_proj > 90:
            prediction_str = "System likely under pressure — resources may exhaust soon"
        elif cpu_proj > 70 or mem_proj > 70:
            prediction_str = "Moderate resource pressure expected"
        else:
            prediction_str = "Resource usage within safe bounds"

        horizon = context.get("horizon", "short_term")

        return PredictionResult(
            prediction=prediction_str,
            confidence=avg_conf,
            uncertainty=uncertainty,
            horizon=horizon,
            supporting_evidence=evidence,
            risk_factors=risk_factors,
        )

    # ── task duration estimate ─────────────────────────────────────────

    def _duration_estimate(
        self, historical: list[dict], current: dict, context: dict
    ) -> PredictionResult:
        """Estimate task duration from historical completion times."""
        completed = [t for t in historical if t.get("status") == "completed"]
        durations = [
            t.get("actual_duration", t.get("estimated_duration", 0))
            for t in completed
            if t.get("actual_duration") or t.get("estimated_duration")
        ]

        if not durations:
            return PredictionResult(
                prediction="No duration history — estimate unavailable",
                confidence=0.0,
                uncertainty=1.0,
                horizon="unknown",
                risk_factors=["No historical data for duration estimation"],
            )

        avg_dur = sum(durations) / len(durations)
        stddev = self._stddev(durations)
        current_est = current.get("estimated_duration", avg_dur)
        complexity_ratio = current.get("complexity", 3) / 3.0

        estimate = avg_dur * complexity_ratio
        lower = max(0, estimate - stddev)
        upper = estimate + stddev

        confidence = min(0.85, 0.3 + (1 - min(1, stddev / avg_dur if avg_dur else 1)) * 0.4)
        uncertainty = 1.0 - confidence

        evidence = [
            f"Historical avg duration: {avg_dur:.1f}s",
            f"Std deviation: {stddev:.1f}s",
            f"Complexity ratio: {complexity_ratio:.2f}",
            f"Range: [{lower:.1f}, {upper:.1f}]",
        ]
        risk_factors = []
        if stddev / avg_dur > 0.3 if avg_dur else False:
            risk_factors.append("High variance in historical durations")
        if complexity_ratio > 1.5:
            risk_factors.append("Task complexity above average")

        return PredictionResult(
            prediction=f"Estimated duration: {estimate:.1f}s (range: {lower:.1f}–{upper:.1f}s)",
            confidence=confidence,
            uncertainty=uncertainty,
            horizon="current_task",
            supporting_evidence=evidence,
            risk_factors=risk_factors,
        )

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _stddev(values: list[float]) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / (n - 1)
        return math.sqrt(variance)

    def _update_health(self, success: bool):
        with self._lock:
            total = self._total_calls
            failures = self._failures
        self._health_score = max(0.0, 1.0 - (failures / max(1, total)))
        if self._health_score < 0.3:
            self._status = ModelStatus.DEGRADED
        elif self._status == ModelStatus.DEGRADED and self._health_score >= 0.5:
            self._status = ModelStatus.ACTIVE
