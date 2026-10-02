"""Performance telemetry: aggregate latency reports and degraded-mode detection."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Optional
from collections import deque

from .latency_tracker import LatencyTracker


@dataclass
class LatencyReport:
    timestamp: float
    stage_latencies: dict[str, float]
    total_ms: float
    cache_hit_rate: float
    parallel_tasks: int
    fast_path_hit: bool
    model_tier: str
    degraded: bool
    summary: str = ""


class PerformanceTelemetry:
    """Collect and summarize performance telemetry across all subsystems."""

    _instance: Optional['PerformanceTelemetry'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, history_size: int = 200):
        # Singleton construction is serialized by the class lock (see
        # __new__); __init__ runs once per returned instance, but two threads
        # may both reach here for the same fresh instance. Guard with the
        # class lock so fields are initialized exactly once.
        with PerformanceTelemetry._lock_class:
            if getattr(self, "_initialized", False):
                return
            self._initialized = True
            self._history: deque[LatencyReport] = deque(maxlen=history_size)
            self._request_count = 0
            self._fast_path_count = 0
            self._total_latency_ms = 0.0
            # Plain Lock: every critical section below is O(1)/O(n-copy) and
            # NEVER nests another public method that acquires this lock.
            self._lock = threading.Lock()

    def record(self, report: LatencyReport):
        with self._lock:
            self._history.append(report)
            self._request_count += 1
            self._total_latency_ms += report.total_ms
            if report.fast_path_hit:
                self._fast_path_count += 1

    def build_report(self, stage_latencies: dict[str, float], total_ms: float,
                     cache_hit_rate: float = 0.0, parallel_tasks: int = 0,
                     fast_path_hit: bool = False, model_tier: str = "fast",
                     degraded: bool = False) -> LatencyReport:
        report = LatencyReport(
            timestamp=time.time(),
            stage_latencies=stage_latencies,
            total_ms=total_ms,
            cache_hit_rate=cache_hit_rate,
            parallel_tasks=parallel_tasks,
            fast_path_hit=fast_path_hit,
            model_tier=model_tier,
            degraded=degraded,
        )
        avg = self.avg_latency()
        report.summary = (
            f"Total: {total_ms:.1f}ms | Avg: {avg:.1f}ms | "
            f"Cache: {cache_hit_rate:.0%} | Fast: {self.fast_path_ratio():.0%} | "
            f"{'DEGRADED' if degraded else 'OK'}"
        )
        self.record(report)
        return report

    def avg_latency(self) -> float:
        with self._lock:
            if not self._history:
                return 0.0
            return self._total_latency_ms / self._request_count if self._request_count else 0.0

    def fast_path_ratio(self) -> float:
        with self._lock:
            return self._fast_path_count / self._request_count if self._request_count else 0.0

    def recent(self, n: int = 10) -> list[LatencyReport]:
        with self._lock:
            return list(self._history)[-n:]

    @staticmethod
    def _tail_is_degraded(tail: list[LatencyReport]) -> bool:
        """Pure function: degraded rule over an already-copied report tail."""
        if len(tail) < 3:
            return False
        return sum(1 for r in tail if r.degraded) >= len(tail) * 0.6

    def is_degraded(self) -> bool:
        return self._tail_is_degraded(self.recent(5))

    def summary(self) -> dict:
        # U.1 FIX: copy minimal state UNDER the lock, then compute OUTSIDE it.
        # The previous implementation held the lock while calling
        # is_degraded()/avg_latency()/fast_path_ratio(), which re-acquire the
        # same non-reentrant Lock -> guaranteed same-thread self-deadlock on
        # any non-empty history.
        with self._lock:
            if not self._history:
                return {"status": "no_data", "requests": 0}
            request_count = self._request_count
            fast_path_count = self._fast_path_count
            total_latency_ms = self._total_latency_ms
            latest_latency_ms = self._history[-1].total_ms
            tail = list(self._history)[-5:]

        degraded = self._tail_is_degraded(tail)
        avg = total_latency_ms / request_count if request_count else 0.0
        ratio = fast_path_count / request_count if request_count else 0.0
        return {
            "status": "degraded" if degraded else "healthy",
            "total_requests": request_count,
            "avg_latency_ms": round(avg, 1),
            "fast_path_ratio": round(ratio, 2),
            "latest_latency_ms": round(latest_latency_ms, 1),
        }

    @classmethod
    def singleton(cls) -> 'PerformanceTelemetry':
        return cls()

    @classmethod
    def reset_singleton(cls):
        with cls._lock_class:
            cls._instance = None
