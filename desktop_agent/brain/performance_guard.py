"""
MYRAA Brain

Performance Regression Guard

Implements performance regression detection to prevent degradations in
system performance over time. Tracks performance baselines and alerts
when performance degrades beyond acceptable thresholds.
"""

from __future__ import annotations

import json
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import logging


logger = logging.getLogger(__name__)


class RegressionStatus(Enum):
    """Status of performance regression check."""
    HEALTHY = "healthy"          # Performance within acceptable bounds
    DEGRADED = "degraded"        # Performance degraded but within warning bounds
    REGRESSION = "regression"    # Significant performance regression detected
    IMPROVED = "improved"        # Performance improved significantly
    UNKNOWN = "unknown"          # Insufficient data to determine status


@dataclass
class PerformanceBaseline:
    """Baseline performance metrics for a component or operation."""
    operation_name: str
    baseline_mean: float
    baseline_std: float
    sample_count: int
    last_updated: float
    measurement_unit: str = "ms"  # milliseconds, seconds, etc.

    # Acceptable degradation thresholds (as percentage increase)
    warning_threshold_pct: float = 20.0   # 20% degradation triggers warning
    critical_threshold_pct: float = 50.0  # 50% degradation triggers regression

    # Improvement thresholds (as percentage decrease)
    improvement_threshold_pct: float = 30.0  # 30% improvement noted as improvement


@dataclass
class RegressionCheckResult:
    """Result of a performance regression check."""
    operation_name: str
    status: RegressionStatus
    current_value: float
    baseline_mean: float
    baseline_std: float
    change_pct: float
    sample_count: int
    message: str
    timestamp: float = field(default_factory=time.time)


