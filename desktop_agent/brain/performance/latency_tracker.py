"""Latency budgeting and tracking for MYRAA execution pipeline.

Tracks per-stage latency, enforces budgets, and provides percentile reports.
Every pipeline stage (perception, context, decision, planning, execution)
gets a latency budget. If a stage exceeds its budget, it's flagged and
the system can degrade gracefully.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import deque


class LatencyBudget(Enum):
    """Per-stage latency budgets in milliseconds."""
    PERCEPTION = 50
    CONTEXT_FUSION = 100
    MEMORY_RETRIEVAL = 80
    AI_ROUTING = 30
    DECISION = 150
    PLANNING = 200
    EXECUTION = 500
    VERIFICATION = 100
    TOTAL_BUDGET = 1200

    # Fast path budgets (sub-millisecond targets)
    FAST_PATH_CACHE = 5
    FAST_PATH_TOOL = 50
    FAST_PATH_SIMPLE = 20


@dataclass(frozen=True)
class LatencySample:
    """A single latency measurement."""
    stage: str
    elapsed_ms: float
    timestamp: float
    budget_ms: float
    over_budget: bool
    metadata: dict = field(default_factory=dict)


@dataclass
class StageStats:
    """Aggregated statistics for a pipeline stage."""
    stage: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p99_ms: float = 0.0
    over_budget_count: int = 0
    budget_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def over_budget_ratio(self) -> float:
        return self.over_budget_count / self.count if self.count > 0 else 0.0


class LatencyTracker:
    """Thread-safe latency tracking with budget enforcement.

    Usage:
        tracker = LatencyTracker()
        with tracker.measure("perception", LatencyBudget.PERCEPTION):
            result = do_perception()
        report = tracker.report()
    """

    _instance: Optional['LatencyTracker'] = None
    _lock_class = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, max_samples: int = 10000, window_size: int = 100):
        if self._initialized:
            return
        self._initialized = True
        self._max_samples = max_samples
        self._window_size = window_size
        self._samples: deque[LatencySample] = deque(maxlen=max_samples)
        self._stage_windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._active_contexts: dict[str, float] = {}

    def measure(self, stage: str, budget: LatencyBudget, metadata: Optional[dict] = None):
        """Context manager that measures execution time."""
        return _MeasurementContext(self, stage, budget, metadata or {})

    def record(self, stage: str, elapsed_ms: float, budget: LatencyBudget,
               metadata: Optional[dict] = None):
        """Record a latency sample."""
        over_budget = elapsed_ms > budget.value
        sample = LatencySample(
            stage=stage,
            elapsed_ms=elapsed_ms,
            timestamp=time.time(),
            budget_ms=budget.value,
            over_budget=over_budget,
            metadata=metadata or {},
        )
        with self._lock:
            self._samples.append(sample)
            if stage not in self._stage_windows:
                self._stage_windows[stage] = deque(maxlen=self._window_size)
            self._stage_windows[stage].append(elapsed_ms)

    def get_stage_stats(self, stage: str) -> StageStats:
        """Get aggregated stats for a stage."""
        with self._lock:
            samples = [s for s in self._samples if s.stage == stage]
            if not samples:
                return StageStats(stage=stage)
            elapsed = sorted(s.elapsed_ms for s in samples)
            budget = samples[0].budget_ms
            over = sum(1 for s in samples if s.over_budget)
            n = len(elapsed)
            return StageStats(
                stage=stage,
                count=n,
                total_ms=sum(elapsed),
                min_ms=elapsed[0],
                max_ms=elapsed[-1],
                p50_ms=elapsed[int(n * 0.5)] if n > 1 else elapsed[0],
                p90_ms=elapsed[int(n * 0.9)] if n > 1 else elapsed[0],
                p99_ms=elapsed[int(n * 0.99)] if n > 1 else elapsed[0],
                over_budget_count=over,
                budget_ms=budget,
            )

    def report(self) -> dict[str, StageStats]:
        """Get stats for all tracked stages."""
        with self._lock:
            stages = set(s.stage for s in self._samples)
        return {stage: self.get_stage_stats(stage) for stage in stages}

    def total_latency(self) -> float:
        """Total pipeline latency for the most recent request."""
        with self._lock:
            if not self._samples:
                return 0.0
            recent = self._samples[-1]
            # Sum unique stages from the most recent window
            return sum(
                self._stage_windows.get(s, deque())[-1]
                for s in set(ss.stage for ss in list(self._samples)[-20:])
            )

    def is_degraded(self) -> bool:
        """Check if any stage is consistently over budget."""
        report = self.report()
        return any(stats.over_budget_ratio > 0.3 for stats in report.values() if stats.count > 5)

    def reset(self):
        """Reset all tracking data."""
        with self._lock:
            self._samples.clear()
            self._stage_windows.clear()

    @classmethod
    def singleton(cls) -> 'LatencyTracker':
        return cls()

    @classmethod
    def reset_singleton(cls):
        with cls._lock_class:
            cls._instance = None


class _MeasurementContext:
    """Context manager for latency measurement."""

    def __init__(self, tracker: LatencyTracker, stage: str,
                 budget: LatencyBudget, metadata: dict):
        self._tracker = tracker
        self._stage = stage
        self._budget = budget
        self._metadata = metadata
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        if exc_type is not None:
            self._metadata["error"] = str(exc_val)
        self._tracker.record(self._stage, elapsed_ms, self._budget, self._metadata)
        return False
