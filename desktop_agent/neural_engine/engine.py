"""Neural Intelligence Engine — central inference orchestrator.

Canonical flow:
request → neural task → select specialist model(s) → preprocess → inference
→ normalize → confidence → fusion → domain engine → verification

This engine ENHANCES existing MYRAA intelligence.
It does NOT replace Super-Brain, Memory, Vision, Trading, or Verification.
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Any, Optional
from collections import OrderedDict

from .model_contract import (
    ModelSpec, ModelResult, InferenceRequest, FusionResult,
    ModelDomain, ModelModality, ModelStatus, LatencyClass, ModelDeployment,
)

logger = logging.getLogger(__name__)


class NeuralTelemetry:
    """Tracks inference metrics without leaking secrets."""

    def __init__(self, max_history: int = 500):
        self._max_history = max_history
        self._latencies: list[float] = []
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._fallbacks: int = 0
        self._errors: int = 0
        self._total_inferences: int = 0
        self._domain_counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def record_inference(self, domain: str, latency_ms: float,
                         cache_hit: bool = False, fallback: bool = False,
                         error: bool = False, confidence: float = 0.0):
        with self._lock:
            self._total_inferences += 1
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._max_history:
                self._latencies = self._latencies[-self._max_history:]
            if cache_hit:
                self._cache_hits += 1
            if fallback:
                self._fallbacks += 1
            if error:
                self._errors += 1
            self._domain_counts[domain] = self._domain_counts.get(domain, 0) + 1

    def summary(self) -> dict:
        with self._lock:
            if not self._latencies:
                return {"total": 0, "status": "no_data"}
            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)
            return {
                "total_inferences": self._total_inferences,
                "cache_hit_rate": round(self._cache_hits / max(1, self._total_inferences), 3),
                "fallback_rate": round(self._fallbacks / max(1, self._total_inferences), 3),
                "error_rate": round(self._errors / max(1, self._total_inferences), 3),
                "p50_ms": round(sorted_lat[n // 2], 1),
                "p90_ms": round(sorted_lat[int(n * 0.9)], 1),
                "p99_ms": round(sorted_lat[int(n * 0.99)], 1),
                "domain_counts": dict(self._domain_counts),
            }

    def reset(self):
        with self._lock:
            self._latencies.clear()
            self._cache_hits = 0
            self._cache_misses = 0
            self._fallbacks = 0
            self._errors = 0
            self._total_inferences = 0
            self._domain_counts.clear()


class InferenceCache:
    """LRU cache for inference results with TTL."""

    def __init__(self, max_size: int = 200, default_ttl_ms: float = 30000.0):
        self._max_size = max_size
        self._default_ttl_ms = default_ttl_ms
        self._cache: OrderedDict[str, tuple[float, ModelResult]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[ModelResult]:
        with self._lock:
            if key in self._cache:
                ts, result = self._cache[key]
                if (time.time() - ts) * 1000 < self._default_ttl_ms:
                    self._cache.move_to_end(key)
                    return result
                del self._cache[key]
            return None

    def put(self, key: str, result: ModelResult, ttl_ms: Optional[float] = None):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (time.time(), result)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class SpecialistModelWrapper:
    """Wraps a callable into the standardized ModelSpec + ModelResult contract."""

    def __init__(self, spec: ModelSpec, inference_fn, fallback_fn=None):
        self.spec = spec
        self._inference_fn = inference_fn
        self._fallback_fn = fallback_fn
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0
        self._latencies: list[float] = []
        self._last_error: Optional[str] = None

    @property
    def model_id(self) -> str:
        return self.spec.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    @property
    def health_score(self) -> float:
        return self._health_score

    def inference(self, request: InferenceRequest) -> ModelResult:
        start = time.perf_counter()
        self._total_calls += 1
        try:
            output = self._inference_fn(request)
            elapsed = (time.perf_counter() - start) * 1000
            self._latencies.append(elapsed)
            if len(self._latencies) > 100:
                self._latencies = self._latencies[-100:]
            self._update_health(success=True)
            if isinstance(output, ModelResult):
                return output
            return ModelResult(
                model_id=self.model_id,
                output=output,
                confidence=0.5,
                uncertainty=0.5,
                latency_ms=elapsed,
                timestamp=time.time(),
                source=self.spec.provider or "local",
                version=self.spec.version,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            self._failures += 1
            self._last_error = str(e)
            self._update_health(success=False)
            if self._fallback_fn:
                try:
                    output = self._fallback_fn(request)
                    return ModelResult(
                        model_id=f"{self.model_id}_fallback",
                        output=output,
                        confidence=0.3,
                        uncertainty=0.7,
                        latency_ms=elapsed,
                        timestamp=time.time(),
                        source="fallback",
                        warnings=[f"Fallback used: {e}"],
                        version=self.spec.version,
                    )
                except Exception:
                    pass
            return ModelResult(
                model_id=self.model_id,
                output=None,
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="error",
                warnings=[str(e)],
                version=self.spec.version,
            )

    def _update_health(self, success: bool):
        recent_failures = self._failures
        recent_calls = self._total_calls
        self._health_score = max(0.0, 1.0 - (recent_failures / max(1, recent_calls)))
        if self._health_score < 0.3:
            self._status = ModelStatus.DEGRADED

    def avg_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)


class NeuralEngine:
    """Central neural intelligence orchestrator.

    Singleton. Connects specialist models for vision, trading, design,
    voice, prediction, personalization, and multimodal intelligence.
    """

    _instance: Optional['NeuralEngine'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._models: dict[str, SpecialistModelWrapper] = {}
        self._domain_models: dict[ModelDomain, list[str]] = {}
        self._cache = InferenceCache()
        self._telemetry = NeuralTelemetry()
        self._lock = threading.Lock()

    @classmethod
    def singleton(cls) -> 'NeuralEngine':
        return cls()

    @classmethod
    def reset_singleton(cls):
        with cls._lock_class:
            if cls._instance:
                cls._instance._cache.clear()
                cls._instance._telemetry.reset()
            cls._instance = None

    def register_model(self, spec: ModelSpec, inference_fn, fallback_fn=None):
        with self._lock:
            wrapper = SpecialistModelWrapper(spec, inference_fn, fallback_fn)
            self._models[spec.model_id] = wrapper
            self._domain_models.setdefault(spec.domain, []).append(spec.model_id)
            logger.info(f"Registered neural model: {spec.model_id} ({spec.domain.value})")

    def unregister_model(self, model_id: str) -> bool:
        with self._lock:
            if model_id not in self._models:
                return False
            wrapper = self._models.pop(model_id)
            domain_list = self._domain_models.get(wrapper.spec.domain, [])
            if model_id in domain_list:
                domain_list.remove(model_id)
            return True

    def get_model(self, model_id: str) -> Optional[SpecialistModelWrapper]:
        return self._models.get(model_id)

    def list_models(self, domain: Optional[ModelDomain] = None,
                    status: Optional[ModelStatus] = None) -> list[ModelSpec]:
        result = []
        for wrapper in self._models.values():
            if domain and wrapper.spec.domain != domain:
                continue
            if status and wrapper.status != status:
                continue
            result.append(wrapper.spec)
        return result

    def _select_models(self, request: InferenceRequest) -> list[SpecialistModelWrapper]:
        if request.preferred_model_id:
            wrapper = self._models.get(request.preferred_model_id)
            if wrapper and wrapper.status in (ModelStatus.ACTIVE, ModelStatus.STAGED):
                return [wrapper]

        candidates = []
        for model_id in self._domain_models.get(request.domain, []):
            wrapper = self._models.get(model_id)
            if wrapper and wrapper.status in (ModelStatus.ACTIVE, ModelStatus.STAGED):
                candidates.append(wrapper)

        for model_id, wrapper in self._models.items():
            if wrapper.spec.matches_domain(request.domain) and wrapper.spec.matches_modality(request.modality):
                if wrapper not in candidates and wrapper.status in (ModelStatus.ACTIVE,):
                    candidates.append(wrapper)

        candidates.sort(key=lambda w: w.health_score, reverse=True)
        return candidates

    def infer(self, request: InferenceRequest) -> ModelResult:
        if request.cache_key:
            cached = self._cache.get(request.cache_key)
            if cached:
                self._telemetry.record_inference(
                    request.domain.value, 0.0, cache_hit=True,
                    confidence=cached.confidence,
                )
                return ModelResult(
                    model_id=cached.model_id,
                    output=cached.output,
                    confidence=cached.confidence,
                    uncertainty=cached.uncertainty,
                    latency_ms=0.0,
                    timestamp=cached.timestamp,
                    source=cached.source,
                    cached=True,
                    version=cached.version,
                )

        candidates = self._select_models(request)
        if not candidates:
            self._telemetry.record_inference(request.domain.value, 0.0, error=True)
            return ModelResult(
                model_id="none",
                output=None,
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=0.0,
                timestamp=time.time(),
                source="no_model",
                warnings=["No suitable model found"],
            )

        start = time.perf_counter()
        best_result: Optional[ModelResult] = None
        for wrapper in candidates:
            result = wrapper.inference(request)
            if best_result is None or result.confidence > best_result.confidence:
                best_result = result
            if result.confidence >= request.confidence_threshold:
                break

        elapsed = (time.perf_counter() - start) * 1000
        if best_result is None:
            best_result = ModelResult(
                model_id="none",
                output=None,
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="all_failed",
                warnings=["All candidate models failed"],
            )

        self._telemetry.record_inference(
            request.domain.value, elapsed,
            confidence=best_result.confidence,
        )

        if request.cache_key:
            self._cache.put(request.cache_key, best_result)

        return best_result

    def infer_parallel(self, requests: list[InferenceRequest],
                       timeout_ms: float = 10000.0) -> list[ModelResult]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results: list[Optional[ModelResult]] = [None] * len(requests)

        with ThreadPoolExecutor(max_workers=min(len(requests), 4)) as pool:
            future_to_idx = {}
            for i, req in enumerate(requests):
                future = pool.submit(self.infer, req)
                future_to_idx[future] = i

            for future in as_completed(future_to_idx, timeout=timeout_ms / 1000.0):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result(timeout=0)
                except Exception:
                    results[idx] = ModelResult(
                        model_id="timeout",
                        output=None,
                        confidence=0.0,
                        uncertainty=1.0,
                        latency_ms=timeout_ms,
                        timestamp=time.time(),
                        source="timeout",
                        warnings=["Inference timed out"],
                    )

        return [r or ModelResult(
            model_id="none", output=None, confidence=0.0, uncertainty=1.0,
            latency_ms=0, timestamp=time.time(), source="missing",
        ) for r in results]

    def select_best_for_domain(self, domain: ModelDomain,
                               modality: ModelModality = ModelModality.TEXT
                               ) -> Optional[ModelSpec]:
        request = InferenceRequest(domain=domain, modality=modality)
        candidates = self._select_models(request)
        if not candidates:
            return None
        return candidates[0].spec

    def model_health(self) -> dict[str, dict]:
        result = {}
        for model_id, wrapper in self._models.items():
            result[model_id] = {
                "status": wrapper.status.value,
                "health_score": round(wrapper.health_score, 3),
                "avg_latency_ms": round(wrapper.avg_latency_ms(), 1),
                "total_calls": wrapper._total_calls,
                "failures": wrapper._failures,
                "domain": wrapper.spec.domain.value,
            }
        return result

    def telemetry_summary(self) -> dict:
        return self._telemetry.summary()

    def cache_stats(self) -> dict:
        return {"size": self._cache.size}

    def invalidate_cache(self, key: Optional[str] = None):
        if key:
            self._cache.invalidate(key)
        else:
            self._cache.clear()