class PerformanceRegressionGuard:
    """
    Guards against performance regressions by maintaining baselines and
    checking current performance against established baselines.
    """

    def __init__(self, baseline_file: Optional[Path] = None):
        """
        Initialize the performance regression guard.

        Args:
            baseline_file: Path to file for storing/loading baselines.
                          If None, uses default location.
        """
        self._lock = threading.RLock()
        self._baselines: Dict[str, PerformanceBaseline] = {}
        self._recent_measurements: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)  # Keep last 100 measurements
        )

        # Set baseline file path
        if baseline_file is None:
            self._baseline_file = Path(__file__).parent / "performance_baselines.json"
        else:
            self._baseline_file = baseline_file

        # Load existing baselines
        self._load_baselines()

    def record_measurement(self, operation_name: str, value: float):
        """
        Record a performance measurement for an operation.

        Args:
            operation_name: Name of the operation being measured
            value: Measured value (in consistent units, preferably milliseconds)
        """
        with self._lock:
            self._recent_measurements[operation_name].append(value)

    def check_regression(self, operation_name: str,
                        min_samples_for_check: int = 10) -> RegressionCheckResult:
        """
        Check if performance has regressed for an operation.

        Args:
            operation_name: Name of the operation to check
            min_samples_for_check: Minimum samples needed to perform check

        Returns:
            RegressionCheckResult indicating regression status
        """
        with self._lock:
            # Get recent measurements
            measurements = self._recent_measurements.get(operation_name)
            if not measurements or len(measurements) < min_samples_for_check:
                return RegressionCheckResult(
                    operation_name=operation_name,
                    status=RegressionStatus.UNKNOWN,
                    current_value=0.0,
                    baseline_mean=0.0,
                    baseline_std=0.0,
                    change_pct=0.0,
                    sample_count=len(measurements) if measurements else 0,
                    message=f"Insufficient samples for {operation_name}: {len(measurements) if measurements else 0}/{min_samples_for_check}"
                )

            # Calculate current statistics
            current_values = list(measurements)
            current_mean = sum(current_values) / len(current_values)
            current_std = (sum((x - current_mean) ** 2 for x in current_values) / len(current_values)) ** 0.5

            # Get baseline
            baseline = self._baselines.get(operation_name)
            if not baseline:
                # No baseline yet, establish one
                self._establish_baseline(operation_name, current_mean, current_std, len(current_values))
                return RegressionCheckResult(
                    operation_name=operation_name,
                    status=RegressionStatus.UNKNOWN,
                    current_value=current_mean,
                    baseline_mean=current_mean,
                    baseline_std=current_std,
                    change_pct=0.0,
                    sample_count=len(current_values),
                    message=f"Baseline established for {operation_name}"
                )

            # Calculate change percentage
            if baseline.baseline_mean == 0:
                change_pct = 0.0
            else:
                change_pct = ((current_mean - baseline.baseline_mean) / baseline.baseline_mean) * 100

            # Determine status
            status = RegressionStatus.HEALTHY
            message = f"Performance within normal bounds for {operation_name}"

            if change_pct > baseline.critical_threshold_pct:
                status = RegressionStatus.REGRESSION
                message = f"Performance regression detected for {operation_name}: {change_pct:.1f}% degradation"
            elif change_pct > baseline.warning_threshold_pct:
                status = RegressionStatus.DEGRADED
                message = f"Performance degradation warning for {operation_name}: {change_pct:.1f}% degradation"
            elif change_pct < -baseline.improvement_threshold_pct:
                status = RegressionStatus.IMPROVED
                message = f"Performance improvement detected for {operation_name}: {abs(change_pct):.1f}% improvement"

            return RegressionCheckResult(
                operation_name=operation_name,
                status=status,
                current_value=current_mean,
                baseline_mean=baseline.baseline_mean,
                baseline_std=baseline.baseline_std,
                change_pct=change_pct,
                sample_count=len(current_values),
                message=message
            )

    def _establish_baseline(self, operation_name: str, mean: float, std: float, sample_count: int):
        """Establish a new baseline for an operation."""
        baseline = PerformanceBaseline(
            operation_name=operation_name,
            baseline_mean=mean,
            baseline_std=std,
            sample_count=sample_count,
            last_updated=time.time()
        )
        self._baselines[operation_name] = baseline
        self._save_baselines()
        logger.info(f"Established performance baseline for {operation_name}: {mean:.2f} ± {std:.2f}")

    def update_baseline(self, operation_name: str, mean: float, std: float, sample_count: int):
        """Update an existing baseline with new values."""
        with self._lock:
            if operation_name in self._baselines:
                baseline = self._baselines[operation_name]
                baseline.baseline_mean = mean
                baseline.baseline_std = std
                baseline.sample_count = sample_count
                baseline.last_updated = time.time()
                self._save_baselines()
                logger.info(f"Updated performance baseline for {operation_name}: {mean:.2f} ± {std:.2f}")
            else:
                self._establish_baseline(operation_name, mean, std, sample_count)

    def get_baseline(self, operation_name: str) -> Optional[PerformanceBaseline]:
        """Get the baseline for an operation."""
        with self._lock:
            return self._baselines.get(operation_name)

    def get_all_baselines(self) -> Dict[str, PerformanceBaseline]:
        """Get all established baselines."""
        with self._lock:
            return self._baselines.copy()

    def _save_baselines(self):
        """Save baselines to file."""
        try:
            baselines_dict = {}
            for name, baseline in self._baselines.items():
                baselines_dict[name] = {
                    "operation_name": baseline.operation_name,
                    "baseline_mean": baseline.baseline_mean,
                    "baseline_std": baseline.baseline_std,
                    "sample_count": baseline.sample_count,
                    "last_updated": baseline.last_updated,
                    "measurement_unit": baseline.measurement_unit,
                    "warning_threshold_pct": baseline.warning_threshold_pct,
                    "critical_threshold_pct": baseline.critical_threshold_pct,
                    "improvement_threshold_pct": baseline.improvement_threshold_pct
                }

            with open(self._baseline_file, 'w') as f:
                json.dump(baselines_dict, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save performance baselines: {e}")

    def _load_baselines(self):
        """Load baselines from file."""
        try:
            if self._baseline_file.exists():
                with open(self._baseline_file, 'r') as f:
                    baselines_dict = json.load(f)

                for name, data in baselines_dict.items():
                    baseline = PerformanceBaseline(
                        operation_name=data["operation_name"],
                        baseline_mean=data["baseline_mean"],
                        baseline_std=data["baseline_std"],
                        sample_count=data["sample_count"],
                        last_updated=data["last_updated"],
                        measurement_unit=data.get("measurement_unit", "ms"),
                        warning_threshold_pct=data.get("warning_threshold_pct", 20.0),
                        critical_threshold_pct=data.get("critical_threshold_pct", 50.0),
                        improvement_threshold_pct=data.get("improvement_threshold_pct", 30.0)
                    )
                    self._baselines[name] = baseline

                logger.info(f"Loaded {len(self._baselines)} performance baselines")

        except Exception as e:
            logger.error(f"Failed to load performance baselines: {e}")
            # Continue with empty baselines


# Global performance regression guard instance
performance_guard = PerformanceRegressionGuard()


def record_performance(operation_name: str, value: float):
    """
    Record a performance measurement.

    Args:
        operation_name: Name of the operation being measured
        value: Measured value (preferably in milliseconds)
    """
    performance_guard.record_measurement(operation_name, value)


def check_performance_regression(operation_name: str,
                               min_samples_for_check: int = 10) -> RegressionCheckResult:
    """
    Check for performance regression in an operation.

    Args:
        operation_name: Name of the operation to check
        min_samples_for_check: Minimum samples needed to perform check

    Returns:
        RegressionCheckResult indicating regression status
    """
    return performance_guard.check_regression(operation_name, min_samples_for_check)


def get_performance_baseline(operation_name: str) -> Optional[PerformanceBaseline]:
    """Get the performance baseline for an operation."""
    return performance_guard.get_baseline(operation_name)


def reset_performance_baselines():
    """Reset all performance baselines (useful for testing)."""
    with performance_guard._lock:
        performance_guard._baselines.clear()
        performance_guard._recent_measurements.clear()
        if performance_guard._baseline_file.exists():
            performance_guard._baseline_file.unlink()
        logger.info("All performance baselines reset")


# Convenience decorators for automatic performance tracking
def track_performance(operation_name: str):
    """
    Decorator to automatically track performance of a function.

    Args:
        operation_name: Name to use for performance tracking
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                record_performance(operation_name, latency_ms)
        return wrapper
    return decorator


def track_async_performance(operation_name: str):
    """
    Decorator to automatically track performance of an async function.

    Args:
        operation_name: Name to use for performance tracking
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                record_performance(operation_name, latency_ms)
        return wrapper
    return decorator