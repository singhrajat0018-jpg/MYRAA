"""Model Registry — single source of truth for all registered neural models.

Thread-safe singleton that tracks every model's spec, lifecycle state,
benchmark scores, health, and promotion history.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..model_contract import ModelDomain, ModelSpec, ModelStatus

logger = logging.getLogger(__name__)

_PROMOTION_STATES = [
    ModelStatus.ACTIVE,
    ModelStatus.TESTING,
    ModelStatus.STAGED,
    ModelStatus.ACTIVE,
]


@dataclass
class _ModelEntry:
    """Internal bookkeeping for a single registered model."""
    spec: ModelSpec
    status: ModelStatus = ModelStatus.TESTING
    enabled: bool = True
    registered_at: float = field(default_factory=time.time)
    last_validated: Optional[float] = None
    last_benchmark: Optional[float] = None
    latency_p50_ms: float = 0.0
    latency_p99_ms: float = 0.0
    quality_score: float = 0.0
    memory_mb: float = 0.0
    gpu_mb: float = 0.0
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    confidence_calibration: float = 1.0
    promotion_history: list[dict[str, Any]] = field(default_factory=list)
    failure_count: int = 0
    success_count: int = 0

    def to_summary(self) -> dict[str, Any]:
        return {
            "model_id": self.spec.model_id,
            "domain": self.spec.domain.value,
            "version": self.spec.version,
            "provider": self.spec.provider,
            "status": self.status.value,
            "enabled": self.enabled,
            "latency_p50_ms": round(self.latency_p50_ms, 2),
            "quality_score": round(self.quality_score, 3),
            "benchmark_scores": {k: round(v, 3) for k, v in self.benchmark_scores.items()},
            "confidence_calibration": round(self.confidence_calibration, 3),
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_validated": self.last_validated,
            "last_benchmark": self.last_benchmark,
        }


class ModelRegistry:
    """Thread-safe singleton registry for all neural models."""

    _instance: Optional[ModelRegistry] = None
    _lock_cls = threading.Lock()

    def __new__(cls) -> ModelRegistry:
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._lock = threading.Lock()
                    inst._models: dict[str, _ModelEntry] = {}
                    cls._instance = inst
        return cls._instance

    # -- public API --

    def register(self, spec: ModelSpec, *, status: ModelStatus = ModelStatus.TESTING) -> None:
        with self._lock:
            if spec.model_id in self._models:
                raise ValueError(f"Model already registered: {spec.model_id}")
            entry = _ModelEntry(spec=spec, status=status)
            self._models[spec.model_id] = entry
            logger.info("Registered model %s (domain=%s, version=%s)", spec.model_id, spec.domain.value, spec.version)

    def unregister(self, model_id: str) -> _ModelEntry:
        with self._lock:
            entry = self._models.pop(model_id, None)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            logger.info("Unregistered model %s", model_id)
            return entry

    def get(self, model_id: str) -> Optional[_ModelEntry]:
        with self._lock:
            return self._models.get(model_id)

    def get_active_for_domain(self, domain: ModelDomain) -> Optional[_ModelEntry]:
        """Return the best active model for *domain* (highest quality_score)."""
        with self._lock:
            candidates = [
                e for e in self._models.values()
                if e.status == ModelStatus.ACTIVE
                and e.enabled
                and e.spec.matches_domain(domain)
            ]
            if not candidates:
                return None
            return max(candidates, key=lambda e: e.quality_score)

    def set_status(self, model_id: str, status: ModelStatus) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            old = entry.status
            entry.status = status
            logger.info("Model %s status: %s -> %s", model_id, old.value, status.value)

    def update_benchmark(self, model_id: str, scores: dict[str, float], *, latency_p50: float = 0.0, latency_p99: float = 0.0, quality: float = 0.0) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            entry.benchmark_scores.update(scores)
            entry.latency_p50_ms = latency_p50
            entry.latency_p99_ms = latency_p99
            entry.quality_score = quality
            entry.last_benchmark = time.time()

    def update_resources(self, model_id: str, *, memory_mb: float = 0.0, gpu_mb: float = 0.0) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            entry.memory_mb = memory_mb
            entry.gpu_mb = gpu_mb

    def set_confidence_calibration(self, model_id: str, calibration: float) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            entry.confidence_calibration = calibration

    def record_success(self, model_id: str) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is not None:
                entry.success_count += 1

    def record_failure(self, model_id: str) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is not None:
                entry.failure_count += 1

    def enable(self, model_id: str) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            entry.enabled = True

    def disable(self, model_id: str) -> None:
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                raise KeyError(f"Model not registered: {model_id}")
            entry.enabled = False

    # -- promotion / demotion --

    def validate_promotion(self, model_id: str) -> tuple[bool, list[str]]:
        """Check prerequisites before promotion. Returns (ok, reasons)."""
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                return False, ["model not registered"]
            reasons: list[str] = []
            if not entry.enabled:
                reasons.append("model is disabled")
            if entry.status not in (ModelStatus.TESTING, ModelStatus.STAGED):
                reasons.append(f"status '{entry.status.value}' not promotable")
            if entry.failure_count > 0 and entry.success_count == 0:
                reasons.append("has failures but no successes")
            if entry.quality_score <= 0:
                reasons.append("no quality benchmark recorded")
            if entry.last_validated is None:
                reasons.append("never validated")
            return len(reasons) == 0, reasons

    def promote_model(self, model_id: str) -> tuple[bool, str]:
        """Safe promotion through the full pipeline:
        REGISTER → VALIDATE → BENCHMARK → COMPARE → SECURITY_CHECK → REGRESSION → STAGE → PROMOTE
        Returns (success, message).
        """
        ok, reasons = self.validate_promotion(model_id)
        if not ok:
            return False, "; ".join(reasons)

        with self._lock:
            entry = self._models.get(model_id)

            stages_done: list[str] = []
            now = time.time()

            # VALIDATE — already checked in validate_promotion
            stages_done.append("VALIDATE")

            # BENCHMARK — must have scores recorded
            if not entry.benchmark_scores:
                return False, "no benchmark scores recorded"
            stages_done.append("BENCHMARK")

            # COMPARE — must not be worse than current active in same domain
            current_active = self._get_best_active(entry.spec.domain)
            if current_active and entry.quality_score < current_active.quality_score:
                return False, f"quality {entry.quality_score:.3f} < current active {current_active.quality_score:.3f}"
            stages_done.append("COMPARE")

            # SECURITY_CHECK — confidence calibration must be sane
            if entry.confidence_calibration < 0.5:
                return False, f"confidence calibration too low: {entry.confidence_calibration:.3f}"
            stages_done.append("SECURITY_CHECK")

            # REGRESSION — no recent failures
            if entry.failure_count > entry.success_count:
                return False, f"failure_count ({entry.failure_count}) > success_count ({entry.success_count})"
            stages_done.append("REGRESSION")

            # STAGE → PROMOTE
            entry.status = ModelStatus.ACTIVE
            entry.promotion_history.append({
                "action": "promote",
                "timestamp": now,
                "stages": stages_done,
            })
            logger.info("Promoted model %s through stages %s", model_id, stages_done)
            return True, f"promoted through {', '.join(stages_done)}"

    def demote_model(self, model_id: str, reason: str = "") -> tuple[bool, str]:
        """Safe demotion: ACTIVE → DEGRADED → DISABLED. Cannot demote already-disabled."""
        with self._lock:
            entry = self._models.get(model_id)
            if entry is None:
                return False, f"model not registered: {model_id}"

            now = time.time()
            old_status = entry.status

            if entry.status == ModelStatus.ACTIVE:
                entry.status = ModelStatus.DEGRADED
            elif entry.status == ModelStatus.DEGRADED:
                entry.status = ModelStatus.DISABLED
            elif entry.status == ModelStatus.STAGED:
                entry.status = ModelStatus.DISABLED
            elif entry.status == ModelStatus.TESTING:
                entry.status = ModelStatus.DISABLED
            elif entry.status in (ModelStatus.DISABLED, ModelStatus.RETIRED):
                return False, f"cannot demote from {entry.status.value}"

            entry.promotion_history.append({
                "action": "demote",
                "from": old_status.value,
                "to": entry.status.value,
                "reason": reason,
                "timestamp": now,
            })
            logger.info("Demoted model %s: %s -> %s (reason=%s)", model_id, old_status.value, entry.status.value, reason)
            return True, f"demoted from {old_status.value} to {entry.status.value}"

    # -- reporting --

    def health_report(self) -> dict[str, Any]:
        with self._lock:
            by_status: dict[str, int] = {}
            by_domain: dict[str, dict[str, int]] = {}
            total = 0

            for entry in self._models.values():
                total += 1
                s = entry.status.value
                by_status[s] = by_status.get(s, 0) + 1

                d = entry.spec.domain.value
                if d not in by_domain:
                    by_domain[d] = {"total": 0, "active": 0, "degraded": 0, "disabled": 0}
                by_domain[d]["total"] += 1
                if entry.status == ModelStatus.ACTIVE:
                    by_domain[d]["active"] += 1
                elif entry.status == ModelStatus.DEGRADED:
                    by_domain[d]["degraded"] += 1
                elif entry.status == ModelStatus.DISABLED:
                    by_domain[d]["disabled"] += 1

            active_models = [
                e.to_summary()
                for e in self._models.values()
                if e.status == ModelStatus.ACTIVE
            ]

            return {
                "total_models": total,
                "by_status": by_status,
                "by_domain": by_domain,
                "active_models": active_models,
                "generated_at": time.time(),
            }

    def all_entries(self) -> list[dict[str, Any]]:
        """Snapshot of every registered model as a plain dict."""
        with self._lock:
            return [e.to_summary() for e in self._models.values()]

    # -- internals --

    def _get_best_active(self, domain: ModelDomain) -> Optional[_ModelEntry]:
        candidates = [
            e for e in self._models.values()
            if e.status == ModelStatus.ACTIVE
            and e.enabled
            and e.spec.matches_domain(domain)
        ]
        return max(candidates, key=lambda e: e.quality_score) if candidates else None
