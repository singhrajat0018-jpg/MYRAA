"""Model Fallback - ordered fallback chains per domain with adaptive health tracking.

When a specialist model fails, the chain returns the next available healthy
model. Failures and successes feed back to bias future fallback selection.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from ..model_contract import ModelDomain

logger = logging.getLogger(__name__)

_FAILURE_WINDOW_S = 300.0
_HEALTH_THRESHOLD = 0.3


@dataclass
class _ModelHealth:
    """Per-model health tracking within a fallback chain."""
    model_id: str
    failure_count: int = 0
    success_count: int = 0
    recent_failures: list[float] = field(default_factory=list)
    last_success: Optional[float] = None

    @property
    def success_rate(self) -> float:
        total = self.failure_count + self.success_count
        if total == 0:
            return 1.0
        return self.success_count / total

    @property
    def recent_failure_rate(self) -> float:
        now = time.time()
        cutoff = now - _FAILURE_WINDOW_S
        self.recent_failures = [t for t in self.recent_failures if t > cutoff]
        total = self.failure_count + self.success_count
        if total == 0:
            return 0.0
        return len(self.recent_failures) / total

    def is_healthy(self) -> bool:
        if self.success_count == 0 and self.failure_count > 0:
            return False
        if self.recent_failure_rate >= _HEALTH_THRESHOLD:
            return False
        return self.success_rate >= _HEALTH_THRESHOLD


class FallbackChain:
    """Ordered fallback chains per domain with health-aware selection."""

    def __init__(self, chains: dict[ModelDomain, list[str]]) -> None:
        self._chains: dict[ModelDomain, list[str]] = {k: list(v) for k, v in chains.items()}
        self._health: dict[str, _ModelHealth] = {}
        self._lock = threading.Lock()
        for model_ids in self._chains.values():
            for mid in model_ids:
                if mid not in self._health:
                    self._health[mid] = _ModelHealth(model_id=mid)

    def get_fallback(self, domain: ModelDomain, failed_model_id: str) -> Optional[str]:
        """Return the next healthy model in the chain after *failed_model_id*, or None."""
        with self._lock:
            chain = self._chains.get(domain, [])
            if failed_model_id not in chain:
                logger.warning("Model %s not in fallback chain for %s", failed_model_id, domain.value)
                return None
            idx = chain.index(failed_model_id)
            for candidate_id in chain[idx + 1:]:
                health = self._health.get(candidate_id)
                if health is not None and not health.is_healthy():
                    continue
                return candidate_id
            return None

    def get_first_healthy(self, domain: ModelDomain) -> Optional[str]:
        """Return the first healthy model in the chain for *domain*."""
        with self._lock:
            for mid in self._chains.get(domain, []):
                health = self._health.get(mid)
                if health is None or health.is_healthy():
                    return mid
            return None

    def record_failure(self, model_id: str, error: str = "") -> None:
        with self._lock:
            health = self._health.get(model_id)
            if health is None:
                health = _ModelHealth(model_id=model_id)
                self._health[model_id] = health
            health.failure_count += 1
            health.recent_failures.append(time.time())
            logger.warning("Fallback recorded failure for %s: %s", model_id, error)

    def record_success(self, model_id: str) -> None:
        with self._lock:
            health = self._health.get(model_id)
            if health is None:
                health = _ModelHealth(model_id=model_id)
                self._health[model_id] = health
            health.success_count += 1
            health.last_success = time.time()

    def is_healthy(self, model_id: str) -> bool:
        with self._lock:
            health = self._health.get(model_id)
            if health is None:
                return True
            return health.is_healthy()

    def health_report(self) -> dict[str, dict]:
        with self._lock:
            report: dict[str, dict] = {}
            for mid, h in self._health.items():
                report[mid] = {
                    "success_rate": round(h.success_rate, 3),
                    "recent_failure_rate": round(h.recent_failure_rate, 3),
                    "healthy": h.is_healthy(),
                    "failure_count": h.failure_count,
                    "success_count": h.success_count,
                    "last_success": h.last_success,
                }
            return report

    def get_chain(self, domain: ModelDomain) -> list[str]:
        with self._lock:
            return list(self._chains.get(domain, []))


def build_default_chains() -> dict[ModelDomain, list[str]]:
    """Return sensible default fallback chains for every known domain."""
    return {
        ModelDomain.VISION: ["vision-specialist", "multimodal-general", "general-purpose"],
        ModelDomain.TRADING: ["trading-specialist", "prediction-general", "general-purpose"],
        ModelDomain.VOICE: ["voice-specialist", "multimodal-general", "general-purpose"],
        ModelDomain.PREDICTION: ["prediction-specialist", "trading-specialist", "general-purpose"],
        ModelDomain.PERSONALIZATION: ["personalization-specialist", "general-purpose"],
        ModelDomain.MULTIMODAL: ["multimodal-specialist", "general-purpose"],
        ModelDomain.GENERAL: ["general-purpose"],
    }
