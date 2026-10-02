"""Multimodal Neural Fusion Engine -- combines specialist model outputs.

Flow:
list[ModelResult] -> NeuralFusion.fuse() -> FusionResult

Uses intelligent weighting: confidence x quality x freshness decay.
Detects disagreement, outliers, and evidence quality across models.
NOT simple averaging -- each result is weighted by multiple factors.
"""

from __future__ import annotations

import math
import time
import threading
import logging
from typing import Any, Optional

from ..model_contract import (
    ModelResult, FusionResult, ModelDomain,
)

logger = logging.getLogger(__name__)

_FRESHNESS_HALF_LIFE_S: float = 60.0
_MIN_WEIGHT: float = 0.01
_OUTLIER_STD_THRESHOLD: float = 1.5


class NeuralFusion:
    """Multimodal Neural Fusion Engine that combines specialist outputs.

    Thread-safe. Produces FusionResult with intelligent weighting based on
    confidence, quality, freshness, source reliability, and domain relevance.
    """

    _instance: Optional['NeuralFusion'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> 'NeuralFusion':
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._fusion_count: int = 0
        self._disagreement_count: int = 0
        self._lock = threading.Lock()
        self._initialized = True

    @classmethod
    def new(cls) -> 'NeuralFusion':
        return cls()

    @property
    def fusion_count(self) -> int:
        return self._fusion_count

    @property
    def disagreement_count(self) -> int:
        return self._disagreement_count

    def fuse(
        self,
        results: list[ModelResult],
        domain: ModelDomain = ModelDomain.GENERAL,
        context: dict[str, Any] | None = None,
    ) -> FusionResult:
        start = time.perf_counter()
        ctx = context or {}
        request_id = ctx.get("request_id", "fusion_unknown")

        if not results:
            return FusionResult(
                request_id=request_id, domain=domain, outputs=[],
                fused_output=None, combined_confidence=0.0,
                combined_uncertainty=1.0, disagreement_score=0.0,
                ensemble_size=0, latency_ms=0.0, warnings=["No results to fuse"],
            )

        weights = self.weighted_combine(results)
        disagreement = self.calculate_disagreement(results)
        outliers = self.detect_outliers(results)
        outlier_ids = {o.model_id for o in outliers}

        total_weight = sum(weights)
        combined_confidence = 0.0
        combined_uncertainty = 0.0
        if total_weight > 0:
            combined_confidence = sum(
                r.confidence * w for r, w in zip(results, weights)
            ) / total_weight
            combined_uncertainty = sum(
                r.uncertainty * w for r, w in zip(results, weights)
            ) / total_weight

        if outliers:
            outlier_penalty = len(outliers) / max(len(results), 1) * 0.3
            combined_confidence = max(0.0, combined_confidence - outlier_penalty)

        if disagreement > 0.5:
            combined_confidence *= (1.0 - disagreement * 0.2)

        fused_output = self._select_fused_output(results, weights, outlier_ids)
        warnings: list[str] = []
        if disagreement > 0.5:
            warnings.append(f"High disagreement detected: {disagreement:.2f}")
        if outliers:
            warnings.append(f"Outliers detected: {[o.model_id for o in outliers]}")

        elapsed = (time.perf_counter() - start) * 1000
        with self._lock:
            self._fusion_count += 1
            if disagreement > 0.3:
                self._disagreement_count += 1

        return FusionResult(
            request_id=request_id, domain=domain, outputs=results,
            fused_output=fused_output,
            combined_confidence=round(combined_confidence, 4),
            combined_uncertainty=round(combined_uncertainty, 4),
            disagreement_score=round(disagreement, 4),
            ensemble_size=len(results),
            latency_ms=round(elapsed, 2),
            warnings=warnings,
        )

    def weighted_combine(self, results: list[ModelResult]) -> list[float]:
        now = time.time()
        weights: list[float] = []

        for r in results:
            base = r.confidence * r.quality
            age_s = max(0.0, now - r.timestamp)
            freshness = math.pow(0.5, age_s / _FRESHNESS_HALF_LIFE_S)
            source_mult = self._source_reliability(r.source)
            uncertainty_mult = max(0.1, 1.0 - r.uncertainty * 0.5)
            w = base * freshness * source_mult * uncertainty_mult
            weights.append(max(_MIN_WEIGHT, w))

        return weights

    def calculate_disagreement(self, results: list[ModelResult]) -> float:
        if len(results) < 2:
            return 0.0

        confidences = [r.confidence for r in results]
        conf_spread = max(confidences) - min(confidences)

        output_divergence = self._compute_output_divergence(results)

        uncertainties = [r.uncertainty for r in results]
        unc_spread = max(uncertainties) - min(uncertainties)

        direction_conflict = self._detect_directional_conflict(results)

        disagreement = (
            conf_spread * 0.25
            + output_divergence * 0.35
            + unc_spread * 0.15
            + direction_conflict * 0.25
        )

        return min(1.0, max(0.0, disagreement))

    def detect_outliers(self, results: list[ModelResult]) -> list[ModelResult]:
        if len(results) < 3:
            return []

        weights = self.weighted_combine(results)
        total_w = sum(weights)
        if total_w <= 0:
            return []

        mean_conf = sum(r.confidence * w for r, w in zip(results, weights)) / total_w
        variance = sum(
            w * (r.confidence - mean_conf) ** 2 for r, w in zip(results, weights)
        ) / total_w
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std < 0.01:
            return []

        outliers: list[ModelResult] = []
        for r in results:
            z_score = abs(r.confidence - mean_conf) / std
            if z_score > _OUTLIER_STD_THRESHOLD:
                outliers.append(r)

        return outliers

    def _source_reliability(self, source: str) -> float:
        reliable = {
            "trading_specialist": 1.1,
            "vision_specialist": 1.0,
            "voice_specialist": 1.0,
            "multimodal_specialist": 1.05,
            "prediction_specialist": 0.95,
            "personalization_specialist": 0.9,
        }
        for key, mult in reliable.items():
            if key in source:
                return mult
        if "error" in source or "fallback" in source:
            return 0.5
        if "timeout" in source:
            return 0.3
        return 0.85

    def _compute_output_divergence(self, results: list[ModelResult]) -> float:
        if len(results) < 2:
            return 0.0

        outputs = [r.output for r in results]
        numeric_outputs = []
        for o in outputs:
            if isinstance(o, (int, float)):
                numeric_outputs.append(float(o))
            elif hasattr(o, "confidence"):
                numeric_outputs.append(float(o.confidence))
            elif hasattr(o, "pattern_score"):
                numeric_outputs.append(float(o.pattern_score))

        if len(numeric_outputs) >= 2:
            spread = max(numeric_outputs) - min(numeric_outputs)
            return min(1.0, spread)

        str_outputs = [str(o)[:200] for o in outputs]
        unique = set(str_outputs)
        if len(unique) <= 1:
            return 0.0
        return min(1.0, len(unique) / len(results) * 0.5)

    def _detect_directional_conflict(self, results: list[ModelResult]) -> float:
        if len(results) < 2:
            return 0.0

        bullish = 0
        bearish = 0
        neutral = 0

        for r in results:
            o = r.output
            if o is None:
                neutral += 1
                continue

            score = None
            if hasattr(o, "trend_score"):
                score = o.trend_score
            elif hasattr(o, "confidence") and hasattr(o, "uncertainty"):
                score = o.confidence if o.uncertainty < 0.5 else None
            elif isinstance(o, dict):
                score = o.get("trend_score") or o.get("signal")

            if score is None:
                neutral += 1
            elif score > 0.6:
                bullish += 1
            elif score < 0.4:
                bearish += 1
            else:
                neutral += 1

        if bullish > 0 and bearish > 0:
            conflict_ratio = min(bullish, bearish) / max(bullish + bearish, 1)
            return min(1.0, conflict_ratio * 2.0)

        return 0.0

    def _select_fused_output(
        self,
        results: list[ModelResult],
        weights: list[float],
        outlier_ids: set[str],
    ) -> Any:
        candidates = [
            (r, w) for r, w in zip(results, weights) if r.model_id not in outlier_ids
        ]
        if not candidates:
            candidates = list(zip(results, weights))
        candidates.sort(key=lambda pair: pair[1], reverse=True)
        best = candidates[0][0]
        return best.output

    def reset(self) -> None:
        with self._lock:
            self._fusion_count = 0
            self._disagreement_count = 0

    @classmethod
    def reset_singleton(cls) -> None:
        with cls._lock_class:
            cls._instance = None
